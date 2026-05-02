import json
import logging
import os
from typing import Dict, Any

from fastmcp import FastMCP
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("google-docs-mcp")

mcp = FastMCP("Google Docs MCP")


def get_service_from_token(access_token: str):
    """Create Google Docs service from access token."""
    try:
        creds = Credentials(token=access_token)
        return build('docs', 'v1', credentials=creds)
    except Exception as e:
        logger.error(f"Failed to create service: {e}")
        raise


@mcp.tool()
def read_document(document_id: str, access_token: str) -> str:
    """Read the full content of a Google Doc including structure.
    
    Args:
        document_id: The Google Docs document ID
        access_token: OAuth access token for Google Docs API
        
    Returns:
        JSON string with document title, content, structure, and metadata
    """
    try:
        service = get_service_from_token(access_token)
        document = service.documents().get(documentId=document_id).execute()
        
        title = document.get('title', 'Untitled Document')
        body = document.get('body', {})
        content = extract_text_from_body(body)
        
        # Get structural information for the agent to understand positioning
        structure_info = extract_structure_info(body)
        
        result = {
            "success": True,
            "title": title,
            "content": content,
            "document_id": document_id,
            "word_count": len(content.split()),
            "structure": structure_info,
            "revision_id": document.get('revisionId')
        }
        
        return json.dumps(result, indent=2)
        
    except HttpError as e:
        logger.error(f"HTTP error reading document: {e}")
        error_msg = {
            "success": False,
            "error": f"HTTP {e.resp.status}",
            "message": str(e)
        }
        return json.dumps(error_msg)
    except Exception as e:
        logger.exception("Error reading document")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def generate_batch_request(
    operation: str,
    document_id: str,
    parameters: str,
    access_token: str
) -> str:
    """Generate a Google Docs API batch request JSON for document modifications.
    
    This tool helps the agent create the proper API request format without executing it.
    The request will be stored and executed only after user approval.
    
    Args:
        operation: Type of operation (insert_text, delete_range, replace_text, format_text, insert_paragraph)
        document_id: The Google Docs document ID
        parameters: JSON string with operation-specific parameters
        access_token: OAuth access token for Google Docs API
        
    Returns:
        JSON string with the batch request that can be executed later
        
    Example parameters for different operations:
    
    insert_text: {"text": "Hello", "index": 1}
    delete_range: {"start_index": 10, "end_index": 20}
    replace_text: {"text": "New text", "start_index": 10, "end_index": 20}
    format_text: {"start_index": 1, "end_index": 10, "bold": true}
    insert_paragraph: {"text": "paragraph content", "index": -1}
    """
    try:
        # Read document to get current state and validate indices
        service = get_service_from_token(access_token)
        document = service.documents().get(documentId=document_id).execute()
        body = document.get('body', {})
        content = body.get('content', [])
        
        # Parse parameters
        params = json.loads(parameters)
        
        # Build the batch request based on operation type
        requests_list = []
        
        if operation == "insert_text":
            text = params.get('text', '')
            index = params.get('index', -1)
            
            # Calculate actual index if -1 (end of document)
            if index == -1:
                index = calculate_end_index(content)
            
            # Ensure proper formatting
            if not text.endswith('\n'):
                text += '\n'
            
            requests_list.append({
                'insertText': {
                    'location': {'index': index},
                    'text': text
                }
            })
            
        elif operation == "delete_range":
            start_index = params.get('start_index')
            end_index = params.get('end_index')
            
            requests_list.append({
                'deleteContentRange': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    }
                }
            })
            
        elif operation == "replace_text":
            # Replace is delete + insert
            start_index = params.get('start_index')
            end_index = params.get('end_index')
            text = params.get('text', '')
            
            # Delete first
            requests_list.append({
                'deleteContentRange': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    }
                }
            })
            
            # Then insert at the same position
            requests_list.append({
                'insertText': {
                    'location': {'index': start_index},
                    'text': text
                }
            })
            
        elif operation == "format_text":
            start_index = params.get('start_index')
            end_index = params.get('end_index')
            
            text_style = {}
            if params.get('bold') is not None:
                text_style['bold'] = params.get('bold')
            if params.get('italic') is not None:
                text_style['italic'] = params.get('italic')
            if params.get('font_size') is not None:
                text_style['fontSize'] = {'magnitude': params.get('font_size'), 'unit': 'PT'}
            
            requests_list.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    },
                    'textStyle': text_style,
                    'fields': ','.join(text_style.keys())
                }
            })
            
        elif operation == "insert_paragraph":
            text = params.get('text', '')
            index = params.get('index', -1)
            
            if index == -1:
                index = calculate_end_index(content)
            
            # Ensure paragraph formatting
            if not text.startswith('\n') and index > 1:
                text = '\n' + text
            if not text.endswith('\n'):
                text += '\n'
            
            requests_list.append({
                'insertText': {
                    'location': {'index': index},
                    'text': text
                }
            })
        
        else:
            return json.dumps({
                "success": False,
                "error": f"Unknown operation: {operation}"
            })
        
        # Create the batch request object
        batch_request = {
            "document_id": document_id,
            "requests": requests_list
        }
        
        result = {
            "success": True,
            "batch_request": batch_request,
            "operation": operation,
            "parameters": params,
            "preview": generate_preview(operation, params, document)
        }
        
        return json.dumps(result, indent=2)
        
    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid parameters JSON: {str(e)}"
        })
    except Exception as e:
        logger.exception("Error generating batch request")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def execute_batch_request(batch_request: str, access_token: str) -> str:
    """Execute a pre-generated batch request on a Google Doc.
    
    This is typically called after user approval of the batch request.
    
    Args:
        batch_request: JSON string containing the batch request to execute
        access_token: OAuth access token for Google Docs API
        
    Returns:
        Execution result
    """
    try:
        service = get_service_from_token(access_token)
        
        # Parse the batch request
        batch_data = json.loads(batch_request)
        document_id = batch_data.get('document_id')
        requests_list = batch_data.get('requests', [])
        
        if not document_id or not requests_list:
            return json.dumps({
                "success": False,
                "error": "Invalid batch request format"
            })
        
        # Execute the batch update
        result = service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests_list}
        ).execute()
        
        return json.dumps({
            "success": True,
            "message": "Batch request executed successfully",
            "result": result,
            "document_id": document_id
        }, indent=2)
        
    except HttpError as e:
        logger.error(f"HTTP error executing batch request: {e}")
        return json.dumps({
            "success": False,
            "error": f"HTTP {e.resp.status}: {str(e)}"
        })
    except Exception as e:
        logger.exception("Error executing batch request")
        return json.dumps({"success": False, "error": str(e)})


def extract_text_from_body(body: dict) -> str:
    """Extract text content from document body."""
    text_parts = []
    
    for element in body.get('content', []):
        if 'paragraph' in element:
            paragraph = element['paragraph']
            for elem in paragraph.get('elements', []):
                if 'textRun' in elem:
                    text_parts.append(elem['textRun'].get('content', ''))
    
    return ''.join(text_parts)


def extract_structure_info(body: dict) -> Dict[str, Any]:
    """Extract structural information about the document."""
    structure = {
        "paragraphs": [],
        "total_length": 1
    }
    
    for element in body.get('content', []):
        if 'paragraph' in element:
            para_start = element.get('startIndex', 0)
            para_end = element.get('endIndex', 0)
            para_text = ""
            
            paragraph = element['paragraph']
            for elem in paragraph.get('elements', []):
                if 'textRun' in elem:
                    para_text += elem['textRun'].get('content', '')
            
            structure['paragraphs'].append({
                "start_index": para_start,
                "end_index": para_end,
                "text_preview": para_text[:100].strip()
            })
            
            structure['total_length'] = max(structure['total_length'], para_end)
    
    return structure


def calculate_end_index(content: list) -> int:
    """Calculate the end index of the document content."""
    if content:
        for element in reversed(content):
            if 'paragraph' in element:
                return element.get('endIndex', 1) - 1
        return content[-1].get('endIndex', 1) - 1
    return 1


def generate_preview(operation: str, params: Dict[str, Any], document: dict) -> str:
    """Generate a human-readable preview of what the operation will do."""
    if operation == "insert_text":
        text = params.get('text', '')
        preview = text[:100] + "..." if len(text) > 100 else text
        return f"Will insert: '{preview}'"
    
    elif operation == "delete_range":
        start = params.get('start_index')
        end = params.get('end_index')
        chars = end - start
        return f"Will delete {chars} characters (index {start} to {end})"
    
    elif operation == "replace_text":
        text = params.get('text', '')
        preview = text[:50] + "..." if len(text) > 50 else text
        return f"Will replace text with: '{preview}'"
    
    elif operation == "format_text":
        formatting = []
        if params.get('bold'):
            formatting.append("bold")
        if params.get('italic'):
            formatting.append("italic")
        if params.get('font_size'):
            formatting.append(f"{params.get('font_size')}pt")
        return f"Will apply formatting: {', '.join(formatting)}"
    
    return f"Will perform {operation}"


if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "localhost")
    port = int(os.getenv("MCP_PORT", "8001"))
    
    logger.info(f"Starting MCP server on {host}:{port}")
    mcp.run(transport="streamable-http", host=host, port=port)