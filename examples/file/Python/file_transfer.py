"""Helpers for the UART file-transfer example shared with SerialTransfer.h."""

import struct


FILE_BUFFER_SIZE = 4096
MAX_FILENAME_BYTES = 31
MAX_CHUNK_DATA = 255 - 2  # reserve two payload bytes for the file offset
FNV_OFFSET_BASIS = 2166136261
FNV_PRIME = 16777619
_FILE_HEADER = struct.Struct("<HI")
_FILE_OFFSET = struct.Struct("<H")
_FILE_TRAILER = struct.Struct("<HI")


def file_hash(data):
    """Return the 32-bit FNV-1a checksum used by the Arduino example."""
    value = FNV_OFFSET_BASIS
    for byte in data:
        value = ((value ^ byte) * FNV_PRIME) & 0xFFFFFFFF
    return value


def _encode_filename(name):
    if not isinstance(name, str) or not name or name in (".", ".."):
        raise ValueError("filename must be a non-empty file name")
    invalid = "/\\\x00<>:\"|?*"
    if any(character in invalid or ord(character) < 32 for character in name):
        raise ValueError("filename must be a plain file name without control or path characters")
    if name.endswith((" ", ".")):
        raise ValueError("filename must not end with a space or period")
    windows_device = name.split(".", 1)[0].rstrip(" ").upper()
    reserved_names = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    reserved_names.update("COM{}".format(number) for number in range(1, 10))
    reserved_names.update("LPT{}".format(number) for number in range(1, 10))
    reserved_names.update("COM{}".format(number) for number in "¹²³")
    reserved_names.update("LPT{}".format(number) for number in "¹²³")
    if windows_device in reserved_names:
        raise ValueError("filename is reserved by Windows")
    encoded = name.encode("utf-8")
    if len(encoded) > MAX_FILENAME_BYTES:
        raise ValueError("UTF-8 filename must be at most 31 bytes")
    return encoded


def make_file_header(name, data):
    """Build ID 0 payload: uint16 size, uint32 FNV-1a, UTF-8 filename."""
    if len(data) > FILE_BUFFER_SIZE:
        raise ValueError("file exceeds the Arduino receiver's 4096-byte buffer")
    return _FILE_HEADER.pack(len(data), file_hash(data)) + _encode_filename(name)


def iter_file_chunks(data):
    """Yield ID 1 payloads containing a little-endian offset and up to 253 bytes."""
    for offset in range(0, len(data), MAX_CHUNK_DATA):
        chunk = data[offset:offset + MAX_CHUNK_DATA]
        yield _FILE_OFFSET.pack(offset) + chunk


def make_file_trailer(data):
    """Build ID 2 payload repeating the file size and checksum."""
    return _FILE_TRAILER.pack(len(data), file_hash(data))


class FileReceiver:
    """Validate the simple ID 0/1/2 file protocol used by the Arduino example."""

    def __init__(self):
        self.abort()

    def abort(self):
        self.active = False
        self.name = None
        self.expected_size = 0
        self.expected_hash = 0
        self.data = bytearray()

    def process(self, packet_id, payload):
        """Consume one received packet, returning ``(name, data)`` when verified."""
        payload = bytes(payload)
        try:
            if packet_id == 0:
                self._start(payload)
                return None
            if not self.active:
                return None
            if packet_id == 1:
                self._append(payload)
                return None
            if packet_id == 2:
                result = self._finish(payload)
                self.abort()
                return result
        except (UnicodeDecodeError, struct.error, ValueError):
            self.abort()
            raise
        return None

    def _start(self, payload):
        self.abort()
        if len(payload) < _FILE_HEADER.size + 1:
            raise ValueError("file header is too short")
        size, checksum = _FILE_HEADER.unpack_from(payload)
        filename_bytes = payload[_FILE_HEADER.size:]
        # Accept C-string headers from older Arduino examples as well as the
        # current length-delimited UTF-8 filename payload.
        if filename_bytes.endswith(b"\x00"):
            filename_bytes = filename_bytes[:-1]
        if not filename_bytes or b"\x00" in filename_bytes:
            raise ValueError("filename contains an embedded NUL byte")
        name = filename_bytes.decode("utf-8")
        _encode_filename(name)
        if size > FILE_BUFFER_SIZE:
            raise ValueError("file exceeds the Arduino receiver's 4096-byte buffer")
        self.name = name
        self.expected_size = size
        self.expected_hash = checksum
        self.data = bytearray()
        self.active = True

    def _append(self, payload):
        if len(payload) <= _FILE_OFFSET.size:
            raise ValueError("file chunk has no data")
        offset = _FILE_OFFSET.unpack_from(payload)[0]
        chunk = payload[_FILE_OFFSET.size:]
        if offset != len(self.data):
            raise ValueError("file chunk is missing, repeated, or out of order")
        if len(self.data) + len(chunk) > self.expected_size:
            raise ValueError("file chunk exceeds the announced file size")
        self.data.extend(chunk)

    def _finish(self, payload):
        if len(payload) != _FILE_TRAILER.size:
            raise ValueError("file trailer must contain a size and checksum")
        size, checksum = _FILE_TRAILER.unpack(payload)
        if (size != self.expected_size or checksum != self.expected_hash or
                len(self.data) != self.expected_size or file_hash(self.data) != self.expected_hash):
            raise ValueError("file size or FNV-1a checksum did not match")
        return self.name, bytes(self.data)
