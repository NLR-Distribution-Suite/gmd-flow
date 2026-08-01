"""Shared helpers for the GDM-Flow MCP server.

Holds path/model_ref resolution, result serializers, and documentation
utilities used across the ``tools/``, ``resources/``, and ``prompts/``
subpackages.
"""

from __future__ import annotations

import importlib.resources
import inspect
from pathlib import Path
from typing import Any

import numpy as np
from dist_stack.registry import (
    ModelNotFoundError,
    RegistryUnavailableError,
    lookup,
    resolve_model_ref,
)
from gdm.distribution import DistributionSystem

import gdm_flow as gdm_flow_api

# ---------------------------------------------------------------------------
# Documentation index helpers
# ---------------------------------------------------------------------------


def _resolve_docs_root() -> Path:
    """Resolve the packaged ``gdm_flow`` docs directory.

    Uses :func:`importlib.resources.files` so the docs resolve from the
    installed package (wheel or editable install) instead of a repo-relative
    path. Falls back to the legacy repo-relative ``docs/`` folder when the
    packaged docs are unavailable (e.g. an older install).
    """
    try:
        root = Path(importlib.resources.files("gdm_flow") / "docs")
    except (ModuleNotFoundError, TypeError):  # pragma: no cover
        root = Path(__file__).resolve().parents[3] / "docs"
    if root.is_dir():
        return root
    return Path(__file__).resolve().parents[3] / "docs"


DOCS_ROOT = _resolve_docs_root()
_DOC_SUFFIXES = {".md", ".ipynb"}


def _iter_doc_files() -> list[Path]:
    if not DOCS_ROOT.exists():
        return []
    files: list[Path] = []
    for path in DOCS_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _DOC_SUFFIXES:
            continue
        if "_build" in path.parts:
            continue
        files.append(path)
    return sorted(files)


def _extract_snippet(text: str, query: str, radius: int = 140) -> str:
    haystack = text.lower()
    needle = query.lower()
    idx = haystack.find(needle)
    if idx < 0:
        return ""
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "... " + snippet
    if end < len(text):
        snippet = snippet + " ..."
    return snippet


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _list_public_api_symbols() -> list[str]:
    symbols = getattr(gdm_flow_api, "__all__", [])
    return sorted(str(name) for name in symbols)


def _api_reference_for_symbol(symbol_name: str) -> dict[str, Any]:
    if not hasattr(gdm_flow_api, symbol_name):
        raise ValueError(f"Unknown public API symbol: {symbol_name}")
    symbol = getattr(gdm_flow_api, symbol_name)
    signature = None
    if callable(symbol):
        try:
            signature = str(inspect.signature(symbol))
        except (TypeError, ValueError):
            signature = None
    doc = inspect.getdoc(symbol) or ""
    return {
        "symbol": symbol_name,
        "module": getattr(symbol, "__module__", ""),
        "signature": signature,
        "doc": doc,
    }


# ---------------------------------------------------------------------------
# System loading / model_ref resolution
# ---------------------------------------------------------------------------


def _load_system(system_path: str) -> DistributionSystem:
    path = Path(system_path)
    if not path.exists():
        raise FileNotFoundError(f"System JSON file not found: {system_path}")
    return DistributionSystem.from_json(str(path))


def _resolve_model_ref_to_path(model_ref: dict[str, Any]) -> str:
    """Resolve model_ref payload into a concrete system JSON path.

    Path-carrying refs pass through; model_id/version resolve via the
    dist_stack model registry (DIST_STACK_MODEL_REGISTRY_DB).
    """
    return resolve_model_ref(model_ref)


def _resolve_provenance(model_ref: dict | None) -> dict[str, Any]:
    """Resolve ``{model_id, model_version, model_hash}`` from a model_ref.

    When ``model_ref`` carries a ``model_id``, the version and hash are looked
    up in the dist_stack model registry (``resolve_path=False`` — only the
    metadata is needed). Path-only refs and refs whose ``model_id`` is missing
    from the registry resolve to all-None (honest, not fabricated). Never
    raises; registry unavailability also yields all-None.
    """
    provenance: dict[str, Any] = {
        "model_id": None,
        "model_version": None,
        "model_hash": None,
    }
    if not isinstance(model_ref, dict):
        return provenance
    model_id = model_ref.get("model_id")
    if not isinstance(model_id, str) or not model_id.strip():
        return provenance
    try:
        record = lookup(
            model_id,
            version=model_ref.get("version"),
            registry_db=model_ref.get("registry_db"),
            resolve_path=False,
        )
    except (ModelNotFoundError, RegistryUnavailableError):
        return provenance
    provenance["model_id"] = record.model_id
    provenance["model_version"] = record.version
    provenance["model_hash"] = record.model_hash
    return provenance


def _get_system_path_arg(
    system_path: str | None = None, model_ref: dict[str, Any] | None = None
) -> str:
    """Extract system path from either legacy system_path or model_ref."""
    if isinstance(system_path, str) and system_path.strip():
        return system_path

    if isinstance(model_ref, dict):
        return _resolve_model_ref_to_path(model_ref)

    raise ValueError("Expected either 'system_path' or 'model_ref'")


# ---------------------------------------------------------------------------
# Result serializers
# ---------------------------------------------------------------------------


def _serialize_complex(value: complex) -> dict[str, float]:
    return {"real": float(value.real), "imag": float(value.imag)}


def _serialize_ybus_result(
    result: Any,
    *,
    include_matrix: bool,
    matrix_preview_limit: int,
) -> dict[str, Any]:
    ybus = result.ybus
    is_sparse = hasattr(ybus, "toarray")
    ybus_dense = ybus.toarray() if is_sparse else ybus
    n_nodes = len(result.index_to_label)

    payload: dict[str, Any] = {
        "n_nodes": n_nodes,
        "n_nonzero": int(np.count_nonzero(ybus_dense)),
        "is_sparse": bool(is_sparse),
        "index_to_label": [
            {"bus": str(bus), "phase": str(phase)}
            for bus, phase in result.index_to_label
        ],
    }

    if include_matrix:
        preview_n = max(1, min(int(matrix_preview_limit), n_nodes))
        payload["matrix_preview"] = {
            "rows": preview_n,
            "cols": preview_n,
            "values": [
                [_serialize_complex(v) for v in row[:preview_n]]
                for row in ybus_dense[:preview_n]
            ],
        }

    return payload


def _source_bus_totals(
    labels: list[tuple[str, str]], s_injection: np.ndarray
) -> dict[str, float]:
    if not labels:
        return {"source_bus": "", "p_w": 0.0, "q_var": 0.0}
    source_bus = labels[0][0]
    p = 0.0
    q = 0.0
    for idx, label in enumerate(labels):
        if label[0] == source_bus:
            p += float(s_injection[idx].real)
            q += float(s_injection[idx].imag)
    return {"source_bus": source_bus, "p_w": p, "q_var": q}


def _serialize_ac_result(result: Any, include_details: bool) -> dict[str, Any]:
    voltage_mag = np.abs(result.voltage)
    source_totals = _source_bus_totals(
        result.ybus_result.index_to_label, result.power_injection
    )
    payload: dict[str, Any] = {
        "success": bool(result.success),
        "message": str(result.message),
        "iterations": int(result.iterations),
        "initial_objective": float(result.initial_objective),
        "final_objective": float(result.final_objective),
        "voltage_min_v": float(np.min(voltage_mag)) if voltage_mag.size else 0.0,
        "voltage_max_v": float(np.max(voltage_mag)) if voltage_mag.size else 0.0,
        "source_injection": source_totals,
    }
    if include_details:
        payload["nodes"] = [
            {
                "bus": bus,
                "phase": phase,
                "voltage": _serialize_complex(result.voltage[idx]),
                "power_injection": _serialize_complex(result.power_injection[idx]),
            }
            for idx, (bus, phase) in enumerate(result.ybus_result.index_to_label)
        ]
    return payload


def _serialize_dc_result(result: Any, include_details: bool) -> dict[str, Any]:
    dispatch_total = float(sum(result.generator_dispatch_w.values()))
    payload: dict[str, Any] = {
        "success": bool(result.success),
        "message": str(result.message),
        "objective": float(result.objective),
        "iterations": int(result.iterations),
        "slack_injection_w": float(result.slack_injection_w),
        "total_dispatch_w": dispatch_total,
        "generator_count": len(result.generator_dispatch_w),
    }
    if include_details:
        payload["generator_dispatch_w"] = {
            name: float(value) for name, value in result.generator_dispatch_w.items()
        }
        payload["theta_rad"] = [
            {"bus": bus, "phase": phase, "theta_rad": float(theta)}
            for (bus, phase), theta in sorted(result.theta_rad.items())
        ]
        payload["nodal_balance_w"] = [
            {"bus": bus, "phase": phase, "balance_w": float(balance)}
            for (bus, phase), balance in sorted(result.nodal_balance_w.items())
        ]
    return payload


def _serialize_lindistflow_result(result: Any, include_details: bool) -> dict[str, Any]:
    voltage_values = list(result.voltage_v.values())
    payload: dict[str, Any] = {
        "success": bool(result.success),
        "message": str(result.message),
        "source_bus": str(result.source_bus),
        "voltage_min_v": float(min(voltage_values)) if voltage_values else 0.0,
        "voltage_max_v": float(max(voltage_values)) if voltage_values else 0.0,
        "modeled_nodes": len(result.voltage_v),
        "modeled_branches": len(result.p_flow_w),
    }
    if include_details:
        payload["voltage_v"] = [
            {"bus": bus, "phase": phase, "voltage_v": float(v)}
            for (bus, phase), v in sorted(result.voltage_v.items())
        ]
        payload["p_flow_w"] = [
            {"branch": branch, "phase": phase, "p_flow_w": float(v)}
            for (branch, phase), v in sorted(result.p_flow_w.items())
        ]
        payload["q_flow_var"] = [
            {"branch": branch, "phase": phase, "q_flow_var": float(v)}
            for (branch, phase), v in sorted(result.q_flow_var.items())
        ]
    return payload


def _serialize_ac_pf_result(result: Any) -> dict[str, Any]:
    labels = result.ybus_result.index_to_label
    return {
        "success": bool(result.success),
        "message": str(result.message),
        "iterations": int(result.iterations),
        "max_mismatch_pu": float(result.max_mismatch_pu),
        "voltage_pu": [
            {
                "bus": bus,
                "phase": phase,
                "magnitude_pu": float(np.abs(v_pu)),
                "angle_rad": float(np.angle(v_pu)),
            }
            for (bus, phase), v_pu in zip(labels, result.voltage_pu)
        ],
        "power_injection": [
            {
                "bus": bus,
                "phase": phase,
                "real_w": float(s.real),
                "imag_var": float(s.imag),
            }
            for (bus, phase), s in zip(labels, result.power_injection)
        ],
    }


def _serialize_qsts_summary(result: Any) -> dict[str, Any]:
    return {
        "solver": str(result.solver),
        "num_timesteps": int(result.num_timesteps),
        "num_converged": int(result.num_converged),
        "resolution_seconds": float(result.resolution.total_seconds()),
        "initial_timestamp": (
            str(result.initial_timestamp) if result.initial_timestamp else None
        ),
        "db_path": result.db_path,
        "run_id": result.run_id,
        "battery_soc_traces": [
            {
                "battery_id": name,
                "soc_values": [float(value) for value in values],
            }
            for name, values in result.battery_soc_traces.items()
        ],
    }


def _serialize_multiperiod_result(result: Any) -> dict[str, Any]:
    return {
        "success": bool(result.success),
        "message": str(result.message),
        "solver": str(result.solver),
        "num_timesteps": int(result.num_timesteps),
        "objective": float(result.objective),
        "generator_dispatch_w": {
            str(timestep): {
                name: float(value) for name, value in dispatch.items()
            }
            for timestep, dispatch in result.generator_dispatch_w.items()
        },
        "battery_soc": {
            name: [float(value) for value in values]
            for name, values in result.battery_soc.items()
        },
        "db_path": result.db_path,
        "run_id": result.run_id,
    }
