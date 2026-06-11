import asyncio
from typing import Callable, Awaitable


async def run_tasks(
    tasks: list[Callable[[], Awaitable[None]]],
    max_concurrent: int,
) -> None:
    if max_concurrent <= 0:
        raise ValueError("max_concurrent must be a positive integer")

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _worker(task: Callable[[], Awaitable[None]]) -> None:
        async with semaphore:
            await task()

    task_list = [asyncio.create_task(_worker(t)) for t in tasks]

    try:
        await asyncio.gather(*task_list)
    except asyncio.CancelledError:
        for t in task_list:
            if not t.done():
                t.cancel()
        try:
            await asyncio.gather(*task_list, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        raise
