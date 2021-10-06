#include "SerialTransfer.h"


SerialTransfer myTransfer;

struct STRUCT {
  char z;
  double y;
} testStruct;

char arr[6];


void setup()
{
  Serial.begin(115200);
  myTransfer.begin(Serial);
}


void loop()
{
  if(myTransfer.available())
  {
    // use this variable to keep track of how many
    // bytes we've processed from the receive buffer
    uint16_t recSize = 0;

    recSize = myTransfer.rxObj(testStruct, recSize);
    recSize = myTransfer.rxObj(arr, recSize);
  }
}
