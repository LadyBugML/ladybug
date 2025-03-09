import torch
import ollama

try:
    from experimental_unixcoder.unixcoder import UniXcoder  # Try live version
except ImportError:
    from unixcoder import UniXcoder  # Fallback to testing version


class BugLocalization:
    def __init__(self):
        # Set up device and initialize the UniXcoder model
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print("CUDA is available" if torch.cuda.is_available() else "CUDA is not available")
        #self.model = UniXcoder("microsoft/unixcoder-base")
        #self.model.to(self.device)

        # Encoding for Long Texts
    def encode_text(self, text):
        """
        Encodes long text by splitting it into chunks of roughly 500 characters
        (before tokenization). Each chunk is tokenized and encoded individually.
        Returns a list of embeddings (as lists), one for each chunk.
        """
        chunk_size = 100000  # Split by 500 characters as an example
        embeddings = []

        # Split text into roughly 500-character chunks
        for i in range(0, len(text), chunk_size):
            text_chunk = text[i:i + chunk_size]
            print(f"Processing text chunk {i // chunk_size + 1}")  # Debug print

            # Tokenize the chunk
            #tokens = self.model.tokenize([text_chunk], mode="<encoder-only>")[0]
            #source_ids = torch.tensor([tokens]).to(self.device)
            
            # Get model output
            try:
                #_, embedding = self.model(source_ids)
                #norm_embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
                ollama_output = ollama.embed(model='deepseek-coder-v2:latest', input=text_chunk)
                embedding_vector = ollama_output["embeddings"]
                """
                if embedding_vector:  # Make sure embedding is not empty
                    tensor_embedding = torch.tensor(embedding_vector, device=self.device)  # Convert to a PyTorch tensor
                    norm_embedding = torch.nn.functional.normalize(tensor_embedding, p=2, dim=0)  # Normalize to unit length
                    embeddings.append(norm_embedding.tolist())  # Convert back to list and store
                """
                # Normalize embedding
                embedding_vector =  torch.tensor(embedding_vector, dtype=torch.float32)
                embedding_vector = torch.nn.functional.normalize(embedding_vector, p=2, dim=1)

                # Store normalized embedding as list
                embeddings.append(embedding_vector.tolist())  
                
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
        similarities = []

        for file_id, file_embeddings in db_embeddings:
            max_similarity = float('-inf')

            # Convert query embeddings and file embeddings from lists back to tensors
            for query_embedding in query_embeddings:
                query_tensor = torch.tensor(query_embedding, device=self.device)
                for file_embedding in file_embeddings:
                    file_tensor = torch.tensor(file_embedding, device=self.device)

                    # Compute similarity
                    similarity = torch.nn.functional.cosine_similarity(
                        query_tensor, file_tensor, dim=1
                    ).item()

                    if similarity > max_similarity:
                        max_similarity = similarity

            similarities.append((file_id, max_similarity))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities

if __name__ == "__main__":
    # Create an instance of the BugLocalization class
    bug_localizer = BugLocalization()
    
    # Example bug report text (long text)
    sample_text = "Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens...Your long bug report text that exceeds 512 tokens..."
    print("Encoding bug report for bug localization...")
    query_embeddings = bug_localizer.encode_text(sample_text)
    
    # Example database embeddings for files (each with long text)
    file1_text = "Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens..Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens...Contents of file 1 that is over 512 tokens..."
    file2_text = "Contents of file 2 that is over 512 tokens..."
    
    file1_embeddings = bug_localizer.encode_text(file1_text)
    # print(file1_embeddings)
    file2_embeddings = bug_localizer.encode_text(file2_text)
    # print(file2_embeddings)
    
    # Prepare data for MongoDB storage (embeddings as lists)
    db_embeddings = [
        ("file1", file1_embeddings),
        ("file2", file2_embeddings)
    ]
    
    # Rank files based on similarity to the query
    print("Ranking files based on similarity...")
    ranked_files = bug_localizer.rank_files(query_embeddings, db_embeddings)
    print("Ranked files:", ranked_files)
