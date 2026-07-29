"""Additional CLI tests covering ts-info, qsts, plot, and fix commands."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

import gdm_flow.cli as cli


class _DummyConsole:
    def print(self, *args, **kwargs):
        return None

    def status(self, *args, **kwargs):
        class _Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Ctx()


class _FakeSystem:
    def get_components(self, *args, **kwargs):
        return iter([])

    def get_source_bus(self):
        class _Bus:
            name = "source"
            phases = []

        return _Bus()


class TestTsInfoCommand:
    def test_ts_info_no_time_series(self, monkeypatch):
        monkeypatch.setattr(cli, "console", _DummyConsole())
        monkeypatch.setattr(cli, "_load_system", lambda _m: _FakeSystem())
        monkeypatch.setattr(
            "gdm_flow.time_series.has_time_series_data", lambda _s: False
        )
        cli.ts_info(model=Path("ignored.json"))

    def test_ts_info_with_time_series(self, monkeypatch):
        monkeypatch.setattr(cli, "console", _DummyConsole())
        monkeypatch.setattr(cli, "_load_system", lambda _m: _FakeSystem())
        monkeypatch.setattr(
            "gdm_flow.time_series.has_time_series_data", lambda _s: True
        )
        monkeypatch.setattr(
            "gdm_flow.time_series.get_time_series_length", lambda _s: 1000
        )
        monkeypatch.setattr(
            "gdm_flow.time_series.get_time_series_resolution",
            lambda _s: timedelta(minutes=15),
        )

        from gdm_flow.time_series import TimeSeriesInfo

        ts_info = TimeSeriesInfo(
            component_type="DistributionLoad",
            component_name="load1",
            variable_name="active_power",
            length=1000,
            resolution=timedelta(minutes=15),
            initial_timestamp=None,
            units="watt",
        )
        monkeypatch.setattr(
            "gdm_flow.time_series.list_component_time_series",
            lambda _s: {"DistributionLoad": [ts_info]},
        )
        cli.ts_info(model=Path("ignored.json"))


class TestQSTSCommand:
    def test_qsts_no_time_series_raises_exit(self, monkeypatch):
        monkeypatch.setattr(cli, "console", _DummyConsole())
        monkeypatch.setattr(cli, "err_console", _DummyConsole())
        monkeypatch.setattr(cli, "_load_system", lambda _m: _FakeSystem())
        monkeypatch.setattr(
            "gdm_flow.time_series.has_time_series_data", lambda _s: False
        )
        with pytest.raises(typer.Exit):
            cli.qsts(model=Path("ignored.json"))

    def test_qsts_runs_successfully(self, monkeypatch):
        monkeypatch.setattr(cli, "_load_system", lambda _m: _FakeSystem())
        monkeypatch.setattr(
            "gdm_flow.time_series.has_time_series_data", lambda _s: True
        )
        monkeypatch.setattr(
            "gdm_flow.time_series.get_time_series_length", lambda _s: 100
        )
        monkeypatch.setattr(
            "gdm_flow.time_series.get_time_series_resolution",
            lambda _s: timedelta(minutes=15),
        )

        from gdm_flow.time_series import QSTSSummary

        mock_summary = QSTSSummary(
            solver="ldf",
            num_timesteps=10,
            num_converged=10,
            resolution=timedelta(minutes=15),
            initial_timestamp=None,
            db_path=None,
            run_id=None,
            battery_soc_traces={},
        )
        monkeypatch.setattr(
            "gdm_flow.time_series.run_qsts",
            lambda *a, **kw: mock_summary,
        )

        from io import StringIO
        from rich.console import Console

        monkeypatch.setattr(cli, "console", Console(file=StringIO(), quiet=True))

        cli.qsts(
            model=Path("ignored.json"),
            solver=cli.Solver.ldf,
            start=0,
            end=10,
            step=1,
            db=None,
        )


class TestPlotCommand:
    def test_plot_command_calls_dashboard(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cli, "console", _DummyConsole())
        monkeypatch.setattr(cli, "_load_system", lambda _m: _FakeSystem())

        dashboard_called = {"called": False}

        monkeypatch.setitem(
            cli.SOLVER_MAP,
            cli.Solver.ldf,
            lambda _s: {
                "solver": "LinDistFlow",
                "success": True,
                "source_p": 100.0,
                "source_q": 10.0,
                "elapsed": 0.01,
                "iterations": 0,
                "result": None,
            },
        )

        def _fake_generate_dashboard(system, results, output, model_name=None):
            dashboard_called["called"] = True

        monkeypatch.setattr(
            "gdm_flow.dashboard.generate_dashboard", _fake_generate_dashboard
        )

        out = tmp_path / "test.html"
        cli.plot(model=Path("model.json"), output=out, solver=[cli.Solver.ldf])
        assert dashboard_called["called"]

    def test_plot_handles_solver_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cli, "console", _DummyConsole())
        monkeypatch.setattr(cli, "err_console", _DummyConsole())
        monkeypatch.setattr(cli, "_load_system", lambda _m: _FakeSystem())

        def _failing_solver(_s):
            raise RuntimeError("solver failed")

        monkeypatch.setitem(cli.SOLVER_MAP, cli.Solver.ac, _failing_solver)

        def _fake_generate_dashboard(system, results, output, model_name=None):
            pass

        monkeypatch.setattr(
            "gdm_flow.dashboard.generate_dashboard", _fake_generate_dashboard
        )

        out = tmp_path / "test.html"
        cli.plot(model=Path("model.json"), output=out, solver=[cli.Solver.ac])


class TestMultiperiodCommand:
    def test_multiperiod_no_time_series_raises_exit(self, monkeypatch):
        monkeypatch.setattr(cli, "console", _DummyConsole())
        monkeypatch.setattr(cli, "err_console", _DummyConsole())
        monkeypatch.setattr(cli, "_load_system", lambda _m: _FakeSystem())
        monkeypatch.setattr(
            "gdm_flow.time_series.has_time_series_data", lambda _s: False
        )
        with pytest.raises(typer.Exit):
            cli.multiperiod(
                model=Path("ignored.json"),
                solver=cli.Solver.dc,
                start=0,
                end=None,
                step=1,
                ramp=None,
                db=None,
            )


class TestFormatHelpers:
    def test_fmt_w_megawatt(self):
        assert "MW" in cli._fmt_w(5_000_000.0)

    def test_fmt_w_kilowatt(self):
        assert "kW" in cli._fmt_w(5_000.0)

    def test_fmt_w_watt(self):
        assert "W" in cli._fmt_w(50.0)

    def test_fmt_var_megavar(self):
        assert "Mvar" in cli._fmt_var(5_000_000.0)

    def test_fmt_var_kilovar(self):
        assert "kvar" in cli._fmt_var(5_000.0)

    def test_fmt_var_var(self):
        assert "var" in cli._fmt_var(50.0)

    def test_success_badge_true(self):
        assert "PASS" in cli._success_badge(True)

    def test_success_badge_false(self):
        assert "FAIL" in cli._success_badge(False)
