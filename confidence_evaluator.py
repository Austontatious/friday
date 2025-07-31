from typing import Dict, Any, List
import numpy as np
from transformers import AutoTokenizer, AutoModel
import torch
from sentence_transformers import SentenceTransformer
import logging

class ConfidenceEvaluator:
    def __init__(self):
        """Initialize confidence evaluator with models."""
        try:
            # Load models for different evaluation aspects
            self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')
            self.model = AutoModel.from_pretrained('bert-base-uncased')
            
            # Move model to GPU if available
            if torch.cuda.is_available():
                self.model = self.model.to("cuda")
                
        except Exception as e:
            logging.error(f"Error initializing confidence evaluator: {e}")
            raise

    def evaluate(self, user_input: str, context: Dict[str, Any]) -> float:
        """Evaluate confidence score for user input."""
        try:
            # Calculate different aspects of confidence
            semantic_score = self._evaluate_semantic_similarity(user_input, context)
            clarity_score = self._evaluate_clarity(user_input)
            context_score = self._evaluate_context_relevance(user_input, context)
            
            # Weighted combination of scores
            confidence_score = (
                0.4 * semantic_score +
                0.3 * clarity_score +
                0.3 * context_score
            )
            
            return float(np.clip(confidence_score, 0.0, 1.0))
            
        except Exception as e:
            logging.error(f"Error evaluating confidence: {e}")
            return 0.5  # Default to medium confidence on error

    def _evaluate_semantic_similarity(self, user_input: str, context: Dict[str, Any]) -> float:
        """Evaluate semantic similarity between input and context."""
        try:
            # Get context text
            context_text = " ".join([
                str(v) for v in context.values()
                if isinstance(v, str)
            ])
            
            # Generate embeddings
            input_embedding = self.semantic_model.encode(user_input)
            context_embedding = self.semantic_model.encode(context_text)
            
            # Calculate cosine similarity
            similarity = np.dot(input_embedding, context_embedding) / (
                np.linalg.norm(input_embedding) * np.linalg.norm(context_embedding)
            )
            
            return float(np.clip(similarity, 0.0, 1.0))
            
        except Exception as e:
            logging.error(f"Error in semantic similarity evaluation: {e}")
            return 0.5

    def _evaluate_clarity(self, user_input: str) -> float:
        """Evaluate clarity of user input."""
        try:
            # Tokenize input
            inputs = self.tokenizer(
                user_input,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # Get model outputs
            with torch.no_grad():
                outputs = self.model(**inputs)
                attention = outputs.attentions[-1]  # Get last layer attention
            
            # Calculate attention variance as clarity measure
            attention_variance = torch.var(attention.mean(dim=1)).item()
            clarity_score = 1.0 - min(attention_variance, 1.0)
            
            return float(clarity_score)
            
        except Exception as e:
            logging.error(f"Error in clarity evaluation: {e}")
            return 0.5

    def _evaluate_context_relevance(self, user_input: str, context: Dict[str, Any]) -> float:
        """Evaluate relevance of input to context."""
        try:
            # Extract key terms from context
            context_terms = set()
            for value in context.values():
                if isinstance(value, str):
                    terms = value.lower().split()
                    context_terms.update(terms)
            
            # Extract terms from user input
            input_terms = set(user_input.lower().split())
            
            # Calculate term overlap
            overlap = len(context_terms.intersection(input_terms))
            total_terms = len(context_terms.union(input_terms))
            
            if total_terms == 0:
                return 0.5
            
            relevance_score = overlap / total_terms
            return float(relevance_score)
            
        except Exception as e:
            logging.error(f"Error in context relevance evaluation: {e}")
            return 0.5

    def get_evaluation_details(self, user_input: str, context: Dict[str, Any]) -> Dict[str, float]:
        """Get detailed confidence evaluation scores."""
        return {
            "semantic_similarity": self._evaluate_semantic_similarity(user_input, context),
            "clarity": self._evaluate_clarity(user_input),
            "context_relevance": self._evaluate_context_relevance(user_input, context),
            "overall_confidence": self.evaluate(user_input, context)
        }
