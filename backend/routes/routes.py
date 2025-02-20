import logging
import os
import json
import time
import chardet

import requests
import shutil
import zipfile
import io
import requests
import queue
import threading

from flask import Blueprint, abort, request, jsonify
from git import Repo, GitCommandError
from datetime import datetime
from stat import S_IWUSR, S_IREAD
from dotenv import load_dotenv

from services.db_service import fetch_all_embeddings, fetch_corpus_embeddings, process_and_patch_embeddings, retrieve_repo_file_contents, retrieve_stored_sha
from services.initialization_service import process_and_store_embeddings
from services.message_service import send_update_to_probot
from services.report_service import reorder_rankings
from utils.file_utils import post_process_cleanup, write_file_for_report_processing
from utils.git_utils import extract_and_validate_repo_info, partial_clone
from database.database import Database
from utils.preprocess_bug_report import preprocess_bug_report
from utils.preprocess_source_code import preprocess_source_code
from utils.extract_gui_data import extract_gs_terms, extract_sc_terms, build_corpus, get_boosted_files
from utils.filter import filter_files
from experimental_unixcoder.bug_localization import BugLocalization

# Initialize Blueprint for Routes
routes = Blueprint('routes', __name__)

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
NODE_URL = os.environ.get("NODE_URL") or "http://localhost:3000"
print("NODE_URL: ", NODE_URL)

# ======================================================================================================================
# Routes
# ======================================================================================================================
@routes.route('/')
def index():
    return "Hello, World!"

@routes.route("/initialization", methods=["POST"])
def initialization():
    """
    Initialization Endpoint:
    - Clones the repository.
    - Computes embeddings.
    - Stores embeddings along with repository information and SHA.
    - Always performs a fresh setup, overwriting any existing embeddings.
    """
    """
    Post Initialization Example:
    POST localhost:5000/initialization
    RAW JSON:
    {
    "repoData": {
        "repo_url": "https://github.com/LadyBugML/ladybug-data-android",
        "owner": "LadyBugML",
        "repo_name": "ladybug-data-android",
        "default_branch": "main",
        "latest_commit_sha": "3b54e17143c9906585fc0df1b4d2a3f969a2de5a"
        }
    } 
    """

    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data")

    logger.info("Received data from /initialization request.")
    print(data)
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


@routes.route('/report', methods=["POST"])
def report():
    """
    Report Endpoint:
    - Receives repository information with the latest_commit_sha.
    - Writes the 'issue' to ./reports/repo_name/report.txt.
    - Preprocesses the bug report.
    - Checks if the provided SHA matches the stored SHA.
    - If SHAs do not match:
        - Reclones the repository.
        - Recomputes embeddings.
        - Updates the stored embeddings and SHA.
    - If SHAs match:
        - Confirms that embeddings are up to date.
    """
    GUI_DATA = True

    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data")

    repository = data.get('repository')
    issue = data.get('issue')
    trace = data.get('trace')
    comment_id = data.get('comment_id')
    if comment_id is None:
        comment_id = -1

    if not repository or not issue:
        abort(400, description="Missing 'repository' or 'issue' in the data")

    logger.info("Received data from /report request.")

    # Extract Screen Component / GUI Screen Terms for boosting and query expansion
    sc_terms = extract_sc_terms(trace)
    gs_terms = extract_gs_terms(trace)

    if not gs_terms or not sc_terms:
        GUI_DATA = False
        logger.info("No GUI Data Detected")


    # Extract and validate repository information
    repo_info = extract_and_validate_repo_info(repository)
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "✅ **Report Processing Started**: Repository information validated.")

    # Write issue to report file
    try:
        report_file_path = write_file_for_report_processing(repo_info['repo_name'], issue)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Report Written**: Issue has been written to the report file.")
    except Exception as e:
        logger.error(f"Failed to write issue to file: {e}")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              f"❌ **Report Writing Failed**: {e}")
        abort(500, description="Failed to write issue to file")

    # Preprocess bug report
    try:
        preprocessed_bug_report = preprocess_bug_report(report_file_path, sc_terms)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Bug Report Preprocessed**: Bug report has been successfully preprocessed.")
    except Exception as e:
        logger.error(f"Failed to preprocess bug report: {e}")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              f"❌ **Preprocessing Failed**: {e}")
        abort(500, description="Failed to preprocess bug report")

    # Retrieve the stored SHA
    stored_commit_sha = retrieve_stored_sha(repo_info['owner'], repo_info['repo_name'])
    if not stored_commit_sha:
        logger.info("No stored commit SHA found.")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "⚠️ **SHA Retrieval Failed**: No stored commit SHA found.")
        return jsonify({"message": "Failed because no stored commit SHA"}), 500

    logger.info(f"Stored commit SHA: {stored_commit_sha}")

    # Check if embeddings and code file contents are up to date
    if stored_commit_sha == repo_info['latest_commit_sha']:
        logger.info('Embeddings are up to date.')
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Embeddings Status**: Embeddings are up to date.")
    else:
        logger.info('Embeddings are outdated. Recomputing embeddings.')
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Embeddings Outdated**: Recomputing embeddings due to new commits.")
        try:
            changed_files = partial_clone(stored_commit_sha, repo_info)
            process_and_patch_embeddings(changed_files, repo_info)
            post_process_cleanup(repo_info)
            send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                                  "✅ **Embeddings Updated**: Embeddings have been recomputed and updated.")
        except Exception as e:
            logger.error(f"Failed to recompute embeddings: {e}")
            send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                                  f"❌ **Embeddings Update Failed**: {e}")
            abort(500, description=str(e))
        
    # Initialize Bug Localizer and ranked list
    bug_localizer = BugLocalization()
    top_ten_files = []
    
    # Ranking generation with GUI data
    if(GUI_DATA):
        # Fetch all source code files from DB for filtering + boosting with GUI data
        try:
            query = {
                "repo_name": repo_info['repo_name'],
                "owner": repo_info['owner']
            }
            repo_files = retrieve_repo_file_contents(query)    
            send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                                "✅ **Source Code Files Fetched**: Retrieved all source code files from the database.")
        except Exception as e:
            logger.info('Failed to find repo.')
            send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                                "❌ **Source Code Retrieval Failed**: Could not fetch source code from the database.")
            return jsonify({"message": "Failed to find repo."}), 405

        # Apply filtering and get boosted files
        corpus = build_corpus(repo_files, sc_terms, repo_info)
        boosted_files = get_boosted_files(repo_files, gs_terms)

        # Fetch corpus embeddings from database
        corpus_embeddings = fetch_corpus_embeddings(repo_info, corpus, comment_id)

        # Apply boosting and create rankings
        ranked_files = bug_localizer.rank_files(preprocessed_bug_report, corpus_embeddings)
        reranked_files = reorder_rankings(ranked_files, boosted_files)

        # Only return top ten files
        for i in range(min(10, len(reranked_files))):
            top_ten_files.append(reranked_files[i])

    # Ranking generation without GUI data
    else:
        # Fetch all embeddings from DB
        repo_embeddings = fetch_all_embeddings(repo_info, comment_id)
        ranked_files = bug_localizer.rank_files(preprocessed_bug_report, repo_embeddings)

        # Only return top ten files
        for i in range(min(10, len(ranked_files))):
            top_ten_files.append(ranked_files[i])
        
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "⚠️ **Note**: Rankings have beeen calculated _without_ GUI Data. Consider submitting a trace to boost rankings!")

    # Return rankings to GitHub
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "🎯 **Bug Localization Completed**: Ranked relevant files identified.")
    return jsonify({"message": "Report processed successfully", "ranked_files": top_ten_files}), 200