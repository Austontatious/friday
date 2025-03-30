import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import os
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

class MemoryManager:
    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.contexts: List[Dict[str, Any]] = []
        self.memory_file = "friday_memory/context_store.json"
        self._initialize_memory()

    def _initialize_memory(self):
        """Initialize or load existing memory store."""
        os.makedirs("friday_memory", exist_ok=True)
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                self.contexts = json.load(f)
                if self.contexts:
                    # Rebuild FAISS index from stored contexts
                    embeddings = [self.encoder.encode(ctx['text']) for ctx in self.contexts]
                    self.index.add(np.array(embeddings).astype('float32'))

    def store_context(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store new context with FAISS indexing."""
        # Generate embedding
        embedding = self.encoder.encode(text)
        
        # Add to FAISS index
        self.index.add(np.array([embedding]).astype('float32'))
        
        # Store context with metadata
        context_id = f"ctx_{len(self.contexts)}"
        context_entry = {
            'id': context_id,
            'text': text,
            'metadata': metadata or {},
            'timestamp': str(datetime.now())
        }
        self.contexts.append(context_entry)
        
        # Persist to disk
        self._save_memory()
        
        return context_id

    def retrieve_context(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant contexts using FAISS similarity search."""
        try:
            # Check if index is empty
            if self.index.ntotal == 0:
                return []
                
            # Generate query embedding
            query_embedding = self.encoder.encode(query)
            
            # Search in FAISS index
            distances, indices = self.index.search(
                np.array([query_embedding]).astype('float32'), k
            )
            
            # Return relevant contexts
            return [self.contexts[i] for i in indices[0] if i < len(self.contexts)]
        except Exception as e:
            logging.error(f"Error retrieving context: {e}")
            return []

    def update_context(self, context_id: str, new_text: str, new_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update existing context with new information."""
        for ctx in self.contexts:
            if ctx['id'] == context_id:
                # Update embedding in FAISS
                old_embedding = self.encoder.encode(ctx['text'])
                new_embedding = self.encoder.encode(new_text)
                
                # Remove old embedding and add new one
                self.index.remove(np.array([old_embedding]).astype('float32'))
                self.index.add(np.array([new_embedding]).astype('float32'))
                
                # Update context
                ctx['text'] = new_text
                if new_metadata:
                    ctx['metadata'].update(new_metadata)
                
                self._save_memory()
                return True
        return False

    def delete_context(self, context_id: str) -> bool:
        """Delete context from memory store."""
        for i, ctx in enumerate(self.contexts):
            if ctx['id'] == context_id:
                # Remove embedding from FAISS
                embedding = self.encoder.encode(ctx['text'])
                self.index.remove(np.array([embedding]).astype('float32'))
                
                # Remove context
                self.contexts.pop(i)
                self._save_memory()
                return True
        return False

    def _save_memory(self):
        """Persist memory store to disk."""
        with open(self.memory_file, 'w') as f:
            json.dump(self.contexts, f, indent=2)

    def get_context_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent context history."""
        return sorted(
            self.contexts,
            key=lambda x: x['timestamp'],
            reverse=True
        )[:limit]

    def clear_memory(self):
        """Clear all stored contexts and reset FAISS index."""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.contexts = []
        self._save_memory()

