#include "SerialTransfer.h"


SerialTransfer myTransfer;

double y;


void setup()
{
  Serial.begin(115200);
  myTransfer.begin(Serial);

  y = 4.5;
}


void loop()
{
  myTransfer.sendDatum(y);
  delay(500);
}
