# API — DC OPF

## `DCGenerator`

Dataclass representing a generator in the DC OPF formulation.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Generator identifier |
| `node` | `tuple[str, str]` | `(bus_name, phase)` where generator is connected |
| `p_min_w` | `float` | Minimum active power output (W) |
| `p_max_w` | `float` | Maximum active power output (W) |
| `cost_quadratic` | `float` | Quadratic cost coefficient ($/W²) |
| `cost_linear` | `float` | Linear cost coefficient ($/W) |
| `cost_constant` | `float` | Fixed cost ($) |

**Example:**

```python
from gdm_flow import DCGenerator

solar = DCGenerator(
    name="solar_pv_1",
    node=("bus_2", "A"),
    p_min_w=0.0,
    p_max_w=5000.0,
    cost_quadratic=0.0,
    cost_linear=5.0,
    cost_constant=0.0,
)
```

## `DCOPFResult`

Dataclass returned by DC OPF solvers.

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether optimizer converged |
| `message` | `str` | Status message |
| `objective` | `float` | Minimized total cost |
| `iterations` | `int` | Optimizer iterations |
| `generator_dispatch_w` | `dict[str, float]` | Optimal dispatch per generator |
| `theta_rad` | `dict[BusPhaseLabel, float]` | Voltage angles (radians) |
| `nodal_balance_w` | `dict[BusPhaseLabel, float]` | Net nodal power balance |
| `slack_injection_w` | `float` | Total slack bus injection (W) |
| `ybus_result` | `YBusResult` | Y-bus and node indexing |

## `solve_dc_opf`

Low-level DC OPF solver accepting explicit generators and demand.

```python
def solve_dc_opf(
    system: DistributionSystem,
    *,
    generators: list[DCGenerator],
    demand_w: dict[BusPhaseLabel, float],
    slack_label: list[BusPhaseLabel] | None = None,
    theta_min_rad: float = -1.0,
    theta_max_rad: float = 1.0,
    theta_penalty: float = 1e-6,
    include_neutral: bool = False,
    include_shunt: bool = True,
    include_transformers: bool = True,
    sparse: bool = False,
    frequency_hz: float = 60.0,
    debug: bool = False,
) -> DCOPFResult:
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `generators` | — | List of `DCGenerator` objects |
| `demand_w` | — | Active power demand per node (W, positive = load) |
| `slack_label` | `None` | Slack bus labels (auto-detected if omitted) |
| `theta_min_rad` | `-1.0` | Lower angle bound (radians) |
| `theta_max_rad` | `1.0` | Upper angle bound (radians) |
| `theta_penalty` | `1e-6` | Small regularization on angles |

## `solve_dc_opf_from_components`

High-level wrapper that builds generators and demand from system components.

```python
def solve_dc_opf_from_components(
    system: DistributionSystem,
    *,
    include_solar_generators: bool = True,
    include_battery_generators: bool = True,
    include_loads: bool = True,
    solar_cost_linear: float = 5.0,
    battery_cost_linear: float = 15.0,
    grid_cost_linear: float = 50.0,
    **kwargs,
) -> DCOPFResult:
```

**Cost defaults:** Solar=5, Battery=15, Grid=50. Lower cost → dispatched first.

## Builder Functions

### `build_dc_generators_from_components`

```python
def build_dc_generators_from_components(
    system: DistributionSystem,
    *,
    include_solar: bool = True,
    include_battery: bool = True,
    solar_cost_linear: float = 5.0,
    battery_cost_linear: float = 15.0,
    grid_cost_linear: float = 50.0,
) -> list[DCGenerator]:
```

Creates generators for solar PV (`active_power` for p_max), batteries (`active_power` for p_max), and grid import (at each source bus phase).

### `build_dc_load_profile_from_components`

```python
def build_dc_load_profile_from_components(
    system: DistributionSystem,
) -> dict[BusPhaseLabel, float]:
```

Returns demand dictionary from `DistributionLoad` components.
