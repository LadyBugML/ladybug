import torch
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

try:
    from experimental_unixcoder.unixcoder import UniXcoder  # Try live version
except ImportError:
    from unixcoder import UniXcoder  # Fallback to testing version


class BugLocalization:
    def __init__(self, max_tokens=512, top_k=1):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = UniXcoder("microsoft/unixcoder-base")
        self.model.to(self.device)
        self.max_tokens = max_tokens
        self.top_k = top_k

        # Set up Tree-sitter for Java
        JAVA_LANGUAGE = Language(tsjava.language())
        self.parser = Parser(JAVA_LANGUAGE)

    # === Method 1: For Java Code ===
    def encode_code(self, code_str):
        """
        Extracts method-level chunks from Java code and returns a list of normalized embeddings.
        """
        chunks = self.extract_methods_from_java(code_str)
        embeddings = []

        # print(f"{len(chunks)} chunks extracted.")
        for chunk in chunks:
            
            tokens = self.model.tokenize([chunk], mode="<encoder-only>")[0]
            source_ids = torch.tensor([tokens]).to(self.device)

            try:
                _, embedding = self.model(source_ids)
                embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
                embeddings.append(embedding.squeeze(0).tolist())
            except Exception as e:
                print(f"Error embedding chunk: {e}")
                continue

        return embeddings

    # === Method 2: For Bug Reports (Natural Language) ===
    def encode_bug_report(self, text):
        """
        Encodes a natural language bug report into a single normalized embedding.
        """
        tokens = self.model.tokenize([text], mode="<encoder-only>")[0]
        source_ids = torch.tensor([tokens]).to(self.device)

        _, embedding = self.model(source_ids)
        embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
        return [embedding.squeeze(0).tolist()]

    # === Java Method Chunking ===
    def extract_methods_from_java(self, source_code):
        tree = self.parser.parse(bytes(source_code, "utf-8"))
        root_node = tree.root_node
        chunks = []

        def walk(node):
            if node.type == "method_declaration":
                method_text = self.node_text(bytes(source_code, "utf-8"), node)
                tokens = self.model.tokenize([method_text], mode="<encoder-only>")[0]

                if len(tokens) > self.max_tokens:
                    # Sliding window chunking
                    stride = self.max_tokens // 2
                    for i in range(0, len(tokens), stride):
                        sub_tokens = tokens[i:i + self.max_tokens]
                        sub_ids = torch.tensor([sub_tokens]).to(self.device)
                        decoded = self.model.decode(sub_ids[0])
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
        return source_bytes[node.start_byte:node.end_byte].decode('utf-8')

    # === Ranking Logic ===
    def rank_files(self, query_embeddings, db_embeddings):
        """
        Ranks files using top-k average cosine similarity between
        batched query embeddings and file chunk embeddings.
        """
        results = []

        # Convert query embeddings to tensor
        query_tensor = torch.tensor(query_embeddings, device=self.device)
        if query_tensor.ndim == 1:
            query_tensor = query_tensor.unsqueeze(0)
        norm_query = torch.nn.functional.normalize(query_tensor, p=2, dim=1)

        for file_id, file_embeddings in db_embeddings:
            if not file_embeddings:
                results.append((file_id, float('-inf')))
                continue

            # Convert file chunk embeddings to tensor
            file_tensor = torch.tensor(file_embeddings, device=self.device)
            if file_tensor.ndim == 1:
                file_tensor = file_tensor.unsqueeze(0)
            norm_file = torch.nn.functional.normalize(file_tensor, p=2, dim=1)

            # Similarity matrix: [N_query, N_chunks]
            sim_matrix = torch.einsum("ac,bc->ab", norm_query, norm_file)  # [N_query, N_file_chunks]

            # Flatten to one list of scores
            scores = sim_matrix.flatten().tolist()

            # Top-k pooling
            if scores:
                scores.sort(reverse=True)
                top_k_avg = sum(scores[:self.top_k]) / min(self.top_k, len(scores))
            else:
                top_k_avg = float('-inf')

            results.append((file_id, top_k_avg))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

