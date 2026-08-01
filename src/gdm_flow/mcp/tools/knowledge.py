"""Documentation and API knowledge tools for the GDM-Flow MCP server."""

from __future__ import annotations

import json

from mcp.server import MCPServer

from gdm_flow.mcp.common import (
    DOCS_ROOT,
    _api_reference_for_symbol,
    _extract_snippet,
    _iter_doc_files,
    _list_public_api_symbols,
    _read_text_file,
)


def register(mcp: MCPServer) -> None:
    """Register documentation and API knowledge tools."""

    @mcp.tool()
    def list_documentation() -> str:
        """List available GDM-Flow documentation files (docs/*.md, docs/*.ipynb).

        Returns:
            JSON payload with the docs root, file count, and relative paths.
        """
        files = _iter_doc_files()
        rel_paths = [str(path.relative_to(DOCS_ROOT)) for path in files]
        return json.dumps(
            {
                "docs_root": str(DOCS_ROOT),
                "count": len(rel_paths),
                "files": rel_paths,
            },
            indent=2,
            default=str,
        )

    @mcp.tool()
    def search_documentation(query: str, max_results: int = 5) -> str:
        """Search GDM-Flow documentation and return relevant snippets.

        Args:
            query: Search term or phrase.
            max_results: Maximum number of matches to return.

        Returns:
            JSON payload with matching document paths and snippets.
        """
        query = query.strip()
        max_results = max(1, max_results)

        matches: list[dict[str, str]] = []
        for doc_path in _iter_doc_files():
            text = _read_text_file(doc_path)
            snippet = _extract_snippet(text, query)
            if not snippet:
                continue
            matches.append(
                {
                    "path": str(doc_path.relative_to(DOCS_ROOT)),
                    "snippet": snippet,
                }
            )
            if len(matches) >= max_results:
                break

        return json.dumps(
            {
                "query": query,
                "count": len(matches),
                "results": matches,
            },
            indent=2,
            default=str,
        )

    @mcp.tool()
    def get_documentation_page(
        doc_path: str,
        start_line: int = 1,
        max_lines: int = 160,
    ) -> str:
        """Read a specific documentation page by relative path from docs/.

        Args:
            doc_path: Path relative to docs/ (e.g., solvers/ac_opf.md).
            start_line: 1-based start line.
            max_lines: Maximum number of lines to return.

        Returns:
            JSON payload with the resolved path, line range, and page content.
        """
        doc_path = doc_path.strip()
        start_line = max(1, start_line)
        max_lines = max(1, max_lines)

        full_path = (DOCS_ROOT / doc_path).resolve()
        docs_root_resolved = DOCS_ROOT.resolve()
        if not str(full_path).startswith(str(docs_root_resolved)):
            raise ValueError("doc_path must stay within docs/ directory")
        if not full_path.exists() or not full_path.is_file():
            raise FileNotFoundError(f"Documentation file not found: {doc_path}")

        lines = _read_text_file(full_path).splitlines()
        start_idx = start_line - 1
        end_idx = min(len(lines), start_idx + max_lines)

        return json.dumps(
            {
                "path": str(full_path.relative_to(docs_root_resolved)),
                "start_line": start_line,
                "end_line": end_idx,
                "content": "\n".join(lines[start_idx:end_idx]),
            },
            indent=2,
            default=str,
        )

    @mcp.tool()
    def list_api_symbols() -> str:
        """List public API symbols exposed by gdm_flow.__all__.

        Returns:
            JSON payload with the symbol count and sorted symbol names.
        """
        symbols = _list_public_api_symbols()
        return json.dumps(
            {
                "count": len(symbols),
                "symbols": symbols,
            },
            indent=2,
            default=str,
        )

    @mcp.tool()
    def get_api_reference(symbol_name: str) -> str:
        """Get module, signature, and docstring for a public GDM-Flow API symbol.

        Args:
            symbol_name: Public symbol name (e.g., solve_dc_opf_from_components).

        Returns:
            JSON payload with the symbol name, module, signature, and docstring.
        """
        symbol_name = symbol_name.strip()
        return json.dumps(
            _api_reference_for_symbol(symbol_name),
            indent=2,
            default=str,
        )
