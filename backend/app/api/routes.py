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

from database.database import Database
from services.utils.preprocess_bug_report import preprocess_bug_report
from services.utils.preprocess_source_code import preprocess_source_code
from services.utils.extract_gui_data import extract_gs_terms, extract_sc_terms, build_corpus, get_boosted_files
from services.utils.filter import filter_files
from experimental_unixcoder.bug_localization import BugLocalization

# Initialize Database
db = Database()

# Initialize Blueprint for Routes
routes = Blueprint('routes', __name__)

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Initialize a thread-safe queue for messages
message_queue = queue.Queue()

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
            # Get the repo document for the query     
            repo_collection = db.get_repo_collection()
            query_repo = repo_collection.find_one(query)
            repo_files = db.get_repo_file_contents(query_repo["_id"])     
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


# ======================================================================================================================
# Helper Functions
# ======================================================================================================================

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

def message_worker():
    """
    Background worker that sends messages to Probot from the message_queue.
    Ensures that each message is sent with at least a 5-second interval.
    """
    while True:
        try:
            # Get the next message from the queue
            owner, repo, comment_id, message = message_queue.get()
            if owner and repo and comment_id and message:
                success = actual_send_update_to_probot(owner, repo, comment_id, message)
                if success:
                    logger.info(f"Message sent to Probot: {message}")
                else:
                    logger.error(f"Failed to send message to Probot: {message}")

        except Exception as e:
            logger.error(f"Error in message_worker: {e}")


def actual_send_update_to_probot(owner, repo, comment_id, message):
    """
    Sends an update message to the Probot /post-message endpoint to comment on a GitHub issue or pull request.

    Args:
        owner (str): The GitHub username or organization name that owns the repository.
        repo (str): The name of the repository.
        comment_id (int): The number of the issue or pull request to comment on.
        message (str): The message to post as a comment.

    Returns:
        bool: True if the comment was posted successfully, False otherwise.
    """
    payload = {
        'owner': owner,
        'repo': repo,
        'comment_id': comment_id,
        'message': message
    }
    try:
        response = requests.post(f'{NODE_URL}/post-message', json=payload)
        response.raise_for_status()  # Raises stored HTTPError, if one occurred.

        logger.info(f"Successfully posted message to {owner}/{repo} Issue #{comment_id}: {message}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to post message to Probot: {e}")
        return False


def send_update_to_probot(owner, repo, comment_id, message):
    """
    Enqueues a message to be sent to Probot.

    Args:
        owner (str): The GitHub username or organization name that owns the repository.
        repo (str): The name of the repository.
        comment_id (int): The number of the issue or pull request to comment on.
        message (str): The message to post as a comment.
    """
    if comment_id == -1:
        return

    message_queue.put((owner, repo, comment_id, message))
    logger.debug(f"Enqueued message for Probot: {message}")


def partial_clone(old_sha, repo_info):
    """
    Clones the diff between two commits, applying pre-MVP filtering. Files are saved to the repos directory.

    :param old_sha: The current SHA stored in the database
    :param repo_info: Dictionary containing repository info
    :return changed_files: Dictionary of changed files and their change type (added, modified, removed)
    """
    repo_dir = os.path.join('repos', repo_info['owner'], repo_info['repo_name'])
    new_sha = repo_info['latest_commit_sha']

    github_diff_data = get_diff_from_github(repo_info, old_sha, new_sha)
    changed_files = create_changed_files_dict(github_diff_data, repo_dir)

    zip_archive = get_latest_repo_data_from_github(repo_info)

    extract_files(changed_files, zip_archive, repo_dir)

    return changed_files

def get_diff_from_github(repo_info, old_sha, new_sha):
    """
    Uses the GitHub API to compare commits between the current version of the repo on the server and the version on GitHub.

    Parameters:
        old_sha: The current SHA stored in the database
        new_sha: The SHA of the latest commit on GitHub
        repo_info: Dictionary containing repository info
    
    Returns:
        The JSON response from GitHub containing the diff between the two versions
    """

    url = f"https://api.github.com/repos/{repo_info['owner']}/{repo_info['repo_name']}/compare/{old_sha}...{new_sha}"
    logger.info(url)
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Failed to fetch diff from GitHub. Status Code: {response.status_code}")
        return None

def create_changed_files_dict(github_diff_data, repo_dir):
    """
    Creates a dictionary of changed files based on the GitHub API JSON response.

    Parameters:
        github_diff_data: A JSON object containing the diff between two repo versions

    Returns:
        A dictionary mapping change types to project file paths
    """

    # Check if 'files' key is present in response data
    if 'files' in github_diff_data:
        files = github_diff_data['files']

        # Filter files based on the `.java` extension
        changed_files = {
            "added": [f["filename"].replace(repo_dir + '/', '') for f in files if
                        f["status"] == "added" and f["filename"].endswith(".java")],
            "modified": [f["filename"].replace(repo_dir + '/', '') for f in files if
                            f["status"] == "modified" and f["filename"].endswith(".java")],
            "removed": [f["filename"].replace(repo_dir + '/', '') for f in files if
                        f["status"] == "removed" and f["filename"].endswith(".java")]
        }

        logger.info(f"Changed files: {changed_files}")
        return changed_files
    else:
        logger.error("Error: 'files' key not found in response data.")
        return None

def get_latest_repo_data_from_github(repo_info):
    """
    Gets the latest repo data as a zip file.

    :param repo_info: Dictionary containing repository info
    :return zip_archive: The zipfile of the repository at the latest commit
    """

    url = f"https://api.github.com/repos/{repo_info['owner']}/{repo_info['repo_name']}/zipball/{repo_info['latest_commit_sha']}"
    response = requests.get(url)

    if response.status_code == 200:
        return zipfile.ZipFile(io.BytesIO(response.content))
    else:
        print("Failed to download zip archive.")


def extract_files(changed_files, zip_archive, repo_dir):
    """
    Extracts filtered source code files from a zipfile.

    :param changed_files: Dictionary of changed files and their change type (added, modified, removed)
    :param zip_archive: Zipfile of the repository at the latest commit
    :param repo_dir: The directory of the repository.
    """
    os.makedirs(repo_dir, exist_ok=True)

    extracted_files = {}
    for change_type, file_list in changed_files.items():
        for file_path in file_list:
            try:
                zip_file_path = next((item for item in zip_archive.namelist() if item.endswith(file_path)), None)
                if file_path in changed_files['added'] or (file_path in changed_files['modified'] and zip_file_path):
                    with zip_archive.open(zip_file_path) as file:
                        file_content = file.read().decode("utf-8")
                        extracted_files[file_path] = file_content

                        # Write to output directory
                        output_path = os.path.join(repo_dir, file_path)
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)  # Create subdirectories if needed
                        with open(output_path, "w", encoding="utf-8") as out_file:
                            out_file.write(file_content)
            except KeyError:
                print(f"File {file_path} not found in archive.")


def post_process_cleanup(repo_info):
    dir_path = os.path.join('repos', repo_info['owner'], repo_info['repo_name'])
    try:
        if os.path.exists(dir_path):
            if os.path.isdir(dir_path):
                shutil.rmtree(dir_path)
                logger.info(f"Directory {dir_path} deleted successfully.")
    except Exception as e:
        logger.error(f"An error occurred while deleting the directory: {e}")


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


def clean_embedding_paths_for_db(preprocessed_files, repo_dir):
    """
    Cleans up the file paths for the database by removing the repo_dir prefix.

    :param preprocessed_files: List of preprocessed file tuples.
    :param repo_dir: The directory of the repository.
    """

    # This converts it into an easily printable form and removes the repo_dir prefix
    clean_files = []
    for file in preprocessed_files:
        clean_file = {
            'path': str(file[0]).replace(repo_dir + '/', ''),
            'name': file[1],
            'embedding_text': file[2]
        }
        clean_files.append(clean_file)
    return clean_files


def clone_repo(repo_url, repo_dir):
    """
    Clones the repository. If the repository directory already exists, it is purged before cloning.

    :param repo_url: The URL of the repository to clone.
    :param repo_dir: The directory where the repository will be cloned.
    :raises: GitCommandError if cloning fails.
    """
    logger.debug(f"Cloning repository from {repo_url} to {repo_dir}.")

    if os.path.exists(repo_dir):
        logger.info(f"Repository directory {repo_dir} exists. Purging for fresh clone.")
        change_repository_file_permissions(repo_dir)
        shutil.rmtree(repo_dir)

    try:
        Repo.clone_from(repo_url, repo_dir)
        logger.info('Repository cloned successfully.')
    except GitCommandError as e:
        logger.error(f"Failed to clone repository: {e}")
        raise


def write_file_for_report_processing(repo_name, issue_content):
    """
    Writes the issue content to a report file in the specified repository's report directory.

    :param repo_name: The name of the repository.
    :param issue_content: The content of the issue to write.
    :return: The path to the report file.
    :raises: Exception if writing to the file fails.
    """
    reports_dir = os.path.join('reports', repo_name)
    os.makedirs(reports_dir, exist_ok=True)  # Create the directory if it doesn't exist

    report_file_path = os.path.join(reports_dir, 'report.txt')
    try:
        with open(report_file_path, 'w', encoding='utf-8') as report_file:
            report_file.write(issue_content)
        logger.info(f"Issue written to {report_file_path}.")
        return report_file_path
    except Exception as e:
        logger.error(f"Failed to write issue to file: {e}")
        raise


def change_repository_file_permissions(repo_dir):
    """
    Changes the file permissions for all of the files in the repository directory, so that deletion can occur.
    :param repo_dir: The path of the repository.
    """

    os.chmod(repo_dir, S_IWUSR | S_IREAD)
    for root, dirs, files in os.walk(repo_dir):

        for subdir in dirs:
            os.chmod(os.path.join(root, subdir), S_IWUSR | S_IREAD)

        for file in files:
            os.chmod(os.path.join(root, file), S_IWUSR | S_IREAD)


def extract_and_validate_repo_info(data):
    """
    Extracts and validates repository information from the incoming request data.

    :param data: The JSON data from the request.
    :return: A dictionary containing repository information.
    :raises: aborts the request with a 400 error if validation fails.
    """
    logger.debug("Extracting and validating repository information.")

    # Extract repository information from data
    repo_url = data.get('repo_url')
    owner = data.get('owner')
    repo_name = data.get('repo_name')
    default_branch = data.get('default_branch')
    latest_commit_sha = data.get('latest_commit_sha')

    # Validate required fields
    if not all([repo_url, owner, repo_name, default_branch, latest_commit_sha]):
        missing = [field for field in ['repo_url', 'owner', 'repo_name', 'default_branch', 'latest_commit_sha']
                   if not data.get(field)]
        logger.error(f"Missing required repository information: {', '.join(missing)}")
        abort(400, description=f"Missing required repository information: {', '.join(missing)}")

    repo_info = {
        'repo_url': repo_url,
        'owner': owner,
        'repo_name': repo_name,
        'default_branch': default_branch,
        'latest_commit_sha': latest_commit_sha
    }

    logger.debug(f"Validated repository information: {repo_info}")
    return repo_info


# ======================================================================================================================
# Handler Methods
# ======================================================================================================================
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


# ======================================================================================================================
# Live Database (MongoDB) Methods
# ======================================================================================================================

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

def reorder_rankings(ranked_files: list[tuple], gs_files: list[str]):
    """
    Boosts GS files to the top of the ranking while preserving their relative order.

    Parameters:
        ranked_files: List of tuples (route, similarity_score), sorted by similarity score.
        gs_files: List or set of routes that should be prioritized.

    Returns:
        boosted_rankings: A reordered list with gs_files at the top in their original order.
    """

    gs_ranked = [item for item in ranked_files if item[0] in gs_files]
    non_gs_ranked = [item for item in ranked_files if item[0] not in gs_files]

    return gs_ranked + non_gs_ranked

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

# Start the background worker thread
worker_thread = threading.Thread(target=message_worker, daemon=True)
worker_thread.start()
