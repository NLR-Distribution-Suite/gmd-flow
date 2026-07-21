# AC Power Flow (Fixed-Point Iteration)

The AC PF solver implements an OpenDSS-style fixed-point iteration for distribution systems. Unlike the [AC OPF](ac_opf.md) which *optimises* voltage magnitudes within bounds, the AC PF solves the standard power-flow equations: given fixed P/Q injections at PQ buses and a fixed voltage at the slack bus, find the voltage magnitude and angle at every bus.

## Formulation

The solver works directly in SI units (volts, amps, siemens) — no per-unit conversion — to avoid the ill-conditioning that arises when nominal voltages span 120 V–40 kV (a 331:1 ratio causing Y-pu diagonal ratios exceeding 325 million).

### Fixed-Point Iteration

At each iteration, the current injection at each non-slack node is computed from the specified power and current voltage:

$$
I_i^{(k)} = \frac{\overline{S_i^{\text{spec}}}}{\overline{V_i^{(k)}}} \quad \forall i \notin \text{slack}
$$

The updated voltage is obtained by solving the linear system:

$$
V_{\text{ns}}^{(k+1)} = Y_{\text{ns}}^{-1} \left( I_{\text{ns}}^{(k)} - Y_{\text{ns,slack}} \cdot V_{\text{slack}} \right)
$$

where $Y_{\text{ns}}$ is the Y-bus submatrix for non-slack nodes and $Y_{\text{ns,slack}}$ couples non-slack nodes to the fixed slack voltages.

An acceleration factor $\alpha = 0.5$ damps the update:

$$
V_{\text{ns}}^{(k+1)} = V_{\text{ns}}^{(k)} + \alpha \left( V_{\text{ns,calc}} - V_{\text{ns}}^{(k)} \right)
$$

### Convergence Criterion

Convergence is measured by the maximum relative voltage change across all non-slack nodes:

$$
\max_i \frac{|V_i^{(k+1)} - V_i^{(k)}|}{V_{\text{base},i}} < \text{tolerance}
$$

### Initial Voltage Estimate

Rather than starting from a flat 1.0 pu profile, the solver builds an initial voltage by solving $V = Y^{-1} \cdot I_{\text{source}}$ with loads modeled as constant impedances. This direct solve accounts for all transformer ratios and connections, giving a physically correct starting point.

## Key Features

- **SI-unit formulation** — avoids per-unit ill-conditioning across multi-voltage-level systems (120 V–40 kV)
- **Sparse LU factorisation** — a single `scipy.sparse.linalg.splu` factorisation reused across all fixed-point iterations
- **OpenDSS-style iteration** — no Jacobian construction; each iteration is a fast back-substitution
- **Direct initial solve** — $V = Y^{-1} \cdot I$ with constant-impedance loads provides a physically correct warm start
- **Neutral node support** — explicit neutral (N) nodes on split-phase secondary buses held at 0 V reference
- **Split-phase angle initialization** — correct S1/S2 angle initialization for center-tapped transformers with propagation through secondary networks
- **Connectivity detection** — unreachable nodes are automatically treated as slack to prevent singular systems
- **External warm-start (QSTS)** — accepts `v0_complex` from a previous timestep for time-series simulation

## Usage

### Low-level interface

```python
from gdm.distribution import DistributionSystem
from gdm_flow import solve_ac_power_flow

system = DistributionSystem.from_json("model.json")

result = solve_ac_power_flow(
    system,
    p_spec_w={("bus_5", "A"): -20_000.0},
    q_spec_var={("bus_5", "A"): -5_000.0},
    max_iterations=100,
    tolerance=1e-6,
)

print(result.success, result.iterations)
print(result.max_mismatch_pu)
```

### Component-based interface

```python
from gdm.distribution import DistributionSystem
from gdm_flow import solve_ac_power_flow_from_components

system = DistributionSystem.from_json("model.json")

result = solve_ac_power_flow_from_components(
    system,
    include_loads=True,
    include_solar=True,
    include_capacitor=True,
    load_scale=1.0,
    solar_scale=1.0,
)

print(f"Converged: {result.success}")
print(f"Iterations: {result.iterations}")
print(f"Max voltage change: {result.max_mismatch_pu:.2e} pu")
```

## Result Object

`ACPowerFlowResult` contains:

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether solver converged within tolerance |
| `message` | `str` | Convergence status message |
| `ybus_result` | `YBusResult` | Y-bus matrix and node mapping |
| `voltage` | `np.ndarray` | Complex bus voltages in SI volts |
| `voltage_pu` | `np.ndarray` | Per-unit voltage magnitudes |
| `power_injection` | `np.ndarray` | Complex power injection at each bus (W + j·var) |
| `iterations` | `int` | Number of fixed-point iterations |
| `max_mismatch_pu` | `float` | Final maximum per-unit voltage change |

## AC PF vs AC OPF

| Aspect | AC PF | AC OPF |
|--------|-------|--------|
| **Method** | Fixed-point iteration (current injection) | Nonlinear least-squares (optimisation) |
| **Units** | SI (volts, amps, siemens) | Per-unit |
| **Slack bus** | Fixed at nominal voltage | Adjusted within bounds |
| **Voltage bounds** | None — reports actual voltages | Enforced via `vm_min_pu` / `vm_max_pu` |
| **Regulator targets** | Not modeled | Soft voltage targets via penalty |
| **Use case** | Classical power flow baseline | Voltage regulation studies |

Both solvers share the same Y-bus construction and produce compatible result objects, making them easy to compare side-by-side.
