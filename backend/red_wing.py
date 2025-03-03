import time
from pathlib import Path
from experimental_unixcoder.bug_localization import BugLocalization
from services.report_service import reorder_rankings
from utils.preprocess_bug_report import preprocess_bug_report
from utils.extract_gui_data import build_corpus, extract_gs_terms, extract_sc_terms, get_boosted_files
from utils.preprocess_source_code import preprocess_source_code
from utils.filter import filter_files

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


def localize_buggy_files_with_GUI_data(project_path):
    """
    Assumes project_path is the root directory containing all the projects.
    
    {project_path}/Execution-1.json
    {project_path}/source_code
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

    print(f"\n{BLUE}{BOLD}Trace Information:{RESET}")
    # print(json.dumps(trace, indent=2))

    sc_terms = extract_sc_terms(json.dumps(trace))
    gs_terms = extract_gs_terms(json.dumps(trace))

    filtered_files = filter_files(source_code_path)  # return value not necessary for testing
    preprocessed_files = preprocess_source_code(source_code_path)  # output: list(tuple(path, name, embeddings))
    preprocessed_bug_report = preprocess_bug_report(bug_report_path, sc_terms)  # output: string


    # util function here to get code files and content: tuple(file_path, file_name, file_contents)
    # input: source_code path
    # output: list(tuple(path, name, content))
    repo_files = to_repo_files(source_code_path)

    corpus = build_corpus(repo_files, sc_terms, None)
    # util function here to transform preprocessed_files currently list(path, name, embeddings) to a tuple with (routes, embeddings)
    corpus_embeddings = to_corpus_embeddings(preprocessed_files, corpus)

    boosted_files = get_boosted_files(repo_files, gs_terms)

    bug_localizer = BugLocalization()

    ranked_files = bug_localizer.rank_files(preprocessed_bug_report, corpus_embeddings)
    reranked_files = reorder_rankings(ranked_files, boosted_files)

    # util function here to get ranking of true buggy files
    buggy_file_rankings = get_buggy_file_rankings(reranked_files, ground_truth_path, bug_id)

    print(buggy_file_rankings)
    print(f"\n{GREEN}{BOLD}Buggy File Rankings (with GUI Data):{RESET}")

    if buggy_file_rankings:
        for bug_id, file, rank in buggy_file_rankings:
            print(f"Rank {YELLOW}{rank}{RESET}: {file}")
    else:
        print(f"{RED}No buggy file rankings found.{RESET}")

    return buggy_file_rankings


def localize_buggy_files_without_GUI_data(project_path):
    bug_id = int(re.search(r'bug-(\d+)', project_path).group(1))

    source_code_path = f'{project_path}/code'
    bug_report_path = f'{project_path}/bug_report_{bug_id}.txt'
    ground_truth_path = f'{project_path}/{bug_id}.json'

    filtered_files = filter_files(source_code_path)
    preprocessed_files = preprocess_source_code(source_code_path)
    preprocessed_bug_report = preprocess_bug_report(bug_report_path, [])

    print(f"\n{BLUE}{BOLD}Preprocessed Bug Report:{RESET}")
    print(preprocessed_bug_report)

    corpus_embeddings = to_corpus_embeddings(preprocessed_files, None)

    bug_localizer = BugLocalization()

    ranked_files = bug_localizer.rank_files(preprocessed_bug_report, corpus_embeddings)
    print(f"\n{BLUE}{BOLD}Ranked Files:{RESET}")
    print(ranked_files)

    buggy_file_rankings = get_buggy_file_rankings(ranked_files, ground_truth_path, bug_id)

    print(f"BUGGY FILE RANKINGS: {buggy_file_rankings}")

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
    print(f"CORPUS COUNT: {count}")
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
                print(f"{RED}Error: The source code file at '{file_path}' was not found.{RESET}")
                continue
    return repo_files


def get_buggy_file_rankings(reranked_files, ground_truth_path, bug_id):
    with open(ground_truth_path, 'r') as f:
        ground_truth = json.load(f)

    bug_file_names = [bug["file_name"] for bug in ground_truth.get("bug_location", [])]
    print(f"\n{BLUE}{BOLD}Bug File Names:{RESET}")
    print(bug_file_names)

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
                print(f"{RED}Warning: Repository directory does not exist: {repo_path}{RESET}")
    else:
        all_repos = sorted(glob.glob(os.path.join(repo_home, "bug-*")))
        all_repos = [r for r in all_repos if os.path.isdir(r)]
        if flag_all:
            repo_paths = all_repos
        elif repo_count > 0:
            if repo_count > len(all_repos):
                print(
                    f"{YELLOW}Requested {repo_count} repos but only found {len(all_repos)}. Using all available repos.{RESET}")
                repo_paths = all_repos
            else:
                repo_paths = random.sample(all_repos, repo_count)
        else:
            print(f"{RED}Error: Invalid arguments provided{RESET}")
            return []

    return repo_paths


def main():
    print_banner()
    parser = argparse.ArgumentParser(description="Red Wings script")
    parser.add_argument('-p', required=True, dest="path", help="Repo home path")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-a', action='store_true', help="Iterate over all repos")
    group.add_argument('-r', type=int, dest="repo_count", help="Number of repos to randomly select")
    group.add_argument('-i', type=int, nargs='+', dest="repo_ids", help="One or more repo IDs")
    args = parser.parse_args()

    start = time.time()
    repo_home = args.path
    if not os.path.isdir(repo_home):
        print(f"{RED}Error: The provided repo home path does not exist: {repo_home}{RESET}")
        return

    repo_paths = collect_repos(
        repo_home,
        flag_all=args.a,
        repo_count=args.repo_count,
        repo_ids=args.repo_ids
    )

    if not repo_paths:
        print(f"{RED}Error: No repositories found{RESET}")
        return

    print(f"\n{GREEN}{BOLD}Collected Repo Paths:{RESET}")
    print(f"{YELLOW}" + f"\n".join(repo_paths) + f"{RESET}")
    all_buggy_file_rankings = []
    best_rankings_per_bug = []
    for path in repo_paths:
        rankings = localize_buggy_files_with_GUI_data(path)
        all_buggy_file_rankings.append(rankings)
        if rankings:
            best_rank = min(r[2] for r in rankings)
            best_rankings_per_bug.append(best_rank)
        else:
            best_rankings_per_bug.append(9999)

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

    print(f"\n{GREEN}{BOLD}Hits@10 Ratio:{RESET} {hits_10}/{total_bugs} = {hits_at_10_ratio:.2f}")
    print(f"\n{GREEN}{BOLD}Hits@5 Ratio:{RESET} {hits_5}/{total_bugs} = {hits_at_5_ratio:.2f}")
    print(f"\n{GREEN}{BOLD}Hits@1 Ratio:{RESET} {hits_1}/{total_bugs} = {hits_at_1_ratio:.2f}")
    end = time.time()
    print(f"\n{GREEN}{BOLD}Execution Time:{RESET} {end - start:.2f} seconds")


def hits_at_k(k, rankings):
    hits = 0
    for rank in rankings:
        if rank <= k:
            hits += 1
    return hits


if __name__ == '__main__':
    main()
