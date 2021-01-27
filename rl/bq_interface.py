import random
import asyncio, aiohttp, websockets

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

        async def __aenter__(self):
            reg_data = {"username": name, "password": pw, "email": email, "avatar": str(avatar)}

            res = await sess.post(BREADQUEST_SERVER + "createAccountAction", data=reg_data)
            if not (await res.json())["success"]:
                print("oh no")
                raise RegisterFailedException()

            sid = res.cookies.get("connect.sid").value

            ws = await websockets.connect(
                BREADQUEST_SERVER_WS + "gameUpdate",
                extra_headers={"Cookie": "connect.sid=" + sid},
            )

            print(ws)

            self.ws = ws
            self.sid = sid

            return LoggedInClient(ws, sid)

        async def __aexit__(self, exc_type, exc, tb):
            await self.ws.close()

        def __str__(self):
            return f"LoggedInClient(name={repr(self.name)}, sid={repr(self.sid)})"

    return LoggedInClient(None, None)

async def main():
    async with aiohttp.ClientSession() as sess:
        name = "apio-" + str(random.randrange(0, 10**10))
        async with register_user(sess, name, "aaa") as cl:
            print(cl)

if __name__ == "__main__":
    asyncio.run(main())
