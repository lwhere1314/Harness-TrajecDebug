import asyncio
from typing import Callable, Awaitable


async def run_tasks(tasks: list[Callable[[], Awaitable[None]]], max_concurrent: int) -> None:
    if max_concurrent <= 0:
        raise ValueError("max_concurrent must be positive")

    if not tasks:
        return

    next_index = 0
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal next_index
        while True:
            async with lock:
                if next_index >= len(tasks):
                    break
                task = tasks[next_index]
                next_index += 1
            await task()

    num_workers = min(max_concurrent, len(tasks))
    workers = [asyncio.create_task(worker()) for _ in range(num_workers)]

    try:
        await asyncio.gather(*workers)
    except BaseException as exc:
        for w in workers:
            if not w.done():
                w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        raise exc
