# LinDistFlow

LinDistFlow is a linearized power flow approximation for **radial** distribution feeders. It computes bus voltages and branch power flows using a single backward/forward sweep — no iteration required.

## Formulation

The DistFlow equations for a radial feeder branch $(i \to j)$ with impedance $r + jx$:

$$P_j = P_{ij} - r_{ij} \cdot \frac{P_{ij}^2 + Q_{ij}^2}{V_i^2}$$
$$Q_j = Q_{ij} - x_{ij} \cdot \frac{P_{ij}^2 + Q_{ij}^2}{V_i^2}$$
$$V_j^2 = V_i^2 - 2(r_{ij} P_{ij} + x_{ij} Q_{ij}) + (r_{ij}^2 + x_{ij}^2) \cdot \frac{P_{ij}^2 + Q_{ij}^2}{V_i^2}$$

The **linearized** approximation drops the quadratic loss terms:

$$V_j^2 \approx V_i^2 - 2(r_{ij} P_{ij} + x_{ij} Q_{ij})$$

### Two-Pass Algorithm

1. **Backward sweep** (leaves → root): Sum demands at each node to compute branch power flows
2. **Forward sweep** (root → leaves): Propagate voltage drops from the source using linearized equations

### Transformer Support

For transformer edges with turns ratio $a$ and impedance $z$, the voltage drop includes the turns ratio:

$$V_j = \frac{V_i}{a} - \frac{r \cdot P + x \cdot Q}{V_i / a}$$

## Usage

### High-Level (Recommended)

```python
from gdm_flow import solve_lindistflow

result = solve_lindistflow(system)

print(f"Success:    {result.success}")
print(f"Source bus:  {result.source_bus}")

# Total source injection
source_p = sum(result.p_net_w.values())
print(f"Source P:   {source_p:.1f} W")
```

### With Custom Injections

```python
from gdm_flow import (
    build_lindistflow_net_injections_from_components,
    solve_lindistflow,
)

# Build default injections, then modify
p_net, q_net = build_lindistflow_net_injections_from_components(
    system,
    include_loads=True,
    include_solar=True,
    include_battery=True,
    include_capacitor=True,
)

# Add a custom 2 kW load
p_net[("bus_3", "A")] = p_net.get(("bus_3", "A"), 0.0) + 2000.0

result = solve_lindistflow(system, p_net_w=p_net, q_net_var=q_net)
```

## Result Object

`LinDistFlowResult` contains:

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

## Sign Convention

- **Positive** `p_net_w` / `q_net_var` → load/demand (consumes power)
- **Negative** `p_net_w` / `q_net_var` → injection/generation (produces power)

## Limitations

- **Radial networks only** — requires a tree topology from the source bus
- **No losses** — the linearization drops $I^2R$ loss terms
- **No iteration** — single pass means no convergence issues but also no accuracy refinement
- **Voltage approximation** — works with $V^2$ internally, so accuracy degrades at high loading

## Center-Tapped Transformer Support

LinDistFlow traverses the GDM directed graph (not the Y-bus) and handles center-tapped transformers natively through the edge-based voltage drop propagation. All loads downstream of split-phase service transformers are included in the backward sweep. Unlike DC OPF, LinDistFlow does not rely on a small-angle approximation and correctly models power flow through center-tapped transformers.
