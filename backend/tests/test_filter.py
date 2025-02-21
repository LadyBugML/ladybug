from utils.filter import filter_files
import pytest
from pathlib import Path

def test_filter_empty_repo(tmp_path):
    # Call filter on an empty directory (simulating an empty repo)
    result = filter_files(tmp_path)

    assert result == []

def test_filter_invalid_path(tmp_path):
    # Call filter on a non-existent path
    invalid_path = tmp_path / "nonexistent_repo"
    assert not invalid_path.exists()

    with pytest.raises(ValueError, match="is not a valid directory."):
        filter_files(invalid_path)

def test_filter_single_java_file(tmp_path):
    # Simulate a single java file passed into filter_files()
    java_file = tmp_path / "SingleFile.java"
    java_file.write_text("public class SingleFile {}")

    with pytest.raises(ValueError, match="is not a valid directory"):
        filter_files(java_file)

def test_filter_hidden_files(tmp_path):
    # Create a regular Java file
    java_file = tmp_path / "Regular.java"
    java_file.write_text("public class Regular {}")
    
    # Create a hidden Java file
    hidden_java_file = tmp_path / ".HiddenFile.java"
    hidden_java_file.write_text("public class HiddenFile {}")
    
    # Create a hidden non-Java file
    hidden_non_java_file = tmp_path / ".HiddenFile.txt"
    hidden_non_java_file.write_text("This is a text file.")

    result = filter_files(tmp_path)
    
    assert Path(java_file) in result
    assert Path(hidden_java_file) not in result
    assert Path(hidden_non_java_file) not in result
    
    hidden_files = [f for f in tmp_path.rglob('*') if f.name.startswith('.')]
    assert len(hidden_files) == 0, "Hidden files remain in the directory"

def test_filter_only_java_files(tmp_path):
    # Set up three Java files
    java_file1 = tmp_path / "File1.java"
    java_file2 = tmp_path / "File2.java"
    java_file3 = tmp_path / "File3.java"
    java_file1.write_text("public class File1 {}")
    java_file2.write_text("public class File2 {}")
    java_file3.write_text("public class File3 {}")

    result = filter_files(tmp_path)

    # Assert that exactly three Java files are returned
    assert len(result) == 3, "Expected 3 Java files to remain after filtering"
    assert java_file1 in result
    assert java_file2 in result
    assert java_file3 in result

    # Assert that all three Java files remained
    java_files = [f for f in tmp_path.rglob('*') if f.name.endswith('.java')]
    assert len(java_files) == 3, "Java files incorrectly filtered from input path"

def test_filter_with_nested_directories_and_empty_dir(tmp_path):
    # Create a nested directory structure with Java and non-Java files
    nested_dir1 = tmp_path / "dir1"
    nested_dir1.mkdir()
    nested_dir2 = nested_dir1 / "dir2"
    nested_dir2.mkdir()
    
    # Java files across different directories
    java_file1 = tmp_path / "File1.java"
    java_file2 = nested_dir1 / "File2.java"
    java_file3 = nested_dir2 / "File3.java"
    java_file1.write_text("public class File1 {}")
    java_file2.write_text("public class File2 {}")
    java_file3.write_text("public class File3 {}")
    
    # Non-Java and hidden files
    non_java_file = tmp_path / "File.txt"
    hidden_file = nested_dir1 / ".HiddenFile.java"
    non_java_file.write_text("This is a text file.")
    hidden_file.write_text("public class HiddenFile {}")
    
    # Add an empty directory to test if it's removed
    empty_dir = nested_dir1 / "empty_dir"
    empty_dir.mkdir()

    # Call the filter function
    result = filter_files(tmp_path)

    # Assert that only the three Java files are returned
    assert len(result) == 3, "Expected 3 Java files to remain after filtering"
    assert java_file1 in result
    assert java_file2 in result
    assert java_file3 in result

    # Check the input directory to ensure only Java files and no empty directories remain
    all_files = list(tmp_path.rglob('*'))
    assert all(f.suffix == ".java" for f in all_files if f.is_file()), "Non-Java files are present"
    assert all(f.name.startswith('.') == False for f in all_files if f.is_file()), "Hidden files are present"
    
    # Check there are no empty directories, including the one we created
    empty_dirs = [d for d in tmp_path.rglob("*") if d.is_dir() and not any(d.iterdir())]
    assert len(empty_dirs) == 0, "Empty directories are present"
