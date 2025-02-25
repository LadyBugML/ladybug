from pathlib import Path
from experimental_unixcoder.bug_localization import BugLocalization
from services.report_service import reorder_rankings
from utils.preprocess_bug_report import preprocess_bug_report
from utils.extract_gui_data import build_corpus, extract_gs_terms, extract_sc_terms, get_boosted_files
from utils.preprocess_source_code import preprocess_source_code
from utils.filter import filter_files
import json
import re

def localize_buggy_files_with_GUI_data(project_path):
    """
    Assumes project_path is the root directory containing all the projects.
    
    {project_path}/Execution-1.json
    {project_path}/source_code
    {project_path}/bug_report_{bug-id}.txt
    {project_path}/{bug-id}.json
    """
    bug_id = int(re.search(r'bug-(\d+)', project_path).group(1))

    trace_path = f'{project_path}/trace/Execution-1.json'
    source_code_path = f'{project_path}/source_code'
    bug_report_path = f'{project_path}/bug_report_{bug_id}.txt'
    ground_truth_path = f'{project_path}/{bug_id}.json'

    with open(trace_path, 'r') as f:
        trace = json.load(f)

    print(trace)

    sc_terms = extract_sc_terms(trace)
    gs_terms = extract_gs_terms(trace)

    filtered_files = filter_files(source_code_path) # return value not necessary for testing
    preprocessed_files = preprocess_source_code(source_code_path) # output: list(tuple(path, name, embeddings))
    preprocessed_bug_report = preprocess_bug_report(bug_report_path, sc_terms) # output: string
    
    # util function here to transform preprocessed_files currently list(path, name, embeddings) to a tuple with (routes, embeddings)
    corpus_embeddings = to_corpus_embeddings(preprocessed_files)

    # util function here to get code files and content: tuple(file_path, file_name, file_contents)
    # input: source_code path
    # output: list(tuple(path, name, content))
    repo_files = to_repo_files(source_code_path)

    corpus = build_corpus(repo_files, sc_terms, None)
    boosted_files = get_boosted_files(repo_files, gs_terms)

    bug_localizer = BugLocalization()

    ranked_files = bug_localizer.rank_files(preprocessed_bug_report, corpus_embeddings)
    reranked_files = reorder_rankings(ranked_files, boosted_files)

    # util function here to get ranking of true buggy files
    buggy_file_rankings = get_buggy_file_rankings(reranked_files, ground_truth_path)

def localize_buggy_files_without_GUI_data(project_path):
    bug_id = int(re.search(r'bug-(\d+)', project_path).group(1))

    source_code_path = f'{project_path}/code'
    bug_report_path = f'{project_path}/bug_report_{bug_id}.txt'
    ground_truth_path = f'{project_path}/{bug_id}.json'

    filtered_files = filter_files(source_code_path) # return value not necessary for testing
    preprocessed_files = preprocess_source_code(source_code_path) # output: list(tuple(path, name, embeddings))
    preprocessed_bug_report = preprocess_bug_report(bug_report_path, "") # output: string
    
    # print(f"PREPROCESSED FILES: {preprocessed_files}")
    print(f"PREPROCESSED BUG REPORT: {preprocessed_bug_report}")

    # util function here to transform preprocessed_files currently list(path, name, embeddings) to a tuple with (routes, embeddings)
    corpus_embeddings = to_corpus_embeddings(preprocessed_files)
    # print(f"CORPUS EMBEDDINGS: {corpus_embeddings}")    

    bug_localizer = BugLocalization()

    ranked_files = bug_localizer.rank_files(preprocessed_bug_report, corpus_embeddings)
    print(f"RANKED FILES: {ranked_files}")

    # util function here to get ranking of true buggy files
    buggy_file_rankings = get_buggy_file_rankings(ranked_files, ground_truth_path)

    print(f"BUGGY FILE RANKINGS: {buggy_file_rankings}")


def to_corpus_embeddings(preprocessed_files):
    corpus_embeddings = []
    for file in preprocessed_files:
        corpus_embeddings.append((file[0], file[2]))
    return corpus_embeddings

def to_repo_files(source_code_path):
    repo_files = []
    repo = Path(source_code_path)
    for file_path in repo.rglob("*"):
        if file_path.is_file():
            try: 
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                    repo_files.append((file_path, file_path.name, file_content))
            except FileNotFoundError:
                print(f"Error: The source code file at '{file_path}' was not found.")
                return
    return repo_files

def get_buggy_file_rankings(reranked_files, ground_truth_path):
    # Load the ground truth JSON file
    with open(ground_truth_path, 'r') as f:
        ground_truth = json.load(f)

    # Extract the list of bug file names from the JSON
    bug_file_names = [bug["file_name"] for bug in ground_truth.get("bug_location", [])]
    print(f"BUG FILE NAMES: {bug_file_names}")

    results = []
    # Enumerate the input tuple with 1-indexing
    for rank, (file_path, score) in enumerate(reranked_files, start=1):
        # Check if any bug file name is a substring of the file_path
        for bug_file in bug_file_names:
            if bug_file in str(file_path):
                results.append((file_path, rank))

    return results

localize_buggy_files_without_GUI_data("/home/noarchway/CopyBuggy/BuggyProjects/bug-2")