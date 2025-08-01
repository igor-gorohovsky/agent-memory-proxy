from dataclasses import dataclass, field

@dataclass
class Config:
    CONFIG_FILENAME: str = ".amp.yaml"
    ENV_VAR: str = "AGENT_MEMORY_PATHS"
    DEFAULT_ENCODING: str = "utf-8"
    DEBOUNCE_DELAY: float = 0.05  # 50ms debounce
    
    AGENT_DEFAULTS: dict[str, str] = field(default_factory=lambda:{
        'claude': 'CLAUDE.md',
        'gemini': 'GEMINI.md',
        'cursor': '.cursor/rules/project.mdc',
        'qwen': 'QWEN.md',
    })

config = Config()

