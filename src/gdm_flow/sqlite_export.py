"""SQLite export utilities for AC OPF, AC PF, DC OPF, and LinDistFlow results."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import math
import sqlite3
from typing import Dict, Mapping, Sequence, Tuple
from uuid import uuid4

import numpy as np

from .ac_opf import PowerFlowOptimizationResult
from .ac_pf import ACPowerFlowResult
from .dc_opf import DCOPFResult
from .lindistflow import LinDistFlowResult

BusPhaseLabel = Tuple[str, str]
BranchPhaseLabel = Tuple[str, str]


class RunType(str, Enum):
    """Run kinds used as ``run_id`` prefixes when exporting to SQLite.

    The enum values are the exact string prefixes serialized into the
    ``run_id`` column (``<prefix>_<uuid>``) — do not change them.
    """

    AC_OPF = "ac"
    AC_PF = "pf"
    DC_OPF = "dc"
    LINDISTFLOW = "lindistflow"
    QSTS = "qsts"
    MULTIPERIOD = "mp"


class ViolationKind(str, Enum):
    """Violation kind values persisted in the ``voltage_violations`` table.

    The enum values are the exact strings serialized into the
    ``violation_kind`` column — do not change them.
    """

    OVERVOLTAGE = "overvoltage"
    UNDERVOLTAGE = "undervoltage"
    OVER = "over"
    UNDER = "under"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_run_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            implementation TEXT NOT NULL,
            success INTEGER NOT NULL,
            message TEXT,
            created_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ac_opf_summary (
            run_id TEXT PRIMARY KEY,
            iterations INTEGER NOT NULL,
            initial_objective REAL NOT NULL,
            final_objective REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ac_opf_nodes (
            run_id TEXT NOT NULL,
            bus_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            voltage_mag_v REAL NOT NULL,
            voltage_min_v REAL,
            voltage_max_v REAL,
            voltage_angle_rad REAL NOT NULL,
            p_injection_w REAL NOT NULL,
            q_injection_var REAL NOT NULL,
            PRIMARY KEY (run_id, bus_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ac_opf_branches (
            run_id TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            p_flow_w REAL,
            q_flow_var REAL,
            loading_va REAL,
            loading_limit_va REAL,
            PRIMARY KEY (run_id, branch_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ac_pf_summary (
            run_id TEXT PRIMARY KEY,
            iterations INTEGER NOT NULL,
            max_mismatch_pu REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ac_pf_nodes (
            run_id TEXT NOT NULL,
            bus_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            voltage_mag_v REAL NOT NULL,
            voltage_min_v REAL,
            voltage_max_v REAL,
            voltage_angle_rad REAL NOT NULL,
            p_injection_w REAL NOT NULL,
            q_injection_var REAL NOT NULL,
            PRIMARY KEY (run_id, bus_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ac_pf_branches (
            run_id TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            p_flow_w REAL,
            q_flow_var REAL,
            loading_va REAL,
            loading_limit_va REAL,
            PRIMARY KEY (run_id, branch_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS dc_opf_summary (
            run_id TEXT PRIMARY KEY,
            objective REAL NOT NULL,
            iterations INTEGER NOT NULL,
            slack_injection_w REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS dc_opf_generators (
            run_id TEXT NOT NULL,
            generator_name TEXT NOT NULL,
            dispatch_w REAL NOT NULL,
            PRIMARY KEY (run_id, generator_name),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS dc_opf_nodes (
            run_id TEXT NOT NULL,
            bus_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            theta_rad REAL NOT NULL,
            nodal_balance_w REAL NOT NULL,
            PRIMARY KEY (run_id, bus_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS dc_opf_branches (
            run_id TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            p_flow_w REAL,
            q_flow_var REAL,
            loading_va REAL,
            loading_limit_va REAL,
            PRIMARY KEY (run_id, branch_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lindistflow_summary (
            run_id TEXT PRIMARY KEY,
            source_bus TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lindistflow_nodes (
            run_id TEXT NOT NULL,
            bus_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            voltage_v REAL NOT NULL,
            voltage_min_v REAL,
            voltage_max_v REAL,
            p_net_w REAL NOT NULL,
            q_net_var REAL NOT NULL,
            PRIMARY KEY (run_id, bus_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lindistflow_branches (
            run_id TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            p_flow_w REAL NOT NULL,
            q_flow_var REAL NOT NULL,
            loading_va REAL,
            loading_limit_va REAL,
            PRIMARY KEY (run_id, branch_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS voltage_violations (
            run_id TEXT NOT NULL,
            implementation TEXT NOT NULL,
            bus_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            voltage_v REAL NOT NULL,
            voltage_min_v REAL,
            voltage_max_v REAL,
            violation_v REAL NOT NULL,
            violation_kind TEXT NOT NULL,
            PRIMARY KEY (run_id, implementation, bus_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS loading_violations (
            run_id TEXT NOT NULL,
            implementation TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            p_flow_w REAL NOT NULL,
            q_flow_var REAL NOT NULL,
            loading_va REAL NOT NULL,
            loading_limit_va REAL NOT NULL,
            loading_pct REAL NOT NULL,
            PRIMARY KEY (run_id, implementation, branch_name, phase),
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS losses (
            run_id TEXT PRIMARY KEY,
            implementation TEXT NOT NULL,
            p_loss_w REAL NOT NULL,
            q_loss_var REAL NOT NULL,
            method TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        """
    )

    # Backward-compatible migrations for pre-existing databases.
    _ensure_columns(
        conn,
        "ac_opf_nodes",
        [
            ("voltage_min_v", "REAL"),
            ("voltage_max_v", "REAL"),
        ],
    )
    _ensure_columns(
        conn,
        "lindistflow_nodes",
        [
            ("voltage_min_v", "REAL"),
            ("voltage_max_v", "REAL"),
        ],
    )
    _ensure_columns(
        conn,
        "lindistflow_branches",
        [
            ("loading_va", "REAL"),
            ("loading_limit_va", "REAL"),
        ],
    )


def _ensure_columns(
    conn: sqlite3.Connection,
    table_name: str,
    columns: Sequence[tuple[str, str]],
) -> None:
    existing = {
        row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for col_name, col_type in columns:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")


def export_ac_opf_result_to_sqlite(
    result: PowerFlowOptimizationResult,
    db_path: str,
    *,
    run_id: str | None = None,
    voltage_limits_v: Mapping[BusPhaseLabel, tuple[float, float]] | None = None,
    branch_loading_va: Mapping[BranchPhaseLabel, float] | None = None,
    branch_loading_limits_va: Mapping[BranchPhaseLabel, float] | None = None,
    branch_flow_w_var: Mapping[BranchPhaseLabel, tuple[float, float]] | None = None,
) -> str:
    """Export an AC OPF result into SQLite and return the run_id."""

    run_id = run_id or _make_run_id(RunType.AC_OPF.value)
    conn = _connect(db_path)
    try:
        _create_schema(conn)
        conn.execute(
            "INSERT INTO runs(run_id, implementation, success, message, created_at_utc) VALUES (?, ?, ?, ?, ?)",
            (run_id, "ac_opf", int(result.success), result.message, _utc_now_iso()),
        )
        conn.execute(
            "INSERT INTO ac_opf_summary(run_id, iterations, initial_objective, final_objective) VALUES (?, ?, ?, ?)",
            (
                run_id,
                result.iterations,
                result.initial_objective,
                result.final_objective,
            ),
        )

        rows = []
        for idx, (bus_name, phase) in enumerate(result.ybus_result.index_to_label):
            v = result.voltage[idx]
            s = result.power_injection[idx]
            limits = (voltage_limits_v or {}).get((bus_name, phase))
            v_min = float(limits[0]) if limits is not None else None
            v_max = float(limits[1]) if limits is not None else None
            rows.append(
                (
                    run_id,
                    bus_name,
                    phase,
                    float(abs(v)),
                    v_min,
                    v_max,
                    float(math.atan2(v.imag, v.real)),
                    float(s.real),
                    float(s.imag),
                )
            )

        conn.executemany(
            """
            INSERT INTO ac_opf_nodes(
                run_id, bus_name, phase, voltage_mag_v, voltage_min_v, voltage_max_v,
                voltage_angle_rad, p_injection_w, q_injection_var
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        violation_rows = []
        for row in rows:
            _run_id, bus_name, phase, voltage_v, v_min, v_max, *_ = row
            if v_max is not None and voltage_v > v_max:
                violation_rows.append(
                    (
                        run_id,
                        "ac_opf",
                        bus_name,
                        phase,
                        voltage_v,
                        v_min,
                        v_max,
                        float(voltage_v - v_max),
                        ViolationKind.OVERVOLTAGE.value,
                    )
                )
            elif v_min is not None and voltage_v < v_min:
                violation_rows.append(
                    (
                        run_id,
                        "ac_opf",
                        bus_name,
                        phase,
                        voltage_v,
                        v_min,
                        v_max,
                        float(v_min - voltage_v),
                        ViolationKind.UNDERVOLTAGE.value,
                    )
                )

        if violation_rows:
            conn.executemany(
                """
                INSERT INTO voltage_violations(
                    run_id, implementation, bus_name, phase, voltage_v,
                    voltage_min_v, voltage_max_v, violation_v, violation_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                violation_rows,
            )

        branch_labels = set(branch_loading_va or {}) | set(
            branch_loading_limits_va or {}
        )
        branch_rows = []
        for branch_name, phase in sorted(branch_labels):
            pq = (branch_flow_w_var or {}).get((branch_name, phase))
            p_flow_w = float(pq[0]) if pq is not None else None
            q_flow_var = float(pq[1]) if pq is not None else None
            branch_rows.append(
                (
                    run_id,
                    branch_name,
                    phase,
                    p_flow_w,
                    q_flow_var,
                    (
                        float((branch_loading_va or {})[(branch_name, phase)])
                        if (branch_loading_va or {}).get((branch_name, phase))
                        is not None
                        else None
                    ),
                    (
                        float((branch_loading_limits_va or {})[(branch_name, phase)])
                        if (branch_loading_limits_va or {}).get((branch_name, phase))
                        is not None
                        else None
                    ),
                )
            )

        if branch_rows:
            conn.executemany(
                """
                INSERT INTO ac_opf_branches(
                    run_id, branch_name, phase, p_flow_w, q_flow_var, loading_va, loading_limit_va
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                branch_rows,
            )

            loading_violation_rows = []
            for row in branch_rows:
                (
                    _run_id,
                    branch_name,
                    phase,
                    p_flow_w,
                    q_flow_var,
                    loading_va,
                    loading_limit_va,
                ) = row
                if (
                    loading_va is not None
                    and loading_limit_va is not None
                    and loading_limit_va > 0
                    and loading_va > loading_limit_va
                ):
                    loading_violation_rows.append(
                        (
                            run_id,
                            "ac_opf",
                            branch_name,
                            phase,
                            float(p_flow_w or 0.0),
                            float(q_flow_var or 0.0),
                            float(loading_va),
                            float(loading_limit_va),
                            float(100.0 * loading_va / loading_limit_va),
                        )
                    )

            if loading_violation_rows:
                conn.executemany(
                    """
                    INSERT INTO loading_violations(
                        run_id, implementation, branch_name, phase, p_flow_w, q_flow_var,
                        loading_va, loading_limit_va, loading_pct
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    loading_violation_rows,
                )

        total_p_loss_w = float(np.sum(result.power_injection.real))
        total_q_loss_var = float(np.sum(result.power_injection.imag))
        conn.execute(
            """
            INSERT INTO losses(run_id, implementation, p_loss_w, q_loss_var, method)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "ac_opf",
                total_p_loss_w,
                total_q_loss_var,
                "sum_nodal_injections",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return run_id


def export_ac_pf_result_to_sqlite(
    result: ACPowerFlowResult,
    db_path: str,
    *,
    run_id: str | None = None,
    voltage_limits_v: Mapping[BusPhaseLabel, tuple[float, float]] | None = None,
    branch_loading_va: Mapping[BranchPhaseLabel, float] | None = None,
    branch_loading_limits_va: Mapping[BranchPhaseLabel, float] | None = None,
    branch_flow_w_var: Mapping[BranchPhaseLabel, tuple[float, float]] | None = None,
) -> str:
    """Export an AC PF result into SQLite and return the run_id."""

    run_id = run_id or _make_run_id(RunType.AC_PF.value)
    conn = _connect(db_path)
    try:
        _create_schema(conn)
        conn.execute(
            "INSERT INTO runs(run_id, implementation, success, message, created_at_utc) VALUES (?, ?, ?, ?, ?)",
            (run_id, "ac_pf", int(result.success), result.message, _utc_now_iso()),
        )
        conn.execute(
            "INSERT INTO ac_pf_summary(run_id, iterations, max_mismatch_pu) VALUES (?, ?, ?)",
            (
                run_id,
                result.iterations,
                result.max_mismatch_pu,
            ),
        )

        rows = []
        for idx, (bus_name, phase) in enumerate(result.ybus_result.index_to_label):
            v = result.voltage[idx]
            v_mag = abs(v)
            v_angle = float(np.angle(v))
            s = result.power_injection[idx]
            p_w = float(s.real)
            q_var = float(s.imag)

            v_min = None
            v_max = None
            if voltage_limits_v and (bus_name, phase) in voltage_limits_v:
                v_min, v_max = voltage_limits_v[(bus_name, phase)]

            rows.append(
                (run_id, bus_name, phase, v_mag, v_min, v_max, v_angle, p_w, q_var)
            )

        conn.executemany(
            """
            INSERT INTO ac_pf_nodes(
                run_id, bus_name, phase, voltage_mag_v, voltage_min_v, voltage_max_v,
                voltage_angle_rad, p_injection_w, q_injection_var
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        # Voltage violations
        violation_rows = []
        for run_id_v, bus_name, phase, v_mag, v_min, v_max, *_ in rows:
            if v_min is not None and v_mag < v_min:
                violation_rows.append(
                    (
                        run_id,
                        "ac_pf",
                        bus_name,
                        phase,
                        v_mag,
                        v_min,
                        v_max,
                        v_min - v_mag,
                        ViolationKind.UNDER.value,
                    )
                )
            elif v_max is not None and v_mag > v_max:
                violation_rows.append(
                    (
                        run_id,
                        "ac_pf",
                        bus_name,
                        phase,
                        v_mag,
                        v_min,
                        v_max,
                        v_mag - v_max,
                        ViolationKind.OVER.value,
                    )
                )

        if violation_rows:
            conn.executemany(
                """
                INSERT INTO voltage_violations(
                    run_id, implementation, bus_name, phase,
                    voltage_v, voltage_min_v, voltage_max_v, violation_v, violation_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                violation_rows,
            )

        # Branch loading
        if branch_loading_va:
            branch_rows = []
            for (branch_name, phase), loading in branch_loading_va.items():
                limit = (
                    branch_loading_limits_va.get((branch_name, phase))
                    if branch_loading_limits_va
                    else None
                )
                p_w, q_var = (0.0, 0.0)
                if branch_flow_w_var and (branch_name, phase) in branch_flow_w_var:
                    p_w, q_var = branch_flow_w_var[(branch_name, phase)]
                branch_rows.append(
                    (run_id, branch_name, phase, p_w, q_var, loading, limit)
                )

            conn.executemany(
                """
                INSERT INTO ac_pf_branches(
                    run_id, branch_name, phase, p_flow_w, q_flow_var, loading_va, loading_limit_va
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                branch_rows,
            )

            # Loading violations
            loading_violation_rows = []
            for row in branch_rows:
                (
                    _,
                    branch_name,
                    phase,
                    p_flow_w,
                    q_flow_var,
                    loading_va,
                    loading_limit_va,
                ) = row
                if (
                    loading_va is not None
                    and loading_limit_va is not None
                    and loading_limit_va > 0
                    and loading_va > loading_limit_va
                ):
                    loading_violation_rows.append(
                        (
                            run_id,
                            "ac_pf",
                            branch_name,
                            phase,
                            float(p_flow_w or 0.0),
                            float(q_flow_var or 0.0),
                            float(loading_va),
                            float(loading_limit_va),
                            float(100.0 * loading_va / loading_limit_va),
                        )
                    )

            if loading_violation_rows:
                conn.executemany(
                    """
                    INSERT INTO loading_violations(
                        run_id, implementation, branch_name, phase, p_flow_w, q_flow_var,
                        loading_va, loading_limit_va, loading_pct
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    loading_violation_rows,
                )

        total_p_loss_w = float(np.sum(result.power_injection.real))
        total_q_loss_var = float(np.sum(result.power_injection.imag))
        conn.execute(
            """
            INSERT INTO losses(run_id, implementation, p_loss_w, q_loss_var, method)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "ac_pf",
                total_p_loss_w,
                total_q_loss_var,
                "sum_nodal_injections",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return run_id


def export_dc_opf_result_to_sqlite(
    result: DCOPFResult,
    db_path: str,
    *,
    run_id: str | None = None,
    branch_loading_va: Mapping[BranchPhaseLabel, float] | None = None,
    branch_loading_limits_va: Mapping[BranchPhaseLabel, float] | None = None,
    branch_flow_w_var: Mapping[BranchPhaseLabel, tuple[float, float]] | None = None,
) -> str:
    """Export a DC OPF result into SQLite and return the run_id."""

    run_id = run_id or _make_run_id(RunType.DC_OPF.value)
    conn = _connect(db_path)
    try:
        _create_schema(conn)
        conn.execute(
            "INSERT INTO runs(run_id, implementation, success, message, created_at_utc) VALUES (?, ?, ?, ?, ?)",
            (run_id, "dc_opf", int(result.success), result.message, _utc_now_iso()),
        )
        conn.execute(
            "INSERT INTO dc_opf_summary(run_id, objective, iterations, slack_injection_w) VALUES (?, ?, ?, ?)",
            (run_id, result.objective, result.iterations, result.slack_injection_w),
        )

        gen_rows = [
            (run_id, gen_name, float(dispatch))
            for gen_name, dispatch in result.generator_dispatch_w.items()
        ]
        conn.executemany(
            "INSERT INTO dc_opf_generators(run_id, generator_name, dispatch_w) VALUES (?, ?, ?)",
            gen_rows,
        )

        node_rows = [
            (
                run_id,
                bus_name,
                phase,
                float(theta),
                float(result.nodal_balance_w[(bus_name, phase)]),
            )
            for (bus_name, phase), theta in result.theta_rad.items()
        ]
        conn.executemany(
            "INSERT INTO dc_opf_nodes(run_id, bus_name, phase, theta_rad, nodal_balance_w) VALUES (?, ?, ?, ?, ?)",
            node_rows,
        )

        branch_labels = set(branch_loading_va or {}) | set(
            branch_loading_limits_va or {}
        )
        branch_rows = []
        for branch_name, phase in sorted(branch_labels):
            pq = (branch_flow_w_var or {}).get((branch_name, phase))
            p_flow_w = float(pq[0]) if pq is not None else None
            q_flow_var = float(pq[1]) if pq is not None else None
            branch_rows.append(
                (
                    run_id,
                    branch_name,
                    phase,
                    p_flow_w,
                    q_flow_var,
                    (
                        float((branch_loading_va or {})[(branch_name, phase)])
                        if (branch_loading_va or {}).get((branch_name, phase))
                        is not None
                        else None
                    ),
                    (
                        float((branch_loading_limits_va or {})[(branch_name, phase)])
                        if (branch_loading_limits_va or {}).get((branch_name, phase))
                        is not None
                        else None
                    ),
                )
            )

        if branch_rows:
            conn.executemany(
                """
                INSERT INTO dc_opf_branches(
                    run_id, branch_name, phase, p_flow_w, q_flow_var, loading_va, loading_limit_va
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                branch_rows,
            )

            loading_violation_rows = []
            for row in branch_rows:
                (
                    _run_id,
                    branch_name,
                    phase,
                    p_flow_w,
                    q_flow_var,
                    loading_va,
                    loading_limit_va,
                ) = row
                if (
                    loading_va is not None
                    and loading_limit_va is not None
                    and loading_limit_va > 0
                    and loading_va > loading_limit_va
                ):
                    loading_violation_rows.append(
                        (
                            run_id,
                            "dc_opf",
                            branch_name,
                            phase,
                            float(p_flow_w or 0.0),
                            float(q_flow_var or 0.0),
                            float(loading_va),
                            float(loading_limit_va),
                            float(100.0 * loading_va / loading_limit_va),
                        )
                    )

            if loading_violation_rows:
                conn.executemany(
                    """
                    INSERT INTO loading_violations(
                        run_id, implementation, branch_name, phase, p_flow_w, q_flow_var,
                        loading_va, loading_limit_va, loading_pct
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    loading_violation_rows,
                )

        # Standard DC OPF formulation is lossless.
        conn.execute(
            """
            INSERT INTO losses(run_id, implementation, p_loss_w, q_loss_var, method)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "dc_opf",
                0.0,
                0.0,
                "lossless_dc_assumption",
            ),
        )

        conn.commit()
    finally:
        conn.close()

    return run_id


def export_lindistflow_result_to_sqlite(
    result: LinDistFlowResult,
    db_path: str,
    *,
    run_id: str | None = None,
    voltage_limits_v: Mapping[BusPhaseLabel, tuple[float, float]] | None = None,
    loading_limits_va: Mapping[BranchPhaseLabel, float] | None = None,
) -> str:
    """Export a LinDistFlow result into SQLite and return the run_id."""

    run_id = run_id or _make_run_id(RunType.LINDISTFLOW.value)
    conn = _connect(db_path)
    try:
        _create_schema(conn)
        conn.execute(
            "INSERT INTO runs(run_id, implementation, success, message, created_at_utc) VALUES (?, ?, ?, ?, ?)",
            (
                run_id,
                "lindistflow",
                int(result.success),
                result.message,
                _utc_now_iso(),
            ),
        )
        conn.execute(
            "INSERT INTO lindistflow_summary(run_id, source_bus) VALUES (?, ?)",
            (run_id, result.source_bus),
        )

        node_labels = (
            set(result.voltage_v) | set(result.p_net_w) | set(result.q_net_var)
        )
        node_rows = []
        for bus_name, phase in sorted(node_labels):
            limits = (voltage_limits_v or {}).get((bus_name, phase))
            v_min = float(limits[0]) if limits is not None else None
            v_max = float(limits[1]) if limits is not None else None
            node_rows.append(
                (
                    run_id,
                    bus_name,
                    phase,
                    float(result.voltage_v.get((bus_name, phase), 0.0)),
                    v_min,
                    v_max,
                    float(result.p_net_w.get((bus_name, phase), 0.0)),
                    float(result.q_net_var.get((bus_name, phase), 0.0)),
                )
            )
        conn.executemany(
            """
            INSERT INTO lindistflow_nodes(
                run_id, bus_name, phase, voltage_v, voltage_min_v, voltage_max_v,
                p_net_w, q_net_var
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            node_rows,
        )

        node_violation_rows = []
        for row in node_rows:
            _run_id, bus_name, phase, voltage_v, v_min, v_max, *_ = row
            if v_max is not None and voltage_v > v_max:
                node_violation_rows.append(
                    (
                        run_id,
                        "lindistflow",
                        bus_name,
                        phase,
                        voltage_v,
                        v_min,
                        v_max,
                        float(voltage_v - v_max),
                        ViolationKind.OVERVOLTAGE.value,
                    )
                )
            elif v_min is not None and voltage_v < v_min:
                node_violation_rows.append(
                    (
                        run_id,
                        "lindistflow",
                        bus_name,
                        phase,
                        voltage_v,
                        v_min,
                        v_max,
                        float(v_min - voltage_v),
                        ViolationKind.UNDERVOLTAGE.value,
                    )
                )

        if node_violation_rows:
            conn.executemany(
                """
                INSERT INTO voltage_violations(
                    run_id, implementation, bus_name, phase, voltage_v,
                    voltage_min_v, voltage_max_v, violation_v, violation_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                node_violation_rows,
            )

        branch_labels = set(result.p_flow_w) | set(result.q_flow_var)
        branch_rows = []
        for branch_name, phase in sorted(branch_labels):
            p_flow_w = float(result.p_flow_w.get((branch_name, phase), 0.0))
            q_flow_var = float(result.q_flow_var.get((branch_name, phase), 0.0))
            branch_rows.append(
                (
                    run_id,
                    branch_name,
                    phase,
                    p_flow_w,
                    q_flow_var,
                    float(math.hypot(p_flow_w, q_flow_var)),
                    (
                        float((loading_limits_va or {})[(branch_name, phase)])
                        if (loading_limits_va or {}).get((branch_name, phase))
                        is not None
                        else None
                    ),
                )
            )
        conn.executemany(
            """
            INSERT INTO lindistflow_branches(
                run_id, branch_name, phase, p_flow_w, q_flow_var, loading_va, loading_limit_va
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            branch_rows,
        )

        loading_violation_rows = []
        for row in branch_rows:
            (
                _run_id,
                branch_name,
                phase,
                p_flow_w,
                q_flow_var,
                loading_va,
                loading_limit_va,
            ) = row
            if (
                loading_limit_va is not None
                and loading_limit_va > 0
                and loading_va > loading_limit_va
            ):
                loading_violation_rows.append(
                    (
                        run_id,
                        "lindistflow",
                        branch_name,
                        phase,
                        p_flow_w,
                        q_flow_var,
                        loading_va,
                        loading_limit_va,
                        float(100.0 * loading_va / loading_limit_va),
                    )
                )

        if loading_violation_rows:
            conn.executemany(
                """
                INSERT INTO loading_violations(
                    run_id, implementation, branch_name, phase, p_flow_w, q_flow_var,
                    loading_va, loading_limit_va, loading_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                loading_violation_rows,
            )

        # LinDistFlow here is solved in a linear lossless form.
        conn.execute(
            """
            INSERT INTO losses(run_id, implementation, p_loss_w, q_loss_var, method)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "lindistflow",
                0.0,
                0.0,
                "lossless_lindistflow_assumption",
            ),
        )

        conn.commit()
    finally:
        conn.close()

    return run_id


def export_all_results_to_sqlite(
    db_path: str,
    *,
    ac_result: PowerFlowOptimizationResult | None = None,
    pf_result: ACPowerFlowResult | None = None,
    dc_result: DCOPFResult | None = None,
    lindistflow_result: LinDistFlowResult | None = None,
    ac_voltage_limits_v: Mapping[BusPhaseLabel, tuple[float, float]] | None = None,
    ac_branch_loading_va: Mapping[BranchPhaseLabel, float] | None = None,
    ac_branch_loading_limits_va: Mapping[BranchPhaseLabel, float] | None = None,
    ac_branch_flow_w_var: Mapping[BranchPhaseLabel, tuple[float, float]] | None = None,
    pf_voltage_limits_v: Mapping[BusPhaseLabel, tuple[float, float]] | None = None,
    pf_branch_loading_va: Mapping[BranchPhaseLabel, float] | None = None,
    pf_branch_loading_limits_va: Mapping[BranchPhaseLabel, float] | None = None,
    pf_branch_flow_w_var: Mapping[BranchPhaseLabel, tuple[float, float]] | None = None,
    dc_branch_loading_va: Mapping[BranchPhaseLabel, float] | None = None,
    dc_branch_loading_limits_va: Mapping[BranchPhaseLabel, float] | None = None,
    dc_branch_flow_w_var: Mapping[BranchPhaseLabel, tuple[float, float]] | None = None,
    lindistflow_voltage_limits_v: Mapping[BusPhaseLabel, tuple[float, float]]
    | None = None,
    lindistflow_loading_limits_va: Mapping[BranchPhaseLabel, float] | None = None,
) -> Dict[str, str]:
    """Export any subset of AC OPF/AC PF/DC OPF/LinDistFlow results and return run_ids by key."""

    run_ids: Dict[str, str] = {}
    if ac_result is not None:
        run_ids["ac_opf"] = export_ac_opf_result_to_sqlite(
            ac_result,
            db_path,
            voltage_limits_v=ac_voltage_limits_v,
            branch_loading_va=ac_branch_loading_va,
            branch_loading_limits_va=ac_branch_loading_limits_va,
            branch_flow_w_var=ac_branch_flow_w_var,
        )
    if pf_result is not None:
        run_ids["ac_pf"] = export_ac_pf_result_to_sqlite(
            pf_result,
            db_path,
            voltage_limits_v=pf_voltage_limits_v,
            branch_loading_va=pf_branch_loading_va,
            branch_loading_limits_va=pf_branch_loading_limits_va,
            branch_flow_w_var=pf_branch_flow_w_var,
        )
    if dc_result is not None:
        run_ids["dc_opf"] = export_dc_opf_result_to_sqlite(
            dc_result,
            db_path,
            branch_loading_va=dc_branch_loading_va,
            branch_loading_limits_va=dc_branch_loading_limits_va,
            branch_flow_w_var=dc_branch_flow_w_var,
        )
    if lindistflow_result is not None:
        run_ids["lindistflow"] = export_lindistflow_result_to_sqlite(
            lindistflow_result,
            db_path,
            voltage_limits_v=lindistflow_voltage_limits_v,
            loading_limits_va=lindistflow_loading_limits_va,
        )
    return run_ids
