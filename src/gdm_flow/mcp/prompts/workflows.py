"""Pre-built prompt templates for common GDM-Flow workflows."""

from __future__ import annotations

from mcp.server import MCPServer


def register(mcp: MCPServer) -> None:
    """Register workflow prompt templates."""

    @mcp.prompt(description="Load a system, run AC power flow, and export results")
    def run_ac_pf_workflow(system_path: str) -> str:
        """Load a system, run AC power flow, and export results.

        Args:
            system_path: Path to the system JSON file.
        """
        return f"""I'll help you run an AC power flow analysis.

System path: {system_path}

1. First, load the system using `run_ac_pf` with the system path.
2. Review the power flow results (voltages, power injections).
3. Export the results to SQLite using `export_sqlite`.
4. Optionally, plot the time series dashboard using `plot_ts`.
"""

    @mcp.prompt(description="Load a system, run QSTS simulation, and plot time series")
    def run_qsts_workflow(system_path: str) -> str:
        """Load a system, run QSTS simulation, and plot time series.

        Args:
            system_path: Path to the system JSON file.
        """
        return f"""I'll help you run a quasi-static time series simulation.

System path: {system_path}

1. Load the system using the system path.
2. Run `run_qsts` with the desired solver (ac/pf/dc/ldf) and timestep range.
3. Review the QSTS summary (convergence, battery SOC traces).
4. Plot the time series dashboard using `plot_ts` with the db_path from the run.
5. Export results to SQLite if not already done.
"""

    @mcp.prompt(description="Load a system, run OPF analysis, and compare solvers")
    def run_opf_workflow(system_path: str) -> str:
        """Load a system, run OPF analysis, and compare solvers.

        Args:
            system_path: Path to the system JSON file.
        """
        return f"""I'll help you run an optimal power flow analysis.

System path: {system_path}

1. Load the system using the system path.
2. Run `run_ac_opf` for AC OPF, `run_dc_opf` for DC OPF, or
   `run_lindistflow` for LinDistFlow.
3. Use `compare_solvers` to compare results across solver types.
4. Run `run_multiperiod` for multi-period optimization.
5. Export results to SQLite using `export_sqlite`.
"""
