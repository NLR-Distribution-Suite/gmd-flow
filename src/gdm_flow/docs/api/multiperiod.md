# API — Multi-Period OPF

## `BatterySpec`

Battery parameters for multi-period optimization.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | — | Battery identifier |
| `node` | `tuple[str, str]` | — | `(bus_name, phase)` connection point |
| `energy_capacity_wh` | `float` | — | Total energy capacity (Wh) |
| `p_charge_max_w` | `float` | — | Maximum charging power (W) |
| `p_discharge_max_w` | `float` | — | Maximum discharging power (W) |
| `soc_initial` | `float` | `0.5` | Initial state of charge |
| `soc_min` | `float` | `0.1` | Minimum allowable SOC |
| `soc_max` | `float` | `0.9` | Maximum allowable SOC |
| `charge_efficiency` | `float` | `0.95` | Charging efficiency |
| `discharge_efficiency` | `float` | `0.95` | Discharging efficiency |
| `cost_linear` | `float` | `10.0` | Linear cost coefficient |

## `MultiPeriodResult`

Result from multi-period optimization.

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether solver converged |
| `message` | `str` | Status message |
| `solver` | `str` | Solver used (`"dc"` or `"ldf"`) |
| `num_timesteps` | `int` | Number of timesteps |
| `objective` | `float` | Optimal objective value |
| `generator_dispatch_w` | `dict[int, dict[str, float]]` | `timestep → {gen_name → watts}` |
| `battery_soc` | `dict[str, list[float]]` | `battery_name → SOC trace` |
| `nodal_voltage` | `dict \| None` | Per-timestep voltages (LinDistFlow only) |
| `theta_rad` | `dict \| None` | Per-timestep angles (DC OPF only) |
| `slack_injection_w` | `dict \| None` | Per-timestep slack injection (DC OPF only) |
| `db_path` | `str \| None` | SQLite database path |
| `run_id` | `str \| None` | Unique run identifier |

## Functions

### `build_battery_specs_from_components(system, ...)`

Extract `BatterySpec` list from system battery components.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system` | `DistributionSystem` | — | Input system |
| `soc_initial` | `float` | `0.5` | Initial SOC for all batteries |
| `soc_min` | `float` | `0.1` | Minimum SOC |
| `soc_max` | `float` | `0.9` | Maximum SOC |
| `charge_efficiency` | `float` | `0.95` | Charging efficiency |
| `discharge_efficiency` | `float` | `0.95` | Discharging efficiency |
| `cost_linear` | `float` | `10.0` | Linear cost |

**Returns:** `list[BatterySpec]`

### `solve_multiperiod_dc_opf(system, *, generators, timestep_range, ...)`

Solve multi-period DC OPF with battery SOC coupling and optional ramp constraints.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system` | `DistributionSystem` | — | Input system with time series |
| `generators` | `list[DCGenerator]` | — | Dispatchable generators |
| `timestep_range` | `range` | — | Timestep indices |
| `battery_specs` | `list[BatterySpec] \| None` | `None` | Battery parameters (auto-extracted if None) |
| `ramp_limit_w` | `float \| None` | `None` | Generator ramp limit (W) |
| `db_path` | `str \| None` | `None` | SQLite output path |

**Returns:** `MultiPeriodResult`

**Formulation:** Joint LP over all timesteps with:
- Nodal power balance per timestep
- Generator capacity bounds
- Battery charge/discharge limits and SOC dynamics
- Optional ramp limits: $|P_g^t - P_g^{t-1}| \leq R$

### `solve_multiperiod_lindistflow(system, *, timestep_range, ...)`

Solve multi-period LinDistFlow with battery SOC coupling.

Two-stage approach:
1. LP optimizes battery dispatch schedule across all timesteps
2. LinDistFlow re-solves per timestep with optimized battery injections

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system` | `DistributionSystem` | — | Input system with time series |
| `timestep_range` | `range` | — | Timestep indices |
| `battery_specs` | `list[BatterySpec] \| None` | `None` | Battery parameters |
| `db_path` | `str \| None` | `None` | SQLite output path |

**Returns:** `MultiPeriodResult`
