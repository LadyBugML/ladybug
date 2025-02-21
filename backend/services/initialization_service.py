from datetime import datetime
import logging
import os

from flask import abort, jsonify
from services.db_service import send_initialized_data_to_db
from services.message_service import send_update_to_probot
from utils.preprocess_source_code import preprocess_source_code
from utils.file_utils import clean_embedding_paths_for_db, post_process_cleanup
from utils.filter import filter_files
from utils.git_utils import clone_repo, extract_and_validate_repo_info

logger = logging.getLogger(__name__)

def initialize(data):

    repo_data = data.get('repoData')
    comment_id = data.get('comment_id')
    if comment_id is None:
        comment_id = -1

    repo_info = extract_and_validate_repo_info(repo_data)
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "✅ **Initialization Started**: Validating repository information.")

    try:
        process_and_store_embeddings(repo_info, comment_id)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Cloning Repository**: Repository cloned successfully.")
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              f"❌ **Initialization Failed**: {e}")
        abort(500, description=str(e))

    try:
        post_process_cleanup(repo_info)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Embeddings Stored**: Embeddings computed and stored successfully.")
    except Exception as e:
        logger.error(f"Post-processing failed: {e}")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              f"⚠️ **Post-Processing Warning**: {e}")

    logger.info('Embeddings stored successfully.')
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "✅ **Initialization Completed**: All embeddings are up to date.")
    return jsonify({"message": "Embeddings computed and stored"}), 200

def process_and_store_embeddings(repo_info, comment_id):
    """
    Processes the repository by cloning, computing embeddings, and storing them. Always performs a fresh setup.

    :param repo_info: Dictionary containing repository information.
    :param comment_id: Comment ID.
    """
    repo_dir = os.path.join('repos', repo_info['owner'], repo_info['repo_name'])

    clone_repo(repo_info['repo_url'], repo_dir)
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], repo_info.get('comment_id'),
                          "✅ **Cloning Completed**: Repository cloned successfully.")

    filtered_files = filter_files(repo_dir)
    for file in filtered_files:
        logger.info(f"Filtered file: {file}")

    if not filtered_files:
        logger.error("No Java files found in repository.")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], repo_info.get('comment_id'),
                              "⚠️ **No Java Files Found**: No `.java` files detected in the repository.")
        raise ValueError("No Java files found in repository.")

    # Preprocess the source code files
    preprocessed_files = preprocess_source_code(repo_dir)
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "✅ **Embeddings Calculated**: Wow that took a while huh.")
    for file in preprocessed_files:
        logger.info(f"Preprocessed file: {file}")

    # Clean data
    clean_paths = clean_embedding_paths_for_db(preprocessed_files, repo_dir)

    # Create repo document
    repo_document = {
        'repo_name': repo_info['repo_name'],
        'owner': repo_info['owner'],
        'commit_sha': repo_info['latest_commit_sha'],
        'stored_at': datetime.utcnow().isoformat() + 'Z'
    }

    # Create embedddings documents
    code_file_documents = [
        {
            'route': file['path'],
            'embedding': file['embedding_text'],
            'last_updated': datetime.utcnow().isoformat() + 'Z'
        }
        for file in clean_paths
    ]

    # Store repo and embeddings
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], repo_info.get('comment_id'),
                          "✅ **Storing Embeddings**: Storing repository information and embeddings in the database.")
    send_initialized_data_to_db(repo_document, code_file_documents, filtered_files)