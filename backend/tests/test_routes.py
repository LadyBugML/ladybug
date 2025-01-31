from app.api.routes import reorder_rankings

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