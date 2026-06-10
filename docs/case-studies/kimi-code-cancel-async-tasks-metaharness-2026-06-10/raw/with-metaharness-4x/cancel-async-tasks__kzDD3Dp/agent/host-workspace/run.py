import asyncio
from collections.abc import Awaitable, Callable


async def run_tasks(
    tasks: list[Callable[[], Awaitable[None]]],
    max_concurrent: int,
) -> None:
    if not tasks or max_concurrent <= 0:
        return

    queue: asyncio.Queue[Callable[[], Awaitable[None]]] = asyncio.Queue()
    for task in tasks:
        queue.put_nowait(task)

    async def worker() -> None:
        while True:
            try:
                task = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                await task()
            finally:
                queue.task_done()

    n_workers = min(max_concurrent, len(tasks))
    workers = [asyncio.create_task(worker()) for _ in range(n_workers)]

    try:
        await asyncio.gather(*workers)
    except BaseException:
        for w in workers:
            if not w.done():
                w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        raise
