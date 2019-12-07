import serial
from platform import system


CONTINUE        = 2
NEW_DATA        = 1
NO_DATA         = 0
CHECKSUM_ERROR  = -1
PAYLOAD_ERROR   = -2
STOP_BYTE_ERROR = -3

START_BYTE      = 0x7E
STOP_BYTE       = 0x81

MAX_PACKET_SIZE = 0xFE

find_start_byte    = 0
find_overhead_byte = 1
find_payload_len   = 2
find_payload       = 3
find_checksum      = 4
find_end_byte      = 5


class SerialTransfer(object):
    def __init__(self, port_num, baud=115200):
        self.txBuff = (', ' * (MAX_PACKET_SIZE - 1)).split(',')
        self.rxBuff = (', ' * (MAX_PACKET_SIZE - 1)).split(',')
        
        self.bytesRead    = 0
        self.status       = 0
        self.overheadByte = 0xFF
        
        self.state = find_start_byte
        
        if system() == 'Windows':
            port_name = 'COM{}'.format(port_num)
        else:
            port_name = '/dev/ttyUSB{}'.format(port_num)
        
        self.connection          = serial.Serial()
        self.connection.port     = port_name
        self.connection.baudrate = baud
        
    def calc_overhead(self, pay_len):
        '''
        TODO
        '''
        
        self.overheadByte = 0xFF

        for i in range(pay_len):
            if self.txBuff[i] == START_BYTE:
                self.overheadByte = i
                break
    
    def find_last(self, pay_len):
        '''
        TODO
        '''
        
        if pay_len <= MAX_PACKET_SIZE:
            for i in range(pay_len - 1, 0, -1):
                if self.txBuff[i] == START_BYTE:
                    return i
        return -1
    
    def stuff_packet(self, pay_len):
        '''
        TODO
        '''
        
        refByte = self.find_last(pay_len)

        if (not refByte == -1) and (refByte <= MAX_PACKET_SIZE):
            for i in range(pay_len - 1, 0, -1):
                if self.txBuff[i] == START_BYTE:
                    self.txBuff[i] = refByte - i
                    refByte = i
    
    def find_checksum(self, arr, pay_len):
        '''
        TODO
        '''
        
        checksum = 0
    
        for i in range(pay_len):
            if type(arr[i]) == str:
                checksum += ord(arr[i])
            else:
                checksum += arr[i]
    
        checksum = ~checksum
        checksum = checksum & 0xFF
    
        return checksum

    def send(self, message_len):
        '''
        TODO
        '''
        
        stack = []
        
        if message_len <= MAX_PACKET_SIZE:
            self.calc_overhead(message_len)
            self.stuff_packet(message_len)
            checksum = self.find_checksum(self.txBuff, message_len)
            
            stack.append(START_BYTE)
            stack.append(self.overheadByte)
            stack.append(message_len)
            
            for i in range(message_len):
                if type(self.txBuff[i]) == str:
                    val = ord(self.txBuff[i])
                else:
                    val = self.txBuff[i]
                
                stack.append(val)
            
            stack.append(checksum)
            stack.append(STOP_BYTE)
            
            stack = bytearray(stack)
            
            with self.connection as ser:
                ser.write(stack)
            
            return True
        return False

    def unpack_packet(self, pay_len):
        '''
        TODO
        '''

        testIndex = self.recOverheadByte
        delta     = 0
    
        if testIndex <= MAX_PACKET_SIZE:
            while self.rxBuff[testIndex]:
                delta = self.rxBuff[testIndex]
                self.rxBuff[testIndex] = START_BYTE
                testIndex += delta
                
            self.rxBuff[testIndex] = START_BYTE

    def available(self):
        '''
        TODO
        '''
        
        with self.connection as ser:
            if ser.in_waiting:
                while ser.in_waiting:
                    recChar = ser.read()
    
                    if self.state == find_start_byte:##########################
                        if recChar == START_BYTE:
                            self.state = find_overhead_byte
    
                    elif self.state == find_overhead_byte:
                        self.recOverheadByte = recChar
                        self.state           = find_payload_len
    
                    elif self.state == find_payload_len:#######################
                        if recChar <= MAX_PACKET_SIZE:
                            self.bytesToRec = recChar
                            self.state = find_payload
                        else:
                            self.bytesRead = 0
                            self.state     = find_start_byte
                            self.status    = PAYLOAD_ERROR
                            return self.bytesRead
    
                    elif self.state == find_payload:###########################
                        if self.payIndex < self.bytesToRec:
                            self.rxBuff[self.payIndex] = recChar
                            self.payIndex += 1
    
                            if self.payIndex == self.bytesToRec:
                                self.payIndex = 0
                                self.state    = find_checksum
    
                    elif self.state == find_checksum:##########################
                        calcChecksum = find_checksum(self.bytesToRec)
    
                        if calcChecksum == recChar:
                            self.state = find_end_byte
                        else:
                            self.bytesRead = 0
                            self.state     = find_start_byte
                            self.status    = CHECKSUM_ERROR
                            return self.bytesRead
                    
                    elif self.state == find_end_byte:##########################
                        self.state = find_start_byte
    
                        if recChar == STOP_BYTE:
                            self.unpack_packet(self.bytesToRec)
                            self.bytesRead = self.bytesToRec
                            self.status    = NEW_DATA
                            return self.bytesRead
    
                        self.bytesRead = 0
                        self.status    = STOP_BYTE_ERROR
                        return self.bytesRead
                        
                    else:######################################################
                        print('ERROR: Undefined state: {}'.format(self.state))
    
                        self.bytesRead = 0
                        self.state     = find_start_byte
                        return self.bytesRead
            else:
                self.bytesRead = 0
                self.status    = NO_DATA
                return self.bytesRead
        
            self.bytesRead = 0
            self.status    = CONTINUE
            return self.bytesRead


if __name__ == '__main__':
    hi = SerialTransfer(15)

    hi.txBuff[0] = 'h'
    hi.txBuff[1] = 'i'
    hi.txBuff[2] = '\n'
    
    hi.send(3)
    
