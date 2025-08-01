import os
import sys
from pathlib import Path

from watchdog.observers import Observer

from config import MemoryProxyConfig
from constants import config
from file_ops import PathUtils
from log import logger
from sync import MemorySyncHandler


class MemoryProxyWatcher:
    """Main watcher that manages multiple directory watchers"""

    def __init__(self):
        self._observer = Observer()
        self.handlers: dict[Path, MemorySyncHandler] = {}
        self.watched_directories: set[Path] = set()

    def start(self) -> bool:
        paths_str = os.environ.get(config.ENV_VAR, "")
        watch_dirs = PathUtils.resolve_paths(paths_str)

        if not watch_dirs:
            logger.error(
                "No valid directories specified in AGENT_MEMORY_PATHS. Stopping execution..."
            )
            sys.exit(1)

        logger.info(f"Scanning directories: {[str(d) for d in watch_dirs]}")

        all_configs = []
        for directory in watch_dirs:
            configs = self._scan_for_configs(directory)
            all_configs.extend(configs)

        if not all_configs:
            logger.error(
                "No direcrories with configuration file were found. Stopping execution..."
            )
            sys.exit(1)

        for config_path in all_configs:
            self._add_watcher(config_path)

        self._observer.start()
        logger.info(
            f"Agent Memory Proxy started, watching {len(self.handlers)} directories"
        )

        return True

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()
        logger.info("Agent Memory Proxy stopped")

    def _scan_for_configs(self, directory: Path) -> list[Path]:
        """Recursively scan directory for config files"""
        configs = []

        for root, dirs, files in os.walk(directory):
            root_dir = Path(root)

            if config.CONFIG_FILENAME in files:
                config_path = root_dir / config.CONFIG_FILENAME
                configs.append(config_path)
                dirs.clear()
                logger.info(f"Found config: {config_path}")

        return configs

    def _add_watcher(self, config_path: Path) -> None:
        try:
            config = MemoryProxyConfig(config_path)
            watch_path = config.directory

            if watch_path in self.watched_directories:
                logger.warning(
                    f"Directory {watch_path} is already being watched, skipping {config_path}"
                )
                return

            handler = MemorySyncHandler(config)

            # Perform initial sync
            handler.initial_sync()

            # Watch the directory with recursive setting from config
            self._observer.schedule(
                handler, str(watch_path), recursive=config.recursive
            )
            self.handlers[config_path] = handler
            self.watched_directories.add(watch_path)

            watch_mode = (
                "recursively" if config.recursive else "non-recursively"
            )
            logger.info(f"Watching directory {watch_mode}: {watch_path}")

        except Exception as e:
            logger.error(f"Failed to add watcher for {config_path}: {e}")
