import ollama

if __name__ == "__main__":
    embedding = ollama.embed(model='deepseek-r1:latest', input='The sky is blue because of rayleigh scattering')
    print(embedding)