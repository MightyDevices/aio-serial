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
        # queue exception, can be set by using the 'close' method. after setting
        # every attempt to put more data to the queue will result in re-raising
        # the exception
        self._exc = None
        # create queue
        super().__init__(*args, **kwargs)

    # close the queue channel
    def close(self, exc=None):
        # .. by emitting the closed event
        self._closed_ev.set()
        # store the exception as well. if none is provided then use the default
        # exception for the queue closure
        self._exc = exc or AIOSerialQueueClosed()

    # get value without waiting
    def get_nowait(self):
        # queue empty and closed?
        if self.qsize() == 0 and self._closed_ev.is_set():
            raise self._exc
        # use the underlying implementation
        return super().get_nowait()

    # get value from queue, values can be fetched even when the queue is closed
    async def get(self):
        # got elements in the queue, then there is no need to wait.
        if self.qsize() > 0:
            return super().get_nowait()
        # queue closed
        elif self._closed_ev.is_set():
            raise self._exc

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
            raise self._exc

        # get data from the queue
        return task_q.result()

    # put data into queue without waiting
    def put_nowait(self, item):
        # queue is closed
        if self._closed_ev.is_set():
            raise self._exc
        # use underlying implementation
        super().put_nowait(item)

    # put value into queue
    async def put(self, item):
        # queue closed, no point in further processing
        if self._closed_ev.is_set():
            raise self._exc
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
            raise self._exc
