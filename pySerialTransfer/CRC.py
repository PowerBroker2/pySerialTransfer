import sys


class CRC(object):
    def __init__(self, polynomial=0x9B, crc_len=8):
        self.poly      = polynomial & 0xFF
        self.crc_len   = crc_len
        self.table_len = pow(2, crc_len)
        self.cs_table  = [' ' for x in range(self.table_len)]
        
        self.generate_table()
    
    def generate_table(self):
        for i in range(len(self.cs_table)):
            curr = i
            
            for j in range(8):
                if (curr & 0x80) != 0:
                    curr = ((curr << 1) & 0xFF) ^ self.poly
                else:
                    curr <<= 1
            
            self.cs_table[i] = curr
    
    def print_table(self):
        for i in range(len(self.cs_table)):
            sys.stdout.write(hex(self.cs_table[i]).upper().replace('X', 'x'))
            
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
                crc = self.cs_table[crc ^ arr[i]]
                
        except TypeError:
            crc = self.cs_table[arr]
            
        return crc


if __name__ == '__main__':
    crc = CRC()
    print(crc.print_table())
    print(' ')
    print(hex(crc.calculate(0x31)).upper().replace('X', 'x'))