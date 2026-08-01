import asyncio
import json
import os
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from mcp.server import MCPServer

from gdm_flow.mcp.common import _get_system_path_arg
from gdm_flow.mcp.server import create_server
from gdm_flow.mcp.tools import knowledge, solvers

# ---------------------------------------------------------------------------
# Register tools on a shared MCPServer instance
# ---------------------------------------------------------------------------

_mcp = MCPServer("gdm-flow-test")
solvers.register(_mcp)
knowledge.register(_mcp)


def _call(name: str, **kwargs) -> dict:
    """Call a registered tool function directly and parse its JSON result."""
    fn = _mcp._tool_manager._tools[name].fn
    return json.loads(fn(**kwargs))


def test_mcp_list_resources():
    server = create_server()
    resources = asyncio.run(server.list_resources())
    assert len(resources) == 2

    by_uri = {str(resource.uri): resource for resource in resources}
    assert set(by_uri) == {"gdm-flow://solvers", "gdm-flow://workflows"}
    assert by_uri["gdm-flow://solvers"].name == "Available Solvers"
    assert by_uri["gdm-flow://workflows"].name == "Canonical Workflows"


def test_mcp_read_resources():
    server = create_server()
    for uri in ("gdm-flow://solvers", "gdm-flow://workflows"):
        contents = asyncio.run(server.read_resource(uri))
        assert len(contents) == 1
        data = json.loads(contents[0].content)
        assert isinstance(data, list) and len(data) > 0


def test_mcp_list_prompts():
    server = create_server()
    prompts = asyncio.run(server.list_prompts())
    assert len(prompts) == 3

    names = {prompt.name for prompt in prompts}
    assert names == {
        "run_ac_pf_workflow",
        "run_qsts_workflow",
        "run_opf_workflow",
    }
    for prompt in prompts:
        assert prompt.arguments is not None
        assert [arg.name for arg in prompt.arguments] == ["system_path"]
        assert all(arg.required for arg in prompt.arguments)


def test_mcp_get_prompts():
    server = create_server()
    for name in (
        "run_ac_pf_workflow",
        "run_qsts_workflow",
        "run_opf_workflow",
    ):
        result = asyncio.run(
            server.get_prompt(name, {"system_path": "/tmp/system.json"})
        )
        assert len(result.messages) == 1
        message = result.messages[0]
        assert message.role == "user"
        text = message.content.text
        assert "system_path" in text or "system path" in text
        assert len(text) > 50


def test_mcp_list_tools_includes_documentation_tools():
    server = create_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "calculate_ybus" in tool_names
    assert "run_ac_opf" in tool_names
    assert "list_documentation" in tool_names
    assert "search_documentation" in tool_names
    assert "get_documentation_page" in tool_names
    assert "list_api_symbols" in tool_names
    assert "get_api_reference" in tool_names

    # Newly added time-series / solver tools
    assert "run_ac_pf" in tool_names
    assert "run_qsts" in tool_names
    assert "run_multiperiod" in tool_names
    assert "plot_ts" in tool_names


def test_mcp_documentation_tools_smoke():
    listing = _call("list_documentation")
    assert listing["count"] > 0
    assert "intro.md" in listing["files"]

    search = _call("search_documentation", query="AC OPF", max_results=3)
    assert search["count"] >= 1

    page = _call(
        "get_documentation_page",
        doc_path="intro.md",
        start_line=1,
        max_lines=20,
    )
    assert page["path"] == "intro.md"
    assert "GDM-Flow" in page["content"]


def test_mcp_api_reference_tools_smoke():
    symbol_listing = _call("list_api_symbols")
    assert symbol_listing["count"] > 0
    assert "calculate_ybus" in symbol_listing["symbols"]

    api_ref = _call("get_api_reference", symbol_name="calculate_ybus")
    assert api_ref["symbol"] == "calculate_ybus"
    assert api_ref["module"].startswith("gdm_flow")
    assert api_ref["signature"] is not None


def test_get_system_path_arg_accepts_direct_model_ref_path():
    path = _get_system_path_arg(model_ref={"path": "/tmp/model.json"})
    assert path == "/tmp/model.json"


def test_get_system_path_arg_resolves_registry_model_ref(tmp_path):
    db_path = tmp_path / "registry.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE models (
                model_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                stored_path TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO models (model_id, version, stored_path) VALUES (?, ?, ?)",
            ("opf123", 2, "/tmp/opf_v2.json"),
        )

    os.environ["DIST_STACK_MODEL_REGISTRY_DB"] = str(db_path)
    try:
        path = _get_system_path_arg(
            model_ref={"model_id": "opf123", "version": 2}
        )
    finally:
        os.environ.pop("DIST_STACK_MODEL_REGISTRY_DB", None)

    assert path == "/tmp/opf_v2.json"


def test_get_system_path_arg_resolves_library_registered_model(tmp_path):
    from dist_stack.registry import register

    model_path = tmp_path / "registered_v1.json"
    model_path.write_text('{"name": "registered-model"}', encoding="utf-8")

    db_path = tmp_path / "registry.sqlite"
    record = register(
        model_id="lib123",
        version=1,
        stored_path=model_path,
        registry_db=db_path,
    )

    os.environ["DIST_STACK_MODEL_REGISTRY_DB"] = str(db_path)
    try:
        path = _get_system_path_arg(
            model_ref={"model_id": "lib123", "version": 1}
        )
    finally:
        os.environ.pop("DIST_STACK_MODEL_REGISTRY_DB", None)

    assert record.version == 1
    assert path == str(model_path)


def test_mcp_run_ac_pf(tmp_path, system):
    system_path = tmp_path / "system.json"
    system.to_json(str(system_path))

    result = _call(
        "run_ac_pf",
        system_path=str(system_path),
        max_iterations=100,
        tolerance=1e-6,
    )

    assert result["success"] is True
    assert result["iterations"] > 0
    assert result["max_mismatch_pu"] < 1e-4
    assert len(result["voltage_pu"]) > 0
    for v in result["voltage_pu"]:
        assert v["magnitude_pu"] > 0.0
        assert isinstance(v["angle_rad"], float)
    assert len(result["power_injection"]) == len(result["voltage_pu"])
    for p in result["power_injection"]:
        assert "real_w" in p
        assert "imag_var" in p


def test_mcp_run_qsts(tmp_path, system):
    system_path = tmp_path / "system.json"
    system.to_json(str(system_path))

    result = _call(
        "run_qsts",
        system_path=str(system_path),
        solver="ldf",
        timestep_start=0,
        timestep_end=2,
    )

    assert result["solver"] == "ldf"
    assert result["num_timesteps"] == 3
    assert result["num_converged"] == 3
    assert result["resolution_seconds"] == 900
    assert result["initial_timestamp"] is not None
    assert "battery_soc_traces" in result


def test_mcp_run_multiperiod(tmp_path, system):
    system_path = tmp_path / "system.json"
    system.to_json(str(system_path))

    result = _call(
        "run_multiperiod",
        system_path=str(system_path),
        timestep_start=0,
        timestep_end=2,
    )

    assert result["success"] is True
    assert result["solver"] == "dc"
    assert result["num_timesteps"] == 3
    assert isinstance(result["objective"], float)
    assert len(result["generator_dispatch_w"]) == 3
    for dispatch in result["generator_dispatch_w"].values():
        assert len(dispatch) > 0
        for name, value in dispatch.items():
            assert isinstance(name, str)
            assert isinstance(value, float)


def test_mcp_plot_ts(tmp_path, system):
    system_path = tmp_path / "system.json"
    system.to_json(str(system_path))
    db_path = tmp_path / "qsts.db"

    qsts = _call(
        "run_qsts",
        system_path=str(system_path),
        solver="ldf",
        timestep_start=0,
        timestep_end=2,
        db_path=str(db_path),
    )
    assert qsts["db_path"] == str(db_path)
    assert qsts["run_id"] is not None

    result = _call(
        "plot_ts",
        db_path=str(db_path),
        run_id=qsts["run_id"],
    )
    assert result["message"]
    assert Path(result["output_path"]).exists()
