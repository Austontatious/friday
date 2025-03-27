from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

chroma_client = PersistentClient(path="./friday_memory")
collection = chroma_client.get_or_create_collection("friday-memory")

model = SentenceTransformer("all-MiniLM-L6-v2")

# Init collection
collection = chroma_client.get_or_create_collection(name="friday-memory")

def save_to_memory(prompt: str, response: str):
    embedding = model.encode(prompt).tolist()
    collection.add(
        documents=[response],
        metadatas=[{"prompt": prompt}],
        embeddings=[embedding],
        ids=[prompt[:8] + str(len(prompt))]
    )

def recall_from_memory(prompt: str, top_k=3):
    embedding = model.encode(prompt).tolist()
    results = collection.query(query_embeddings=[embedding], n_results=top_k)
    return results["documents"][0] if results["documents"] else []

def list_memory(limit=10):
    results = collection.get()
    items = zip(results["ids"], results["metadatas"], results["documents"])
    return list(items)[-limit:]

def clear_memory():
    collection.delete(ids=collection.get()["ids"])
