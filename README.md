# MCP Server Sync Tool

This Python script synchronizes user-scoped MCP (Model Context Protocol) server configurations from a source JSON configuration file to the configuration files of various development tools. The tool only syncs user-scoped MCP servers (from the `mcpServers` key) and does not modify workspace-scoped configurations. It only adds new servers or updates existing ones - it never removes servers that exist in your target configs but not in the source.

## Installation and Usage

### Quick Start with uvx (Recommended)

Run directly from GitHub without installation. Use your `~/.claude.json` or any config file in Claude-compatible format (with a top-level `mcpServers` key) as your source.

```bash
# Using your Claude config as the source
uvx --from git+https://github.com/ejfn/mcp-sync mcp-sync -c ~/.claude.json

# Using your own config file as the source
uvx --from git+https://github.com/ejfn/mcp-sync mcp-sync -c /path/to/your-config.json
```

### Traditional Installation

```bash
# Install the package
pip install git+https://github.com/ejfn/mcp-sync

# Run the tool
mcp-sync -c /path/to/your-config.json
```

## Command Line Options

The sync tool provides the following options:

- `-c, --config <file>`: Path to your MCP servers JSON configuration file (required)
- `--prune`: Remove MCP servers from target configs that are not present in the source config

**Examples:**

```bash
# Sync and preserve extra servers in targets
mcp-sync -c ~/.claude.json

# Sync and remove servers from targets that are not present in your source config
mcp-sync -c ~/.claude.json --prune
```

## Configuration File

The tool requires a JSON configuration file that defines your user-scoped MCP servers. You can use any self-managed config file, as long as it contains the `mcpServers` key (user-scoped). Workspace-scoped configurations are ignored. Here's an example configuration:

```json
{
  "mcpServers": {
    "memory": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory@latest"],
      "env": {}
    },
    "context7-http": {
      "type": "http",
      "url": "https://mcp.context7.com/mcp"
    },
    "context7-sse": {
      "type": "sse",
      "url": "https://mcp.context7.com/sse"
    }
  }
}
```

## How It Works

The tool reads user-scoped MCP servers from your source config file (`mcpServers` key) and copies or updates them into each supported tool's config. Existing servers in the target configs that aren't in the source are preserved. Workspace-scoped servers are ignored.

### Process Overview

1. **Read Configuration**: Loads your user-scoped MCP server definitions from the `mcpServers` key in the specified JSON file
2. **Find Target Tools**: Locates configuration files for all supported development tools
3. **Create Backups**: Backs up existing files (e.g., `~/.claude.json` → `~/.claude.json.backup`)
4. **Add/Update Servers**: 
   - Adds new user-scoped servers from the source that don't exist in the target
   - Updates existing user-scoped servers if their configuration has changed
   - Preserves any servers in the target that aren't in the source
   - Does not modify workspace-scoped server configurations

Each supported tool has:
- **Path**: Location of the tool's configuration file
- **Format**: Either "json" or "toml"
- **Key**: The top-level key where MCP servers are stored

Fields are copied directly from the source config to each target, with minimal tool-specific adjustments (such as special handling for Gemini CLI HTTP URLs).

## Supported Tools

The sync tool currently supports these configurations for user-scoped MCP servers:

- **Claude Code** (`~/.claude.json`) - Uses `mcpServers` key
- **Gemini CLI** (`~/.gemini/settings.json`) - Uses `mcpServers` key  
- **VS Code GitHub Copilot** (`~/.config/Code/User/mcp.json`) - Uses `servers` key
- **VS Code GitHub Copilot (WSL)** (`~/.vscode-server/data/User/mcp.json`) - Uses `servers` key
- **OpenAI Codex CLI** (`~/.codex/config.toml`) - Uses `mcp_servers` key in TOML format (Codex only supports servers of type `stdio`)

All tools support environment variables through the `env` object in the source configuration. Only user-scoped MCP servers are synced - workspace-scoped configurations remain untouched.
