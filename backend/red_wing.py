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


# New function to run a single loop iteration in parallel
def run_loop(loop_number, repo_paths, verbose, improvement, base):
    # This function runs one loop iteration
    if improvement:
        (all_buggy_file_rankings_gui, best_rankings_gui) = process_repos(repo_paths, verbose, True)  # with gui
        (all_buggy_file_rankings_base, best_rankings_base) = process_repos(repo_paths, verbose, False)  # without gui
        output_big_metrics_with_improvement(all_buggy_file_rankings_gui, best_rankings_gui, best_rankings_base,
                                            loop_number)
    elif base:
        all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose, False)
        output_big_metrics(all_buggy_file_rankings, best_rankings_per_bug, None, loop_number)
    else:
        all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose, True)
        output_big_metrics(all_buggy_file_rankings, best_rankings_per_bug, None, loop_number)
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

    # If looping, run the entire process in parallel with 3 workers
    if loop_count > 1:
        with ProcessPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(1, loop_count + 1):
                console.print(f"Submitting loop {i}")
                futures.append(executor.submit(run_loop, i, repo_paths, verbose, improvement, base))
            for future in as_completed(futures):
                result = future.result()
                console.print(result)
    else:
        if (improvement):
            (all_buggy_file_rankings_gui, best_rankings_gui) = process_repos(repo_paths, verbose, True)  # with gui
            (all_buggy_file_rankings_base, best_rankings_base) = process_repos(repo_paths, verbose,
                                                                               False)  # without gui
            output_metrics_with_improvement(all_buggy_file_rankings_gui, best_rankings_gui, best_rankings_base)
        elif (base):
            all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose, False)
            output_metrics(all_buggy_file_rankings, best_rankings_per_bug, None)
        else:
            all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose, True)
            output_metrics(all_buggy_file_rankings, best_rankings_per_bug, None)


if __name__ == '__main__':
    import multiprocessing as mp
    mp.set_start_method('spawn', force=True)
    main()
