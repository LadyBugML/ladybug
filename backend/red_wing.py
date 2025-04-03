# file: backend/red_wing.py
import os
import time
import torch
from rich.console import Console
from rich.table import Table
from concurrent.futures import ProcessPoolExecutor, as_completed
from red_wing.localization import collect_repos
from red_wing.cli_helpers import parse_cli_arguments, process_repos, output_metrics, output_metrics_with_improvement, \
    output_big_metrics, output_big_metrics_with_improvement
import datetime
from experimental_unixcoder.bug_localization import BugLocalization

console = Console()

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

def run_loop(loop_number, repo_paths, verbose, improvement, base, filename,model):
    # This function runs one loop iteration
    BugLocalization(model=model)
    if improvement:
        (all_buggy_file_rankings_gui, best_rankings_gui) = process_repos(repo_paths, verbose, True)  # with gui
        (all_buggy_file_rankings_base, best_rankings_base) = process_repos(repo_paths, verbose, False)  # without gui
        output_big_metrics_with_improvement(all_buggy_file_rankings_gui, best_rankings_gui, best_rankings_base,
                                            loop_number, filename)
    elif base:
        all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose, False)
        output_big_metrics(all_buggy_file_rankings, best_rankings_per_bug, None, loop_number, filename)
    else:
        all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose, True)
        output_big_metrics(all_buggy_file_rankings, best_rankings_per_bug, None, loop_number, filename)
    return f"Loop {loop_number} completed"


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("CUDA is available" if device.type == "cuda" else "CUDA is not available")
    print_banner()
    args = parse_cli_arguments()
    verbose = args.v
    repo_home = args.path
    improvement = args.m
    base = args.b
    loop_count = args.loop
    model = args.model

    cleaned_model = model.replace("/", "_").replace("-", "_")

    if not os.path.isdir(repo_home):
        console.print(f"\nError: The provided repo home path does not exist: {repo_home}\n")
        return

    repo_paths = collect_repos(
        repo_home,
        flag_all=args.a,
        repo_count=args.repo_count,
        repo_ids=args.repo_ids
    )
    if not repo_paths:
        console.print("\nError: No repositories found\n")
        return

    repo_table = Table(title="Collected Repo Paths")
    repo_table.add_column("Repository Path", style="yellow", justify="left")
    for repo in repo_paths:
        repo_table.add_row(repo)
    console.print("\n")
    console.print(repo_table)
    console.print("\n")

    timestamp = datetime.datetime.now().strftime("%m%d-%H%M")
    repo_val = (args.repo_count if args.repo_count else "all")
    metrics_filename = f"metrics/big/{cleaned_model}-{repo_val}repos-{loop_count}loops"
    if improvement:
        metrics_filename += "-improvement"
    if base:
        metrics_filename += "-base"
    metrics_filename += f"-{timestamp}.csv"
    os.makedirs('metrics/big', exist_ok=True)
    os.makedirs('metrics/preprocessed_data', exist_ok=True)

    # If looping, run the entire process in parallel with 3 workers
    if loop_count > 1:
        with ProcessPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(1, loop_count + 1):
                console.print(f"Submitting loop {i}")
                # Pass the computed metrics_filename to each loop iteration
                futures.append(executor.submit(run_loop, i, repo_paths, verbose, improvement, base, metrics_filename, model))
            for future in as_completed(futures):
                result = future.result()
                console.print(result)
        # Use the dynamic filename here as well instead of "bigMetrics.csv"
        with open(metrics_filename, "a") as f:
            f.write(f"running model: {model}\n")
    else:
        if improvement:
            (all_buggy_file_rankings_gui, best_rankings_gui) = process_repos(repo_paths, verbose, True)  # with gui
            (all_buggy_file_rankings_base, best_rankings_base) = process_repos(repo_paths, verbose,
                                                                               False)  # without gui
            output_metrics_with_improvement(all_buggy_file_rankings_gui, best_rankings_gui, best_rankings_base)
        elif base:
            all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose, False)
            output_metrics(all_buggy_file_rankings, best_rankings_per_bug, None)
        else:
            all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose, True)
            output_metrics(all_buggy_file_rankings, best_rankings_per_bug, None)


if __name__ == '__main__':
    import multiprocessing as mp

    mp.set_start_method('spawn', force=True)
    main()
