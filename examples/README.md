# Examples

This folder contains runnable examples for all three optimization flavors in `gdm-flow`.

## Demo model

- `models/p5r.json` is a downloaded `DistributionSystem` demo model (via `gdmloader`).
- `models/p1rhs7_1247.json` is a larger Smart-DS style `DistributionSystem` model (via `gdmloader`).

## Run examples

From the repository root:

```bash
python examples/run_ac_opf_example.py
python examples/run_dc_opf_example.py
python examples/run_lindistflow_example.py
python examples/compare_plotly_results.py
```

If your active Python is not your project environment, use your full interpreter path.

## Plotly output

`compare_plotly_results.py` writes an interactive HTML comparison chart to:

- `examples/plots/opf_comparison_plotly.html`

The chart includes:

- Voltage magnitude comparison
- Voltage angle comparison
- Voltage magnitude absolute error
- Source active power flow comparison
- Top branch active power flow magnitudes
- Total loss estimate comparison
- Run quality summary table
