from app.api.routes import reorder_rankings
from app.api.routes import create_changed_files_dict

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