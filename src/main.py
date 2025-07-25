import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Set, Optional

import pathspec
import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Constants
CONFIG_FILENAME = ".amp.yaml"
ENV_VAR = "AGENT_MEMORY_PATHS"
DEFAULT_ENCODING = "utf-8"

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("agent-memory-proxy")


class GitignoreManager:
    """Manages gitignore rules for filtering directories and files"""
    
    def __init__(self, root_path: Path):
        self.root_path = root_path.resolve()
        self.spec_cache: Dict[Path, Optional[pathspec.PathSpec]] = {}
        
    def _find_gitignore_files(self, directory: Path) -> List[Path]:
        """Find all .gitignore files from directory up to root"""
        gitignore_files = []
        current = directory.resolve()
        
        while current.is_relative_to(self.root_path) or current == self.root_path:
            gitignore_path = current / ".gitignore"
            if gitignore_path.exists():
                gitignore_files.append(gitignore_path)
            
            if current == self.root_path:
                break
            current = current.parent
            
        return reversed(gitignore_files)
    
    def _load_gitignore_spec(self, directory: Path) -> Optional[pathspec.PathSpec]:
        """Load and parse gitignore rules for a directory"""
        if directory in self.spec_cache:
            return self.spec_cache[directory]
            
        try:
            gitignore_files = self._find_gitignore_files(directory)
            patterns = []
            
            for gitignore_file in gitignore_files:
                with open(gitignore_file, 'r', encoding=DEFAULT_ENCODING) as f:
                    patterns.extend(f.read().splitlines())
            
            if patterns:
                spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)
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


class MemoryProxyConfig:
    """Handles configuration parsing and validation"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.directory = config_path.parent
        self.mappings: Dict[str, str] = {}
        self.recursive: bool = True
        self.respect_gitignore: bool = True
        self.load_config()

    def load_config(self):
        """Load and parse YAML configuration"""
        try:
            with open(self.config_path, "r", encoding=DEFAULT_ENCODING) as f:
                config = yaml.safe_load(f)

            if not config or "mappings" not in config:
                raise ValueError(
                    f"Invalid config in {self.config_path}: missing 'mappings' section"
                )

            self.mappings = config["mappings"]
            
            # Load optional settings with defaults
            self.recursive = config.get("recursive", True)
            self.respect_gitignore = config.get("respect_gitignore", True)
            
            logger.info(
                f"Loaded config from {self.config_path} with {len(self.mappings)} mappings "
                f"(recursive={self.recursive}, respect_gitignore={self.respect_gitignore})"
            )

        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            raise


class MemorySyncHandler(FileSystemEventHandler):
    """Handles file system events and syncs memory files"""

    def __init__(self, config: MemoryProxyConfig):
        self.config = config
        self.syncing = False
        self.last_sync_time = 0.0
        self.debounce_delay = 0.05  # 50ms debounce
        # Track which files are targets (generated files)
        self.target_files: Set[Path] = set()
        for target, source in self.config.mappings.items():
            self.target_files.add(self.config.directory / target)
            
        # Initialize gitignore manager if enabled
        self.gitignore_manager: Optional[GitignoreManager] = None
        if self.config.respect_gitignore:
            self.gitignore_manager = GitignoreManager(self.config.directory)

    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        logger.debug(f"File modified: {file_path}")

        # Skip ignored files
        if self.gitignore_manager and self.gitignore_manager.is_ignored(file_path):
            logger.debug(f"Skipping ignored file: {file_path}")
            return

        # Prevent recursive syncing
        if self.syncing:
            logger.debug(f"Skipping {file_path} - currently syncing")
            return

        # Debounce rapid fire events
        current_time = time.time()
        time_since_last = current_time - self.last_sync_time
        if time_since_last < self.debounce_delay:
            logger.debug(f"Debouncing {file_path} - {time_since_last:.3f}s since last sync")
            return

        # Set syncing flag before processing any targets
        self.syncing = True
        try:
            # Check if this is a source file that needs syncing
            synced_targets = []
            for target, source in self.config.mappings.items():
                # Handle both absolute and relative source paths in recursive mode
                source_path = self.config.directory / source

                # In recursive mode, check if the modified file matches any source
                # either directly or if it's the same filename in a subdirectory
                file_matches_source = False
                
                if file_path == source_path:
                    # Direct match - create target at config level
                    file_matches_source = True
                    target_path = self.config.directory / target
                elif self.config.recursive:
                    # Check if it's the same filename in a subdirectory
                    if file_path.name == source_path.name and file_path.is_relative_to(self.config.directory):
                        file_matches_source = True
                        # Create target in the same directory as the modified source file
                        target_path = file_path.parent / target

                if file_matches_source:
                    self.sync_file(file_path, target_path)
                    synced_targets.append(str(target_path))
            
            # Log all synced targets in one message
            if synced_targets:
                # Show directory path once, then source and target filenames
                source_rel = file_path.relative_to(self.config.directory)
                source_dir = source_rel.parent if source_rel.parent != Path('.') else self.config.directory.name
                target_filenames = []
                for target_path_str in synced_targets:
                    target_path_obj = Path(target_path_str)
                    target_filenames.append(target_path_obj.name)
                
                targets_str = ", ".join(target_filenames)
                if source_dir == self.config.directory.name:
                    logger.info(f"Synced {source_dir}/{source_rel.name} -> {targets_str}")
                else:
                    logger.info(f"Synced {source_dir}/{source_rel.name} -> {targets_str}")
                self.last_sync_time = current_time
        finally:
            # Reset syncing flag after all targets are processed
            self.syncing = False

    def sync_file(self, source: Path, target: Path):
        """Sync content from source to target file"""
        try:
            if not source.exists():
                logger.warning(f"Source file {source} does not exist")
                return

            # Create target directory if needed
            target.parent.mkdir(parents=True, exist_ok=True)

            # Read source content
            with open(source, "r", encoding=DEFAULT_ENCODING) as f:
                content = f.read()

            # Write to target
            with open(target, "w", encoding=DEFAULT_ENCODING) as f:
                f.write(content)


        except Exception as e:
            logger.error(f"Failed to sync {source} to {target}: {e}")

    def initial_sync(self):
        """Perform initial sync for all mappings"""
        logger.info(f"Performing initial sync for {self.config.directory}")

        for target, source in self.config.mappings.items():
            source_path = self.config.directory / source

            if source_path.exists():
                # Direct match - create target at config level
                target_path = self.config.directory / target
                self.sync_file(source_path, target_path)
            elif self.config.recursive:
                # In recursive mode, search for source files with the same name in subdirectories
                found_source = self._find_source_file_recursive(source)
                if found_source:
                    # Create target in the same directory as the found source file
                    target_path = found_source.parent / target
                    self.sync_file(found_source, target_path)
                else:
                    logger.warning(
                        f"Source file {source} not found in {self.config.directory} or subdirectories"
                    )
            else:
                logger.warning(
                    f"Source file {source_path} does not exist, skipping initial sync"
                )
                
    def _find_source_file_recursive(self, source_filename: str) -> Optional[Path]:
        """Find a source file with the given name in subdirectories"""
        try:
            for root, dirs, files in os.walk(self.config.directory):
                # Filter out ignored directories if gitignore is enabled
                if self.gitignore_manager:
                    dirs[:] = [d for d in dirs if not self.gitignore_manager.is_ignored(Path(root) / d)]
                
                if source_filename in files:
                    candidate_path = Path(root) / source_filename
                    # Skip if the file is ignored
                    if self.gitignore_manager and self.gitignore_manager.is_ignored(candidate_path):
                        continue
                    return candidate_path
        except Exception as e:
            logger.debug(f"Error searching for {source_filename}: {e}")
        
        return None


class MemoryProxyWatcher:
    """Main watcher that manages multiple directory watchers"""

    def __init__(self):
        self.observer = Observer()
        self.handlers: Dict[Path, MemorySyncHandler] = {}
        self.watched_directories: Set[Path] = set()

    def get_watch_directories(self) -> List[Path]:
        """Get directories to watch from environment variable"""
        paths_str = os.environ.get(ENV_VAR, ".")
        paths = []

        for path_str in paths_str.split(os.pathsep):
            path = Path(path_str).resolve()
            if path.exists() and path.is_dir():
                paths.append(path)
            else:
                logger.warning(f"Ignoring invalid path: {path_str}")

        return paths

    def scan_for_configs(self, directory: Path) -> List[Path]:
        """Recursively scan directory for config files, respecting gitignore"""
        configs = []
        gitignore_manager = GitignoreManager(directory)

        try:
            for root, dirs, files in os.walk(directory):
                root_path = Path(root)
                
                # Filter out ignored directories to avoid walking into them
                dirs[:] = [d for d in dirs if not gitignore_manager.is_ignored(root_path / d)]
                
                if CONFIG_FILENAME in files:
                    config_path = root_path / CONFIG_FILENAME
                    # Check if the config file itself is ignored
                    if not gitignore_manager.is_ignored(config_path):
                        configs.append(config_path)
                        logger.info(f"Found config: {config_path}")
                    else:
                        logger.debug(f"Skipping ignored config: {config_path}")
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")

        return configs

    def add_watcher(self, config_path: Path):
        """Add a watcher for a specific config"""
        try:
            config = MemoryProxyConfig(config_path)
            watch_path = config.directory

            # Check if directory is already being watched
            if watch_path in self.watched_directories:
                logger.warning(f"Directory {watch_path} is already being watched, skipping {config_path}")
                return

            handler = MemorySyncHandler(config)

            # Perform initial sync
            handler.initial_sync()

            # Watch the directory with recursive setting from config
            self.observer.schedule(handler, str(watch_path), recursive=config.recursive)
            self.handlers[config_path] = handler
            self.watched_directories.add(watch_path)

            watch_mode = "recursively" if config.recursive else "non-recursively"
            logger.info(f"Watching directory {watch_mode}: {watch_path}")

        except Exception as e:
            logger.error(f"Failed to add watcher for {config_path}: {e}")

    def start(self):
        """Start watching all configured directories"""
        watch_dirs = self.get_watch_directories()

        if not watch_dirs:
            logger.warning("No valid directories specified in AGENT_MEMORY_PATHS")
            watch_dirs = [Path.cwd()]

        logger.info(f"Scanning directories: {[str(d) for d in watch_dirs]}")

        # Find all configs
        all_configs = []
        for directory in watch_dirs:
            configs = self.scan_for_configs(directory)
            all_configs.extend(configs)

        if not all_configs:
            logger.warning("No configuration files found")
            return False

        # Add watchers for each config
        for config_path in all_configs:
            self.add_watcher(config_path)

        # Start observer
        self.observer.start()
        logger.info(
            f"Agent Memory Proxy started, watching {len(self.handlers)} directories"
        )

        return True

    def stop(self):
        """Stop all watchers"""
        self.observer.stop()
        self.observer.join()
        logger.info("Agent Memory Proxy stopped")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Agent Memory Proxy - Unified memory management for AI code agents"
    )
    parser.add_argument(
        "--daemon", "-d", action="store_true", help="Run as daemon/background process"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Create watcher
    watcher = MemoryProxyWatcher()

    try:
        if not watcher.start():
            logger.error("Failed to start watcher")
            sys.exit(1)

        # Keep running
        logger.info("Press Ctrl+C to stop...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        watcher.stop()


if __name__ == "__main__":
    main()
