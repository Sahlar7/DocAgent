import logging
import os
import json
from typing import Dict, Any, List, Tuple
from urllib import response

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an intelligent AI assistant with direct access to Google Docs. You can read documents, understand their content, and make precise modifications when requested.

Your personality:
- Conversational and helpful, not robotic or overly formal
- Proactive in understanding user intent
- Clear about what you're doing without being verbose
- Admit when you're unsure and ask clarifying questions

How you work:
- When asked about document content, read it and provide thoughtful analysis
- When asked to modify a document, explain what you'll do in natural language
- You generate modification plans that require user approval before execution
- Always confirm successful operations

Available tools:
- read_document: Read and analyze document content and structure
- generate_batch_request: Create a modification plan (insert, delete, replace, format text)
- execute_batch_request: Execute an approved modification plan

Important: Always pass the access_token parameter to every tool call.

When modifying documents:
1. Read the document first to understand its current state
2. Create a clear modification plan using generate_batch_request
3. Explain in natural language what will change
4. Wait for approval before execution

Be natural, be helpful, and focus on understanding what the user actually wants rather than just following rigid procedures."""


class DocsAIAgent:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.mcp_url = os.getenv("MCP_SERVER_URL")
        if not self.mcp_url:
            raise ValueError("MCP_SERVER_URL environment variable not set")
        
        self.google_api_key = os.getenv("GEMINI_API_KEY")
        if not self.google_api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        # Use higher temperature for more natural responses
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.8,  # Increased for more natural conversation
            google_api_key=self.google_api_key
        )
        
        # Conversation history - keep more context
        self.messages: List[Tuple[str, str]] = [("system", SYSTEM_PROMPT)]
        self.current_access_token = None
        self.pending_batch_request = None
        self.document_context = {}
        
    async def _get_mcp_client(self):
        """Create MCP client."""
        return MultiServerMCPClient({
            "google_docs_mcp_server": {
                "transport": "streamable_http",
                "url": self.mcp_url
            }
        })
    
    async def process_request(
        self,
        user_request: str,
        document_id: str,
        access_token: str
    ) -> Dict[str, Any]:
        """Process a user request with improved conversation handling."""
        try:
            self.current_access_token = access_token
            
            # Get MCP client and tools
            client = await self._get_mcp_client()
            tools = await client.get_tools()
            
            # Create agent
            agent = create_agent(tools=tools, model=self.llm)
            
            # Build a more conversational context prompt
            context_prompt = f"""Document ID: {document_id}
Access Token: {access_token}

Remember to pass access_token to all tool calls. Process this naturally and conversationally."""
            
            # Add context and user message
            self.messages.append(("system", context_prompt))
            self.messages.append(("human", user_request))
            
            # Invoke agent
            response = await agent.ainvoke({"messages": self.messages})
            
            # Get agent's response
            raw_content = response["messages"][-1].content

            if isinstance(raw_content, list):
                agent_message = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in raw_content
                    if not isinstance(block, dict) or block.get("type") == "text"
                )
            elif isinstance(raw_content, str):
                agent_message = raw_content
            else:
                agent_message = str(raw_content)            
            # Check if agent called generate_batch_request
            batch_request = self._extract_batch_request_from_response(response)
            requires_approval = batch_request is not None
            
            # Store batch request if generated
            if batch_request:
                self.pending_batch_request = batch_request
            
            # Add assistant response to history (without system context)
            self.messages.append(("assistant", agent_message))
            
            # Trim conversation history if too long (keep system + last 40 messages)
            if len(self.messages) > 42:  # system + 40 messages + current
                self.messages = [self.messages[0]] + self.messages[-40:]
            
            return {
                "success": True,
                "message": agent_message,
                "requires_approval": requires_approval,
                "batch_request": batch_request,
                "has_operation": batch_request is not None
            }
            
        except Exception as e:
            logger.exception("Error processing request")
            
            # Provide a natural error message
            error_message = self._generate_error_message(str(e), user_request)
            
            return {
                "success": False,
                "message": error_message,
                "requires_approval": False,
                "error": str(e)
            }
    
    def _extract_batch_request_from_response(self, response: dict) -> Dict[str, Any]:
        """Extract batch request from agent response if generate_batch_request was called."""
        try:
            # Look through the messages for tool results
            messages = response.get("messages", [])
            
            for msg in reversed(messages):
                # Check if this is a tool result message
                if hasattr(msg, 'content'):
                    try:
                        content = msg.content
                        if isinstance(content, str) and 'batch_request' in content:
                            parsed = json.loads(content)
                            if parsed.get('success') and 'batch_request' in parsed:
                                return parsed['batch_request']
                    except (json.JSONDecodeError, AttributeError):
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting batch request: {e}")
            return None
    
    def _generate_error_message(self, error: str, user_request: str) -> str:
        """Generate a natural error message based on the error type."""
        error_lower = error.lower()
        
        if "auth" in error_lower or "permission" in error_lower:
            return "I'm having trouble accessing the document. Could you check that I have the right permissions?"
        
        if "not found" in error_lower or "404" in error:
            return "I couldn't find that document. Could you verify the document ID?"
        
        if "rate limit" in error_lower:
            return "I'm being rate limited by Google's API. Let's wait a moment and try again."
        
        if "timeout" in error_lower:
            return "The request timed out. The document might be very large or the connection is slow. Want to try again?"
        
        # Generic error with helpful context
        return f"I ran into an issue while processing your request. The error was: {error}. Would you like to try rephrasing your request or try something else?"
    
    async def execute_approved_operation(
        self,
        batch_request: Dict[str, Any],
        access_token: str
    ) -> Dict[str, Any]:
        """Execute an approved batch request."""
        try:
            client = await self._get_mcp_client()
            tools = await client.get_tools()
            
            execute_tool = next(
                (t for t in tools if t.name == "execute_batch_request"),
                None
            )
            
            if not execute_tool:
                return {
                    "success": False,
                    "error": "execute_batch_request tool not found"
                }
            
            # Execute the batch request
            result = await execute_tool.ainvoke({
                "batch_request": json.dumps(batch_request),
                "access_token": access_token
            })
            
            # Parse result
            if isinstance(result, str):
                result = json.loads(result)
            
            # Add success note to conversation
            if result.get('success'):
                self.messages.append(
                    ("system", "Document modification completed successfully")
                )
            
            return result
            
        except Exception as e:
            logger.exception("Error executing approved operation")
            return {
                "success": False,
                "error": str(e)
            }
    
    def clear_history(self):
        """Clear conversation history but keep system prompt."""
        self.messages = [self.messages[0]]  # Keep only the system prompt
        self.pending_batch_request = None
        self.document_context = {}
        logger.info("Conversation history cleared")
    
    def get_context_summary(self) -> str:
        """Get a summary of the current conversation context."""
        # Subtract 1 for system prompt, divide by 2 for exchanges
        exchange_count = max(0, (len(self.messages) - 1) // 2)
        if exchange_count == 0:
            return "No conversation history"
        return f"Conversation has {exchange_count} exchanges"