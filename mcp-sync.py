import json
import shutil
from pathlib import Path

# --- Centralized Tool Configuration ---

HOME_DIR = Path.home()
TOOL_CONFIGS = {
    "claude_code": {
        "display_name": "Claude Code",
        "path": HOME_DIR / '.claude.json',
        "key": "mcpServers",
        "format": "json",
        "key_mappings": {
            "type": "type",
            "command": "command", 
            "args": "args",
            "env": "env"
        }
    },
    "gemini_cli": {
        "display_name": "Gemini CLI",
        "path": HOME_DIR / '.gemini' / 'settings.json',
        "key": "mcpServers",
        "format": "json",
        "key_mappings": {
            "type": "type",
            "command": "command",
            "args": "args", 
            "env": "env"
        }
    },
    "vscode": {
        "display_name": "GitHub Copilot in VS Code",
        "path": HOME_DIR / '.config' / 'Code' / 'User' / 'mcp.json',
        "key": "servers",
        "format": "json",
        "key_mappings": {
            "type": "type",
            "command": "command",
            "args": "args",
            "env": "env"
        }
    },
    "vscode_wsl": {
        "display_name": "GitHub Copilot in VS Code (WSL)",
        "path": HOME_DIR / '.vscode-server' / 'data' / 'User' / 'mcp.json',
        "key": "servers",
        "format": "json",
        "key_mappings": {
            "type": "type",
            "command": "command",
            "args": "args",
            "env": "env"
        }
    },
    "codex": {
        "display_name": "OpenAI Codex CLI",
        "path": HOME_DIR / '.codex' / 'config.toml',
        "key": "mcp_servers",
        "format": "toml",
        "key_mappings": {
            "type": "type",
            "command": "command",
            "args": "args",
            "env": "env"
        }
    }
}

# --- Transformation Functions ---

def transform_json_format(source_servers, key_mappings):
    """
    Normalized transformation function for JSON-based tools.
    Uses explicit key mapping to ensure compatibility.
    """
    transformed_servers = {}
    
    for name, config in source_servers.items():
        server_config = {}
        # Map known keys
        for source_key, target_key in key_mappings.items():
            if source_key in config:
                server_config[target_key] = config[source_key]
                
        transformed_servers[name] = server_config
    return transformed_servers

def transform_for_codex(source_servers, key_mappings):
    """
    Transforms the source MCP server data for OpenAI Codex CLI's TOML format.
    Each server becomes a [mcp_servers.{name}] section with all available keys.
    Uses explicit key mapping to ensure compatibility.
    Returns a TOML string to be written to the config file.
    """
    def escape_toml_string(value):
        """Escape special characters for TOML string values."""
        if isinstance(value, str):
            return value.replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
        return str(value)
    
    def format_toml_value(value):
        """Format a Python value as a TOML value."""
        if isinstance(value, str):
            return f'"{escape_toml_string(value)}"'
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, list):
            formatted_items = [format_toml_value(item) for item in value]
            return f"[{', '.join(formatted_items)}]"
        elif isinstance(value, dict):
            formatted_items = [f'"{k}" = {format_toml_value(v)}' for k, v in value.items()]
            return f"{{ {', '.join(formatted_items)} }}"
        else:
            return f'"{escape_toml_string(str(value))}"'
    
    toml_lines = []
    
    for name, config in source_servers.items():
        toml_lines.append(f"[mcp_servers.{name}]")
        
        # Map known keys
        for source_key, target_key in key_mappings.items():
            if source_key in config:
                toml_lines.append(f"{target_key} = {format_toml_value(config[source_key])}")
        
        toml_lines.append("")  # Empty line between servers
    
    return "\n".join(toml_lines)


# --- Core Sync Logic ---

def update_config_file(dest_path, transformed_data, config_key):
    """
    Reads a destination JSON file, creates a backup, and updates the
    specified key with the transformed MCP data. This function is silent on success.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    settings = {}
    if dest_path.exists():
        backup_path = dest_path.with_suffix(dest_path.suffix + '.backup')
        shutil.copy2(dest_path, backup_path)

        if dest_path.stat().st_size > 0:
            with open(dest_path, 'r') as f:
                try:
                    settings = json.load(f)
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from {dest_path}. Its content will be overwritten.")
                    settings = {}

    settings[config_key] = transformed_data

    with open(dest_path, 'w') as f:
        json.dump(settings, f, indent=2)


def update_toml_config_file(dest_path, transformed_data):
    """
    Updates a TOML config file with MCP server data.
    For Codex CLI, this merges the MCP servers into the existing config.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    existing_content = ""
    if dest_path.exists():
        backup_path = dest_path.with_suffix(dest_path.suffix + '.backup')
        shutil.copy2(dest_path, backup_path)
        
        with open(dest_path, 'r') as f:
            existing_content = f.read()

    # Remove existing [mcp_servers.*] sections
    lines = existing_content.split('\n')
    filtered_lines = []
    skip_section = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[mcp_servers.'):
            skip_section = True
            continue
        elif stripped.startswith('[') and not stripped.startswith('[mcp_servers.'):
            skip_section = False
        
        if not skip_section:
            filtered_lines.append(line)

    # Clean up empty lines at the end
    while filtered_lines and not filtered_lines[-1].strip():
        filtered_lines.pop()

    # Add the new MCP servers section
    if filtered_lines:
        filtered_lines.append("")  # Add separator
    filtered_lines.append("# MCP Servers Configuration")
    filtered_lines.extend(transformed_data.split('\n'))

    with open(dest_path, 'w') as f:
        f.write('\n'.join(filtered_lines))


def sync_mcp_configs():
    """
    Syncs MCP server configurations by transforming the source data
    for each specific tool's format using a centralized configuration.
    """
    source_path = Path(__file__).parent / 'mcp-servers.json'

    try:
        with open(source_path, 'r') as f:
            source_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading source file {source_path}: {e}")
        return

    source_servers = source_data.get("mcpServers")
    if not source_servers:
        print(f"Error: 'mcpServers' key not found or empty in {source_path}")
        return

    server_names = ", ".join(source_servers.keys())
    print(f"Found servers: {server_names}")
    print("Syncing MCP server configurations...")
    
    for config in TOOL_CONFIGS.values():
        if config['path'].exists():
            display_name = config['display_name']
            print(f" -> Syncing settings for {display_name}")
            
            # Use normalized transformation based on format
            if config['format'] == 'toml':
                transformed_data = transform_for_codex(source_servers, config['key_mappings'])
                update_toml_config_file(config['path'], transformed_data)
            else:  # JSON format
                transformed_data = transform_json_format(source_servers, config['key_mappings'])
                update_config_file(config['path'], transformed_data, config['key'])
    
    print("Sync complete.")

def main():
    """Entry point for the mcp-sync command."""
    sync_mcp_configs()


if __name__ == "__main__":
    main()
