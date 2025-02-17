from app.api.routes import reorder_rankings
from app.api.routes import create_changed_files_dict
from app.api.routes import extract_files
from app.api.routes import post_process_cleanup
from app.api.routes import write_file_for_report_processing

from unittest.mock import MagicMock, patch
import zipfile
import os
from app.api.routes import post_process_cleanup
import shutil
from unittest.mock import patch, MagicMock

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