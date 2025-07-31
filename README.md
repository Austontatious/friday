# FRIDAY AI Assistant

FRIDAY is an advanced AI assistant designed to help developers with coding tasks, debugging, and software development. It combines multiple language models to provide intelligent code assistance and natural language interactions.

## Features

- Multi-model support (DeepSeek, Llama)
- Intelligent code completion and generation
- Natural language code explanations
- Debugging assistance
- Context-aware responses
- Configurable model settings
- Robust error handling and logging

## Prerequisites

- Python 3.8 or higher
- Node.js 14 or higher
- Git
- CUDA-capable GPU (recommended for better performance)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/friday.git
cd friday
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install Node.js dependencies:
```bash
cd frontend
npm install
cd ..
```

5. Copy the example environment file and configure it:
```bash
cp .env.example .env
```

Edit the `.env` file with your configuration:
```env
# API Keys
ANTHROPIC_API_KEY=your_api_key_here

# Model Paths
DEEPSEEK_MODEL_PATH=models/deepseek-coder-6.7b-instruct.Q4_K_M.gguf
LLAMA_MODEL_PATH=models/llama-2-7b-chat

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Backend and Frontend Ports
FRIDAY_PORT=8001
REACT_APP_BACKEND_PORT=8002
REACT_APP_BACKEND_URL=http://localhost:8001
```

## Usage

1. Start the application:
```bash
./start.sh
```

This will start both the backend and frontend servers. The application will be available at:
- Frontend: http://localhost:8000
- Backend API: http://localhost:8001

2. Access the web interface and start interacting with FRIDAY.

## Project Structure

```
friday/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   └── services/
│   ├── tests/
│   └── main.py
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
├── models/
├── scripts/
├── .env.example
├── requirements.txt
└── start.sh
```

## Model Configuration

FRIDAY supports multiple language models with different capabilities:

### DeepSeek Model
- Context length: 16384 tokens
- Specialized for code generation and explanation
- Uses GGUF format for efficient inference

### Llama Model
- Context length: 4096 tokens
- General-purpose language model
- Supports various coding tasks

## Development

### Running Tests
```bash
pytest backend/tests/
```

### Code Style
The project uses:
- Black for Python code formatting
- isort for import sorting
- flake8 for linting
- mypy for type checking

Run the formatters:
```bash
black backend/
isort backend/
```

### Adding New Models

1. Add model configuration in `model_config.py`
2. Implement model loading in `model_loader.py`
3. Update `persona.py` to support the new model
4. Add model-specific prompts and handling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- DeepSeek AI for the code-specialized model
- Meta AI for the Llama model
- The open-source community for various tools and libraries 