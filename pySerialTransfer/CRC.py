import sys
from functools import lru_cache


class CRC:
    def __init__(self, polynomial=0x9B, crc_len=8):
        self.poly      = polynomial & 0xFF
        self.crc_len   = crc_len
        self.table_len = pow(2, crc_len)
        
    @lru_cache(2 ^ 16)
    def calculate_checksum(self, index: int):
        """Calculate the checksum for a given index.
        An LRU cached version of the CRC calculation function, with an upper bound on the cache size of 2^16
        """
        if index > self.table_len:
            raise ValueError('Index out of range')
        curr = index
        for j in range(8):
            if (curr & 0x80) != 0:
                curr = ((curr << 1) & 0xFF) ^ self.poly
            else:
                curr <<= 1
        return curr
    
    def print_table(self):
        for i in range(self.table_len):
            sys.stdout.write(hex(self.calculate_checksum(i)).upper().replace('X', 'x'))
            
            if (i + 1) % 16:
                sys.stdout.write(' ')
            else:
                sys.stdout.write('\n')
    
    def calculate(self, arr, dist=None):
        crc = 0
        
        try:
            if dist:
                indicies = dist
            else:
                indicies = len(arr)
            
            for i in range(indicies):
                try:
                    nex_el = int(arr[i])
                except ValueError:
                    nex_el = ord(arr[i])
                
                crc = self.calculate_checksum(crc ^ nex_el)
                
        except TypeError:
            crc = self.calculate_checksum(arr)
            
        return crc


if __name__ == '__main__':
    crc_instance = CRC()
    print(crc_instance.print_table())
    print(' ')
    print(hex(crc_instance.calculate(0x31)).upper().replace('X', 'x'))
