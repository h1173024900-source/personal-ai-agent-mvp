import asyncio
import secrets
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

import agent_ws_demo as demo


class WebSocketTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.token = secrets.token_urlsafe(32)
        self.task = {"type": "task.dispatch", "task_id": "example",
                     "tool": "ping", "args": {}}
        self.results = []

        async def handler(ws):
            await demo.cloud(ws, {"test-device": self.token},
                             self.task, self.results.append)

        self.server = await serve(handler, demo.HOST, 0, max_size=demo.LIMIT,
                                  compression=None, origins=[None])
        self.addAsyncCleanup(self.server.wait_closed)
        self.addAsyncCleanup(self.server.close)
        self.url = f"ws://{demo.HOST}:{self.server.sockets[0].getsockname()[1]}"

    async def auth(self, ws, device_id="test-device", token=None):
        await demo.send(ws, {"type": "auth", "device_id": device_id,
                             "token": self.token if token is None else token})

    async def assert_policy_close(self, ws):
        with self.assertRaises(ConnectionClosed) as exc:
            await demo.receive(ws)
        self.assertEqual(exc.exception.rcvd.code, 1008)
        self.assertEqual(self.results, [])

    async def run_agent(self):
        await asyncio.wait_for(demo.local_agent(
            self.url, "test-device", self.token), timeout=10)
        self.assertEqual(len(self.results), 1)
        return self.results[0]

    async def test_roundtrip(self):
        self.assertEqual(await self.run_agent(), {
            "type": "task.result", "task_id": "example",
            "status": "completed", "result": "pong"})

    async def test_unknown_tool(self):
        self.task["tool"] = "unknown"
        self.assertEqual((await self.run_agent())["status"], "rejected")

    async def test_nonempty_ping_args(self):
        self.task["args"] = {"unexpected": True}
        self.assertEqual((await self.run_agent())["status"], "rejected")

    async def test_invalid_token(self):
        async with connect(self.url, proxy=None) as ws:
            await self.auth(ws, token=secrets.token_urlsafe(32))
            await self.assert_policy_close(ws)

    async def test_unknown_device(self):
        async with connect(self.url, proxy=None) as ws:
            await self.auth(ws, device_id="unknown")
            await self.assert_policy_close(ws)

    async def test_malformed_auth(self):
        for frame in ("{", "[]", '{"type":"auth","type":"auth"}', b"binary"):
            with self.subTest(frame=frame):
                async with connect(self.url, proxy=None) as ws:
                    await ws.send(frame)
                    await self.assert_policy_close(ws)

    async def test_bad_result(self):
        for fields in ({"task_id": "wrong"}, {"result": "wrong"},
                       {"status": "invented"}):
            with self.subTest(fields=fields):
                async with connect(self.url, proxy=None) as ws:
                    await self.auth(ws)
                    self.assertEqual(await demo.receive(ws), {"type": "auth.ok"})
                    self.assertEqual(await demo.receive(ws), self.task)
                    result = demo.execute(self.task)
                    result.update(fields)
                    await demo.send(ws, result)
                    await self.assert_policy_close(ws)

    async def test_invalid_dispatch_is_not_executed(self):
        for fields in ({"task_id": ""}, {"args": []}, {"tool": []},
                       {"type": "unknown"}, {"extra": 1}):
            with self.subTest(fields=fields):
                with self.assertRaises(demo.ProtocolError):
                    demo.execute({**self.task, **fields})
