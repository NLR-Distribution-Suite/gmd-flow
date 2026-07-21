import json
import sqlite3
from pathlib import Path

from gdm_flow.export_cli import main


def test_export_cli_writes_all_runs(tmp_path):
    db_path = tmp_path / "cli_results.sqlite"

    ac_json = tmp_path / "ac.json"
    dc_json = tmp_path / "dc.json"
    ldf_json = tmp_path / "ldf.json"

    ac_json.write_text(
        json.dumps(
            {
                "success": True,
                "message": "ok",
                "iterations": 3,
                "initial_objective": 10.0,
                "final_objective": 1.0,
                "index_to_label": [["bus_1", "A"], ["bus_2", "A"]],
                "voltage": [
                    {"real": 400.0, "imag": 0.0},
                    {"real": 398.0, "imag": -1.0},
                ],
                "power_injection": [
                    {"real": 1000.0, "imag": 50.0},
                    {"real": -1000.0, "imag": -50.0},
                ],
            }
        )
    )

    dc_json.write_text(
        json.dumps(
            {
                "success": True,
                "message": "ok",
                "objective": 5.0,
                "iterations": 4,
                "slack_injection_w": 100.0,
                "generator_dispatch_w": {"gen_1": 1000.0},
                "theta_rad": {"bus_1|A": 0.0, "bus_2|A": -0.01},
                "nodal_balance_w": {"bus_1|A": 0.0, "bus_2|A": 0.0},
            }
        )
    )

    ldf_json.write_text(
        json.dumps(
            {
                "success": True,
                "message": "ok",
                "source_bus": "bus_1",
                "voltage_v": {"bus_1|A": 400.0, "bus_2|A": 398.0},
                "p_flow_w": {"line_1|A": 1000.0},
                "q_flow_var": {"line_1|A": 200.0},
                "p_net_w": {"bus_2|A": 1000.0},
                "q_net_var": {"bus_2|A": 200.0},
            }
        )
    )

    rc = main(
        [
            "--db",
            str(db_path),
            "--ac-json",
            str(ac_json),
            "--dc-json",
            str(dc_json),
            "--lindistflow-json",
            str(ldf_json),
        ]
    )
    assert rc == 0

    conn = sqlite3.connect(str(db_path))
    try:
        n_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert n_runs == 3
    finally:
        conn.close()


def test_export_cli_writes_templates_only(tmp_path):
    templates_dir = tmp_path / "templates"

    rc = main(["--write-templates", str(templates_dir)])
    assert rc == 0

    expected = {
        "ac_result.template.json",
        "dc_result.template.json",
        "lindistflow_result.template.json",
    }
    created = {p.name for p in templates_dir.iterdir() if p.is_file()}
    assert expected.issubset(created)

    ac_payload = json.loads(Path(templates_dir / "ac_result.template.json").read_text())
    assert "index_to_label" in ac_payload
    assert "voltage" in ac_payload
