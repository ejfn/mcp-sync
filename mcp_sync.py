import argparse
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
    Reads a destination JSON file, creates a backup, and adds/updates MCP servers from transformed_data.
    Does NOT remove existing servers that aren't in the source.
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

    # Add new servers or update existing ones, don't remove any
    existing_servers = settings.get(config_key, {})
    added_count = 0
    updated_count = 0
    
    for name, config in transformed_data.items():
        if name not in existing_servers:
            existing_servers[name] = config
            added_count += 1
        else:
            # Only count as update if the config actually changed
            if existing_servers[name] != config:
                existing_servers[name] = config
                updated_count += 1
    
    settings[config_key] = existing_servers
    
    if added_count > 0 and updated_count > 0:
        print(f"    Added {added_count} new server(s), updated {updated_count} existing server(s)")
    elif added_count > 0:
        print(f"    Added {added_count} new server(s)")
    elif updated_count > 0:
        print(f"    Updated {updated_count} existing server(s)")
    else:
        print(f"    No changes needed")

    with open(dest_path, 'w') as f:
        json.dump(settings, f, indent=2)


def update_toml_config_file(dest_path, transformed_data):
    """
    Updates a TOML config file with MCP server data.
    Adds new servers or updates existing ones; does NOT remove existing servers.
    """
    import re
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    existing_content = ""
    if dest_path.exists():
        backup_path = dest_path.with_suffix(dest_path.suffix + '.backup')
        shutil.copy2(dest_path, backup_path)
        
        with open(dest_path, 'r') as f:
            existing_content = f.read()

    # Parse existing server names and their content
    existing_servers = {}
    server_pattern = r'\[mcp_servers\.([^\]]+)\](.*?)(?=\[mcp_servers\.|$)'
    matches = re.findall(server_pattern, existing_content, re.DOTALL)
    for server_name, content in matches:
        existing_servers[server_name] = f"[mcp_servers.{server_name}]{content}".strip()
    
    # Process new/updated servers
    new_blocks = []
    updated_blocks = []
    
    for block in transformed_data.split('\n\n'):
        if block.strip():
            match = re.match(r'\[mcp_servers\.([^\]]+)\]', block.strip())
            if match:
                server_name = match.group(1)
                if server_name in existing_servers:
                    # Only update if the content actually changed
                    if existing_servers[server_name] != block.strip():
                        updated_blocks.append((server_name, block.strip()))
                else:
                    # Add new server
                    new_blocks.append(block.strip())
    
    # Rebuild content with updates
    if new_blocks or updated_blocks:
        # Remove old server sections and rebuild
        lines = existing_content.split('\n')
        filtered_lines = []
        skip_section = False
        current_server = None
        
        for line in lines:
            stripped = line.strip()
            server_match = re.match(r'\[mcp_servers\.([^\]]+)\]', stripped)
            if server_match:
                current_server = server_match.group(1)
                if current_server in [name for name, _ in updated_blocks]:
                    skip_section = True
                    continue
                else:
                    skip_section = False
            elif stripped.startswith('[') and not stripped.startswith('[mcp_servers.'):
                skip_section = False
                current_server = None
            
            if not skip_section:
                filtered_lines.append(line)
        
        # Write updated content
        with open(dest_path, 'w') as f:
            f.write('\n'.join(filtered_lines).rstrip())
            
            # Add updated servers
            if updated_blocks:
                for server_name, block in updated_blocks:
                    f.write('\n\n' + block)
            
            # Add new servers
            if new_blocks:
                for block in new_blocks:
                    f.write('\n\n' + block)
        
        added_count = len(new_blocks)
        updated_count = len(updated_blocks)
        
        if added_count > 0 and updated_count > 0:
            print(f"    Added {added_count} new server(s), updated {updated_count} existing server(s)")
        elif added_count > 0:
            print(f"    Added {added_count} new server(s)")
        elif updated_count > 0:
            print(f"    Updated {updated_count} existing server(s)")
    else:
        print(f"    No changes needed")


def sync_mcp_configs(config_file_path):
    """
    Syncs MCP server configurations by transforming the source data
    for each specific tool's format using a centralized configuration.
    
    Args:
        config_file_path (str or Path): Path to the MCP servers JSON config file.
    """
    source_path = Path(config_file_path).expanduser().resolve()

    try:
        with open(source_path, 'r') as f:
            source_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading source file '{source_path}': {e}")
        return

    source_servers = source_data.get("mcpServers")
    if not source_servers:
        source_servers = source_data.get("servers")
        if not source_servers:
            print(f"Error: Neither 'mcpServers' nor 'servers' key found or empty in '{source_path}'")
            return

    server_names = ", ".join(source_servers.keys())
    print(f"Found servers: {server_names}")
    print("Syncing MCP server configurations...")
    
    for config in TOOL_CONFIGS.values():
        target_path = config['path'].expanduser().resolve()
        if target_path == source_path:
            print(f" -> Skipping sync for {config['display_name']} (source config)")
            continue
        if target_path.exists():
            display_name = config['display_name']
            print(f" -> Syncing settings for {display_name}")
            
            # Use normalized transformation based on format
            if config['format'] == 'toml':
                transformed_data = transform_for_codex(source_servers, config['key_mappings'])
                update_toml_config_file(target_path, transformed_data)
            else:  # JSON format
                transformed_data = transform_json_format(source_servers, config['key_mappings'])
                update_config_file(target_path, transformed_data, config['key'])
    
    print("Sync complete.")

def main():
    """Entry point for the mcp-sync command."""
    parser = argparse.ArgumentParser(
        description="Sync MCP server configurations across different tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -c /path/to/config.json   # Use config file
  %(prog)s --config ~/my-mcp.json    # Use config file (long form)
        """
    )
    parser.add_argument(
        '-c', '--config',
        type=str,
        required=True,
        help='Path to the MCP servers JSON configuration file (required)'
    )
    
    args = parser.parse_args()
    
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file '{config_path}' does not exist.")
        return 1
    if not config_path.is_file():
        print(f"Error: '{config_path}' is not a file.")
        return 1
    
    print(f"Using config file: {config_path}")
    sync_mcp_configs(config_path)


if __name__ == "__main__":
    main()
