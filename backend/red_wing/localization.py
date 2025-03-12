import os
import glob
import json
import re
import random
from pathlib import Path
from experimental_unixcoder.bug_localization import BugLocalization
from utils.preprocess_bug_report import preprocess_bug_report
from utils.extract_gui_data import build_corpus, extract_gs_terms, extract_sc_terms, get_boosted_files
from utils.preprocess_source_code import preprocess_source_code
from utils.filter import filter_files
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()
# ANSI escape codes for coloring output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"


def reorder_rankings(ranked_files: list[tuple], gs_files: list[str]):
    """Boosts GS files to the top of the ranking while preserving their relative order."""
    gs_ranked = [item for item in ranked_files if item[0] in gs_files]
    non_gs_ranked = [item for item in ranked_files if item[0] not in gs_files]
    return gs_ranked + non_gs_ranked


def localize_buggy_files_with_GUI_data(project_path, verbose=False):
    """
    Process a repository that contains GUI data.
    Expects the following in project_path:
      - Execution-1.json
      - code/ (source code directory)
      - bug_report_{bug-id}.txt
      - {bug-id}.json (ground truth)
    """
    bug_id = int(re.search(r'bug-(\d+)', project_path).group(1))
    trace_path = os.path.join(project_path, "Execution-1.json")
    source_code_path = os.path.join(project_path, "code")
    bug_report_path = os.path.join(project_path, f"bug_report_{bug_id}.txt")
    ground_truth_path = os.path.join(project_path, f"{bug_id}.json")

    with open(trace_path, 'r') as f:
        trace = json.load(f)

    # Create a preview of the trace (first 10 lines)
    trace_str = json.dumps(trace, indent=2)
    trace_lines = trace_str.splitlines()
    trace_preview = "\n".join(trace_lines[:10])
    if len(trace_lines) > 10:
        trace_preview += "\n..."
    trace_panel = Panel.fit(trace_preview, title=f"Trace Information for Bug {bug_id}", border_style="blue")
    console.print("\n")
    console.print(trace_panel)
    console.print("\n")

    sc_terms = extract_sc_terms(json.dumps(trace))
    gs_terms = extract_gs_terms(json.dumps(trace))

    filtered_files = filter_files(source_code_path)
    preprocessed_files = preprocess_source_code(source_code_path, verbose=verbose)
    preprocessed_bug_report = preprocess_bug_report(bug_report_path, sc_terms, verbose=verbose)

    repo_files = to_repo_files(source_code_path)
    corpus = build_corpus(repo_files, sc_terms, None)
    corpus_embeddings = to_corpus_embeddings(preprocessed_files, corpus)
    boosted_files = get_boosted_files(repo_files, gs_terms)

    bug_localizer = BugLocalization()
    ranked_files = bug_localizer.rank_files(preprocessed_bug_report, corpus_embeddings)
    reranked_files = reorder_rankings(ranked_files, boosted_files)
    buggy_file_rankings = get_buggy_file_rankings(reranked_files, ground_truth_path, bug_id)
    
    if buggy_file_rankings:
        table = Table(title=f"Buggy File Rankings for Bug {bug_id}")
        table.add_column("Rank", justify="center", style="yellow")
        table.add_column("File", justify="left", style="green")
        for b_id, file, rank in buggy_file_rankings:
            table.add_row(str(rank), file)
        console.print("\n")
        console.print(table)
        console.print("\n")
    else:
        console.print("\n")
        console.print(Panel("No buggy file rankings found.", title=f"Bug {bug_id} Rankings", border_style="red"))
        console.print("\n")

    return buggy_file_rankings


def localize_buggy_files_without_GUI_data(project_path, verbose=False):
    bug_id = int(re.search(r'bug-(\d+)', project_path).group(1))
    source_code_path = os.path.join(project_path, "code")
    bug_report_path = os.path.join(project_path, f"bug_report_{bug_id}.txt")
    ground_truth_path = os.path.join(project_path, f"{bug_id}.json")

    filtered_files = filter_files(source_code_path)
    preprocessed_files = preprocess_source_code(source_code_path, verbose=verbose)
    preprocessed_bug_report = preprocess_bug_report(bug_report_path, [], verbose=verbose)

    console.print("\n")
    console.print(Panel(preprocessed_bug_report, title="Preprocessed Bug Report", border_style="blue"))
    console.print("\n")

    corpus_embeddings = to_corpus_embeddings(preprocessed_files, None)
    bug_localizer = BugLocalization()
    ranked_files = bug_localizer.rank_files(preprocessed_bug_report, corpus_embeddings)

    console.print("\n")
    console.print(Panel(str(ranked_files), title="Ranked Files", border_style="blue"))
    console.print("\n")

    buggy_file_rankings = get_buggy_file_rankings(ranked_files, ground_truth_path, bug_id)

    console.print("\n")
    console.print(
        Panel(f"BUGGY FILE RANKINGS: {buggy_file_rankings}", title="Buggy File Rankings", border_style="blue"))
    console.print("\n")

    return buggy_file_rankings


def to_corpus_embeddings(preprocessed_files, corpus=None):
    corpus_embeddings = []
    count = 0
    if corpus:
        for file in preprocessed_files:
            if file[0] in corpus:
                count += 1
                corpus_embeddings.append((file[0], file[2]))
    else:
        for file in preprocessed_files:
            count += 1
            corpus_embeddings.append((file[0], file[2]))
    console.print(f"\nCORPUS COUNT: {count}\n")
    return corpus_embeddings


def to_repo_files(source_code_path):
    repo_files = []
    repo = Path(source_code_path)
    for file_path in repo.rglob("*"):
        if file_path.is_file():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    repo_files.append((file_path, file_path.name, content))
            except FileNotFoundError:
                console.print(f"\n{RED}Error: The source code file at '{file_path}' was not found.{RESET}\n")
    return repo_files


def get_buggy_file_rankings(reranked_files, ground_truth_path, bug_id):
    with open(ground_truth_path, 'r') as f:
        ground_truth = json.load(f)
    bug_file_names = [bug["file_name"] for bug in ground_truth.get("bug_location", [])]
    console.print("\n")
    console.print(Panel(str(bug_file_names), title="Bug File Names", border_style="blue"))
    console.print("\n")
    results = []
    for rank, (file_path, score) in enumerate(reranked_files, start=1):
        normalized_path = str(Path(file_path).as_posix())  # Convert to Linux-style
        for bug_file in bug_file_names:
            if bug_file in normalized_path:
                relative_path = normalized_path.split('/code', 1)[-1]
                results.append((bug_id, relative_path, rank))
    return results


def collect_repos(repo_home, flag_all=False, repo_count=None, repo_ids=None):
    repo_paths = []
    if repo_ids:
        for repo_id in repo_ids:
            path = os.path.join(repo_home, f"bug-{repo_id}")
            if os.path.isdir(path):
                repo_paths.append(path)
            else:
                console.print(f"\n{RED}Warning: Repository directory does not exist: {path}{RESET}\n")
    else:
        all_repos = sorted(glob.glob(os.path.join(repo_home, "bug-*")))
        all_repos = [r for r in all_repos if os.path.isdir(r)]
        if flag_all:
            repo_paths = all_repos
        elif repo_count and repo_count > 0:
            if repo_count > len(all_repos):
                console.print(
                    f"\n{YELLOW}Requested {repo_count} repos but only found {len(all_repos)}. Using all available repos.{RESET}\n")
                repo_paths = all_repos
            else:
                repo_paths = random.sample(all_repos, repo_count)
        else:
            console.print(f"\n{RED}Error: Invalid arguments provided{RESET}\n")
    return repo_paths


def hits_at_k(k, rankings):
    return sum(1 for rank in rankings if rank <= k)

def map_at_k(k, all_buggy_file_rankings):
    """
    Calculates Mean Average Precision (MAP) at k for all buggy file rankings

    Args:
        k (int): Cutoff point for MAP calculation
        all_buggy_file_rankings (list(tuples)): Ranking output of redwing

    Returns:
        mean_average_precision
    """
    total_projects = len(all_buggy_file_rankings)
    average_precisions = []

    # Calculate average precision@k values for each buggy project
    for project in all_buggy_file_rankings:
        precision_values = []
        relevant_file_count = 0

        # Calculate amount of relevant buggy files up to k
        # A buggy file is relevant is it appears before or at k
        # Calculate precision at the buggy file
        for bug_ranking in project:
            rank = bug_ranking[2]
            # Check if the ranking is within k
            if rank <= k:
                relevant_file_count+=1
                precision_at_rank = relevant_file_count / rank
                precision_values.append(precision_at_rank)

        # Calculate AP@k for the buggy project if any buggy files were ranked within k
        if precision_values:
            average_precision = sum(precision_values) / len(precision_values)
        else:
            average_precision = 0

        average_precisions.append(average_precision)

    # Calculate MAP for entire dataset
    mean_average_precision = sum(average_precisions) / total_projects
    return mean_average_precision

def find_first_rank(k, buggy_file_rankings):
    best_rank = float('inf')  # Set to infinity initially
    for b_id, file, rank in buggy_file_rankings:
        if rank <= k:
            best_rank = min(best_rank, rank)
    return best_rank if best_rank != float('inf') else float('inf')  # Avoid returning 0


def sum_reciprocal_rank(k, rankings):
    first_rank = find_first_rank(k, rankings)
    return 1 / first_rank if first_rank != float('inf') else 0


# Computes Mean Reciprocal Rank (MRR@K) across all projects
def mrr_at_k(k, all_buggy_file_rankings):
    """
    Calculates Mean Reciprocal Rank (MRR) at k for all buggy file rankings.

    Args:
        k (int): Cutoff point for MRR calculation.
        all_buggy_file_rankings (list of lists of tuples): Rankings per project.

    Returns:
        float: Mean Reciprocal Rank at K.
    """
    total_projects = len(all_buggy_file_rankings)
    if total_projects == 0:
        return 0

    reciprocal_ranks = []

    # Compute reciprocal rank for each project
    for project in all_buggy_file_rankings:
        reciprocal_rank = sum_reciprocal_rank(k, project)
        reciprocal_ranks.append(reciprocal_rank)

    return sum(reciprocal_ranks) / total_projects
def calculate_effectiveness(buggy_file_rankings):
    """
    Calculate the minimum, maximum, and average ranks of buggy files in the rankings

    Args:
        buggy_file_rankings (list(tuples)): Ranking output of redwing
    """
    best_ranks = []
    for ranking in buggy_file_rankings:
        if ranking:
            best_rank = min(r[2] for r in ranking if len(r) >= 3)
            best_ranks.append(best_rank)

    return (min(best_ranks), max(best_ranks), sum(best_ranks) / len(best_ranks))
