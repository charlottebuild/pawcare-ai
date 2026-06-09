from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pawcare import mcp_tools


class MCPToolPermission(str, Enum):
    read_only = "read_only"
    preview_only = "preview_only"
    write_disabled = "write_disabled"


@dataclass(frozen=True)
class MCPToolDefinition:
    name: str
    description: str
    permission: MCPToolPermission
    handler: Callable[..., dict[str, object]]
    returns_mutation: bool = False
    exposes_internal_state: bool = False


class PawCareMCPToolRegistry:
    """Controlled allowlist for PawCare MCP sidecar tools."""

    def __init__(self, tools: list[MCPToolDefinition] | None = None) -> None:
        self._tools: dict[str, MCPToolDefinition] = {}
        for tool in tools or default_mcp_tools():
            self.register(tool)

    @property
    def tools(self) -> list[MCPToolDefinition]:
        return list(self._tools.values())

    def get(self, name: str) -> MCPToolDefinition:
        return self._tools[name]

    def register(self, tool: MCPToolDefinition) -> None:
        self._validate_tool(tool)
        if tool.name in self._tools:
            raise ValueError(f"MCP tool {tool.name!r} is already registered.")
        self._tools[tool.name] = tool

    def register_all(self, mcp_app: Any) -> None:
        for tool in self.tools:
            decorated = mcp_app.tool(name=tool.name, description=tool.description)
            decorated(tool.handler)

    def _validate_tool(self, tool: MCPToolDefinition) -> None:
        if not tool.name.strip():
            raise ValueError("MCP tool name must not be blank.")
        if not tool.description.strip():
            raise ValueError(f"MCP tool {tool.name!r} must include a description.")
        if tool.returns_mutation:
            raise ValueError(
                f"MCP tool {tool.name!r} cannot be registered because it returns mutation output."
            )
        if tool.exposes_internal_state:
            raise ValueError(
                f"MCP tool {tool.name!r} cannot expose internal agent or safety state."
            )


def default_mcp_tools() -> list[MCPToolDefinition]:
    return [
        MCPToolDefinition(
            name="screen_abnormal_signals",
            description="Screen messy user wording for known abnormal pet care signals.",
            permission=MCPToolPermission.read_only,
            handler=mcp_tools.screen_abnormal_signals,
        ),
        MCPToolDefinition(
            name="search_care_context",
            description="Return non-diagnostic professional references and similar cases.",
            permission=MCPToolPermission.read_only,
            handler=mcp_tools.search_care_context,
        ),
        MCPToolDefinition(
            name="preview_pet_response",
            description="Preview PawCare's safe user-facing response without writing pet data.",
            permission=MCPToolPermission.preview_only,
            handler=mcp_tools.preview_pet_response,
        ),
        MCPToolDefinition(
            name="run_golden_eval",
            description="Run the local Golden Dataset and return a lightweight summary.",
            permission=MCPToolPermission.read_only,
            handler=mcp_tools.run_golden_eval,
        ),
    ]
