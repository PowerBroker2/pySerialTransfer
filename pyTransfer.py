import serial


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
    def __init__(self, port_name, baud=115200):
        self.txBuff = []
        self.rxBuff = []
        
        self.bytesRead    = 0
        self.status       = 0
        self.overheadByte = 0xFF
        
        self.state = find_start_byte
        
        self.connection = serial.Serial(port_name, baudrate=baud)
        self.connection.open()
        
    def calc_overhead(self, pay_len):
        '''
        TODO
        '''
        
        self.overheadByte = 0xFF

        for i in range(len(pay_len)):
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
    
        for i in range(len(pay_len)):
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
            
            for i in range(len(message_len)):
                stack.append(self.txBuff[i])
            
            stack.append(checksum)
            stack.append(STOP_BYTE)
            
            stack = bytearray(stack)
            self.connection.write(stack)
            
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
        
        if self.connection.in_waiting:
            while self.connection.in_waiting:
                recChar = self.connection.read()

                if self.state == find_start_byte:##############################
                    if recChar == START_BYTE:
                        self.state = find_overhead_byte

                elif self.state == find_overhead_byte:
                    self.recOverheadByte = recChar
                    self.state           = find_payload_len

                elif self.state == find_payload_len:###########################
                    if recChar <= MAX_PACKET_SIZE:
                        self.bytesToRec = recChar
                        self.state = find_payload
                    else:
                        self.bytesRead = 0
                        self.state     = find_start_byte
                        self.status    = PAYLOAD_ERROR
                        return self.bytesRead

                elif self.state == find_payload:###############################
                    if self.payIndex < self.bytesToRec:
                        self.rxBuff[self.payIndex] = recChar
                        self.payIndex += 1

                        if self.payIndex == self.bytesToRec:
                            self.payIndex = 0
                            self.state    = find_checksum

                elif self.state == find_checksum:##############################
                    calcChecksum = find_checksum(self.bytesToRec)

                    if calcChecksum == recChar:
                        self.state = find_end_byte
                    else:
                        self.bytesRead = 0
                        self.state     = find_start_byte
                        self.status    = CHECKSUM_ERROR
                        return self.bytesRead
                
                elif self.state == find_end_byte:##############################
                    self.state = find_start_byte

                    if recChar == STOP_BYTE:
                        self.unpack_packet(self.bytesToRec)
                        self.bytesRead = self.bytesToRec
                        self.status    = NEW_DATA
                        return self.bytesRead

                    self.bytesRead = 0
                    self.status    = STOP_BYTE_ERROR
                    return self.bytesRead
                    
                else:###########################################################
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
    hi = SerialTransfer('COM4')
    
    
    
    
