"""GDM-Flow MCP Server — main application wiring.

Implements the unified ``MCPServer`` + per-module ``register()`` pattern
(see ``docs/architecture-assessment/10-mcp-sdk-unification-plan.md``).
"""

from __future__ import annotations

import logging
from typing import Annotated

import typer
from mcp.server import MCPServer

from gdm_flow.mcp import __version__

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gdm_flow_mcp")


def create_server() -> MCPServer:
    """Create and configure the MCPServer server instance."""
    mcp = MCPServer(
        "gdm-flow-mcp",
        instructions=(
            "GDM-Flow MCP server for power flow and optimal power flow "
            "analysis on grid-data-models distribution systems. Use the tools "
            "to build Y-bus matrices, run AC/DC OPF, LinDistFlow, AC power "
            "flow, quasi-static time series and multi-period optimizations, "
            "export results to SQLite, and query project documentation."
        ),
    )

    # -- Register tool modules -------------------------------------------------
    from gdm_flow.mcp.tools import knowledge, solvers

    solvers.register(mcp)
    knowledge.register(mcp)

    # -- Register resources ----------------------------------------------------
    from gdm_flow.mcp.resources import index as resources_index

    resources_index.register(mcp)

    # -- Register prompts ------------------------------------------------------
    from gdm_flow.mcp.prompts import workflows

    workflows.register(mcp)

    return mcp


def _run_server(
    log_level: Annotated[str, typer.Option(help="Logging level")] = "INFO",
) -> None:
    """Start the GDM-Flow MCP server over stdio."""
    logging.getLogger("gdm_flow_mcp").setLevel(log_level.upper())
    logger.info("Starting GDM-Flow MCP Server v%s", __version__)

    create_server().run(transport="stdio")


def main() -> None:
    typer.run(_run_server)


if __name__ == "__main__":
    main()
