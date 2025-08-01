import pytest
from pathlib import Path
import time
from unittest.mock import Mock, MagicMock
import yaml

from sync import SyncDebouncer, FileMatcher, MemorySyncHandler
from config import MemoryProxyConfig
from constants import config as app_config


class TestSyncDebouncer:
    """Tests for SyncDebouncer focusing on debouncing behavior"""
    
    def test_should_not_debounce_first_sync(self):
        debouncer = SyncDebouncer(delay=0.1)
        
        assert not debouncer.should_debounce()
    
    def test_should_debounce_rapid_syncs(self):
        debouncer = SyncDebouncer(delay=0.1)
        
        debouncer.start_sync()
        debouncer.finish_sync()
        
        # Immediately after sync, should debounce
        assert debouncer.should_debounce()
    
    def test_should_not_debounce_after_delay(self):
        debouncer = SyncDebouncer(delay=0.05)
        
        debouncer.start_sync()
        debouncer.finish_sync()
        
        time.sleep(0.06)  # Wait longer than delay
        
        assert not debouncer.should_debounce()
    
    def test_should_debounce_when_syncing_in_progress(self):
        debouncer = SyncDebouncer(delay=0.1)
        
        debouncer.start_sync()
        
        assert debouncer.should_debounce()
        
        debouncer.finish_sync()
        
        # After finishing, should still debounce due to timing
        assert debouncer.should_debounce()
    
    def test_sync_state_transitions(self):
        debouncer = SyncDebouncer()
        
        assert not debouncer.syncing
        
        debouncer.start_sync()
        assert debouncer.syncing
        
        debouncer.finish_sync()
        assert not debouncer.syncing


class TestFileMatcher:
    """Tests for FileMatcher focusing on file matching behavior"""
    
    def test_find_direct_match(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {
            "agents": ["claude"],
            "truth_memory_file": "AGENT.md"
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        matcher = FileMatcher(config)
        
        source_file = temp_dir / "AGENT.md"
        targets = matcher.find_sync_targets(source_file)
        
        assert len(targets) == 1
        assert targets[0] == (source_file, temp_dir / "CLAUDE.md")
    
    def test_find_multiple_targets(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {
            "agents": ["claude", "gemini", "cursor"],
            "truth_memory_file": "AGENT.md"
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        matcher = FileMatcher(config)
        
        source_file = temp_dir / "AGENT.md"
        targets = matcher.find_sync_targets(source_file)
        
        assert len(targets) == 3
        target_paths = [t[1] for t in targets]
        assert temp_dir / "CLAUDE.md" in target_paths
        assert temp_dir / "GEMINI.md" in target_paths
        assert temp_dir / ".cursor/rules/project.mdc" in target_paths
    
    def test_find_recursive_match(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {
            "agents": ["claude"],
            "truth_memory_file": "AGENT.md"
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        config.recursive = True
        matcher = FileMatcher(config)
        
        # File in subdirectory with same name
        sub_dir = temp_dir / "subdir"
        sub_dir.mkdir()
        source_file = sub_dir / "AGENT.md"
        
        targets = matcher.find_sync_targets(source_file)
        
        assert len(targets) == 1
        assert targets[0] == (source_file, sub_dir / "CLAUDE.md")
    
    def test_no_match_for_unrelated_file(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {
            "agents": ["claude"],
            "truth_memory_file": "AGENT.md"
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        matcher = FileMatcher(config)
        
        unrelated_file = temp_dir / "README.md"
        targets = matcher.find_sync_targets(unrelated_file)
        
        assert len(targets) == 0
    
    def test_custom_truth_file_matching(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {
            "agents": ["claude"],
            "truth_memory_file": "CUSTOM_MEMORY.md"
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        matcher = FileMatcher(config)
        
        source_file = temp_dir / "CUSTOM_MEMORY.md"
        targets = matcher.find_sync_targets(source_file)
        
        assert len(targets) == 1
        assert targets[0] == (source_file, temp_dir / "CLAUDE.md")


class TestMemorySyncHandler:
    """Tests for MemorySyncHandler focusing on sync behavior"""
    
    def test_sync_file_copies_content(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {"agents": ["claude"]}
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        handler = MemorySyncHandler(config)
        
        source = temp_dir / "source.txt"
        target = temp_dir / "target.txt"
        content = "Test content for sync"
        source.write_text(content)
        
        handler.sync_file(source, target)
        
        assert target.exists()
        assert target.read_text() == content
    
    def test_sync_file_creates_parent_directories(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {"agents": ["cursor"]}
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        handler = MemorySyncHandler(config)
        
        source = temp_dir / "AGENT.md"
        target = temp_dir / ".cursor/rules/project.mdc"
        content = "Cursor rules"
        source.write_text(content)
        
        handler.sync_file(source, target)
        
        assert target.exists()
        assert target.read_text() == content
    
    def test_sync_file_handles_missing_source(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {"agents": ["claude"]}
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        handler = MemorySyncHandler(config)
        
        source = temp_dir / "missing.txt"
        target = temp_dir / "target.txt"
        
        # Should not raise, just log warning
        handler.sync_file(source, target)
        
        assert not target.exists()
    
    def test_initial_sync_syncs_existing_files(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {
            "agents": ["claude", "gemini"],
            "truth_memory_file": "AGENT.md"
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create source file
        source_content = "Initial memory content"
        (temp_dir / "AGENT.md").write_text(source_content)
        
        config = MemoryProxyConfig(config_path)
        handler = MemorySyncHandler(config)
        
        handler.initial_sync()
        
        assert (temp_dir / "CLAUDE.md").exists()
        assert (temp_dir / "CLAUDE.md").read_text() == source_content
        assert (temp_dir / "GEMINI.md").exists()
        assert (temp_dir / "GEMINI.md").read_text() == source_content
    
    def test_initial_sync_recursive_mode(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {
            "agents": ["claude"],
            "truth_memory_file": "AGENT.md"
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create source file in subdirectory
        sub_dir = temp_dir / "docs"
        sub_dir.mkdir()
        source_content = "Nested memory content"
        (sub_dir / "AGENT.md").write_text(source_content)
        
        config = MemoryProxyConfig(config_path)
        config.recursive = True
        handler = MemorySyncHandler(config)
        
        handler.initial_sync()
        
        # Should find and sync the nested file
        assert (sub_dir / "CLAUDE.md").exists()
        assert (sub_dir / "CLAUDE.md").read_text() == source_content
    
    def test_on_modified_triggers_sync(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {"agents": ["claude"]}
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        handler = MemorySyncHandler(config)
        
        # Create source and target files
        source = temp_dir / "AGENT.md"
        target = temp_dir / "CLAUDE.md"
        source.write_text("Original content")
        
        # Simulate file modification event
        event = Mock()
        event.is_directory = False
        event.src_path = str(source)
        
        handler.on_modified(event)
        
        # Give time for any async operations
        time.sleep(0.1)
        
        assert target.exists()
        assert target.read_text() == "Original content"
    
    def test_debouncing_prevents_rapid_syncs(self, temp_dir: Path):
        config_path = temp_dir / ".amp.yaml"
        config_data = {"agents": ["claude"]}
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = MemoryProxyConfig(config_path)
        handler = MemorySyncHandler(config)
        
        # Mock the sync_file method to count calls
        sync_count = 0
        original_sync = handler.sync_file
        def counting_sync(*args, **kwargs):
            nonlocal sync_count
            sync_count += 1
            return original_sync(*args, **kwargs)
        handler.sync_file = counting_sync
        
        source = temp_dir / "AGENT.md"
        source.write_text("Content")
        
        # Simulate rapid file modifications
        event = Mock()
        event.is_directory = False
        event.src_path = str(source)
        
        handler.on_modified(event)
        handler.on_modified(event)  # Should be debounced
        handler.on_modified(event)  # Should be debounced
        
        time.sleep(0.1)
        
        # Should only sync once due to debouncing
        assert sync_count == 1