"""
Shared test doubles for asyncpg (FakeConnection/FakePool) and the Anthropic
SDK (FakeAnthropicClient) -- used across backend/src/tests/unit/test_hybrid.py,
test_resolver.py, test_synthesizer.py, test_llm_judge.py, test_pipeline.py.

Not shipped as production code; lives under tests/fixtures because it's
only ever imported by tests.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class _NullAsyncCtx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeConnection:
    """Routes fetch/fetchval/fetchrow/execute calls to canned responses
    based on a substring match against the SQL text, so hybrid.py's two
    concurrent legs (vector query contains "decision_embeddings", keyword
    query contains "plainto_tsquery") each get the right canned rows
    regardless of asyncio.gather's scheduling order."""

    def __init__(
        self,
        fetch_by_marker: dict[str, list[dict[str, Any]]] | None = None,
        fetchval_by_marker: dict[str, Any] | None = None,
        fetchrow_by_marker: dict[str, dict[str, Any] | None] | None = None,
    ) -> None:
        self.fetch_by_marker = fetch_by_marker or {}
        self.fetchval_by_marker = fetchval_by_marker or {}
        self.fetchrow_by_marker = fetchrow_by_marker or {}
        self.calls: list[tuple[str, str, tuple]] = []  # (method, query, args)

    def _match(self, mapping: dict, query: str):
        for marker, value in mapping.items():
            if marker in query:
                return value
        return None

    async def execute(self, query: str, *args) -> str:
        self.calls.append(("execute", query, args))
        return "OK"

    async def fetch(self, query: str, *args) -> list[dict[str, Any]]:
        self.calls.append(("fetch", query, args))
        rows = self._match(self.fetch_by_marker, query)
        return rows if rows is not None else []

    async def fetchval(self, query: str, *args) -> Any:
        self.calls.append(("fetchval", query, args))
        return self._match(self.fetchval_by_marker, query)

    async def fetchrow(self, query: str, *args) -> dict[str, Any] | None:
        self.calls.append(("fetchrow", query, args))
        return self._match(self.fetchrow_by_marker, query)

    def transaction(self):
        return _NullAsyncCtx()


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self):
        conn = self.connection

        class _Acquire:
            async def __aenter__(self_inner):
                return conn

            async def __aexit__(self_inner, *exc_info):
                return False

        return _Acquire()


def make_tool_use_message(tool_name: str, tool_input: dict, stop_reason: str = "tool_use") -> SimpleNamespace:
    """Duck-typed stand-in for anthropic.types.Message -- our code only ever
    reads .content, .stop_reason, and each content block's .type/.name/.input,
    so a SimpleNamespace is sufficient without depending on anthropic's
    internal model classes."""
    block = SimpleNamespace(type="tool_use", name=tool_name, input=tool_input)
    return SimpleNamespace(content=[block], stop_reason=stop_reason)


class FakeMessages:
    def __init__(self, response: SimpleNamespace | list[SimpleNamespace]) -> None:
        self._responses = response if isinstance(response, list) else [response]
        self._call_index = 0
        self.calls: list[dict] = []

    async def create(self, **kwargs) -> SimpleNamespace:
        self.calls.append(kwargs)
        response = self._responses[min(self._call_index, len(self._responses) - 1)]
        self._call_index += 1
        return response


class FakeAnthropicClient:
    def __init__(self, response: SimpleNamespace | list[SimpleNamespace]) -> None:
        self.messages = FakeMessages(response)
