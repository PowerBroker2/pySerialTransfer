from time import sleep
from pySerialTransfer import pySerialTransfer as txfer


class struct(object):
    z = ''
    y = 0.0


arr = ''


if __name__ == '__main__':
    try:
        testStruct = struct
        link = txfer.SerialTransfer('COM11')
        
        link.open()
        sleep(5)
    
        while True:
            if link.available():
                recSize = 0
                
                testStruct.z = link.rx_obj(obj_type='c', start_pos=recSize)
                recSize += txfer.STRUCT_FORMAT_LENGTHS['c']
                
                testStruct.y = link.rx_obj(obj_type='f', start_pos=recSize)
                recSize += txfer.STRUCT_FORMAT_LENGTHS['f']
                
                arr = link.rx_obj(obj_type=str,
                                  start_pos=recSize,
                                  obj_byte_size=6)
                recSize += len(arr)
                
                print('{}{} | {}'.format(testStruct.z, testStruct.y, arr))
                
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