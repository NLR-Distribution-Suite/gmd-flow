# API — AC PF (Fixed-Point Iteration)

## `ACPowerFlowResult`

Dataclass returned by AC PF solvers.

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether solver converged |
| `message` | `str` | Solver status message |
| `ybus_result` | `YBusResult` | Y-bus matrix and node mapping |
| `voltage` | `np.ndarray` | Complex nodal voltages (V) |
| `voltage_pu` | `np.ndarray` | Per-unit voltage magnitudes |
| `power_injection` | `np.ndarray` | Complex power injections (W + j·var) |
| `iterations` | `int` | Fixed-point iterations |
| `max_mismatch_pu` | `float` | Final maximum per-unit voltage change |

## `solve_ac_power_flow`

Low-level fixed-point iteration AC power flow solver (OpenDSS-style).

```python
def solve_ac_power_flow(
    system: DistributionSystem,
    *,
    p_spec_w: dict[BusPhaseLabel, float] | None = None,
    q_spec_var: dict[BusPhaseLabel, float] | None = None,
    slack_label: BusPhaseLabel | list[BusPhaseLabel] | None = None,
    include_neutral: bool = False,
    include_shunt: bool = False,
    convert_geometry_to_matrix: bool = True,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> ACPowerFlowResult:
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `p_spec_w` | `None` | Active power spec per node (W, positive = generation) |
| `q_spec_var` | `None` | Reactive power spec per node (var) |
| `slack_label` | `None` | Slack bus-phase node(s). Defaults to all non-neutral phases of the source bus |
| `include_neutral` | `False` | Include neutral phase in Y-bus |
| `include_shunt` | `False` | Include shunt admittance from `c_matrix` |
| `convert_geometry_to_matrix` | `True` | Convert geometry-based impedances to matrix form |
| `max_iterations` | `100` | Maximum fixed-point iterations |
| `tolerance` | `1e-6` | Per-unit voltage change convergence threshold |

## `solve_ac_power_flow_from_components`

Convenience wrapper that auto-derives P/Q specs from system components.

```python
def solve_ac_power_flow_from_components(
    system: DistributionSystem,
    *,
    include_loads: bool = True,
    include_solar: bool = True,
    include_battery: bool = False,
    include_capacitor: bool = True,
    load_scale: float = 1.0,
    solar_scale: float = 1.0,
    battery_scale: float = 1.0,
    capacitor_scale: float = 1.0,
    slack_label: BusPhaseLabel | list[BusPhaseLabel] | None = None,
    include_neutral: bool = False,
    include_shunt: bool = False,
    convert_geometry_to_matrix: bool = True,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> ACPowerFlowResult:
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `include_loads` | `True` | Include distribution loads in P/Q specs |
| `include_solar` | `True` | Include solar PV generation |
| `include_battery` | `False` | Include battery storage |
| `include_capacitor` | `True` | Include capacitor reactive injection |
| `load_scale` | `1.0` | Multiplier for load magnitudes |
| `solar_scale` | `1.0` | Multiplier for solar generation |
| `battery_scale` | `1.0` | Multiplier for battery dispatch |
| `capacitor_scale` | `1.0` | Multiplier for capacitor injection |
| `slack_label` | `None` | Slack bus-phase node(s) |
| `max_iterations` | `100` | Maximum fixed-point iterations |
| `tolerance` | `1e-6` | Per-unit voltage change convergence threshold |
