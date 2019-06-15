import serial
import asyncio as aio


# exception
class AIOSerialQueueClosed(Exception):
    pass


# queue with closed signal
class AIOSerialQueue(aio.Queue):
    # constructor
    def __init__(self, *args, **kwargs):
        # this event will be used to notify about channel that is represented by
        # the queue being closed
        self._closed_ev = aio.Event()
        # create queue
        super().__init__(*args, **kwargs)

    # close the queue channel
    def close(self):
        # .. by emitting the closed event
        self._closed_ev.set()

    # get value without waiting
    def get_nowait(self):
        # queue empty and closed?
        if self.qsize() == 0 and self._closed_ev.is_set():
            raise AIOSerialQueueClosed()
        # use the underlying implementation
        return super().get_nowait()

    # get value from queue, values can be fetched even when the queue is closed
    async def get(self):
        # got elements in the queue, then there is no need to wait.
        if self.qsize() > 0:
            return super().get_nowait()
        # queue closed
        elif self._closed_ev.is_set():
            raise AIOSerialQueueClosed()

        # create two tasks
        task_q = aio.create_task(super().get())
        task_e = aio.create_task(self._closed_ev.wait())
        # wait for the queue to have something for us or wait for the closed
        # event
        _, pend = await aio.wait([task_q, task_e],
                                 return_when=aio.FIRST_COMPLETED)
        # cancel pending tasks
        for p in pend:
            p.cancel()
        # closed event was set!
        if task_e.done():
            raise AIOSerialQueueClosed()

        # get data from the queue
        return task_q.result()

    # put data into queue without waiting
    def put_nowait(self, item):
        # queue is closed
        if self._closed_ev.is_set():
            raise AIOSerialQueueClosed()
        # use underlying implementation
        super().put_nowait(item)

    # put value into queue
    async def put(self, item):
        # queue closed, no point in further processing
        if self._closed_ev.is_set():
            raise AIOSerialQueueClosed()
        # create two tasks
        task_q = aio.create_task(super().put(item))
        task_e = aio.create_task(self._closed_ev.wait())
        # wait for the queue to have something for us or wait for the closed
        # event
        _, pend = await aio.wait([task_e, task_q],
                                 return_when=aio.FIRST_COMPLETED)
        # cancel pending tasks
        for p in pend:
            p.cancel()
        # closed event was set!
        if task_e.done():
            raise AIOSerialQueueClosed()


# aio serial port exception
class AIOSerialException(Exception):
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
            raise AIOSerialException("Unable to open Serial Port")
        # are we working with the line mode?
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
        # start by closing the tx queue
        self._txq.close()
        # wait for tx thread to end processing (meaning that all queue contents
        # are sent)
        await self._tx_thread_fut

        # close the rx queue
        self._rxq.close()
        # cancel ongoing read-write operation
        self.sp.cancel_read()
        # wait for the rx/tx thread to end
        await self._rx_thread_fut

        # and finally close the port
        self.sp.close()

    # reception thread
    def _rx_thread(self):
        # get the proper read function according to mode
        read_func = self.sp.readline if self.line_mode else self.sp.read
        # end when rx is done
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
                # close the queue
                aio.run_coroutine_threadsafe(aio.coroutine(self._rxq.close)(),
                                             self.loop)
                # break the loop
                break

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
                # close the queue
                aio.run_coroutine_threadsafe(aio.coroutine(self._txq.close)(),
                                             self.loop)
                # break the loop
                break

    # read from serial port
    async def read(self):
        # port might get closed
        try:
            # get data from the queue
            return await self._rxq.get()
        # closed queue means closed port
        except AIOSerialQueueClosed:
            raise AIOSerialException("Serial Port closed!")

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
            raise AIOSerialException("Serial Port closed!")
