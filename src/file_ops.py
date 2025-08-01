"""
File operations, path utilities, and gitignore management
"""

import os
from pathlib import Path
from typing import Optional

import pathspec
import yaml

from constants import config
from log import logger


class FileOperations:
    """Utility class for file operations with consistent error handling"""

    @staticmethod
    def read_file(path: Path, encoding: str = config.DEFAULT_ENCODING) -> str:
        """Read file content with error handling"""
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            raise

    @staticmethod
    def write_file(
        path: Path, content: str, encoding: str = config.DEFAULT_ENCODING
    ) -> None:
        """Write file content with error handling"""
        try:
            # Create target directory if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding=encoding) as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to write file {path}: {e}")
            raise

    @staticmethod
    def load_yaml_config(path: Path) -> dict:
        """Load YAML configuration file"""
        try:
            content = FileOperations.read_file(path)
            config = yaml.safe_load(content)
            if not config:
                raise ValueError(f"Empty or invalid YAML in {path}")
            return config
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in {path}: {e}")
            raise ValueError(f"Invalid YAML in {path}: {e}") from e


class PathUtils:
    """Utility class for path operations"""

    @staticmethod
    def get_relative_path_info(
        file_path: Path, base_path: Path
    ) -> tuple[str, str]:
        """Get display-friendly relative path info"""
        try:
            relative_path = file_path.relative_to(base_path)
            parent_dir = relative_path.parent

            if parent_dir == Path("."):
                source_dir = base_path.name
            else:
                source_dir = str(parent_dir)

            return source_dir, relative_path.name
        except ValueError:
            # File is outside base path
            return str(file_path.parent), file_path.name

    @staticmethod
    def resolve_paths(paths_str: str) -> list[Path]:
        """Resolve and validate paths from environment string"""
        paths = []
        for path_str in paths_str.split(os.pathsep):
            path = Path(path_str).resolve()
            if path.exists() and path.is_dir():
                paths.append(path)
            else:
                logger.warning(f"Ignoring invalid path: {path_str}")
        return paths


class GitignoreManager:
    """Manages gitignore rules for filtering directories and files"""

    def __init__(self, root_path: Path):
        self.root_path = root_path.resolve()
        self.spec_cache: dict[Path, Optional[pathspec.PathSpec]] = {}

    def _find_gitignore_files(self, directory: Path) -> list[Path]:
        """Find all .gitignore files from directory up to root"""
        gitignore_files = []
        current = directory.resolve()

        while (
            current.is_relative_to(self.root_path) or current == self.root_path
        ):
            gitignore_path = current / ".gitignore"
            if gitignore_path.exists():
                gitignore_files.append(gitignore_path)

            if current == self.root_path:
                break
            current = current.parent

        return list(reversed(gitignore_files))

    def _load_gitignore_spec(
        self, directory: Path
    ) -> Optional[pathspec.PathSpec]:
        """Load and parse gitignore rules for a directory"""
        if directory in self.spec_cache:
            return self.spec_cache[directory]

        try:
            gitignore_files = self._find_gitignore_files(directory)
            patterns = []

            for gitignore_file in gitignore_files:
                with open(
                    gitignore_file, encoding=config.DEFAULT_ENCODING
                ) as f:
                    patterns.extend(f.read().splitlines())

            if patterns:
                spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
                self.spec_cache[directory] = spec
                return spec
            else:
                self.spec_cache[directory] = None
                return None

        except Exception as e:
            logger.debug(f"Error loading gitignore for {directory}: {e}")
            self.spec_cache[directory] = None
            return None

    def is_ignored(self, path: Path) -> bool:
        """Check if a path should be ignored based on gitignore rules"""
        path = path.resolve()

        # Get relative path from root
        try:
            rel_path = path.relative_to(self.root_path)
        except ValueError:
            # Path is outside root, don't ignore
            return False

        # Check gitignore rules from the path's directory
        directory = path.parent if path.is_file() else path
        spec = self._load_gitignore_spec(directory)

        if spec is None:
            return False

        # Check if path matches any ignore patterns
        return spec.match_file(str(rel_path))
