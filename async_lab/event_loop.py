import asyncio
import time

# Blocking-call rule: in a single event loop, one blocking call like time.sleep()
# stops all other coroutines on that loop until it returns.

async def coro_a():
    print("coro_a: before wait")
    time.sleep(1)  # blocking on purpose
    print("coro_a: after wait")

async def coro_b():
    print("coro_b: before wait")
    await asyncio.sleep(1)
    print("coro_b: after wait")

async def main():
    # Record start time
    start = time.perf_counter()

    await coro_a()
    await coro_b()

    # Calculate and print total elapsed time
    elapsed = time.perf_counter() - start
    print(f"Total elapsed time: {elapsed:.3f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
