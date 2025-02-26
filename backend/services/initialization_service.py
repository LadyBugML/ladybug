from datetime import datetime
import logging
import os
from flask import abort, jsonify
from services.db_service import send_initialized_data_to_db
from services.messenger_service  import ProbotMessenger
from utils.preprocess_source_code import preprocess_source_code
from utils.file_utils import clean_embedding_paths_for_db, post_process_cleanup
from utils.filter import filter_files
from utils.git_utils import clone_repo, extract_and_validate_repo_info

logger = logging.getLogger(__name__)


def initialize(data):
    repo_data = data.get('repoData')
    comment_id = data.get('comment_id', -1)
    repo_info = extract_and_validate_repo_info(repo_data)
    messenger = ProbotMessenger(repo_info, comment_id)

    messenger.send("init_start")
    try:
        process_and_store_embeddings(repo_info, messenger)
        messenger.send("cloning_repo")
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        messenger.send("init_failed", error=str(e))
        abort(500, description=str(e))
    try:
        post_process_cleanup(repo_info)
        messenger.send("embeddings_stored")
    except Exception as e:
        logger.error(f"Post-processing failed: {e}")
        messenger.send("post_processing_warning", error=str(e))
    logger.info('Embeddings stored successfully.')
    messenger.send("init_complete")
    return jsonify({"message": "Embeddings computed and stored"}), 200


def process_and_store_embeddings(repo_info, messenger):
    repo_dir = os.path.join('repos', repo_info['owner'], repo_info['repo_name'])
    clone_repo(repo_info['repo_url'], repo_dir)
    messenger.send("cloning_complete")
    filtered_files = filter_files(repo_dir)
    for file in filtered_files:
        logger.info(f"Filtered file: {file}")
    if not filtered_files:
        logger.error("No Java files found in repository.")
        messenger.send("no_java_files")
        raise ValueError("No Java files found in repository.")

    # Preprocess the source code files
    preprocessed_files = preprocess_source_code(repo_dir)
    messenger.send("embeddings_calculated")
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
    messenger.send("storing_embeddings")
    send_initialized_data_to_db(repo_document, code_file_documents, filtered_files)
