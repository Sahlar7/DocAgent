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

def search_with_sources(query):
    """
    Perform a search using SerpAPI and format the results with source information.
    """
    search_wrapper = SerpAPIWrapper()
    raw_results = search_wrapper.results(query)
    
    formatted_content = ""
    sources_list = []
    
    if "answer_box" in raw_results:
        answer_box = raw_results["answer_box"]
        if "answer" in answer_box:
            formatted_content += f"{answer_box['answer']}\n\n"
        elif "snippet" in answer_box:
            formatted_content += f"{answer_box['snippet']}\n\n"
            
        if "source" in answer_box and "link" in answer_box:
            sources_list.append(f"[1] {answer_box.get('title', 'Answer Box')} - {answer_box['link']} ({answer_box['source']})")
            formatted_content += "(Source [1])\n\n"
    
    if "organic_results" in raw_results and raw_results["organic_results"]:
        formatted_content += "Search Results:\n\n"
        
        for idx, result in enumerate(raw_results["organic_results"][:5]):
            title = result.get("title", "No Title")
            link = result.get("link", "No Link")
            snippet = result.get("snippet", "No description available.")
            source = result.get("source", "Unknown Source")
            
            source_idx = idx + 1
            if "answer_box" in raw_results:
                source_idx += 1
                
            formatted_content += f"Result {idx+1}: {snippet}\n(Source [{source_idx}])\n\n"
            sources_list.append(f"[{source_idx}] {title} - {link} ({source})")
    
    if sources_list:
        formatted_content += "\nSources:\n" + "\n".join(sources_list)
    else:
        formatted_content += "No relevant sources found."
    
    return formatted_content

search_tool = Tool(
    name="Search",
    func=search_with_sources,
    description="Useful for answering questions by finding academic sources, links, and abstracts. Always use this tool when you need to find information that would benefit from citations."
)

SYSTEM_TEMPLATE = """
You are an assistant that helps edit and update Google Docs. When processing a query:

1. Use the Google Doc's current content as context
2. For research tasks, utilize search tools to find information
3. When making edits, only modify what's necessary and preserve the rest of the document
4. Your output should be the COMPLETE updated document content that will replace the current content
5. Format your response properly for Google Docs with appropriate headings, paragraphs, and citations
6. When you use search results, ALWAYS include proper citations in the document using the citation numbers provided in the search results
7. Format citations at the end of sentences or paragraphs where information from sources is used, e.g., "Large language models are becoming more common in everyday applications [2]."
8. MAINTAIN the "Sources" section if it's provided in search results - do not modify it except to update the index of each source if necessary
9. If other references already exist in the document, append new citations to the end of the list, ensuring they are numbered correctly

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
    verbose=True,
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

If you use the search tool to find information, please incorporate the citations appropriately 
in the document. The search results will include numbered references that you should integrate into 
your writing (e.g., "This is a fact from a source [1].").

Maintain the "Sources" section that comes with search results - Do NOT remove it. You may update only the index of each source
to integrate with existing references.
"""
    
    try:
        result = agent.invoke({"input": prompt})
        updated_content = result.get("output", "Error: No output returned from agent")
        return updated_content
    except Exception as e:
        return f"Error processing request: {str(e)}\n\nPlease try again with a different query."

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
        
        print("\nResearching and updating document... (this may take a moment)")
        try:
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
        except Exception as e:
            print(f"Error processing your request: {e}")
            
        continue_prompt = input("\nDo you want to make another query? (y/n): ")
        if continue_prompt.lower() != 'y':
            print("Exiting the assistant.")
            break
        print("\n")