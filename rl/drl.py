import random
import asyncio, aiohttp
from bq_interface import register_user, Action

N_INSTANCES = 10

async def run(clients):
    while True:
        await asyncio.gather(*[
            cl.update_world()
            for cl in clients
        ])
        await asyncio.gather(*[
            cl.perform_action(random.choice(list(Action)))
            for cl in clients
        ])


async def start_n_more_clients(clients, n):
    if n == 0:
        await run(clients)
    else:
        async with aiohttp.ClientSession() as sess, register_user(sess, f"smartboi-{n}", f"aaaaa") as cl:
            # await asyncio.sleep(0.2)
            await start_n_more_clients(clients + [cl], n - 1)

async def main():
    await start_n_more_clients([], N_INSTANCES)

if __name__ == "__main__":
    asyncio.run(main())
