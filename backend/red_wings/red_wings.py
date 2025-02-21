#!/usr/bin/env python3
import argparse
import random


def main():
    parser = argparse.ArgumentParser(description="Red Wings script")
    parser.add_argument('-p', required=True, dest="path", help="Repo home path")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-a', action='store_true', help="Activate flag -a")
    group.add_argument('-r', type=int, dest="repo_count", help="Number of repos as an integer")
    group.add_argument('-i', type=int, nargs='+', dest="repo_ids", help="One or more repo IDs as integers")
    args = parser.parse_args()

    print("Repo home path:", args.path)
    if args.a:
        print("Flag -a activated")
    if args.repo_count is not None:
        print("Number of repos:", args.repo_count)
    if args.repo_ids is not None:
        print("Repo IDs:", args.repo_ids)

def sample_repos(n):
    return random.sample(range(1, 100), n)

if __name__ == '__main__':
    main()
