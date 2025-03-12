import os
import time
from rich.console import Console
from rich.table import Table
from red_wing.localization import collect_repos
from red_wing.cli_helpers import parse_cli_arguments, process_repos, output_metrics
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
    time.sleep(1)

def main():
    print_banner()
    args = parse_cli_arguments()
    verbose = args.v
    repo_home = args.path
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

    all_buggy_file_rankings, best_rankings_per_bug = process_repos(repo_paths, verbose)
    output_metrics(all_buggy_file_rankings, best_rankings_per_bug)

if __name__ == '__main__':
    main()
