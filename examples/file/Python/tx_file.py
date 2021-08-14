from time import sleep
from pySerialTransfer import pySerialTransfer as txfer


file = 'Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Aenean commodo ligula eget dolor. Aenean massa. Cum sociis natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus. Donec quam felis, ultricies nec, pellentesque eu, pretium quis, sem. Nulla consequat massa quis enim. Donec pede justo, fringilla vel, aliquet nec, vulputate eget, arcu. In enim justo, rhoncus ut, imperdiet a, venenatis vitae, justo. Nullam dictum felis eu pede mollis pretium. Integer tincidunt. Cras dapibus. Vivamus elementum semper nisi. Aenean vulputate eleifend tellus. Aenean leo ligula, porttitor eu, consequat vitae, eleifend ac, enim. Aliquam lorem ante, dapibus in, viverra quis, feugiat a, tellus. Phasellus viverra nulla ut metus varius laoreet. Quisque rutrum. Aenean imperdiet. Etiam ultricies nisi vel augue. Curabitur ullamcorper ultricies nisi. Nam eget dui. Etiam rhoncus. Maecenas tempus, tellus eget condimentum rhoncus, sem quam semper libero, sit amet adipiscing sem neque sed ipsum. Nam quam nunc, blandit vel, luctus pulvinar, hendrerit id, lorem. Maecenas nec odio et ante tincidunt tempus. Donec vitae sapien ut libero venenatis faucibus. Nullam quis ante. Etiam sit amet orci eget eros faucibus tincidunt. Duis leo. Sed fringilla mauris sit amet nibh. Donec sodales sagittis magna. Sed consequat, leo eget bibendum sodales, augue velit cursus nunc, quis gravida magna mi a libero. Fusce vulputate eleifend sapien. Vestibulum purus quam, scelerisque ut, mollis sed, nonummy id, metus. Nullam accumsan lorem in dui. Cras ultricies mi eu turpis hendrerit fringilla. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; In ac dui quis mi consectetuer lacinia. Nam pretium turpis et arcu. Duis arcu tortor, suscipit eget, imperdiet nec, imperdiet iaculis, ipsum. Sed aliquam ultrices mauris. Integer ante arcu, accumsan a, consectetuer eget, posuere ut, mauris. Praesent adipiscing. Phasellus ullamcorper ipsum rutrum nunc. Nunc nonummy metus. Vestib'
fileSize = len(file)
fileName = 'test.txt'


if __name__ == '__main__':
    try:
        link = txfer.SerialTransfer('COM11')
        
        link.open()
        sleep(5)
    
        while True:
            link.send(link.tx_obj(fileName))
            
            numPackets = int(fileSize / (txfer.MAX_PACKET_SIZE - 2))
            
            if numPackets % txfer.MAX_PACKET_SIZE:
                numPackets += 1
            
            
            
            for i in range(numPackets):
                fileIndex = i * txfer.MAX_PACKET_SIZE
                dataLen = txfer.MAX_PACKET_SIZE - 2
                
                if (fileIndex + (txfer.MAX_PACKET_SIZE - 2)) > fileSize:
                    dataLen = fileSize - fileIndex
                
                dataStr = file[fileIndex:dataLen]
                
                sendSize = link.tx_obj(fileIndex, val_type_override='h')
                sendSize = link.tx_obj(dataStr, start_pos=sendSize)
                link.send(sendSize)
                
                sleep(1)
            
            sleep(10)
                
    except KeyboardInterrupt:
        link.close()