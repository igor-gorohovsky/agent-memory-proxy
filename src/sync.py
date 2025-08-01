"""
File synchronization, event handling, and debouncing logic
"""

import os
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler

from config import MemoryProxyConfig
from constants import config
from file_ops import FileOperations, GitignoreManager, PathUtils
from log import logger


class SyncDebouncer:
    """Handles debouncing for file sync operations"""

    def __init__(self, delay: float = config.DEBOUNCE_DELAY):
        self.delay = delay
        self.last_sync_time = 0.0
        self.syncing = False

    def should_debounce(self) -> bool:
        """Check if we should debounce this sync operation"""
        if self.syncing:
            return True

        current_time = time.time()
        time_since_last = current_time - self.last_sync_time
        return time_since_last < self.delay

    def start_sync(self) -> None:
        """Mark sync as started"""
        self.syncing = True

    def finish_sync(self) -> None:
        """Mark sync as finished and update timestamp"""
        self.syncing = False
        self.last_sync_time = time.time()


class FileMatcher:
    """Handles matching files against source patterns"""

    def __init__(self, config: MemoryProxyConfig):
        self.config = config

    def find_sync_targets(
        self, modified_file: Path
    ) -> list[tuple[Path, Path]]:
        """Find all sync targets for a modified file"""
        targets = []

        for target, source in self.config.mappings.items():
            source_path = self.config.directory / source

            # Check for direct match
            if modified_file == source_path:
                target_path = self.config.directory / target
                targets.append((modified_file, target_path))

            # Check for recursive match
            elif (
                self.config.recursive
                and modified_file.name == source_path.name
                and modified_file.is_relative_to(self.config.directory)
            ):
                target_path = modified_file.parent / target
                targets.append((modified_file, target_path))

        return targets


class MemorySyncHandler(FileSystemEventHandler):
    """Handles file system events and syncs memory files"""

    def __init__(self, config: MemoryProxyConfig):
        self.config = config
        self.debouncer = SyncDebouncer()
        self.file_matcher = FileMatcher(config)

        # Track which files are targets (generated files)
        self.target_files: set[Path] = set()
        for target, _source in self.config.mappings.items():
            self.target_files.add(self.config.directory / target)

        # Initialize gitignore manager if enabled
        self.gitignore_manager: Optional[GitignoreManager] = None
        if self.config.respect_gitignore:
            self.gitignore_manager = GitignoreManager(self.config.directory)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events"""
        if event.is_directory:
            return

        file_path = Path(str(event.src_path))
        logger.debug(f"File modified: {file_path}")

        if not self._should_process_file(file_path):
            return

        self._process_file_modification(file_path)

    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed for syncing"""
        # Skip ignored files
        if self.gitignore_manager and self.gitignore_manager.is_ignored(
            file_path
        ):
            logger.debug(f"Skipping ignored file: {file_path}")
            return False

        # Debounce rapid fire events
        if self.debouncer.should_debounce():
            logger.debug(
                f"Debouncing {file_path} - currently syncing or too recent"
            )
            return False

        return True

    def _process_file_modification(self, file_path: Path) -> None:
        """Process a file modification and sync targets"""
        self.debouncer.start_sync()

        try:
            sync_targets = self.file_matcher.find_sync_targets(file_path)

            if sync_targets:
                synced_paths = self._sync_all_targets(sync_targets)
                self._log_sync_results(file_path, synced_paths)
                self.debouncer.finish_sync()
        finally:
            if self.debouncer.syncing:
                self.debouncer.syncing = False

    def _sync_all_targets(
        self, targets: list[tuple[Path, Path]]
    ) -> list[Path]:
        """Sync all target files and return synced paths"""
        synced_paths = []
        for source_path, target_path in targets:
            self.sync_file(source_path, target_path)
            synced_paths.append(target_path)
        return synced_paths

    def _log_sync_results(
        self, source_file: Path, synced_paths: list[Path]
    ) -> None:
        """Log the results of sync operations"""
        if not synced_paths:
            return

        source_dir, source_name = PathUtils.get_relative_path_info(
            source_file, self.config.directory
        )
        target_names = [path.name for path in synced_paths]
        targets_str = ", ".join(target_names)

        logger.info(f"Synced {source_dir}/{source_name} -> {targets_str}")

    def sync_file(self, source: Path, target: Path) -> None:
        """Sync content from source to target file"""
        try:
            if not source.exists():
                logger.warning(f"Source file {source} does not exist")
                return

            content = FileOperations.read_file(source)
            FileOperations.write_file(target, content)

        except Exception as e:
            logger.error(f"Failed to sync {source} to {target}: {e}")

    def initial_sync(self) -> None:
        """Perform initial sync for all mappings"""
        logger.info(f"Performing initial sync for {self.config.directory}")

        for target, source in self.config.mappings.items():
            self._sync_initial_mapping(target, source)

    def _sync_initial_mapping(self, target: str, source: str) -> None:
        """Sync a single mapping during initial sync"""
        source_path = self.config.directory / source

        if source_path.exists():
            # Direct match - create target at config level
            target_path = self.config.directory / target
            self.sync_file(source_path, target_path)
        elif self.config.recursive:
            # In recursive mode, search for source files in subdirectories
            found_source = self._find_source_file_recursive(source)
            if found_source:
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

    def _find_source_file_recursive(
        self, source_filename: str
    ) -> Optional[Path]:
        """Find a source file with the given name in subdirectories"""
        try:
            for root, dirs, files in os.walk(self.config.directory):
                # Filter out ignored directories if gitignore is enabled
                if self.gitignore_manager:
                    dirs[:] = [
                        d
                        for d in dirs
                        if not self.gitignore_manager.is_ignored(
                            Path(root) / d
                        )
                    ]

                if source_filename in files:
                    candidate_path = Path(root) / source_filename
                    # Skip if the file is ignored
                    if (
                        self.gitignore_manager
                        and self.gitignore_manager.is_ignored(candidate_path)
                    ):
                        continue
                    return candidate_path
        except Exception as e:
            logger.debug(f"Error searching for {source_filename}: {e}")

        return None
