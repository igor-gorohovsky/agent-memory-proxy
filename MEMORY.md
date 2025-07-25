# Agent Memory Proxy

## Project Overview

Agent Memory Proxy is a Python-based file synchronization tool that solves the problem of maintaining consistent project context across multiple AI code agents (Claude, Gemini, Cursor, Copilot, etc.).
It watches for changes in a single source file (typically `MEMORY.md`) and automatically syncs it to various agent-specific formats.

### Problem Statement
- Different AI code agents use different file formats and locations for project context
- Developers need to manually maintain multiple files with the same information
- Keeping these files in sync is tedious and error-prone

### Solution
- Single source of truth: One `MEMORY.md` file
- Automatic synchronization via file watching
- Configurable mappings through YAML configuration
- Cross-platform support (Windows, macOS, Linux, WSL)

## Architecture

### Core Components

1. **MemoryProxyConfig** (`src/main.py`)
   - Loads and validates YAML configuration files
   - Manages mapping between source and target files

2. **MemorySyncHandler** (`src/main.py`)
   - Handles file system events using watchdog
   - Performs actual file synchronization
   - Prevents recursive syncing with a flag

3. **MemoryProxyWatcher** (`src/main.py`)
   - Main orchestrator class
   - Manages multiple directory watchers
   - Scans for configuration files

## File Structure

```
agent-memory-proxy/
├── src/
│   └── main.py
├── scripts/
│   ├── install.sh
│   └── install.bat
├── tests/
│   └── test_agent_memory_proxy.py
├── pyproject.toml                 # Poetry configuration and metadata
├── README.md                      # User documentation
├── MEMORY.md                      # This file - project context
├── .amp.yaml                      # Project's own proxy config
├── LICENSE                        # MIT License
├── .gitignore                     # Git ignore patterns
└── .github/
    └── workflows/
        └── ci.yml                 # CI/CD pipeline
```

## Code Conventions

### Python Style
- **PEP 8** compliant with 79-character line limit

### Type Hints
- All functions have type hints
- Use `typing` module for complex types
- Use None, list, dict, set, tuple and pipe ('|') instead of Union, Optional, List, Dict, Set, Tuple

## Testing Strategy


### Key Test Classes
1. `TestMemoryProxyConfig`: Configuration loading and validation
2. `TestMemorySyncHandler`: File synchronization logic
3. `TestMemoryProxyWatcher`: Main watcher functionality
4. `TestMainFunction`: Entry point and CLI argument handling
5. `TestIntegration`: End-to-end workflow tests

### Running Tests
```bash
# All tests
poetry run pytest tests

# Specific test
poetry run pytest tests/<specific_test_name.py>
```

## Platform-Specific Considerations

### Windows
- Service installation: Task Scheduler or NSSM
- File paths: Handle both forward and backslashes

### macOS
- Service installation: launchd

### Linux
- Service installation: systemd

### WSL
- No systemd by default
- Use Windows Task Scheduler or nohup
- Path translation between Windows and WSL

