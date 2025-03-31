from tree_sitter import Language, Parser
import tree_sitter_java as tsjava
import os
import tempfile

# # Compile Java grammar once
# def build_java_language():
#     LANGUAGE_PATH = os.path.join(tempfile.gettempdir(), 'java.so')
#     if not os.path.exists(LANGUAGE_PATH):
#         Language.build_library(
#             # Path to the .so file to generate
#             LANGUAGE_PATH,
#             # List of language grammar repos
#             ['https://github.com/tree-sitter/tree-sitter-java']
#         )
#     return Language(LANGUAGE_PATH, 'java')

JAVA_LANGUAGE = Language(tsjava.language())

def get_parser():
    parser = Parser(JAVA_LANGUAGE)
    return parser

def node_text(source_code, node):
    """Extract raw text from a Tree-sitter node."""
    start, end = node.start_byte, node.end_byte
    return source_code[start:end].decode('utf-8')

def extract_methods_from_java(source_code, max_tokens=512):
    parser = get_parser()
    tree = parser.parse(bytes(source_code, "utf8"))
    root_node = tree.root_node

    chunks = []

    def walk(node):
        # We’re only interested in method_declaration nodes
        if node.type == 'method_declaration':
            text = node_text(bytes(source_code, 'utf-8'), node)
            token_count = len(text.split())

            # If too long, split into subchunks
            if token_count > max_tokens:
                tokens = text.split()
                start = 0
                while start < len(tokens):
                    subchunk = " ".join(tokens[start:start+max_tokens])
                    chunks.append(subchunk)
                    start += max_tokens // 2  # Overlap 50%
            else:
                chunks.append(text)

        for child in node.children:
            walk(child)

    walk(root_node)
    return chunks

if __name__ == "__main__":
    with open("/home/darren/Documents/ladybug/dataset/bug-2/code/bug-2/shared/src/main/java/io/github/zwieback/familyfinance/widget/filter/DecimalNumberInputFilter.java", "r", encoding="utf-8") as f:
        source = f.read()

    method_chunks = extract_methods_from_java(source)

    print(f"Extracted {len(method_chunks)} method-level chunks:")
    for i, chunk in enumerate(method_chunks, 1):
        print(f"\n--- Chunk {i} ---\n{chunk}\n")  # Print first 300 chars
