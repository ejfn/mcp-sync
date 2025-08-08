# MCP Server Sync Tool

This Python script synchronizes MCP (Model Context Protocol) server configurations from a central `mcp-servers.json` file to the configuration files of various development tools.

## Purpose

The goal of this tool is to maintain a single source of truth for MCP server definitions and ensure that development environments like Claude Code, Gemini CLI, VS Code GitHub Copilot, and OpenAI Codex CLI are all using the same, up-to-date configurations.

## How It Works

The script reads the server definitions from `mcp-servers.json` located in the same directory. For each supported tool, it uses explicit key mappings to transform the data into the correct format and then updates the respective configuration file.

### Key Mapping Architecture

The tool uses a centralized configuration system where each tool has:
- **Path**: Location of the tool's configuration file
- **Format**: Either "json" or "toml" 
- **Key**: The top-level key where MCP servers are stored
- **Key Mappings**: Explicit mapping of source keys to target keys

This ensures consistent and predictable transformations across all tools.

### Environment Variables Support

The sync tool supports environment variables in the source configuration. See the included `mcp-servers.json` file for examples of MCP server configurations with environment variable support.

The environment variables will be properly synced to all supported tools using their respective formats.

## Usage

To run the synchronization process:

```bash
python3 mcp-sync.py
```

The script will automatically:
1.  Locate the source `mcp-servers.json`.
2.  Find the destination configuration files for all supported tools.
3.  Create a backup of each destination file (e.g., `~/.claude.json` will be backed up to `~/.claude.json.backup`).
4.  Update the `mcpServers` (or equivalent) key in each destination file with the new configuration.

## Extending the Tool

The script is designed to be easily extensible. To add support for a new tool or modify an existing one, simply update the `TOOL_CONFIGS` dictionary at the top of the `mcp-sync.py` file.

Each entry in the dictionary requires:
- `display_name`: Human-readable name for the tool
- `path`: The absolute `Path` to the tool's configuration file
- `key`: The top-level key where the server configurations should be stored (e.g., `"mcpServers"` or `"servers"`)
- `format`: Either `"json"` or `"toml"` to specify the file format
- `key_mappings`: A dictionary mapping source keys to target keys for that specific tool

Example configuration:
```python
"new_tool": {
    "display_name": "New MCP Tool",
    "path": HOME_DIR / '.newtool' / 'config.json',
    "key": "mcpServers",
    "format": "json",
    "key_mappings": {
        "type": "type",
        "command": "executable", 
        "args": "arguments",
        "env": "environment"
    }
}
```

The tool uses normalized transformation functions:
- **JSON tools**: Use `transform_json_format()` with explicit key mappings
- **TOML tools**: Use `transform_for_codex()` with explicit key mappings

This architecture ensures that each tool's specific formatting requirements are met while keeping the core logic clean and maintainable.

## Supported Tools

The sync tool currently supports:

- **Claude Code** (`~/.claude.json`) - Uses `mcpServers` key
- **Gemini CLI** (`~/.gemini/settings.json`) - Uses `mcpServers` key  
- **VS Code GitHub Copilot** (`~/.config/Code/User/mcp.json`) - Uses `servers` key
- **VS Code GitHub Copilot (WSL)** (`~/.vscode-server/data/User/mcp.json`) - Uses `servers` key
- **OpenAI Codex CLI** (`~/.codex/config.toml`) - Uses `mcp_servers` key in TOML format

All tools support environment variables through the `env` object in the source configuration.
