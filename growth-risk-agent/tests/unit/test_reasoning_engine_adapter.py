"""The evaluation copy's stream filter keeps only events that carry content."""

from app.app_utils.reasoning_engine_adapter import _has_content


def test_checkpoint_events_have_no_content():
    assert not _has_content({"author": "growth_risk_orchestrator", "content": None})
    assert not _has_content({"author": "action_pipeline"})
    assert not _has_content({"author": "x", "content": {"role": "model", "parts": []}})


def test_events_with_parts_are_kept():
    text = {"content": {"role": "model", "parts": [{"text": "Root cause: ..."}]}}
    call = {"content": {"parts": [{"function_call": {"name": "adk_request_confirmation"}}]}}
    assert _has_content(text)
    assert _has_content(call)


def test_non_dict_events_are_kept():
    assert _has_content("raw string event")


def test_call_logging_is_opt_in(monkeypatch, caplog):
    from app.app_utils.reasoning_engine_adapter import _log_call

    output = {"events": [{"content": None}, {"content": {"parts": [{"text": "hi"}]}}]}
    monkeypatch.delenv("LOG_REASONING_ENGINE_CALLS", raising=False)
    _log_call("sync", "get_session", {"session_id": "s"}, output)
    assert not caplog.records

    monkeypatch.setenv("LOG_REASONING_ENGINE_CALLS", "true")
    _log_call("sync", "get_session", {"session_id": "s"}, output)
    assert "method=get_session" in caplog.text
    assert "events=2 without_content=1" in caplog.text


def _client(monkeypatch, skip: bool):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.app_utils import reasoning_engine_adapter as adapter

    session = {
        "id": "s",
        "events": [
            {"author": "user", "content": {"parts": [{"text": "hi"}]}},
            {"author": "growth_risk_orchestrator", "content": None},
        ],
    }

    class FakeRuntime:
        def set_up(self):
            pass

        def register_operations(self):
            return {"async": ["async_get_session"], "async_stream": []}

        async def async_get_session(self, **_):
            return session

    monkeypatch.setattr(adapter, "AdkApp", lambda **_: FakeRuntime())
    monkeypatch.setenv("STREAM_SKIP_EMPTY_EVENTS", "true" if skip else "false")
    app = FastAPI()
    adapter.attach_reasoning_engine_routes(app)
    return TestClient(app)


def test_session_reads_drop_empty_events_when_enabled(monkeypatch):
    client = _client(monkeypatch, skip=True)
    body = {"class_method": "async_get_session", "input": {"user_id": "u", "session_id": "s"}}
    events = client.post("/api/reasoning_engine", json=body).json()["output"]["events"]
    assert [e["author"] for e in events] == ["user"]


def test_session_reads_unchanged_by_default(monkeypatch):
    client = _client(monkeypatch, skip=False)
    body = {"class_method": "async_get_session", "input": {"user_id": "u", "session_id": "s"}}
    events = client.post("/api/reasoning_engine", json=body).json()["output"]["events"]
    assert len(events) == 2
