from enum import Enum
import random
import asyncio, aiohttp, websockets
from urllib.parse import urlencode
import json

GRADIENT = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

BREADQUEST_SERVER = "http://localhost:2080/"
BREADQUEST_SERVER_WS = "ws://localhost:2080/"

class Action(Enum):
    WALK_UP = 0
    WALK_RIGHT = 1
    WALK_DOWN = 2
    WALK_LEFT = 3

    BREAK_UP = 4
    BREAK_RIGHT = 5
    BREAK_DOWN = 6
    BREAK_LEFT = 7

    # TODO:
    PLACE_UP = 8
    PLACE_RIGHT = 9
    PLACE_DOWN = 10
    PLACE_LEFT = 11

    EAT = 12

    def get_cmd(self, client):
        if Action.WALK_UP.value <= self.value <= Action.WALK_LEFT.value:
            return [ { "commandName": "walk", "direction": self.value - Action.WALK_UP.value } ]
        elif Action.BREAK_UP.value <= self.value <= Action.BREAK_LEFT.value:
            return [ { "commandName": "removeTile", "direction": self.value - Action.BREAK_UP.value } ]
        elif Action.PLACE_UP.value <= self.value <= Action.PLACE_LEFT.value:
            for it in client.inventory.keys():
                if client.inventory[it] > 0 and TileType.get_category(it) == TileType.WALL:
                    return [{
                        "commandName": "placeTile",
                        "direction": self.value - Action.PLACE_UP.value,
                        "tile": it,
                    }]
            return []
        elif self == Action.EAT:
            return [ { "commandName": "eatBread" } ]



class TileType(Enum):
    AIR = 0
    WALL = 1
    TRAIL = 2
    MY_TRAIL = 3
    INGREDIENT = 4
    SPECIAL = 5
    ENEMY = 6

    def get_category(id, my_color=-1):
        if id == -1:
            return TileType.ENEMY
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
        if self == TileType.ENEMY:
            return '&'


class RegisterFailedException(Exception):
    pass

def register_user(vision_size, sess, name, pw, email="aaaa@aa.aa", avatar=7):
    class LoggedInClient:
        def __init__(self, ws, sid):
            self.sid = sid
            self.ws = ws
            self.name = name
            self.avatar = avatar

            self.entered = False
            self.world = {} # {(Δx, Δy): tileId}
            self.bread_count = 0
            self.inventory = {} # {tile id: count}

            self.vision_size = vision_size

        async def __aenter__(self):
            print("Registering user", name)
            reg_data = {"username": name, "password": pw, "email": email, "avatar": str(avatar)}

            res = await sess.post(BREADQUEST_SERVER + "createAccountAction", data=reg_data)
            j = await res.json()
            if j["success"]:
                print("Registration of", name, "successful")
            else:
                print("Registration of", name, "failed")

            login_data = {"username": name, "password": pw}

            res = await sess.post(BREADQUEST_SERVER + "loginAction", data=login_data)
            j = await res.json()
            if j["success"]:
                sid = res.cookies.get("connect.sid").value
                print("Logged in as", name, "successfully")
            else:
                raise RegisterFailedException()

            cookies = {"Cookie": urlencode({"connect.sid": sid})}
            if not (await res.json())["success"]:
                print("oh no")
                raise RegisterFailedException()

            ws = await websockets.connect(
                BREADQUEST_SERVER_WS + "gameUpdate",
                extra_headers={"Cookie": "connect.sid=" + sid},
            )
            print("Connected", name, "to websocket")

            self.ws = ws
            self.sid = sid

            return LoggedInClient(ws, sid)

        async def __aexit__(self, exc_type, exc, tb):
            await self.ws.close()

        def __str__(self):
            return f"LoggedInClient(name={repr(self.name)}, sid={repr(self.sid)})"

        async def update_world(self):
            commands = \
                [ { "commandName": "assertPos", "pos": {"x": 0, "y": 0, }, }
                , { "commandName": "getTiles", "size": self.vision_size*2+1 }
                , { "commandName": "getEntities" }
                , { "commandName": "getInventoryChanges" }
                ]

            if not self.entered:
                commands.insert(0, { "commandName": "startPlaying" })

            await self.ws.send(json.dumps(commands))

            res = json.loads(await self.ws.recv())
            assert res["success"]
            my_pos = (0, 0)
            for cmd in res["commandList"]:
                if cmd["commandName"] == "setLocalPlayerPos":
                    my_pos = cmd["pos"]["x"], cmd["pos"]["y"]
                elif cmd["commandName"] == "setLocalPlayerInfo":
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
                elif cmd["commandName"] == "addEntity":
                    if cmd["entityInfo"]["className"] == "Player":
                        e_id = -1
                    else:
                        continue
                    xy = cmd["entityInfo"]["pos"]
                    rpos = xy["x"] - my_pos[0], xy["y"] - my_pos[1]
                    if rpos[0] < -self.vision_size or rpos[0] > self.vision_size:
                        continue
                    if rpos[1] < -self.vision_size or rpos[1] > self.vision_size:
                        continue
                    self.world[rpos] = e_id
                elif cmd["commandName"] == "setInventory":
                    self.inventory = {int(k): v for k, v in cmd["inventory"].items()}

        async def perform_action(self, action):
            await self.ws.send(json.dumps(
                [ *action.get_cmd(self) ]
            ))
            res = json.loads(await self.ws.recv())
            assert res["success"]

    return LoggedInClient(None, None)

async def main():
    async with aiohttp.ClientSession() as sess:
        name = "apio-" + str(random.randrange(0, 10**10))
        async with register_user(3, sess, name, "aaa") as cl:
            print(cl)
            await cl.update_world()
            await cl.perform_action(Action.WALK_UP)
            await cl.perform_action(Action.WALK_RIGHT)
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
