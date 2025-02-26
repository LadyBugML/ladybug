from services.worker_service import send_update_to_probot

CANNED_RESPONSES = {
    "init_start": "✅ **Initialization Started**: Validating repository information.",
    "cloning_repo": "✅ **Cloning Repository**: Repository cloned successfully.",
    "init_failed": "❌ **Initialization Failed**: {error}",
    "post_processing_warning": "⚠️ **Post-Processing Warning**: {error}",
    "embeddings_stored": "✅ **Embeddings Stored**: Embeddings computed and stored successfully.",
    "init_complete": "✅ **Initialization Completed**: All embeddings are up to date.",
    "cloning_complete": "✅ **Cloning Completed**: Repository cloned successfully.",
    "no_java_files": "⚠️ **No Java Files Found**: No `.java` files detected in the repository.",
    "embeddings_calculated": "✅ **Embeddings Calculated**: Wow that took a while huh.",
    "storing_embeddings": "✅ **Storing Embeddings**: Storing repository information and embeddings in the database.",
    "repo_embeddings_fetched": "✅ **Repository Embeddings Fetched**: Retrieved all repository embeddings from the database.",
    "repo_embeddings_retrieval_failed": "❌ **Repository Embeddings Retrieval Failed**: Could not fetch all repository embeddings from the database.",
    "corpus_embeddings_fetched": "✅ **Corpus Embeddings Fetched**: Retrieved all corpus embeddings from the database.",
    "corpus_embeddings_retrieval_failed": "❌ **Corpus Embeddings Retrieval Failed**: Could not fetch corpus embeddings from the database.",
    "report_processing_started": "✅ **Report Processing Started**: Repository information validated.",
    "report_written": "✅ **Report Written**: Issue has been written to the report file.",
    "report_writing_failed": "❌ **Report Writing Failed**: {error}",
    "bug_report_preprocessed": "✅ **Bug Report Preprocessed**: Bug report has been successfully preprocessed.",
    "preprocessing_failed": "❌ **Preprocessing Failed**: {error}",
    "sha_retrieval_failed": "⚠️ **SHA Retrieval Failed**: No stored commit SHA found.",
    "embeddings_status": "✅ **Embeddings Status**: Embeddings are up to date.",
    "embeddings_outdated": "✅ **Embeddings Outdated**: Recomputing embeddings due to new commits.",
    "embeddings_updated": "✅ **Embeddings Updated**: Embeddings have been recomputed and updated.",
    "source_code_files_fetched": "✅ **Source Code Files Fetched**: Retrieved all source code files from the database.",
    "source_code_retrieval_failed": "❌ **Source Code Retrieval Failed**: Could not fetch source code from the database.",
    "no_gui_data_note": "⚠️ **Note**: Rankings have been calculated _without_ GUI Data. Consider submitting a trace to boost rankings!",
    "bug_localization_completed": "🎯 **Bug Localization Completed**: Ranked relevant files identified.",
}


class ProbotMessenger:
    def __init__(self, repo_info, comment_id=-1):
        self.owner = repo_info['owner']
        self.repo = repo_info['repo_name']
        self.comment_id = comment_id

    def send(self, key, **kwargs):
        message_template = CANNED_RESPONSES.get(key, "")
        message = message_template.format(**kwargs) if kwargs else message_template
        send_update_to_probot(self.owner, self.repo, self.comment_id, message)
