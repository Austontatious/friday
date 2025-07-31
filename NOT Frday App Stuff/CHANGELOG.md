# Changelog

## Future Optimizations
- Implement batch processing for multiple requests
- Add model quantization options
- Optimize memory usage and GPU utilization
- Add model-specific inference parameters
- Implement dynamic context length based on input size
- Add model warmup and preloading
- Implement request queuing and prioritization
- Reduce KV cache size by lowering context window from 4096 to 2048 tokens
- Decrease batch size from 256 to 128 to reduce memory footprint
- Implement proper model unloading between requests to free memory
- Add memory monitoring and adaptive scaling based on system resources
- Investigate model sharing and lazy loading techniques for improved memory efficiency

## Current Issues (To Fix)
1. Model Loading
   - Special token configuration issues (all special tokens should be marked as EOG)
   - Context length limitation (fixed to use full 16384 context length)
   - Tokenizer configuration validation
   - Memory exhaustion when loading the DeepSeek model (OOM killer terminates process)
   - Excessive KV cache allocation (2048 MiB) causing high memory usage

2. Frontend
   - Compilation termination (fixed with proper directory handling)
   - Port management (working correctly)
   - Development server stability

3. Backend
   - File watching and reload issues (fixed with proper directory handling)
   - Process management
   - Error handling and recovery
   - Memory management for large language models
   - Need for efficient resource allocation to prevent OOM kills

## Recent Changes
- Added error handling for model monitoring and reporting to prevent crashes
- Fixed missing logging import in model_cache.py
- Modified model selection to only use DEEPSEEK model and avoid any fallback attempts
- Fixed ConfidenceEvaluator class to handle different context types (dict, list, None)
- Fixed circular imports in friday.py and task_manager.py
- Removed Claude and ChatGPT O1 references from ModelType to fix circular imports (will be revisited later)
- Fixed backend directory issue in start.sh
- Updated model configuration to use full context length (16384)
- Added all special tokens as EOG tokens to fix token configuration warnings
- Improved process management and file watching 
- Created a mock server as a temporary solution while addressing memory issues

## Action Items (2025-03-30)
- Implement memory optimization strategies for the DeepSeek model:
  - Reduce context window size from 4096 to 2048
  - Decrease batch size from 256 to 128
  - Add proper model resource cleanup
  - Implement memory monitoring
  - Investigate alternatives to the full 6.7B model if memory constraints persist 