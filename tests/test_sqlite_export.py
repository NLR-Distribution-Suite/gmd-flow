import sqlite3

import numpy as np
import pytest

from gdm_flow import (
    DCOPFResult,
    LinDistFlowResult,
    PowerFlowOptimizationResult,
    YBusResult,
    export_ac_opf_result_to_sqlite,
    export_all_results_to_sqlite,
    export_dc_opf_result_to_sqlite,
    export_lindistflow_result_to_sqlite,
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


def _make_dc_result() -> DCOPFResult:
    labels = [("bus_1", "A"), ("bus_2", "A")]
    ybus = YBusResult(
        ybus=np.array([[1 + 0j, -1 + 0j], [-1 + 0j, 1 + 0j]], dtype=np.complex128),
        index_to_label=labels,
        label_to_index={label: i for i, label in enumerate(labels)},
    )
    return DCOPFResult(
        success=True,
        message="ok",
        objective=123.0,
        iterations=7,
        generator_dispatch_w={"gen_a": 1500.0},
        theta_rad={("bus_1", "A"): 0.0, ("bus_2", "A"): -0.01},
        nodal_balance_w={("bus_1", "A"): 0.0, ("bus_2", "A"): 0.0},
        slack_injection_w=500.0,
        ybus_result=ybus,
    )


def _make_lindistflow_result() -> LinDistFlowResult:
    return LinDistFlowResult(
        success=True,
        message="ok",
        source_bus="bus_1",
        voltage_v={("bus_1", "A"): 400.0, ("bus_2", "A"): 398.0},
        p_flow_w={("line_1", "A"): 1000.0},
        q_flow_var={("line_1", "A"): 200.0},
        p_net_w={("bus_2", "A"): 1000.0},
        q_net_var={("bus_2", "A"): 200.0},
    )


def test_export_individual_results_to_sqlite(tmp_path):
    db_path = tmp_path / "results.sqlite"

    ac_id = export_ac_opf_result_to_sqlite(_make_ac_result(), str(db_path))
    dc_id = export_dc_opf_result_to_sqlite(_make_dc_result(), str(db_path))
    ldf_id = export_lindistflow_result_to_sqlite(
        _make_lindistflow_result(), str(db_path)
    )

    conn = sqlite3.connect(str(db_path))
    try:
        runs = conn.execute("SELECT implementation, run_id FROM runs").fetchall()
        impls = {row[0] for row in runs}
        assert impls == {"ac_opf", "dc_opf", "lindistflow"}
        assert {ac_id, dc_id, ldf_id}.issubset({row[1] for row in runs})

        ac_nodes = conn.execute(
            "SELECT COUNT(*) FROM ac_opf_nodes WHERE run_id = ?", (ac_id,)
        ).fetchone()[0]
        dc_nodes = conn.execute(
            "SELECT COUNT(*) FROM dc_opf_nodes WHERE run_id = ?", (dc_id,)
        ).fetchone()[0]
        ldf_nodes = conn.execute(
            "SELECT COUNT(*) FROM lindistflow_nodes WHERE run_id = ?", (ldf_id,)
        ).fetchone()[0]

        assert ac_nodes == 2
        assert dc_nodes == 2
        assert ldf_nodes >= 2
    finally:
        conn.close()


def test_export_all_results_to_sqlite(tmp_path):
    db_path = tmp_path / "results_all.sqlite"

    run_ids = export_all_results_to_sqlite(
        str(db_path),
        ac_result=_make_ac_result(),
        dc_result=_make_dc_result(),
        lindistflow_result=_make_lindistflow_result(),
    )

    assert set(run_ids) == {"ac_opf", "dc_opf", "lindistflow"}

    conn = sqlite3.connect(str(db_path))
    try:
        n_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert n_runs == 3
        n_losses = conn.execute("SELECT COUNT(*) FROM losses").fetchone()[0]
        assert n_losses == 3
    finally:
        conn.close()


def test_export_all_results_writes_limit_columns(tmp_path):
    db_path = tmp_path / "results_limits.sqlite"

    run_ids = export_all_results_to_sqlite(
        str(db_path),
        ac_result=_make_ac_result(),
        dc_result=_make_dc_result(),
        lindistflow_result=_make_lindistflow_result(),
        ac_voltage_limits_v={("bus_1", "A"): (395.0, 405.0)},
        ac_branch_loading_va={("line_1", "A"): 980.0},
        ac_branch_loading_limits_va={("line_1", "A"): 950.0},
        ac_branch_flow_w_var={("line_1", "A"): (900.0, 200.0)},
        dc_branch_loading_va={("line_1", "A"): 970.0},
        dc_branch_loading_limits_va={("line_1", "A"): 950.0},
        dc_branch_flow_w_var={("line_1", "A"): (970.0, 0.0)},
        lindistflow_voltage_limits_v={("bus_2", "A"): (390.0, 410.0)},
        lindistflow_loading_limits_va={("line_1", "A"): 950.0},
    )

    ac_id = run_ids["ac_opf"]
    dc_id = run_ids["dc_opf"]
    ldf_id = run_ids["lindistflow"]

    conn = sqlite3.connect(str(db_path))
    try:
        ac_row = conn.execute(
            """
            SELECT voltage_min_v, voltage_max_v
            FROM ac_opf_nodes
            WHERE run_id = ? AND bus_name = 'bus_1' AND phase = 'A'
            """,
            (ac_id,),
        ).fetchone()
        assert ac_row == (395.0, 405.0)

        ldf_node_row = conn.execute(
            """
            SELECT voltage_min_v, voltage_max_v
            FROM lindistflow_nodes
            WHERE run_id = ? AND bus_name = 'bus_2' AND phase = 'A'
            """,
            (ldf_id,),
        ).fetchone()
        assert ldf_node_row == (390.0, 410.0)

        ldf_branch_row = conn.execute(
            """
            SELECT loading_va, loading_limit_va
            FROM lindistflow_branches
            WHERE run_id = ? AND branch_name = 'line_1' AND phase = 'A'
            """,
            (ldf_id,),
        ).fetchone()
        assert ldf_branch_row is not None
        assert ldf_branch_row[0] == pytest.approx((1000.0**2 + 200.0**2) ** 0.5)
        assert ldf_branch_row[1] == pytest.approx(950.0)

        ac_branch_row = conn.execute(
            """
            SELECT p_flow_w, q_flow_var, loading_va, loading_limit_va
            FROM ac_opf_branches
            WHERE run_id = ? AND branch_name = 'line_1' AND phase = 'A'
            """,
            (ac_id,),
        ).fetchone()
        assert ac_branch_row == (900.0, 200.0, 980.0, 950.0)

        dc_branch_row = conn.execute(
            """
            SELECT p_flow_w, q_flow_var, loading_va, loading_limit_va
            FROM dc_opf_branches
            WHERE run_id = ? AND branch_name = 'line_1' AND phase = 'A'
            """,
            (dc_id,),
        ).fetchone()
        assert dc_branch_row == (970.0, 0.0, 970.0, 950.0)
    finally:
        conn.close()


def test_export_all_results_persists_violation_rows(tmp_path):
    db_path = tmp_path / "results_violations.sqlite"

    run_ids = export_all_results_to_sqlite(
        str(db_path),
        ac_result=_make_ac_result(),
        dc_result=_make_dc_result(),
        lindistflow_result=_make_lindistflow_result(),
        ac_voltage_limits_v={
            ("bus_1", "A"): (395.0, 399.0),
            ("bus_2", "A"): (399.0, 410.0),
        },
        ac_branch_loading_va={("line_1", "A"): 980.0},
        ac_branch_loading_limits_va={("line_1", "A"): 900.0},
        ac_branch_flow_w_var={("line_1", "A"): (850.0, 200.0)},
        dc_branch_loading_va={("line_1", "A"): 970.0},
        dc_branch_loading_limits_va={("line_1", "A"): 900.0},
        dc_branch_flow_w_var={("line_1", "A"): (970.0, 0.0)},
        lindistflow_voltage_limits_v={
            ("bus_2", "A"): (399.0, 410.0),
        },
        lindistflow_loading_limits_va={("line_1", "A"): 900.0},
    )

    ac_id = run_ids["ac_opf"]
    dc_id = run_ids["dc_opf"]
    ldf_id = run_ids["lindistflow"]

    conn = sqlite3.connect(str(db_path))
    try:
        ac_violations = conn.execute(
            """
            SELECT bus_name, phase, violation_kind
            FROM voltage_violations
            WHERE run_id = ? AND implementation = 'ac_opf'
            ORDER BY bus_name, phase
            """,
            (ac_id,),
        ).fetchall()
        assert ac_violations == [
            ("bus_1", "A", "overvoltage"),
            ("bus_2", "A", "undervoltage"),
        ]

        ldf_voltage_violations = conn.execute(
            """
            SELECT bus_name, phase, violation_kind
            FROM voltage_violations
            WHERE run_id = ? AND implementation = 'lindistflow'
            ORDER BY bus_name, phase
            """,
            (ldf_id,),
        ).fetchall()
        assert ldf_voltage_violations == [
            ("bus_2", "A", "undervoltage"),
        ]

        loading_violations = conn.execute(
            """
            SELECT implementation, branch_name, phase, loading_pct
            FROM loading_violations
            WHERE run_id IN (?, ?, ?)
            ORDER BY implementation, branch_name, phase
            """,
            (ac_id, dc_id, ldf_id),
        ).fetchall()
        assert len(loading_violations) == 3
        assert loading_violations[0][0] == "ac_opf"
        assert loading_violations[0][1] == "line_1"
        assert loading_violations[0][2] == "A"
        assert loading_violations[0][3] > 100.0
        assert loading_violations[1][0] == "dc_opf"
        assert loading_violations[1][1] == "line_1"
        assert loading_violations[1][2] == "A"
        assert loading_violations[1][3] > 100.0
        assert loading_violations[2][0] == "lindistflow"
        assert loading_violations[2][1] == "line_1"
        assert loading_violations[2][2] == "A"
        assert loading_violations[2][3] > 100.0
    finally:
        conn.close()


def test_losses_table_contains_expected_methods_and_values(tmp_path):
    db_path = tmp_path / "results_losses.sqlite"

    run_ids = export_all_results_to_sqlite(
        str(db_path),
        ac_result=_make_ac_result(),
        dc_result=_make_dc_result(),
        lindistflow_result=_make_lindistflow_result(),
    )

    conn = sqlite3.connect(str(db_path))
    try:
        ac_row = conn.execute(
            "SELECT p_loss_w, q_loss_var, method FROM losses WHERE run_id = ?",
            (run_ids["ac_opf"],),
        ).fetchone()
        dc_row = conn.execute(
            "SELECT p_loss_w, q_loss_var, method FROM losses WHERE run_id = ?",
            (run_ids["dc_opf"],),
        ).fetchone()
        ldf_row = conn.execute(
            "SELECT p_loss_w, q_loss_var, method FROM losses WHERE run_id = ?",
            (run_ids["lindistflow"],),
        ).fetchone()

        assert ac_row == (0.0, 0.0, "sum_nodal_injections")
        assert dc_row == (0.0, 0.0, "lossless_dc_assumption")
        assert ldf_row == (0.0, 0.0, "lossless_lindistflow_assumption")
    finally:
        conn.close()
