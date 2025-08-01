# Agent Development Rules

@README.md - See project overview, setup, and installation instructions

## Project Structure

```
agent-memory-proxy/
├── src/
│   ├── __init__.py
│   ├── main.py              # Core classes and entry point
│   ├── config.py            # Configuration handling
│   ├── constants.py         # Project constants
│   ├── file_ops.py          # File operations utilities
│   ├── sync.py              # Synchronization logic
│   └── watcher.py           # File watching implementation
├── scripts/
│   ├── install.sh           # Unix installation script
│   ├── install.bat          # Windows installation script
│   └── daemons/             # Service/daemon configurations
├── tests/
├── pyproject.toml           # uv/Python configuration
├── README.md                # User documentation
├── AGENT.md                 # This file - development context
├── .amp.yaml                # Project's own proxy config
└── .github/
    └── workflows/
        └── ci.yml           # CI/CD pipeline
```


## Development Guidelines

### Code Standards
- PEP 8 compliant, 79-character line limit
- Type hints required for all functions
- Use `typing` module for complex types
- Avoid using relative imports

### Commands
- Run tests: `uv run pytest tests`
- Run lint + type check + tests on all Python versions: `tox`
- Run specific Python versions (each includes lint + type check + tests): `tox -e py39,py310,py311,py312,py313`
- Run only linting: `tox -e lint` or `uv run ruff check src/`
- Run only type checking: `tox -e type-check` or `uv run basedpyright src/`
- **Important**: When running watcher for tests ALWAYS set small timeout: `timeout 3 uv run amp`

