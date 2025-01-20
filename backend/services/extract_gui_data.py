import json

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