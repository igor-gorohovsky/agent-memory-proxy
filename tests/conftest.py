import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_config_data() -> dict:
    """Sample configuration data for testing"""
    return {
        "respect_gitignore": True,
        "truth_memory_file": "AGENT.md",
        "agents": ["claude", "gemini", "cursor"]
    }


@pytest.fixture
def sample_agent_content() -> str:
    """Sample content for agent memory files"""
    return """# Agent Memory

This is a test agent memory file.

## Rules
- Test rule 1
- Test rule 2

## Context
Some test context here.
"""
