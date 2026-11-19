"""Loopback-only authenticated WebSocket task demo."""
import asyncio
import json
import re
import secrets

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

HOST = "127.0.0.1"
TIMEOUT = 5
LIMIT = 4096
IDENTIFIER = re.compile(r"[a-zA-Z0-9_-]{1,64}")


class ProtocolError(ValueError):
    """Invalid peer message."""


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate key")
        result[key] = value
    return result


def invalid_constant(_):
    raise ProtocolError("invalid JSON constant")


async def receive(ws):
    raw = await asyncio.wait_for(ws.recv(), TIMEOUT)
    if not isinstance(raw, str) or len(raw.encode()) > LIMIT:
        raise ProtocolError("invalid frame")
    try:
        value = json.loads(raw, object_pairs_hook=unique_fields,
                           parse_constant=invalid_constant)
    except (ValueError, RecursionError):
        raise ProtocolError("invalid JSON") from None
    if not isinstance(value, dict):
        raise ProtocolError("expected object")
    return value


async def send(ws, message):
    await ws.send(json.dumps(message, allow_nan=False))


def ping(args):
    if args:
        raise ProtocolError("ping takes no arguments")
    return "pong"


TOOLS = {"ping": ping}


def execute(task):
    task_id = task.get("task_id")
    if (
        set(task) != {"type", "task_id", "tool", "args"}
        or task["type"] != "task.dispatch"
        or not isinstance(task_id, str) or not IDENTIFIER.fullmatch(task_id)
        or not isinstance(task["tool"], str)
        or not isinstance(task["args"], dict)
    ):
        raise ProtocolError("invalid dispatch")
    handler = TOOLS.get(task["tool"])
    status, result = "rejected", None
    if handler is not None:
        try:
            result = handler(task["args"])
        except ProtocolError:
            pass
        else:
            status = "completed"
    return {"type": "task.result", "task_id": task_id,
            "status": status, "result": result}


def validate_result(message, task):
    if (
        set(message) != {"type", "task_id", "status", "result"}
        or message["type"] != "task.result"
        or message["task_id"] != task["task_id"]
    ):
        raise ProtocolError("invalid task result")
    if message["status"] == "rejected" and message["result"] is None:
        return message
    if (task["tool"] == "ping" and task["args"] == {}
            and message["status"] == "completed" and message["result"] == "pong"):
        return message
    raise ProtocolError("invalid result payload")


def authenticated(auth, credentials):
    if set(auth) != {"type", "device_id", "token"} or auth["type"] != "auth":
        return False
    device_id, candidate = auth["device_id"], auth["token"]
    if not isinstance(device_id, str) or not isinstance(candidate, str) or not candidate.isascii():
        return False
    expected = credentials.get(device_id)
    return expected is not None and secrets.compare_digest(candidate.encode(), expected.encode())


async def cloud(ws, credentials, task, on_result):
    try:
        auth = await receive(ws)
        if not authenticated(auth, credentials):
            raise ProtocolError("unauthorized")
        await send(ws, {"type": "auth.ok"})
        await send(ws, task)
        on_result(validate_result(await receive(ws), task))
    except (ProtocolError, asyncio.TimeoutError):
        await ws.close(code=1008, reason="policy violation")
    except ConnectionClosed:
        pass


async def local_agent(url, device_id, token):
    async with connect(url, max_size=LIMIT, compression=None, proxy=None) as ws:
        await send(ws, {"type": "auth", "device_id": device_id, "token": token})
        if await receive(ws) != {"type": "auth.ok"}:
            raise ProtocolError("authentication not acknowledged")
        await send(ws, execute(await receive(ws)))
        # Wait for server closure so the CLI only succeeds after server validation.
        await asyncio.wait_for(ws.wait_closed(), TIMEOUT)
        if ws.close_code != 1000:
            raise ProtocolError("server did not accept task result")


async def main():
    device_id = "local-demo"
    token = secrets.token_urlsafe(32)
    task = {"type": "task.dispatch", "task_id": "demo-1",
            "tool": "ping", "args": {}}
    results = []

    async def handler(ws):
        await cloud(ws, {device_id: token}, task, results.append)

    async with serve(handler, HOST, 0, max_size=LIMIT, compression=None,
                     origins=[None]) as server:
        port = server.sockets[0].getsockname()[1]
        await local_agent(f"ws://{HOST}:{port}", device_id, token)
    if not results:
        raise ProtocolError("no task result received")
    print(json.dumps(results[0]))


if __name__ == "__main__":
    asyncio.run(main())
