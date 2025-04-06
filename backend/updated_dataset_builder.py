import os
import shutil
import argparse
import json

# Final state mappings: bug-id -> final state
final_states = {
    "2": 41, "8": 14, "10": 15, "11": 2, "18": 21, "19": 5, 
    "44": 21, "45": 11, "53": 18, "54": 10, "55": 50, "56": 19, 
    "71": 17, "76": 6, "84": 13, "87": 32, "92": 4, "106": 13, "110": 5,
    "117": 11, "128": 28, "129": 33, "130": 2, "135": 14, "158": 10, 
    "159": 34, "160": 14, "162": 6, "168": 3, "191": 1, "192": 12, 
    "193": 5, "199": 11, "200": 9, "201": 37, "206": 14, "209": 50, 
    "227": 25, "248": 45, "256": 19, "271": 22, "275": 8, "1028": 13,
    "1073": 8, "1089": 7, "1096": 14, "1130": 12, "1146": 6, "1147": 20, "1150": 11,
    "1151": 5, "1198": 20, "1202": 11, "1205": 22, "1207": 13, "1213": 44,
    "1214": 13, "1215": 31, "1222": 17, "1223": 19, "1224": 39, "1228": 24,
    "1299": 20, "1389": 2, "1399": 14, "1402": 15, "1403": 24, "1406": 20, "1425": 18,
    "1428": 12, "1430": 21, "1441": 18, "1445": 14, "1446": 18, "1481": 16, 
    "1563": 7, "1568": 8, "1640": 4, "1641": 9, "1645": 35
}

def process_trace(src_trace_path, dest_trace_path, bug_id):
    if os.path.exists(src_trace_path):
        with open(src_trace_path, 'r') as f:
            trace_data = json.load(f)
        
        # Only process if trace contains "steps" and we have a final state mapping for this bug
        if "steps" in trace_data:
            if bug_id in final_states:
                final_state = final_states[bug_id]
                desired_seq = final_state + 1
                new_steps = []
                for step in trace_data["steps"]:
                    # Collect steps that are less than or equal to the desired sequence step
                    if step.get("sequenceStep", 0) <= desired_seq:
                        new_steps.append(step)
                    else:
                        # Stop collecting once we've passed the desired sequence step
                        break
                if new_steps:
                    # Ensure the last step's sequenceStep is exactly desired_seq
                    new_steps[-1]["sequenceStep"] = desired_seq
                trace_data["steps"] = new_steps
            else:
                print(f"Warning: No final state mapping for bug {bug_id}. Leaving trace unmodified.")
        else:
            print(f"Warning: No 'steps' found in trace for bug {bug_id}.")
        
        with open(dest_trace_path, 'w') as f:
            json.dump(trace_data, f, indent=4)
    else:
        print(f"Warning: {src_trace_path} does not exist.")

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
                
            # 2. Copy {BUG_ID}.json from BugLocalizationGroundTruth
            bug_json_filename = f"{bug_id}.json"
            src_bug_json = os.path.join(bug_localization_dir, bug_json_filename)
            if os.path.exists(src_bug_json):
                shutil.copy2(src_bug_json, os.path.join(bug_dest_dir, bug_json_filename))
            else:
                print(f"Warning: {src_bug_json} does not exist.")
                
            # 3. Process Execution-1.json from TraceReplayer-Data/TR{BUG_ID} and trim its steps
            trace_folder = f"TR{bug_id}"
            src_trace_execution = os.path.join(trace_replayer_dir, trace_folder, "Execution-1.json")
            dest_trace_execution = os.path.join(bug_dest_dir, "Execution-1.json")
            process_trace(src_trace_execution, dest_trace_execution, bug_id)
            
            # 4. Create a 'code' folder and copy the repository into it
            code_dest_dir = os.path.join(bug_dest_dir, "code")
            os.makedirs(code_dest_dir, exist_ok=True)
            dest_repo_code_path = os.path.join(code_dest_dir, repo_name)
            
            # Copy the entire repository folder (non-destructive copy)
            try:
                shutil.copytree(repo_path, dest_repo_code_path)
            except FileExistsError:
                print(f"Folder {dest_repo_code_path} already exists. Skipping copy of repository code.")
            
            print(f"Processed repository: {repo_name}")

if __name__ == "__main__":
    main()
