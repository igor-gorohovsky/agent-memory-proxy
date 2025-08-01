from pathlib import Path
from typing import Dict, List

from constants import config
from log import logger
from file_ops import FileOperations


class ConfigValidator:
    @staticmethod
    def validate_agents_list(agents) -> List[str]:
        if not isinstance(agents, list):
            raise ValueError(f"'agents' must be a list, got {type(agents)}")
        
        validated_agents = []
        for agent in agents:
            if not isinstance(agent, str):
                raise ValueError(f"Agent name must be string, got {type(agent)}: {agent}")
            
            agent_lower = agent.lower()
            if agent_lower not in config.AGENT_DEFAULTS:
                available = ', '.join(sorted(config.AGENT_DEFAULTS.keys()))
                raise ValueError(f"Unknown agent '{agent}'. Available: {available}")
            
            validated_agents.append(agent_lower)
        
        return validated_agents
    
    @staticmethod
    def create_mappings(agents: List[str], truth_file: str) -> Dict[str, str]:
        """Create target->source mappings from agent list"""
        mappings = {}
        for agent in agents:
            target_path = config.AGENT_DEFAULTS[agent]
            mappings[target_path] = truth_file
        return mappings


class MemoryProxyConfig:
    """Handles configuration parsing and validation"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.directory = config_path.parent
        self.mappings: Dict[str, str] = {}
        self.recursive: bool = True
        self.respect_gitignore: bool = True
        self.truth_memory_file: str = "AGENT.md"
        self._load_and_validate_config()

    def _load_and_validate_config(self) -> None:
        """Load and validate YAML configuration"""
        try:
            config_data = FileOperations.load_yaml_config(self.config_path)
            
            if "agents" not in config_data:
                raise ValueError(
                    f"Invalid config in {self.config_path}: missing 'agents' section"
                )

            # Load settings with defaults
            self.respect_gitignore = config_data.get("respect_gitignore", True)
            self.truth_memory_file = config_data.get("truth_memory_file", "AGENT.md")
            
            # Validate and process agents
            agents = ConfigValidator.validate_agents_list(config_data["agents"])
            self.mappings = ConfigValidator.create_mappings(agents, self.truth_memory_file)
                
            logger.info(
                f"Loaded config from {self.config_path} with {len(agents)} agents "
                f"(truth_file={self.truth_memory_file}, respect_gitignore={self.respect_gitignore})"
            )

        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            raise
