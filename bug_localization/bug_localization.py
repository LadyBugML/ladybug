# https://github.com/microsoft/CodeBERT/blob/master/UniXcoder/README.md
import torch
from unixcoder import UniXcoder

class BugLocalization:
    def __init__(self):
        # Set up device and initialize the UniXcoder model
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = UniXcoder("microsoft/unixcoder-base")
        self.model.to(self.device)

    # Encoding Embeddings
    def encode_text(self, text):
        """
        Encodes a single text (bug report, function, or body of code) into an embedding.
        Args:
            text: The body of text.

        Returns:
            embedding: The embedding for the body of text.
        """
        tokens_ids = self.model.tokenize([text], max_length=512, mode="<encoder-only>")
        source_ids = torch.tensor(tokens_ids).to(self.device)
        _, embedding = self.model(source_ids)
        norm_embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
        return norm_embedding

    def encode_batch(self, texts):
        """
        Encodes a batch of texts into embeddings.
        
        Args:
            texts: The text batch.

        Returns:
            embeddings: The embeddings for the batch of texts.
        """
        embeddings = []
        for text in texts:
            embeddings.append(self.encode_text(text))
        return embeddings

    # File Ranking for Bug Localization
    def rank_files(self, query_embedding, db_embeddings):
        """
        Ranks files based on similarity to the query embedding.
        
        Args:
            query_embedding: The embedding of the bug report or query.
            db_embeddings: A list of tuples, where each tuple contains (file_id, embedding)
                         representing the file's unique identifier and its precomputed embedding.
                         
        Returns:
            similarities: A sorted list of (file_id, similarity_score) tuples in descending order of similarity.
        """
        # Normalize the query embedding
        # norm_query_embedding = torch.nn.functional.normalize(query_embedding, p=2, dim=1)
        
        # Calculate similarity scores
        similarities = []
        for file_id, embedding in db_embeddings:
            db_embedding = torch.tensor(embedding).to(self.device)
            similarity = torch.einsum("ac,bc->ab", db_embedding, query_embedding).item()
            similarities.append((file_id, similarity))
        
        # Sort files by similarity score in descending order
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities
