import argparse
import datetime
import os
from rich.progress import Progress, BarColumn, TextColumn
from rich.console import Console
from rich.table import Table
from red_wing.localization import collect_repos, localize_buggy_files_with_GUI_data, hits_at_k

console = Console()

# ANSI escape codes for coloring output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"

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

    table = Table(title="Summary Metrics")
    table.add_column("Metric", justify="left", style="cyan")
    table.add_column("Hits", justify="center", style="magenta")
    table.add_column("Ratio", justify="center", style="green")
    table.add_row("Hits@50", f"{hits_50}/{total_bugs}", f"{hits_at_50_ratio:.2f}")
    table.add_row("Hits@25", f"{hits_25}/{total_bugs}", f"{hits_at_25_ratio:.2f}")
    table.add_row("Hits@10", f"{hits_10}/{total_bugs}", f"{hits_at_10_ratio:.2f}")
    table.add_row("Hits@5", f"{hits_5}/{total_bugs}", f"{hits_at_5_ratio:.2f}")
    table.add_row("Hits@1", f"{hits_1}/{total_bugs}", f"{hits_at_1_ratio:.2f}")
    console.print("\n")
    console.print(table)
    console.print("\n")
