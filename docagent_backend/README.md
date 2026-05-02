# Google Docs AI Agent Backend

Simple FastAPI backend for the Google Docs AI Agent extension.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Add Google Credentials
1. Download `credentials.json` from Google Cloud Console
2. Place it in this directory (`docagent_backend/`)

### 3. Start Server
```bash
# Option 1: FastAPI CLI (recommended)
fastapi dev app.py

# Option 2: Uvicorn
uvicorn app:app --reload

# Option 3: Python directly
python app.py
```

Server runs at: `http://localhost:8000`

## Configuration

Edit `.env` file:
```bash
GOOGLE_CREDENTIALS_PATH=credentials.json
SERVER_HOST=localhost
SERVER_PORT=8000
AGENT_MODEL=gemini-pro
DEBUG=true
```

## API Endpoints

- `GET /` - Service info
- `GET /health` - Health check with auth status
- `GET /api/status` - Status for extension
- `POST /api/chat` - Chat with AI agent
- `GET /api/document/{id}/info` - Document info
- `GET /api/approvals` - Pending approvals
- `POST /api/approve/{id}` - Handle approvals

## Files

- `app.py` - Main FastAPI application
- `config.py` - Simple environment config
- `google_auth.py` - Google OAuth handling
- `docs_reader.py` - Google Docs API reader
- `ai_agent.py` - LangChain AI agent
- `.env` - Configuration file

## Testing

1. Start server: `fastapi dev app.py`
2. Visit: `http://localhost:8000`
3. Test API: `http://localhost:8000/api/status`
4. Load extension in Chrome
5. Open Google Docs and try the sidebar!