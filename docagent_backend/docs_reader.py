"""
Simple Google Docs reader.
"""

import logging
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class DocsReader:
    def __init__(self, google_auth):
        self.auth = google_auth
    
    def read_document(self, document_id):
        """Read content from a Google Doc."""
        try:
            service = self.auth.get_service()
            document = service.documents().get(documentId=document_id).execute()
            
            title = document.get('title', 'Untitled Document')
            content = self._extract_text(document.get('body', {}))
            
            return {
                'document_id': document_id,
                'title': title,
                'content': content,
                'accessible': True
            }
            
        except HttpError as e:
            logger.error(f"Error reading document {document_id}: {e}")
            if e.resp.status == 404:
                return {'accessible': False, 'error': 'Document not found'}
            elif e.resp.status == 403:
                return {'accessible': False, 'error': 'Access denied'}
            else:
                return {'accessible': False, 'error': f'API error: {e.resp.status}'}
        except Exception as e:
            logger.error(f"Unexpected error reading document: {e}")
            return {'accessible': False, 'error': str(e)}
    
    def _extract_text(self, body):
        """Extract text content from document body."""
        text_parts = []
        
        for element in body.get('content', []):
            if 'paragraph' in element:
                paragraph = element['paragraph']
                for elem in paragraph.get('elements', []):
                    if 'textRun' in elem:
                        text_parts.append(elem['textRun'].get('content', ''))
        
        return ''.join(text_parts)
    
    def get_document_info(self, document_id):
        """Get basic document information."""
        try:
            service = self.auth.get_service()
            document = service.documents().get(
                documentId=document_id,
                fields='documentId,title'
            ).execute()
            
            return {
                'success': True,
                'document_id': document_id,
                'title': document.get('title', 'Untitled Document'),
                'accessible': True
            }
            
        except HttpError as e:
            logger.error(f"Error getting document info: {e}")
            return {
                'success': False,
                'accessible': False,
                'error': f'HTTP {e.resp.status}'
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                'success': False,
                'accessible': False,
                'error': str(e)
            }