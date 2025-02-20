import logging
import os


class Fake_preprocessor:
    @staticmethod
    def preprocess_files(repo_dir: str):
        """
        Walk through the repository directory, process each non-hidden file,
        and generate embeddings while ignoring hidden files and directories.

        Args:
            repo_dir (str): The path to the repository directory.

        Returns:
            list: A list of embedding dictionaries for each processed file.
        """
        logger = logging.getLogger(__name__)
        embeddings = []
        logger.info(f"Starting preprocessing of repository: {repo_dir}")

        try:
            for dirpath, dirnames, filenames in os.walk(repo_dir):
                # Modify dirnames in-place to skip hidden directories
                original_dirnames = dirnames.copy()
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                skipped_dirs = set(original_dirnames) - set(dirnames)
                for skipped_dir in skipped_dirs:
                    logger.debug(f"Skipped hidden directory: {os.path.join(dirpath, skipped_dir)}")

                for filename in filenames:
                    # Skip hidden files
                    if filename.startswith('.'):
                        logger.debug(f"Skipped hidden file: {os.path.join(dirpath, filename)}")
                        continue

                    file_path = os.path.join(dirpath, filename)
                    # Placeholder for actual embedding logic
                    embedding = {
                        'file_path': file_path,
                        'embedding': 'dummy_embedding',  # Replace with actual embedding logic
                    }
                    embeddings.append(embedding)
                    logger.debug(f"Processed file: {file_path}")

        except Exception as e:
            logger.error(f"Error during preprocessing: {e}")
            raise  # Re-raise exception after logging

        logger.info(f"Completed preprocessing. Total files processed: {len(embeddings)}")
        return embeddings
