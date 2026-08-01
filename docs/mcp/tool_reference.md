# MCP Tool Reference

This page documents the tools exposed by `gdm-flow-mcp-server`.

## Solver And Matrix Tools

## `calculate_ybus`
Build phase-domain Y-bus matrix metadata from a DistributionSystem JSON.

Key inputs:
- `system_path` (required)
- `include_neutral` (default `false`)
- `include_shunt` (default `false`)
- `include_transformers` (default `true`)
- `include_open_switches` (default `false`)
- `convert_geometry_to_matrix` (default `true`)
- `sparse` (default `true`)
- `include_matrix` (default `false`)
- `matrix_preview_limit` (default `10`)

Returns:
- Node count, nonzero count, sparse flag
- Label mapping (`bus`, `phase`)
- Optional top-left matrix preview

## `run_ac_opf`
Run AC OPF from component-derived specs.

Key inputs:
- `system_path` (required)
- Component toggles (`include_loads`, `include_solar`, `include_battery`, `include_capacitor`)
- Regulator toggles (`include_regulator_targets`, `include_regulator_limits`)
- Network options (`include_neutral`, `include_shunt`, `convert_geometry_to_matrix`)
- Voltage bounds (`vm_min_pu`, `vm_max_pu`)
- `max_nfev`
- `include_details`

Returns:
- Convergence status and objective values
- Voltage min/max
- Source injection totals
- Optional per-node voltage and injection details

## `run_dc_opf`
Run DC OPF from component-derived demand and generators.

Key inputs:
- `system_path` (required)
- Generator toggles (`include_solar_generators`, `include_battery_generators`)
- `include_loads`, `include_slack_generator`, `slack_cost_linear`
- Network options (`include_neutral`, `include_shunt`, `convert_geometry_to_matrix`)
- Angle bounds (`theta_min_rad`, `theta_max_rad`)
- `theta_penalty`, `maxiter`
- `include_details`

Returns:
- Convergence status, objective, iterations
- Slack injection and total dispatch
- Optional generator dispatch, theta, nodal balance details

## `run_lindistflow`
Run LinDistFlow using component-derived net injections.

Key inputs:
- `system_path` (required)
- Component toggles (`include_loads`, `include_solar`, `include_battery`, `include_capacitor`)
- `include_neutral`, `include_open_switches`
- `include_details`

Returns:
- Convergence status and source bus
- Voltage min/max and modeled counts
- Optional node voltages and branch flows

## `compare_solvers`
Run AC OPF, DC OPF, and LinDistFlow and return side-by-side summary.

Key inputs:
- `system_path` (required)
- `include_details`

Returns:
- Per-solver result blocks (`ac`, `dc`, `lindistflow`)
- Summary block with quick comparison fields

## `export_sqlite`
Run selected solvers and export results to SQLite.

Key inputs:
- `system_path` (required)
- `db_path` (required)
- `run_ac`, `run_dc`, `run_lindistflow` (all default `true`)

Returns:
- Database path
- Run IDs written by solver type
- Exported solver flags

## Documentation And API Tools

## `list_documentation`
List documentation files under `docs/` (`.md`, `.ipynb`, excluding build artifacts).

## `search_documentation`
Search docs text and return snippets.

Key inputs:
- `query` (required)
- `max_results` (default `5`)

## `get_documentation_page`
Read a docs page by path relative to `docs/`.

Key inputs:
- `doc_path` (required, for example `solvers/ac_opf.md`)
- `start_line` (default `1`)
- `max_lines` (default `160`)

## `list_api_symbols`
List public symbols exported by `gdm_flow.__all__`.

## `get_api_reference`
Get module, signature, and docstring for a public API symbol.

Key inputs:
- `symbol_name` (required)
