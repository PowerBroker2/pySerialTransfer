import logging
import os
import json
import struct
from enum import Enum
from typing import Union

import serial
import serial.tools.list_ports
from array import array
from .CRC import CRC


class InvalidSerialPort(Exception):
    pass


class InvalidCallbackList(Exception):
    pass


class Status(Enum):
    CONTINUE        = 3
    NEW_DATA        = 2
    NO_DATA         = 1
    CRC_ERROR       = 0
    PAYLOAD_ERROR   = -1
    STOP_BYTE_ERROR = -2


START_BYTE = 0x7E
STOP_BYTE  = 0x81

MAX_PACKET_SIZE = 0xFE

BYTE_FORMATS = {'native':          '@',
                'native_standard': '=',
                'little-endian':   '<',
                'big-endian':      '>',
                'network':         '!'}

STRUCT_FORMAT_LENGTHS = {'c': 1,
                         'b': 1,
                         'B': 1,
                         '?': 1,
                         'h': 2,
                         'H': 2,
                         'i': 4,
                         'I': 4,
                         'l': 4,
                         'L': 4,
                         'q': 8,
                         'Q': 8,
                         'e': 2,
                         'f': 4,
                         'd': 8}

ARRAY_FORMAT_LENGTHS = {'b': 1,
                        'B': 1,
                        'u': 2,
                        'h': 2,
                        'H': 2,
                        'i': 2,
                        'I': 2,
                        'l': 4,
                        'q': 8,
                        'Q': 8,
                        'f': 4,
                        'd': 8}


class State(Enum):
    FIND_START_BYTE    = 0
    FIND_ID_BYTE       = 1
    FIND_OVERHEAD_BYTE = 2
    FIND_PAYLOAD_LEN   = 3
    FIND_PAYLOAD       = 4
    FIND_CRC           = 5
    FIND_END_BYTE      = 6


def constrain(val, min_, max_):
    if val < min_:
        return min_
    elif val > max_:
        return max_
    return val


def serial_ports():
    return [p.device for p in serial.tools.list_ports.comports(include_links=True)]


class SerialTransfer:
    def __init__(self, port, baud=115200, restrict_ports=True, debug=True, byte_format=BYTE_FORMATS['little-endian'], timeout=0.05, write_timeout=None):
        '''
        Description:
        ------------
        Initialize transfer class and connect to the specified USB device

        :param port: int or str - port the USB device is connected to
        :param baud: int        - baud (bits per sec) the device is configured for
        :param restrict_ports: bool - only allow port selection from auto
                                      detected list
        :param byte_format:    str  - format for values packed/unpacked via the
                                      struct package as defined by
                                      https://docs.python.org/3/library/struct.html#struct-format-strings
        :param timeout:       float - timeout (in s) to set on pySerial for maximum wait for a read from the OS
                                      default 50ms marries up with DEFAULT_TIMEOUT in SerialTransfer
        :param write_timeout: float - timeout (in s) to set on pySerial for maximum wait for a write operation to the serial port
                                      default None causes no write timeouts to be raised
        :return: void
        '''

        self.bytes_to_rec = 0
        self.pay_index = 0
        self.rec_overhead_byte = 0
        self.tx_buff = [' '] * MAX_PACKET_SIZE
        self.rx_buff = [' '] * MAX_PACKET_SIZE

        self.debug        = debug
        self.id_byte       = 0
        self.bytes_read    = 0
        self.status       = 0
        self.overhead_byte = 0xFF
        self.callbacks    = []
        self.byte_format  = byte_format

        self.state = State.FIND_START_BYTE
        
        if restrict_ports:
            self.port_name = None
            for p in serial_ports():
                if p == port or os.path.split(p)[-1] == port:
                    self.port_name = p
                    break

            if self.port_name is None:
                raise InvalidSerialPort('Invalid serial port specified.\
                    Valid options are {ports},  but {port} was provided'.format(
                    **{'ports': serial_ports(), 'port': port}))
        else:
            self.port_name = port

        self.crc = CRC()
        self.connection = serial.Serial()
        self.connection.port = self.port_name
        self.connection.baudrate = baud
        self.connection.timeout = timeout
        self.connection.write_timeout = write_timeout

    def open(self):
        '''
        Description:
        ------------
        Open serial port and connect to device if possible

        :return: bool - True if successful, else False
        '''

        if not self.connection.is_open:
            try:
                self.connection.open()
                return True
            except serial.SerialException as e:
                logging.exception(e)
                return False
        return True
    
    def set_callbacks(self, callbacks: Union[list[callable], tuple[callable]]):
        '''
        Description:
        ------------
        Specify a sequence of callback functions to be automatically called by
        self.tick() when a new packet is fully parsed. The ID of the parsed
        packet is then used to determine which callback needs to be called.

        :return: void
        '''
        
        if not isinstance(callbacks, (list, tuple)):
            raise InvalidCallbackList('Parameter "callbacks" is not of type "list" or "tuple"')
        
        if not all([callable(cb) for cb in callbacks]):
            raise InvalidCallbackList('One or more elements in "callbacks" are not callable')
        
        self.callbacks = callbacks

    def close(self):
        '''
        Description:
        ------------
        Close serial port

        :return: void
        '''
        if self.connection.is_open:
            self.connection.close()
    
    def tx_obj(self, val, start_pos=0, byte_format='', val_type_override=''):
        '''
        Description:
        -----------
        Insert an arbitrary variable's value into the TX buffer starting at the
        specified index
        
        :param val:         n/a - value to be inserted into TX buffer
        :param start_pos:   int - index of TX buffer where the first byte
                                  of the value is to be stored in
        :param byte_format: str - byte order, size and alignment according to
                                  https://docs.python.org/3/library/struct.html#struct-format-strings
        :param val_type_override: str - manually specify format according to
                                        https://docs.python.org/3/library/struct.html#format-characters
    
        :return: int - index of the last byte of the value in the TX buffer + 1,
                       None if operation failed
        '''
        
        if val_type_override:
            format_str = val_type_override
            
        else:
            if isinstance(val, str):
                val = val.encode()
                format_str = '%ds' % len(val)
                
            elif isinstance(val, dict):
                val = json.dumps(val).encode()
                format_str = '%ds' % len(val)
                
            elif isinstance(val, float):
                format_str = 'f'
                
            elif isinstance(val, bool):
                format_str = '?'
                
            elif isinstance(val, int):
                format_str = 'i'
                
            elif isinstance(val, list):
                for el in val:
                    start_pos = self.tx_obj(el, start_pos)
                
                return start_pos
            
            else:
                return None
      
        if byte_format:
            val_bytes = struct.pack(byte_format + format_str, val)
            
        else:
            if format_str == 'c':
                val_bytes = struct.pack(self.byte_format + format_str, bytes(str(val), "utf-8"))
            else:
                val_bytes = struct.pack(self.byte_format + format_str, val)

        return self.tx_struct_obj(val_bytes, start_pos)

    def tx_struct_obj(self, val_bytes, start_pos=0):
        '''
        Description:
        -----------
        Insert a byte array into the TX buffer starting at the
        specified index
        
        :param val_bytes:   bytearray - value to be inserted into TX buffer
        :param start_pos:   int - index of TX buffer where the first byte
                                  of the value is to be stored in
        :return: int - index of the last byte of the value in the TX buffer + 1,
                       None if operation failed
        '''
      
        for index in range(len(val_bytes)):
            self.tx_buff[index + start_pos] = val_bytes[index]
        
        return start_pos + len(val_bytes)

    def rx_obj(self, obj_type, start_pos=0, obj_byte_size=0, list_format=None, byte_format=''):
        '''
        Description:
        ------------
        Extract an arbitrary variable's value from the RX buffer starting at
        the specified index. If object_type is list, it is assumed that the
        list to be extracted has homogeneous element types where the common
        element type can neither be list, dict, nor string longer than a
        single char
        
        :param obj_type:      type or str - type of object to extract from the
                                            RX buffer or format string as
                                            defined by https://docs.python.org/3/library/struct.html#format-characters
        :param start_pos:     int  - index of TX buffer where the first byte
                                     of the value is to be stored in
        :param obj_byte_size: int  - number of bytes making up extracted object
        :param list_format:   char - array.array format char to represent the
                                     common list element type as defined by
                                     https://docs.python.org/3/library/array.html#module-array
        :param byte_format: str    - byte order, size and alignment according to
                                     https://docs.python.org/3/library/struct.html#struct-format-strings
    
        :return unpacked_response: obj - object extracted from the RX buffer,
                                         None if operation failed
        '''
        
        if (obj_type == str) or (obj_type == dict):
            buff = bytes(self.rx_buff[start_pos:(start_pos + obj_byte_size)])
            format_str = '%ds' % len(buff)
            
        elif obj_type == float:
            format_str = 'f'
            buff = bytes(self.rx_buff[start_pos:(start_pos + STRUCT_FORMAT_LENGTHS[format_str])])
            
        elif obj_type == int:
            format_str = 'i'
            buff = bytes(self.rx_buff[start_pos:(start_pos + STRUCT_FORMAT_LENGTHS[format_str])])
            
        elif obj_type == bool:
            format_str = '?'
            buff = bytes(self.rx_buff[start_pos:(start_pos + STRUCT_FORMAT_LENGTHS[format_str])])
            
        elif obj_type == list:
            buff = bytes(self.rx_buff[start_pos:(start_pos + obj_byte_size)])
            
            if list_format:
                arr = array(list_format, buff)
                return arr.tolist()
            
            else:
                return None
        
        elif isinstance(obj_type, str):
            buff = bytes(self.rx_buff[start_pos:(start_pos + STRUCT_FORMAT_LENGTHS[obj_type])])
            format_str = obj_type
        
        else:
            return None
        
        if byte_format:
            unpacked_response = struct.unpack(byte_format + format_str, buff)[0]
            
        else:
            unpacked_response = struct.unpack(self.byte_format + format_str, buff)[0]
        
        if (obj_type == str) or (obj_type == dict):
            # remove any trailing bytes of value 0 from data
            if 0 in unpacked_response:
                unpacked_response = unpacked_response[:unpacked_response.index(0)]

            unpacked_response = unpacked_response.decode('utf-8')
        
        if obj_type == dict:
            unpacked_response = json.loads(unpacked_response)
        
        return unpacked_response

    def calc_overhead(self, pay_len):
        '''
        Description:
        ------------
        Calculates the COBS (Consistent Overhead Stuffing) Overhead
        byte and stores it in the class's overhead_byte variable. This
        variable holds the byte position (within the payload) of the
        first payload byte equal to that of START_BYTE

        :param pay_len: int - number of bytes in the payload

        :return: void
        '''

        self.overhead_byte = 0xFF

        for i in range(pay_len):
            if self.tx_buff[i] == START_BYTE:
                self.overhead_byte = i
                break

    def find_last(self, pay_len):
        '''
        Description:
        ------------
        Finds last instance of the value START_BYTE within the given
        packet array

        :param pay_len: int - number of bytes in the payload

        :return: int - location of the last instance of the value START_BYTE
                       within the given packet array
        '''

        if pay_len <= MAX_PACKET_SIZE:
            for i in range(pay_len - 1, -1, -1):
                if self.tx_buff[i] == START_BYTE:
                    return i
        return -1

    def stuff_packet(self, pay_len):
        '''
        Description:
        ------------
        Enforces the COBS (Consistent Overhead Stuffing) ruleset across
        all bytes in the packet against the value of START_BYTE

        :param pay_len: int - number of bytes in the payload

        :return: void
        '''

        ref_byte = self.find_last(pay_len)

        if (not ref_byte == -1) and (ref_byte <= MAX_PACKET_SIZE):
            for i in range(pay_len - 1, -1, -1):
                if self.tx_buff[i] == START_BYTE:
                    self.tx_buff[i] = ref_byte - i
                    ref_byte = i

    def send(self, message_len, packet_id=0):
        '''
        Description:
        ------------
        Send a specified number of bytes in packetized form

        :param message_len: int - number of bytes from the tx_buff to send as
                                  payload in the packet
        :param packet_id:   int - ID of the packet to send                                  

        :return: bool - whether or not the operation was successful
        '''

        stack = []
        message_len = constrain(message_len, 0, MAX_PACKET_SIZE)

        try:
            self.calc_overhead(message_len)
            self.stuff_packet(message_len)
            found_checksum = self.crc.calculate(self.tx_buff, message_len)

            stack.append(START_BYTE)
            stack.append(packet_id)
            stack.append(self.overhead_byte)
            stack.append(message_len)

            for i in range(message_len):
                if isinstance(self.tx_buff[i], str):
                    val = ord(self.tx_buff[i])
                else:
                    val = int(self.tx_buff[i])

                stack.append(val)

            stack.append(found_checksum)
            stack.append(STOP_BYTE)

            stack = bytearray(stack)
            
            if self.open():
                self.connection.write(stack)

            return True

        except:
            import traceback
            traceback.print_exc()

            return False

    def unpack_packet(self):
        '''
        Description:
        ------------
        Unpacks all COBS-stuffed bytes within the array

        :return: void
        '''

        test_index = self.rec_overhead_byte

        if test_index <= MAX_PACKET_SIZE:
            while self.rx_buff[test_index]:
                delta = self.rx_buff[test_index]
                self.rx_buff[test_index] = START_BYTE
                test_index += delta

            self.rx_buff[test_index] = START_BYTE

    def available(self):
        '''
        Description:
        ------------
        Parses incoming serial data, analyzes packet contents,
        and reports errors/successful packet reception

        :return self.bytes_read: int - number of bytes read from the received
                                      packet
        '''

        if self.open():
            if self.connection.in_waiting:
                while self.connection.in_waiting:
                    rec_char = int.from_bytes(self.connection.read(),
                                             byteorder='big')

                    if self.state == State.FIND_START_BYTE:
                        if rec_char == START_BYTE:
                            self.state = State.FIND_ID_BYTE
                    
                    elif self.state == State.FIND_ID_BYTE:
                        self.id_byte = rec_char
                        self.state = State.FIND_OVERHEAD_BYTE

                    elif self.state == State.FIND_OVERHEAD_BYTE:
                        self.rec_overhead_byte = rec_char
                        self.state = State.FIND_PAYLOAD_LEN

                    elif self.state == State.FIND_PAYLOAD_LEN:
                        if rec_char > 0 and rec_char <= MAX_PACKET_SIZE:
                            self.bytes_to_rec = rec_char
                            self.pay_index = 0
                            self.state = State.FIND_PAYLOAD
                        else:
                            self.bytes_read = 0
                            self.state = State.FIND_START_BYTE
                            self.status = Status.PAYLOAD_ERROR
                            return self.bytes_read

                    elif self.state == State.FIND_PAYLOAD:
                        if self.pay_index < self.bytes_to_rec:
                            self.rx_buff[self.pay_index] = rec_char
                            self.pay_index += 1

                            # Try to receive as many more bytes as we can, but we might not get all of them
                            # if there is a timeout from the OS
                            if self.pay_index != self.bytes_to_rec:
                                more_bytes = list(self.connection.read(self.bytes_to_rec - self.pay_index))
                                next_index = self.pay_index + len(more_bytes)

                                self.rx_buff[self.pay_index:next_index] = more_bytes
                                self.pay_index = next_index

                            if self.pay_index == self.bytes_to_rec:
                                self.state = State.FIND_CRC

                    elif self.state == State.FIND_CRC:
                        found_checksum = self.crc.calculate(
                            self.rx_buff, self.bytes_to_rec)

                        if found_checksum == rec_char:
                            self.state = State.FIND_END_BYTE
                        else:
                            self.bytes_read = 0
                            self.state = State.FIND_START_BYTE
                            self.status = Status.CRC_ERROR
                            return self.bytes_read

                    elif self.state == State.FIND_END_BYTE:
                        self.state = State.FIND_START_BYTE

                        if rec_char == STOP_BYTE:
                            self.unpack_packet()
                            self.bytes_read = self.bytes_to_rec
                            self.status = Status.NEW_DATA
                            return self.bytes_read

                        self.bytes_read = 0
                        self.status = Status.STOP_BYTE_ERROR
                        return self.bytes_read

                    else:
                        logging.error('Undefined state: {}'.format(self.state))

                        self.bytes_read = 0
                        self.state = State.FIND_START_BYTE
                        return self.bytes_read
            else:
                self.bytes_read = 0
                self.status = Status.NO_DATA
                return self.bytes_read

        self.bytes_read = 0
        self.status = Status.CONTINUE
        return self.bytes_read
    
    def tick(self):
        '''
        Description:
        ------------
        Automatically parse all incoming packets, print debug statements if
        necessary (if enabled), and call the callback function that corresponds
        to the parsed packet's ID (if such a callback exists for that packet
        ID)

        :return: void
        '''
        
        if self.available():
            if self.id_byte < len(self.callbacks):
                self.callbacks[self.id_byte]()
            elif self.debug:
                logging.error('No callback available for packet ID {}'.format(self.id_byte))
            
            return True
        
        elif self.debug and self.status in [Status.CRC_ERROR, Status.PAYLOAD_ERROR, Status.STOP_BYTE_ERROR]:
            if self.status == Status.CRC_ERROR:
                err_str = 'CRC_ERROR'
            elif self.status == Status.PAYLOAD_ERROR:
                err_str = 'PAYLOAD_ERROR'
            elif self.status == Status.STOP_BYTE_ERROR:
                err_str = 'STOP_BYTE_ERROR'
            else:
                err_str = str(self.status)
                
            logging.error('{}'.format(err_str))
        
        return False
