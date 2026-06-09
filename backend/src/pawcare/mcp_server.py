from __future__ import annotations

from typing import Any

from pawcare.mcp_registry import PawCareMCPToolRegistry
from pawcare.mcp_tools import (
    preview_pet_response,
    run_golden_eval,
    screen_abnormal_signals,
    search_care_context,
)

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover - exercised only when dev dependency is absent.

    class FastMCP:  # type: ignore[no-redef]
        """Small import-time shim so tests stay stable without the optional SDK."""

        def __init__(self, name: str) -> None:
            self.name = name
            self.tools: dict[str, Any] = {}

        def tool(self, fn=None, **kwargs):
            tool_name = kwargs.get("name")

            def decorator(func):
                self.tools[str(tool_name or func.__name__)] = func
                return func

            if fn is not None:
                return decorator(fn)
            return decorator

        def run(self) -> None:
            raise RuntimeError(
                "Install PawCare dev dependencies before running the MCP server: "
                'python -m pip install -e ".[dev]"'
            )


mcp = FastMCP("PawCare MCP")
registry = PawCareMCPToolRegistry()
registry.register_all(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
