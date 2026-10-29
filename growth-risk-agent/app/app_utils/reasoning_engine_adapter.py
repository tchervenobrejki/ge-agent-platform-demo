# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Serve the reasoning_engine ``{class_method, input}`` contract over HTTP.

Exists to guarantee support for the Google Cloud console playground and Gemini
(via ADK registration), which both invoke the engine through this contract.
Agent Runtime forwards calls to ``/api/reasoning_engine`` (sync) and
``/api/stream_reasoning_engine`` (streaming); dispatch is limited to the
:class:`AdkApp` ``register_operations()`` methods so the wire output matches an
agent packaged for Agent Runtime.
"""

import inspect
import json
import logging
import os

from agentplatform.agent_engines.templates.adk import AdkApp
from fastapi import FastAPI, HTTPException, Request, encoders, responses
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app.app_utils import services

logger = logging.getLogger(__name__)


def _no_op_instrumentor_builder(project_id: str) -> None:
    """No-op so set_up() keeps the startup instrumentor and generate_content spans."""
    return None


def _has_content(event: object) -> bool:
    """True unless the event is a content-less checkpoint (agent start/end)."""
    if not isinstance(event, dict):
        return True
    return bool((event.get("content") or {}).get("parts"))


def _skip_empty_events() -> bool:
    """Evaluation copy only (STREAM_SKIP_EMPTY_EVENTS=true)."""
    return os.getenv("STREAM_SKIP_EMPTY_EVENTS", "").lower() == "true"


def _log_call(route: str, class_method: str, kwargs: dict, output: object = None) -> None:
    """Diagnostics for console Agent Evaluation (LOG_REASONING_ENGINE_CALLS=true)."""
    if os.getenv("LOG_REASONING_ENGINE_CALLS", "").lower() != "true":
        return
    summary = ""
    if isinstance(output, dict) and isinstance(output.get("events"), list):
        events = output["events"]
        empty = sum(not _has_content(e) for e in events)
        summary = f" events={len(events)} without_content={empty}"
    logger.warning(
        "reasoning_engine call: route=%s method=%s input_keys=%s%s",
        route,
        class_method,
        sorted(kwargs),
        summary,
    )


def attach_reasoning_engine_routes(app: FastAPI) -> None:
    """Register reasoning_engine routes that dispatch to an AdkApp."""
    runtime: AdkApp | None = None
    streaming_methods: set[str] = set()
    sync_methods: set[str] = set()

    def get_runtime() -> AdkApp:
        nonlocal runtime, streaming_methods, sync_methods
        if runtime is None:
            from app.agent import app as adk_app

            # Reuse the process-wide services so sessions created here are
            # visible to the adk_api and A2A paths, and vice versa (see services.py).
            runtime = AdkApp(
                app=adk_app,
                session_service_builder=services.get_session_service,
                artifact_service_builder=services.get_artifact_service,
                memory_service_builder=services.get_memory_service,
                instrumentor_builder=_no_op_instrumentor_builder,
            )
            runtime.set_up()
            operations = runtime.register_operations()
            streaming_methods = set(operations.get("stream", [])) | set(
                operations.get("async_stream", [])
            )
            sync_methods = set(operations.get("", [])) | set(
                operations.get("async", [])
            )
        return runtime

    def resolve_method(class_method: str, *, streaming: bool):
        rt = get_runtime()
        allowed = streaming_methods if streaming else sync_methods
        if class_method not in allowed:
            raise HTTPException(
                status_code=404,
                detail=f"Unsupported reasoning_engine method: {class_method!r}",
            )
        return getattr(rt, class_method)

    @app.post("/api/stream_reasoning_engine")
    async def stream_query(request: Request) -> responses.StreamingResponse:
        body = await request.json()
        method = resolve_method(body["class_method"], streaming=True)
        kwargs = body.get("input") or {}
        _log_call("stream", body["class_method"], kwargs)
        stream = (
            await method(**kwargs)
            if inspect.iscoroutinefunction(method)
            else method(**kwargs)
        )

        # Resumable runs emit content-less agent checkpoint events, which the
        # console's Agent Evaluation fails on ("'NoneType' object has no
        # attribute 'get'"), so the evaluation copy drops them from the stream.
        # The session still stores them, so resuming after approval works.
        skip_empty = _skip_empty_events()

        async def generator():
            events = (
                stream
                if hasattr(stream, "__aiter__")
                else iterate_in_threadpool(stream)
            )
            async for event in events:
                encoded = encoders.jsonable_encoder(event)
                if skip_empty and not _has_content(encoded):
                    continue
                yield json.dumps(encoded) + "\n"

        return responses.StreamingResponse(
            content=generator(), media_type="application/json"
        )

    @app.post("/api/reasoning_engine")
    async def query(request: Request) -> responses.JSONResponse:
        body = await request.json()
        method = resolve_method(body["class_method"], streaming=False)
        kwargs = body.get("input") or {}
        if inspect.iscoroutinefunction(method):
            output = await method(**kwargs)
        else:
            output = await run_in_threadpool(method, **kwargs)
        encoded = encoders.jsonable_encoder(output)
        # The console's Agent Evaluation reads the session back after every
        # turn (async_get_session) and fails on content-less checkpoint events,
        # so the evaluation copy drops them here too.
        if (
            _skip_empty_events()
            and body["class_method"] in ("get_session", "async_get_session")
            and isinstance(encoded, dict)
            and isinstance(encoded.get("events"), list)
        ):
            encoded["events"] = [e for e in encoded["events"] if _has_content(e)]
        _log_call("sync", body["class_method"], kwargs, encoded)
        return responses.JSONResponse(content={"output": encoded})
