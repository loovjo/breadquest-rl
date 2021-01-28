import random
import asyncio, aiohttp, websockets
from urllib.parse import urlencode
import json

GRADIENT = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "


VISION_SIZE = 5

BREADQUEST_SERVER = "http://localhost:2080/"
BREADQUEST_SERVER_WS = "ws://localhost:2080/"

class RegisterFailedException(Exception):
    pass

def register_user(sess, name, pw, email="aaaa@aa.aa", avatar=0):
    class LoggedInClient:
        def __init__(self, ws, sid):
            self.sid = sid
            self.ws = ws
            self.name = name

            self.entered = False
            self.world = {} # {(Δx, Δy): tileId}
            self.bread_count = 0

        async def __aenter__(self):
            reg_data = {"username": name, "password": pw, "email": email, "avatar": str(avatar)}

            res = await sess.post(BREADQUEST_SERVER + "createAccountAction", data=reg_data)
            if not (await res.json())["success"]:
                print("oh no")
                raise RegisterFailedException()
            sid = res.cookies.get("connect.sid").value

            cookies = {"Cookie": urlencode({"connect.sid": sid})}
            print(cookies)

            login_data = {"username": name, "password": pw}
            res = await sess.post(BREADQUEST_SERVER + "loginAction", data=login_data, headers=cookies)
            print(res)

            if not (await res.json())["success"]:
                print("oh no")
                raise RegisterFailedException()

            ws = await websockets.connect(
                BREADQUEST_SERVER_WS + "gameUpdate",
                extra_headers={"Cookie": "connect.sid=" + sid},
            )

            self.ws = ws
            self.sid = sid

            return LoggedInClient(ws, sid)

        async def __aexit__(self, exc_type, exc, tb):
            await self.ws.close()

        def __str__(self):
            return f"LoggedInClient(name={repr(self.name)}, sid={repr(self.sid)})"

        async def update_world(self):
            commands = \
                [ { "commandName": "getTiles", "size": VISION_SIZE }
                , { "commandName": "getEntities" }
                , { "commandName": "getInventoryChanges" }
                ]

            if not self.entered:
                commands.insert(0, { "commandName": "startPlaying" })

            await self.ws.send(json.dumps(commands))

            res = json.loads(await self.ws.recv())
            assert res["success"]
            for cmd in res["commandList"]:
                if cmd["commandName"] == "setLocalPlayerInfo":
                    self.bread_count = cmd["breadCount"]
                elif cmd["commandName"] == "setTiles":
                    self.world.clear()
                    size = cmd["size"]
                    center = size // 2
                    for i, t in enumerate(cmd["tileList"]):
                        xi, yi = i % size, i // size
                        dx, dy = xi - center, yi - center
                        self.world[(dx, dy)] = t

    return LoggedInClient(None, None)

async def main():
    async with aiohttp.ClientSession() as sess:
        name = "apio-" + str(random.randrange(0, 10**10))
        async with register_user(sess, name, "aaa") as cl:
            print(cl)
            await cl.update_world()
            print(cl.world)

            xs = [x for x, y in cl.world.keys()]
            ys = [y for x, y in cl.world.keys()]
            minx, maxx = min(xs), max(xs)
            miny, maxy = min(ys), max(ys)
            for y in range(miny, maxy + 1):
                for x in range(minx, maxx + 1):
                    if (x, y) in cl.world:
                        print(GRADIENT[min(len(GRADIENT) - 1, 127 - cl.world[(x, y)])], end="")
                    else:
                        print(" ", end="")
                print()


if __name__ == "__main__":
    asyncio.run(main())
