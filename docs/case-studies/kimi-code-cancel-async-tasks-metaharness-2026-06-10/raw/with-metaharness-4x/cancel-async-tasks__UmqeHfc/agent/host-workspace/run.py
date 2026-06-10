import asyncio
from collections.abc import Awaitable, Callable


async def run_tasks(tasks: list[Callable[[], Awaitable[None]]], max_concurrent: int) -> None:
    """Run async tasks with a limit on concurrent execution.

    If the caller is cancelled (e.g. KeyboardInterrupt), active tasks are
    cancelled and awaited so their ``finally`` cleanup blocks still run.
    """
    if max_concurrent <= 0:
        return

    task_iter = iter(tasks)
    workers: list[asyncio.Task[None]] = []

    async def worker() -> None:
        while True:
            try:
                task_factory = next(task_iter)
            except StopIteration:
                break
            await task_factory()

    for _ in range(min(max_concurrent, len(tasks))):
        workers.append(asyncio.create_task(worker()))

    try:
        await asyncio.gather(*workers)
    except BaseException:
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        raise
