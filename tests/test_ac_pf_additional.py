"""Tests for ac_pf module and _utils module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from gdm_flow._utils import _phase_name, _phase_voltage
from gdm_flow.ac_pf import ACPowerFlowResult, solve_ac_power_flow


MODEL_PATH = Path("examples/models/p5r.json")


@pytest.fixture()
def system():
    if not MODEL_PATH.exists():
        pytest.skip("p5r.json model not found")
    from gdm.distribution import DistributionSystem

    return DistributionSystem.from_json(str(MODEL_PATH))


class TestUtils:
    def test_phase_name_from_enum(self):
        from gdm.distribution.enums import Phase

        assert _phase_name(Phase.A) == "A"
        assert _phase_name(Phase.B) == "B"
        assert _phase_name(Phase.C) == "C"
        assert _phase_name(Phase.N) == "N"

    def test_phase_name_from_string(self):
        assert _phase_name("A") == "A"
        assert _phase_name("S1") == "S1"

    def test_phase_voltage_line_to_ground(self):
        from gdm.distribution.enums import VoltageTypes

        class _V:
            def to(self, unit):
                return MagicMock(magnitude=120.0)

        result = _phase_voltage(_V(), VoltageTypes.LINE_TO_GROUND)
        assert result == 120.0

    def test_phase_voltage_line_to_line(self):
        from gdm.distribution.enums import VoltageTypes
        import math

        class _V:
            def to(self, unit):
                return MagicMock(magnitude=208.0)

        result = _phase_voltage(_V(), VoltageTypes.LINE_TO_LINE)
        expected = 208.0 / math.sqrt(3)
        assert abs(result - expected) < 0.01


class TestACPowerFlow:
    def test_solve_basic(self, system):
        result = solve_ac_power_flow(system)
        assert isinstance(result, ACPowerFlowResult)
        assert result.success is True
        assert result.iterations > 0
        assert len(result.voltage) > 0
        assert len(result.voltage_pu) > 0

    def test_solve_with_tolerances(self, system):
        result = solve_ac_power_flow(system, max_iterations=200, tolerance=1e-4)
        assert result.success is True

    def test_solve_with_warm_start(self, system):
        # First solve
        result1 = solve_ac_power_flow(system)
        assert result1.success

        # Build warm start from first result
        labels = result1.ybus_result.index_to_label
        v0 = {labels[i]: complex(result1.voltage[i]) for i in range(len(labels))}

        # Second solve with warm start should converge faster
        result2 = solve_ac_power_flow(system, v0_complex=v0)
        assert result2.success
        assert result2.iterations <= result1.iterations

    def test_power_injection_shape_matches_voltage(self, system):
        result = solve_ac_power_flow(system)
        assert result.voltage.shape == result.power_injection.shape

    def test_voltage_pu_reasonable(self, system):
        result = solve_ac_power_flow(system)
        # Per-unit voltages should be near 1.0 for a well-conditioned system
        assert np.all(result.voltage_pu > 0.8)
        assert np.all(result.voltage_pu < 1.2)

    def test_max_mismatch_below_tolerance(self, system):
        result = solve_ac_power_flow(system, tolerance=1e-5)
        if result.success:
            assert result.max_mismatch_pu < 1e-5
