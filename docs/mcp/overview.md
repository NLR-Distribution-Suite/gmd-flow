# MCP Overview

GDM-Flow includes an MCP (Model Context Protocol) server that exposes OPF and Y-bus workflows as callable tools for MCP-compatible clients.

## What It Provides

- Run solver workflows through structured tool calls
- Access Y-bus metadata for distribution models
- Export solver results to SQLite
- Search and read GDM-Flow documentation from MCP clients
- Inspect public GDM-Flow API symbols and docstrings

## Install

Install with MCP and optimization dependencies:

```bash
pip install -e ".[mcp,optimization]"
```

## Run the Server

```bash
gdm-flow-mcp-server
```

The server runs over stdio and is intended for MCP clients (for example, VS Code agent integrations) to start and manage.

## Tool Families

- Solver tools: run AC OPF, DC OPF, LinDistFlow, and cross-solver comparison
- Matrix tools: compute Y-bus metadata and optional preview values
- Export tools: persist selected solver outputs to SQLite
- Documentation tools: list/search/read docs and get API references

## model_ref Interoperability

All solver and export tools accept either:

- `system_path` (legacy)
- `model_ref` (registry-aware)

### model_ref shape

```json
{
	"model_id": "abc123def456",
	"version": 2
}
```

Or direct path-carrying references:

```json
{
	"stored_path": "/abs/path/to/system.json"
}
```

### Resolution order

1. `stored_path`
2. `path`
3. `source_path`
4. Registry lookup by `model_id` / `version`

Lookup uses `model_ref.registry_db` first, then `DIST_STACK_MODEL_REGISTRY_DB`.

### Example

```json
{
	"model_ref": {
		"model_id": "abc123def456",
		"version": 2
	},
	"db_path": "./opf_results.sqlite"
}
```

For complete tool details and parameters, see the MCP Tool Reference page.
