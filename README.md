# pySerialTransfer
Python package to transfer data in a fast, reliable, and packetized form.

If using this package to communicate with Arduinos, see https://github.com/PowerBroker2/SerialTransfer for the corresponding and compatible library (also available through the Arduino IDE's Libraries Manager).

# To Install
```
pip install pySerialTransfer
```

# Example Sketch
```python
from pySerialTransfer import pySerialTransfer as txfer

if __name__ == '__main__':
    try:
        link = txfer.SerialTransfer(13)
    
        link.txBuff[0] = 'h'
        link.txBuff[1] = 'i'
        link.txBuff[2] = '\n'
        
        link.send(3)
        
        while not link.available():
            if link.status < 0:
                print('ERROR: {}'.format(link.status))
            
        print('Response received:')
        
        response = ''
        for index in range(link.bytesRead):
            response += chr(link.rxBuff[index])
        
        print(response)
        link.close()
        
    except KeyboardInterrupt:
        link.close()
```
