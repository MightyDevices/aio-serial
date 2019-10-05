# AIOSerial

A simple yet functional _asyncio_ wrapper for _pyserial_.

## How to install

1. Clone the repository or use it as a submodulde for your project:
`git clone --recurse-submodules https://github.com/MightyDevices/aioserial AIOSerial` OR 
`git submodule add https://github.com/MightyDevices/aioserial AIOSerial` followed by
`git submodule update --init --recursive AIOSerial`
2. Install the requirements: `pip install -r requirements.txt`

## How to use

Constructor uses the same parameters as `serial.Serial`. The only difference is 
that the port name (parameter `port`) must be a valid port name as the port 
will be open during the object creation. No explicit `open` function is provided.

Please find the Example.py for the full-blown use case with proper exception 
handling. 

Since I've converted this project to be a python module please 
copy Example.py file to the AIOSerial parent directory before executing. 
Otherwise import issues will arise.
 
`cp Example.py ../Example.py`

**Two ways to open port:**

```python
from AIOSerial.AIOSerial import *

# 1. direct object creation
aios = AIOSerial('COM3', baudrate=115200)

# basic communication
await aios.write(b"test data")
rcvd = await aios.read()

# do your stuff here
# ...

# close the port
await aios.close()

# 2. using 'async with' compound statement
async with AIOSerial('COM3', baudrate=115200) as aios:
    # basic communication
    await aios.write(b"test data")
    rcvd = await aios.read()
    
    # do your stuff here
    # ...
    
    # no need to close the port, it will be closed after leaving 
    # the 'async with' block
    pass

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
