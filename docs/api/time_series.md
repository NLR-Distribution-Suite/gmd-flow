# API — Time Series

## `TimeSeriesInfo`

Metadata for a single time series attached to a component.

| Field | Type | Description |
|-------|------|-------------|
| `component_type` | `str` | Component class name (e.g. `"DistributionLoad"`) |
| `component_name` | `str` | Component instance name |
| `variable_name` | `str` | Time series variable (e.g. `"active_power"`, `"irradiance"`) |
| `length` | `int` | Number of timesteps |
| `resolution` | `timedelta \| None` | Duration between timesteps |
| `initial_timestamp` | `datetime \| None` | Timestamp of first data point |
| `units` | `str` | Unit string (e.g. `"kilowatt"`) |

## `BatterySOCTracker`

Tracks battery state-of-charge across QSTS timesteps with efficiency and SOC limits.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | — | Battery component name |
| `energy_capacity_wh` | `float` | — | Total energy capacity (Wh) |
| `p_charge_max_w` | `float` | — | Maximum charging power (W) |
| `p_discharge_max_w` | `float` | — | Maximum discharging power (W) |
| `soc` | `float` | `0.5` | Current state of charge (0–1) |
| `soc_min` | `float` | `0.1` | Minimum SOC |
| `soc_max` | `float` | `0.9` | Maximum SOC |
| `charge_efficiency` | `float` | `0.95` | Charging efficiency |
| `discharge_efficiency` | `float` | `0.95` | Discharging efficiency |

**Methods:**
- `get_available_bounds(dt_hours)` → `(p_min_w, p_max_w)` — SOC-constrained power bounds
- `update(p_dispatch_w, dt_hours)` → `float` — Update SOC and return clamped dispatch

## `QSTSSummary`

Return type for completed QSTS simulations.

| Field | Type | Description |
|-------|------|-------------|
| `solver` | `str` | Solver used |
| `num_timesteps` | `int` | Total timesteps simulated |
| `num_converged` | `int` | Number that converged |
| `resolution` | `timedelta` | Timestep duration |
| `initial_timestamp` | `datetime \| None` | First timestamp |
| `db_path` | `str \| None` | SQLite database path |
| `run_id` | `str \| None` | Unique run identifier |
| `battery_soc_traces` | `dict[str, list[float]]` | Battery SOC histories |

## Discovery Functions

### `list_component_time_series(system)`

Discover all time series on loads, solar, and batteries.

**Returns:** `dict[str, list[TimeSeriesInfo]]` — keyed by component type name.

### `has_time_series_data(system)`

Check if any component has time series. **Returns:** `bool`.

### `get_time_series_length(system)`

Return minimum timestep count across all time series. **Raises** `ValueError` if none found.

### `get_time_series_resolution(system)`

Return time series resolution. **Raises** `ValueError` if none found.

### `get_time_series_timestamps(system)`

Return array of `datetime64` timestamps.

## Per-Timestep Extractors

### `build_nodal_power_specs_at_timestep(system, t_idx, ...)`

Build AC-convention nodal P/Q specs at timestep `t_idx`. Positive = generation, negative = load.

**Returns:** `(dict[BusPhaseLabel, float], dict[BusPhaseLabel, float])` — `(p_spec_w, q_spec_var)`

### `build_dc_load_profile_at_timestep(system, t_idx, ...)`

Build DC demand profile at timestep `t_idx`. Positive = demand.

**Returns:** `dict[BusPhaseLabel, float]`

### `build_lindistflow_injections_at_timestep(system, t_idx, ...)`

Build LinDistFlow net injections at timestep `t_idx`. Positive = demand, negative = injection.

**Returns:** `(dict[BusPhaseLabel, float], dict[BusPhaseLabel, float])` — `(p_net_w, q_net_var)`

## QSTS Orchestrator

### `run_qsts(system, solver, timestep_range, *, db_path=None, ...)`

Run Quasi-Static Time Series simulation.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system` | `DistributionSystem` | — | Input system with time series |
| `solver` | `str` | — | `"ac"`, `"pf"`, `"dc"`, or `"ldf"` |
| `timestep_range` | `range` | — | Timestep indices to simulate |
| `db_path` | `str \| None` | `None` | SQLite path for streaming results |
| `progress_callback` | `callable \| None` | `None` | Called with `(done, total)` |

**Returns:** `QSTSSummary`
