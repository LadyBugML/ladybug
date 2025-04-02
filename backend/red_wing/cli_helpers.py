import argparse
import datetime
import os
from nltk import find, pr
from rich.progress import Progress, BarColumn, TextColumn
from rich.console import Console
from rich.table import Table
from red_wing.localization import (
    collect_repos,
    localize_buggy_files_with_GUI_data,
    localize_buggy_files_without_GUI_data,
    hits_at_k,
    calculate_map,
    calculate_mrr,
    calculate_effectiveness,
    calculate_improvement,
)
import inquirer
import os
from types import SimpleNamespace
from transformers import AutoTokenizer, AutoModel
from experimental_unixcoder.bug_localization import BugLocalization

console = Console()
selected_model = None
# ANSI escape codes for coloring output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"

availableModels = {}
huggingFaceModels = [
    "Salesforce/codet5p-110m-embedding",
    "microsoft/unixcoder-base",
    "bigcode/starcoder2-3b",
]

def parse_cli_arguments():
    global selected_model
    # Define the cache file path in the user's home directory
    cache_file = os.path.expanduser("~/.red_wing_last_repo_home")
    default_repo_home = None
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            default_repo_home = f.read().strip()

    # ask common questions: repo home path, verbose, mode, and iteration mode.
    common_questions = [
        inquirer.Text(
            "path", message="Enter the repo home path", default=default_repo_home
        ),
        inquirer.Confirm("v", message="Enable verbose output?", default=False),
        inquirer.List(
            "mode",
            message="Select localization mode",
            choices=[
                ("Run enhanced localization (default)", "default"),
                (
                    "Calculate relative improvement between base and GUI-enhanced rankings",
                    "m",
                ),
                ("Run base localization", "b"),
            ],
        ),
        inquirer.List(
            "iteration",
            message="Select iteration mode",
            choices=[
                ("Iterate over all repos", "a"),
                ("Select number of repos to randomly select", "r"),
                ("Select one or more repo IDs", "i"),
            ],
        ),
    ]
    answers = inquirer.prompt(common_questions)

    # Cache the repo home path for future runs.
    with open(cache_file, "w") as f:
        f.write(answers["path"])

    # ask additional questions based on the selected iteration mode.
    if answers["iteration"] == "r":
        additional_questions = [
            inquirer.Text(
                "repo_count", message="Enter number of repos to randomly select"
            )
        ]
        extra_answers = inquirer.prompt(additional_questions)
        answers.update(extra_answers)
        answers["repo_ids"] = None
    elif answers["iteration"] == "i":
        additional_questions = [
            inquirer.Text(
                "repo_ids", message="Enter one or more repo IDs separated by spaces"
            )
        ]
        extra_answers = inquirer.prompt(additional_questions)
        answers.update(extra_answers)
        answers["repo_count"] = None
    else:
        answers["repo_count"] = None
        answers["repo_ids"] = None

    # ask for the number of loops.
    loop_question = [
        inquirer.Text("loop", message="Enter number of loops", default="1")
    ]
    loop_answer = inquirer.prompt(loop_question)
    answers.update(loop_answer)

    # ask for the model selection.
    model_question = [
        inquirer.List(
            "model",
            message="Select a model",
            choices=[(model, model) for model in huggingFaceModels],
        )
    ]
    model_answer = inquirer.prompt(model_question)
    answers.update(model_answer)

    # Process mode selection: set flags for improvement or base mode.
    m = answers["mode"] == "m"
    b = answers["mode"] == "b"
    loop = int(answers["loop"])
    repo_count = int(answers["repo_count"]) if answers.get("repo_count") else None
    repo_ids = (
        [int(x) for x in answers["repo_ids"].split()]
        if answers.get("repo_ids")
        else None
    )
    selected_model = answers["model"]
    BugLocalization(selected_model)
    return SimpleNamespace(
        path=answers["path"],
        v=answers["v"],
        m=m,
        b=b,
        a=(answers["iteration"] == "a"),
        repo_count=repo_count,
        repo_ids=repo_ids,
        loop=loop,
    )


def process_repos(repo_paths, verbose, enhanced: True):
    all_buggy_file_rankings = []
    best_rankings_per_bug = []
    with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} repos")
    ) as progress:
        task = progress.add_task("Processing repos...", total=len(repo_paths))
        for path in repo_paths:
            if (enhanced):
                rankings = localize_buggy_files_with_GUI_data(path, verbose=verbose)
            else:
                rankings = localize_buggy_files_without_GUI_data(path, verbose=verbose)
            all_buggy_file_rankings.append(rankings)
            if rankings:
                best_rank = min(r[2] for r in rankings)
                best_rankings_per_bug.append(best_rank)
            else:
                best_rankings_per_bug.append(9999)
            progress.update(task, advance=1)
    return all_buggy_file_rankings, best_rankings_per_bug


def output_metrics_with_improvement(all_buggy_file_rankings_gui, best_rankings_gui, best_rankings_base):
    # Compute Hits@10 for both GUI and baseline
    gui_hits_at_10 = hits_at_k(10, best_rankings_gui)
    base_hits_at_10 = hits_at_k(10, best_rankings_base)

    improvement = calculate_improvement(gui_hits_at_10, base_hits_at_10)

    output_metrics(all_buggy_file_rankings_gui, best_rankings_gui, improvement)

    improvement_table = Table(title="Relative Improvement Metrics")
    improvement_table.add_column("Metric", justify="left", style="cyan")
    improvement_table.add_column("Value", justify="center", style="magenta")
    improvement_table.add_row("Relative Improvement @ 10", f"{improvement:.3f}")

    base_hits_table = Table(title="BASE HITS AT 10")
    base_hits_table.add_column("Metric", justify="left", style="cyan")
    base_hits_table.add_column("Value", justify="center", style="magenta")
    base_hits_table.add_row("Base Hits @ 10", f"{base_hits_at_10}")

    gui_hits_table = Table(title="ENHANCED HITS AT 10")
    gui_hits_table.add_column("Metric", justify="left", style="cyan")
    gui_hits_table.add_column("Value", justify="center", style="magenta")
    gui_hits_table.add_row("Ehanced Hits @ 10", f"{gui_hits_at_10}")

    console.print("\n")
    console.print(improvement_table)


def output_metrics(all_buggy_file_rankings, best_rankings_per_bug, improvement: None):
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

    map = calculate_map(all_buggy_file_rankings)

    mrr = calculate_mrr(all_buggy_file_rankings)

    effectiveness = calculate_effectiveness(all_buggy_file_rankings) * 100

    current_time = datetime.datetime.now().strftime("%m%d%y%H%M")
    csv_file_name = f"metrics/{current_time}.csv"
    os.makedirs('metrics', exist_ok=True)
    with open(csv_file_name, "w") as f:
        f.write(f"hits@50, {hits_50}/{total_bugs}, {hits_at_50_ratio:.2f}\n")
        f.write(f"hits@25, {hits_25}/{total_bugs}, {hits_at_25_ratio:.2f}\n")
        f.write(f"hits@10, {hits_10}/{total_bugs}, {hits_at_10_ratio:.2f}\n")
        f.write(f"hits@5, {hits_5}/{total_bugs}, {hits_at_5_ratio:.2f}\n")
        f.write(f"hits@1, {hits_1}/{total_bugs}, {hits_at_1_ratio:.2f}\n")
        f.write(f"\n")

        f.write(f"map, {map:.3f}\n")
        f.write(f"\n")

        f.write(f"mrr, {mrr:.3f}\n")
        f.write(f"\n")

        f.write(f"best effectiveness, {effectiveness[0]}\n")
        f.write(f"worst effectiveness, {effectiveness[1]}\n")
        f.write(f"mean effectiveness, {effectiveness[2]:.3f}\n")
        f.write(f"\n")

        if improvement:
            f.write(f"relative improvement, {improvement:.3f}\n")

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

    map_table = Table(title="Mean Average Precision Metrics")
    map_table.add_column("Metric", justify="left", style="cyan")
    map_table.add_column("Value", justify="center", style="magenta")
    map_table.add_row("MAP", f"{map:.3f}")
    console.print("\n")
    console.print(map_table)

    mrr_table = Table(title="Mean Reciprocal Rank Metrics")
    mrr_table.add_column("Metric", justify="left", style="cyan")
    mrr_table.add_column("Value", justify="center", style="magenta")
    mrr_table.add_row("MRR", f"{mrr:.3f}")
    console.print("\n")
    console.print(mrr_table)

    console.print(f"\nMetrics saved to {csv_file_name}")
    effectiveness_table = Table(title="Effectiveness Metrics")
    effectiveness_table.add_column("Metric", justify="left", style="cyan")
    effectiveness_table.add_column("Value", justify="center", style="magenta")
    effectiveness_table.add_row("Best Effectiveness", f"{effectiveness[0]}")
    effectiveness_table.add_row("Worst Effectiveness", f"{effectiveness[1]}")
    effectiveness_table.add_row("Mean Effectiveness", f"{effectiveness[2]:.3f}")
    console.print("\n")
    console.print(effectiveness_table)


# New function to output metrics to bigMetrics.csv without rankings details
def output_big_metrics(all_buggy_file_rankings, best_rankings_per_bug, improvement, loop_number):
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

    map_value = calculate_map(all_buggy_file_rankings)
    mrr_value = calculate_mrr(all_buggy_file_rankings)
    effectiveness = calculate_effectiveness(all_buggy_file_rankings)

    with open("bigMetrics.csv", "a") as f:
        f.write(f"running loop {loop_number}\n")
        f.write(f"hits@50, {hits_50}/{total_bugs}, {hits_at_50_ratio:.2f}\n")
        f.write(f"hits@25, {hits_25}/{total_bugs}, {hits_at_25_ratio:.2f}\n")
        f.write(f"hits@10, {hits_10}/{total_bugs}, {hits_at_10_ratio:.2f}\n")
        f.write(f"hits@5, {hits_5}/{total_bugs}, {hits_at_5_ratio:.2f}\n")
        f.write(f"hits@1, {hits_1}/{total_bugs}, {hits_at_1_ratio:.2f}\n")
        f.write("\n")
        f.write(f"map, {map_value:.3f}\n")
        f.write("\n")
        f.write(f"mrr, {mrr_value:.3f}\n")
        f.write("\n")
        f.write(f"best effectiveness, {effectiveness[0]}\n")
        f.write(f"worst effectiveness, {effectiveness[1]}\n")
        f.write(f"mean effectiveness, {effectiveness[2]:.3f}\n")
        f.write("\n")
        if improvement:
            f.write(f"relative improvement, {improvement:.3f}\n")
            f.write("\n")


# New function to output metrics with improvement to bigMetrics.csv without rankings details
def output_big_metrics_with_improvement(all_buggy_file_rankings_gui, best_rankings_gui, best_rankings_base,
                                        loop_number):
    gui_hits_at_10 = hits_at_k(10, best_rankings_gui)
    base_hits_at_10 = hits_at_k(10, best_rankings_base)
    improvement_value = calculate_improvement(gui_hits_at_10, base_hits_at_10)

    total_bugs = len(best_rankings_gui)
    hits_50 = hits_at_k(50, best_rankings_gui)
    hits_25 = hits_at_k(25, best_rankings_gui)
    hits_10 = hits_at_k(10, best_rankings_gui)
    hits_5 = hits_at_k(5, best_rankings_gui)
    hits_1 = hits_at_k(1, best_rankings_gui)
    hits_at_50_ratio = hits_50 / total_bugs if total_bugs > 0 else 0
    hits_at_25_ratio = hits_25 / total_bugs if total_bugs > 0 else 0
    hits_at_10_ratio = hits_10 / total_bugs if total_bugs > 0 else 0
    hits_at_5_ratio = hits_5 / total_bugs if total_bugs > 0 else 0
    hits_at_1_ratio = hits_1 / total_bugs if total_bugs > 0 else 0

    map_value = calculate_map(all_buggy_file_rankings_gui)
    mrr_value = calculate_mrr(all_buggy_file_rankings_gui)
    effectiveness = calculate_effectiveness(all_buggy_file_rankings_gui)

    with open("bigMetrics.csv", "a") as f:
        f.write(f"running loop {loop_number}\n")
        f.write(f"hits@50, {hits_50}/{total_bugs}, {hits_at_50_ratio:.2f}\n")
        f.write(f"hits@25, {hits_25}/{total_bugs}, {hits_at_25_ratio:.2f}\n")
        f.write(f"hits@10, {hits_10}/{total_bugs}, {hits_at_10_ratio:.2f}\n")
        f.write(f"hits@5, {hits_5}/{total_bugs}, {hits_at_5_ratio:.2f}\n")
        f.write(f"hits@1, {hits_1}/{total_bugs}, {hits_at_1_ratio:.2f}\n")
        f.write("\n")
        f.write(f"map, {map_value:.3f}\n")
        f.write("\n")
        f.write(f"mrr, {mrr_value:.3f}\n")
        f.write("\n")
        f.write(f"best effectiveness, {effectiveness[0]}\n")
        f.write(f"worst effectiveness, {effectiveness[1]}\n")
        f.write(f"mean effectiveness, {effectiveness[2]:.3f}\n")
        f.write("\n")
        f.write(f"relative improvement, {improvement_value:.3f}\n")
        f.write("\n")
