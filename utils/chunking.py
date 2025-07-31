import os
from typing import List, Dict

import tiktoken  # pip install tiktoken

DEFAULT_CHUNK_TOKENS = 200
DEFAULT_OVERLAP_TOKENS = 40
ENCODING = "cl100k_base"  # For OpenAI/gpt-4. Use "gpt2" for LLaMA-style

tokenizer = tiktoken.get_encoding(ENCODING)

def chunk_code(code: str, filepath: str, chunk_size: int = DEFAULT_CHUNK_TOKENS, overlap: int = DEFAULT_OVERLAP_TOKENS) -> List[Dict]:
    tokens = tokenizer.encode(code)
    total_tokens = len(tokens)
    chunks = []

    for start in range(0, total_tokens, chunk_size - overlap):
        end = min(start + chunk_size, total_tokens)
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append({
            "text": chunk_text,
            "start_token": start,
            "end_token": end,
            "filepath": filepath
        })

    return chunks

