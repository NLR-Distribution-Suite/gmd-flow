"""Coverage tests using ieee-13 model (capacitors) and mocks (batteries, regulators)."""

from __future__ import annotations

from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from gdm.distribution import DistributionSystem


IEEE13_PATH = Path("tests/data/ieee-13/gdm/ieee13_system.json")
P5R_PATH = Path("examples/models/p5r.json")


@pytest.fixture()
def ieee13():
    if not IEEE13_PATH.exists():
        pytest.skip("ieee13 model not found")
    return DistributionSystem.from_json(str(IEEE13_PATH))


@pytest.fixture()
def p5r():
    if not P5R_PATH.exists():
        pytest.skip("p5r model not found")
    return DistributionSystem.from_json(str(P5R_PATH))


# ── time_series.py — capacitor paths ────────────────────────────────────


class TestTimeSeriesCapacitorPaths:
    """Exercise capacitor code in build_nodal_power_specs_at_timestep using ieee-13."""

    def test_build_nodal_specs_includes_capacitor_q(self, ieee13):
        from gdm_flow.time_series import build_nodal_power_specs_at_timestep

        # ieee-13 has no time series, but capacitor injection is static
        p_spec, q_spec = build_nodal_power_specs_at_timestep(
            ieee13, 0, include_capacitor=True
        )
        # Capacitor at bus 675 should inject reactive power
        cap_q = sum(v for (bus, _), v in q_spec.items() if bus == "675")
        assert cap_q > 0  # positive Q injection from capacitor

    def test_build_lindistflow_injections_includes_capacitor(self, ieee13):
        from gdm_flow.time_series import build_lindistflow_injections_at_timestep

        p_net, q_net = build_lindistflow_injections_at_timestep(
            ieee13, 0, include_capacitor=True
        )
        # Capacitor should reduce net Q at bus 675 (negative = injection)
        cap_q = sum(v for (bus, _), v in q_net.items() if bus == "675")
        assert cap_q < 0  # capacitor injects, so net Q is negative


class TestTimeSeriesBatteryPathsMocked:
    """Exercise battery code paths with mocked battery components."""

    def _make_system_with_battery(self):
        """Create a mock system with a fake battery component."""
        from gdm.distribution.components import (
            DistributionBattery,
            DistributionCapacitor,
            DistributionLoad,
            DistributionSolar,
        )
        from gdm.distribution.enums import Phase

        mock_system = MagicMock()

        class FakeBus:
            name = "bus_bat"

        class FakeBattery:
            in_service = True
            bus = FakeBus()
            phases = [Phase.A]
            active_power = MagicMock()
            active_power.to.return_value = MagicMock(magnitude=500.0)
            reactive_power = MagicMock()
            reactive_power.to.return_value = MagicMock(magnitude=100.0)

        def get_components(comp_type):
            if comp_type == DistributionBattery:
                return [FakeBattery()]
            return []

        mock_system.get_components = get_components
        mock_system.has_time_series = lambda comp: False
        return mock_system

    def test_build_nodal_specs_with_battery(self):
        from gdm_flow.time_series import build_nodal_power_specs_at_timestep

        system = self._make_system_with_battery()
        p_spec, q_spec = build_nodal_power_specs_at_timestep(
            system, 0, include_battery=True, include_loads=False,
            include_solar=False, include_capacitor=False,
        )
        assert ("bus_bat", "A") in p_spec
        assert p_spec[("bus_bat", "A")] == 500.0

    def test_build_dc_load_profile_with_battery_negative(self):
        from gdm_flow.time_series import build_dc_load_profile_at_timestep

        system = self._make_system_with_battery()
        demand = build_dc_load_profile_at_timestep(
            system, 0, include_loads=False,
            include_battery_as_negative_load=True,
        )
        assert ("bus_bat", "A") in demand
        assert demand[("bus_bat", "A")] < 0

    def test_build_lindistflow_injections_with_battery(self):
        from gdm_flow.time_series import build_lindistflow_injections_at_timestep

        system = self._make_system_with_battery()
        p_net, q_net = build_lindistflow_injections_at_timestep(
            system, 0, include_battery=True, include_loads=False,
            include_solar=False, include_capacitor=False,
        )
        assert ("bus_bat", "A") in p_net
        assert p_net[("bus_bat", "A")] < 0


class TestTimeSeriesQSTSStreaming:
    """Exercise AC/PF streaming to sqlite in QSTS."""

    def test_stream_ac_result_to_sqlite(self):
        import sqlite3

        from gdm_flow.time_series import _create_ts_schema, _stream_timestep_to_sqlite

        conn = sqlite3.connect(":memory:")
        _create_ts_schema(conn)
        conn.execute(
            "INSERT INTO ts_runs VALUES (?, ?, ?, ?, ?, ?)",
            ("run_ac", "ac", "qsts", 10, 900, None),
        )

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.voltage = np.array([120 + 0j, 119 - 1j])
        mock_result.power_injection = np.array([1000 + 200j, -500 - 100j])
        mock_result.ybus_result = MagicMock()
        mock_result.ybus_result.index_to_label = [("bus1", "A"), ("bus2", "A")]

        nominal = {("bus1", "A"): 120.0, ("bus2", "A"): 120.0}
        _stream_timestep_to_sqlite(conn, "run_ac", 0, "ac", mock_result, nominal)

        rows = conn.execute("SELECT * FROM ts_nodes").fetchall()
        assert len(rows) == 2
        summary = conn.execute("SELECT * FROM ts_summary").fetchone()
        assert summary is not None
        conn.close()


# ── strategies.py — regulator tap with mock ─────────────────────────────


class TestRegulatorTapStrategyMocked:
    """Test AdjustRegulatorTapStrategy.apply() with mocked regulators."""

    def test_apply_undervoltage_adjusts_tap_up(self):
        from gdm.distribution.components.distribution_regulator import (
            DistributionRegulator,
        )
        from gdm.distribution.enums import Phase

        from gdm_flow.fix.detect import VoltageViolation, ViolationReport
        from gdm_flow.fix.strategies import AdjustRegulatorTapStrategy

        mock_system = MagicMock()

        mock_v_setpoint = MagicMock()
        mock_product = MagicMock()
        mock_product.to.return_value = MagicMock(magnitude=120.0)
        mock_v_setpoint.__mul__ = lambda self, other: mock_product

        mock_controller = MagicMock()
        mock_controller.controlled_bus = MagicMock()
        mock_controller.controlled_bus.name = "bus1"
        mock_controller.controlled_phase = Phase.A
        mock_controller.v_setpoint = mock_v_setpoint
        mock_controller.pt_ratio = MagicMock(magnitude=60.0)

        mock_reg = MagicMock()
        mock_reg.in_service = True
        mock_reg.name = "reg1"
        mock_reg.controllers = [mock_controller]

        mock_system.get_components = lambda ct: (
            [mock_reg] if ct == DistributionRegulator else []
        )

        report = ViolationReport(
            success=True,
            solver="ldf",
            voltage_violations=[
                VoltageViolation(
                    bus_name="bus1", phase="A",
                    voltage_v=113.0, nominal_v=120.0,
                    min_v=114.0, max_v=126.0,
                    kind="undervoltage",
                )
            ],
        )

        strategy = AdjustRegulatorTapStrategy()
        actions = strategy.apply(mock_system, report)
        assert len(actions) == 1
        assert "reg1" in actions[0].component_name

    def test_apply_overvoltage_adjusts_tap_down(self):
        from gdm.distribution.components.distribution_regulator import (
            DistributionRegulator,
        )
        from gdm.distribution.enums import Phase

        from gdm_flow.fix.detect import VoltageViolation, ViolationReport
        from gdm_flow.fix.strategies import AdjustRegulatorTapStrategy

        mock_system = MagicMock()

        mock_v_setpoint = MagicMock()
        mock_product = MagicMock()
        mock_product.to.return_value = MagicMock(magnitude=125.0)
        mock_v_setpoint.__mul__ = lambda self, other: mock_product

        mock_controller = MagicMock()
        mock_controller.controlled_bus = MagicMock()
        mock_controller.controlled_bus.name = "bus2"
        mock_controller.controlled_phase = Phase.B
        mock_controller.v_setpoint = mock_v_setpoint
        mock_controller.pt_ratio = MagicMock(magnitude=60.0)

        mock_reg = MagicMock()
        mock_reg.in_service = True
        mock_reg.name = "reg2"
        mock_reg.controllers = [mock_controller]

        mock_system.get_components = lambda ct: (
            [mock_reg] if ct == DistributionRegulator else []
        )

        report = ViolationReport(
            success=True,
            solver="ldf",
            voltage_violations=[
                VoltageViolation(
                    bus_name="bus2", phase="B",
                    voltage_v=128.0, nominal_v=120.0,
                    min_v=114.0, max_v=126.0,
                    kind="overvoltage",
                )
            ],
        )

        strategy = AdjustRegulatorTapStrategy()
        actions = strategy.apply(mock_system, report)
        assert len(actions) == 1
        assert "reg2" in actions[0].component_name


class TestAddCapacitorWithExisting:
    """Test AddCapacitorStrategy with ieee-13 model."""

    def test_apply_at_bus_without_capacitor(self, ieee13):
        from gdm_flow.fix.detect import VoltageViolation, ViolationReport
        from gdm_flow.fix.strategies import AddCapacitorStrategy

        # Use a bus that does NOT have an existing cap (e.g. "632")
        report = ViolationReport(
            success=True,
            solver="ldf",
            voltage_violations=[
                VoltageViolation(
                    bus_name="632", phase="A",
                    voltage_v=110.0, nominal_v=120.0,
                    min_v=114.0, max_v=126.0,
                    kind="undervoltage",
                )
            ],
        )
        strategy = AddCapacitorStrategy(kvar_step=50.0)
        actions = strategy.apply(ieee13, report)
        assert len(actions) == 1
        assert "new_cap_632" in actions[0].component_name

    def test_apply_skips_regulator_controlled_buses(self, ieee13):
        from gdm_flow.fix.detect import VoltageViolation, ViolationReport
        from gdm_flow.fix.strategies import AddCapacitorStrategy

        # Only overvoltage — should not be able to fix
        report = ViolationReport(
            success=True,
            solver="ldf",
            voltage_violations=[
                VoltageViolation(
                    bus_name="632", phase="A",
                    voltage_v=130.0, nominal_v=120.0,
                    min_v=114.0, max_v=126.0,
                    kind="overvoltage",
                )
            ],
        )
        strategy = AddCapacitorStrategy()
        assert not strategy.can_fix(report)


# ── cli.py — multiperiod and fix commands ───────────────────────────────


class TestMultiperiodCommand:
    def test_multiperiod_dc_runs(self, monkeypatch, p5r):
        import gdm_flow.cli as cli
        from io import StringIO
        from rich.console import Console

        monkeypatch.setattr(cli, "console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "err_console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "_load_system", lambda _m: p5r)

        cli.multiperiod(
            model=Path("ignored.json"),
            solver=cli.Solver.dc,
            start=0,
            end=4,
            step=1,
            ramp=None,
            db=None,
        )

    def test_multiperiod_ldf_runs(self, monkeypatch, p5r):
        import gdm_flow.cli as cli
        from io import StringIO
        from rich.console import Console

        monkeypatch.setattr(cli, "console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "err_console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "_load_system", lambda _m: p5r)

        cli.multiperiod(
            model=Path("ignored.json"),
            solver=cli.Solver.ldf,
            start=0,
            end=4,
            step=1,
            ramp=None,
            db=None,
        )

    def test_multiperiod_invalid_solver_raises(self, monkeypatch, p5r):
        import gdm_flow.cli as cli
        from io import StringIO
        from rich.console import Console

        monkeypatch.setattr(cli, "console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "err_console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "_load_system", lambda _m: p5r)

        import typer
        with pytest.raises(typer.Exit):
            cli.multiperiod(
                model=Path("ignored.json"),
                solver=cli.Solver.ac,
                start=0,
                end=4,
                step=1,
                ramp=None,
                db=None,
            )


class TestFixCommand:
    def test_fix_command_runs(self, monkeypatch, p5r):
        import gdm_flow.cli as cli
        from io import StringIO
        from rich.console import Console

        monkeypatch.setattr(cli, "console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "err_console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "_load_system", lambda _m: p5r)

        cli.fix_command(
            model=Path("ignored.json"),
            solver=cli.Solver.ldf,
            max_iter=2,
            vm_min_pu=0.95,
            vm_max_pu=1.05,
            output=None,
        )


class TestComparePerPhaseLoading:
    """Test the per-phase loading table section of compare."""

    def test_compare_with_real_model(self, monkeypatch, p5r):
        import gdm_flow.cli as cli
        from io import StringIO
        from rich.console import Console

        monkeypatch.setattr(cli, "console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "err_console", Console(file=StringIO(), quiet=True))
        monkeypatch.setattr(cli, "_load_system", lambda _m: p5r)
        monkeypatch.setattr(cli, "_export_html", lambda *a, **kw: None)

        cli.compare(model=Path("ignored.json"), output=None)


class TestRunPfCLI:
    """Test _run_pf helper which was uncovered."""

    def test_run_pf_returns_result(self, p5r):
        import gdm_flow.cli as cli

        out = cli._run_pf(p5r)
        assert out["solver"] == "AC PF"
        assert out["success"] is True
        assert out["source_p"] != 0.0
        assert out["v_min"] > 0


class TestACOPFCapacitorAndBatteryPaths:
    """Test ac_opf build_nodal_power_specs with capacitors (ieee-13) and batteries (mock)."""

    def test_build_specs_with_capacitor(self, ieee13):
        from gdm_flow.ac_opf import build_nodal_power_specs_from_components

        p_spec, q_spec = build_nodal_power_specs_from_components(
            ieee13, include_capacitor=True
        )
        # Bus 675 has a 200 kvar capacitor on each phase
        cap_q = sum(v for (bus, _), v in q_spec.items() if bus == "675")
        assert cap_q > 0

    def test_build_specs_with_battery_mock(self):
        from gdm.distribution.components import DistributionBattery
        from gdm.distribution.enums import Phase

        from gdm_flow.ac_opf import build_nodal_power_specs_from_components

        mock_system = MagicMock()

        class FakeBus:
            name = "bat_bus"

        class FakeBattery:
            in_service = True
            bus = FakeBus()
            phases = [Phase.A]
            active_power = MagicMock()
            active_power.to.return_value = MagicMock(magnitude=1000.0)
            reactive_power = MagicMock()
            reactive_power.to.return_value = MagicMock(magnitude=200.0)

        def get_components(comp_type):
            if comp_type == DistributionBattery:
                return [FakeBattery()]
            return []

        mock_system.get_components = get_components
        mock_system.get_source_bus = MagicMock(return_value=MagicMock(name="src"))

        p_spec, q_spec = build_nodal_power_specs_from_components(
            mock_system, include_battery=True, include_loads=False,
            include_solar=False, include_capacitor=False,
        )
        assert ("bat_bus", "A") in p_spec
        assert p_spec[("bat_bus", "A")] == 1000.0
