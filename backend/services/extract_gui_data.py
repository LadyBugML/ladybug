import glob
import json
import re

def extract_sc_terms(json_path: str):
    """
    Extracts all Screen Components terms from the Execution.json. Assumes that the buggy state is the last state in the trace.
    The returned list has NOT yet been preprocessed, so terms include underscores and other puctuation.
    Args: 
        json_path (str): Path to the Execution.json on the server

    Returns:
        List[str]: List of strings representing SC terms
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

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

def extract_gs_terms(json_path: str):
    """
    Extracts all GUI Screen terms from the Execution.json. Assumes that the buggy state is the last state in the trace.

    Args: 
        json_path (str): Path to the Execution.json on the server

    Returns:
        List[str]: List of strings representing GS terms
    """

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

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
        if gs_window:
            gs_terms.add(gs_window.group(1))

    return list(gs_terms)

def check_if_term_exist(search_terms, file_content):
    """
    Checks if any search terms (SC or GS terms) exist in the contents of a file. This function does NOT map
    any search terms to file paths.
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

def map_sc_terms_to_files(java_files_data: list[dict], sc_terms: list[str]):
    """
    Maps SC terms to files using a brute force approach.

    Args: 
        java_files_data (list[dict]): A list of dictionaries where each dictionary represents a file with its path and contents

    Returns: 
        sc_files (list[str]): A list of strings with each string being the file path of a mapped SC file
    """
    sc_files = []
    for file_data in java_files_data:
        search_term_exist = check_if_term_exist(sc_terms, file_data["contents"])

        if search_term_exist == True:
            sc_files.append(file_data["path"])

    return sc_files