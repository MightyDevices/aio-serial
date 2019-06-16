# AIOSerial

A simple yet functional _asyncio_ wrapper for _pyserial_.

## How to install
1. Clone the repository or use it as a submodulde for your project:
`git clone https://github.com/MightyDevices/aioserial AIOSerial` OR 
`git submodule add https://github.com/MightyDevices/aioserial AIOSerial`
2. Install the requirements: OR for your virtual env
`pip install -r requirements.txt`

## How to use

Constructor uses the same parameters as `serial.Serial`. The only difference is 
that the port name (parameter `port`) must be a valid port name as the port 
will be open during the object creation. No `open` function is present.

Please find the Example.py for the full-blown use case with proper exception 
handling. 

Since I've converted this project to become a python module please 
copy Example.py file to the AIOSerial parent directory before executing
 
`cp Example.py ../Example.py`

**Two ways to open port:**

```python
from AIOSerial.AIOSerial import *

# 1. direct object creation
aios = AIOSerial('COM3', baudrate=115200)
# do your stuff here
# ...
pass
# close the port
await aios.close()

# 2. using 'async with' compound statement
async with AIOSerial('COM3', baudrate=115200) as aios:
    # do your stuff here
    # ...
    pass
    # no need to close the port, it will be closed after leaving 
    # the 'async with' block
```

**Read and write operations use `byte-strings` or `bytearrays` and work 
like this:**

```python
import asyncio as aio
from AIOSerial.AIOSerial import *

# open the port with following settings
async with AIOSerial('COM18', baudrate=115200) as aios:
    # send some data, here we use the AT protocol as it is one of the
    # most popular ways for the communication over the serial port
    await aios.write(b"AT\r\n")
    # read may fail if the peer device does not understand the AT
    # command
    try:
        # read with timeout
        rcvd = await aio.wait_for(aios.read(), timeout=1.0)
        # print the data received
        print(f"data received: {rcvd}")
    # read timeout
    except aio.TimeoutError:
        print("reception timed out ;-(")
```
