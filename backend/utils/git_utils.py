import io
import logging
import os
import shutil
import zipfile
from flask import abort
from git import GitCommandError, Repo
import requests

from utils.file_utils import change_repository_file_permissions

logger = logging.getLogger(__name__)

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