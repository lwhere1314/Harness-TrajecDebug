import asyncio
from typing import Callable, Awaitable


async def run_tasks(tasks: list[Callable[[], Awaitable[None]]], max_concurrent: int) -> None:
    if not tasks or max_concurrent <= 0:
        return

    idx = 0
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal idx
        while True:
            async with lock:
                if idx >= len(tasks):
                    break
                task = tasks[idx]
                idx += 1
            await task()

    num_workers = min(max_concurrent, len(tasks))
    workers = [asyncio.create_task(worker()) for _ in range(num_workers)]

    try:
        await asyncio.gather(*workers)
    except BaseException:
        for w in workers:
            if not w.done():
                w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        raise
