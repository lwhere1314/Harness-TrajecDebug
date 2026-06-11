import asyncio
from typing import Callable, Awaitable


async def run_tasks(tasks: list[Callable[[], Awaitable[None]]], max_concurrent: int) -> None:
    """Run async tasks with a limit on concurrent execution.

    If the caller is cancelled (e.g. via Ctrl+C), all running tasks are
    cancelled and given a chance to run their cleanup code before the
    cancellation is re-raised.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run(task: Callable[[], Awaitable[None]]) -> None:
        async with semaphore:
            await task()

    runners = [asyncio.create_task(_run(task)) for task in tasks]

    try:
        await asyncio.gather(*runners)
    except asyncio.CancelledError:
        for r in runners:
            if not r.done():
                r.cancel()
        # Allow tasks to finish their cleanup (finally blocks, etc.)
        await asyncio.gather(*runners, return_exceptions=True)
        raise
