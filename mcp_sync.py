import argparse
import json
import shutil
import re
import sys
from pathlib import Path

# --- Centralized Tool Configuration ---

HOME_DIR = Path.home()
TOOL_CONFIGS = {
    "claude_code": {
        "display_name": "Claude Code",
        "path": HOME_DIR / '.claude.json',
        "key": "mcpServers",
        "format": "json"
    },
    "gemini_cli": {
        "display_name": "Gemini CLI",
        "path": HOME_DIR / '.gemini' / 'settings.json',
        "key": "mcpServers",
        "format": "json"
    },
    "vscode": {
        "display_name": "GitHub Copilot in VS Code",
        "path": HOME_DIR / '.config' / 'Code' / 'User' / 'mcp.json',
        "key": "servers",
        "format": "json"
    },
    "vscode_wsl": {
        "display_name": "GitHub Copilot in VS Code (WSL)",
        "path": HOME_DIR / '.vscode-server' / 'data' / 'User' / 'mcp.json',
        "key": "servers",
        "format": "json"
    },
    "codex": {
        "display_name": "OpenAI Codex CLI",
        "path": HOME_DIR / '.codex' / 'config.toml',
        "key": "mcp_servers",
        "format": "toml"
    }
}

# --- Transformation Functions ---

def transform_json_format(source_servers, tool_name=None):
    """
    Transformation function for JSON-based tools.
    Special handling for Gemini CLI: when type == 'http', 'url' becomes 'httpUrl'.
    """
    transformed_servers = {}
    for name, config in source_servers.items():
        server_config = {}
        # Copy all fields as-is with special handling
        for key, value in config.items():
            # Special handling for Gemini CLI: when type == 'http', 'url' becomes 'httpUrl'
            if tool_name == "gemini_cli" and config.get("type") == "http" and key == "url":
                server_config["httpUrl"] = value
            else:
                server_config[key] = value
            
        transformed_servers[name] = server_config
    return transformed_servers

def transform_for_codex(source_servers):
    """
    Transforms the source MCP server data for OpenAI Codex CLI's TOML format.
    Each server becomes a [mcp_servers.{name}] section with all available keys.
    Returns a TOML string to be written to the config file.
    Skips any server where type is not 'stdio'.
    """
    def escape_toml_string(value):
        """Escape special characters for TOML string values."""
        if isinstance(value, str):
            return value.replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
        return str(value)
    
    def quote_toml_key(key: str) -> str:
        """Quote and escape a TOML key (for table headers)."""
        return f'"{escape_toml_string(str(key))}"'
    
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
        # Skip if type is not 'stdio'
        if config.get('type') != 'stdio':
            continue
        # Always quote server names to avoid TOML bare-key edge cases
        toml_lines.append(f"[mcp_servers.{quote_toml_key(name)}]")
        
        # Copy all keys as-is
        for key, value in config.items():
            toml_lines.append(f"{key} = {format_toml_value(value)}")
        
        toml_lines.append("")  # Empty line between servers
    
    return "\n".join(toml_lines)


# --- Core Sync Logic ---

def update_config_file(dest_path, transformed_data, config_key, prune=False):
    """
    Reads a destination JSON file, creates a backup, and adds/updates MCP servers from transformed_data.
    If prune=True, removes servers not present in the source.
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
    existing_servers = settings.get(config_key, {})
    added_count = 0
    updated_count = 0
    removed_count = 0
    # Add/update servers
    for name, config in transformed_data.items():
        if name not in existing_servers:
            existing_servers[name] = config
            added_count += 1
        else:
            if existing_servers[name] != config:
                existing_servers[name] = config
                updated_count += 1
    # Remove servers not present in source if prune is True
    if prune:
        to_remove = [name for name in existing_servers if name not in transformed_data]
        for name in to_remove:
            del existing_servers[name]
            removed_count += 1
    settings[config_key] = existing_servers
    msg = []
    if added_count > 0:
        msg.append(f"Added {added_count} new server(s)")
    if updated_count > 0:
        msg.append(f"Updated {updated_count} existing server(s)")
    if removed_count > 0:
        msg.append(f"Removed {removed_count} server(s)")
    if msg:
        print("    " + ", ".join(msg))
    else:
        print(f"    No changes needed")
    with open(dest_path, 'w') as f:
        json.dump(settings, f, indent=2)


def update_toml_config_file(dest_path, transformed_data, prune=False):
    """
    Updates a TOML config file with MCP server data.
    Adds new servers or updates existing ones; removes servers not present in source if prune=True.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    existing_content = ""
    if dest_path.exists():
        backup_path = dest_path.with_suffix(dest_path.suffix + '.backup')
        shutil.copy2(dest_path, backup_path)
        with open(dest_path, 'r') as f:
            existing_content = f.read()
    # Parse existing server names and their content
    existing_servers = {}
    server_pattern = r'\[mcp_servers\.(?:"([^"]+)"|([^\]]+))\](.*?)(?=\[mcp_servers\.|$)'
    matches = re.findall(server_pattern, existing_content, re.DOTALL)
    for qname, uname, content in matches:
        server_name = qname if qname else uname
        header = f'[mcp_servers."{server_name}"]'
        existing_servers[server_name] = f"{header}{content}".strip()
    # Process new/updated servers
    new_blocks = []
    updated_blocks = []
    source_server_names = set()
    for block in transformed_data.split('\n\n'):
        if block.strip():
            match = re.match(r'\[mcp_servers\.(?:"([^"]+)"|([^\]]+))\]', block.strip())
            if match:
                server_name = match.group(1) if match.group(1) else match.group(2)
                source_server_names.add(server_name)
                if server_name in existing_servers:
                    if existing_servers[server_name] != block.strip():
                        updated_blocks.append((server_name, block.strip()))
                else:
                    new_blocks.append(block.strip())
    # Remove servers not present in source if prune is True
    removed_count = 0
    if prune:
        to_remove = [name for name in existing_servers if name not in source_server_names]
        for name in to_remove:
            del existing_servers[name]
            removed_count += 1
    # Rebuild content with updates
    lines = existing_content.split('\n')
    filtered_lines = []
    skip_section = False
    current_server = None
    for line in lines:
        stripped = line.strip()
        server_match = re.match(r'\[mcp_servers\.(?:"([^"]+)"|([^\]]+))\]', stripped)
        if server_match:
            current_server = server_match.group(1) if server_match.group(1) else server_match.group(2)
            if current_server in [name for name, _ in updated_blocks]:
                skip_section = True
                continue
            elif prune and current_server not in source_server_names:
                skip_section = True
                continue
            else:
                skip_section = False
        elif stripped.startswith('[') and not stripped.startswith('[mcp_servers.'):
            skip_section = False
            current_server = None
        if not skip_section:
            filtered_lines.append(line)
    with open(dest_path, 'w') as f:
        f.write('\n'.join(filtered_lines).rstrip())
        if updated_blocks:
            for server_name, block in updated_blocks:
                f.write('\n\n' + block)
        if new_blocks:
            for block in new_blocks:
                f.write('\n\n' + block)
    added_count = len(new_blocks)
    updated_count = len(updated_blocks)
    msg = []
    if added_count > 0:
        msg.append(f"Added {added_count} new server(s)")
    if updated_count > 0:
        msg.append(f"Updated {updated_count} existing server(s)")
    if removed_count > 0:
        msg.append(f"Removed {removed_count} server(s)")
    if msg:
        print("    " + ", ".join(msg))
    else:
        print(f"    No changes needed")


def sync_mcp_configs(config_file_path, prune=False):
    """
    Syncs MCP server configurations by transforming the source data
    for each specific tool's format using a centralized configuration.
    Optionally removes servers not present in the source if prune=True.
    Args:
        config_file_path (str or Path): Path to the MCP servers JSON config file.
        prune (bool): If True, remove servers not present in the source.
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
        print(f"Error: 'mcpServers' key not found or empty in '{source_path}'")
        return
    # Validate source server structure
    if not isinstance(source_servers, dict):
        print(f"Error: Source servers must be an object/dict; got {type(source_servers).__name__} from '{source_path}'")
        return

    server_names = ", ".join(source_servers.keys())
    print(f"Found servers: {server_names}")
    print("Syncing MCP server configurations...")
    
    for tool_name, config in TOOL_CONFIGS.items():
        target_path = config['path'].expanduser().resolve()
        display_name = config['display_name']
        if target_path == source_path:
            print(f" -> Skipping sync for {display_name} (source config)")
            continue
        if not target_path.exists():
            # Silently skip when target config does not exist
            continue
        print(f" -> Syncing settings for {display_name}")
        # Use transformation based on format
        if config['format'] == 'toml':
            transformed_data = transform_for_codex(source_servers)
            update_toml_config_file(target_path, transformed_data, prune=prune)
        else:  # JSON format
            transformed_data = transform_json_format(source_servers, tool_name=tool_name)
            update_config_file(target_path, transformed_data, config['key'], prune=prune)
    
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
  %(prog)s -c config.json --prune    # Remove servers not present in source
        """
    )
    parser.add_argument(
        '-c', '--config',
        type=str,
        required=True,
        help='Path to the MCP servers JSON configuration file (required)'
    )
    parser.add_argument(
        '--prune',
        action='store_true',
        help='Remove MCP servers from target configs that are not present in the source config'
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
    sync_mcp_configs(config_path, prune=args.prune)

if __name__ == "__main__":
    sys.exit(main())
