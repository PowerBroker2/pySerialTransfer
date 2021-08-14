from time import sleep
from pySerialTransfer import pySerialTransfer as txfer


y = 0.0


if __name__ == '__main__':
    try:
        link = txfer.SerialTransfer('COM11')
        
        link.open()
        sleep(5)
    
        while True:
            if link.available():
                y = link.rx_obj(obj_type='f')
                print(y)
                
            elif link.status < 0:
                if link.status == txfer.CRC_ERROR:
                    print('ERROR: CRC_ERROR')
                elif link.status == txfer.PAYLOAD_ERROR:
                    print('ERROR: PAYLOAD_ERROR')
                elif link.status == txfer.STOP_BYTE_ERROR:
                    print('ERROR: STOP_BYTE_ERROR')
                else:
                    print('ERROR: {}'.format(link.status))
                
        
    except KeyboardInterrupt:
        link.close()