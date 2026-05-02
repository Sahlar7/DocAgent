# DocAgent

DocAgent is an AI-powered assistant for Google Docs that helps with research, drafting, editing, and citation support. It combines a FastAPI backend, a Chrome extension interface, and Google/AI integrations to let you interact with documents directly from Google Docs.

## Project Structure

- `docagent_backend/` - FastAPI backend and Google Docs/MCP agent logic
- `docagent_extension/` - Chrome extension UI and browser integration

## Features

- AI chat assistant for Google Docs
- Document reading, modification planning, and approval workflow
- Google Docs API MCP Server
- Chrome extension sidebar integration
- Optional web and academic search for citation-aware research

## Getting Started

### 1. Install Python Dependencies

```bash
pip install -r docagent_backend/requirements.txt
```

### 2. Configure Google Credentials

For the backend, set up Google Cloud credentials:

1. Create a Google Cloud project with Google Docs API enabled.
2. Create a service account and download the JSON credentials file.
3. Save the file in the repo root or backend folder.
4. Set environment variables:

```bash
set GOOGLE_APPLICATION_CREDENTIALS=path\to\credentials.json
set GOOGLE_API_KEY=your_google_api_key
set SERPAPI_API_KEY=your_serpapi_api_key
set MCP_SERVER_URL=http://127.0.0.1:8001
```

> On PowerShell use `setx` to persist variables, or create a `.env` file and load it before running.

## Running the Backend

From `docagent_backend/`, start the FastAPI server:

```bash
cd docagent_backend
uvicorn app:app --reload
```

Alternative:

```bash
python app.py
```

The backend will run at `http://localhost:8000` by default.

## MCP Server

The MCP server exposes Google Docs operations as callable tools for the backend agent. It is responsible for:

- reading Google Docs content via OAuth tokens
- generating Google Docs batch requests for edits
- validating and previewing modification requests
- executing updates only after approval

The backend uses `MCP_SERVER_URL` to connect to this server at `http://localhost:8001/mcp` by default.

### Start the MCP Server

```bash
cd docagent_backend
python mcp_google_docs.py
```

By default the MCP server listens on:

- `MCP_HOST=127.0.0.1`
- `MCP_PORT=8001`

You can override these values in `docagent_backend/.env` or your shell.

### How the MCP server fits into the system

1. The Chrome extension sends chat requests to the FastAPI backend at `http://localhost:8000`.
2. The backend agent uses `MCP_SERVER_URL` to call the local MCP server.
3. The MCP server performs Google Docs operations and returns structured results.
4. The backend uses the results to generate replies or modification plans.

### MCP configuration file

The MCP entrypoint is defined in `docagent_backend/mcp_config.json`:

```json
{
  "mcpServers": {
    "google-docs": {
      "command": "python",
      "args": ["mcp_google_docs.py"],
      "cwd": ".",
      "env": {},
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## Using the Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Select the `docagent_extension/` folder
5. Open a Google Docs document and use the sidebar/chat interface


## Configuration

- `docagent_backend/credentials.json` - Google Cloud service account credentials
- `.env` - environment variables for API keys and configuration
- `MCP_SERVER_URL` - MCP server URL for backend agent communication

## Useful Endpoints (Backend)

- `GET /` - Service information
- `GET /health` - Health check
- `POST /api/chat` - Send a chat request to the AI agent
- `GET /api/document/{id}/info` - Retrieve document info
- `GET /api/approvals` - List pending approval requests
- `POST /api/approve/{id}` - Approve or deny modifications

## Notes

- This repository is intended for development and experimentation. Feel free to fork it and work more on the extension
- Since Google has released their own integrated Gemini features with G-Suite, development by the original author has ended
- From experimentation, the agent really is only able to do basic writing jobs well. Formatting and other edits sometimes take some more prompting.