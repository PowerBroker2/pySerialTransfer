import logging
import os
import operator
from ctypes import c_wchar, sizeof
import json
import math
import struct
import time
from enum import Enum
from typing import Callable, List, Optional, Tuple, Union

import serial
import serial.tools.list_ports
from .CRC import CRC


def _as_bytes(values):
    """Convert a byte buffer or legacy list of byte values to bytes."""
    if isinstance(values, (bytes, bytearray, memoryview)):
        return bytes(values)
    result = bytearray()
    for value in values:
        if isinstance(value, str):
            if len(value) != 1:
                raise ValueError("buffer strings must contain one character")
            value = ord(value)
        result.append(operator.index(value))
    return bytes(result)


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
    STOP_BYTE_ERROR = -2  # Deprecated: current UART frames have no stop byte.
    STALE_PACKET_ERROR = -3


START_BYTE = 0x7E
STOP_BYTE  = 0x81

MAX_PACKET_SIZE = 0xFF
DEFAULT_TIMEOUT = 0.05

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

# Standard wire widths used by rx_obj(..., list_format=...). Keep the
# legacy Unicode entry for callers that use this table for native arrays.
ARRAY_FORMAT_LENGTHS = dict(STRUCT_FORMAT_LENGTHS, u=sizeof(c_wchar))


class State(Enum):
    FIND_START_BYTE    = 0
    FIND_ID_BYTE       = 1
    FIND_PAYLOAD_LEN   = 2
    FIND_PAYLOAD       = 3
    FIND_CRC           = 4
    # Deprecated compatibility states; current UART frames have no stuffing or stop byte.
    FIND_OVERHEAD_BYTE = 5
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
    def __init__(self, port, baud=115200, restrict_ports=True, debug=True, byte_format=BYTE_FORMATS['little-endian'], timeout=0.05, write_timeout=None, inter_byte_timeout=DEFAULT_TIMEOUT):
        '''
        Description:
        ------------
        Configure a UART connection. open(), send(), or available() opens the port.

        :param port: str - serial device name or path
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
        self.tx_buff = bytearray(MAX_PACKET_SIZE)
        self.rx_buff = bytearray(MAX_PACKET_SIZE)

        self.debug        = debug
        self.id_byte       = 0
        self._candidate_id = 0
        self.bytes_read    = 0
        self.status       = Status.NO_DATA
        self.overhead_byte = 0xFF
        self.callbacks    = []
        self.byte_format  = byte_format
        if inter_byte_timeout is not None:
            try:
                inter_byte_timeout = float(inter_byte_timeout)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("inter_byte_timeout must be a positive finite number or None") from exc
            if not math.isfinite(inter_byte_timeout) or inter_byte_timeout <= 0:
                raise ValueError("inter_byte_timeout must be a positive finite number or None")
        self.inter_byte_timeout = inter_byte_timeout

        self.state = State.FIND_START_BYTE
        self._calc_crc = 0
        self._last_byte_time = None
        self._pending_rx = memoryview(b'')
        self._pending_time = None

        if restrict_ports:
            available_ports = serial_ports()
            self.port_name = None
            port_key = os.path.normcase(os.fspath(port))
            for candidate in available_ports:
                if port_key in (os.path.normcase(candidate), os.path.normcase(os.path.basename(candidate))):
                    self.port_name = candidate
                    break

            if self.port_name is None:
                names = ', '.join(available_ports) if available_ports else '(none)'
                raise InvalidSerialPort("Invalid serial port {!r}. Available ports: {}".format(port, names))
        else:
            self.port_name = os.fspath(port)

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
                if self.debug:
                    logging.getLogger(__name__).error("Unable to open %s: %s", self.port_name, e)
                return False
        return True
    
    def set_callbacks(self, callbacks: Union[List[Optional[Callable]], Tuple[Optional[Callable], ...]]):
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
        
        if not all(cb is None or callable(cb) for cb in callbacks):
            raise InvalidCallbackList('One or more elements in "callbacks" are not callable')
        
        self.callbacks = callbacks.copy() if isinstance(callbacks, list) else callbacks

    def close(self):
        '''
        Description:
        ------------
        Close serial port

        :return: void
        '''
        try:
            if self.connection.is_open:
                self.connection.close()
        finally:
            self._clear_received()
    
    def tx_obj(self, val, start_pos=0, byte_format='', val_type_override=''):
        """Pack a value into the TX buffer and return the next free offset.

        Strings and dictionaries are UTF-8 encoded, floats use IEEE-754
        single precision, booleans use one byte, and integers use signed
        32-bit encoding. Lists pack each element in sequence. Use
        ``val_type_override`` for a specific struct format such as ``h``.
        Returns None without writing a partial value if the value does not fit.
        """
        try:
            start_pos = operator.index(start_pos)
            if not 0 <= start_pos <= MAX_PACKET_SIZE:
                return None
            prefix = byte_format or self.byte_format
            packed = bytearray()
            self._pack_value(packed, val, prefix, val_type_override, MAX_PACKET_SIZE - start_pos)
            return self.tx_struct_obj(packed, start_pos)
        except (struct.error, TypeError, ValueError, OverflowError, RecursionError):
            return None

    @staticmethod
    def _pack_value(packed, val, prefix, fmt, capacity):
        if not fmt:
            if isinstance(val, list):
                for item in val:
                    SerialTransfer._pack_value(packed, item, prefix, "", capacity)
                return
            if isinstance(val, dict):
                val = json.dumps(val)
            if isinstance(val, str):
                val = val.encode("utf-8")
            if isinstance(val, (bytes, bytearray, memoryview)):
                val = bytes(val)
                fmt = "%ds" % len(val)
            elif isinstance(val, bool):
                fmt = "?"
            elif isinstance(val, int):
                fmt = "i"
            elif isinstance(val, float):
                fmt = "f"
            else:
                raise TypeError("unsupported value")
        elif isinstance(val, str) and (fmt == "c" or "s" in fmt or "p" in fmt):
            val = val.encode("utf-8")
        if fmt == "c" and isinstance(val, bytearray):
            val = bytes(val)

        fmt = prefix + fmt
        if struct.calcsize(fmt) > capacity - len(packed):
            raise ValueError("value exceeds remaining payload size")
        packed.extend(struct.pack(fmt, val))

    def tx_struct_obj(self, val_bytes, start_pos=0):
        try:
            start_pos = operator.index(start_pos)
            source = _as_bytes(val_bytes)
        except (TypeError, ValueError, OverflowError):
            return None
        if start_pos < 0:
            return None

        if isinstance(self.tx_buff, bytearray) and len(self.tx_buff) == MAX_PACKET_SIZE:
            buffer = self.tx_buff
        else:
            buffer = bytearray(_as_bytes(self.tx_buff)[:MAX_PACKET_SIZE])
            if len(buffer) < MAX_PACKET_SIZE:
                buffer.extend(b"\x00" * (MAX_PACKET_SIZE - len(buffer)))
            self.tx_buff = buffer

        if start_pos >= MAX_PACKET_SIZE:
            return MAX_PACKET_SIZE
        end_pos = min(start_pos + len(source), MAX_PACKET_SIZE)
        buffer[start_pos:end_pos] = source[:end_pos - start_pos]
        return end_pos

    def rx_obj(self, obj_type, start_pos=0, obj_byte_size=0, list_format=None, byte_format=''):
        """Unpack a value from the most recently received payload.

        ``obj_byte_size`` is a byte count. Zero means all remaining payload
        bytes for strings, dictionaries, and lists. List formats use Python
        struct format characters, with byte order controlled by ``byte_format``
        or the instance's ``byte_format`` setting. Returns None for incomplete
        or invalid values.
        """
        try:
            start_pos = operator.index(start_pos)
            requested_size = operator.index(obj_byte_size)
            payload = _as_bytes(self.rx_buff)
        except (TypeError, ValueError, OverflowError):
            return None
        if start_pos < 0 or requested_size < 0:
            return None

        valid_length = min(max(int(self.bytes_read), 0), len(payload))
        available = valid_length - start_pos
        if available < 0 or requested_size > available:
            return None
        if available == 0 and self.status != Status.NEW_DATA:
            return None
        prefix = byte_format or self.byte_format

        if obj_type in (str, dict, bytes):
            size = requested_size or available
            raw = payload[start_pos:start_pos + size]
            if obj_type is bytes:
                return raw
            raw = raw.split(b"\x00", 1)[0]
            try:
                value = raw.decode("utf-8")
                if obj_type is str:
                    return value
                decoded = json.loads(value)
                return decoded if isinstance(decoded, dict) else None
            except (ValueError, RecursionError):
                return None

        if obj_type is list:
            if not list_format:
                return None
            size = requested_size or available
            raw = payload[start_pos:start_pos + size]
            try:
                item_size = struct.calcsize(prefix + list_format)
                if item_size <= 0 or len(raw) % item_size:
                    return None
                values = struct.iter_unpack(prefix + list_format, raw)
                return [item[0] if len(item) == 1 else item for item in values]
            except (struct.error, TypeError, ValueError, SystemError):
                return None

        if obj_type is float:
            format_str = 'f'
        elif obj_type is int:
            format_str = 'i'
        elif obj_type is bool:
            format_str = '?'
        elif isinstance(obj_type, str):
            format_str = obj_type
        else:
            return None

        try:
            size = struct.calcsize(prefix + format_str)
            if size > (requested_size or available):
                return None
            raw = payload[start_pos:start_pos + size]
            fields = struct.unpack(prefix + format_str, raw)
            return fields[0] if len(fields) == 1 else fields or None
        except (struct.error, TypeError, ValueError, SystemError):
            return None

    def calc_overhead(self, pay_len):
        """Deprecated compatibility shim; current UART frames have no stuffing."""
        self.overhead_byte = 0xFF

    def find_last(self, pay_len):
        """Deprecated compatibility shim; current UART frames have no stuffing."""
        return -1

    def stuff_packet(self, pay_len):
        """Deprecated compatibility shim; leave current UART payloads unchanged."""
        return None

    def send(self, message_len, packet_id=0):
        """Write the Arduino UART frame, completing any short serial writes."""
        try:
            requested_len = operator.index(message_len)
            if requested_len < 0:
                return False
            requested_len = min(requested_len, MAX_PACKET_SIZE)
            packet_id = operator.index(packet_id) & 0xFF
            if requested_len > len(self.tx_buff):
                return False
            payload = _as_bytes(self.tx_buff[:requested_len])
            if not self.open():
                return False

            frame = bytearray((START_BYTE, packet_id, len(payload)))
            frame.extend(payload)
            crc_value = self.crc.update(0, packet_id)
            crc_value = self.crc.update(crc_value, len(payload))
            for value in payload:
                crc_value = self.crc.update(crc_value, value)
            frame.append(crc_value)

            view = memoryview(frame)
            written = 0
            while written < len(frame):
                count = self.connection.write(view[written:])
                if not isinstance(count, int) or count <= 0 or count > len(frame) - written:
                    return False
                written += count
            return True
        except (TypeError, ValueError, OverflowError, serial.SerialException):
            if self.debug:
                logging.getLogger(__name__).exception("Unable to send packet")
            return False

    def unpack_packet(self):
        """Deprecated no-op: UART payloads are no longer stuffed."""
        return None

    def _reset_parser_state(self):
        self.state = State.FIND_START_BYTE
        self.bytes_to_rec = 0
        self.pay_index = 0
        self._candidate_id = 0
        self._calc_crc = 0
        self._last_byte_time = None

    def _process_byte(self, rec_char, now):
        rec_char = int(rec_char) & 0xFF

        if (self.state != State.FIND_START_BYTE and
                self.inter_byte_timeout is not None and
                self._last_byte_time is not None and
                now - self._last_byte_time >= self.inter_byte_timeout):
            self._reset_parser_state()
            self.status = Status.STALE_PACKET_ERROR
            if rec_char == START_BYTE:
                self.state = State.FIND_ID_BYTE
                self._last_byte_time = now
            return self.status

        if self.state != State.FIND_START_BYTE:
            self._last_byte_time = now

        if self.state == State.FIND_START_BYTE:
            if rec_char == START_BYTE:
                self.state = State.FIND_ID_BYTE
                self._last_byte_time = now
        elif self.state == State.FIND_ID_BYTE:
            self._candidate_id = rec_char
            self._calc_crc = self.crc.update(0, rec_char)
            self.state = State.FIND_PAYLOAD_LEN
        elif self.state == State.FIND_PAYLOAD_LEN:
            self.bytes_to_rec = rec_char
            self._calc_crc = self.crc.update(self._calc_crc, rec_char)
            self.pay_index = 0
            self.state = State.FIND_CRC if rec_char == 0 else State.FIND_PAYLOAD
        elif self.state == State.FIND_PAYLOAD:
            self.rx_buff[self.pay_index] = rec_char
            self._calc_crc = self.crc.update(self._calc_crc, rec_char)
            self.pay_index += 1
            if self.pay_index == self.bytes_to_rec:
                self.state = State.FIND_CRC
        elif self.state == State.FIND_CRC:
            if self._calc_crc == rec_char:
                self.bytes_read = self.bytes_to_rec
                self.id_byte = self._candidate_id
                self._reset_parser_state()
                self.status = Status.NEW_DATA
                return self.status
            self.bytes_read = 0
            self._reset_parser_state()
            self.status = Status.CRC_ERROR
            return self.status

        self.status = Status.CONTINUE
        return self.status

    def _clear_received(self):
        self._pending_rx = memoryview(b"")
        self._pending_time = None
        self.id_byte = 0
        self.bytes_read = 0
        self.status = Status.NO_DATA
        self._reset_parser_state()

    def reset(self):
        """Discard buffered input and clear both payload buffers."""
        if self.connection.is_open:
            self.connection.reset_input_buffer()
        self.tx_buff = bytearray(MAX_PACKET_SIZE)
        self.rx_buff = bytearray(MAX_PACKET_SIZE)
        self._clear_received()

    def available(self):
        """Poll without waiting for a complete packet. Check status for empty frames."""
        self.bytes_read = 0
        if not self.open():
            self.status = Status.NO_DATA
            return 0

        had_data = False
        last_error = None
        # Process a saved tail, then at most one OS read per call. A bounded
        # read keeps a noisy continuous stream from monopolizing the caller.
        for pending in (True, False):
            if pending:
                data, now = self._pending_rx, self._pending_time
                self._pending_rx = memoryview(b"")
            else:
                waiting = self.connection.in_waiting
                if not waiting:
                    break
                data = memoryview(self.connection.read(min(waiting, 4096)))
                now = time.monotonic()
            if not data:
                continue

            had_data = True
            for index, rec_char in enumerate(data):
                self._process_byte(rec_char, now)
                if self.status == Status.NEW_DATA:
                    self._pending_rx = data[index + 1:]
                    self._pending_time = now
                    return self.bytes_read
                if self.status in (Status.CRC_ERROR, Status.STALE_PACKET_ERROR):
                    last_error = self.status

        if (self.state != State.FIND_START_BYTE and
                self.inter_byte_timeout is not None and
                self._last_byte_time is not None and
                time.monotonic() - self._last_byte_time >= self.inter_byte_timeout):
            self._reset_parser_state()
            last_error = Status.STALE_PACKET_ERROR

        if last_error is not None:
            self.status = last_error
        elif had_data:
            self.status = Status.CONTINUE
        else:
            self.status = Status.NO_DATA
        return 0

    def tick(self):
        """Parse input, dispatch a matching callback, and report completion."""
        self.available()
        if self.status == Status.NEW_DATA:
            if self.id_byte < len(self.callbacks):
                callback = self.callbacks[self.id_byte]
                if callback is not None:
                    callback()
            elif self.callbacks and self.debug:
                logging.error("No callback available for packet ID %s", self.id_byte)
            return True

        if self.debug and self.status in (Status.CRC_ERROR, Status.STALE_PACKET_ERROR):
            logging.error("%s", self.status.name)
        return False
