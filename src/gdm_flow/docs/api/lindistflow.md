# API — LinDistFlow

## `LinDistFlowResult`

Dataclass returned by the LinDistFlow solver.

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether the solve completed |
| `message` | `str` | Status message |
| `source_bus` | `str` | Name of the source/root bus |
| `voltage_v` | `dict[BusPhaseLabel, float]` | Bus-phase voltage magnitudes (V) |
| `p_flow_w` | `dict[BranchPhaseLabel, float]` | Branch active power flows (W) |
| `q_flow_var` | `dict[BranchPhaseLabel, float]` | Branch reactive power flows (var) |
| `p_net_w` | `dict[BusPhaseLabel, float]` | Net active power at each bus (W) |
| `q_net_var` | `dict[BusPhaseLabel, float]` | Net reactive power at each bus (var) |

**Type aliases:**
- `BusPhaseLabel = tuple[str, str]` — e.g., `("bus_1", "A")`
- `BranchPhaseLabel = tuple[str, str, str]` — e.g., `("line_1", "bus_1", "A")`

## `solve_lindistflow`

Main solver function.

```python
def solve_lindistflow(
    system: DistributionSystem,
    *,
    p_net_w: dict[BusPhaseLabel, float] | None = None,
    q_net_var: dict[BusPhaseLabel, float] | None = None,
    include_neutral: bool = False,
    include_shunt: bool = True,
    include_transformers: bool = True,
    frequency_hz: float = 60.0,
    debug: bool = False,
) -> LinDistFlowResult:
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `p_net_w` | `None` | Net active power per node (W). Auto-built from components if omitted. |
| `q_net_var` | `None` | Net reactive power per node (var). Auto-built from components if omitted. |
| `include_neutral` | `False` | Include neutral phase nodes in Y-bus |
| `include_shunt` | `True` | Include line charging in Y-bus |
| `include_transformers` | `True` | Include transformers in Y-bus |
| `frequency_hz` | `60.0` | System frequency |
| `debug` | `False` | Print diagnostic information |

When `p_net_w` and `q_net_var` are both `None`, the solver automatically calls `build_lindistflow_net_injections_from_components` to extract loads, solar, batteries, and capacitors.

## `build_lindistflow_net_injections_from_components`

```python
def build_lindistflow_net_injections_from_components(
    system: DistributionSystem,
    *,
    include_loads: bool = True,
    include_solar: bool = True,
    include_battery: bool = True,
    include_capacitor: bool = True,
) -> tuple[dict[BusPhaseLabel, float], dict[BusPhaseLabel, float]]:
```

Returns `(p_net_w, q_net_var)` from system components.

**Sign convention:**
- Positive values = load/demand
- Negative values = generation/injection

**Example:**

```python
from gdm_flow import build_lindistflow_net_injections_from_components

p_net, q_net = build_lindistflow_net_injections_from_components(
    system,
    include_loads=True,
    include_solar=True,
)

# Modify injections
p_net[("bus_3", "A")] += 1000.0  # Add 1 kW load

from gdm_flow import solve_lindistflow
result = solve_lindistflow(system, p_net_w=p_net, q_net_var=q_net)
```
