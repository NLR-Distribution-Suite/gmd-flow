# Command-Line Interface

GDM-Flow includes a modern CLI built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/) for colorful, readable terminal output.

## Installation

The CLI is installed automatically with the package:

```bash
pip install -e .
```

The command `gdm-flow` becomes available in your terminal.

## Commands

### `gdm-flow info`

Display system topology, component counts, and power summary.

```bash
gdm-flow info examples/models/p5r.json
```

**Output includes:**
- Source bus name and phases
- Bus count, transformer count, load count, solar PV count
- Total load (P and Q), solar active/rated power, net demand
- Per-bus details: phases, rated voltage, bus type

### `gdm-flow run`

Run one or more solvers on a distribution system model.

```bash
# Run AC OPF only (default)
gdm-flow run examples/models/p5r.json

# Run multiple solvers
gdm-flow run examples/models/p5r.json -s ac -s pf -s dc -s ldf

# Verbose — show voltage table and dispatch details
gdm-flow run examples/models/p5r.json -s ac -s dc -v
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `-s`, `--solver` | `ac` | Solver(s) to run: `ac`, `pf`, `dc`, `ldf` (repeatable) |
| `-v`, `--verbose` | `false` | Show detailed voltage and dispatch tables |

### `gdm-flow compare`

Run all four solvers and display a side-by-side comparison.

```bash
gdm-flow compare examples/models/p5r.json

# Also generate an HTML comparison plot
gdm-flow compare examples/models/p5r.json -o comparison.html
```

The comparison shows:
- Status (pass/fail) for each solver
- Source power (P and Q)
- Execution time and iteration count
- DC dispatch breakdown (grid, solar, battery)
- Agreement panel showing maximum disagreement in watts

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--output` | None | Export comparison to interactive HTML (requires plotly) |

### `gdm-flow plot`

Generate an interactive Plotly dashboard with voltage profiles, power flows, branch loading, losses, and equipment state.

```bash
# Generate dashboard with all four solvers
gdm-flow plot examples/models/p5r.json

# Select specific solvers
gdm-flow plot examples/models/p5r.json -s ac -s pf

# Custom output path
gdm-flow plot examples/models/p5r.json -o my_dashboard.html
```

The dashboard includes:
- **Voltage-distance profiles** along feeder paths (per-phase subplots preserving radial topology)
- **Per-phase voltage comparison** across solvers
- **Branch power flow and loading** analysis with ampacity limit tracking
- **Line loss breakdown** per branch
- **Equipment state** tables for capacitors, regulators, and transformers

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--output`, `-o` | `<model>_dashboard.html` | Output HTML path |
| `-s`, `--solver` | `ac pf dc ldf` | Solver(s) to include (repeatable) |

> **Requires:** `pip install -e '.[plotting]'` (installs plotly)

### `gdm-flow export`

Run solvers and export results to a SQLite database.

```bash
# Export all solvers
gdm-flow export examples/models/p5r.json --db results.db

# Export only AC and DC
gdm-flow export examples/models/p5r.json --db results.db -s ac -s dc
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--db` | *required* | Path to SQLite database file |
| `-s`, `--solver` | `ac pf dc ldf` | Solver(s) to export (repeatable) |

### `gdm-flow report-overvoltage`

Print voltage limit violations from exported AC OPF or LinDistFlow node results.

```bash
# Check latest AC run in database
gdm-flow report-overvoltage --db results.db

# Check latest AC PF run
gdm-flow report-overvoltage --db results.db -s pf

# Check latest LinDistFlow run
gdm-flow report-overvoltage --db results.db -s ldf

# Check a specific run id
gdm-flow report-overvoltage --db results.db -s ac --run-id ac_123456abcdef
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--db` | *required* | Path to SQLite database file |
| `-s`, `--solver` | `ac` | Solver result set: `ac`, `pf`, or `ldf` |
| `--run-id` | latest run | Specific run id to inspect |

### `gdm-flow report-overload`

Print branch loading violations from exported AC OPF, DC OPF, or LinDistFlow branch results.

> **DC note:** `-s dc` uses a post-processed DC approximation (angle-difference, P-only proxy), not full AC branch power flow.

```bash
# Check latest LinDistFlow run
gdm-flow report-overload --db results.db

# Check latest AC OPF run
gdm-flow report-overload --db results.db -s ac

# Check latest DC OPF run
gdm-flow report-overload --db results.db -s dc

# For DC, optionally print full percentage table instead of ranked severity
gdm-flow report-overload --db results.db -s dc --no-dc-severity-only

# Check a specific run id
gdm-flow report-overload --db results.db --run-id lindistflow_123456abcdef
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--db` | *required* | Path to SQLite database file |
| `-s`, `--solver` | `ldf` | Solver result set: `ac`, `dc`, or `ldf` |
| `--run-id` | latest solver run | Specific run id to inspect |
| `--dc-severity-only/--no-dc-severity-only` | `true` | For DC reports, show ranked severity instead of percent magnitudes |

### `gdm-flow db-schema`

Print the SQLite table/column schema for a database file.

```bash
# Show user tables and columns
gdm-flow db-schema --db results.db

# Include sqlite_* internal tables
gdm-flow db-schema --db results.db --include-internal
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--db` | *required* | Path to SQLite database file |
| `--include-internal` | `false` | Include SQLite internal tables |

---

## Time Series Commands

### `gdm-flow ts-info`

Display time series data availability for each component type in a model.

```bash
gdm-flow ts-info examples/models/p5r.json
```

**Output includes:**
- Overall time series length and resolution
- Per component type: variable name, length, resolution, start timestamp, units

### `gdm-flow qsts`

Run a Quasi-Static Time Series simulation. Each timestep is solved independently using the selected solver, with automatic warm-starting from the previous solution.

```bash
# Run LinDistFlow QSTS for first 24 hours (96 × 15-min steps)
gdm-flow qsts examples/models/p5r.json --solver ldf --end 96

# Stream results to SQLite
gdm-flow qsts examples/models/p5r.json -s ac --end 96 --db qsts.db

# Custom timestep range with stride
gdm-flow qsts examples/models/p5r.json -s pf --start 0 --end 192 --step 2
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `-s`, `--solver` | `ldf` | Solver to use: `ac`, `pf`, `dc`, `ldf` |
| `--start` | `0` | First timestep index |
| `--end` | all | Last timestep index |
| `--step` | `1` | Timestep stride |
| `--db` | None | SQLite path for streaming results |

### `gdm-flow multiperiod`

Run multi-period OPF with battery SOC coupling across the full time horizon.

```bash
# Multi-period DC OPF for 24 hours
gdm-flow multiperiod examples/models/p5r.json --solver dc --end 96

# With generator ramp limits and SQLite export
gdm-flow multiperiod examples/models/p5r.json -s dc --end 96 --ramp 5000 --db mp.db

# Multi-period LinDistFlow
gdm-flow multiperiod examples/models/p5r.json -s ldf --end 96
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `-s`, `--solver` | `dc` | Solver: `dc` or `ldf` only |
| `--start` | `0` | First timestep index |
| `--end` | `96` | Last timestep index |
| `--step` | `1` | Timestep stride |
| `--ramp` | None | Generator ramp limit in watts (DC OPF only) |
| `--db` | None | SQLite database path |

### `gdm-flow plot-ts`

Generate interactive Plotly HTML plots from QSTS or multi-period results stored in SQLite.

```bash
# Plot latest run
gdm-flow plot-ts qsts.db

# Plot specific run with custom output
gdm-flow plot-ts qsts.db --run-id ldf_abc123 -o timeseries.html
```

**Output includes:**
- Source power over time
- Voltage profiles per bus/phase across timesteps
- Battery SOC traces (when batteries are present)

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--run-id` | latest | Specific run ID |
| `-o`, `--output` | `<db>_ts.html` | Output HTML path |

> **Requires:** `pip install -e '.[plotting]'` (installs plotly)

## Examples

### Quick System Check

```bash
# What's in this model?
gdm-flow info examples/models/p5r.json

# Run all solvers and see if they agree
gdm-flow compare examples/models/p5r.json
```

### Full Analysis Pipeline

```bash
# 1. Inspect the system
gdm-flow info examples/models/p5r.json

# 2. Run solvers with detailed output
gdm-flow run examples/models/p5r.json -s ac -s pf -s dc -s ldf -v

# 3. Export to database for further analysis
gdm-flow export examples/models/p5r.json --db analysis.db

# 4. Generate comparison plot
gdm-flow compare examples/models/p5r.json -o comparison.html

# 5. Generate interactive dashboard
gdm-flow plot examples/models/p5r.json -o dashboard.html
```
