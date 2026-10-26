import asyncio
import time 

async def say_hello():
    time.sleep(1)  # This is a blocking call and will block the event loop 
    await asyncio.sleep(1)
    print("inside say_hello")
    return "hello result"

async def say_world():
    await asyncio.sleep(1)
    print("inside say_world")
    return "world result"

async def wrapper():
    print("inside wrapper, about to await say_hello")
    value = await say_hello()
    await asyncio.sleep(1)
    print(f"inside wrapper, got: {value}")
    return value + " from wrapper"

async def main():
    print("inside main, about to await wrapper")
    result1 = await wrapper()
    print("inside main, got first:", result1)

    print("inside main, about to await say_world")
    result2 = await say_world()
    print("inside main, got second:", result2)

if __name__ == "__main__":
    asyncio.run(main())
