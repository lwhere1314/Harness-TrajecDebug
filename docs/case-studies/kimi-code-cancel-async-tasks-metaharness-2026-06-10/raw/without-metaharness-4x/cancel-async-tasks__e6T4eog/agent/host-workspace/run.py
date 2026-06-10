import asyncio
from typing import Awaitable, Callable


async def run_tasks(
    tasks: list[Callable[[], Awaitable[None]]],
    max_concurrent: int,
) -> None:
    """Run async tasks with bounded concurrency and graceful cancellation."""
    if max_concurrent <= 0:
        raise ValueError("max_concurrent must be positive")

    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded(task: Callable[[], Awaitable[None]]) -> None:
        async with semaphore:
            await task()

    running = [asyncio.create_task(bounded(t)) for t in tasks]

    try:
        await asyncio.gather(*running)
    except (KeyboardInterrupt, asyncio.CancelledError):
        for t in running:
            if not t.done():
                t.cancel()
        await asyncio.gather(*running, return_exceptions=True)
        raise
