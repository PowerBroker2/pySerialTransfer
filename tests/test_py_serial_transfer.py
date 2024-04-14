from unittest.mock import patch, MagicMock, PropertyMock

import pytest
import serial

from pySerialTransfer.pySerialTransfer import (
    InvalidCallbackList,
    InvalidSerialPort,
    SerialTransfer,
    State,
    BYTE_FORMATS, 
    MAX_PACKET_SIZE, 
    START_BYTE,
)


@pytest.fixture(autouse=True)
def mock_serial():
    with patch('serial.Serial') as mock:
        mock.return_value.is_open = False
        yield mock
        
        
@pytest.fixture(autouse=True)
def mock_comports():
    with patch('serial.tools.list_ports.comports') as mock:
        mock.return_value = [MagicMock(device='COM3')]
        yield mock
        
        
def make_incoming_byte_stream(incoming_byte_values: list[int], connection: MagicMock) -> list[bytes]:
    """Create a list of bytes objects from a list of byte values, set the in_waiting property of the connection mock, and
    set the read side effect of the connection mock to return the list of bytes objects. 
    Return the list of bytes objects."""
    incoming_bytes = [bytes([b]) for b in incoming_byte_values]
    type(connection).in_waiting = PropertyMock(side_effect=[True] * len(incoming_bytes) + [False])
    connection.read.side_effect = incoming_bytes
    return incoming_bytes
        
        
def test_port_is_required():
    """Test that the SerialTransfer class raises a TypeError when no port is passed"""
    with pytest.raises(TypeError):
        SerialTransfer()


def test_init_defaults():
    """Basic test for SerialTransfer class initialization defaults"""
    st = SerialTransfer('COM3')
    assert st.port_name == 'COM3'
    assert st.debug is True
    assert st.byte_format == BYTE_FORMATS['little-endian']
    assert st.connection.port == 'COM3'
    assert st.connection.baudrate == 115200
    assert st.connection.timeout == 0.05
    assert st.connection.write_timeout is None
    assert st.state == State.FIND_START_BYTE


def test_raises_exception_on_invalid_port():
    """Test that the SerialTransfer class raises an InvalidSerialPort exception when an invalid port is passed."""
    with pytest.raises(InvalidSerialPort):
        SerialTransfer('NOT_A_REAL_PORT')
    

def test_port_restriction_can_be_bypassed(mock_comports):
    """Test that the SerialTransfer class can be initialized with an invalid port if the port restriction is bypassed"""
    st = SerialTransfer(port='NOT_A_REAL_PORT', restrict_ports=False)
    assert mock_comports.call_count == 0
    assert st.port_name == 'NOT_A_REAL_PORT'


@pytest.mark.parametrize('port, baud, timeout, write_timeout', [
    ('COM3', 9600, 0.1, 0.1),
    ('COM4', 115200, 0.05, 0.05),
    ('COM5', 57600, 0.01, 0.01),
    ('COM6', 38400, 0.1, 0.1),
    ('COM7', 19200, 0.05, 0.05),
])    
def test_serial_params_can_be_overridden(mock_comports, port, baud, timeout, write_timeout):
    """Test that the SerialTransfer class can be initialized with custom serial parameters"""
    mock_comports.return_value = [MagicMock(device=port)]
    st = SerialTransfer(port=port, baud=baud, timeout=timeout, write_timeout=write_timeout)
    assert st.port_name == port
    assert st.connection.baudrate == baud
    assert st.connection.timeout == timeout
    assert st.connection.write_timeout == write_timeout
    
    
def test_open_returns_true_on_success(mock_serial):
    """Test that the open method returns True when the serial connection is successfully opened"""
    st = SerialTransfer('COM3')
    st.connection.open.return_value = True
    result = st.open()
    
    assert result is True
    
    
def test_open_returns_false_on_serial_exception(mock_serial):
    """Test that the open method returns False when the serial connection raises an exception"""
    st = SerialTransfer('COM3')
    st.connection.open.side_effect = serial.SerialException
    result = st.open()
    
    assert result is False
    

def test_open_on_open_connection(mock_serial):
    """Test that the open method does not call the connection.open method if the connection is already open"""
    st = SerialTransfer('COM3')
    st.connection.is_open = True
    result = st.open()
    
    assert st.connection.open.call_count == 0


def test_close_closes_connection(mock_serial):
    """Test that the close method calls the connection.close method"""
    st = SerialTransfer('COM3')
    st.connection.is_open = True
    st.close()
    
    assert st.connection.close.call_count == 1


@pytest.mark.parametrize('tx_buff, payload_length, expected_overhead_byte', [
    ([START_BYTE, 0x01, 0x02, 0x03, 0x04], 5, 0x00),  # found in 1st byte
    ([0x01, START_BYTE, 0x03, 0x04, 0x05], 5, 0x01),  # found in 2nd byte
    ([0x02, 0x03, START_BYTE, 0x05, 0x06], 5, 0x02),  # found in 3rd byte
    ([0x03, 0x04, 0x05, START_BYTE, 0x07], 5, 0x03),  # found in 4th byte
    ([0x04, 0x05, 0x06, 0x07, START_BYTE], 5, 0x04),  # found in 5th byte
    ([0x05, 0x06, 0x07, 0x08, 0x09], 5, 0xFF),  # not found in payload
    ([0x06, 0x07, 0x08, 0x09, START_BYTE], 4, 0xFF),  # not present within the payload length
])
def test_calc_overhead_basic(tx_buff, payload_length, expected_overhead_byte):
    """Test that the calc_overhead method sets the overhead property to the byte position in the payload of the first 
    payload byte equal to the START_BYTE value"""
    st = SerialTransfer('COM3')
    st.tx_buff = tx_buff
    st.calc_overhead(payload_length)
    
    assert st.overhead_byte == expected_overhead_byte


@pytest.mark.parametrize('tx_buff, payload_length, expected_position', [
    ([START_BYTE, START_BYTE, START_BYTE, START_BYTE, START_BYTE], 5, 4),  # all bytes are START_BYTE, last byte pos is payload length -1 
    ([START_BYTE, START_BYTE, START_BYTE, 0x01, 0x01], 5, 2),  # first 3 bytes are START_BYTE, last byte pos is 2
    ([START_BYTE, START_BYTE, START_BYTE, 0x01, START_BYTE], 4, 2),  # trailing START_BYTE is ignored as it is not part of the payload
    ([START_BYTE, START_BYTE, START_BYTE, START_BYTE, START_BYTE], MAX_PACKET_SIZE + 1, -1),  # special case: payload length exceeds MAX_PACKET_SIZE, return -1
    
])
def test_find_last(tx_buff, payload_length, expected_position):
    """Test that the find_last method returns the index of the last occurrence of the START_BYTE value in the tx_buff"""
    st = SerialTransfer('COM3')
    st.tx_buff = tx_buff
    result = st.find_last(payload_length)
    
    assert result == expected_position
    

def test_stuff_packet():
    # Create an instance of SerialTransfer
    st = SerialTransfer('COM3')

    # Set up a specific tx_buff
    st.tx_buff = [START_BYTE if i % 2 == 0 else i for i in range(MAX_PACKET_SIZE)]

    # Call stuff_packet with a specific payload length
    st.stuff_packet(MAX_PACKET_SIZE)

    # Assert that tx_buff has been modified as expected
    expected_tx_buff = [2, 1, 2, 3, 2, 5, 2, 7, 2, 9, 2, 11, 2, 13, 2, 15, 2, 17, 2, 19, 2, 21, 2, 23, 2, 25, 2, 27, 2, 29, 2, 31, 2, 33, 2, 35, 2, 37, 2, 39, 2, 41, 2, 43, 2, 45, 2, 47, 2, 49, 2, 51, 2, 53, 2, 55, 2, 57, 2, 59, 2, 61, 2, 63, 2, 65, 2, 67, 2, 69, 2, 71, 2, 73, 2, 75, 2, 77, 2, 79, 2, 81, 2, 83, 2, 85, 2, 87, 2, 89, 2, 91, 2, 93, 2, 95, 2, 97, 2, 99, 2, 101, 2, 103, 2, 105, 2, 107, 2, 109, 2, 111, 2, 113, 2, 115, 2, 117, 2, 119, 2, 121, 2, 123, 2, 125, 2, 127, 2, 129, 2, 131, 2, 133, 2, 135, 2, 137, 2, 139, 2, 141, 2, 143, 2, 145, 2, 147, 2, 149, 2, 151, 2, 153, 2, 155, 2, 157, 2, 159, 2, 161, 2, 163, 2, 165, 2, 167, 2, 169, 2, 171, 2, 173, 2, 175, 2, 177, 2, 179, 2, 181, 2, 183, 2, 185, 2, 187, 2, 189, 2, 191, 2, 193, 2, 195, 2, 197, 2, 199, 2, 201, 2, 203, 2, 205, 2, 207, 2, 209, 2, 211, 2, 213, 2, 215, 2, 217, 2, 219, 2, 221, 2, 223, 2, 225, 2, 227, 2, 229, 2, 231, 2, 233, 2, 235, 2, 237, 2, 239, 2, 241, 2, 243, 2, 245, 2, 247, 2, 249, 2, 251, 0, 253]
    assert st.tx_buff == expected_tx_buff


def test_stuff_packet_pay_length_exceeds_max_packet_size():
    """Test that the stuff_packet method does not modify the tx_buff when the payload length exceeds MAX_PACKET_SIZE"""
    # Create an instance of SerialTransfer
    st = SerialTransfer('COM3')

    # Set up a specific tx_buff
    start_tx_buff = [START_BYTE if i % 2 == 0 else i for i in range(MAX_PACKET_SIZE)]
    st.tx_buff = start_tx_buff.copy()

    # Call stuff_packet with a payload length that exceeds MAX_PACKET_SIZE
    st.stuff_packet(MAX_PACKET_SIZE + 1)

    # Assert that tx_buff has been modified as expected
    assert st.tx_buff == start_tx_buff


def test_unpack_packet():
    # Create an instance of SerialTransfer
    st = SerialTransfer('COM3')

    # Set up a specific rx_buff
    st.rx_buff = [2, 1, 2, 3, 2, 5, 2, 7, 2, 9, 2, 11, 2, 13, 2, 15, 2, 17, 2, 19, 2, 21, 2, 23, 2, 25, 2, 27, 2, 29, 2, 31, 2, 33, 2, 35, 2, 37, 2, 39, 2, 41, 2, 43, 2, 45, 2, 47, 2, 49, 2, 51, 2, 53, 2, 55, 2, 57, 2, 59, 2, 61, 2, 63, 2, 65, 2, 67, 2, 69, 2, 71, 2, 73, 2, 75, 2, 77, 2, 79, 2, 81, 2, 83, 2, 85, 2, 87, 2, 89, 2, 91, 2, 93, 2, 95, 2, 97, 2, 99, 2, 101, 2, 103, 2, 105, 2, 107, 2, 109, 2, 111, 2, 113, 2, 115, 2, 117, 2, 119, 2, 121, 2, 123, 2, 125, 2, 127, 2, 129, 2, 131, 2, 133, 2, 135, 2, 137, 2, 139, 2, 141, 2, 143, 2, 145, 2, 147, 2, 149, 2, 151, 2, 153, 2, 155, 2, 157, 2, 159, 2, 161, 2, 163, 2, 165, 2, 167, 2, 169, 2, 171, 2, 173, 2, 175, 2, 177, 2, 179, 2, 181, 2, 183, 2, 185, 2, 187, 2, 189, 2, 191, 2, 193, 2, 195, 2, 197, 2, 199, 2, 201, 2, 203, 2, 205, 2, 207, 2, 209, 2, 211, 2, 213, 2, 215, 2, 217, 2, 219, 2, 221, 2, 223, 2, 225, 2, 227, 2, 229, 2, 231, 2, 233, 2, 235, 2, 237, 2, 239, 2, 241, 2, 243, 2, 245, 2, 247, 2, 249, 2, 251, 0, 253]
    
    # Call unpack_packet
    st.unpack_packet()
    
    # Assert that rx_payload has been modified as expected
    expected_rx_payload = st.tx_buff = [START_BYTE if i % 2 == 0 else i for i in range(MAX_PACKET_SIZE)]
    assert st.rx_buff == expected_rx_payload

    
def test_set_callbacks():
    """Test that the set_callbacks method sets the callback property to the passed callbacks"""
    # Create an instance of SerialTransfer
    st = SerialTransfer('COM3')
    
    def callback_1():
        pass
    
    def callback_2():
        pass
    
    # Set up a specific callbacks list
    callbacks = [callback_1, callback_2]
    
    # Call set_callbacks
    st.set_callbacks(callbacks)
    
    # Assert that the callbacks property has been set as expected
    assert st.callbacks == callbacks    
        

def test_set_callbacks_raises_on_invalid_callback_types():
    """Test that the set_callbacks method raises an InvalidCallbackList when the callbacks parameter is not a list"""
    # Create an instance of SerialTransfer
    st = SerialTransfer('COM3')
    
    # Set up callbacks with a non-list value
    callbacks = 'foo'
    
    # Call set_callbacks
    with pytest.raises(InvalidCallbackList):
        st.set_callbacks(callbacks) #  type: ignore


def test_set_callbacks_raises_on_non_callable_callbacks():
    """Test that the set_callbacks method raises a TypeError when the callbacks parameter is not a list"""
    # Create an instance of SerialTransfer
    st = SerialTransfer('COM3')

    # Set up a specific callbacks dictionary
    callbacks = ['foo', 'bar']

    # Call set_callbacks
    with pytest.raises(InvalidCallbackList):
        st.set_callbacks(callbacks)  # type: ignore
    
    
@pytest.mark.parametrize("val, start_pos, byte_format, val_type_override, expected", [
    ("test", 0, '', '', 4),
    ({"key": "value"}, 0, '', '', 16),
    (1.23, 0, '', '', 4),
    (123, 0, '', '', 4),
    (True, 0, '', '', 1),
    (['a', 'b', 'c'], 0, '', '', 3),
    ("test", 0, '>', '', 4),
    (123, 0, '', 'h', 2),
    pytest.param(
        '11', 0, '', 'c', 1, 
        marks=pytest.mark.xfail(
            reason="tx_obj does not handle gracefully handle exceptions when 'c' type is manually declared"
        )
    ),
])
def test_tx_obj_known_types(val, start_pos, byte_format, val_type_override, expected):
    """Test that the tx_obj method returns the expected number of bytes for known types"""
    st = SerialTransfer('COM3')
    result = st.tx_obj(val, start_pos, byte_format, val_type_override)
    assert result == expected


def test_tx_obj_unhandled_type():
    """Test that the tx_obj returns None when an unhandled type is passed"""
    st = SerialTransfer('COM3')
    return_value = st.tx_obj(object, 0, '', '')
    assert return_value is None
    
    
def test_tx_obj_val_type_override():
    """Test that the tx_obj method uses the val_type_override parameter when it is passed"""
    st = SerialTransfer('COM3')
    result = st.tx_obj(123, 0, '', 'h')
    assert result == 2


@pytest.mark.parametrize("rx_bytes, obj_type, start_pos, byte_format, expected", [
    ([116, 101, 115, 116], str, 0, '', "test"),
    ([123, 34, 107, 101, 121, 34, 58, 32, 34, 118, 97, 108, 117, 101, 34, 125], dict, 0, '', {"key": "value"}),
    ([164, 112, 157, 63], float, 0, '', 1.23),
    ([123, 0, 0, 0], int, 0, '', 123),
    ([1, 0, 0, 0], bool, 0, '', True),
    ([116, 101, 115, 116], str, 0, '>', "test"),
])
def test_rx_obj_known_types(rx_bytes, obj_type, start_pos, byte_format, expected):
    """Test that the rx_obj method returns the expected value for known types"""
    st = SerialTransfer('COM3')
    st.rx_buff = rx_bytes + [' '] * (MAX_PACKET_SIZE - len(rx_bytes))  # First set the rx_buff
    result = st.rx_obj(obj_type, start_pos=start_pos, obj_byte_size=len(rx_bytes), byte_format=byte_format)  # Then receive it
    if isinstance(result, float):
        assert pytest.approx(result, 0.01) == expected
    else:
        assert result == expected


def test_rx_obj_unhandled_type():
    """Test that the rx_obj returns None when an unhandled type is passed"""
    st = SerialTransfer('COM3')
    return_value = st.rx_obj(object)
    assert return_value is None    
    
    
def test_send():
    # Create an instance of SerialTransfer
    st = SerialTransfer('COM3')

    # Mock the write method of the serial object
    st.connection.write = MagicMock()

    # Define the message to be sent
    message = [1, 2, 3, 4, 5]
    message_len = len(message)
    message_crc = 0x80

    # Add the message to the tx_buff
    st.tx_buff[:message_len] = message

    # Call the send method
    st.send(message_len)

    # Check that the write method was called with the correct argument
    st.connection.write.assert_called_once()

    # Get the actual value that was written
    actual_value = st.connection.write.call_args[0][0]

    # The expected value is the message wrapped in a bytearray, with additional bytes for the packet structure
    expected_value = bytearray([0x7E, 0, 0xFF, message_len] + message + [message_crc, 0x81])

    # Assert that the actual value matches the expected value
    assert actual_value == expected_value


def test_available_with_no_data():
    st = SerialTransfer('COM3')
    incoming_byte_values = []
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    assert st.available() == 0


def test_available_with_new_data():
    st = SerialTransfer('COM3')
    incoming_byte_values = [0x7E, 0, 0xFF, 0x04, 0x01, 0x02, 0x03, 0x04, 0xC8, 0x81]
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    assert st.available() == 4


def test_available_with_crc_error():
    st = SerialTransfer('COM3')
    incoming_byte_values = [0x7E, 0x00, 0xFF, 0x04, 0x01, 0x02, 0x03, 0x04, 0x81, 0x81]
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    assert st.available() == 0


def test_available_with_stop_byte_error():
    st = SerialTransfer('COM3')
    incoming_byte_values = [0x7E, 0, 0xFF, 0x04, 0x01, 0x02, 0x03, 0x04, 0x80, 0x7E]
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    assert st.available() == 0
    

def test_tick_with_valid_data():
    """Test that the tick method returns True when valid data is received."""
    st = SerialTransfer('COM3')
    incoming_byte_values = [0x7E, 0, 0xFF, 0x04, 0x01, 0x02, 0x03, 0x04, 0xC8, 0x81]
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    result = st.tick()
    assert result is True

    
def test_tick_with_valid_data_and_callback():
    """Test that the tick method calls the callback function when valid data is received."""
    callback = MagicMock()
    st = SerialTransfer('COM3')
    st.set_callbacks([callback])
    incoming_byte_values = [0x7E, 0, 0xFF, 0x04, 0x01, 0x02, 0x03, 0x04, 0xC8, 0x81]
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    result = st.tick()
    assert result is True
    callback.assert_called_once()
    
    
def test_set_callbacks_with_non_callable_items():
    """Test that set_callbacks raises an exception when non callable callbacks are passed, and that the callbacks 
    property is not modified."""
    st = SerialTransfer('COM3')
    original_callbacks = st.callbacks
    
    def i_am_callable():
        pass
    
    with pytest.raises(InvalidCallbackList):
        st.set_callbacks(["i'm not callable", i_am_callable])
    assert st.callbacks == original_callbacks
    

def test_set_callbacks_with_non_iterable():
    """Test that set_callbacks raises an exception when non list|tuple callbacks are passed, and that the callbacks
    property is not modified."""
    st = SerialTransfer('COM3')
    original_callbacks = st.callbacks
    
    with pytest.raises(InvalidCallbackList):
        st.set_callbacks(True)  # type: ignore
    assert st.callbacks == original_callbacks
    
    
@pytest.mark.parametrize('incoming_byte_values, expected_print_str', [
    ([0x7E, 0, 0xFF, 0x04, 0x01, 0x02, 0x03, 0x04, 0xFF, 0x81], 'CRC_ERROR'),
    ([0x7E, 0, 0xFF, 0x04, 0x01, 0x02, 0x03, 0x04, 0xC8, 0x7E], 'STOP_BYTE_ERROR'),
    ([0x7E, 0, 0xFF, 0xFF, 0x01, 0x02, 0x03, 0x04, 0xC8, 0x81], 'PAYLOAD_ERROR'),
])
def test_tick_with_invalid_data(caplog, incoming_byte_values, expected_print_str):
    """Test that the tick method returns False when invalid data is received."""
    st = SerialTransfer('COM3')
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    result = st.tick()
    assert result is False
    assert len(caplog.records) == 1
    assert caplog.records[0].message == f"{expected_print_str}"
    assert caplog.records[0].levelname == 'ERROR'


@pytest.mark.parametrize('incoming_byte_values, expected_print_str', [
    ([0x7E, 0, 0xFF, 0x04, 0x01, 0x02, 0x03, 0x04, 0xFF, 0x81], 'CRC_ERROR'),
    ([0x7E, 0, 0xFF, 0x04, 0x01, 0x02, 0x03, 0x04, 0xC8, 0x7E], 'STOP_BYTE_ERROR'),
    ([0x7E, 0, 0xFF, 0xFF, 0x01, 0x02, 0x03, 0x04, 0xC8, 0x81], 'PAYLOAD_ERROR'),
])
def test_tick_with_invalid_data_debug_false(caplog, incoming_byte_values, expected_print_str):
    """Test that the tick method does not print when presented with invalid data and debug is False."""
    st = SerialTransfer('COM3', debug=False)
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    result = st.tick()
    assert result is False
    assert len(caplog.records) == 0

    