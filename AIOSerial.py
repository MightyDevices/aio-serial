import serial
import asyncio as aio
import logging

# import the queue class
from .AIOExtensions.ClosableQueue import ClosableQueue, ClosableQueueClosed

# module logger
log = logging.getLogger(__name__)

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

        # reception/transmission queue
        self._rxq = ClosableQueue()
        self._txq = ClosableQueue()

        # get current event loop
        self.loop = aio.get_running_loop()
        # create receive and transmission tasks
        self._rx_thread_fut = self.loop.run_in_executor(None, self._rx_thread)
        self._tx_thread_fut = self.loop.run_in_executor(None, self._tx_thread)

        # log information
        log.info('Serial Port is now opened')

    # called when entering 'async with' block
    async def __aenter__(self):
        # all was done in the constructor, so we can simply return the opened
        # port
        return self

    # called when exiting 'async with' block
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

        # wait for the rx/tx thread to end, these need to be gathered to
        # collect all the exceptions
        await aio.gather(self._tx_thread_fut, self._rx_thread_fut)
        
        # ensure that we call the close function no matter what
        self.sp.close()

        # log information
        log.info('Serial Port is now closed')

    # reception thread
    def _rx_thread(self):
        # get the proper read function according to mode
        read_func = self.sp.readline if self.line_mode else self.sp.read
        # putting into the rx queue may fail, read may fail as well
        try:
            # this loop can only be broken by exceptions
            while True:
                # read from the port
                data = read_func()
                # try putting the data to the queue, this will raise an
                # exception when queue is closed which is in turn caused by the
                # port itself getting closed. we use the result to
                # raise the exception if any was thrown by the _rxq.put()
                aio.run_coroutine_threadsafe(self._rxq.put(data),
                                             self.loop).result()
                # log information
                log.debug(f'Serial Port RX Thread: {data}')
        # queue closed exception raised? exit the loop gracefully (no
        # exceptions) as this can only happen when the port is getting
        # intentionally closed
        except ClosableQueueClosed:
            pass
        # serial port exceptions, all of these notify that we are in some
        # serious trouble
        except serial.SerialException:
            # create the exception of our own
            e = AIOSerialErrorException("Serial Port Reception Error")
            # close the queue
            aio.run_coroutine_threadsafe(aio.coroutine(self._rxq.close)(e),
                                            self.loop)
        # log information
        log.info('Serial Port RX Thread has ended')
                
    # transmission thread
    def _tx_thread(self):
        # this may fail due to serial port or queue
        try:
            # this loop can only be broken by exceptions
            while True:
                # try getting data from the queue, this will raise an
                # exception when queue is closed due to the fact that port is
                # getting closed
                data = aio.run_coroutine_threadsafe(self._txq.get(),
                                                    self.loop).result()
                # write the data to the serial port
                self.sp.write(data)
                # log information
                log.debug(f'Serial Port TX Thread: {data}')
        # queue closed exception raised? exit the loop gracefully (no
        # exceptions) as this can only happen when the port is getting
        # intentionally closed
        except ClosableQueueClosed:
            pass
        # serial port related exceptions
        except serial.SerialException:
            # create the exception of our own
            e = AIOSerialErrorException("Serial Port Transmission Error")
            # close the queue
            aio.run_coroutine_threadsafe(aio.coroutine(self._txq.close)(e),
                                            self.loop)
        # log information
        log.info('Serial Port RX Thread has ended')

    # read from serial port
    async def read(self):
        # port might get closed
        try:
            # get data from the queue
            return await self._rxq.get()
        # closed queue means closed port
        except ClosableQueueClosed:
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
