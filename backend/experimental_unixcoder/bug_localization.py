import torch
import numpy as np

try:
    from experimental_unixcoder.unixcoder import UniXcoder  # Try live version
except ImportError:
    from unixcoder import UniXcoder  # Fallback to testing version


class BugLocalization:
    def __init__(self):
        # Set up device and initialize the UniXcoder model
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # print("CUDA is available" if torch.cuda.is_available() else "CUDA is not available")
        self.model = UniXcoder("microsoft/unixcoder-base")
        self.model.to(self.device)

        # Encoding for Long Texts
    def encode_text(self, text, verbose=False):
        """
        Encodes long text by splitting it into chunks of roughly 500 characters
        (before tokenization). Each chunk is tokenized and encoded individually.
        Returns a list of embeddings (as lists), one for each chunk.
        """
        chunk_size = 500  # Split by 500 characters as an example
        embeddings = []

        # Split text into roughly 500-character chunks
        for i in range(0, len(text), chunk_size):
            text_chunk = text[i:i + chunk_size]
            if verbose:
                print(f"Processing text chunk {i // chunk_size + 1}")  # Debug print

            # Tokenize the chunk
            tokens = self.model.tokenize([text_chunk], mode="<encoder-only>")[0]
            source_ids = torch.tensor([tokens]).to(self.device)
            
            # Get model output
            try:
                _, embedding = self.model(source_ids)
                norm_embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
                embeddings.append(norm_embedding.tolist())  # Store normalized embedding as list
            except Exception as e:
                print(f"Error processing chunk {i // chunk_size + 1}: {e}")
                continue
        # print(embeddings)
        return embeddings


    # File Ranking for Bug Localization
    def rank_files(self, query_embeddings, db_embeddings):
        """
        Ranks files based on similarity to the query embeddings.

        Parameters:
        - query_embeddings: A list of embeddings (as lists) for the query (bug report).
        - db_embeddings: A list of tuples, where each tuple contains (file_id, embeddings)
                         where embeddings is a list of embeddings (as lists) for that file.

        Returns:
        - A sorted list of (file_id, max_similarity_score) tuples in descending order of similarity.
        """
        similarity_score_list = []

        for file_id, code_embeddings in db_embeddings:
            # Convert query embeddings and code file embeddings from lists back to tensors
            # Handling the possibility of a long bug report file...
            for query_emb in query_embeddings:
                query_tensor = torch.tensor(query_emb, device=self.device)
                # Pass code_embeddings through helper methods to take max similarity of the file (with respect to its chunks).
                max_similarity = self.calculate_similarity(code_embeddings, query_tensor)

            similarity_score_list.append((file_id, max_similarity))

        similarity_score_list.sort(key=lambda x: x[1], reverse=True)
        return similarity_score_list

    # Helper method to calculate similarity between the query and code embeddings.
    def calculate_similarity(self, code_embeddings, query_tensor):
        """
        Calculate the maximum similarity score between the query tensor and a list of code embeddings.
        This method calculates the similarity score using the dot product (or cosine similarity)
        between the query tensor and each code embedding tensor.
        Parameters:
        - code_embeddings: A list of code embeddings (as lists) for a specific file.
        - query_tensor: The query tensor for the bug report.
        Returns:
        - The maximum similarity score (float) between the query tensor and the code embeddings.
        """
        # Initialize a list to store similarity scores for each code embedding
        # This will store the similarity scores for each chunk of code embeddings
        sim_score_list = []
        # We must turn the code embeddings (which are lists) into tensors for similarity calculation.
        for code_emb in code_embeddings:
            code_tensor = torch.tensor(code_emb, device=self.device)
            score = torch.einsum("ac,bc->ab", code_tensor, query_tensor)
            score = score[0].cpu().tolist()
            sim_score_list.append(score[0])
        return np.max(sim_score_list)
