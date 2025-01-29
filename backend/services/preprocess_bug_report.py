import re
from services.preprocess import Preprocessor
from pathlib import Path

# Main driver method for preprocessing bug reports
def preprocess_bug_report(bug_report_path: str, sc_terms: list[str]):
    """
    Preprocesses bug reports and applies query reformulation (MVP)

    Args:
        bug_report_path (str): The path to the bug report

    Returns:
        String: The preprocessed bug report
    """
    preprocessor = Preprocessor()
    stop_words_path = Path(__file__).parent / "../data/stop_words/java-keywords-bugs.txt"

    # Put bug report content into a string
    try:
        with open(bug_report_path, "r") as file:
            bug_report_string = file.read()
    except FileNotFoundError:
        print(f"Error: The bug report at '{bug_report_path}' was not found.")
        return 

    # Remove JSON attachment link if exists in the bug report
    json_url_pattern = r'\[[^\]]*\]\(https?:\/\/github\.com\/\S*?\.json\S*\)'
    bug_report_string = re.sub(json_url_pattern, '', bug_report_string, flags=re.IGNORECASE)

    # Expand query with SC Terms
    for sc_term in sc_terms:
        bug_report_string += sc_term

    # Run bug report through preprocessor
    preprocessed_bug_report = preprocessor.preprocess_text(bug_report_string, stop_words_path)

    # Return preprocessed bug report as a string
    return preprocessed_bug_report