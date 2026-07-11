# Y-Bus Construction

The Y-bus (admittance matrix) is the shared foundation for all GDM-Flow solvers. It encodes the network topology, branch impedances, and transformer models in a single complex-valued matrix.

## Theory

For a system with $n$ bus-phase nodes, the Y-bus is an $n \times n$ complex matrix where:

$$Y_{bus} \cdot V = I$$

Each branch between nodes $i$ and $j$ with series admittance $y = z^{-1}$ is stamped as:

$$Y_{ii} \mathrel{+}= y, \quad Y_{jj} \mathrel{+}= y, \quad Y_{ij} \mathrel{-}= y, \quad Y_{ji} \mathrel{-}= y$$

### Transformer Model

Two-winding transformers with turns ratio $a = V_{primary} / V_{secondary}$ use the standard model:

$$\begin{bmatrix} I_p \\ I_s \end{bmatrix} = \begin{bmatrix} y & -ay \\ -ay & a^2 y \end{bmatrix} \begin{bmatrix} V_p \\ V_s \end{bmatrix}$$

This ensures zero current injection at nominal voltages (no phantom power) and properly handles voltage transformation across winding ratios.

### Center-Tapped (Split-Phase) Transformer Model

Center-tapped transformers have three windings: a primary (e.g. phase A at 7200 V) and two 120 V secondaries sharing a neutral center tap. In the GDM data model these appear as:

- **Winding 0** (primary): phases `[A]` (or `B`, `C`)
- **Winding 1**: phases `[S1, N]` — positive polarity
- **Winding 2**: phases `[N, S2]` — reversed polarity

Because primary phases (A/B/C) and secondary phases (S1/S2) have different names, the standard two-winding common-phase matching produces no connections. The center-tapped handler detects this case (empty `common_phases` with ≥ 3 windings) and stamps each secondary winding independently.

**Polarity detection.** The winding phase ordering determines voltage polarity relative to the primary. When the neutral (`N`) appears *before* the signal phase in the winding list (e.g. `[N, S2]`), the voltage at that node is antiphase — the effective turns ratio is negated:

$$a_{S2} = -\frac{V_{primary}}{V_{secondary}}$$

This yields a 180° phase offset between S1 and S2 at the center tap, matching the physical behavior of a center-tapped service transformer.

**Admittance splitting.** The total transformer leakage admittance $y$ is divided equally among secondary windings ($y_w = y / N_{sec}$) so that the parallel combination of all secondary paths equals the total admittance.

**Neutral Node Handling (New in v0.5+)** — When `include_neutral=True`, the Y-bus automatically discovers split-phase secondary buses that have `Phase.N` in their winding phases but not in the bus's own `phases` list, and adds an explicit neutral (N) node for them. This ensures the center tap is represented in the admittance matrix rather than being silently Kron-reduced to ground.

With an explicit neutral node present, the transformer uses **full 4-node stamping** (P, S1, S2, N) instead of Kron reduction. This correctly handles floating (ungrounded) center taps:

$$
\begin{bmatrix}
  y & -a y & 0 & 0 \\
  -a y & a^2 y & -a^2 y & 0 \\
  0 & -a^2 y & a^2 y & 0 \\
  0 & 0 & 0 & 0
\end{bmatrix}
$$

Without a neutral node (legacy behavior or `include_neutral=False`), the neutral is Kron-reduced and the S1–S2 coupling terms are added explicitly.

#### Assumptions

- Each secondary winding is modeled as an independent two-winding transformer path from the primary. Mutual coupling between S1 and S2 secondaries is not modeled within the transformer itself (downstream branch impedance matrices may include S1–S2 coupling).
- Winding polarity is inferred from the ordering of phases in the GDM `winding_phases` list: neutral before signal → reversed polarity.
- The admittance is split equally across secondary windings ($y_w = y / N_{sec}$), assuming identical secondary winding ratings.
- When the neutral node exists in Y-bus, it is held at 0 V (ground reference). This is enforced by marking N nodes as slack in the AC PF solver.

## Node Indexing

The Y-bus assigns a unique integer index to each `(bus_name, phase)` pair. The `YBusResult` contains the mapping:

```python
result = calculate_ybus(system)

# Index → label
label = result.index_to_label[0]  # e.g., ("bus_1", "A")

# Label → index
idx = result.label_to_index[("bus_1", "A")]  # e.g., 0
```

## Supported Branch Types

| Branch Type | Description |
|-------------|-------------|
| `MatrixImpedanceBranch` | Full phase impedance/admittance matrix |
| `SequenceImpedanceBranch` | Positive/zero sequence impedance → phase domain via symmetrical components |
| `GeometryBranch` | Wire geometry → auto-converted to matrix representation |
| `DistributionTransformer` | Two-winding or center-tapped (3-winding) transformer with per-unit leakage impedance |

## Usage

### Basic Y-Bus

```python
from gdm_flow import calculate_ybus

result = calculate_ybus(system)
print(f"Shape: {result.ybus.shape}")
print(f"Nodes: {len(result.index_to_label)}")
```

### With Options

```python
result = calculate_ybus(
    system,
    include_neutral=True,        # Include neutral phase nodes
    include_shunt=True,          # Include line charging (pi model)
    include_transformers=True,   # Include transformer admittance
    sparse=True,                 # Return scipy CSR matrix
    frequency_hz=60.0,           # System frequency for shunt
)
```

### Inspecting the Matrix

```python
import numpy as np

Y = result.ybus
print(f"Non-zero entries: {np.count_nonzero(Y)}")
print(f"Symmetric: {np.allclose(Y, Y.T)}")
print(f"Condition number: {np.linalg.cond(Y):.2e}")
```
