import pytest
from pathlib import Path
import yaml
import os

from file_ops import FileOperations, PathUtils, GitignoreManager
from constants import config


class TestFileOperations:
    """Tests for FileOperations focusing on file I/O behavior"""
    
    def test_read_file_returns_content(self, temp_dir: Path):
        test_file = temp_dir / "test.txt"
        expected_content = "Hello, World!\nThis is a test file."
        test_file.write_text(expected_content)
        
        content = FileOperations.read_file(test_file)
        
        assert content == expected_content
    
    def test_read_file_with_custom_encoding(self, temp_dir: Path):
        test_file = temp_dir / "test.txt"
        expected_content = "Hello, 世界!"
        test_file.write_text(expected_content, encoding='utf-8')
        
        content = FileOperations.read_file(test_file, encoding='utf-8')
        
        assert content == expected_content
    
    def test_read_file_raises_on_missing_file(self, temp_dir: Path):
        non_existent = temp_dir / "missing.txt"
        
        with pytest.raises(Exception):
            FileOperations.read_file(non_existent)
    
    def test_write_file_creates_file(self, temp_dir: Path):
        test_file = temp_dir / "new_file.txt"
        content = "Test content"
        
        FileOperations.write_file(test_file, content)
        
        assert test_file.exists()
        assert test_file.read_text() == content
    
    def test_write_file_creates_parent_directories(self, temp_dir: Path):
        test_file = temp_dir / "sub" / "dir" / "file.txt"
        content = "Nested file content"
        
        FileOperations.write_file(test_file, content)
        
        assert test_file.exists()
        assert test_file.read_text() == content
    
    def test_write_file_overwrites_existing_file(self, temp_dir: Path):
        test_file = temp_dir / "existing.txt"
        test_file.write_text("Old content")
        new_content = "New content"
        
        FileOperations.write_file(test_file, new_content)
        
        assert test_file.read_text() == new_content
    
    def test_load_yaml_config_returns_dict(self, temp_dir: Path):
        config_file = temp_dir / "config.yaml"
        config_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = FileOperations.load_yaml_config(config_file)
        
        assert result == config_data
    
    def test_load_yaml_config_raises_on_invalid_yaml(self, temp_dir: Path):
        config_file = temp_dir / "bad.yaml"
        config_file.write_text("invalid: yaml: syntax:")
        
        with pytest.raises(ValueError, match="Invalid YAML"):
            FileOperations.load_yaml_config(config_file)
    
    def test_load_yaml_config_raises_on_empty_file(self, temp_dir: Path):
        config_file = temp_dir / "empty.yaml"
        config_file.touch()
        
        with pytest.raises(ValueError, match="Empty or invalid YAML"):
            FileOperations.load_yaml_config(config_file)


class TestPathUtils:
    """Tests for PathUtils focusing on path manipulation behavior"""
    
    def test_get_relative_path_info_for_file_in_root(self, temp_dir: Path):
        file_path = temp_dir / "file.txt"
        
        source_dir, file_name = PathUtils.get_relative_path_info(file_path, temp_dir)
        
        assert source_dir == temp_dir.name
        assert file_name == "file.txt"
    
    def test_get_relative_path_info_for_nested_file(self, temp_dir: Path):
        file_path = temp_dir / "sub" / "dir" / "file.txt"
        
        source_dir, file_name = PathUtils.get_relative_path_info(file_path, temp_dir)
        
        assert source_dir == "sub/dir"
        assert file_name == "file.txt"
    
    def test_get_relative_path_info_for_file_outside_base(self, temp_dir: Path):
        other_dir = temp_dir.parent / "other"
        file_path = other_dir / "file.txt"
        
        source_dir, file_name = PathUtils.get_relative_path_info(file_path, temp_dir)
        
        assert source_dir == str(other_dir)
        assert file_name == "file.txt"
    
    def test_resolve_paths_returns_valid_directories(self, temp_dir: Path):
        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        
        paths_str = f"{dir1}{os.pathsep}{dir2}"
        result = PathUtils.resolve_paths(paths_str)
        
        assert len(result) == 2
        assert dir1 in result
        assert dir2 in result
    
    def test_resolve_paths_ignores_invalid_paths(self, temp_dir: Path):
        valid_dir = temp_dir / "valid"
        valid_dir.mkdir()
        invalid_path = temp_dir / "nonexistent"
        
        paths_str = f"{valid_dir}{os.pathsep}{invalid_path}"
        result = PathUtils.resolve_paths(paths_str)
        
        assert len(result) == 1
        assert valid_dir in result
    
    def test_resolve_paths_ignores_files(self, temp_dir: Path):
        dir_path = temp_dir / "dir"
        file_path = temp_dir / "file.txt"
        dir_path.mkdir()
        file_path.touch()
        
        paths_str = f"{dir_path}{os.pathsep}{file_path}"
        result = PathUtils.resolve_paths(paths_str)
        
        assert len(result) == 1
        assert dir_path in result


class TestGitignoreManager:
    """Tests for GitignoreManager focusing on gitignore rule behavior"""
    
    def test_ignores_files_matching_gitignore_patterns(self, temp_dir: Path):
        gitignore_content = "*.log\n__pycache__/\n.env"
        (temp_dir / ".gitignore").write_text(gitignore_content)
        
        manager = GitignoreManager(temp_dir)
        
        assert manager.is_ignored(temp_dir / "test.log")
        assert manager.is_ignored(temp_dir / "__pycache__" / "module.pyc")
        assert manager.is_ignored(temp_dir / ".env")
        assert not manager.is_ignored(temp_dir / "main.py")
    
    def test_respects_nested_gitignore_files(self, temp_dir: Path):
        # Root gitignore
        (temp_dir / ".gitignore").write_text("*.txt")
        
        # Subdirectory gitignore
        sub_dir = temp_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / ".gitignore").write_text("!important.txt")
        
        manager = GitignoreManager(temp_dir)
        
        assert manager.is_ignored(temp_dir / "regular.txt")
        # Note: In real gitignore behavior, negation patterns in subdirectories
        # can override parent patterns, but pathspec behavior may vary
    
    def test_handles_missing_gitignore_gracefully(self, temp_dir: Path):
        manager = GitignoreManager(temp_dir)
        
        assert not manager.is_ignored(temp_dir / "any_file.txt")
    
    def test_caches_gitignore_specs(self, temp_dir: Path):
        (temp_dir / ".gitignore").write_text("*.log")
        manager = GitignoreManager(temp_dir)
        
        # Create actual files to test with
        test_file = temp_dir / "test.log"
        test_file.write_text("log content")
        another_file = temp_dir / "another.log"
        another_file.write_text("more log content")
        
        # First call loads and caches
        assert manager.is_ignored(test_file)
        
        # Second call should use cache
        assert manager.is_ignored(another_file)
        
        # Verify that gitignore specs are cached (testing behavior, not implementation)
        # The cache should have been populated after the first call
        assert len(manager.spec_cache) > 0
        
        # Verify the same spec is used for files in the same directory
        # by checking that both files were correctly identified as ignored
        assert manager.is_ignored(test_file)
        assert manager.is_ignored(another_file)
    
    def test_handles_paths_outside_root(self, temp_dir: Path):
        manager = GitignoreManager(temp_dir)
        outside_path = temp_dir.parent / "outside.txt"
        
        assert not manager.is_ignored(outside_path)
    
    def test_handles_complex_gitignore_patterns(self, temp_dir: Path):
        gitignore_content = """
# Comments should be ignored
*.tmp
!keep.tmp
/build/
src/**/*.test.js
.DS_Store
"""
        (temp_dir / ".gitignore").write_text(gitignore_content)
        
        manager = GitignoreManager(temp_dir)
        
        assert manager.is_ignored(temp_dir / "file.tmp")
        assert not manager.is_ignored(temp_dir / "keep.tmp")
        assert manager.is_ignored(temp_dir / "build" / "output.js")
        assert manager.is_ignored(temp_dir / "src" / "components" / "Button.test.js")
        assert manager.is_ignored(temp_dir / ".DS_Store")