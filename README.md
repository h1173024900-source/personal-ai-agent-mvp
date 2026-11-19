# Personal AI Agent MVP

Phase 1: one local Python process starts a loopback WebSocket coordinator
and connects a demo device. It proves a single authenticated, request/result
round trip. It does not yet coordinate physical devices or cloud workers.

## Run

Requires Python 3.10+.

```sh
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python agent_ws_demo.py
python -m unittest -v
```

Expected demo output:

```json
{"type": "task.result", "task_id": "demo-1", "status": "completed", "result": "pong"}
```

See [TEST_RESULTS.md](TEST_RESULTS.md) for the actual verification run.

## Architecture and protocol

1. **Device → coordinator:** sends an `auth` envelope with `device_id` and
   `token`. The server checks the token against the named device in an
   in-memory credential map using constant-time comparison. The demo
   generates a fresh random token every run, never prints it, and passes it
   to both roles in-process. Unauthenticated peers receive no task.
2. **Coordinator → device:** replies `auth.ok` and sends one
   `task.dispatch` envelope with `task_id`, `tool`, and an `args` object.
3. **Device → coordinator:** validates the envelope and checks its local
   tool allowlist. Only `ping` with empty arguments executes. Unknown tools
   or invalid ping arguments receive `rejected`. A valid ping receives
   `completed` and `pong`. Both use the `task.result` envelope.
4. **Coordinator:** validates the result shape, ID and payload before recording it.

Malformed frames or protocol violations fail closed. Messages are bounded
to 4 KiB, reads time out, and the server accepts no browser Origin.
The demo binds only to IPv4 loopback, with an OS-selected port. Do not
expose it or forward its port: plaintext WebSocket is not safe for remote use.
A token identifies a peer in this demo; it does not attest the device or
prove that an untrusted worker genuinely performed a task.

## Not implemented

No AI planner, persistent scheduler, retries, distributed queue, parallel
or remote worker management, durable logs, TLS, certificate verification,
device enrollment/revocation, credential storage, rate limiting,
or operating-system sandbox. No shell, file, or network tool is exposed.
