import serial
import asyncio as aio


# import the queue class
from .AIOSerialQueue import *


# aio serial port exception
class AIOSerialException(Exception):
    pass


# unable to open the port
class AIOSerialNotOpenException(AIOSerialException):
    pass


# port is already closed, no communication will take place
class AIOSerialClosedException(AIOSerialException):
    pass


# port fatal error
class AIOSerialErrorException(AIOSerialException):
    pass


# serial port asyncio implementation
class AIOSerial:
    # create the serial port
    def __init__(self, *args, line_mode=False, **kwargs):
        # this may fail due to port not being present
        try:
            # open the serial port connection
            self.sp = serial.Serial(*args, **kwargs)
            # port was not opened
            if not self.sp.is_open:
                raise AIOSerialException()
        # re-raise the exception as AioSerialException
        except (AIOSerialException, serial.SerialException):
            raise AIOSerialNotOpenException("Unable to open the Serial Port")

        # are we working with the line mode? This will cause the read
        # functionality to return full text lines which is often desired
        # behavior for text protocols
        self.line_mode = line_mode

        # reception queue
        self._rxq = AIOSerialQueue()
        self._txq = AIOSerialQueue()

        # get current event loop
        self.loop = aio.get_running_loop()
        # receive and transmission tasks
        self._rx_thread_fut = self.loop.run_in_executor(None, self._rx_thread)
        self._tx_thread_fut = self.loop.run_in_executor(None, self._tx_thread)

    # open the port
    async def __aenter__(self):
        # all was done in the constructor, so we can simply return the opened
        # port
        return self

    # close the port
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # close the port
        await self.close()

    # close the serial port, do the cleanup
    async def close(self):
        # port is open?
        if self.sp.is_open:
            # cancel ongoing read-write operation to ensure that rx thread is
            # not stuck inside the read() function
            self.sp.cancel_read()
        # close both queues
        self._txq.close()
        self._rxq.close()
        # both of threads may raise an exception in case of port malfunction
        try:
            # wait for the rx/tx thread to end, these need to be gathered to
            # collect all the exceptions
            await aio.gather(self._tx_thread_fut, self._rx_thread_fut)
        # ensure that we call the close function no matter what
        finally:
            self.sp.close()

    # reception thread
    def _rx_thread(self):
        # get the proper read function according to mode
        read_func = self.sp.readline if self.line_mode else self.sp.read
        # this loop can only be broken by exceptions
        while True:
            # putting into the rx queue may fail, read may fail as well
            try:
                # read from the port
                data = read_func()
                # try putting to queue, this will raise an exception when queue
                # is closed due to port getting closed. we use the result to
                # raise the exception if any was thrown by the _rxq.put()
                aio.run_coroutine_threadsafe(self._rxq.put(data),
                                             self.loop).result()
            # queue closed exception raised? exit the loop
            except AIOSerialQueueClosed:
                break
            # serial port exceptions
            except serial.SerialException:
                # create the exception of our own
                e = AIOSerialErrorException("Serial Port Reception Error")
                # close the queue
                aio.run_coroutine_threadsafe(aio.coroutine(self._rxq.close)(e),
                                             self.loop)
                # break the loop by rising the exception that will be re-risen
                # by the close function
                raise e

    # transmission thread
    def _tx_thread(self):
        # transmission thread runs as long as this flag is valid
        while True:
            # this may fail due to serial port or queue
            try:
                # try getting data from the queue, this will raise an
                # exception when queue  is closed due to port getting closed
                data = aio.run_coroutine_threadsafe(self._txq.get(),
                                                    self.loop).result()
                # write to serial port
                self.sp.write(data)
            # queue closed exception raised? exit the loop
            except AIOSerialQueueClosed:
                break
            # serial port related exceptions
            except serial.SerialException:
                # create the exception of our own
                e = AIOSerialErrorException("Serial Port Transmission Error")
                # close the queue
                aio.run_coroutine_threadsafe(aio.coroutine(self._txq.close)(e),
                                             self.loop)
                # break the loop
                raise e

    # read from serial port
    async def read(self):
        # port might get closed
        try:
            # get data from the queue
            return await self._rxq.get()
        # closed queue means closed port
        except AIOSerialQueueClosed:
            raise AIOSerialClosedException("Serial Port is closed")

    # write to serial port
    async def write(self, data):
        # unsupported type of data
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("Data must be of type bytes or bytearray")
        # port might get closed
        try:
            # put data to port
            await self._txq.put(data)
        # closed queue means closed port
        except AIOSerialQueueClosed:
            raise AIOSerialClosedException("Serial Port is closed")
