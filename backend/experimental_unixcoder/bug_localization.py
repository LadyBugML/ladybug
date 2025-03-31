from transformers import AutoTokenizer, AutoModel
import torch
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava


class BugLocalization:
    def __init__(self, max_tokens=512, top_k=1):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5p-110m-embedding", trust_remote_code=True)
        self.model = AutoModel.from_pretrained("Salesforce/codet5p-110m-embedding", trust_remote_code=True).to(self.device)
        self.model.eval()

        self.max_tokens = max_tokens
        self.top_k = top_k

        # Tree-sitter for Java
        JAVA_LANGUAGE = Language(tsjava.language())
        self.parser = Parser(JAVA_LANGUAGE)

    def old_chunking_encode_code(self, text, verbose=False):
        """
        Encodes long text by splitting it into chunks of roughly 500 characters
        (before tokenization). Each chunk is tokenized and encoded individually.
        Returns a list of embeddings (as lists), one for each chunk.
        """
        chunk_size = 500  # Split by 500 characters as an example
        embeddings = []

        chunks = []
        # Split text into roughly 500-character chunks
        for i in range(0, len(text), chunk_size):
            text_chunk = text[i:i + chunk_size]
            chunks.append(text_chunk)
            if verbose:
                print(f"Processing text chunk {i // chunk_size + 1}")  # Debug print

            inputs = self.tokenizer(text_chunk, return_tensors="pt", truncation=True, padding=True, max_length=self.max_tokens).to(self.device)
            with torch.no_grad():
                output = self.model(**inputs)[0]  # shape: [1, 256]
                norm_embedding = torch.nn.functional.normalize(output, p=2, dim=-1)
                embeddings.append(norm_embedding.squeeze(0).tolist())
        # print(embeddings)
        return embeddings, chunks
    
    def encode_code(self, code_str):
        chunks = self.extract_methods_from_java(code_str)
        embeddings = []

        for chunk in chunks:
            inputs = self.tokenizer(chunk, return_tensors="pt", truncation=True, padding=True, max_length=self.max_tokens).to(self.device)
            with torch.no_grad():
                output = self.model(**inputs)[0]  # shape: [1, 256]
                norm_embedding = torch.nn.functional.normalize(output, p=2, dim=-1)
                embeddings.append(norm_embedding.squeeze(0).tolist())

        return embeddings, chunks

    def encode_bug_report(self, text):
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True).to(self.device)
        with torch.no_grad():
            output = self.model(**inputs)[0]
            norm_embedding = torch.nn.functional.normalize(output, p=2, dim=-1)
            return [norm_embedding.squeeze(0).tolist()]


    def extract_methods_from_java(self, source_code):
        tree = self.parser.parse(bytes(source_code, "utf-8"))
        root_node = tree.root_node
        method_texts = []

        def walk(node):
            if node.type == "method_declaration":
                method_text = self.node_text(bytes(source_code, "utf-8"), node)
                method_texts.append(method_text)
            for child in node.children:
                walk(child)

        walk(root_node)

        # === Smart packing implementation ===
        def smart_pack_methods(methods, tokenizer, max_tokens=512):
            packed_chunks = []
            current_chunk = []
            current_len = 0

            for method in methods:
                method_tokens = tokenizer(method, truncation=False, add_special_tokens=False)["input_ids"]
                method_len = len(method_tokens)

                # Optional: skip methods that are too long
                if method_len > max_tokens:
                    continue  # or: handle separately if you want

                if current_len + method_len > max_tokens:
                    packed_chunks.append("\n\n".join(current_chunk))
                    current_chunk = [method]
                    current_len = method_len
                else:
                    current_chunk.append(method)
                    current_len += method_len

            if current_chunk:
                packed_chunks.append("\n\n".join(current_chunk))

            return packed_chunks

        return smart_pack_methods(method_texts, self.tokenizer, max_tokens=self.max_tokens)


    def node_text(self, source_bytes, node):
        return source_bytes[node.start_byte:node.end_byte].decode('utf-8')

    def rank_files(self, query_embeddings, db_embeddings):
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
