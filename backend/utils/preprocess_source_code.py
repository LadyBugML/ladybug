from pathlib import Path
from utils.preprocess import Preprocessor

def preprocess_source_code(root, verbose=True):
    """
    Preprocesses all source code files in a source code repository. Assumes all files contained
    in the root directory have had non-.java files filtered out.

    Args:
        root (string): path to the root directory of the source code repository

    Returns:
        tuple (list): list of tuples mapping file name to preprocessed contents
    """

    preprocessor = Preprocessor()

    preprocessed_files = []

    repo = Path(root)

    # Traverse the root directory
    for file_path in repo.rglob("*"):
        if file_path.is_file():
            # Read and preprocess source code file and append it to the output list
            try: 
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                    preprocessed_file_content = preprocessor.preprocess_text(file_content, verbose=verbose, bug_report=False)
                    preprocessed_files.append((file_path, file_path.name, preprocessed_file_content))
            except FileNotFoundError:
                print(f"Error: The source code file at '{file_path}' was not found.")
                return

    return preprocessed_files