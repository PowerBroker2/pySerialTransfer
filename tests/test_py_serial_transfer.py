from __future__ import annotations

from unittest.mock import patch, MagicMock, PropertyMock

import pytest
import serial

from pySerialTransfer.pySerialTransfer import (
    InvalidCallbackList,
    InvalidSerialPort,
    SerialTransfer,
    State,
    Status,
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
    stream = bytes(incoming_byte_values)
    type(connection).in_waiting = PropertyMock(side_effect=[len(stream), 0])
    connection.read.side_effect = [stream] if stream else []
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


def test_legacy_stuffing_helpers_are_noops():
    st = SerialTransfer('COM3')
    payload = bytearray([START_BYTE, 1, START_BYTE])
    st.tx_buff = payload[:]
    st.calc_overhead(len(payload))
    assert st.overhead_byte == 0xFF
    assert st.find_last(len(payload)) == -1
    st.stuff_packet(len(payload))
    assert st.tx_buff == payload


def test_unpack_packet_is_compatibility_noop():
    st = SerialTransfer('COM3')
    st.rx_buff = bytearray([0x7E, 0, 0x81])
    st.bytes_read = 3
    before = st.rx_buff[:]
    st.unpack_packet()
    assert st.rx_buff == before


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
    ('A', 0, '', 'c', 1),
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
    st.bytes_read = len(rx_bytes)
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
    st.connection.write = MagicMock(side_effect=len)

    # Define the message to be sent
    message = [1, 2, 3, 4, 5]
    message_len = len(message)

    # Add the message to the tx_buff
    st.tx_buff[:message_len] = message

    # Call the send method
    assert st.send(message_len)

    # Check that the write method was called with the correct argument
    st.connection.write.assert_called_once()

    # Get the actual value that was written
    actual_value = st.connection.write.call_args[0][0]

    # The expected value is the message wrapped in a bytearray, with additional bytes for the packet structure
    expected_value = bytearray([0x7E, 0, message_len] + message + [0xBF])

    # Assert that the actual value matches the expected value
    assert actual_value == expected_value


def test_available_with_no_data():
    st = SerialTransfer('COM3')
    incoming_byte_values = []
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    assert st.available() == 0


def test_available_with_new_data():
    st = SerialTransfer('COM3')
    incoming_byte_values = [0x7E, 0, 0x04, 0x01, 0x02, 0x03, 0x04, 0x6A]
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    assert st.available() == 4


def test_available_with_crc_error():
    st = SerialTransfer('COM3')
    incoming_byte_values = [0x7E, 0x00, 0x04, 0x01, 0x02, 0x03, 0x04, 0x6B]
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    assert st.available() == 0


def test_available_does_not_require_stop_byte():
    st = SerialTransfer('COM3')
    incoming_byte_values = [0x7E, 0, 0x04, 0x01, 0x02, 0x03, 0x04, 0x6A]
    make_incoming_byte_stream(incoming_byte_values, st.connection)
    assert st.available() == 4
    assert st.status == Status.NEW_DATA


def test_tick_with_valid_data():
    """Test that the tick method returns True when valid data is received."""
    st = SerialTransfer('COM3')
    incoming_byte_values = [0x7E, 0, 0x04, 0x01, 0x02, 0x03, 0x04, 0x6A]
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    result = st.tick()
    assert result is True

    
def test_tick_with_valid_data_and_callback():
    """Test that the tick method calls the callback function when valid data is received."""
    callback = MagicMock()
    st = SerialTransfer('COM3')
    st.set_callbacks([callback])
    incoming_byte_values = [0x7E, 0, 0x04, 0x01, 0x02, 0x03, 0x04, 0x6A]
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
    ([0x7E, 0, 0x04, 0x01, 0x02, 0x03, 0x04, 0x6B], 'CRC_ERROR'),
    ([0x7E, 0, 0x04, 0x01, 0x02, 0x03, 0x04, 0x6B], 'CRC_ERROR'),
    ([0x7E, 0, 0x00, 0x01], 'CRC_ERROR'),
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
    ([0x7E, 0, 0x04, 0x01, 0x02, 0x03, 0x04, 0x6B], 'CRC_ERROR'),
    ([0x7E, 0, 0x04, 0x01, 0x02, 0x03, 0x04, 0x6B], 'CRC_ERROR'),
    ([0x7E, 0, 0x00, 0x01], 'CRC_ERROR'),
])
def test_tick_with_invalid_data_debug_false(caplog, incoming_byte_values, expected_print_str):
    """Test that the tick method does not print when presented with invalid data and debug is False."""
    st = SerialTransfer('COM3', debug=False)
    make_incoming_byte_stream(incoming_byte_values=incoming_byte_values, connection=st.connection)
    result = st.tick()
    assert result is False
    assert len(caplog.records) == 0



def test_available_accepts_zero_length_packet():
    st = SerialTransfer('COM3')
    make_incoming_byte_stream([0x7E, 0, 0, 0], st.connection)
    assert st.available() == 0
    assert st.status == Status.NEW_DATA
    assert st.bytes_read == 0


def test_available_accepts_255_byte_payload():
    st = SerialTransfer('COM3')
    payload = list(range(255))
    frame = [0x7E, 1, 0xFF] + payload + [0xA2]
    make_incoming_byte_stream(frame, st.connection)
    assert st.available() == 255
    assert st.status == Status.NEW_DATA
    assert list(st.rx_buff) == payload


def test_tick_dispatches_zero_length_packet():
    callback = MagicMock()
    st = SerialTransfer('COM3')
    st.set_callbacks([callback])
    make_incoming_byte_stream([0x7E, 0, 0, 0], st.connection)
    assert st.tick() is True
    callback.assert_called_once()



def test_available_reports_stale_partial_packet():
    st = SerialTransfer('COM3', inter_byte_timeout=0.01)
    make_incoming_byte_stream([], st.connection)
    st.state = State.FIND_ID_BYTE
    st._last_byte_time = 1.0
    with patch('pySerialTransfer.pySerialTransfer.time.monotonic', return_value=2.0):
        assert st.available() == 0
    assert st.status == Status.STALE_PACKET_ERROR



def test_available_buffers_back_to_back_packets():
    st = SerialTransfer('COM3')
    first = [0x7E, 0, 4, 1, 2, 3, 4, 0x6A]
    second = [0x7E, 1, 4, 4, 3, 2, 1, 0x9B]
    make_incoming_byte_stream(first + second, st.connection)
    assert st.available() == 4
    assert st.id_byte == 0
    assert st.available() == 4
    assert st.id_byte == 1
    assert list(st.rx_buff[:4]) == [4, 3, 2, 1]


def test_send_completes_partial_writes():
    st = SerialTransfer('COM3')
    st.connection.write.side_effect = [2, 2]
    assert st.send(0) is True
    assert st.connection.write.call_count == 2


def test_send_stops_when_serial_write_makes_no_progress():
    st = SerialTransfer('COM3')
    st.connection.write.side_effect = [2, 0]
    assert st.send(0) is False
    assert st.connection.write.call_count == 2



def test_available_parses_frame_across_poll_calls():
    st = SerialTransfer('COM3')
    first = bytes([0x7E, 0, 4])
    second = bytes([1, 2, 3, 4, 0x6A])

    type(st.connection).in_waiting = PropertyMock(side_effect=[len(first), 0])
    st.connection.read.side_effect = [first]
    assert st.available() == 0
    assert st.status == Status.CONTINUE

    type(st.connection).in_waiting = PropertyMock(side_effect=[len(second), 0])
    st.connection.read.side_effect = [second]
    assert st.available() == 4
    assert st.status == Status.NEW_DATA
    assert list(st.rx_buff[:4]) == [1, 2, 3, 4]



def test_rx_obj_unpacks_struct_list_values():
    st = SerialTransfer('COM3')
    st.rx_buff[:8] = bytes([1, 0, 0, 0, 254, 255, 255, 255])
    st.bytes_read = 8
    assert st.rx_obj(list, obj_byte_size=8, list_format='i') == [1, -2]


def test_rx_obj_rejects_incomplete_list_element():
    st = SerialTransfer('COM3')
    st.rx_buff[:3] = bytes([1, 0, 0])
    st.bytes_read = 3
    assert st.rx_obj(list, list_format='i') is None


def test_tx_obj_character_and_invalid_values():
    st = SerialTransfer('COM3')
    assert st.tx_obj('A', val_type_override='c') == 1
    assert st.tx_buff[0] == ord('A')
    before = st.tx_buff[:]
    assert st.tx_obj('AB', val_type_override='c') is None
    assert st.tx_buff == before


def test_tx_obj_list_failure_rolls_back_partial_bytes():
    st = SerialTransfer('COM3')
    before = st.tx_buff[:]
    assert st.tx_obj([1, object()]) is None
    assert st.tx_buff == before


def test_packet_id_is_published_only_after_valid_crc():
    st = SerialTransfer('COM3')
    st.id_byte = 7
    crc_value = st.crc.update(st.crc.update(0, 9), 0)
    for value in (START_BYTE, 9, 0, crc_value ^ 1):
        st._process_byte(value, 1.0)
    assert st.status == Status.CRC_ERROR
    assert st.id_byte == 7


@pytest.mark.parametrize('timeout', [0, -0.1, float('nan'), float('inf')])
def test_constructor_rejects_invalid_inter_byte_timeout(timeout):
    with pytest.raises(ValueError):
        SerialTransfer('COM3', inter_byte_timeout=timeout)



def test_send_rejects_negative_payload_length():
    st = SerialTransfer('COM3')
    assert st.send(-1) is False
    st.connection.write.assert_not_called()



def test_invalid_port_message_lists_ports_once(mock_comports):
    with pytest.raises(InvalidSerialPort, match="Available ports: COM3"):
        SerialTransfer('MISSING')
    assert mock_comports.call_count == 1






def test_send_rejects_payload_length_larger_than_buffer():
    st = SerialTransfer('COM3')
    st.tx_buff = bytearray([1, 2])
    assert st.send(3) is False
    st.connection.write.assert_not_called()
