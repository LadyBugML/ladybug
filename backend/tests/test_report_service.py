
import zipfile
import os
import pytest
from unittest.mock import MagicMock, patch
from stat import S_IWUSR, S_IREAD
from werkzeug.exceptions import HTTPException

from services.report_service import reorder_rankings
from utils.file_utils import change_repository_file_permissions, post_process_cleanup, write_file_for_report_processing
from utils.git_utils import create_changed_files_dict, extract_and_validate_repo_info, extract_files

def test_create_changed_files_dict_with_added_files():
    github_diff_data = {
        "files": [
            {"filename": "src/main/java/com/example/NewFile.java", "status": "added"},
            {"filename": "src/main/java/com/example/AnotherFile.java", "status": "added"}
        ]
    }
    repo_dir = "repo_owner/repo_name"
    expected_result = {
        "added": ["src/main/java/com/example/NewFile.java", "src/main/java/com/example/AnotherFile.java"],
        "modified": [],
        "removed": []
    }
    result = create_changed_files_dict(github_diff_data, repo_dir)
    assert result == expected_result, f"Expected {expected_result}, but got {result}"

def test_create_changed_files_dict_with_modified_files():
    github_diff_data = {
        "files": [
            {"filename": "src/main/java/com/example/ModifiedFile.java", "status": "modified"},
            {"filename": "src/main/java/com/example/AnotherModifiedFile.java", "status": "modified"}
        ]
    }
    repo_dir = "repo_dir"
    expected_result = {
        "added": [],
        "modified": ["src/main/java/com/example/ModifiedFile.java", "src/main/java/com/example/AnotherModifiedFile.java"],
        "removed": []
    }
    result = create_changed_files_dict(github_diff_data, repo_dir)
    assert result == expected_result, f"Expected {expected_result}, but got {result}"

def test_create_changed_files_dict_with_removed_files():
    github_diff_data = {
        "files": [
            {"filename": "src/main/java/com/example/RemovedFile.java", "status": "removed"},
            {"filename": "src/main/java/com/example/AnotherRemovedFile.java", "status": "removed"}
        ]
    }
    repo_dir = "repo_dir"
    expected_result = {
        "added": [],
        "modified": [],
        "removed": ["src/main/java/com/example/RemovedFile.java", "src/main/java/com/example/AnotherRemovedFile.java"]
    }
    result = create_changed_files_dict(github_diff_data, repo_dir)
    assert result == expected_result, f"Expected {expected_result}, but got {result}"

def test_create_changed_files_dicf_with_all_types_of_files():
    github_diff_data = {
        "files": [
            {"filename": "src/main/java/com/example/NewFile.java", "status": "added"},
            {"filename": "src/main/java/com/example/ModifiedFile.java", "status": "modified"},
            {"filename": "src/main/java/com/example/RemovedFile.java", "status": "removed"}
        ]
    }
    repo_dir = "repo_dir"
    expected_result = {
        "added": ["src/main/java/com/example/NewFile.java"],
        "modified": ["src/main/java/com/example/ModifiedFile.java"],
        "removed": ["src/main/java/com/example/RemovedFile.java"]
    }
    result = create_changed_files_dict(github_diff_data, repo_dir)
    assert result == expected_result, f"Expected {expected_result}, but got {result}"

def test_reorder_rankings():
    ranked_files = [
        ("path/to/file1.java", 0.59),
        ("path/to/file2.java", 0.55),
        ("path/to/file3.java", 0.48),
        ("path/to/file4.java", 0.47),
        ("path/to/file5.java", 0.47),
        ("path/to/file6.java", 0.45),
        ("path/to/file7.java", 0.43),
        ("path/to/file8.java", 0.42),
    ]

    gs_files = ["path/to/file2.java", "path/to/file3.java", "path/to/file7.java"]

    expected_boosted_ranked_files = [
        ("path/to/file2.java", 0.55),
        ("path/to/file3.java", 0.48),
        ("path/to/file7.java", 0.43),
        ("path/to/file1.java", 0.59),
        ("path/to/file4.java", 0.47),
        ("path/to/file5.java", 0.47),
        ("path/to/file6.java", 0.45),
        ("path/to/file8.java", 0.42),
    ]

    boosted_ranked_files = reorder_rankings(ranked_files, gs_files)

    assert boosted_ranked_files == expected_boosted_ranked_files, f"Mismatch: {boosted_ranked_files}"

def test_extract_files_with_added_files():
    changed_files = {
        "added": ["src/main/java/com/example/NewFile.java"],
        "modified": [],
        "removed": []
    }
    repo_dir = "repo_dir"
    zip_archive = MagicMock(spec=zipfile.ZipFile)
    zip_archive.namelist.return_value = ["repo_dir/src/main/java/com/example/NewFile.java"]

    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        extract_files(changed_files, zip_archive, repo_dir)
        mock_open.assert_called_once_with(os.path.join(repo_dir, "src/main/java/com/example/NewFile.java"), "w", encoding="utf-8")

def test_extract_files_with_modified_files():
    changed_files = {
        "added": [],
        "modified": ["src/main/java/com/example/ModifiedFile.java"],
        "removed": []
    }
    repo_dir = "repo_dir"
    zip_archive = MagicMock(spec=zipfile.ZipFile)
    zip_archive.namelist.return_value = ["repo_dir/src/main/java/com/example/ModifiedFile.java"]

    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        extract_files(changed_files, zip_archive, repo_dir)
        mock_open.assert_called_once_with(os.path.join(repo_dir, "src/main/java/com/example/ModifiedFile.java"), "w", encoding="utf-8")

def test_extract_files_with_removed_files():
    changed_files = {
        "added": [],
        "modified": [],
        "removed": ["src/main/java/com/example/RemovedFile.java"]
    }
    repo_dir = "repo_dir"
    zip_archive = MagicMock(spec=zipfile.ZipFile)

    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        extract_files(changed_files, zip_archive, repo_dir)
        mock_open.assert_not_called()

def test_extract_files_with_mixed_files():
    changed_files = {
        "added": ["src/main/java/com/example/NewFile.java"],
        "modified": ["src/main/java/com/example/ModifiedFile.java"],
        "removed": ["src/main/java/com/example/RemovedFile.java"]
    }
    repo_dir = "repo_dir"
    zip_archive = MagicMock(spec=zipfile.ZipFile)
    zip_archive.namelist.return_value = [
        "repo_dir/src/main/java/com/example/NewFile.java",
        "repo_dir/src/main/java/com/example/ModifiedFile.java"
    ]

    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        extract_files(changed_files, zip_archive, repo_dir)
        assert mock_open.call_count == 2
        mock_open.assert_any_call(os.path.join(repo_dir, "src/main/java/com/example/NewFile.java"), "w", encoding="utf-8")
        mock_open.assert_any_call(os.path.join(repo_dir, "src/main/java/com/example/ModifiedFile.java"), "w", encoding="utf-8")

def test_extract_files_with_no_files():
    changed_files = {
        "added": [],
        "modified": [],
        "removed": []
    }
    repo_dir = "repo_dir"
    zip_archive = MagicMock(spec=zipfile.ZipFile)

    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        extract_files(changed_files, zip_archive, repo_dir)
        mock_open.assert_not_called()

def test_post_process_cleanup_directory_exists():
    repo_info = {
        'owner': 'repo_owner',
        'repo_name': 'repo_name'
    }
    dir_path = os.path.join('repos', repo_info['owner'], repo_info['repo_name'])

    with patch('os.path.exists', return_value=True), \
            patch('os.path.isdir', return_value=True), \
            patch('shutil.rmtree') as mock_rmtree, \
            patch('logging.Logger.info') as mock_logger_info:
        post_process_cleanup(repo_info)
        mock_rmtree.assert_called_once_with(dir_path)
        mock_logger_info.assert_called_once_with(f"Directory {dir_path} deleted successfully.")

def test_post_process_cleanup_directory_does_not_exist():
    repo_info = {
        'owner': 'repo_owner',
        'repo_name': 'repo_name'
    }

    with patch('os.path.exists', return_value=False), \
            patch('logging.Logger.info') as mock_logger_info:
        post_process_cleanup(repo_info)
        mock_logger_info.assert_not_called()

def test_post_process_cleanup_not_a_directory():
    repo_info = {
        'owner': 'repo_owner',
        'repo_name': 'repo_name'
    }
    dir_path = os.path.join('repos', repo_info['owner'], repo_info['repo_name'])

    with patch('os.path.exists', return_value=True), \
            patch('os.path.isdir', return_value=False), \
            patch('shutil.rmtree') as mock_rmtree, \
            patch('logging.Logger.info') as mock_logger_info:
        post_process_cleanup(repo_info)
        mock_rmtree.assert_not_called()
        mock_logger_info.assert_not_called()

def test_post_process_cleanup_exception():
    repo_info = {
        'owner': 'repo_owner',
        'repo_name': 'repo_name'
    }
    dir_path = os.path.join('repos', repo_info['owner'], repo_info['repo_name'])

    with patch('os.path.exists', return_value=True), \
            patch('os.path.isdir', return_value=True), \
            patch('shutil.rmtree', side_effect=Exception('Test exception')), \
            patch('logging.Logger.error') as mock_logger_error:
        post_process_cleanup(repo_info)
        mock_logger_error.assert_called_once_with(f"An error occurred while deleting the directory: Test exception")

def test_write_file_for_report_processing_success():
    repo_name = "test_repo"
    issue_content = "This is a test issue content."
    reports_dir = os.path.join('reports', repo_name)
    report_file_path = os.path.join(reports_dir, 'report.txt')

    with patch('os.makedirs') as mock_makedirs, \
            patch('builtins.open', new_callable=MagicMock) as mock_open, \
            patch('logging.Logger.info') as mock_logger_info:
        result = write_file_for_report_processing(repo_name, issue_content)
        mock_makedirs.assert_called_once_with(reports_dir, exist_ok=True)
        mock_open.assert_called_once_with(report_file_path, 'w', encoding='utf-8')
        mock_logger_info.assert_called_once_with(f"Issue written to {report_file_path}.")
        assert result == report_file_path

def test_write_file_for_report_processing_exception():
    repo_name = "test_repo"
    issue_content = "This is a test issue content."
    reports_dir = os.path.join('reports', repo_name)
    report_file_path = os.path.join(reports_dir, 'report.txt')

    with patch('os.makedirs') as mock_makedirs, \
            patch('builtins.open', new_callable=MagicMock) as mock_open, \
            patch('logging.Logger.error') as mock_logger_error:
        mock_open.side_effect = Exception("Test exception")
        try:
            write_file_for_report_processing(repo_name, issue_content)
        except Exception as e:
            assert str(e) == "Test exception"
        mock_makedirs.assert_called_once_with(reports_dir, exist_ok=True)
        mock_open.assert_called_once_with(report_file_path, 'w', encoding='utf-8')
        mock_logger_error.assert_called_once_with(f"Failed to write issue to file: Test exception")

def test_change_repository_file_permissions():
    repo_dir = "test_repo_dir"

    with patch('os.chmod') as mock_chmod, \
            patch('os.walk', return_value=[(repo_dir, ['subdir'], ['file1', 'file2'])]) as mock_walk:
        change_repository_file_permissions(repo_dir)
        
        # Check if chmod was called for the repo_dir
        mock_chmod.assert_any_call(repo_dir, S_IWUSR | S_IREAD)
        
        # Check if chmod was called for subdirectories and files
        mock_chmod.assert_any_call(os.path.join(repo_dir, 'subdir'), S_IWUSR | S_IREAD)
        mock_chmod.assert_any_call(os.path.join(repo_dir, 'file1'), S_IWUSR | S_IREAD)
        mock_chmod.assert_any_call(os.path.join(repo_dir, 'file2'), S_IWUSR | S_IREAD)

def test_change_repository_file_permissions_with_no_subdirs_or_files():
    repo_dir = "test_repo_dir"

    with patch('os.chmod') as mock_chmod, \
            patch('os.walk', return_value=[(repo_dir, [], [])]) as mock_walk:
        change_repository_file_permissions(repo_dir)
        
        # Check if chmod was called for the repo_dir
        mock_chmod.assert_any_call(repo_dir, S_IWUSR | S_IREAD)
        
        # Ensure chmod was not called for any subdirectories or files
        assert mock_chmod.call_count == 1

def test_extract_and_validate_repo_info_success():
    data = {
        'repo_url': 'https://github.com/example/repo.git',
        'owner': 'repo_owner',
        'repo_name': 'repo_name',
        'default_branch': 'main',
        'latest_commit_sha': 'abc123'
    }

    expected_repo_info = {
        'repo_url': 'https://github.com/example/repo.git',
        'owner': 'repo_owner',
        'repo_name': 'repo_name',
        'default_branch': 'main',
        'latest_commit_sha': 'abc123'
    }

    with patch('logging.Logger.debug') as mock_logger_debug:
        result = extract_and_validate_repo_info(data)
        assert result == expected_repo_info, f"Expected {expected_repo_info}, but got {result}"
        mock_logger_debug.assert_any_call("Extracting and validating repository information.")
        mock_logger_debug.assert_any_call(f"Validated repository information: {expected_repo_info}")

def test_extract_and_validate_repo_info_missing_fields():
    data = {
        'repo_url': 'https://github.com/example/repo.git',
        'owner': 'repo_owner',
        'repo_name': 'repo_name',
        'default_branch': 'main'
    }

    with pytest.raises(HTTPException) as exc_info:
        extract_and_validate_repo_info(data)
        
        # Extract the raised exception to verify details
        assert exc_info.value.code == 400
        assert exc_info.value.description == "Missing required repository information: latest_commit_sha"

def test_extract_and_validate_repo_info_empty_data():
    data = {}

    with pytest.raises(HTTPException) as exc_info:
        extract_and_validate_repo_info(data)
        
        # Extract the raised exception to verify details
        assert exc_info.value.code == 400
        assert exc_info.value.description == "Missing required repository information: repo_url, owner, repo_name, default_branch, latest_commit_sha"