import unittest
import sys
import os
import shutil
from unittest.mock import patch, MagicMock
import random
import string
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory import MemoryManager
from model_types import ModelType

class TestMemoryManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary test directory
        self.test_dir = "friday_memory_test"
        os.makedirs(self.test_dir, exist_ok=True)
        # Patch path for test data
        self.memory_path_patcher = patch.object(MemoryManager, 'memory_file', 
                                    f"{self.test_dir}/context_store.json")
        self.model_context_path_patcher = patch.object(MemoryManager, 'model_context_file', 
                                          f"{self.test_dir}/model_context.json")
        # Set up the pathchers
        self.memory_path_patcher.start()
        self.model_context_path_patcher.start()
        
        # Initialize a fresh memory manager
        self.memory = MemoryManager()
        
    def tearDown(self):
        # Stop the patchers
        self.memory_path_patcher.stop()
        self.model_context_path_patcher.stop()
        # Remove test directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _random_text(self, length=100):
        """Generate random text for testing."""
        return ''.join(random.choice(string.ascii_letters + ' ') for _ in range(length))
    
    def test_store_context(self):
        """Test storing context in both vector stores."""
        # Store a test context
        text = "This is a test context for vector stores"
        metadata = {"test_key": "test_value"}
        
        context_id = self.memory.store_context(text, metadata)
        
        # Check if context was stored in FAISS
        self.assertEqual(len(self.memory.contexts), 1)
        self.assertEqual(self.memory.contexts[0]['text'], text)
        self.assertEqual(self.memory.contexts[0]['metadata'], metadata)
        
        # Check if FAISS index has been updated
        self.assertEqual(self.memory.faiss_index.ntotal, 1)
        
        # Check if context was stored in ChromaDB
        # We should be able to retrieve it from ChromaDB
        if self.memory.chroma_collection:
            self.assertTrue(self.memory._is_in_chromadb(context_id))
    
    def test_retrieve_context(self):
        """Test retrieving context from both vector stores."""
        # Store multiple test contexts
        contexts = [
            "Python is a programming language.",
            "The cat sat on the mat.",
            "Machine learning is a subfield of artificial intelligence.",
            "Neural networks are used for deep learning tasks.",
            "Vector stores are used for similarity search."
        ]
        
        context_ids = []
        for i, text in enumerate(contexts):
            context_id = self.memory.store_context(text, {"index": i})
            context_ids.append(context_id)
        
        # Test retrieval with a relevant query
        query = "What is machine learning?"
        results = self.memory.retrieve_context(query, k=2)
        
        # We should get results from both stores
        self.assertTrue(len(results) > 0)
        
        # The top result should be about machine learning
        self.assertTrue("machine learning" in results[0]['text'].lower())
        
        # Check that the results have a score field
        self.assertTrue('score' in results[0])
        
        # Check that the results have a source field (faiss, chromadb, or both)
        self.assertTrue('source' in results[0])
    
    def test_update_context(self):
        """Test updating context in both vector stores."""
        # Store a test context
        original_text = "Original test context"
        context_id = self.memory.store_context(original_text)
        
        # Update the context
        updated_text = "Updated test context"
        result = self.memory.update_context(context_id, updated_text)
        
        # Check if update was successful
        self.assertTrue(result)
        
        # Check if context was updated in memory
        updated_context = next((ctx for ctx in self.memory.contexts if ctx['id'] == context_id), None)
        self.assertIsNotNone(updated_context)
        self.assertEqual(updated_context['text'], updated_text)
        
        # Check if update is reflected in retrieval
        results = self.memory.retrieve_context("Updated context")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]['text'], updated_text)
    
    def test_delete_context(self):
        """Test deleting context from both vector stores."""
        # Store a test context
        text = "Context to be deleted"
        context_id = self.memory.store_context(text)
        
        # Verify it exists
        self.assertEqual(len(self.memory.contexts), 1)
        if self.memory.chroma_collection:
            self.assertTrue(self.memory._is_in_chromadb(context_id))
        
        # Delete the context
        result = self.memory.delete_context(context_id)
        
        # Check if deletion was successful
        self.assertTrue(result)
        
        # Check if context was removed from memory
        self.assertEqual(len(self.memory.contexts), 0)
        
        # Check if context was removed from ChromaDB
        if self.memory.chroma_collection:
            self.assertFalse(self.memory._is_in_chromadb(context_id))
    
    def test_clear_memory(self):
        """Test clearing all memory stores."""
        # Store multiple test contexts
        for i in range(5):
            self.memory.store_context(f"Test context {i}")
        
        # Verify contexts exist
        self.assertEqual(len(self.memory.contexts), 5)
        self.assertEqual(self.memory.faiss_index.ntotal, 5)
        
        # Clear memory
        result = self.memory.clear_memory()
        
        # Check if clearing was successful
        self.assertTrue(result)
        
        # Check if all contexts were removed
        self.assertEqual(len(self.memory.contexts), 0)
        self.assertEqual(self.memory.faiss_index.ntotal, 0)
        
        # Check if ChromaDB was reset
        if self.memory.chroma_collection:
            self.assertEqual(self.memory.chroma_collection.count(), 0)
    
    def test_merge_results(self):
        """Test merging results from FAISS and ChromaDB."""
        # Create sample results
        faiss_results = [
            {'id': 'ctx_1', 'text': 'Text 1', 'score': 0.8, 'source': 'faiss'},
            {'id': 'ctx_2', 'text': 'Text 2', 'score': 0.7, 'source': 'faiss'}
        ]
        
        chroma_results = [
            {'id': 'ctx_1', 'text': 'Text 1', 'score': 0.9, 'source': 'chromadb'},  # Higher score
            {'id': 'ctx_3', 'text': 'Text 3', 'score': 0.6, 'source': 'chromadb'}   # New entry
        ]
        
        # Merge results
        merged = self.memory._merge_results(faiss_results, chroma_results)
        
        # Check merged results
        self.assertEqual(len(merged), 3)  # Should have 3 unique entries
        
        # The duplicate should take the higher score
        ctx1 = next(item for item in merged if item['id'] == 'ctx_1')
        self.assertEqual(ctx1['score'], 0.9)  # Should be ChromaDB's score (higher)
        self.assertEqual(ctx1['source'], 'both')  # Should be marked as from both sources
        
        # The unique entries should be preserved
        self.assertTrue(any(item['id'] == 'ctx_2' for item in merged))
        self.assertTrue(any(item['id'] == 'ctx_3' for item in merged))

if __name__ == '__main__':
    unittest.main() 