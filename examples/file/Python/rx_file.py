from time import sleep
from pySerialTransfer import pySerialTransfer as txfer
from pySerialTransfer.pySerialTransfer import Status

file = ''
fileName = ''


if __name__ == '__main__':
    try:
        link = txfer.SerialTransfer('COM11')
        
        link.open()
        sleep(5)
    
        while True:
            if link.available():
                if not link.id_byte:
                    file = ''
                    fileName = link.rx_obj(str, obj_byte_size=8)
                    
                    print('\n\n\nFile Name: {}\n'.format(fileName))
                
                else:
                    nextContents = link.rx_obj(str, start_pos=2, obj_byte_size=link.bytes_read - 2)
                    file += nextContents
                    
                    print(nextContents, end='')
                    
            elif link.status <= 0:
                if link.status == Status.CRC_ERROR:
                    print('ERROR: CRC_ERROR')
                elif link.status == Status.PAYLOAD_ERROR:
                    print('ERROR: PAYLOAD_ERROR')
                elif link.status == Status.STOP_BYTE_ERROR:
                    print('ERROR: STOP_BYTE_ERROR')
                else:
                    print('ERROR: {}'.format(link.status))
                
    except KeyboardInterrupt:
        link.close()