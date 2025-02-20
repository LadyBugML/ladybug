import logging
import os
import shutil
from stat import S_IREAD, S_IWUSR


logger = logging.getLogger(__name__)

def post_process_cleanup(repo_info):
    dir_path = os.path.join('repos', repo_info['owner'], repo_info['repo_name'])
    try:
        if os.path.exists(dir_path):
            if os.path.isdir(dir_path):
                shutil.rmtree(dir_path)
                logger.info(f"Directory {dir_path} deleted successfully.")
    except Exception as e:
        logger.error(f"An error occurred while deleting the directory: {e}")

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