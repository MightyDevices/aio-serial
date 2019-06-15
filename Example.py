# basic imports
import asyncio as aio
# all the asyncio-serial port related stuff
from AIOSerial import AIOSerial, AIOSerialException


# port usage example
async def example():
    # try to open the serial port and do some basic communication
    try:
        # open the port with following settings, use the line mode (return full
        #  text lines from the read method)
        async with AIOSerial('COM18', baudrate=115200, line_mode=True) as aios:
            # this is the way of accessing the serial port internals directly if
            # you are in need of altering the baudrate, etc..
            aios.sp.baudrate = 230400
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
    # all serial port related exceptions end up here
    except AIOSerialException:
        print("Serial port error!")


# run the example
if __name__ == '__main__':
    aio.run(example())
