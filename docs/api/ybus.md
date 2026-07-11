# API — Y-Bus

## `YBusResult`

Dataclass returned by `calculate_ybus`.

| Field | Type | Description |
|-------|------|-------------|
| `ybus` | `np.ndarray` or `scipy.sparse.csr_matrix` | Complex admittance matrix |
| `index_to_label` | `list[tuple[str, str]]` | Maps integer index → `(bus_name, phase)` |
| `label_to_index` | `dict[tuple[str, str], int]` | Maps `(bus_name, phase)` → integer index |

## `calculate_ybus`

```python
def calculate_ybus(
    system: DistributionSystem,
    *,
    include_neutral: bool = False,
    include_shunt: bool = True,
    include_transformers: bool = True,
    include_regulators: bool = True,
    sparse: bool = False,
    frequency_hz: float = 60.0,
    vbase_override: dict[str, float] | None = None,
    debug: bool = False,
) -> YBusResult:
```

Build the bus admittance matrix from all branches and transformers in the system.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `system` | — | A `DistributionSystem` instance |
| `include_neutral` | `False` | Include neutral (N) phase nodes |
| `include_shunt` | `True` | Include line charging admittance (pi model) |
| `include_transformers` | `True` | Include transformer admittance stamps |
| `include_regulators` | `True` | Include regulator turns ratio and impedance |
| `sparse` | `False` | Return `scipy.sparse.csr_matrix` instead of dense `np.ndarray` |
| `frequency_hz` | `60.0` | System frequency for computing shunt susceptance |
| `vbase_override` | `None` | Override nominal voltage bases per bus |
| `debug` | `False` | Print diagnostic information during construction |

**Returns:** `YBusResult`

**Example:**

```python
from gdm.distribution import DistributionSystem
from gdm_flow import calculate_ybus

system = DistributionSystem.from_json("model.json")
result = calculate_ybus(system, sparse=True)

print(f"Matrix shape: {result.ybus.shape}")
print(f"Number of nodes: {len(result.index_to_label)}")
```
