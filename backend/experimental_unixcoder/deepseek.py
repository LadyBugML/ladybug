import ollama
import torch

if __name__ == "__main__":
    embedding = ollama.embed(model='deepseek-coder-v2:latest', input='The sky is blue because of rayleigh scattering')
    embedding_vector = embedding["embeddings"]
    embedding_vector =  torch.tensor(embedding_vector, dtype=torch.float32)
    # Normalize embedding
   
    norm_nl_embedding = torch.nn.functional.normalize(embedding_vector, p=2, dim=1)


    
    # normalized_embedding = embedding_vector / np.linalg.norm(embedding_vector)

    print(norm_nl_embedding)