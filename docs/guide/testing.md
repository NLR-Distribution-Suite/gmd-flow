# Testing

This page collects the recommended local test commands and the CI workflow coverage.

## Local Test Commands

Run the full test suite:

```bash
pytest -v --tb=short
```

Run lint checks (same checks used in CI lint job):

```bash
pre-commit run --all-files
```

Run MCP server tests only:

```bash
pip install -e ".[mcp,optimization,dev]"
pytest -v --tb=short tests/test_mcp_server.py
```

## CI Workflow Coverage

GitHub Actions workflow: `.github/workflows/ci.yml`

- `test`: matrix test suite on Python `3.11`, `3.12`, and `3.13`
- `mcp-test`: MCP-specific tests (`tests/test_mcp_server.py`) with MCP dependencies installed
- `lint`: pre-commit checks on all files

This ensures MCP server behavior is validated in CI and not silently skipped due to missing optional dependencies.
