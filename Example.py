# basic imports
import asyncio as aio
import logging

# Since this is now a python module please copy this example file to the
# AIOSerial parent directory before executing (cp Example.py ../Example.py)

# all the asyncio-serial port related stuff
from AIOSerial.AIOSerial import (AIOSerial, AIOSerialClosedException, 
    AIOSerialErrorException, AIOSerialNotOpenException)

# AIOSerial now logs!
logging.basicConfig(level=logging.DEBUG)

# port usage example
async def example():
    # try to open the serial port and do some basic communication
    try:
        # open the port with following settings, use the line mode (return full
        #  text lines from the read method)
        async with AIOSerial('COM3', baudrate=115200, line_mode=True) as aios:
            # this is the way of accessing the serial port internals directly if
            # you are in need of altering the baudrate, etc..
            aios.sp.baudrate = 230400

            # send some data, here we use the AT protocol as it is one of the
            # most popular ways for the communication over the serial port
            await aios.write(b"AT\r\n")

            # uncomment this to get the AIOSerialClosedException
            #
            # await aios.close()

            # if you use virtual com port (like in case of usb-usart dongles)
            # you can test the AIOSerialErrorException by disconnecting the
            # dongle during following sleep period. You will still get all the 
            # data that was received before the disconnection, but you won't be 
            # able to send any (obviously)
            #
            # await aio.sleep(10)

            # read may fail if the peer device does not understand the AT
            # command
            try:
                while True:
                    # read with timeout
                    rcvd = await aio.wait_for(aios.read(), timeout=1.0)
                    # print the data received
                    print(f"data received: {rcvd}")
            # read timeout
            except aio.TimeoutError:
                print("reception timed out ;-(")
    # unable to open port
    except AIOSerialNotOpenException:
        print("Unable to open the port!")
    # port fatal error
    except AIOSerialErrorException:
        print("Port error!")
    # port already closed
    except AIOSerialClosedException:
        print("Serial port is closed!")


# run the example
if __name__ == '__main__':
    aio.run(example())
