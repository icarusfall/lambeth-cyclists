"""Tests for the shared CycleBot agent.

The point of core.cyclebot is that the portal's chat page and the MCP server
run the *same* tools, so the two can't drift the way the three repos did. The
first test here is that invariant; the rest pin the loop's behaviour, which is
ours now that the tools run in-process rather than behind the MCP connector.

No network: the Notion client is injected and the Anthropic client is passed in.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core import cyclebot


# ---------------------------------------------------------------------------
# Fakes — enough of the Anthropic response shape for the loop to run
# ---------------------------------------------------------------------------


def _text(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use(name, tool_id="tu_1", **arguments):
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=arguments)


def _thinking():
    """Adaptive thinking is on by default, so responses lead with one of these."""
    return SimpleNamespace(type="thinking", thinking="hmm")


def _response(*content, stop_reason="end_turn"):
    return SimpleNamespace(content=list(content), stop_reason=stop_reason)


def _client(*responses):
    """An anthropic.Anthropic stand-in returning each response in turn."""
    api = MagicMock()
    api.messages.create.side_effect = list(responses)
    api.with_options.return_value = api
    return api


# ---------------------------------------------------------------------------
# The invariant: one set of tools, two facades
# ---------------------------------------------------------------------------


def _mcp_server():
    """Import mcp/server.py, which normally runs from its own directory.

    Its own directory goes on sys.path rather than the repo root, which is how
    Railway starts it. The bare `mcp` import inside it still finds the
    installed SDK: our mcp/ has no __init__.py, and a real package beats a
    namespace one.
    """
    import os
    import sys
    import importlib

    path = os.path.join(os.path.dirname(__file__), "..", "..", "mcp")
    path = os.path.abspath(path)
    if path not in sys.path:
        sys.path.insert(0, path)
    os.environ.setdefault("NOTION_API_TOKEN", "test-token")
    return importlib.import_module("server")


def test_the_mcp_server_exposes_exactly_the_registered_tools():
    """The whole reason the tools live in core: the two facades cannot diverge.

    If someone adds a tool to core.cyclebot, MCP clients get it for free. If
    someone adds one straight to mcp/server.py instead, this fails.
    """
    import asyncio

    exposed = {t.name for t in asyncio.run(_mcp_server().mcp.list_tools())}
    assert exposed == set(cyclebot.TOOLS)


def test_the_two_facades_describe_the_tools_identically():
    """One docstring, so the model is told the same thing either way in."""
    import asyncio

    over_mcp = {
        t.name: t.description
        for t in asyncio.run(_mcp_server().mcp.list_tools())
    }
    direct = {t["name"]: t["description"] for t in cyclebot.anthropic_tools()}
    assert over_mcp == direct


def test_every_tool_has_a_description_for_the_model():
    for spec in cyclebot.anthropic_tools():
        assert spec["description"], f"{spec['name']} has no docstring"


def test_schemas_come_from_the_signature():
    specs = {t["name"]: t["input_schema"] for t in cyclebot.anthropic_tools()}

    # A parameter with no default is required...
    assert specs["search_all"]["required"] == ["query"]
    assert specs["search_all"]["properties"]["query"]["type"] == "string"

    # ...and one with a default is not.
    assert specs["list_meetings"]["required"] == []
    assert specs["list_meetings"]["properties"]["limit"]["type"] == "integer"

    # A tool taking nothing still gets a valid object schema.
    assert specs["get_battleground_wards"] == {
        "type": "object", "properties": {}, "required": [],
    }


# ---------------------------------------------------------------------------
# run_tool: the model sees errors rather than the process dying
# ---------------------------------------------------------------------------


def test_an_unknown_tool_is_reported_not_raised():
    got = cyclebot.run_tool("no_such_tool", {})
    assert "Unknown tool" in got
    assert "search_all" in got, "tells the model what it can use instead"


def test_a_failing_tool_is_reported_not_raised(monkeypatch):
    monkeypatch.setitem(
        cyclebot.TOOLS, "boom", MagicMock(side_effect=RuntimeError("notion down"))
    )
    got = cyclebot.run_tool("boom", {})
    assert "notion down" in got


# ---------------------------------------------------------------------------
# answer(): the conversation loop
# ---------------------------------------------------------------------------


def test_a_plain_answer_skips_the_thinking_block():
    api = _client(_response(_thinking(), _text("Three meetings since May.")))
    got = cyclebot.answer([{"role": "user", "content": "how many?"}], client=api)
    assert got == "Three meetings since May."


def test_a_tool_call_is_run_and_fed_back(monkeypatch):
    def fake_projects(status: str = "all") -> str:
        """Projects, for the test."""
        return "## Projects\n- Brixton"

    monkeypatch.setitem(cyclebot.TOOLS, "get_projects", fake_projects)
    api = _client(
        _response(_tool_use("get_projects", status="active"), stop_reason="tool_use"),
        _response(_text("One active project: Brixton.")),
    )

    got = cyclebot.answer([{"role": "user", "content": "what's active?"}], client=api)

    assert got == "One active project: Brixton."
    second_call = api.messages.create.call_args_list[1].kwargs["messages"]
    result = second_call[-1]["content"][0]
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "tu_1"
    assert "Brixton" in result["content"]


def test_the_caller_s_history_is_not_mutated():
    history = [{"role": "user", "content": "hello"}]
    api = _client(
        _response(_tool_use("list_databases"), stop_reason="tool_use"),
        _response(_text("done")),
    )
    cyclebot.answer(history, client=api)
    assert history == [{"role": "user", "content": "hello"}]


def test_the_loop_stops_at_max_turns():
    """A model that only ever asks for tools must not bill indefinitely."""
    forever = [
        _response(_tool_use("list_databases"), stop_reason="tool_use")
        for _ in range(10)
    ]
    api = _client(*forever)

    got = cyclebot.answer([{"role": "user", "content": "x"}], client=api, max_turns=3)

    assert api.messages.create.call_count == 3
    assert "couldn't finish" in got


def test_the_surface_is_appended_to_the_shared_system_prompt():
    api = _client(_response(_text("hi")))
    cyclebot.answer(
        [{"role": "user", "content": "x"}], client=api, surface="You are on WhatsApp."
    )
    system = api.messages.create.call_args.kwargs["system"]
    assert system.startswith(cyclebot.SYSTEM), "shared behaviour comes first"
    assert system.endswith("You are on WhatsApp.")


def test_no_sampling_parameters_are_sent():
    """temperature/top_p/top_k are rejected by Sonnet 5 — see core.claude."""
    api = _client(_response(_text("hi")))
    cyclebot.answer([{"role": "user", "content": "x"}], client=api)
    sent = api.messages.create.call_args.kwargs
    assert not {"temperature", "top_p", "top_k"} & set(sent)
    assert sent["output_config"] == {"effort": "medium"}


# ---------------------------------------------------------------------------
# The injected Notion client
# ---------------------------------------------------------------------------


def test_an_injected_client_is_used_instead_of_the_environment(monkeypatch):
    """The portal loads its token with pydantic-settings, never into os.environ."""
    monkeypatch.setattr(cyclebot, "_notion_client", None)
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)

    fake = MagicMock()
    fake.data_sources.query.return_value = {"results": []}
    cyclebot.use_notion_client(fake)

    assert cyclebot.get_projects() == "No projects found."
    fake.data_sources.query.assert_called_once()


def test_without_a_client_or_a_token_the_failure_is_explicit(monkeypatch):
    monkeypatch.setattr(cyclebot, "_notion_client", None)
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    with pytest.raises(KeyError, match="NOTION_API_TOKEN"):
        cyclebot._notion()


# ---------------------------------------------------------------------------
# Registering a tool
# ---------------------------------------------------------------------------


def test_a_tool_without_a_type_hint_is_refused_at_registration():
    """Better here than as a KeyError halfway through a conversation."""
    def untyped(thing) -> str:
        """Does something."""
        return "x"

    with pytest.raises(TypeError, match="type hint"):
        cyclebot.tool(untyped)


def test_a_tool_without_a_docstring_is_refused_at_registration():
    def undocumented(query: str) -> str:
        return "x"

    with pytest.raises(TypeError, match="docstring"):
        cyclebot.tool(undocumented)


def test_a_refused_tool_is_not_left_registered():
    def untyped(thing) -> str:
        """Does something."""
        return "x"

    before = set(cyclebot.TOOLS)
    with pytest.raises(TypeError):
        cyclebot.tool(untyped)
    assert set(cyclebot.TOOLS) == before
