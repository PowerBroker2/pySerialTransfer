#include "SerialTransfer.h"


SerialTransfer myTransfer;

const int fileSize = 2000;
char file[fileSize];
uint16_t fileIndex = 0;
char fileName[10];


void setup()
{
  Serial.begin(115200);
  
  myTransfer.begin(Serial);
}


void loop()
{
  if (myTransfer.available())
  {
    if (!myTransfer.currentPacketID())
    {
      myTransfer.rxObj(fileName);
    }
    else if (myTransfer.currentPacketID() == 1)
    {
      myTransfer.rxObj(fileIndex);
      
      for(uint8_t i=sizeof(fileIndex); i<myTransfer.bytesRead; i++)
      {
        file[fileIndex] = (char)myTransfer.packet.rxBuff[i]);
        fileIndex++;
      }      
    }
  }
}
