"""CLI for exporting AC/DC/LinDistFlow JSON results to SQLite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import numpy as np

from .ac_opf import PowerFlowOptimizationResult
from .dc_opf import DCOPFResult
from .lindistflow import LinDistFlowResult
from .sqlite_export import export_all_results_to_sqlite
from .ybus import YBusResult

BusPhaseLabel = Tuple[str, str]


def _template_payloads() -> Dict[str, Dict[str, Any]]:
    ac_template: Dict[str, Any] = {
        "success": True,
        "message": "example",
        "iterations": 0,
        "initial_objective": 0.0,
        "final_objective": 0.0,
        "index_to_label": [["bus_1", "A"], ["bus_2", "A"]],
        "voltage": [{"real": 400.0, "imag": 0.0}, {"real": 398.0, "imag": -1.0}],
        "power_injection": [
            {"real": 1000.0, "imag": 50.0},
            {"real": -1000.0, "imag": -50.0},
        ],
    }
    dc_template: Dict[str, Any] = {
        "success": True,
        "message": "example",
        "objective": 0.0,
        "iterations": 0,
        "slack_injection_w": 0.0,
        "generator_dispatch_w": {"gen_1": 0.0},
        "theta_rad": {"bus_1|A": 0.0, "bus_2|A": -0.01},
        "nodal_balance_w": {"bus_1|A": 0.0, "bus_2|A": 0.0},
    }
    ldf_template: Dict[str, Any] = {
        "success": True,
        "message": "example",
        "source_bus": "bus_1",
        "voltage_v": {"bus_1|A": 400.0, "bus_2|A": 398.0},
        "p_flow_w": {"line_1|A": 1000.0},
        "q_flow_var": {"line_1|A": 200.0},
        "p_net_w": {"bus_2|A": -1000.0},
        "q_net_var": {"bus_2|A": -200.0},
    }
    return {
        "ac_result.template.json": ac_template,
        "dc_result.template.json": dc_template,
        "lindistflow_result.template.json": ldf_template,
    }


def _write_templates(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, payload in _template_payloads().items():
        path = output_dir / name
        path.write_text(json.dumps(payload, indent=2) + "\n")
        written.append(path)
    return written


def _parse_label(item: Any) -> BusPhaseLabel:
    if isinstance(item, (list, tuple)) and len(item) == 2:
        return str(item[0]), str(item[1])
    if isinstance(item, dict) and "bus" in item and "phase" in item:
        return str(item["bus"]), str(item["phase"])
    raise ValueError(f"Invalid bus-phase label: {item}")


def _parse_complex_list(values: Iterable[Any]) -> np.ndarray:
    out = []
    for val in values:
        if isinstance(val, dict) and "real" in val and "imag" in val:
            out.append(complex(float(val["real"]), float(val["imag"])))
        elif isinstance(val, (list, tuple)) and len(val) == 2:
            out.append(complex(float(val[0]), float(val[1])))
        else:
            raise ValueError(f"Invalid complex value representation: {val}")
    return np.array(out, dtype=np.complex128)


def _parse_bus_phase_series(data: Any) -> Dict[BusPhaseLabel, float]:
    if isinstance(data, list):
        out: Dict[BusPhaseLabel, float] = {}
        for row in data:
            label = _parse_label(row)
            value = float(row.get("value")) if isinstance(row, dict) else None
            if value is None:
                raise ValueError(f"Invalid series row: {row}")
            out[label] = value
        return out

    if isinstance(data, dict):
        out: Dict[BusPhaseLabel, float] = {}
        for key, value in data.items():
            if "|" in key:
                bus, phase = key.split("|", 1)
                out[(bus, phase)] = float(value)
            else:
                raise ValueError(
                    "Dictionary series keys must use 'bus|phase' format when list form is not used."
                )
        return out

    raise ValueError("Invalid bus-phase series payload.")


def _load_ac_result(path: Path) -> PowerFlowOptimizationResult:
    data = json.loads(path.read_text())
    labels = [_parse_label(item) for item in data["index_to_label"]]
    n = len(labels)
    ybus = YBusResult(
        ybus=np.zeros((n, n), dtype=np.complex128),
        index_to_label=labels,
        label_to_index={label: i for i, label in enumerate(labels)},
    )
    return PowerFlowOptimizationResult(
        success=bool(data["success"]),
        message=str(data.get("message", "")),
        ybus_result=ybus,
        voltage=_parse_complex_list(data["voltage"]),
        power_injection=_parse_complex_list(data["power_injection"]),
        iterations=int(data["iterations"]),
        initial_objective=float(data["initial_objective"]),
        final_objective=float(data["final_objective"]),
    )


def _load_dc_result(path: Path) -> DCOPFResult:
    data = json.loads(path.read_text())
    theta = _parse_bus_phase_series(data["theta_rad"])
    balance = _parse_bus_phase_series(data["nodal_balance_w"])

    labels = sorted(set(theta) | set(balance))
    n = len(labels)
    ybus = YBusResult(
        ybus=np.zeros((n, n), dtype=np.complex128),
        index_to_label=labels,
        label_to_index={label: i for i, label in enumerate(labels)},
    )

    return DCOPFResult(
        success=bool(data["success"]),
        message=str(data.get("message", "")),
        objective=float(data["objective"]),
        iterations=int(data["iterations"]),
        generator_dispatch_w={
            k: float(v) for k, v in data["generator_dispatch_w"].items()
        },
        theta_rad=theta,
        nodal_balance_w=balance,
        slack_injection_w=float(data["slack_injection_w"]),
        ybus_result=ybus,
    )


def _load_lindistflow_result(path: Path) -> LinDistFlowResult:
    data = json.loads(path.read_text())
    return LinDistFlowResult(
        success=bool(data["success"]),
        message=str(data.get("message", "")),
        source_bus=str(data["source_bus"]),
        voltage_v=_parse_bus_phase_series(data["voltage_v"]),
        p_flow_w=_parse_bus_phase_series(data["p_flow_w"]),
        q_flow_var=_parse_bus_phase_series(data["q_flow_var"]),
        p_net_w=_parse_bus_phase_series(data["p_net_w"]),
        q_net_var=_parse_bus_phase_series(data["q_net_var"]),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export OPF/LinDistFlow JSON results to SQLite"
    )
    parser.add_argument("--db", help="Path to SQLite file to create/update")
    parser.add_argument("--ac-json", help="Path to AC OPF result JSON")
    parser.add_argument("--dc-json", help="Path to DC OPF result JSON")
    parser.add_argument("--lindistflow-json", help="Path to LinDistFlow result JSON")
    parser.add_argument(
        "--write-templates",
        help=(
            "Write AC/DC/LinDistFlow JSON template files into this directory. "
            "Useful for bootstrapping valid input files."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.write_templates:
        written = _write_templates(Path(args.write_templates))
        for path in written:
            print(f"template: {path}")

    has_result_inputs = any([args.ac_json, args.dc_json, args.lindistflow_json])
    if not has_result_inputs:
        if args.write_templates:
            return 0
        parser.error(
            "At least one of --ac-json, --dc-json, or --lindistflow-json is required "
            "unless --write-templates is provided."
        )

    if not args.db:
        parser.error("--db is required when exporting JSON results.")

    ac_result = _load_ac_result(Path(args.ac_json)) if args.ac_json else None
    dc_result = _load_dc_result(Path(args.dc_json)) if args.dc_json else None
    ldf_result = (
        _load_lindistflow_result(Path(args.lindistflow_json))
        if args.lindistflow_json
        else None
    )

    run_ids = export_all_results_to_sqlite(
        args.db,
        ac_result=ac_result,
        dc_result=dc_result,
        lindistflow_result=ldf_result,
    )

    for name, run_id in run_ids.items():
        print(f"{name}: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
