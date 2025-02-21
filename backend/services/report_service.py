import logging
from flask import abort, jsonify

from experimental_unixcoder.bug_localization import BugLocalization
from services.db_service import fetch_all_embeddings, fetch_corpus_embeddings, process_and_patch_embeddings, retrieve_repo_file_contents, retrieve_stored_sha
from services.message_service import send_update_to_probot
from utils.preprocess_bug_report import preprocess_bug_report
from utils.file_utils import post_process_cleanup, write_file_for_report_processing
from utils.git_utils import extract_and_validate_repo_info, partial_clone
from utils.extract_gui_data import build_corpus, extract_gs_terms, extract_sc_terms, get_boosted_files

logger = logging.getLogger(__name__)

def process_report(data):

    GUI_DATA = True

    repository = data.get('repository')
    issue = data.get('issue')
    trace = data.get('trace')
    comment_id = data.get('comment_id')
    if comment_id is None:
        comment_id = -1

    if not repository or not issue:
        abort(400, description="Missing 'repository' or 'issue' in the data")

    logger.info("Received data from /report request.")

    # Extract Screen Component / GUI Screen Terms for boosting and query expansion
    sc_terms = extract_sc_terms(trace)
    gs_terms = extract_gs_terms(trace)

    if not gs_terms or not sc_terms:
        GUI_DATA = False
        logger.info("No GUI Data Detected")


    # Extract and validate repository information
    repo_info = extract_and_validate_repo_info(repository)
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "✅ **Report Processing Started**: Repository information validated.")

    # Write issue to report file
    try:
        report_file_path = write_file_for_report_processing(repo_info['repo_name'], issue)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Report Written**: Issue has been written to the report file.")
    except Exception as e:
        logger.error(f"Failed to write issue to file: {e}")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              f"❌ **Report Writing Failed**: {e}")
        abort(500, description="Failed to write issue to file")

    # Preprocess bug report
    try:
        preprocessed_bug_report = preprocess_bug_report(report_file_path, sc_terms)
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Bug Report Preprocessed**: Bug report has been successfully preprocessed.")
    except Exception as e:
        logger.error(f"Failed to preprocess bug report: {e}")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              f"❌ **Preprocessing Failed**: {e}")
        abort(500, description="Failed to preprocess bug report")

    # Retrieve the stored SHA
    stored_commit_sha = retrieve_stored_sha(repo_info['owner'], repo_info['repo_name'])
    if not stored_commit_sha:
        logger.info("No stored commit SHA found.")
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "⚠️ **SHA Retrieval Failed**: No stored commit SHA found.")
        return jsonify({"message": "Failed because no stored commit SHA"}), 500

    logger.info(f"Stored commit SHA: {stored_commit_sha}")

    # Check if embeddings and code file contents are up to date
    if stored_commit_sha == repo_info['latest_commit_sha']:
        logger.info('Embeddings are up to date.')
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Embeddings Status**: Embeddings are up to date.")
    else:
        logger.info('Embeddings are outdated. Recomputing embeddings.')
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "✅ **Embeddings Outdated**: Recomputing embeddings due to new commits.")
        try:
            changed_files = partial_clone(stored_commit_sha, repo_info)
            process_and_patch_embeddings(changed_files, repo_info)
            post_process_cleanup(repo_info)
            send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                                  "✅ **Embeddings Updated**: Embeddings have been recomputed and updated.")
        except Exception as e:
            logger.error(f"Failed to recompute embeddings: {e}")
            send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                                  f"❌ **Embeddings Update Failed**: {e}")
            abort(500, description=str(e))
        
    # Initialize Bug Localizer and ranked list
    bug_localizer = BugLocalization()
    top_ten_files = []
    
    # Ranking generation with GUI data
    if(GUI_DATA):
        # Fetch all source code files from DB for filtering + boosting with GUI data
        try:
            query = {
                "repo_name": repo_info['repo_name'],
                "owner": repo_info['owner']
            }
            repo_files = retrieve_repo_file_contents(query)    
            send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                                "✅ **Source Code Files Fetched**: Retrieved all source code files from the database.")
        except Exception as e:
            logger.info('Failed to find repo.')
            send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                                "❌ **Source Code Retrieval Failed**: Could not fetch source code from the database.")
            return jsonify({"message": "Failed to find repo."}), 405

        # Apply filtering and get boosted files
        corpus = build_corpus(repo_files, sc_terms, repo_info)
        boosted_files = get_boosted_files(repo_files, gs_terms)

        # Fetch corpus embeddings from database
        corpus_embeddings = fetch_corpus_embeddings(repo_info, corpus, comment_id)

        # Apply boosting and create rankings
        ranked_files = bug_localizer.rank_files(preprocessed_bug_report, corpus_embeddings)
        reranked_files = reorder_rankings(ranked_files, boosted_files)

        # Only return top ten files
        for i in range(min(10, len(reranked_files))):
            top_ten_files.append(reranked_files[i])

    # Ranking generation without GUI data
    else:
        # Fetch all embeddings from DB
        repo_embeddings = fetch_all_embeddings(repo_info, comment_id)
        ranked_files = bug_localizer.rank_files(preprocessed_bug_report, repo_embeddings)

        # Only return top ten files
        for i in range(min(10, len(ranked_files))):
            top_ten_files.append(ranked_files[i])
        
        send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                              "⚠️ **Note**: Rankings have beeen calculated _without_ GUI Data. Consider submitting a trace to boost rankings!")

    # Return rankings to GitHub
    send_update_to_probot(repo_info['owner'], repo_info['repo_name'], comment_id,
                          "🎯 **Bug Localization Completed**: Ranked relevant files identified.")
    return jsonify({"message": "Report processed successfully", "ranked_files": top_ten_files}), 200

def reorder_rankings(ranked_files: list[tuple], gs_files: list[str]):
    """
    Boosts GS files to the top of the ranking while preserving their relative order.

    Parameters:
        ranked_files: List of tuples (route, similarity_score), sorted by similarity score.
        gs_files: List or set of routes that should be prioritized.

    Returns:
        boosted_rankings: A reordered list with gs_files at the top in their original order.
    """

    gs_ranked = [item for item in ranked_files if item[0] in gs_files]
    non_gs_ranked = [item for item in ranked_files if item[0] not in gs_files]

    return gs_ranked + non_gs_ranked