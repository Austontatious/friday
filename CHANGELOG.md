# Changelog

## Future Optimizations
- Implement batch processing for multiple requests
- Add model quantization options
- Optimize memory usage and GPU utilization
- Add model-specific inference parameters
- Implement dynamic context length based on input size
- Add model warmup and preloading
- Implement request queuing and prioritization

## Current Issues (To Fix)
1. Model Loading
   - Special token configuration issues (all special tokens should be marked as EOG)
   - Context length limitation (fixed to use full 16384 context length)
   - Tokenizer configuration validation

2. Frontend
   - Compilation termination (fixed with proper directory handling)
   - Port management (working correctly)
   - Development server stability

3. Backend
   - File watching and reload issues (fixed with proper directory handling)
   - Process management
   - Error handling and recovery

## Recent Changes
- Removed Claude and ChatGPT O1 references from ModelType to fix circular imports (will be revisited later)
- Fixed backend directory issue in start.sh
- Updated model configuration to use full context length (16384)
- Added all special tokens as EOG tokens to fix token configuration warnings
- Improved process management and file watching 