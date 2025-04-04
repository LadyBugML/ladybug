import torch
from transformers import AutoTokenizer, AutoModel
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

try:
    from experimental_unixcoder.unixcoder import UniXcoder  # Try live version
except ImportError:
    from unixcoder import UniXcoder  # Fallback to testing version


class BugLocalization:
    def __init__(self, max_tokens=512, top_k=1):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained("microsoft/unixcoder-base")
        self.model = AutoModel.from_pretrained("microsoft/unixcoder-base").to(self.device)

        self.model.eval()
        self.max_tokens = max_tokens
        self.top_k = top_k

        # Initialize tree-sitter
        JAVA_LANGUAGE = Language(tsjava.language())
        self.parser = Parser(JAVA_LANGUAGE)


    def encode_code(self, code_str, verbose):
        """
        Encodes source code into embeddings using the model.

        Args:
            code_str (str): The source code to encode.

        Returns:
            list: A list of normalized embeddings for the code chunks.
        """

        chunks = self.extract_methods_from_java(code_str)

        if verbose:
            for i, chunk in enumerate(chunks, 1):
                print(f"===== CHUNK {i}/{len(chunks)} =====\n")
                print(f"{chunk}\n")
        
        embeddings = []
        for chunk in chunks:
            inputs = self.tokenizer(chunk, return_tensors="pt", truncation=True, padding=True, max_length=self.max_tokens).to(self.device)
            with torch.no_grad():
                output = self.model(**inputs)[0]  # shape: [1, 256]
                norm_embedding = torch.nn.functional.normalize(output, p=2, dim=-1)
                embeddings.append(norm_embedding.squeeze(0).tolist())

        return embeddings


    def encode_bug_report(self, text):
        """
        Encodes a bug report into an embedding using the model.

        Args:
            text (str): The bug report text to encode.

        Returns:
            list: A normalized embedding for the bug report.
        """

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True).to(self.device)
        with torch.no_grad():
            output = self.model(**inputs)[0]
            norm_embedding = torch.nn.functional.normalize(output, p=2, dim=-1)
            return [norm_embedding.squeeze(0).tolist()]


    def extract_methods_from_java(self, source_code):
        """
        Extracts method declarations from Java source code and splits them into chunks.

        Args:
            source_code (str): The Java source code to process.

        Returns:
            list: A list of method chunks extracted from the source code.
        """

        tree = self.parser.parse(bytes(source_code, "utf-8"))
        root_node = tree.root_node
        chunks = []

        def walk(node):
            if node.type == "method_declaration":
                method_text = self.node_text(bytes(source_code, "utf-8"), node)
                tokens = self.tokenizer(method_text, truncation=True, add_special_tokens=False)["input_ids"]
                token_len = len(tokens)

                if token_len > self.max_tokens:
                    stride = self.max_tokens // 2
                    for i in range(0, token_len, stride):
                        sub_tokens = tokens[i:i + self.max_tokens]
                        decoded = self.tokenizer.decode(sub_tokens, skip_special_tokens=True)
                        chunks.append(decoded)
                        if len(sub_tokens) < self.max_tokens:
                            break
                else:
                    chunks.append(method_text)

            for child in node.children:
                walk(child)

        walk(root_node)

        return chunks


    def node_text(self, source_bytes, node):
        """
        Extracts the text corresponding to a tree-sitter node.

        Args:
            source_bytes (bytes): The source code as bytes.
            node (tree_sitter.Node): The tree-sitter node.

        Returns:
            str: The text corresponding to the node.
        """

        return source_bytes[node.start_byte:node.end_byte].decode('utf-8')


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
