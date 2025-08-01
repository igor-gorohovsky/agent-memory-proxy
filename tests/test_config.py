from pathlib import Path

import pytest
import yaml

from config import ConfigValidator, MemoryProxyConfig


class TestConfigValidator:
    """Tests for ConfigValidator focusing on behavior validation"""

    def test_validate_agents_list_with_valid_agents(self):
        agents = ["claude", "gemini", "cursor"]
        result = ConfigValidator.validate_agents_list(agents)
        assert result == ["claude", "gemini", "cursor"]

    def test_validate_agents_list_converts_to_lowercase(self):
        agents = ["Claude", "GEMINI", "CuRsOr"]
        result = ConfigValidator.validate_agents_list(agents)
        assert result == ["claude", "gemini", "cursor"]

    def test_validate_agents_list_rejects_non_list_input(self):
        with pytest.raises(ValueError, match="'agents' must be a list"):
            ConfigValidator.validate_agents_list("claude")

        with pytest.raises(ValueError, match="'agents' must be a list"):
            ConfigValidator.validate_agents_list({"claude": "CLAUDE.md"})

    def test_validate_agents_list_rejects_non_string_agents(self):
        with pytest.raises(ValueError, match="Agent name must be string"):
            ConfigValidator.validate_agents_list([123, "claude"])

        with pytest.raises(ValueError, match="Agent name must be string"):
            ConfigValidator.validate_agents_list([{"name": "claude"}])

    def test_validate_agents_list_rejects_unknown_agents(self):
        with pytest.raises(ValueError, match="Unknown agent 'unknown'"):
            ConfigValidator.validate_agents_list(["claude", "unknown"])

    def test_create_mappings_generates_correct_mappings(self):
        agents = ["claude", "gemini", "cursor"]
        truth_file = "AGENT.md"

        mappings = ConfigValidator.create_mappings(agents, truth_file)

        assert mappings == {
            "CLAUDE.md": "AGENT.md",
            "GEMINI.md": "AGENT.md",
            ".cursor/rules/project.mdc": "AGENT.md"
        }

    def test_create_mappings_with_custom_truth_file(self):
        agents = ["claude"]
        truth_file = "CUSTOM_MEMORY.md"

        mappings = ConfigValidator.create_mappings(agents, truth_file)

        assert mappings == {"CLAUDE.md": "CUSTOM_MEMORY.md"}


class TestMemoryProxyConfig:
    """Tests for MemoryProxyConfig focusing on configuration loading behavior"""

    def test_load_valid_config(self, temp_dir: Path, sample_config_data: dict):
        config_path = temp_dir / ".amp.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(sample_config_data, f)

        config = MemoryProxyConfig(config_path)

        assert config.respect_gitignore is True
        assert config.truth_memory_file == "AGENT.md"
        assert config.recursive is True
        assert len(config.mappings) == 3
        assert config.mappings["CLAUDE.md"] == "AGENT.md"
        assert config.mappings["GEMINI.md"] == "AGENT.md"
        assert config.mappings[".cursor/rules/project.mdc"] == "AGENT.md"

    def test_load_config_with_defaults(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        minimal_config = {"agents": ["claude"]}
        with open(config_path, 'w') as f:
            yaml.dump(minimal_config, f)

        config = MemoryProxyConfig(config_path)

        assert config.respect_gitignore is True  # default
        assert config.truth_memory_file == "AGENT.md"  # default
        assert config.mappings == {"CLAUDE.md": "AGENT.md"}

    def test_load_config_with_custom_values(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        custom_config = {
            "agents": ["gemini"],
            "respect_gitignore": False,
            "truth_memory_file": "PROJECT_RULES.md"
        }
        with open(config_path, 'w') as f:
            yaml.dump(custom_config, f)

        config = MemoryProxyConfig(config_path)

        assert config.respect_gitignore is False
        assert config.truth_memory_file == "PROJECT_RULES.md"
        assert config.mappings == {"GEMINI.md": "PROJECT_RULES.md"}

    def test_config_missing_agents_section(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        invalid_config = {"respect_gitignore": True}
        with open(config_path, 'w') as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(ValueError, match="missing 'agents' section"):
            MemoryProxyConfig(config_path)

    def test_config_with_empty_file(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_path.touch()

        with pytest.raises(ValueError):
            MemoryProxyConfig(config_path)

    def test_config_with_invalid_yaml(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        with open(config_path, 'w') as f:
            f.write("invalid: yaml: syntax:")

        with pytest.raises(ValueError, match="Invalid YAML"):
            MemoryProxyConfig(config_path)

    def test_directory_property_is_parent_of_config_file(self, temp_dir: Path):
        sub_dir = temp_dir / "subdir"
        sub_dir.mkdir()
        config_path = sub_dir / ".amp.yaml"
        with open(config_path, 'w') as f:
            yaml.dump({"agents": ["claude"]}, f)

        config = MemoryProxyConfig(config_path)

        assert config.directory == sub_dir
        assert config.config_path == config_path
