import os
import json
import struct
import serial
import serial.tools.list_ports
from array import array
from .CRC import CRC


class InvalidSerialPort(Exception):
    pass


class InvalidCallbackList(Exception):
    pass


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


find_start_byte    = 0
find_id_byte       = 1
find_overhead_byte = 2
find_payload_len   = 3
find_payload       = 4
find_crc           = 5
find_end_byte      = 6


def msb(val):
    return byte_val(val, num_bytes(val) - 1)


def lsb(val):
    return byte_val(val, 0)


def byte_val(val, pos):
    return int.from_bytes(((val >> (pos * 8)) & 0xFF).to_bytes(2, 'big'), 'big')


def num_bytes(val):
    num_bits = val.bit_length()
    num_bytes = num_bits // 8

    if num_bits % 8:
        num_bytes += 1
    
    if not num_bytes:
        num_bytes = 1

    return num_bytes


def constrain(val, min_, max_):
    if val < min_:
        return min_
    elif val > max_:
        return max_
    return val


def open_ports():
    '''
    Description:
    ------------
    Lists serial port names

    :return port_list: list - all serial ports currently available
    '''
    port_list = []

    for port in serial_ports():
        try:
            s = serial.Serial(port)
            s.close()
            port_list.append(port)
        except (OSError, serial.SerialException):
            pass

    return port_list


def serial_ports():
    return [p.device for p in serial.tools.list_ports.comports(include_links=True)]


class SerialTransfer(object):
    def __init__(self, port, baud=115200, restrict_ports=True, debug=True, byte_format=BYTE_FORMATS['little-endian'], timeout=0.05):
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
        :return: void
        '''

        self.txBuff = [' ' for i in range(MAX_PACKET_SIZE)]
        self.rxBuff = [' ' for i in range(MAX_PACKET_SIZE)]

        self.debug        = debug
        self.idByte       = 0
        self.bytesRead    = 0
        self.status       = 0
        self.overheadByte = 0xFF
        self.callbacks    = []
        self.byte_format  = byte_format

        self.state = find_start_byte
        
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
                print(e)
                return False
        return True
    
    def set_callbacks(self, callbacks):
        '''
        Description:
        ------------
        Specify a list of callback functions to be automatically called by
        self.tick() when a new packet is fully parsed. The ID of the parsed
        packet is then used to determine which callback needs to be called.

        :return: void
        '''
        
        if type(callbacks) == list:
            self.callbacks = callbacks
        else:
            raise InvalidCallbackList('Parameter "callbacks" is not of type "list"')

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
            if type(val) == str:
                val = val.encode()
                format_str = '%ds' % len(val)
                
            elif type(val) == dict:
                val = json.dumps(val).encode()
                format_str = '%ds' % len(val)
                
            elif type(val) == float:
                format_str = 'f'
                
            elif type(val) == int:
                format_str = 'i'
                
            elif type(val) == bool:
                format_str = '?'
                
            elif type(val) == list:
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
            self.txBuff[index + start_pos] = val_bytes[index]
        
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
            buff = bytes(self.rxBuff[start_pos:(start_pos + obj_byte_size)])
            format_str = '%ds' % len(buff)
            
        elif obj_type == float:
            format_str = 'f'
            buff = bytes(self.rxBuff[start_pos:(start_pos + STRUCT_FORMAT_LENGTHS[format_str])])
            
        elif obj_type == int:
            format_str = 'i'
            buff = bytes(self.rxBuff[start_pos:(start_pos + STRUCT_FORMAT_LENGTHS[format_str])])
            
        elif obj_type == bool:
            format_str = '?'
            buff = bytes(self.rxBuff[start_pos:(start_pos + STRUCT_FORMAT_LENGTHS[format_str])])
            
        elif obj_type == list:
            buff = bytes(self.rxBuff[start_pos:(start_pos + obj_byte_size)])
            
            if list_format:
                arr = array(list_format, buff)
                return arr.tolist()
            
            else:
                return None
        
        elif type(obj_type) == str:
            buff = bytes(self.rxBuff[start_pos:(start_pos + STRUCT_FORMAT_LENGTHS[obj_type])])
            format_str = obj_type
        
        else:
            return None
        
        if byte_format:
            unpacked_response = struct.unpack(byte_format + format_str, buff)[0]
            
        else:
            unpacked_response = struct.unpack(self.byte_format + format_str, buff)[0]
        
        if (obj_type == str) or (obj_type == dict):
            unpacked_response = unpacked_response.decode('utf-8')
        
        if obj_type == dict:
            unpacked_response = json.loads(unpacked_response)
        
        return unpacked_response

    def calc_overhead(self, pay_len):
        '''
        Description:
        ------------
        Calculates the COBS (Consistent Overhead Stuffing) Overhead
        byte and stores it in the class's overheadByte variable. This
        variable holds the byte position (within the payload) of the
        first payload byte equal to that of START_BYTE

        :param pay_len: int - number of bytes in the payload

        :return: void
        '''

        self.overheadByte = 0xFF

        for i in range(pay_len):
            if self.txBuff[i] == START_BYTE:
                self.overheadByte = i
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
                if self.txBuff[i] == START_BYTE:
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

        refByte = self.find_last(pay_len)

        if (not refByte == -1) and (refByte <= MAX_PACKET_SIZE):
            for i in range(pay_len - 1, 0, -1):
                if self.txBuff[i] == START_BYTE:
                    self.txBuff[i] = refByte - i
                    refByte = i

    def send(self, message_len, packet_id=0):
        '''
        Description:
        ------------
        Send a specified number of bytes in packetized form

        :param message_len: int - number of bytes from the txBuff to send as
                                  payload in the packet

        :return: bool - whether or not the operation was successful
        '''

        stack = []
        message_len = constrain(message_len, 0, MAX_PACKET_SIZE)

        try:
            self.calc_overhead(message_len)
            self.stuff_packet(message_len)
            found_checksum = self.crc.calculate(self.txBuff, message_len)

            stack.append(START_BYTE)
            stack.append(packet_id)
            stack.append(self.overheadByte)
            stack.append(message_len)

            for i in range(message_len):
                if type(self.txBuff[i]) == str:
                    val = ord(self.txBuff[i])
                else:
                    val = int(self.txBuff[i])

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

    def unpack_packet(self, pay_len):
        '''
        Description:
        ------------
        Unpacks all COBS-stuffed bytes within the array

        :param pay_len: int - number of bytes in the payload

        :return: void
        '''

        testIndex = self.recOverheadByte
        delta = 0

        if testIndex <= MAX_PACKET_SIZE:
            while self.rxBuff[testIndex]:
                delta = self.rxBuff[testIndex]
                self.rxBuff[testIndex] = START_BYTE
                testIndex += delta

            self.rxBuff[testIndex] = START_BYTE

    def available(self):
        '''
        Description:
        ------------
        Parses incoming serial data, analyzes packet contents,
        and reports errors/successful packet reception

        :return self.bytesRead: int - number of bytes read from the received
                                      packet
        '''

        if self.open():
            if self.connection.in_waiting:
                while self.connection.in_waiting:
                    recChar = int.from_bytes(self.connection.read(),
                                             byteorder='big')

                    if self.state == find_start_byte:
                        if recChar == START_BYTE:
                            self.state = find_id_byte
                    
                    elif self.state == find_id_byte:
                        self.idByte = recChar
                        self.state = find_overhead_byte

                    elif self.state == find_overhead_byte:
                        self.recOverheadByte = recChar
                        self.state = find_payload_len

                    elif self.state == find_payload_len:
                        if recChar <= MAX_PACKET_SIZE:
                            self.bytesToRec = recChar
                            self.payIndex = 0
                            self.state = find_payload
                        else:
                            self.bytesRead = 0
                            self.state = find_start_byte
                            self.status = PAYLOAD_ERROR
                            return self.bytesRead

                    elif self.state == find_payload:
                        if self.payIndex < self.bytesToRec:
                            self.rxBuff[self.payIndex] = recChar
                            self.payIndex += 1

                            # Try to receive as many more bytes as we can, but we might not get all of them
                            # if there is a timeout from the OS
                            if self.payIndex != self.bytesToRec:
                                moreBytes = list(self.connection.read(self.bytesToRec - self.payIndex))
                                nextIndex = self.payIndex + len(moreBytes)

                                self.rxBuff[self.payIndex:nextIndex] = moreBytes
                                self.payIndex = nextIndex

                            if self.payIndex == self.bytesToRec:
                                self.state = find_crc

                    elif self.state == find_crc:
                        found_checksum = self.crc.calculate(
                            self.rxBuff, self.bytesToRec)

                        if found_checksum == recChar:
                            self.state = find_end_byte
                        else:
                            self.bytesRead = 0
                            self.state = find_start_byte
                            self.status = CRC_ERROR
                            return self.bytesRead

                    elif self.state == find_end_byte:
                        self.state = find_start_byte

                        if recChar == STOP_BYTE:
                            self.unpack_packet(self.bytesToRec)
                            self.bytesRead = self.bytesToRec
                            self.status = NEW_DATA
                            return self.bytesRead

                        self.bytesRead = 0
                        self.status = STOP_BYTE_ERROR
                        return self.bytesRead

                    else:
                        print('ERROR: Undefined state: {}'.format(self.state))

                        self.bytesRead = 0
                        self.state = find_start_byte
                        return self.bytesRead
            else:
                self.bytesRead = 0
                self.status = NO_DATA
                return self.bytesRead

        self.bytesRead = 0
        self.status = CONTINUE
        return self.bytesRead
    
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
            if self.idByte < len(self.callbacks):
                self.callbacks[self.idByte]()
            elif self.debug:
                print('ERROR: No callback available for packet ID {}'.format(self.idByte))
            
            return True
        
        elif self.debug and not self.status:
            if self.status == CRC_ERROR:
                err_str = 'CRC_ERROR'
            elif self.status == PAYLOAD_ERROR:
                err_str = 'PAYLOAD_ERROR'
            elif self.status == STOP_BYTE_ERROR:
                err_str = 'STOP_BYTE_ERROR'
            else:
                err_str = str(self.status)
                
            print('ERROR: {}'.format(err_str))
        
        return False
