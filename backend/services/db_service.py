from datetime import datetime
import logging
import os

import chardet
from flask import abort, jsonify
from services.message_service import send_update_to_probot
from utils.preprocess_source_code import preprocess_source_code
from utils.file_utils import clean_embedding_paths_for_db
from database.database import Database

db = Database()
logger = logging.getLogger(__name__)

def fetch_all_embeddings(repo_info, comment_id):
    try:
        query = {
            "repo_name": repo_info['repo_name'],
            "owner": repo_info['owner']
        }
        repo_collection = db.get_repo_collection()
        query_repo = repo_collection.find_one(query)
        repo_embeddings = db.get_repo_files_embeddings(query_repo["_id"])
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Repository Embeddings Fetched**: Retrieved all repository embeddings from the database.")
        
        return repo_embeddings
    except Exception as e:
        logger.info('Failed to find repo.')
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "❌ **Repository Embeddings Retrieval Failed**: Could not fetch all repository embeddings from the database.")
        return jsonify({"message": "Failed to find repo."}), 405

def fetch_corpus_embeddings(repo_info, corpus, comment_id):
    try:
        query = {
            "repo_name": repo_info['repo_name'],
            "owner": repo_info['owner']
        }
        repo_collection = db.get_repo_collection()
        query_repo = repo_collection.find_one(query)
        corpus_embeddings = db.get_corpus_files_embeddings(query_repo["_id"], corpus)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Corpus Embeddings Fetched**: Retrieved all corpus embeddings from the database.")
        
        return corpus_embeddings;

    except Exception as e:
        logger.info('Failed to find repo.')
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "❌ **Corpus Embeddings Retrieval Failed**: Could not fetch corpus embeddings from the database.")
        return jsonify({"message": "Failed to find repo."}), 405
    
def update_sha(repo_info):
    db.get_repo_collection().update_one(
        {'repo_name': repo_info['repo_name'], 'owner': repo_info['owner']},
        {
            "$set": {
                "commit_sha": repo_info['latest_commit_sha']
            }
        },
        upsert=False
    )
    logger.info(f"Updated commit SHA to {repo_info['latest_commit_sha']} in the database.")

def update_embeddings_in_db(changed_files, clean_files, repo_info):
    repo_id = db.get_repo_collection().find_one({'repo_name': repo_info['repo_name'], 'owner': repo_info['owner']})[
        '_id']
    logger.info(f"Retrieved repo id : {repo_id}")

    # Add and update embeddings
    for clean_file in clean_files:
        file_path = clean_file['path']
        embedding = clean_file['embedding_text']

        # Upsert the document in the embeddings collection
        db.get_embeddings_collection().update_one(
            {"repo_id": repo_id, "route": file_path},
            {
                "$set": {
                    "embedding": embedding,
                    "last_updated": datetime.utcnow().isoformat() + 'Z'
                }
            },
            upsert=True
        )
        logger.info(f"Upserted embedding for file: {file_path}")

    # Remove embeddings
    for file_path in changed_files.get("removed", []):
        db.get_embeddings_collection().delete_one({"repo_id": repo_id, "route": file_path})
        logger.info(f"Removed embedding for file: {file_path}")

    logger.info("Database updated with added, modified, and removed files.")

def send_initialized_data_to_db(repo_info, code_files, filtered_files):
    """
    Stores the repo document in the 'repos' collection and each code file document in the 'code_files' collection.

    :param repo_info: Repository metadata to store in 'repos' collection.
    :param code_files: List of code files with embeddings to store in 'code_files' collection.
    :raises: Exception if storage fails.
    """
    logger.debug("Storing repo information and embeddings in MongoDB.")
    try:
        # Insert or update the repository information in 'repos' collection
        repo = db.get_repo_collection().find_one_and_replace(
            {'repo_name': repo_info['repo_name'], 'owner': repo_info['owner']},
            repo_info,
            upsert=True,
            return_document=True  # Retrieve the updated document
        )
        repo_id = repo['_id']  # Get the `_id` field of the repository document

        # Insert files to code collection here
        for file_path in map(str, filtered_files):
            insert_to_code_db(file_path, repo_id)

        # Use the repository `_id` (repo_id) as a foreign key in `code_files` collection
        for file_info in code_files:
            file_info['repo_id'] = repo_id  # Add the repo_id reference to each code file document

            # Insert or update each code file's embedding in 'code_files' collection
            db.get_embeddings_collection().replace_one(
                {'repo_id': repo_id, 'route': file_info['route']},
                file_info,
                upsert=True
            )
            logger.info(f"Stored embedding for file: {file_info['route']}")

        logger.info('Repo and code file embeddings stored in database successfully.')
    except Exception as e:
        logger.error(f"Failed to store embeddings in database: {e}")
        raise


def retrieve_stored_sha(owner, repo_name):
    """
    Retrieves the stored commit SHA for the specified repository.

    :param owner: The repository owner's username.
    :param repo_name: The repository name.
    :return: The stored commit SHA or None if not found.
    :raises: Aborts the request with a 500 error if retrieval fails.
    """
    logger.debug(f"Retrieving stored SHA for {owner}/{repo_name}.")
    try:
        stored_commit_sha = retrieve_sha_from_db(owner, repo_name)
    except Exception:
            abort(500, description="Failed to retrieve commit SHA from database.")

    if stored_commit_sha:
        logger.debug(f"Stored commit SHA: {stored_commit_sha}")
    else:
        logger.debug("No stored commit SHA found.")

    return stored_commit_sha

def retrieve_sha_from_db(owner, repo_name):
    """
    Retrieves the stored commit SHA for the specified repository from MongoDB.

    :param owner: The repository owner's username.
    :param repo_name: The repository name.
    :return: The stored commit SHA or None if not found.
    :raises: Exception if retrieval fails.
    """
    logger.debug(f"Retrieving stored SHA for {owner}/{repo_name} from MongoDB.")
    try:
        existing_embedding = db.get_repo_collection().find_one(
            {'repo_name': repo_name, 'owner': owner},
            sort=[('stored_at', -1)]  # Get the latest record
        )
        if existing_embedding:
            stored_commit_sha = existing_embedding.get('commit_sha')
            logger.debug(f"Retrieved stored SHA from database: {stored_commit_sha}")
            return stored_commit_sha
        else:
            logger.debug("No matching embedding found in database.")
            return None
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise

def insert_to_code_db(route, repo_id):
    try:
        # Read file in binary mode to detect encoding
        with open(route, "rb") as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            print(f"Detected encoding for {route}: {encoding}")

        # Now open the file using the detected encoding
        with open(route, "r", encoding=encoding) as file:
            code_content = file.read()
            print("Code content successfully read.")

    except FileNotFoundError:
        logger.info(f"Error: The file at {route} was not found.")
    except IOError as e:
        logger.info(f"Error reading the file: {e}")
    except UnicodeDecodeError as e:
        logger.info(f"Error decoding file {route} with encoding {encoding}: {e}")

    # Create the document to store in the database
    code_file_document = {
        'repo_id' : repo_id,
        'route': route,
        'code content': code_content,
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }

    # Store file content in the database
    db.get_files_collection().replace_one(
        {'repo_id': repo_id, 'route': route},
        code_file_document,
        upsert=True
    )
    logger.info(f"Stored code for file: {route}")

def process_and_patch_embeddings(changed_files, repo_info):
    """
    Processes the repository by cloning, computing embeddings, and storing them. Always performs a fresh setup.

    :param repo_info: Dictionary containing repository information.
    """
    repo_dir = os.path.join('repos', repo_info['owner'], repo_info['repo_name'])

    # Add updating to the files db here
    repo_id = db.get_repo_collection().find_one({'repo_name': repo_info['repo_name'], 'owner': repo_info['owner']})['_id']

    for change_type, files in changed_files.items():
        for file in files:
            route = str(file)
            route = os.path.join(repo_dir, route)

            if change_type == 'removed':
                db.get_files_collection().delete_one(
                    {'repo_id': repo_id, 'route': route}
                )

            else:
                insert_to_code_db(route, repo_id)

    # Preprocess the changed source code files
    preprocessed_files = preprocess_source_code(repo_dir)

    for file in preprocessed_files:
        logger.info(f"Preprocessed changed file: {file}")

    clean_files = clean_embedding_paths_for_db(preprocessed_files, repo_dir)
    update_embeddings_in_db(changed_files, clean_files, repo_info)
    update_sha(repo_info)

def retrieve_repo_file_contents(query):
    repo_collection = db.get_repo_collection()
    query_repo = repo_collection.find_one(query)
    repo_files = db.get_repo_file_contents(query_repo["_id"])

    return repo_files