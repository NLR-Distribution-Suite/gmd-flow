"""Additional MCP server tests covering handler functions and serialization."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytest.importorskip("mcp")

from gdm_flow.mcp import server as mcp_server


MODEL_PATH = Path("examples/models/p5r.json")


@pytest.fixture()
def model_path():
    if not MODEL_PATH.exists():
        pytest.skip("p5r.json model not found")
    return str(MODEL_PATH)


class TestHelperFunctions:
    def test_extract_snippet_found(self):
        text = "This is a test document about power flow analysis."
        snippet = mcp_server._extract_snippet(text, "power flow")
        assert "power flow" in snippet

    def test_extract_snippet_not_found(self):
        text = "This document has nothing relevant."
        snippet = mcp_server._extract_snippet(text, "xyz_nonexistent")
        assert snippet == ""

    def test_extract_snippet_with_ellipsis(self):
        text = "A" * 200 + "TARGET" + "B" * 200
        snippet = mcp_server._extract_snippet(text, "TARGET", radius=50)
        assert snippet.startswith("... ")
        assert snippet.endswith(" ...")

    def test_list_public_api_symbols(self):
        symbols = mcp_server._list_public_api_symbols()
        assert isinstance(symbols, list)
        assert "calculate_ybus" in symbols

    def test_api_reference_for_symbol(self):
        ref = mcp_server._api_reference_for_symbol("calculate_ybus")
        assert ref["symbol"] == "calculate_ybus"
        assert ref["module"].startswith("gdm_flow")
        assert ref["signature"] is not None

    def test_api_reference_for_unknown_symbol(self):
        with pytest.raises(ValueError, match="Unknown public API symbol"):
            mcp_server._api_reference_for_symbol("nonexistent_symbol_xyz")

    def test_serialize_complex(self):
        result = mcp_server._serialize_complex(3 + 4j)
        assert result == {"real": 3.0, "imag": 4.0}

    def test_get_system_path_arg_from_system_path(self):
        path = mcp_server._get_system_path_arg({"system_path": "/data/test.json"})
        assert path == "/data/test.json"

    def test_get_system_path_arg_missing_raises(self):
        with pytest.raises(ValueError, match="Expected either"):
            mcp_server._get_system_path_arg({})

    def test_get_system_path_arg_model_ref_with_path(self):
        path = mcp_server._get_system_path_arg(
            {"model_ref": {"stored_path": "/data/stored.json"}}
        )
        assert path == "/data/stored.json"

    def test_resolve_model_ref_no_model_id(self):
        with pytest.raises(ValueError, match="must include a path or model_id"):
            mcp_server._resolve_model_ref_to_path({})

    def test_resolve_model_ref_no_registry_db(self):
        os.environ.pop("DIST_STACK_MODEL_REGISTRY_DB", None)
        with pytest.raises(ValueError, match="DIST_STACK_MODEL_REGISTRY_DB"):
            mcp_server._resolve_model_ref_to_path({"model_id": "test123"})

    def test_resolve_model_ref_not_found_in_db(self, tmp_path):
        db_path = tmp_path / "registry.sqlite"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE models (model_id TEXT, version INTEGER, stored_path TEXT)"
            )
        os.environ["DIST_STACK_MODEL_REGISTRY_DB"] = str(db_path)
        try:
            with pytest.raises(ValueError, match="model_ref not found"):
                mcp_server._resolve_model_ref_to_path(
                    {"model_id": "nonexistent", "version": 1}
                )
        finally:
            os.environ.pop("DIST_STACK_MODEL_REGISTRY_DB", None)

    def test_resolve_model_ref_latest_version(self, tmp_path):
        db_path = tmp_path / "registry.sqlite"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE models (model_id TEXT, version INTEGER, stored_path TEXT)"
            )
            conn.execute(
                "INSERT INTO models VALUES (?, ?, ?)", ("m1", 1, "/v1.json")
            )
            conn.execute(
                "INSERT INTO models VALUES (?, ?, ?)", ("m1", 2, "/v2.json")
            )
        os.environ["DIST_STACK_MODEL_REGISTRY_DB"] = str(db_path)
        try:
            path = mcp_server._resolve_model_ref_to_path({"model_id": "m1"})
            assert path == "/v2.json"
        finally:
            os.environ.pop("DIST_STACK_MODEL_REGISTRY_DB", None)


class TestSourceBusTotals:
    def test_empty_labels(self):
        result = mcp_server._source_bus_totals([], np.array([]))
        assert result == {"source_bus": "", "p_w": 0.0, "q_var": 0.0}

    def test_single_source_bus(self):
        labels = [("bus1", "A"), ("bus1", "B"), ("bus2", "A")]
        s_inj = np.array([100 + 50j, 200 + 75j, 300 + 100j])
        result = mcp_server._source_bus_totals(labels, s_inj)
        assert result["source_bus"] == "bus1"
        assert result["p_w"] == 300.0
        assert result["q_var"] == 125.0


class TestSerializationFunctions:
    def test_serialize_ybus_result_without_matrix(self):
        mock_result = MagicMock()
        mock_result.ybus = np.array([[1 + 0j, -0.5j], [-0.5j, 1 + 0j]])
        mock_result.index_to_label = [("bus1", "A"), ("bus2", "A")]
        payload = mcp_server._serialize_ybus_result(
            mock_result, include_matrix=False, matrix_preview_limit=10
        )
        assert payload["n_nodes"] == 2
        assert "matrix_preview" not in payload

    def test_serialize_ybus_result_with_matrix(self):
        mock_result = MagicMock()
        mock_result.ybus = np.array([[1 + 0j, -0.5j], [-0.5j, 1 + 0j]])
        mock_result.index_to_label = [("bus1", "A"), ("bus2", "A")]
        payload = mcp_server._serialize_ybus_result(
            mock_result, include_matrix=True, matrix_preview_limit=2
        )
        assert "matrix_preview" in payload
        assert payload["matrix_preview"]["rows"] == 2

    def test_serialize_dc_result_without_details(self):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.message = "ok"
        mock_result.objective = 100.0
        mock_result.iterations = 5
        mock_result.slack_injection_w = 50.0
        mock_result.generator_dispatch_w = {"gen1": 30.0, "gen2": 20.0}
        payload = mcp_server._serialize_dc_result(mock_result, include_details=False)
        assert payload["success"] is True
        assert payload["total_dispatch_w"] == 50.0
        assert "generator_dispatch_w" not in payload

    def test_serialize_dc_result_with_details(self):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.message = "ok"
        mock_result.objective = 100.0
        mock_result.iterations = 5
        mock_result.slack_injection_w = 50.0
        mock_result.generator_dispatch_w = {"gen1": 30.0}
        mock_result.theta_rad = {("bus1", "A"): 0.01}
        mock_result.nodal_balance_w = {("bus1", "A"): 10.0}
        payload = mcp_server._serialize_dc_result(mock_result, include_details=True)
        assert "generator_dispatch_w" in payload
        assert "theta_rad" in payload

    def test_serialize_lindistflow_result_without_details(self):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.message = "converged"
        mock_result.source_bus = "source"
        mock_result.voltage_v = {("bus1", "A"): 120.0, ("bus2", "B"): 119.5}
        mock_result.p_flow_w = {("br1", "A"): 1000.0}
        mock_result.q_flow_var = {("br1", "A"): 200.0}
        payload = mcp_server._serialize_lindistflow_result(
            mock_result, include_details=False
        )
        assert payload["success"] is True
        assert payload["modeled_nodes"] == 2
        assert "voltage_v" not in payload

    def test_serialize_lindistflow_result_with_details(self):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.message = "converged"
        mock_result.source_bus = "source"
        mock_result.voltage_v = {("bus1", "A"): 120.0}
        mock_result.p_flow_w = {("br1", "A"): 1000.0}
        mock_result.q_flow_var = {("br1", "A"): 200.0}
        payload = mcp_server._serialize_lindistflow_result(
            mock_result, include_details=True
        )
        assert "voltage_v" in payload
        assert "p_flow_w" in payload

    def test_serialize_ac_result_without_details(self):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.message = "converged"
        mock_result.iterations = 10
        mock_result.initial_objective = 1.0
        mock_result.final_objective = 0.5
        mock_result.voltage = np.array([120 + 0j, 119 - 1j])
        mock_result.power_injection = np.array([1000 + 200j, -500 - 100j])
        mock_result.ybus_result = MagicMock()
        mock_result.ybus_result.index_to_label = [("bus1", "A"), ("bus2", "A")]
        payload = mcp_server._serialize_ac_result(mock_result, include_details=False)
        assert payload["success"] is True
        assert "nodes" not in payload

    def test_serialize_ac_result_with_details(self):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.message = "converged"
        mock_result.iterations = 10
        mock_result.initial_objective = 1.0
        mock_result.final_objective = 0.5
        mock_result.voltage = np.array([120 + 0j])
        mock_result.power_injection = np.array([1000 + 200j])
        mock_result.ybus_result = MagicMock()
        mock_result.ybus_result.index_to_label = [("bus1", "A")]
        payload = mcp_server._serialize_ac_result(mock_result, include_details=True)
        assert "nodes" in payload
        assert len(payload["nodes"]) == 1


class TestMCPToolHandlers:
    def test_handle_calculate_ybus(self, model_path):
        result = asyncio.run(
            mcp_server._handle_calculate_ybus({"system_path": model_path})
        )
        assert result["n_nodes"] > 0

    def test_handle_run_lindistflow(self, model_path):
        result = asyncio.run(
            mcp_server._handle_run_lindistflow({"system_path": model_path})
        )
        assert result["success"] is True

    def test_handle_run_dc(self, model_path):
        result = asyncio.run(
            mcp_server._handle_run_dc({"system_path": model_path})
        )
        assert result["success"] is True

    def test_handle_run_ac(self, model_path):
        result = asyncio.run(
            mcp_server._handle_run_ac({"system_path": model_path})
        )
        assert result["success"] is True

    def test_handle_compare_solvers(self, model_path):
        result = asyncio.run(
            mcp_server._handle_compare_solvers({"system_path": model_path})
        )
        assert "summary" in result
        assert result["summary"]["lindistflow_success"] is True

    def test_handle_export_sqlite(self, model_path, tmp_path):
        db_file = str(tmp_path / "test_export.db")
        result = asyncio.run(
            mcp_server._handle_export_sqlite(
                {"system_path": model_path, "db_path": db_file}
            )
        )
        assert result["db_path"] == db_file
        assert Path(db_file).exists()

    def test_handle_export_sqlite_none_selected_raises(self, model_path, tmp_path):
        db_file = str(tmp_path / "test.db")
        with pytest.raises(ValueError, match="At least one"):
            asyncio.run(
                mcp_server._handle_export_sqlite(
                    {
                        "system_path": model_path,
                        "db_path": db_file,
                        "run_ac": False,
                        "run_dc": False,
                        "run_lindistflow": False,
                    }
                )
            )

    def test_handle_scale_loads(self, model_path, tmp_path):
        output = str(tmp_path / "scaled.json")
        result = asyncio.run(
            mcp_server._handle_scale_loads(
                {
                    "system_path": model_path,
                    "load_scale": 1.5,
                    "output_path": output,
                }
            )
        )
        assert result["success"] is True
        assert result["load_scale"] == 1.5
        assert result["total_load_kw_after"] > result["total_load_kw_before"]

    def test_handle_fix_violations(self, model_path):
        result = asyncio.run(
            mcp_server._handle_fix_violations({"system_path": model_path})
        )
        assert result["success"] is True

    def test_handle_list_opf_api_symbols(self):
        result = asyncio.run(mcp_server._handle_list_opf_api_symbols({}))
        assert result["count"] > 0

    def test_handle_get_opf_api_reference(self):
        result = asyncio.run(
            mcp_server._handle_get_opf_api_reference(
                {"symbol_name": "calculate_ybus"}
            )
        )
        assert result["symbol"] == "calculate_ybus"

    def test_handle_get_doc_page_path_traversal_blocked(self):
        with pytest.raises(ValueError, match="must stay within"):
            asyncio.run(
                mcp_server._handle_get_opf_documentation_page(
                    {"doc_path": "../../etc/passwd"}
                )
            )

    def test_handle_get_doc_page_not_found(self):
        with pytest.raises(FileNotFoundError):
            asyncio.run(
                mcp_server._handle_get_opf_documentation_page(
                    {"doc_path": "nonexistent_file.md"}
                )
            )

    def test_call_tool_unknown(self):
        result = asyncio.run(mcp_server.call_tool("unknown_tool", {}))
        text = json.loads(result[0].text)
        assert "error" in text

    def test_call_tool_valid(self):
        result = asyncio.run(mcp_server.call_tool("list_opf_api_symbols", {}))
        text = json.loads(result[0].text)
        assert "count" in text

    def test_load_system_not_found(self):
        with pytest.raises(FileNotFoundError):
            mcp_server._load_system("/nonexistent/path.json")


class TestIterDocFiles:
    def test_returns_list(self):
        files = mcp_server._iter_doc_files()
        assert isinstance(files, list)
        # Should find files if docs/ exists
        if mcp_server.DOCS_ROOT.exists():
            assert len(files) > 0
