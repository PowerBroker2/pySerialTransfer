#include "SerialTransfer.h"


SerialTransfer myTransfer;

double y;


void setup()
{
  Serial.begin(115200);
  myTransfer.begin(Serial);
}


void loop()
{
  if(myTransfer.available())
  {
    myTransfer.rxObj(y);
  }
}
