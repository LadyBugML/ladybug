#!/usr/bin/env python3
import argparse
import os
import glob
import random


def collect_repos(repo_home, flag_all=False, repo_count=None, repo_ids=None):
    repo_paths = []

    if repo_ids is not None:
        for repo_id in repo_ids:
            repo_path = os.path.join(repo_home, f"bug-{repo_id}")
            # Verify that the repository directory exists.
            if os.path.isdir(repo_path):
                repo_paths.append(repo_path)
            else:
                print(f"Warning: Repository directory does not exist: {repo_path}")
    else:
        # Get all paths that match the pattern "bug-*"
        all_repos = sorted(glob.glob(os.path.join(repo_home, "bug-*")))
        all_repos = [r for r in all_repos if os.path.isdir(r)]

        if flag_all:
            repo_paths = all_repos
        elif repo_count > 0:
            if repo_count > len(all_repos):
                print(f"Requested {repo_count} repos but only found {len(all_repos)}. Using all available repos.")
                repo_paths = all_repos
            else:
                repo_paths = random.sample(all_repos, repo_count)
        else:
            print("Error: Invalid arguments provided")
            return []

    return repo_paths


def main():
    parser = argparse.ArgumentParser(description="Red Wings script")
    parser.add_argument('-p', required=True, dest="path", help="Repo home path")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-a', action='store_true', help="Iterate over all repos")
    group.add_argument('-r', type=int, dest="repo_count", help="Number of repos to randomly select")
    group.add_argument('-i', type=int, nargs='+', dest="repo_ids", help="One or more repo IDs")
    args = parser.parse_args()

    repo_home = args.path
    # Verify that the repository home path exists.
    if not os.path.isdir(repo_home):
        print(f"Error: The provided repo home path does not exist: {repo_home}")
        return

    repo_paths = collect_repos(
        repo_home,
        flag_all=args.a,
        repo_count=args.repo_count,
        repo_ids=args.repo_ids
    )

    if not repo_paths:
        print("Error: No repositories found")
        return

    print("Collected repo paths:")
    for path in repo_paths:
        initialize_repo(path)


def initialize_repo(repo_path):
    print(f"Initializing repository: {repo_path}")

if __name__ == '__main__':
    main()
