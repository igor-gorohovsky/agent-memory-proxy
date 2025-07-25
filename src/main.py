import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Set

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


class MemoryProxyConfig:
    """Handles configuration parsing and validation"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.directory = config_path.parent
        self.mappings: Dict[str, str] = {}
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
            logger.info(
                f"Loaded config from {self.config_path} with {len(self.mappings)} mappings"
            )

        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            raise


class MemorySyncHandler(FileSystemEventHandler):
    """Handles file system events and syncs memory files"""

    def __init__(self, config: MemoryProxyConfig):
        self.config = config
        self.syncing = False
        # Track which files are targets (generated files)
        self.target_files: Set[Path] = set()
        for target, source in self.config.mappings.items():
            self.target_files.add(self.config.directory / target)

    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return

        # Prevent recursive syncing
        if self.syncing:
            return

        file_path = Path(event.src_path)

        # Check if this is a source file that needs syncing
        for target, source in self.config.mappings.items():
            source_path = self.config.directory / source
            target_path = self.config.directory / target

            # If source file was modified, sync to all its targets
            if file_path == source_path:
                self.sync_file(source_path, target_path)
                break

    def sync_file(self, source: Path, target: Path):
        """Sync content from source to target file"""
        try:
            self.syncing = True

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

            logger.info(f"Synced {source.name} -> {target}")

        except Exception as e:
            logger.error(f"Failed to sync {source} to {target}: {e}")
        finally:
            self.syncing = False

    def initial_sync(self):
        """Perform initial sync for all mappings"""
        logger.info(f"Performing initial sync for {self.config.directory}")

        for target, source in self.config.mappings.items():
            source_path = self.config.directory / source
            target_path = self.config.directory / target

            if source_path.exists():
                self.sync_file(source_path, target_path)
            else:
                logger.warning(
                    f"Source file {source_path} does not exist, skipping initial sync"
                )


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
        """Recursively scan directory for config files"""
        configs = []

        try:
            for root, dirs, files in os.walk(directory):
                if CONFIG_FILENAME in files:
                    config_path = Path(root) / CONFIG_FILENAME
                    configs.append(config_path)
                    logger.info(f"Found config: {config_path}")
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")

        return configs

    def add_watcher(self, config_path: Path):
        """Add a watcher for a specific config"""
        try:
            config = MemoryProxyConfig(config_path)
            handler = MemorySyncHandler(config)

            # Perform initial sync
            handler.initial_sync()

            # Watch the directory
            watch_path = config.directory
            self.observer.schedule(handler, str(watch_path), recursive=False)
            self.handlers[config_path] = handler
            self.watched_directories.add(watch_path)

            logger.info(f"Watching directory: {watch_path}")

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
