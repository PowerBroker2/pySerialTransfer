#include "SerialTransfer.h"


SerialTransfer myTransfer;

float y;


void setup()
{
  Serial.begin(115200);
  myTransfer.begin(Serial);
}


void loop()
{
  if (myTransfer.available() == sizeof(y) && myTransfer.currentPacketID() == 0)
  {
    myTransfer.rxObj(y);
  }
}
