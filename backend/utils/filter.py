from pathlib import Path
from stat import S_IWUSR, S_IREAD

def filter_files(repo_path: str):
    """
    Filters out non-Java files from the input path.

    Args:
        repo_path (str): The path to the repository ("repos/username/repo_name")

    Returns:
        List[Path]: A list of Path objects representing Java files
    """

    repo = Path(repo_path)

    # Validate input directory
    if not repo.is_dir():
        raise ValueError(f"{repo_path} is not a valid directory.")
    
    # List of Java files
    java_files = []

    # Recursively visit subdirectories
    for file in repo.rglob("*"):
        if file.is_file():
            # Remove hidden files
            file.chmod(S_IWUSR | S_IREAD)
            if file.name.startswith('.'):
                file.unlink()
            # Add Java files to list
            elif file.suffix == ".java":
                java_files.append(file)
            # Delete non-Java files
            else:
                file.unlink()
    
    # Delete empty directories in reverse order
    # Sort paths based on depth and delete children first before parents
    for dir_path in sorted(repo.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            dir_path.rmdir()

    return java_files