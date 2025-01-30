import pytest
import mongomock
from database.database import Database  # Update with the actual module name

@pytest.fixture
def mock_database():
    """Fixture to create a mock instance of Database with a mocked MongoDB collection."""
    # Create a mock MongoDB client
    client = mongomock.MongoClient()
    db = client.test_db

    # Create test collections here
    mock_embeddings_collection = db.embeddings

    # Add test data into collections here
    mock_embeddings_collection.insert_many([
        {"repo_id": "12345", "route": "path/to/file1.java", "embedding": [0.1, 0.2, 0.3]},
        {"repo_id": "12345", "route": "path/to/file2.java", "embedding": [0.4, 0.5, 0.6]},
        {"repo_id": "12345", "route": "path/to/file3.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "12345", "route": "to/file4.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "12345", "route": "to/file5.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "12345", "route": "to/file6.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "12345", "route": "to/file7.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "12345", "route": "to/file8.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "12345", "route": "file9.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "12345", "route": "file10.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "2345345", "route": "file10.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "3453467", "route": "file10.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "234234", "route": "file10.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "56785", "route": "file10.java", "embedding": [0.7, 0.8, 0.9]},
        {"repo_id": "21345", "route": "file10.java", "embedding": [0.7, 0.8, 0.9]},
    ])

    # Create Database instance and override the collections here
    database = Database()
    database._Database__embeddings = mock_embeddings_collection  # Override with mock collection

    return database

def test_get_corpus_files_embeddings(mock_database):
    repo_id = "12345"
    corpus = ["path/to/file1.java", "to/file5.java", "file10.java"] 

    expected_output = [
        ("path/to/file1.java", [0.1, 0.2, 0.3]),
        ("to/file5.java", [0.7, 0.8, 0.9]),
        ("file10.java", [0.7, 0.8, 0.9]),  
    ]

    result = mock_database.get_corpus_files_embeddings(repo_id, corpus)

    assert result == expected_output, f"Expected {expected_output}, got {result}"
