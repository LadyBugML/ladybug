import os
import shutil
import argparse

def main():
    parser = argparse.ArgumentParser(description="Combine code repository with bug data into a unified structure.")
    parser.add_argument('--repos', required=True, help="Path to the folder containing code repositories (e.g., bug-X folders)")
    parser.add_argument('--data', required=True, help="Path to the folder containing BugReports, BugLocalizationGroundTruth, and TraceReplayer-Data")
    parser.add_argument('--dest', required=True, help="Destination folder where the combined structure will be created")
    args = parser.parse_args()
    
    repos_dir = args.repos
    data_dir = args.data
    dest_dir = args.dest

    # Define the paths for the three data subfolders
    bug_reports_dir = os.path.join(data_dir, "BugReports")
    bug_localization_dir = os.path.join(data_dir, "BugLocalizationGroundTruth")
    trace_replayer_dir = os.path.join(data_dir, "TraceReplayer-Data")
    
    # Ensure the destination folder exists
    os.makedirs(dest_dir, exist_ok=True)
    
    # Process each repository in the repos folder
    for repo_name in os.listdir(repos_dir):
        repo_path = os.path.join(repos_dir, repo_name)
        if os.path.isdir(repo_path) and repo_name.startswith("bug-"):
            # Extract the BUG_ID from the repository name (e.g., bug-2 -> 2)
            bug_id = repo_name.split("bug-")[-1]
            
            # Create the destination folder for this bug repo
            bug_dest_dir = os.path.join(dest_dir, repo_name)
            os.makedirs(bug_dest_dir, exist_ok=True)
            
            # 1. Copy bug_report_{BUG_ID}.txt
            bug_report_filename = f"bug_report_{bug_id}.txt"
            src_bug_report = os.path.join(bug_reports_dir, bug_report_filename)
            if os.path.exists(src_bug_report):
                shutil.copy2(src_bug_report, os.path.join(bug_dest_dir, bug_report_filename))
            else:
                print(f"Warning: {src_bug_report} does not exist.")
                
            # 2. Copy {BUG_ID}.json
            bug_json_filename = f"{bug_id}.json"
            src_bug_json = os.path.join(bug_localization_dir, bug_json_filename)
            if os.path.exists(src_bug_json):
                shutil.copy2(src_bug_json, os.path.join(bug_dest_dir, bug_json_filename))
            else:
                print(f"Warning: {src_bug_json} does not exist.")
                
            # 3. Copy Execution-1.json from TraceReplayer-Data/TR{BUG_ID}
            trace_folder = f"TR{bug_id}"
            src_trace_execution = os.path.join(trace_replayer_dir, trace_folder, "Execution-1.json")
            if os.path.exists(src_trace_execution):
                shutil.copy2(src_trace_execution, os.path.join(bug_dest_dir, "Execution-1.json"))
            else:
                print(f"Warning: {src_trace_execution} does not exist.")
            
            # 4. Create a 'code' folder and copy the repository into it
            code_dest_dir = os.path.join(bug_dest_dir, "code")
            os.makedirs(code_dest_dir, exist_ok=True)
            dest_repo_code_path = os.path.join(code_dest_dir, repo_name)
            
            # Copy the entire repository folder (non-destructive copy)
            try:
                shutil.copytree(repo_path, dest_repo_code_path)
            except FileExistsError:
                # If the destination repo folder already exists, you may choose to skip or merge.
                print(f"Folder {dest_repo_code_path} already exists. Skipping copy of repository code.")
            
            print(f"Processed repository: {repo_name}")

if __name__ == "__main__":
    main()
