import os
from langchain.agents import initialize_agent
from langchain.memory import ConversationBufferMemory
from langchain.tools import Tool
from langchain.utilities import SerpAPIWrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from googleapiclient.discovery import build
from google.oauth2 import service_account
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()


os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
os.environ["SERPAPI_API_KEY"] = os.getenv("SERPAPI_API_KEY")

SCOPES = ['https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
docs_service = build('docs', 'v1', credentials=credentials)

def read_google_doc(doc_id):
    """Read the current content of a Google Doc."""
    document = docs_service.documents().get(documentId=doc_id).execute()
    doc_content = ''
    
    if 'body' in document and 'content' in document['body']:
        for content in document['body']['content']:
            if 'paragraph' in content:
                for element in content['paragraph']['elements']:
                    if 'textRun' in element:
                        doc_content += element['textRun']['content']
    
    return doc_content

def update_google_doc(doc_id, new_content):
    """Update the Google Doc with edited content."""
    document = docs_service.documents().get(documentId=doc_id).execute()
    
    if 'body' in document and 'content' in document['body']:
        end_index = document['body']['content'][-1].get('endIndex', 0)-1
        if end_index > 1:
            requests = [{
                'deleteContentRange': {
                    'range': {
                        'startIndex': 1,
                        'endIndex': end_index
                    }
                }
            }]
            docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
    if new_content != '':
        requests = [{
            'insertText': {
                'location': {'index': 1},
                'text': new_content
            }
        }]
        docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
    return new_content

search = SerpAPIWrapper()
search_tool = Tool(
    name="Search",
    func=search.run,
    description="Useful for answering questions by finding academic sources, links, and abstracts."
)

SYSTEM_TEMPLATE = """
You are an assistant that helps edit and update Google Docs. When processing a query:

1. Use the Google Doc's current content as context
2. For research tasks, utilize search tools to find information
3. When making edits, only modify what's necessary and preserve the rest of the document
4. Your output should be the COMPLETE updated document content that will replace the current content
5. Format your response properly for Google Docs with appropriate headings, paragraphs, and citations

Remember: Your entire response will be used to update the document, so it should be the complete text 
of the document after your edits, not just the changes or your explanations.
"""

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", 
    temperature=0, 
    google_api_key=os.environ["GOOGLE_API_KEY"],
    system_message=SYSTEM_TEMPLATE
)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

tools = [search_tool]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="chat-conversational-react-description",
    verbose=False,
    memory=memory
)

def handle_research_query(query, doc_id):
    """
    Process a user query to conduct research and update a Google Doc.
    
    Args:
        query (str): The user's research or editing request
        doc_id (str): The Google Doc ID to read from and update
        
    Returns:
        str: The updated document content
    """
    current_doc_content = read_google_doc(doc_id)
    
    prompt = f"""
Current Google Doc Content:
------------------------
{current_doc_content}
------------------------

User Query: {query}

Based on the current document content above and the user query, please perform the requested 
research or edits. Your response should be the COMPLETE updated document content that will 
replace what's currently in the document. Only change what's necessary based on the query.
"""
    
    updated_content = agent.run(prompt)
    
    return updated_content

if __name__ == "__main__":
    doc_id = os.getenv("GOOGLE_DOC_ID")
    
    print("\nGoogle Doc Research Assistant")
    print("----------------------------")
    print(f"Connected to document ID: {doc_id}")
    
    while True:
        query = input("\nEnter your research or editing query (type 'exit' to end program): ")
        if query.lower() == 'exit':
            print("Exiting program.")
            break
        updated_content = handle_research_query(query, doc_id)
            
        print("\nProposed Document Update:")
        print("-" * 50)
        print(updated_content)
        print("-" * 50)
        
        apply_changes = input("\nDo you want to apply these changes to the document? (y/n): ")
        if apply_changes.lower() == 'y':
            update_google_doc(doc_id, updated_content)
            print("Document updated successfully!")
        else: 
            print("Changes not applied.")
        continue_prompt = input("\nDo you want to make another query? (y/n): ")
        if continue_prompt.lower() != 'y':
            print("Exiting the assistant.")
            break
        print("\n")
        