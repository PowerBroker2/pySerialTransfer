"""CRC-8 implementation matching Arduino SerialTransfer's PacketCRC."""

import operator
import sys
from functools import lru_cache


@lru_cache(maxsize=16)
def _crc_table(polynomial):
    entries = []
    for current in range(256):
        for _ in range(8):
            feedback = polynomial if current & 0x80 else 0
            current = ((current << 1) & 0xFF) ^ feedback
        entries.append(current)
    return tuple(entries)


class CRC:
    """Lookup-table CRC-8 using the SerialTransfer polynomial (0x9B)."""

    def __init__(self, polynomial=0x9B, crc_len=8):
        self.poly = polynomial
        # crc_len is retained for compatibility; the wire protocol is CRC-8.
        self.crc_len = 8
        self.table_len = 256

    @property
    def poly(self):
        return self._poly

    @poly.setter
    def poly(self, polynomial):
        self._poly = operator.index(polynomial) & 0xFF
        self._table = _crc_table(self._poly)

    def calculate_checksum(self, index: int):
        """Return one table entry; valid byte indices are 0 through 255."""
        index = operator.index(index)
        if not 0 <= index < self.table_len:
            raise ValueError("CRC table index must be between 0 and 255")
        return self._table[index]

    def update(self, current, value):
        """Update an existing CRC-8 accumulator with one byte value."""
        index = (int(current) ^ int(value)) & 0xFF
        return self._table[index]

    def print_table(self):
        """Print the 256 CRC entries as a 16 by 16 hexadecimal table."""
        for index, value in enumerate(self._table):
            sys.stdout.write("0x{:X}".format(value))
            sys.stdout.write("\n" if (index + 1) % 16 == 0 else " ")

    def calculate(self, arr, dist=None):
        """Calculate CRC-8 over byte values, optionally limiting the count.

        For compatibility, an integer input returns the table entry for that
        byte. A requested count above a sequence's length is clamped; negative
        counts and values outside the byte range are rejected.
        """
        if isinstance(arr, int):
            if dist is not None:
                raise TypeError("dist cannot be used with a scalar CRC table index")
            return self.calculate_checksum(arr)

        try:
            length = len(arr)
        except TypeError as exc:
            raise TypeError("CRC input must be a byte sequence or table index") from exc

        if dist is None:
            count = length
        else:
            try:
                count = operator.index(dist)
            except TypeError as exc:
                raise TypeError("dist must be an integer") from exc
            if count < 0:
                raise ValueError("dist must be non-negative")
            count = min(count, length)

        crc = 0
        for index in range(count):
            value = arr[index]
            if isinstance(value, str):
                try:
                    value = int(value)
                except ValueError:
                    if len(value) != 1:
                        raise ValueError("string CRC elements must be bytes or single characters")
                    value = ord(value)
            else:
                try:
                    value = operator.index(value)
                except TypeError as exc:
                    raise TypeError("CRC sequence elements must be integers or single characters") from exc

            if not 0 <= value <= 0xFF:
                raise ValueError("CRC sequence elements must be between 0 and 255")
            crc = self._table[crc ^ value]
        return crc


if __name__ == '__main__':
    crc_instance = CRC()
    crc_instance.print_table()
    print(' ')
    print(hex(crc_instance.calculate(0x31)).upper().replace('X', 'x'))
