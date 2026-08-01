"""Solver and matrix tools for the GDM-Flow MCP server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer

from gdm_flow import (
    build_battery_specs_from_components,
    build_dc_generators_from_components,
    build_lindistflow_net_injections_from_components,
    export_all_results_to_sqlite,
    generate_ts_dashboard,
    optimize_ac_power_flow_from_components,
    solve_ac_power_flow_from_components,
    solve_dc_opf_from_components,
    solve_lindistflow,
    solve_multiperiod_dc_opf,
)
from gdm_flow import (
    calculate_ybus as _calculate_ybus,
)
from gdm_flow import (
    run_qsts as _run_qsts,
)
from gdm_flow.mcp.common import (
    _get_system_path_arg,
    _load_system,
    _serialize_ac_pf_result,
    _serialize_ac_result,
    _serialize_dc_result,
    _serialize_lindistflow_result,
    _serialize_multiperiod_result,
    _serialize_qsts_summary,
    _serialize_ybus_result,
)


def register(mcp: MCPServer) -> None:
    """Register all solver and matrix tools."""

    @mcp.tool()
    def calculate_ybus(
        system_path: str | None = None,
        model_ref: dict[str, Any] | None = None,
        include_neutral: bool = False,
        include_shunt: bool = False,
        include_transformers: bool = True,
        include_open_switches: bool = False,
        convert_geometry_to_matrix: bool = True,
        sparse: bool = True,
        include_matrix: bool = False,
        matrix_preview_limit: int = 10,
    ) -> str:
        """Build phase-domain Y-bus matrix metadata for a DistributionSystem JSON model.

        Args:
            system_path: Path to system JSON file.
            model_ref: Optional model reference ({model_id/version} or direct stored_path/path).
            include_neutral: Whether to include neutral nodes.
            include_shunt: Whether to include shunt elements.
            include_transformers: Whether to include transformers.
            include_open_switches: Whether to include open switches.
            convert_geometry_to_matrix: Whether to convert geometry to matrix coordinates.
            sparse: Whether to build a sparse Y-bus.
            include_matrix: Include a top-left matrix preview in the result.
            matrix_preview_limit: Preview matrix side length when include_matrix=true.

        Returns:
            JSON payload with node count, nonzero count, sparse flag, label
            mapping, and optional matrix preview.
        """
        system = _load_system(_get_system_path_arg(system_path, model_ref))
        result = _calculate_ybus(
            system,
            include_neutral=include_neutral,
            include_shunt=include_shunt,
            include_transformers=include_transformers,
            include_open_switches=include_open_switches,
            convert_geometry_to_matrix=convert_geometry_to_matrix,
            sparse=sparse,
        )
        return json.dumps(
            _serialize_ybus_result(
                result,
                include_matrix=include_matrix,
                matrix_preview_limit=matrix_preview_limit,
            ),
            indent=2,
            default=str,
        )

    @mcp.tool()
    def run_ac_opf(
        system_path: str | None = None,
        model_ref: dict[str, Any] | None = None,
        include_loads: bool = True,
        include_solar: bool = True,
        include_battery: bool = False,
        include_capacitor: bool = True,
        include_regulator_targets: bool = True,
        include_regulator_limits: bool = True,
        include_neutral: bool = False,
        include_shunt: bool = False,
        convert_geometry_to_matrix: bool = True,
        vm_min_pu: float = 0.95,
        vm_max_pu: float = 1.05,
        max_nfev: int = 300,
        include_details: bool = False,
    ) -> str:
        """Run AC OPF directly from system components.

        Args:
            system_path: Path to system JSON file.
            model_ref: Optional model reference ({model_id/version} or direct stored_path/path).
            include_loads: Whether to include loads.
            include_solar: Whether to include solar.
            include_battery: Whether to include batteries.
            include_capacitor: Whether to include capacitors.
            include_regulator_targets: Whether to enforce regulator target voltages.
            include_regulator_limits: Whether to enforce regulator limits.
            include_neutral: Whether to include neutral nodes.
            include_shunt: Whether to include shunt elements.
            convert_geometry_to_matrix: Whether to convert geometry to matrix coordinates.
            vm_min_pu: Minimum voltage magnitude bound (per-unit).
            vm_max_pu: Maximum voltage magnitude bound (per-unit).
            max_nfev: Maximum number of function evaluations.
            include_details: Include per-node solved values.

        Returns:
            JSON payload with convergence status, objective values, voltage
            min/max, source injection totals, and optional per-node details.
        """
        system = _load_system(_get_system_path_arg(system_path, model_ref))
        result = optimize_ac_power_flow_from_components(
            system,
            include_loads=include_loads,
            include_solar=include_solar,
            include_battery=include_battery,
            include_capacitor=include_capacitor,
            include_regulator_targets=include_regulator_targets,
            include_regulator_limits=include_regulator_limits,
            include_neutral=include_neutral,
            include_shunt=include_shunt,
            convert_geometry_to_matrix=convert_geometry_to_matrix,
            vm_min_pu=vm_min_pu,
            vm_max_pu=vm_max_pu,
            max_nfev=max_nfev,
        )
        return json.dumps(
            _serialize_ac_result(result, include_details=include_details),
            indent=2,
            default=str,
        )

    @mcp.tool()
    def run_dc_opf(
        system_path: str | None = None,
        model_ref: dict[str, Any] | None = None,
        include_solar_generators: bool = True,
        include_battery_generators: bool = True,
        include_loads: bool = True,
        include_slack_generator: bool = True,
        slack_cost_linear: float = 50.0,
        include_neutral: bool = False,
        include_shunt: bool = False,
        convert_geometry_to_matrix: bool = True,
        theta_min_rad: float = -1.5707963267948966,
        theta_max_rad: float = 1.5707963267948966,
        theta_penalty: float = 1e-6,
        maxiter: int = 500,
        include_details: bool = False,
    ) -> str:
        """Run DC OPF directly from system components.

        Args:
            system_path: Path to system JSON file.
            model_ref: Optional model reference ({model_id/version} or direct stored_path/path).
            include_solar_generators: Whether to include solar generators.
            include_battery_generators: Whether to include battery generators.
            include_loads: Whether to include loads.
            include_slack_generator: Whether to include the slack generator.
            slack_cost_linear: Linear cost coefficient for the slack generator.
            include_neutral: Whether to include neutral nodes.
            include_shunt: Whether to include shunt elements.
            convert_geometry_to_matrix: Whether to convert geometry to matrix coordinates.
            theta_min_rad: Minimum voltage angle bound (radians).
            theta_max_rad: Maximum voltage angle bound (radians).
            theta_penalty: Penalty for angle bound violations.
            maxiter: Maximum solver iterations.
            include_details: Include generator dispatch and nodal details.

        Returns:
            JSON payload with convergence status, objective, iterations, slack
            injection, total dispatch, and optional details.
        """
        system = _load_system(_get_system_path_arg(system_path, model_ref))
        result = solve_dc_opf_from_components(
            system,
            include_solar_generators=include_solar_generators,
            include_battery_generators=include_battery_generators,
            include_loads=include_loads,
            include_slack_generator=include_slack_generator,
            slack_cost_linear=slack_cost_linear,
            include_neutral=include_neutral,
            include_shunt=include_shunt,
            convert_geometry_to_matrix=convert_geometry_to_matrix,
            theta_min_rad=theta_min_rad,
            theta_max_rad=theta_max_rad,
            theta_penalty=theta_penalty,
            maxiter=maxiter,
        )
        return json.dumps(
            _serialize_dc_result(result, include_details=include_details),
            indent=2,
            default=str,
        )

    @mcp.tool()
    def run_lindistflow(
        system_path: str | None = None,
        model_ref: dict[str, Any] | None = None,
        include_loads: bool = True,
        include_solar: bool = True,
        include_battery: bool = True,
        include_capacitor: bool = True,
        include_neutral: bool = False,
        include_open_switches: bool = False,
        include_details: bool = False,
    ) -> str:
        """Run LinDistFlow from component-derived net injections.

        Args:
            system_path: Path to system JSON file.
            model_ref: Optional model reference ({model_id/version} or direct stored_path/path).
            include_loads: Whether to include loads.
            include_solar: Whether to include solar.
            include_battery: Whether to include batteries.
            include_capacitor: Whether to include capacitors.
            include_neutral: Whether to include neutral nodes.
            include_open_switches: Whether to include open switches.
            include_details: Include per-node and per-branch outputs.

        Returns:
            JSON payload with convergence status, source bus, voltage min/max,
            modeled counts, and optional details.
        """
        system = _load_system(_get_system_path_arg(system_path, model_ref))
        p_net_w, q_net_var = build_lindistflow_net_injections_from_components(
            system,
            include_loads=include_loads,
            include_solar=include_solar,
            include_battery=include_battery,
            include_capacitor=include_capacitor,
        )
        result = solve_lindistflow(
            system,
            p_net_w=p_net_w,
            q_net_var=q_net_var,
            include_neutral=include_neutral,
            include_open_switches=include_open_switches,
        )
        return json.dumps(
            _serialize_lindistflow_result(result, include_details=include_details),
            indent=2,
            default=str,
        )

    @mcp.tool()
    def compare_solvers(
        system_path: str | None = None,
        model_ref: dict[str, Any] | None = None,
        include_details: bool = False,
    ) -> str:
        """Run AC OPF, DC OPF, and LinDistFlow and return a side-by-side summary.

        Args:
            system_path: Path to system JSON file.
            model_ref: Optional model reference ({model_id/version} or direct stored_path/path).
            include_details: Include full per-solver details in addition to summary.

        Returns:
            JSON payload with per-solver result blocks and a summary block.
        """
        system = _load_system(_get_system_path_arg(system_path, model_ref))

        ac = optimize_ac_power_flow_from_components(system)
        dc = solve_dc_opf_from_components(system)
        ldf = solve_lindistflow(system)

        ac_summary = _serialize_ac_result(ac, include_details=include_details)
        dc_summary = _serialize_dc_result(dc, include_details=include_details)
        ldf_summary = _serialize_lindistflow_result(
            ldf, include_details=include_details
        )

        return json.dumps(
            {
                "ac": ac_summary,
                "dc": dc_summary,
                "lindistflow": ldf_summary,
                "summary": {
                    "ac_success": ac_summary["success"],
                    "dc_success": dc_summary["success"],
                    "lindistflow_success": ldf_summary["success"],
                    "ac_source_p_w": ac_summary["source_injection"]["p_w"],
                    "dc_slack_injection_w": dc_summary["slack_injection_w"],
                    "ldf_source_bus": ldf_summary["source_bus"],
                },
            },
            indent=2,
            default=str,
        )

    @mcp.tool()
    def export_sqlite(
        db_path: str,
        system_path: str | None = None,
        model_ref: dict[str, Any] | None = None,
        run_ac: bool = True,
        run_dc: bool = True,
        run_lindistflow: bool = True,
    ) -> str:
        """Run selected OPF solvers and export results to a SQLite database.

        Args:
            system_path: Path to system JSON file.
            model_ref: Optional model reference ({model_id/version} or direct stored_path/path).
            db_path: Output SQLite database path.
            run_ac: Whether to run and export the AC OPF result.
            run_dc: Whether to run and export the DC OPF result.
            run_lindistflow: Whether to run and export the LinDistFlow result.

        Returns:
            JSON payload with the database path and per-solver run IDs.
        """
        system = _load_system(_get_system_path_arg(system_path, model_ref))
        db_path = str(Path(db_path))

        if not any([run_ac, run_dc, run_lindistflow]):
            raise ValueError("At least one of run_ac, run_dc, run_lindistflow must be true")

        ac_result = optimize_ac_power_flow_from_components(system) if run_ac else None
        dc_result = solve_dc_opf_from_components(system) if run_dc else None
        ldf_result = solve_lindistflow(system) if run_lindistflow else None

        run_ids = export_all_results_to_sqlite(
            db_path,
            ac_result=ac_result,
            dc_result=dc_result,
            lindistflow_result=ldf_result,
        )
        return json.dumps(
            {
                "db_path": db_path,
                "run_ids": run_ids,
                "exported": {
                    "ac": run_ac,
                    "dc": run_dc,
                    "lindistflow": run_lindistflow,
                },
            },
            indent=2,
            default=str,
        )

    @mcp.tool()
    def run_ac_pf(
        system_path: str | None = None,
        model_ref: dict[str, Any] | None = None,
        include_loads: bool = True,
        include_solar: bool = True,
        include_battery: bool = False,
        include_capacitor: bool = True,
        load_scale: float = 1.0,
        solar_scale: float = 1.0,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> str:
        """Run Newton-Raphson AC power flow directly from system components.

        Args:
            system_path: Path to system JSON file.
            model_ref: Optional model reference ({model_id/version} or direct stored_path/path).
            include_loads: Whether to include loads.
            include_solar: Whether to include solar.
            include_battery: Whether to include batteries.
            include_capacitor: Whether to include capacitors.
            load_scale: Multiplicative scale applied to load power.
            solar_scale: Multiplicative scale applied to solar power.
            max_iterations: Maximum Newton-Raphson iterations.
            tolerance: Convergence tolerance.

        Returns:
            JSON payload with convergence status, mismatch, per-node voltages
            and power injections.
        """
        system = _load_system(_get_system_path_arg(system_path, model_ref))
        result = solve_ac_power_flow_from_components(
            system,
            include_loads=include_loads,
            include_solar=include_solar,
            include_battery=include_battery,
            include_capacitor=include_capacitor,
            load_scale=load_scale,
            solar_scale=solar_scale,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
        return json.dumps(_serialize_ac_pf_result(result), indent=2, default=str)

    @mcp.tool()
    def run_qsts(
        solver: Literal["ac", "pf", "dc", "ldf"],
        system_path: str | None = None,
        model_ref: dict[str, Any] | None = None,
        timestep_start: int = 0,
        timestep_end: int = 95,
        db_path: str | None = None,
        include_loads: bool = True,
        include_solar: bool = True,
        include_battery: bool = False,
        include_capacitor: bool = True,
    ) -> str:
        """Run quasi-static time series simulation over component time series.

        Args:
            system_path: Path to system JSON file.
            model_ref: Optional model reference ({model_id/version} or direct stored_path/path).
            solver: Solver to run at each timestep. One of "ac", "pf", "dc", "ldf".
            timestep_start: First timestep index (inclusive).
            timestep_end: Last timestep index (inclusive).
            db_path: Output SQLite database path for streamed results.
            include_loads: Whether to include loads.
            include_solar: Whether to include solar.
            include_battery: Whether to include batteries.
            include_capacitor: Whether to include capacitors.

        Returns:
            JSON payload with the QSTS summary (convergence, resolution,
            battery SOC traces, run metadata).
        """
        system = _load_system(_get_system_path_arg(system_path, model_ref))
        if solver not in ("ac", "pf", "dc", "ldf"):
            raise ValueError(f"Unknown solver: {solver!r}")
        timestep_range = range(timestep_start, timestep_end + 1)
        result = _run_qsts(
            system,
            solver,
            timestep_range,
            db_path=str(db_path) if db_path else None,
            include_loads=include_loads,
            include_solar=include_solar,
            include_battery=include_battery,
            include_capacitor=include_capacitor,
        )
        return json.dumps(_serialize_qsts_summary(result), indent=2, default=str)

    @mcp.tool()
    def run_multiperiod(
        system_path: str | None = None,
        model_ref: dict[str, Any] | None = None,
        timestep_start: int = 0,
        timestep_end: int = 23,
        db_path: str | None = None,
        include_batteries: bool = True,
        ramp_limit_w: float | None = None,
    ) -> str:
        """Run multi-period DC OPF with battery SOC coupling across timesteps.

        Args:
            system_path: Path to system JSON file.
            model_ref: Optional model reference ({model_id/version} or direct stored_path/path).
            timestep_start: First timestep index (inclusive).
            timestep_end: Last timestep index (inclusive).
            db_path: Output SQLite database path for streamed results.
            include_batteries: Whether to include batteries in the optimization.
            ramp_limit_w: Maximum inter-period generator ramp (watts).

        Returns:
            JSON payload with convergence status, objective, per-timestep
            generator dispatch, battery SOC, and run metadata.
        """
        system = _load_system(_get_system_path_arg(system_path, model_ref))
        timestep_range = range(timestep_start, timestep_end + 1)

        battery_specs = (
            build_battery_specs_from_components(system) if include_batteries else []
        )
        generators = build_dc_generators_from_components(system)

        result = solve_multiperiod_dc_opf(
            system,
            generators=generators,
            timestep_range=timestep_range,
            battery_specs=battery_specs,
            ramp_limit_w=float(ramp_limit_w) if ramp_limit_w is not None else None,
            db_path=str(db_path) if db_path else None,
        )
        return json.dumps(
            _serialize_multiperiod_result(result), indent=2, default=str
        )

    @mcp.tool()
    def plot_ts(
        db_path: str,
        run_id: str | None = None,
        output_path: str | None = None,
    ) -> str:
        """Generate an interactive HTML dashboard from QSTS/multi-period SQLite results.

        Args:
            db_path: Path to SQLite database with time series results.
            run_id: Specific run to visualize (defaults to latest run).
            output_path: Output HTML path (defaults to {db_path}.html).

        Returns:
            JSON payload with the output path and a confirmation message.
        """
        db_path = str(db_path)
        output_path = str(output_path or f"{db_path}.html")
        generate_ts_dashboard(db_path, output_path, run_id)
        return json.dumps(
            {
                "output_path": output_path,
                "message": f"Dashboard written to {output_path}",
            },
            indent=2,
            default=str,
        )
