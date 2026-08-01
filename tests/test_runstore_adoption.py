"""Runstore adoption tests (doc 11 §1.5, gdm-flow row).

All runstore + manifest writes are additive/best-effort: when
``DIST_STACK_RUNSTORE_DB`` is unset, export behavior must be byte-identical
to before the runstore was adopted (no raise, no extra side effects beyond the
pre-existing manifest sidecar).
"""

import os

import numpy as np
import pytest

from gdm_flow import (
    PowerFlowOptimizationResult,
    YBusResult,
    export_ac_opf_result_to_sqlite,
)


def _make_ac_result() -> PowerFlowOptimizationResult:
    labels = [("bus_1", "A"), ("bus_2", "A")]
    ybus = YBusResult(
        ybus=np.array([[1 + 0j, -1 + 0j], [-1 + 0j, 1 + 0j]], dtype=np.complex128),
        index_to_label=labels,
        label_to_index={label: i for i, label in enumerate(labels)},
    )
    return PowerFlowOptimizationResult(
        success=True,
        message="ok",
        ybus_result=ybus,
        voltage=np.array([400 + 0j, 398 - 1j], dtype=np.complex128),
        power_injection=np.array([1000 + 50j, -1000 - 50j], dtype=np.complex128),
        iterations=5,
        initial_objective=10.0,
        final_objective=1.0,
    )


# (a) runstore row is written with correct tool/run_type/implementation/model fields
def test_runstore_adoption_row_written(tmp_path, monkeypatch):
    from dist_stack import get_run

    db_path = tmp_path / "results.sqlite"
    runstore_db = tmp_path / "runstore.db"
    monkeypatch.setenv("DIST_STACK_RUNSTORE_DB", str(runstore_db))

    run_id = export_ac_opf_result_to_sqlite(
        _make_ac_result(),
        str(db_path),
        model_id="model-123",
        model_version=3,
        model_hash="hash-abc",
    )

    record = get_run(run_id)
    assert record.tool == "export_ac_opf_result_to_sqlite"
    assert record.run_type == "gdm_flow_run"
    assert record.implementation == "ac"
    assert record.status == "succeeded"
    assert record.message == "ok"
    assert record.model_id == "model-123"
    assert record.model_version == 3
    assert record.model_hash == "hash-abc"
    assert record.payload == {"solver": "AC OPF"}


# (b) env UNSET → the same call succeeds and raises nothing
def test_runstore_adoption_env_unset_no_raise(tmp_path, monkeypatch):
    monkeypatch.delenv("DIST_STACK_RUNSTORE_DB", raising=False)
    assert os.getenv("DIST_STACK_RUNSTORE_DB") is None

    db_path = tmp_path / "results.sqlite"
    run_id = export_ac_opf_result_to_sqlite(_make_ac_result(), str(db_path))

    assert run_id.startswith("ac_")
    # The local SQLite DB is still written exactly as before.
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT implementation, message FROM runs").fetchall()
        assert ("ac_opf", "ok") in rows
    finally:
        conn.close()


# (c) manifest sidecar carries model_id when provided
def test_runstore_adoption_manifest_carries_model_id(tmp_path, monkeypatch):
    from dist_stack.manifest import read_manifest

    # Keep runstore env unset so this only exercises the manifest path.
    monkeypatch.delenv("DIST_STACK_RUNSTORE_DB", raising=False)

    db_path = tmp_path / "results.sqlite"
    export_ac_opf_result_to_sqlite(
        _make_ac_result(),
        str(db_path),
        model_id="model-456",
        model_version=2,
        model_hash="hash-def",
    )

    manifest = read_manifest(str(db_path))
    assert manifest.model_id == "model-456"
    assert manifest.model_version == 2
    assert manifest.model_hash == "hash-def"
    assert manifest.config["solver"] == "AC OPF"


# _resolve_provenance: all-None for None / path-only / unknown / unset registry
def test_resolve_provenance_defaults():
    from gdm_flow.mcp.common import _resolve_provenance

    none_prov = {"model_id": None, "model_version": None, "model_hash": None}
    assert _resolve_provenance(None) == none_prov
    assert _resolve_provenance({}) == none_prov
    assert _resolve_provenance({"path": "/tmp/some/system.json"}) == none_prov
    assert _resolve_provenance({"model_id": "does-not-exist"}) == none_prov


# _resolve_provenance: real registry lookup fills version/hash
def test_resolve_provenance_lookup(tmp_path, monkeypatch):
    from dist_stack.registry import register

    from gdm_flow.mcp.common import _resolve_provenance

    reg_db = tmp_path / "registry.db"
    model_id = "test-model"
    model_path = tmp_path / "system.json"
    model_path.write_text("{}", encoding="utf-8")
    register(
        model_id,
        version=1,
        stored_path=str(model_path),
        model_hash="hash-1",
        registry_db=str(reg_db),
    )
    register(
        model_id,
        version=2,
        stored_path=str(model_path),
        model_hash="hash-2",
        registry_db=str(reg_db),
    )

    # model_ref carries its own registry_db override — no env needed.
    prov = _resolve_provenance({"model_id": model_id, "registry_db": str(reg_db)})
    assert prov == {
        "model_id": model_id,
        "model_version": 2,
        "model_hash": "hash-2",
    }

    prov = _resolve_provenance(
        {"model_id": model_id, "version": 1, "registry_db": str(reg_db)}
    )
    assert prov == {
        "model_id": model_id,
        "model_version": 1,
        "model_hash": "hash-1",
    }

    # Env-var fallback path.
    monkeypatch.setenv("DIST_STACK_MODEL_REGISTRY_DB", str(reg_db))
    prov = _resolve_provenance({"model_id": model_id})
    assert prov == {
        "model_id": model_id,
        "model_version": 2,
        "model_hash": "hash-2",
    }
