from enum import Enum
import random
import asyncio, aiohttp, websockets
from urllib.parse import urlencode
import json

GRADIENT = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "


VISION_SIZE = 5

BREADQUEST_SERVER = "http://localhost:2080/"
BREADQUEST_SERVER_WS = "ws://localhost:2080/"

class Direction(Enum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3

class TileType(Enum):
    AIR = 0
    WALL = 1
    TRAIL = 2
    MY_TRAIL = 3
    INGREDIENT = 4
    SPECIAL = 5

    def get_category(id, my_color=-1):
        if id == 128:
            return TileType.AIR
        elif 129 <= id < 129 + 8:
            return TileType.WALL
        elif 137 <= id < 137 + 8:
            color = id - 137
            if color == my_color:
                return TileType.MY_TRAIL
            else:
                return TileType.TRAIL
        elif 145 <= id <= 148:
            return TileType.INGREDIENT
        elif 149 <= id <= 150:
            return TileType.SPECIAL
        else:
            # TODO: Handle symbols
            return TileType.WALL

    def get_symbol(self):
        if self == TileType.AIR:
            return '`'
        if self == TileType.WALL:
            return '#'
        if self == TileType.TRAIL:
            return '.'
        if self == TileType.MY_TRAIL:
            return ','
        if self == TileType.INGREDIENT:
            return '*'
        if self == TileType.SPECIAL:
            return '='


class RegisterFailedException(Exception):
    pass

def register_user(sess, name, pw, email="aaaa@aa.aa", avatar=7):
    class LoggedInClient:
        def __init__(self, ws, sid):
            self.sid = sid
            self.ws = ws
            self.name = name
            self.avatar = avatar

            self.entered = False
            self.world = {} # {(Δx, Δy): tileId}
            self.bread_count = 0

        async def __aenter__(self):
            print("registering", name)
            reg_data = {"username": name, "password": pw, "email": email, "avatar": str(avatar)}
            print(reg_data)

            res = await sess.post(BREADQUEST_SERVER + "createAccountAction", data=reg_data)

            login_data = {"username": name, "password": pw}

            res = await sess.post(BREADQUEST_SERVER + "loginAction", data=login_data)
            j = await res.json()
            if j["success"]:
                sid = res.cookies.get("connect.sid").value
                print("reg sid", sid)
            else:
                raise RegisterFailedException()

            cookies = {"Cookie": urlencode({"connect.sid": sid})}
            print(cookies)
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
            await self.ws.send(json.dumps(
                [ { "commandName": "walk", "direction": direction.value } ]
            ))
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
                    self.entered = True
                    self.bread_count = cmd["breadCount"]
                elif cmd["commandName"] == "setTiles":
                    self.world.clear()
                    size = cmd["size"]
                    center = size // 2
                    for i, t in enumerate(cmd["tileList"]):
                        xi, yi = i % size, i // size
                        dx, dy = xi - center, yi - center
                        self.world[(dx, dy)] = t

        async def walk(self, direction):
            await self.ws.send(json.dumps(
                [ { "commandName": "walk", "direction": direction.value } ]
            ))
            res = json.loads(await self.ws.recv())
            assert res["success"]

    return LoggedInClient(None, None)

async def main():
    async with aiohttp.ClientSession() as sess:
        name = "apio-" + str(random.randrange(0, 10**10))
        async with register_user(sess, name, "aaa") as cl:
            print(cl)
            await cl.update_world()
            await cl.walk(Direction.UP)
            await cl.walk(Direction.RIGHT)
            await cl.update_world()
            print(cl.world)

            xs = [x for x, y in cl.world.keys()]
            ys = [y for x, y in cl.world.keys()]
            minx, maxx = min(xs), max(xs)
            miny, maxy = min(ys), max(ys)
            for y in range(miny, maxy + 1):
                for x in range(minx, maxx + 1):
                    if (x, y) in cl.world:
                        print(TileType.get_category(cl.world[(x, y)], cl.avatar).get_symbol(), end="")
                    else:
                        print(" ", end="")
                print()


if __name__ == "__main__":
    asyncio.run(main())
