# Test results

Verified in the release candidate workspace. Commands and outputs follow.

```text
Python 3.12.14
websockets 16.0
$ python agent_ws_demo.py
{"type": "task.result", "task_id": "demo-1", "status": "completed", "result": "pong"}
$ python -m unittest -v
test_bad_result (test_agent_ws_demo.WebSocketTests.test_bad_result) ... ok
test_invalid_dispatch_is_not_executed (test_agent_ws_demo.WebSocketTests.test_invalid_dispatch_is_not_executed) ... ok
test_invalid_token (test_agent_ws_demo.WebSocketTests.test_invalid_token) ... ok
test_malformed_auth (test_agent_ws_demo.WebSocketTests.test_malformed_auth) ... ok
test_nonempty_ping_args (test_agent_ws_demo.WebSocketTests.test_nonempty_ping_args) ... ok
test_roundtrip (test_agent_ws_demo.WebSocketTests.test_roundtrip) ... ok
test_unknown_device (test_agent_ws_demo.WebSocketTests.test_unknown_device) ... ok
test_unknown_tool (test_agent_ws_demo.WebSocketTests.test_unknown_tool) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.152s

OK
```
