"""Static resources — expose solver and workflow catalogs via MCP resource URIs."""

from __future__ import annotations

import json

from mcp.server import MCPServer

# Available solver types (static catalog).
_SOLVER_TYPES: list[str] = [
    "ac_opf",
    "dc_opf",
    "lindistflow",
    "ac_pf",
    "qsts",
    "multiperiod",
]

# Workflow prompt catalog (mirrors the prompts registered in prompts/workflows.py).
_WORKFLOW_PROMPTS: list[dict[str, str]] = [
    {
        "name": "run_ac_pf_workflow",
        "description": "Load a system, run AC power flow, and export results",
    },
    {
        "name": "run_qsts_workflow",
        "description": "Load a system, run QSTS simulation, and plot time series",
    },
    {
        "name": "run_opf_workflow",
        "description": "Load a system, run OPF analysis, and compare solvers",
    },
]


def register(mcp: MCPServer) -> None:
    """Register static solver and workflow resources."""

    @mcp.resource(
        "gdm-flow://solvers",
        name="Available Solvers",
        description="All registered solver types",
        mime_type="application/json",
    )
    def list_solvers() -> str:
        """List all registered GDM-Flow solver types."""
        return json.dumps(_SOLVER_TYPES, indent=2)

    @mcp.resource(
        "gdm-flow://workflows",
        name="Canonical Workflows",
        description="Pre-defined workflow prompts for common tasks",
        mime_type="application/json",
    )
    def list_workflows() -> str:
        """List the canonical GDM-Flow workflow prompts."""
        return json.dumps(_WORKFLOW_PROMPTS, indent=2)
