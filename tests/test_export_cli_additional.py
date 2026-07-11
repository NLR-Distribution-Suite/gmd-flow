from __future__ import annotations

import json

import pytest

from gdm_flow import export_cli


def test_parse_helpers_accept_list_and_dict_forms():
    assert export_cli._parse_label(["b1", "A"]) == ("b1", "A")
    assert export_cli._parse_label({"bus": "b2", "phase": "B"}) == ("b2", "B")

    cvals = export_cli._parse_complex_list(
        [
            {"real": 1.0, "imag": -2.0},
            [3.0, 4.0],
        ]
    )
    assert complex(cvals[0]) == complex(1.0, -2.0)
    assert complex(cvals[1]) == complex(3.0, 4.0)

    s1 = export_cli._parse_bus_phase_series({"b1|A": 10.0})
    s2 = export_cli._parse_bus_phase_series(
        [
            {"bus": "b2", "phase": "B", "value": 5.0},
        ]
    )
    assert s1[("b1", "A")] == 10.0
    assert s2[("b2", "B")] == 5.0


def test_parse_helpers_raise_for_invalid_payloads():
    with pytest.raises(ValueError):
        export_cli._parse_label("bad")

    with pytest.raises(ValueError):
        export_cli._parse_complex_list([{"real": 1.0}])

    with pytest.raises(ValueError):
        export_cli._parse_bus_phase_series({"bad_key": 1.0})

    with pytest.raises(TypeError):
        export_cli._parse_bus_phase_series([{"bus": "b", "phase": "A"}])

    with pytest.raises(ValueError):
        export_cli._parse_bus_phase_series([["b", "A"]])

    with pytest.raises(ValueError):
        export_cli._parse_bus_phase_series(123)


def test_loaders_parse_minimal_json_payloads(tmp_path):
    ac = tmp_path / "ac.json"
    dc = tmp_path / "dc.json"
    ldf = tmp_path / "ldf.json"

    ac.write_text(
        json.dumps(
            {
                "success": True,
                "message": "ok",
                "iterations": 1,
                "initial_objective": 1.0,
                "final_objective": 0.1,
                "index_to_label": [["b1", "A"]],
                "voltage": [{"real": 1.0, "imag": 0.0}],
                "power_injection": [{"real": 1.0, "imag": 0.0}],
            }
        )
    )
    dc.write_text(
        json.dumps(
            {
                "success": True,
                "message": "ok",
                "objective": 2.0,
                "iterations": 2,
                "slack_injection_w": 3.0,
                "generator_dispatch_w": {"g": 1.0},
                "theta_rad": {"b1|A": 0.0},
                "nodal_balance_w": {"b1|A": 0.0},
            }
        )
    )
    ldf.write_text(
        json.dumps(
            {
                "success": True,
                "message": "ok",
                "source_bus": "b1",
                "voltage_v": {"b1|A": 1.0},
                "p_flow_w": {"line|A": 1.0},
                "q_flow_var": {"line|A": 0.0},
                "p_net_w": {"b1|A": 1.0},
                "q_net_var": {"b1|A": 0.0},
            }
        )
    )

    assert export_cli._load_ac_result(ac).success is True
    assert export_cli._load_dc_result(dc).success is True
    assert export_cli._load_lindistflow_result(ldf).success is True


def test_main_argument_errors_and_partial_export(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        export_cli.main(["--ac-json", str(tmp_path / "missing.json")])

    # Has result input but missing --db should error.
    ac_existing = tmp_path / "ac-existing.json"
    ac_existing.write_text("{}")
    with pytest.raises(SystemExit):
        export_cli.main(["--ac-json", str(ac_existing)])

    ac = tmp_path / "ac.json"
    ac.write_text(
        json.dumps(
            {
                "success": True,
                "message": "ok",
                "iterations": 1,
                "initial_objective": 1.0,
                "final_objective": 0.1,
                "index_to_label": [["b1", "A"]],
                "voltage": [{"real": 1.0, "imag": 0.0}],
                "power_injection": [{"real": 1.0, "imag": 0.0}],
            }
        )
    )

    captured = {}

    def _fake_export(
        db,
        ac_result=None,
        dc_result=None,
        lindistflow_result=None,
        ac_voltage_limits_v=None,
        lindistflow_voltage_limits_v=None,
        lindistflow_loading_limits_va=None,
    ):
        captured["db"] = db
        captured["ac"] = ac_result is not None
        captured["dc"] = dc_result is not None
        captured["ldf"] = lindistflow_result is not None
        return {"ac": 1}

    monkeypatch.setattr(export_cli, "export_all_results_to_sqlite", _fake_export)
    rc = export_cli.main(["--db", str(tmp_path / "x.sqlite"), "--ac-json", str(ac)])

    assert rc == 0
    assert captured == {
        "db": str(tmp_path / "x.sqlite"),
        "ac": True,
        "dc": False,
        "ldf": False,
    }
