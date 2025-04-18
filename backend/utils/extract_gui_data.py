import json
import re
import os

def extract_sc_terms(json_string: str):
    """
    Extracts all Screen Components terms from the Execution.json. Assumes that the buggy state is the last state in the trace.
    The returned list has NOT yet been preprocessed, so terms include underscores and other puctuation.
    Args: 
        json_path (str): Path to the Execution.json on the server

    Returns:
        List[str]: List of strings representing SC terms
    """
    # Return empty list of terms if the trace is empty
    if(json_string == None):
        return [];

    data = json.loads(json_string)

    last_4_steps = data["steps"][-4:]
    sc_terms = set()

    for step in last_4_steps:
        dyn_gui_components = step.get("screen", {}).get("dynGuiComponents", [])

        for component in dyn_gui_components:
            id_xml = component.get("idXml")
            
            # verify idXml is not None or empty and extract substring after the last "/"
            if id_xml:
                sc_term = id_xml.rsplit("/", 1)[-1] # rsplit splits once from the right
                if sc_term:  # verify sc term is not an empty string
                    sc_terms.add(sc_term)

    # remove unimportant words (check remove_keywords_from_query() function from helpers_code_mapping.py)
    unimportant_words = ["NO_ID","BACK_MODAL", "null"]
    for word in unimportant_words:
        sc_terms.discard(word)

    return list(sc_terms)

def extract_gs_terms(json_string: str):
    """
    Extracts all GUI Screen terms from the Execution.json. Assumes that the buggy state is the last state in the trace.

    Args: 
        json_path (str): Path to the Execution.json on the server

    Returns:
        List[str]: List of strings representing GS terms
    """
    
    # Return empty list of terms if the trace is empty
    if(json_string == None):
            return [];

    data = json.loads(json_string)

    # Get last 4 screens from the trace
    last_4_steps = data["steps"][-4:]
    gs_terms = set()

    # For each step extract step.screen.activity and/or step.screen.window value
    for step in last_4_steps:
        activity = step.get("screen", {}).get("activity", "")
        window = step.get("screen", {}).get("window", "")

        # Use Regex to match Activity name before (Window.*)
        gs_activity = re.search(r'(\w+)(\(Window.*\))', activity)
        if gs_activity:
            gs_terms.add(gs_activity.group(1))

        # Use Regex to match windows only if the FRAGMENT tag is present
        gs_window = re.search(r'FRAGMENT:(.+)', window)
        if gs_window and len(gs_window.group(1)) > 1:
            gs_terms.add(gs_window.group(1))

    return list(gs_terms)

def check_if_sc_term_exists(search_terms, file_content):
    """
    Checks if any SC terms exist in the contents of a file.
    Credit: Junayed Mahmud

    Args:
        search_terms (list[str]): A list of strings representing either SC or GS terms
        file_content (str): The contents of a Java file

    Returns:
        is_matched_keyword (bool): True if a search term was found in the file contents, otherwise false.
    """
    is_matched_keyword = False
    for keyword in search_terms:
        if keyword in file_content:
            is_matched_keyword = True

    return is_matched_keyword

def build_corpus(source_code_files: list[tuple], sc_terms: list[str], repo_info: None):
    """
    Maps SC terms to files using a brute force approach.

    Args: 
        source_code_files (list[tuple]): A list of source code file tuples that contain (file_path, file_name, file_content)

    Returns: 
        sc_files (list[str]): A list of strings with each string being the file path of a mapped SC file
    """

    repo_dir = os.path.join('repos', repo_info['owner'], repo_info['repo_name']) if repo_info else ''

    sc_files = []

    for file in source_code_files:
        search_term_exist = check_if_sc_term_exists(sc_terms, file[2])

        if search_term_exist:
            sc_files.append(file[0].replace(repo_dir + '/', '') if repo_info else file[0])

    return sc_files

def get_boosted_files(source_code_files: list[tuple], gs_terms: list[str]):
    """
    Maps GS terms to files via matching file names

    Args:
        source_code_files (list[tuple]): A list of source code file tuples that contain (file_path, file_name, file_content)
        gs_terms (list[str]): A list of screen names from execution data

    Returns:
        gs_files: List of file paths of matching gs_files that will be boosted 
    """
    gs_files = []

    # Go through each source code file
    for file in source_code_files:
        # Check if the file name matches any of the GS terms and add the file path
        if any(gs_term in file[1] for gs_term in gs_terms):
            gs_files.append(file[0])

    return gs_files