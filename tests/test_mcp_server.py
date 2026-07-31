import asyncio
import os
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from gdm_flow.mcp import server as mcp_server


def test_mcp_list_tools_includes_documentation_tools():
    tools = asyncio.run(mcp_server.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "opf_calculate_ybus" in tool_names
    assert "opf_run_ac" in tool_names
    assert "list_opf_documentation" in tool_names
    assert "search_opf_documentation" in tool_names
    assert "get_opf_documentation_page" in tool_names
    assert "list_opf_api_symbols" in tool_names
    assert "get_opf_api_reference" in tool_names

    # Newly added time-series / solver tools
    assert "opf_run_ac_pf" in tool_names
    assert "opf_run_qsts" in tool_names
    assert "opf_run_multiperiod" in tool_names
    assert "opf_plot_ts" in tool_names


def test_mcp_documentation_tools_smoke():
    listing = asyncio.run(mcp_server._handle_list_opf_documentation({}))
    assert listing["count"] > 0
    assert "intro.md" in listing["files"]

    search = asyncio.run(
        mcp_server._handle_search_opf_documentation(
            {
                "query": "AC OPF",
                "max_results": 3,
            }
        )
    )
    assert search["count"] >= 1

    page = asyncio.run(
        mcp_server._handle_get_opf_documentation_page(
            {
                "doc_path": "intro.md",
                "start_line": 1,
                "max_lines": 20,
            }
        )
    )
    assert page["path"] == "intro.md"
    assert "GDM-Flow" in page["content"]


def test_mcp_api_reference_tools_smoke():
    symbol_listing = asyncio.run(mcp_server._handle_list_opf_api_symbols({}))
    assert symbol_listing["count"] > 0
    assert "calculate_ybus" in symbol_listing["symbols"]

    api_ref = asyncio.run(
        mcp_server._handle_get_opf_api_reference(
            {
                "symbol_name": "calculate_ybus",
            }
        )
    )
    assert api_ref["symbol"] == "calculate_ybus"
    assert api_ref["module"].startswith("gdm_flow")
    assert api_ref["signature"] is not None


def test_get_system_path_arg_accepts_direct_model_ref_path():
    path = mcp_server._get_system_path_arg({"model_ref": {"path": "/tmp/model.json"}})
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
        path = mcp_server._get_system_path_arg(
            {"model_ref": {"model_id": "opf123", "version": 2}}
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
        path = mcp_server._get_system_path_arg(
            {"model_ref": {"model_id": "lib123", "version": 1}}
        )
    finally:
        os.environ.pop("DIST_STACK_MODEL_REGISTRY_DB", None)

    assert record.version == 1
    assert path == str(model_path)


def test_mcp_run_ac_pf(tmp_path, system):
    system_path = tmp_path / "system.json"
    system.to_json(str(system_path))

    result = asyncio.run(
        mcp_server._handle_run_ac_pf(
            {
                "system_path": str(system_path),
                "max_iterations": 100,
                "tolerance": 1e-6,
            }
        )
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

    result = asyncio.run(
        mcp_server._handle_run_qsts(
            {
                "system_path": str(system_path),
                "solver": "ldf",
                "timestep_start": 0,
                "timestep_end": 2,
            }
        )
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

    result = asyncio.run(
        mcp_server._handle_run_multiperiod(
            {
                "system_path": str(system_path),
                "timestep_start": 0,
                "timestep_end": 2,
            }
        )
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

    qsts = asyncio.run(
        mcp_server._handle_run_qsts(
            {
                "system_path": str(system_path),
                "solver": "ldf",
                "timestep_start": 0,
                "timestep_end": 2,
                "db_path": str(db_path),
            }
        )
    )
    assert qsts["db_path"] == str(db_path)
    assert qsts["run_id"] is not None

    result = asyncio.run(
        mcp_server._handle_plot_ts(
            {
                "db_path": str(db_path),
                "run_id": qsts["run_id"],
            }
        )
    )
    assert result["message"]
    assert Path(result["output_path"]).exists()
