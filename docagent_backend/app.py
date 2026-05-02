import logging
import uuid
from datetime import datetime
from typing import Optional, Dict

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_agent import DocsAIAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Google Docs AI Copilot",
    description="AI agent for Google Docs operations",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store pending approvals in memory (use Redis/DB for production)
pending_approvals: Dict[str, Dict] = {}

# Store agent instances per session (use proper session management in production)
agent_sessions: Dict[str, DocsAIAgent] = {}


class ChatRequest(BaseModel):
    document_id: str
    user_request: str
    session_id: Optional[str] = None


class ApprovalRequest(BaseModel):
    approved: bool


@app.get("/")
async def root():
    return {
        "message": "Google Docs AI Copilot Backend",
        "version": "0.2.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health():
    return {"status": "healthy",
            "active_essions": len(agent_sessions),
            "pending_approvals": len(pending_approvals)
    }


@app.post("/api/chat")
async def chat_with_agent(
    request: ChatRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Chat with the AI agent about document operations.
    Expects Authorization header with Google OAuth token.
    """
    try:
        # Extract token from Authorization header
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )
        
        access_token = authorization.replace("Bearer ", "")
        
        # Get or create agent session
        session_id = request.session_id or str(uuid.uuid4())
        if session_id not in agent_sessions:
            logger.info(f"Creating new agent session: {session_id}")
            agent_sessions[session_id] = DocsAIAgent()
        
        agent = agent_sessions[session_id]
        
        logger.info(f"Processing request in session {session_id}: {request.user_request[:50]}...")
        response = await agent.process_request(
            user_request=request.user_request,
            document_id=request.document_id,
            access_token=access_token
        )
        
        # If the agent generated a batch request that needs approval
        if response.get('requires_approval') and response.get('batch_request'):
            request_id = str(uuid.uuid4())
            
            pending_approvals[request_id] = {
                'user_request': request.user_request,
                'document_id': request.document_id,
                'batch_request': response['batch_request'],
                'access_token': access_token,
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',
                'session_id': session_id,
                'preview': response['batch_request'].get('preview', 'Pending operation')
            }
            logger.info(f"Request {request_id} requires approval")
            response['request_id'] = request_id

        response['session_id'] = session_id
        response['conversation_length'] = len(agent.messages) // 2

        logger.info(f"Processed request: {request.user_request[:50]}... | Approval required: {response.get('requires_approval')}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing chat request")
        return {
            "success": False,
            "error": str(e),
            "message": "Sorry, I encountered an error processing your request."
        }


@app.get("/api/approvals")
async def get_approvals():
    """Get all pending approvals."""
    pending_list = [
        {
            "request_id": req_id,
            "user_request": data["user_request"],
            "document_id": data["document_id"],
            "preview": data.get("preview", "Operation pending"),
            "timestamp": data["timestamp"],
            "status": data["status"]
        }
        for req_id, data in pending_approvals.items()
        if data["status"] == "pending"
    ]
    pending_list.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "success": True,
        "approvals": pending_list,
        "count": len(pending_list)
    }


@app.post("/api/approve/{request_id}")
async def approve_changes(request_id: str, approval: ApprovalRequest):
    """Handle approval or rejection of pending operations."""
    try:
        if request_id not in pending_approvals:
            raise HTTPException(status_code=404, detail="Request not found")
        
        approval_data = pending_approvals[request_id]
        
        if not approval.approved:
            approval_data["status"] = "rejected"
            approval_data["approval_timestamp"] = datetime.now().isoformat()
            
            logger.info(f"Request {request_id} rejected")
            
            return {
                "success": True,
                "message": "Changes rejected. No modifications were made.",
                "approved": False,
                "request_id": request_id
            }
        
        # Execute the approved batch request
        session_id = approval_data.get('session_id')
        if session_id not in agent_sessions:
            logger.warning(f"Session {session_id} not found for request {request_id}, creating new session")
            agent_sessions[session_id] = DocsAIAgent()
        
        agent = agent_sessions[session_id]
        
        # Execute via agent which will call the MCP execute_batch_request tool
        result = await agent.execute_approved_operation(
            batch_request=approval_data['batch_request'],
            access_token=approval_data['access_token']
        )
        
        approval_data["status"] = "approved" if result.get('success') else "failed"
        approval_data["approval_timestamp"] = datetime.now().isoformat()
        approval_data["execution_result"] = result
        
        if result.get('success'):
            message = "Changes approved and successfully applied to document."
            logger.info(f"Request {request_id} approved and executed successfully")
        else:
            message = f"Changes approved but execution failed: {result.get('error')}"
            logger.error(f"Request {request_id} execution failed: {result.get('error')}")
        
        return {
            "success": result.get('success', False),
            "message": message,
            "approved": True,
            "request_id": request_id,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing approval")
        return {
            "success": False,
            "error": str(e)
        }



@app.get("/api/session/{session_id}/status")
async def get_session_status(session_id: str):
    """Get detailed session status."""
    if session_id not in agent_sessions:
        return {
            "exists": False,
            "session_id": session_id
        }
    
    agent = agent_sessions[session_id]
    
    # Find pending approvals for this session
    session_approvals = [
        {
            "request_id": req_id,
            "user_request": data["user_request"],
            "operation_type": data.get("operation_type", "unknown"),
            "status": data["status"],
            "timestamp": data["timestamp"]
        }
        for req_id, data in pending_approvals.items()
        if data.get("session_id") == session_id and data["status"] == "pending"
    ]
    
    return {
        "exists": True,
        "session_id": session_id,
        "conversation_exchanges": len(agent.message_history) // 2,
        "context_summary": agent.get_context_summary(),
        "pending_approvals": session_approvals,
        "pending_count": len(session_approvals)
    }

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Delete an agent session completely."""
    if session_id in agent_sessions:
        del agent_sessions[session_id]
        logger.info(f"Session {session_id} deleted")
        return {"success": True, "message": "Session deleted"}
    return {"success": False, "message": "Session not found"}


def _generate_preview_text(batch_request: Dict) -> str:
    """Generate a human-readable preview of the batch request."""
    requests = batch_request.get('requests', [])
    
    if not requests:
        return "No operations"
    
    first_request = requests[0]
    
    if 'insertText' in first_request:
        text = first_request['insertText'].get('text', '')
        preview = text[:80] + "..." if len(text) > 80 else text
        return f"Insert text: {preview}"
    
    elif 'deleteContentRange' in first_request:
        range_data = first_request['deleteContentRange'].get('range', {})
        start = range_data.get('startIndex', 0)
        end = range_data.get('endIndex', 0)
        return f"Delete {end - start} characters"
    
    elif 'updateTextStyle' in first_request:
        style = first_request['updateTextStyle'].get('textStyle', {})
        styles = []
        if style.get('bold'):
            styles.append('bold')
        if style.get('italic'):
            styles.append('italic')
        return f"Format text: {', '.join(styles)}"
    
    return f"{len(requests)} operations"


if __name__ == "__main__":
    import uvicorn
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    host = os.getenv("SERVER_HOST", "localhost")
    port = int(os.getenv("SERVER_PORT", "8000"))
    
    print(f"🚀 Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)