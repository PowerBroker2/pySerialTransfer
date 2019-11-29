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
                    return i;
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
    
        return checksum

    def send(self, message_len):
        '''
        TODO
        '''
        
        if message_len <= MAX_PACKET_SIZE:
            self.calc_overhead(message_len);
            self.stuff_packet(message_len);
            checksum = self.find_checksum(self.txBuff, message_len);
            
            self.connection.write(bytes([START_BYTE]))
            self.connection.write(bytes([self.overheadByte]))
            self.connection.write(bytes([message_len]))
            
            for i in range(len(message_len)):
                self.connection.write(bytes([self.txBuff[i]]))
            
            self.connection.write(bytes([checksum]))
            self.connection.write(bytes([STOP_BYTE]))
            
            return True
        return False

    def unpack_packet(self, pay_len):
        '''
        TODO
        '''

        testIndex = recOverheadByte
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
    
                switch (state)
                    case find_start_byte://///////////////////////////////////////
                    {
                        if (recChar == START_BYTE)
                            state = find_overhead_byte;
                        break;
                    }
    
                    case find_overhead_byte://////////////////////////////////////
                    {
                        recOverheadByte = recChar;
                        state = find_payload_len;
                        break;
                    }
    
                    case find_payload_len:////////////////////////////////////////
                    {
                        if (recChar <= MAX_PACKET_SIZE)
                        {
                            bytesToRec = recChar;
                            state = find_payload;
                        }
                        else
                        {
                            bytesRead = 0;
                            state     = find_start_byte;
                            status    = PAYLOAD_ERROR;
                            return 0;
                        }
                        break;
                    }
    
                    case find_payload:////////////////////////////////////////////
                    {
                        if (payIndex < bytesToRec)
                        {
                            rxBuff[payIndex] = recChar;
                            payIndex++;
    
                            if (payIndex == bytesToRec)
                            {
                                payIndex = 0;
                                state = find_checksum;
                            }
                        }
                        break;
                    }
    
                    case find_checksum:///////////////////////////////////////////
                    {
                        uint8_t calcChecksum = findChecksum(rxBuff, bytesToRec);
    
                        if (calcChecksum == recChar)
                            state = find_end_byte;
                        else
                        {
                            bytesRead = 0;
                            state     = find_start_byte;
                            status    = CHECKSUM_ERROR;
                            return 0;
                        }
                    
                        break;
                    }
    
                    case find_end_byte:///////////////////////////////////////////
                    {
                        state = find_start_byte;
    
                        if (recChar == STOP_BYTE)
                        {
                            unpackPacket(rxBuff, bytesToRec);
                            bytesRead = bytesToRec;
                            status    = NEW_DATA;
                            return bytesToRec;
                        }
    
                        bytesRead = 0
                        status    = STOP_BYTE_ERROR
                        return 0
                        break
                        
                    default:
                        Serial.print("ERROR: Undefined state: ")
                        Serial.println(state)
    
                        bytesRead = 0
                        state     = find_start_byte
                        break
                    
            bytesRead = 0
            status    = NO_DATA;
            return 0
    
        bytesRead = 0
        status    = CONTINUE
        return 0


if __name__ == '__main__':
    hi = SerialTransfer('COM4')
    
    
    
    