from __future__ import annotations

import pytest

from pawcare.mcp_registry import (
    MCPToolDefinition,
    MCPToolPermission,
    PawCareMCPToolRegistry,
)


def _handler() -> dict[str, object]:
    return {"ok": True}


def test_mcp_registry_contains_default_controlled_tools() -> None:
    registry = PawCareMCPToolRegistry()
    tools = {tool.name: tool for tool in registry.tools}

    assert set(tools) == {
        "screen_abnormal_signals",
        "search_care_context",
        "preview_pet_response",
        "run_golden_eval",
    }
    for tool in tools.values():
        assert tool.description
        assert callable(tool.handler)
        assert tool.permission in {
            MCPToolPermission.read_only,
            MCPToolPermission.preview_only,
        }
        assert tool.returns_mutation is False
        assert tool.exposes_internal_state is False
    assert tools["preview_pet_response"].permission == MCPToolPermission.preview_only


def test_mcp_registry_rejects_mutating_or_internal_state_tools() -> None:
    with pytest.raises(ValueError, match="returns mutation"):
        PawCareMCPToolRegistry(
            [
                MCPToolDefinition(
                    name="append_observations",
                    description="Unsafe write tool.",
                    permission=MCPToolPermission.write_disabled,
                    handler=_handler,
                    returns_mutation=True,
                )
            ]
        )

    with pytest.raises(ValueError, match="internal agent or safety state"):
        PawCareMCPToolRegistry(
            [
                MCPToolDefinition(
                    name="debug_agent_outputs",
                    description="Unsafe internal state tool.",
                    permission=MCPToolPermission.read_only,
                    handler=_handler,
                    exposes_internal_state=True,
                )
            ]
        )


def test_mcp_registry_registers_tools_on_mcp_app() -> None:
    class FakeMCP:
        def __init__(self) -> None:
            self.tools: dict[str, object] = {}

        def tool(self, **kwargs):
            name = kwargs["name"]

            def decorator(func):
                self.tools[name] = func
                return func

            return decorator

    fake_mcp = FakeMCP()
    PawCareMCPToolRegistry().register_all(fake_mcp)

    assert set(fake_mcp.tools) == {
        "screen_abnormal_signals",
        "search_care_context",
        "preview_pet_response",
        "run_golden_eval",
    }
