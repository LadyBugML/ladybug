from transformers import AutoTokenizer, AutoModel
import torch
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava


class BugLocalization:
    _instance = None  # Class variable to hold the single instance

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BugLocalization, cls).__new__(cls)
        return cls._instance

    def __init__(self, model="microsoft/unixcoder-base", max_tokens=512, top_k=1):
        if hasattr(self, 'initialized'):
            return
        self.initialized = True
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.is_unixcoder = model.lower() == "microsoft/unixcoder-base"

        if self.is_unixcoder:
            print(f"{'\033[91m'}Loading UnixCoder model...{'\033[0m'}")
            self.tokenizer = AutoTokenizer.from_pretrained(model)
            self.model = AutoModel.from_pretrained(model).to(self.device)
        else:
            print(f"{'\033[92m'}Loading Custom model...{'\033[0m'}")
            self.tokenizer = AutoTokenizer.from_pretrained(model, trust_remote_code=True)
            self.model = AutoModel.from_pretrained(model, trust_remote_code=True).to(self.device)

        self.model.eval()
        self.max_tokens = max_tokens
        self.top_k = top_k

        JAVA_LANGUAGE = Language(tsjava.language())
        self.parser = Parser(JAVA_LANGUAGE)

    def encode_code(self, code_str):
        chunks = self.extract_methods_from_java(code_str)
        embeddings = []

        for chunk in chunks:
            inputs = self.tokenizer(chunk, return_tensors="pt", truncation=True, padding=True,
                                    max_length=self.max_tokens).to(self.device)
            with torch.no_grad():
                if self.is_unixcoder:
                    outputs = self.model(**inputs)
                    cls_embedding = outputs[1]
                    norm_embedding = torch.nn.functional.normalize(cls_embedding, p=2, dim=-1)
                else:
                    output = self.model(**inputs)[0]
                    norm_embedding = torch.nn.functional.normalize(output, p=2, dim=-1)

                embeddings.append(norm_embedding.squeeze(0).tolist())

        return embeddings

    def encode_bug_report(self, text):
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True,
                                max_length=self.max_tokens).to(self.device)
        with torch.no_grad():
            if self.is_unixcoder:
                outputs = self.model(**inputs)
                cls_embedding = outputs[1]
                norm_embedding = torch.nn.functional.normalize(cls_embedding, p=2, dim=-1)
            else:
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
                tokens = self.tokenizer(method_text, truncation=True, add_special_tokens=False,max_length=self.max_tokens)["input_ids"]
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

    def rank_files(self, query_embeddings, db_embeddings):
        """
        Ranks files based on similarity between query embeddings and database embeddings.

        Args:
            query_embeddings (list): Embeddings for the query (e.g., bug report).
            db_embeddings (list): A list of tuples containing file IDs and their embeddings.

        Returns:
            list: A list of tuples (file_id, score) sorted by similarity score in descending order.
        """
        
        results = []

        query_tensor = torch.tensor(query_embeddings, device=self.device)
        if query_tensor.ndim == 1:
            query_tensor = query_tensor.unsqueeze(0)
        norm_query = torch.nn.functional.normalize(query_tensor, p=2, dim=1)

        for file_id, file_embeddings in db_embeddings:
            if not file_embeddings:
                results.append((file_id, float('-inf')))
                continue

            file_tensor = torch.tensor(file_embeddings, device=self.device)
            if file_tensor.ndim == 1:
                file_tensor = file_tensor.unsqueeze(0)
            norm_file = torch.nn.functional.normalize(file_tensor, p=2, dim=1)

            sim_matrix = torch.einsum("ac,bc->ab", norm_query, norm_file)
            scores = sim_matrix.flatten().tolist()

            if scores:
                scores.sort(reverse=True)
                top_k_avg = sum(scores[:self.top_k]) / min(self.top_k, len(scores))
            else:
                top_k_avg = float('-inf')

            results.append((file_id, top_k_avg))

        results.sort(key=lambda x: x[1], reverse=True)
        return results
