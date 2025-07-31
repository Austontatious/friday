# FRIDAY Project File Tree
Date: 2024-04-05

## Core Application Files

### Main Application
```
friday/
├── friday.py                 # Main application entry point, FastAPI setup
├── server.py                 # Server configuration and startup
├── friday_routes.py          # Main API route definitions
├── error_handler.py          # Centralized error handling
├── rate_limiter.py           # API rate limiting implementation
├── process_manager.py        # Background process management
├── response_formatter.py     # Response formatting utilities
├── confidence_evaluator.py   # Model confidence evaluation
├── model_cache.py            # Model caching system
├── prompt_templates.py       # Prompt template management
├── template_loader.py        # Template loading utilities
├── persona.py               # AI persona management
├── persona.txt              # Persona configuration
├── context.json             # Context configuration
├── friday.log               # Application logs
├── fix_log.txt              # Fix tracking log
├── cursor.rules             # Cursor IDE rules
├── replit.nix               # Replit configuration
├── .replit                  # Replit project settings
├── CHANGELOG.md             # Version history
├── ARCHITECTURE.md          # System architecture documentation
├── README.md                # Project documentation
├── requirements.txt         # Python dependencies
├── package.json             # Node.js dependencies
├── postcss.config.js        # PostCSS configuration
├── start.sh                 # Application startup script
├── check-files.sh           # File verification script
├── download_models.sh       # Model download script
├── regen-package-json.js    # Package.json regeneration
├── .env                     # Environment configuration
├── .env.example             # Example environment configuration
├── .gitignore               # Git ignore rules
├── .gitattributes           # Git attributes
└── generated-icon.png       # Application icon
```

### Model Management
```
friday/
├── model_loader.py          # High-level model loading
├── model_loader_core.py     # Core model loading implementation
├── model_types.py           # Model type definitions
├── model_monitor.py         # Model monitoring system
├── models_config.py         # Model configuration
├── train_all_models.py      # Model training script
├── download_datasets.py     # Dataset download utility
├── llama.cpp/               # LLaMA C++ implementation
├── llama-cpp-python/        # Python bindings for LLaMA
└── adapters/                # Model adapters
```

### Context and Memory
```
friday/
├── context.py               # Context management
├── memory.py                # Memory management with FAISS
├── friday_memory/           # Memory storage
├── chromadb/                # ChromaDB integration
└── cache/                   # General caching
```

### Frontend
```
friday/frontend/
├── src/                     # Source code
│   ├── components/          # React components
│   ├── pages/              # Page components
│   ├── hooks/              # Custom React hooks
│   ├── utils/              # Utility functions
│   ├── styles/             # CSS styles
│   ├── App.tsx             # Main application component
│   └── index.tsx           # Application entry point
├── public/                  # Static assets
└── package.json            # Frontend dependencies
```

### Testing and Development
```
friday/
├── tests/                   # Test suite
├── friday_test.py          # Main test file
├── scripts/                # Development scripts
├── pipelines/              # CI/CD pipelines
└── file_check/             # File verification
```

### Environment and Configuration
```
friday/
├── envs/                    # Python environments
├── pip-cache/              # Pip package cache
├── tmp/                    # Temporary files
├── logs/                   # Application logs
├── data/                   # Data storage
└── protos/                 # Protocol buffers
```

## File Interactions

### Core Application Flow
1. `start.sh` → `friday.py`
   - Initializes FastAPI application
   - Sets up middleware and routes
   - Configures error handling

2. `friday.py` → `server.py`
   - Server configuration
   - Port and host settings
   - SSL configuration

3. `friday.py` → `friday_routes.py`
   - API route definitions
   - Request handling
   - Response formatting

### Model Management Flow
1. `model_loader.py` → `model_loader_core.py`
   - Model initialization
   - Resource management
   - Error handling

2. `model_loader.py` → `model_types.py`
   - Model type definitions
   - Task routing
   - Model selection

3. `model_monitor.py` → `model_loader.py`
   - Performance monitoring
   - Resource usage tracking
   - Health checks

### Context and Memory Flow
1. `context.py` → `memory.py`
   - Context storage
   - Memory management
   - FAISS integration

2. `memory.py` → `friday_memory/`
   - Persistent storage
   - Context retrieval
   - Index management

### Frontend Flow
1. `frontend/src/index.tsx` → `App.tsx`
   - Application initialization
   - Route setup
   - State management

2. `App.tsx` → API endpoints
   - Request handling
   - Response processing
   - Error management

## Key Dependencies

### Backend Dependencies
- FastAPI: Web framework
- FAISS: Vector similarity search
- Sentence Transformers: Text embeddings
- PyTorch: Deep learning framework
- ChromaDB: Vector database

### Frontend Dependencies
- React: UI framework
- Chakra UI: Component library
- TypeScript: Type safety
- Axios: HTTP client

## Configuration Files

### Environment Configuration
- `.env`: Environment variables
- `.env.example`: Example configuration
- `models_config.py`: Model settings
- `persona.txt`: AI persona settings

### Development Configuration
- `requirements.txt`: Python packages
- `package.json`: Node.js packages
- `postcss.config.js`: CSS processing
- `.gitignore`: Version control
- `.gitattributes`: Git settings

## Documentation
- `README.md`: Project overview
- `ARCHITECTURE.md`: System design
- `CHANGELOG.md`: Version history
- `cursor.rules`: IDE configuration 