import time
from pathlib import Path
from experimental_unixcoder.bug_localization import BugLocalization
from utils.preprocess_bug_report import preprocess_bug_report
from utils.extract_gui_data import build_corpus, extract_gs_terms, extract_sc_terms, get_boosted_files
from utils.preprocess_source_code import preprocess_source_code
from utils.filter import filter_files
from rich.progress import Progress, BarColumn, TextColumn
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import datetime
import json
import re
import argparse
import os
import glob
import random

# ANSI escape codes for coloring output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"

console = Console()


def print_banner():
    banner = f"""
{RED}{BOLD}
ooooooooo.                   .o8       oooooo   oooooo     oooo  o8o                         
`888   `Y88.                "888        `888.    `888.     .8'   `"'                         
 888   .d88'  .ooooo.   .oooo888         `888.   .8888.   .8'   oooo  ooo. .oo.    .oooooooo 
 888ooo88P'  d88' `88b d88' `888          `888  .8'`888. .8'    `888  `888P"Y88b  888' `88b  
 888`88b.    888ooo888 888   888           `888.8'  `888.8'      888   888   888  888   888  
 888  `88b.  888    .o 888   888            `888'    `888'       888   888   888  `88bod8P'  
o888o  o888o `Y8bod8P' `Y8bod88P"            `8'      `8'       o888o o888o o888o `8oooooo.  
                                                                                  d"     YD  
                                                                                  "Y88888P'  
{RESET}
"""
    print(banner)
    time.sleep(1)


def reorder_rankings(ranked_files: list[tuple], gs_files: list[str]):
    """
    Boosts GS files to the top of the ranking while preserving their relative order.
    """
    gs_ranked = [item for item in ranked_files if item[0] in gs_files]
    non_gs_ranked = [item for item in ranked_files if item[0] not in gs_files]
    return gs_ranked + non_gs_ranked


def localize_buggy_files_with_GUI_data(project_path, verbose=False):
    """
    Assumes project_path is the root directory containing all the projects.
    {project_path}/Execution-1.json
    {project_path}/code
    {project_path}/bug_report_{bug-id}.txt
    {project_path}/{bug-id}.json
    """
    bug_id = int(re.search(r'bug-(\d+)', project_path).group(1))
    trace_path = f'{project_path}/Execution-1.json'
    source_code_path = f'{project_path}/code'
    bug_report_path = f'{project_path}/bug_report_{bug_id}.txt'
    ground_truth_path = f'{project_path}/{bug_id}.json'

    with open(trace_path, 'r') as f:
        trace = json.load(f)

    # Convert trace to a formatted string and show only the first 10 lines
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
    source_code_path = f'{project_path}/code'
    bug_report_path = f'{project_path}/bug_report_{bug_id}.txt'
    ground_truth_path = f'{project_path}/{bug_id}.json'

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
    console.print(Panel(f"BUGGY FILE RANKINGS: {buggy_file_rankings}", title="Buggy File Rankings", border_style="blue"))
    console.print("\n")

    return buggy_file_rankings


def to_corpus_embeddings(preprocessed_files, corpus: None):
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
                    file_content = f.read()
                    repo_files.append((file_path, file_path.name, file_content))
            except FileNotFoundError:
                console.print(f"\n{RED}Error: The source code file at '{file_path}' was not found.{RESET}\n")
                continue
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
        for bug_file in bug_file_names:
            if bug_file in str(file_path):
                relative_path = str(file_path).split('/code', 1)[-1]
                results.append((bug_id, relative_path, rank))
    return results


def collect_repos(repo_home, flag_all=False, repo_count=None, repo_ids=None):
    repo_paths = []
    if repo_ids is not None:
        for repo_id in repo_ids:
            repo_path = os.path.join(repo_home, f"bug-{repo_id}")
            if os.path.isdir(repo_path):
                repo_paths.append(repo_path)
            else:
                console.print(f"\n{RED}Warning: Repository directory does not exist: {repo_path}{RESET}\n")
    else:
        all_repos = sorted(glob.glob(os.path.join(repo_home, "bug-*")))
        all_repos = [r for r in all_repos if os.path.isdir(r)]
        if flag_all:
            repo_paths = all_repos
        elif repo_count > 0:
            if repo_count > len(all_repos):
                console.print(f"\n{YELLOW}Requested {repo_count} repos but only found {len(all_repos)}. Using all available repos.{RESET}\n")
                repo_paths = all_repos
            else:
                repo_paths = random.sample(all_repos, repo_count)
        else:
            console.print(f"\n{RED}Error: Invalid arguments provided{RESET}\n")
            return []
    return repo_paths


def hits_at_k(k, rankings):
    hits = 0
    for rank in rankings:
        if rank <= k:
            hits += 1
    return hits


# --- CLI helper functions ---

def parse_cli_arguments():
    parser = argparse.ArgumentParser(description="Red Wings script")
    parser.add_argument('-p', required=True, dest="path", help="Repo home path")
    parser.add_argument('-v', action='store_true', help="Verbose output")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-a', action='store_true', help="Iterate over all repos")
    group.add_argument('-r', type=int, dest="repo_count", help="Number of repos to randomly select")
    group.add_argument('-i', type=int, nargs='+', dest="repo_ids", help="One or more repo IDs")
    return parser.parse_args()


def process_repos(repo_paths, verbose):
    all_buggy_file_rankings = []
    best_rankings_per_bug = []
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} repos")
    ) as progress:
        task = progress.add_task("Processing repos...", total=len(repo_paths))
        for path in repo_paths:
            rankings = localize_buggy_files_with_GUI_data(path, verbose=verbose)
            all_buggy_file_rankings.append(rankings)
            if rankings:
                best_rank = min(r[2] for r in rankings)
                best_rankings_per_bug.append(best_rank)
            else:
                best_rankings_per_bug.append(9999)
            progress.update(task, advance=1)
    return all_buggy_file_rankings, best_rankings_per_bug


def output_metrics(all_buggy_file_rankings, best_rankings_per_bug):
    total_bugs = len(best_rankings_per_bug)
    hits_50 = hits_at_k(50, best_rankings_per_bug)
    hits_25 = hits_at_k(25, best_rankings_per_bug)
    hits_10 = hits_at_k(10, best_rankings_per_bug)
    hits_5 = hits_at_k(5, best_rankings_per_bug)
    hits_1 = hits_at_k(1, best_rankings_per_bug)

    hits_at_50_ratio = hits_50 / total_bugs if total_bugs > 0 else 0
    hits_at_25_ratio = hits_25 / total_bugs if total_bugs > 0 else 0
    hits_at_10_ratio = hits_10 / total_bugs if total_bugs > 0 else 0
    hits_at_5_ratio = hits_5 / total_bugs if total_bugs > 0 else 0
    hits_at_1_ratio = hits_1 / total_bugs if total_bugs > 0 else 0

    current_time = datetime.datetime.now().strftime("%m%d%y%H%M")
    csv_file_name = f"metrics/{current_time}.csv"
    os.makedirs('metrics', exist_ok=True)
    with open(csv_file_name, "w") as f:
        f.write(f"hits@50, {hits_50}/{total_bugs}, {hits_at_50_ratio:.2f}\n")
        f.write(f"hits@25, {hits_25}/{total_bugs}, {hits_at_25_ratio:.2f}\n")
        f.write(f"hits@10, {hits_10}/{total_bugs}, {hits_at_10_ratio:.2f}\n")
        f.write(f"hits@5, {hits_5}/{total_bugs}, {hits_at_5_ratio:.2f}\n")
        f.write(f"hits@1, {hits_1}/{total_bugs}, {hits_at_1_ratio:.2f}\n")
        f.write("bug_id,file_path,rank\n")
        for rankings in all_buggy_file_rankings:
            for ranking in rankings:
                f.write(f"{ranking[0]},{ranking[1]},{ranking[2]}\n")

    metrics_table = Table(title="Summary Metrics")
    metrics_table.add_column("Metric", justify="left", style="cyan")
    metrics_table.add_column("Hits", justify="center", style="magenta")
    metrics_table.add_column("Ratio", justify="center", style="green")
    metrics_table.add_row("Hits@50", f"{hits_50}/{total_bugs}", f"{hits_at_50_ratio:.2f}")
    metrics_table.add_row("Hits@25", f"{hits_25}/{total_bugs}", f"{hits_at_25_ratio:.2f}")
    metrics_table.add_row("Hits@10", f"{hits_10}/{total_bugs}", f"{hits_at_10_ratio:.2f}")
    metrics_table.add_row("Hits@5", f"{hits_5}/{total_bugs}", f"{hits_at_5_ratio:.2f}")
    metrics_table.add_row("Hits@1", f"{hits_1}/{total_bugs}", f"{hits_at_1_ratio:.2f}")
    console.print("\n")
    console.print(metrics_table)
    console.print("\n")


# --- Main CLI entry point ---

def main():
    print_banner()
    args = parse_cli_arguments()
    verbose = args.v
    repo_home = args.path
    if not os.path.isdir(repo_home):
        console.print(f"\n{RED}Error: The provided repo home path does not exist: {repo_home}{RESET}\n")
        return
    repo_paths = collect_repos(
        repo_home,
        flag_all=args.a,
        repo_count=args.repo_count,
        repo_ids=args.repo_ids
    )
    if not repo_paths:
        console.print(f"\n{RED}Error: No repositories found{RESET}\n")
        return
    repo_table = Table(title="Collected Repo Paths")
    repo_table.add_column("Repository Path", style="yellow", justify="left")
    for repo in repo_paths:
        repo_table.add_row(repo)
    console.print("\n")
    console.print(repo_table)
    console.print("\n")
    all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose)
    output_metrics(all_buggy_file_rankings, best_rankings_per_bug)


if __name__ == '__main__':
    main()
