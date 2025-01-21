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

from services.fake_preprocess import Fake_preprocessor
from database.database import Database
from services.preprocess_bug_report import preprocess_bug_report
from services.preprocess_source_code import preprocess_source_code
from services.filter import filter_files
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

# ======================================================================================================================
# Routes
# ======================================================================================================================

@routes.route("/initialization", methods=["POST"])
def initialization():
    """
    Initialization Endpoint:
    - Clones the repository.
    - Computes embeddings.
    - Stores embeddings along with repository information and SHA.
    - Always performs a fresh setup, overwriting any existing embeddings.
    """
    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data")

    logger.info("Received data from /initialization request.")

    repo_data = data.get('repoData')
    comment_id = data.get('comment_id')

    repo_info = extract_and_validate_repo_info(repo_data)
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "✅ **Initialization Started**: Validating repository information.")

    try:
        process_and_store_embeddings(repo_info,comment_id)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "🌀 **Cloning Repository**: Repository cloned successfully.")
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
                          "🎉 **Initialization Completed**: All embeddings are up to date.")
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
    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data")

    repository = data.get('repository')
    issue = data.get('issue')
    comment_id = data.get('comment_id')

    if not repository or not issue or not comment_id:
        abort(400, description="Missing 'repository' or 'issue' in the data")

    logger.info("Received data from /report request.")

    # Extract and validate repository information
    repo_info = extract_and_validate_repo_info(repository)
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "✅ **Report Processing Started**: Repository information validated.")

    # Write issue to report file
    try:
        report_file_path = write_file_for_report_processing(repo_info['repo_name'], issue)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "📝 **Report Written**: Issue has been written to the report file.")
    except Exception as e:
        logger.error(f"Failed to write issue to file: {e}")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              f"❌ **Report Writing Failed**: {e}")
        abort(500, description="Failed to write issue to file")

    try:
        preprocessed_bug_report = preprocess_bug_report(report_file_path)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "🔍 **Bug Report Preprocessed**: Bug report has been successfully preprocessed.")
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
    # Check if embeddings are up to date
    if stored_commit_sha == repo_info['latest_commit_sha']:
        logger.info('Embeddings are up to date.')
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Embeddings Status**: Embeddings are up to date.")
    else:
        logger.info('Embeddings are outdated. Recomputing embeddings.')
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "🔄 **Embeddings Outdated**: Recomputing embeddings due to new commits.")
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

    # FETCH ALL EMBEDDINGS FROM DB
    try:
        query = {
            "repo_name": repo_info['repo_name'],
            "owner": repo_info['owner']
        }
        repo_collection = db.get_repo_collection()
        query_repo = repo_collection.find_one(query)
        repo_embeddings = db.get_repo_files_embeddings(query_repo["_id"])
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "📚 **Embeddings Fetched**: Retrieved all embeddings from the database.")
    except Exception as e:
        logger.info('Failed to find repo.')
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "❌ **Embeddings Retrieval Failed**: Could not fetch embeddings from the database.")
        return jsonify({"message": "Failed to find repo."}), 405

    bug_localizer = BugLocalization()

    ranked_files = bug_localizer.rank_files(preprocessed_bug_report, repo_embeddings)

    ranked_list = []

    for i in range(min(10, len(ranked_files))):
        ranked_list.append(ranked_files[i])

    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "🎯 **Bug Localization Completed**: Ranked relevant files identified.")
    return jsonify({"message": "Report processed successfully", "ranked_files": ranked_list}), 200


# ======================================================================================================================
# Helper Functions
# ======================================================================================================================

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
            # Wait for 5 seconds before sending the next message
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error in message_worker: {e}")
            # Optional: Add a short sleep to prevent tight loop in case of continuous errors
            time.sleep(5)

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
        response = requests.post('http://localhost:3000/post-message', json=payload)
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
    changed_files = get_changed_files(repo_info, old_sha, new_sha, repo_dir)
    zip_archive = get_zip_archive(repo_info)

    extract_files(changed_files, zip_archive, repo_dir)

    return changed_files


def get_changed_files(repo_info, old_sha, new_sha, repo_dir):
    """
    Gets the diff between two commits and applies filtering.

    :param old_sha: The current SHA stored in the database
    :param new_sha: The SHA of the latest commit on GitHub
    :param repo_info: Dictionary containing repository info
    :return changed_files: Dictionary of changed files and their change type (added, modified, removed)
    """
    url = f"https://api.github.com/repos/{repo_info['owner']}/{repo_info['repo_name']}/compare/{old_sha}...{new_sha}"
    logger.info(url)
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        # Check if 'files' key is present in response data
        if 'files' in data:
            files = data['files']

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
            print("Error: 'files' key not found in response data.")
            return None
    else:
        print(f"Failed to fetch diff from GitHub. Status Code: {response.status_code}")
        return None


def get_zip_archive(repo_info):
    """
    Fetches the zipfile of the repository at the latest commit

    :param repo_info: Dictionary containing repository info
    :return zip_archive: The zipfile of the repository at the latest commit
    """
    # Download repo at the latest commit
    url = f"https://api.github.com/repos/{repo_info['owner']}/{repo_info['repo_name']}/zipball/{repo_info['latest_commit_sha']}"
    response = requests.get(url)

    if response.status_code == 200:
        zip_archive = zipfile.ZipFile(io.BytesIO(response.content))
        return zip_archive
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
                          "🌀 **Cloning Completed**: Repository cloned successfully.")

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
                          "📝 **Embeddings Calculated**: Wow that took a while huh.")
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
                          "📚 **Storing Embeddings**: Storing repository information and embeddings in the database.")
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
        for file_path in map(str, filtered_files):  # Explicitly convert each file_path to a string
            # Now, file_path is guaranteed to be a string
            try:
                # Read file in binary mode to detect encoding
                with open(file_path, "rb") as file:  # Open file in binary mode
                    raw_data = file.read()  # Read raw bytes from the file
                    result = chardet.detect(raw_data)  # Detect encoding
                    encoding = result['encoding']  # Get the detected encoding
                    print(f"Detected encoding for {file_path}: {encoding}")
                
                # Now open the file using the detected encoding
                with open(file_path, "r", encoding=encoding) as file:
                    code_content = file.read()
                    print("Code content successfully read.")
            
            except FileNotFoundError:
                logger.info(f"Error: The file at {file_path} was not found.")
            except IOError as e:
                logger.info(f"Error reading the file: {e}")
            except UnicodeDecodeError as e:
                logger.info(f"Error decoding file {file_path} with encoding {encoding}: {e}")
            
            # Create the document to store in the database
            code_file_document = {
                'repo_id' : repo_id,
                'route': file_path,  # file_path is now guaranteed to be a string
                'code content': code_content,
                'last_updated': datetime.utcnow().isoformat() + 'Z'
            }

            # Store file content in the database
            db.get_files_collection().replace_one(
                {'repo_id': repo_id, 'route': file_path},
                code_file_document,
                upsert=True
            )
            logger.info(f"Stored embedding for file: {file_path}")


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
        if db.USE_DATABASE:
            stored_commit_sha = retrieve_sha_from_db(owner, repo_name)
        else:
            stored_commit_sha = get_latest_sha_from_file_database(owner, repo_name)
    except Exception:
        if db.USE_DATABASE:
            abort(500, description="Failed to retrieve commit SHA from database.")
        else:
            abort(500, description="Failed to retrieve commit SHA from file.")

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


# ======================================================================================================================
# Local Database (File) Methods
# ======================================================================================================================

def get_latest_sha_from_file_database(owner, repo_name):
    """
    Retrieves the latest commit SHA for the specified repository from the local embeddings_records.txt file.

    :param owner: The repository owner's username.
    :param repo_name: The repository name.
    :return: The latest commit SHA or None if not found.
    """
    logger.debug(f"Fetching latest SHA for {owner}/{repo_name} from file.")

    filename = 'embeddings_records.txt'
    if not os.path.exists(filename):
        logger.info(f"Embeddings records file {filename} does not exist.")
        return None
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            for line in reversed(lines):  # Start from the end for the latest entry
                try:
                    record = json.loads(line)
                    if (record['owner'] == owner and
                            record['repo_name'] == repo_name):
                        logger.debug(f"Found matching record: {record}")
                        return record.get('commit_sha')
                except json.JSONDecodeError:
                    logger.warning("Encountered invalid JSON record in embeddings_records.txt.")
                    continue
    except Exception as e:
        logger.error(f"Error reading embeddings records file: {e}")
    return None


def store_embeddings_in_file_database(embeddings_document):
    """
    Stores the embeddings document in the local embeddings_records.txt file.
    Overwrites existing embeddings for the repository to ensure a fresh update.

    :param embeddings_document: The embeddings data to store.
    :raises: Exception if writing to the file fails.
    """
    logger.debug("Storing embeddings in local file.")

    filename = 'embeddings_records.txt'
    try:
        # Read existing records
        records = {}
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as file:
                for line in file:
                    try:
                        record = json.loads(line)
                        key = (record['owner'], record['repo_name'])
                        records[key] = record
                    except json.JSONDecodeError:
                        logger.warning("Encountered invalid JSON record in embeddings_records.txt.")
                        continue

        # Update the record for the current repository
        key = (embeddings_document['owner'], embeddings_document['repo_name'])
        records[key] = embeddings_document

        # Write all records back to the file
        with open(filename, 'w', encoding='utf-8') as file:
            for record in records.values():
                json_record = json.dumps(record)
                file.write(json_record + '\n')

        logger.info('Embeddings stored in text file successfully.')
    except Exception as e:
        logger.error(f"Failed to write to embeddings records file: {e}")
        raise


# Start the background worker thread
worker_thread = threading.Thread(target=message_worker, daemon=True)
worker_thread.start()

