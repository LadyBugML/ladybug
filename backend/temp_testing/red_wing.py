from extract_gui_data import extract_gs_terms, extract_sc_terms
from backend.utils.preprocess_source_code import preprocess_source_code
from backend.utils.filter import filter_files
import json

def process_repo(projects_path):
    """
    Assumes projects_path is the root directory containing all the projects.
    
    """
    trace_path = 'f{projects_path}/trace/Execution-1.json'
    with open(trace_path, 'r') as f:
        trace = json.load(f)

    print(trace)

    sc_terms = extract_sc_terms(trace)
    gs_terms = extract_gs_terms(trace)

    filtered_files = filter_files(projects_path)
    preprocessed_files = preprocess_source_code(projects_path)

process_repo("~/senior-design/BuggyProjects/bug-2")