# MCP Server Sync Tool

This Python script synchronizes MCP (Model Context Protocol) server configurations from a source JSON configuration file to the configuration files of various development tools. The tool only adds new servers or updates existing ones - it never removes servers that exist in your target configs but not in the source.

## Purpose

The goal of this tool is to maintain a single source of truth for MCP server definitions and ensure that development environments like Claude Code, Gemini CLI, VS Code GitHub Copilot, and OpenAI Codex CLI are all using the same, up-to-date configurations.

## Installation and Usage

### Quick Start with uvx (Recommended)

Run directly from GitHub without installation. You can use an existing compatible configuration file (like `.claude.json` or `.gemini/settings.json`) or copy the `sample.json` as a starting point.

```bash
uvx --from git+https://github.com/ejfn/mcp-sync mcp-sync -c /path/to/your-config.json
```

If you use a config file that is also a sync target (e.g., `~/.claude.json`), the tool will skip syncing to that target to avoid overwriting your source.

### Traditional Installation

```bash
# Install the package
pip install git+https://github.com/ejfn/mcp-sync

# Run the tool
mcp-sync -c /path/to/your-config.json
```

### Local Development

```bash
# Clone the repository
git clone https://github.com/ejfn/mcp-sync.git
cd mcp-sync

# Run the script directly
python3 mcp_sync.py -c sample.json
```

## Configuration File

The tool requires a JSON configuration file that defines your MCP servers. Use the included `sample.json` as a template:

```json
{
  "mcpServers": {
    "memory": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory@latest"],
      "env": {}
    },
    "your-custom-server": {
      "type": "stdio", 
      "command": "your-command",
      "args": ["arg1", "arg2"],
      "env": {
        "API_KEY": "your-api-key"
      }
    }
  }
}
```

## How It Works

The script reads server definitions from your source configuration file and adds or updates them in each supported tool's config file. It preserves any existing servers in your target configs that aren't in the source file.

### Process Overview

1. **Read Configuration**: Loads your MCP server definitions from the specified JSON file
2. **Find Target Tools**: Locates configuration files for all supported development tools
3. **Create Backups**: Backs up existing files (e.g., `~/.claude.json` → `~/.claude.json.backup`)
4. **Add/Update Servers**: 
   - Adds new servers from the source that don't exist in the target
   - Updates existing servers if their configuration has changed
   - Preserves any servers in the target that aren't in the source

### Key Mapping Architecture

The tool uses a centralized configuration system where each tool has:
- **Path**: Location of the tool's configuration file
- **Format**: Either "json" or "toml" 
- **Key**: The top-level key where MCP servers are stored
- **Key Mappings**: Explicit mapping of source keys to target keys

This ensures consistent and predictable transformations across all tools.

### Environment Variables Support

The sync tool supports environment variables in your configuration. Environment variables in the `env` object will be properly synced to all supported tools using their respective formats.

## Command Line Options

```bash
mcp-sync -c <config-file>
mcp-sync --config <config-file>
```

**Options:**
- `-c, --config`: Path to your MCP servers JSON configuration file (required)
- `-h, --help`: Show help message

**Examples:**
```bash
# Use a config file in your home directory
mcp-sync -c ~/mcp-config.json

# Use an existing tool config as the source (will skip syncing to itself)
mcp-sync -c ~/.claude.json

# Use the sample config (after copying/customizing it)
mcp-sync -c sample.json
```

## Extending the Tool

The script is designed to be easily extensible. To add support for a new tool or modify an existing one, simply update the `TOOL_CONFIGS` dictionary at the top of the `mcp_sync.py` file.

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
