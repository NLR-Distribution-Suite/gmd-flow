# API — AC OPF

## `PowerFlowOptimizationResult`

Dataclass returned by AC OPF solvers.

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether solver converged |
| `message` | `str` | Solver status message |
| `ybus_result` | `YBusResult` | Y-bus matrix and node mapping |
| `voltage` | `np.ndarray` | Complex nodal voltages (V) |
| `power_injection` | `np.ndarray` | Complex power injections (W + j·var) |
| `iterations` | `int` | Solver iterations |
| `initial_objective` | `float` | Starting objective value |
| `final_objective` | `float` | Converged objective value |

## `optimize_ac_power_flow`

Low-level AC OPF solver accepting explicit power specifications.

```python
def optimize_ac_power_flow(
    system: DistributionSystem,
    *,
    p_spec_w: dict[BusPhaseLabel, float] | None = None,
    q_spec_var: dict[BusPhaseLabel, float] | None = None,
    voltage_targets_v: dict[BusPhaseLabel, float] | None = None,
    voltage_limits_v: dict[BusPhaseLabel, tuple[float, float]] | None = None,
    slack_label: list[BusPhaseLabel] | None = None,
    vm_min_pu: float = 0.95,
    vm_max_pu: float = 1.05,
    voltage_reg_weight: float = 1e-3,
    voltage_target_weight: float = 1.0,
    mismatch_scale_floor_w: float = 1e3,
    max_nfev: int = 300,
    include_neutral: bool = False,
    include_shunt: bool = True,
) -> PowerFlowOptimizationResult:
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `p_spec_w` | `None` | Active power spec per node (W, positive = generation) |
| `q_spec_var` | `None` | Reactive power spec per node (var) |
| `voltage_targets_v` | `None` | Regulator voltage targets (V) |
| `voltage_limits_v` | `None` | Regulator voltage limits `(min_v, max_v)` per node |
| `slack_label` | `None` | List of slack `(bus, phase)` labels |
| `vm_min_pu` | `0.95` | Lower voltage bound (per-unit) |
| `vm_max_pu` | `1.05` | Upper voltage bound (per-unit) |
| `voltage_reg_weight` | `1e-3` | Voltage regularization strength |
| `voltage_target_weight` | `1.0` | Regulator target penalty strength |
| `mismatch_scale_floor_w` | `1e3` | Minimum power mismatch normalization |
| `max_nfev` | `300` | Maximum function evaluations |

## `optimize_ac_power_flow_from_components`

High-level wrapper that extracts power specs from `DistributionSystem` components.

```python
def optimize_ac_power_flow_from_components(
    system: DistributionSystem,
    *,
    include_loads: bool = True,
    include_solar: bool = True,
    include_capacitor: bool = True,
    include_battery: bool = True,
    include_regulator_targets: bool = True,
    include_regulator_limits: bool = True,
    **kwargs,
) -> PowerFlowOptimizationResult:
```

All `**kwargs` are forwarded to `optimize_ac_power_flow`.

## Builder Functions

### `build_nodal_power_specs_from_components`

```python
def build_nodal_power_specs_from_components(
    system: DistributionSystem,
    *,
    include_loads: bool = True,
    include_solar: bool = True,
    include_capacitor: bool = True,
    include_battery: bool = True,
) -> tuple[dict[BusPhaseLabel, float], dict[BusPhaseLabel, float]]:
```

Returns `(p_spec_w, q_spec_var)` dictionaries from system components.

### `build_regulator_voltage_targets_from_components`

```python
def build_regulator_voltage_targets_from_components(
    system: DistributionSystem,
) -> dict[BusPhaseLabel, float]:
```

Returns voltage targets from `DistributionRegulator` components.

### `build_regulator_voltage_limits_from_components`

```python
def build_regulator_voltage_limits_from_components(
    system: DistributionSystem,
) -> dict[BusPhaseLabel, tuple[float, float]]:
```

Returns voltage limits `(min_v, max_v)` from regulator bandwidth settings.
