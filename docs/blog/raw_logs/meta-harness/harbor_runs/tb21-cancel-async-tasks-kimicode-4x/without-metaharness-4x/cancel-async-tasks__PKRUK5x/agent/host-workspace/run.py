import asyncio
from typing import Callable, Awaitable


async def run_tasks(
    tasks: list[Callable[[], Awaitable[None]]],
    max_concurrent: int,
) -> None:
    semaphore = asyncio.Semaphore(max_concurrent)

    async def run_one(task: Callable[[], Awaitable[None]]) -> None:
        async with semaphore:
            await task()

    async_tasks = [asyncio.create_task(run_one(t)) for t in tasks]

    try:
        await asyncio.gather(*async_tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        for t in async_tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*async_tasks, return_exceptions=True)
        raise
