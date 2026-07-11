"""Debug LinDistFlow on IEEE-123."""

import networkx as nx
from gdm.distribution import DistributionSystem
from gdm.distribution.utils import aggregate_single_phase_transformers

system = DistributionSystem.from_json("tests/data/ieee-123/gdm/ieee_123_node.json")
aggregate_single_phase_transformers(system)

# Get the directed graph and inspect remaining cycles
digraph = system.get_directed_graph(return_radial_network=True)
cycles = list(nx.simple_cycles(digraph))
print(f"Remaining cycles after radial reduction: {len(cycles)}")
for c in cycles:
    print(f"  Cycle: {c}")
    # Check edge types in cycle
    for i in range(len(c)):
        u, v = c[i], c[(i + 1) % len(c)]
        edata = digraph.get_edge_data(u, v)
        if edata:
            for k, d in edata.items():
                print(
                    f"    edge {u}->{v}: type={d.get('type', '?')}, is_closed={d.get('is_closed', '?')}"
                )

if not cycles:
    print("Graph is radial! Running LinDistFlow...")
    from gdm_flow.lindistflow import solve_lindistflow

    result = solve_lindistflow(system)
    print(f"Success: {result.success}, message: {result.message}")
    print(f"Source P: {sum(result.p_net_w.values()) / 1e6:.2f} MW")
