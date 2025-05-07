import os
from langchain.agents import initialize_agent
from langchain.memory import ConversationBufferMemory
from langchain.tools import Tool
from langchain_community.utilities import SerpAPIWrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from googleapiclient.discovery import build
from google.oauth2 import service_account
from serpapi import GoogleSearch
from pydantic.v1 import BaseModel
from dotenv import load_dotenv
import time
load_dotenv()


os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
os.environ["SERPAPI_API_KEY"] = os.getenv("SERPAPI_API_KEY")

SCOPES = ['https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
docs_service = build('docs', 'v1', credentials=credentials)

agent = None
cite_style = "apa"

SYSTEM_TEMPLATE = """
You are an assistant that helps edit and update Google Docs. When processing a query:

1. Use the Google Doc's current content as context
2. For research tasks, utilize search tools to find information
3. When making edits, only modify what's necessary and preserve the rest of the document
4. Your output should be the COMPLETE updated document content that will replace the current content
5. Format your response properly for Google Docs with appropriate headings, paragraphs, and citations
6. When you use search results, ALWAYS include proper citations in the document using the citation numbers provided in the search results
7. Format citations at the end of sentences or paragraphs where information from sources is used, e.g., "Large language models are becoming more common in everyday applications (Author Last Name, Year)."
8. MAINTAIN the "Sources" section if it's provided in search results - do not modify it except to update the index of each source if necessary
9. If other references already exist in the document, append new citations to the end of the list, ensuring they are numbered correctly
10. Strictly follow the citation style provided

Remember: Your entire response will be used to update the document, so it should be the complete text 
of the document after your edits, not just the changes and without your explanations.
"""

def initialize():
    global agent
    search_web_tool = Tool(
        name="Search Web",
        func=search_web, 
        description="Useful for answering questions by finding online sources and links. Use this tool when you need to find general information."
    )
    academic_search_tool = Tool(
        name="Search Google Scholar",
        func=search_google_scholar, 
        description="Useful for answering questions by finding academic and scholarly sources, links, and abstracts. Always use this tool when you need to find information that would benefit from citations or research."
    )
    tools = [search_web_tool,academic_search_tool]

    llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", 
    temperature=0, 
    google_api_key=os.environ["GOOGLE_API_KEY"],
    system_message=SYSTEM_TEMPLATE
    )
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent="chat-conversational-react-description",
        verbose=True,
        memory=memory
    )

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

def search_google_scholar(query):
    """
    Search Google Scholar for academic articles and extract citations using SerpAPI.
    """
    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": os.environ["SERPAPI_API_KEY"],
        "hl": "en",
    }

    search = GoogleSearch(params)
    raw_results = search.get_dict()
    
    formatted_content = ""
    sources_list = []
    
    if "organic_results" in raw_results and raw_results["organic_results"]:
        formatted_content += "Search Results:\n\n"
        
        for idx, result in enumerate(raw_results["organic_results"][:5]):
            title = result.get("title", "No Title")
            link = result.get("link", "No Link")
            snippet = result.get("snippet", "No description available.")
            authors = result.get("publication_info", {}).get("summary", "Unknown Authors")
            cite_id = result.get("result_id")
            if cite_id == None:
                cite_id = result.get("inline_links", {}).get("serpapi_cite_link", None)
                
            formatted_content += f"Result {idx+1}: {title}\nAuthors: {authors}\nSummary: {snippet}\n\n"

            if cite_id:
                params = {
                    "engine": "google_scholar_cite",
                    "q": cite_id,
                    "api_key": os.environ["SERPAPI_API_KEY"],
                    "hl": "en",
                }
                cite_search = GoogleSearch(params)
                citations = cite_search.get_dict().get("citations", [])
                citation = "N/A"
                for cite in citations:
                    if cite.get("title", "") == "APA" and cite_style == cite.get("title").lower():
                        citation = cite.get("snippet")
                        break
                    elif cite.get("title", "") == "MLA" and cite_style == cite.get("title").lower():
                        citation = cite.get("snippet")
                        break
                    elif cite.get("title", "") == "Chicago" and cite_style == cite.get("title").lower():
                        citation = cite.get("snippet")
                        break
                    elif cite.get("title", "") == "Harvard" and cite_style == cite.get("title").lower():
                        citation = cite.get("snippet")
                        break
                    elif cite.get("title", "") == "Vancouver" and cite_style == cite.get("title").lower():
                        citation = cite.get("snippet")
                        break
                
                sources_list.append(f"[{idx}] {citation}")    
            else:
                sources_list.append(f"[{idx}] {title} - {link}")
    
    if sources_list:
        formatted_content += "\nSources:\n" + "\n".join(sources_list)
    else:
        formatted_content += "No relevant sources found."
    
    return formatted_content

def search_web(query):
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

def handle_query(query, doc_id):
    """
    Process a user query to conduct research and/or update a Google Doc.
    """
    RETRIES = 10
    RETRY_DELAY = 5
    current_doc_content = read_google_doc(doc_id)
    
    research_words = ['research', 'find', 'locate', 'search', 'study', 'studies', 'look up', 'cite', 'citation', 'discover', 'update', 'academic', 'scholar', 'scholarly']
    research_task = False
    for word in query.lower().split():
        if word in research_words:
            research_task = True
            break

    if research_task:
        prompt = f"""
        Current Google Doc Content:
        ------------------------
        {current_doc_content}
        ------------------------

        User Query: {query}

        You are an academic research assistant. Based on the current document context, previous context, query, and search results, think step by step about how to come up with a good solution. 
        Based on the current document content above and the user query, please perform the requested 
        research or edits. Your response should be the COMPLETE updated document content that will 
        replace what's currently in the document. Only change what's necessary based on the query.

        Please integrate the search results into the document in a coherent way, while maintaining proper academic citations and the sources section.
        Take into account the previous conversation history to provide better continuity. Please summarize and cite relevant articles and include this
        text into the update in a coherent fashion. Provide good, impactful sentences to bring the new summarized information into context within the 
        current document frame.

        Maintain the "Sources" section that comes with search results - Do NOT remove it. You may update only the index of each source
        to integrate with existing references.
        """
    else:
        prompt = f"""
        Current Google Doc Content:
        ------------------------
        {current_doc_content}
        ------------------------

        User Query: {query}

        You are an academic writing assistant. Based on the current document context, previous context, and query, think step by step about how to come up with a good solution. 
        Based on the current document content above and the user query, please perform the requested 
        edits. Your response should be the COMPLETE updated document content that will 
        replace what's currently in the document. Only change what's necessary based on the query.

        Please integrate the requested edits into the document in a coherent way, while maintaining proper academic citations and the sources section.
        Take into account the previous conversation history to provide better continuity.
        """
    
    for attempt in range(1,RETRIES+1):
        try:
            result = agent.invoke({"input": prompt})
            updated_content = result.get("output", "Error: No output returned from agent")
            return updated_content
        except Exception as e:
            if attempt < RETRIES:
                print(f"[Retry {attempt}/{RETRIES}] Error: {e}. Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
                RETRY_DELAY *= 2
            else:
                print(f"[Retry {attempt}/{RETRIES}] Failed after multiple attempts.")
                raise

def main():
    doc_id = os.getenv("GOOGLE_DOC_ID")
    if not doc_id:
        print("No Associated document id, returning")
        return
    initialize()

    print("\nGoogle Doc Research Assistant")
    print("----------------------------")
    print(f"Connected to document ID: {doc_id}")

    global cite_style
    styles = ["apa", "mla", "chicago", "harvard", "vancouver"]
    style = input("\nEnter a valid citation style from the following: apa, mla, harvard, chicago, vancouver\n")
    if style.lower() not in styles:
        print("Invalid citation style, try again")
        return
    else:
        cite_style = style.lower()
    
    while True:
        query = input("\nEnter your research or editing query (type 'exit' to end program): ")
        if query.lower() == 'exit':
            print("Exiting program.")
            break
        
        print("\nProcessing request... (this may take a moment)")
        try:
            updated_content = handle_query(query, doc_id)
                
            print("\nProposed Document Update:")
            print("-" * 50)
            print(updated_content)
            print("-" * 50)
            
            apply_changes = input("\nDo you want to apply these changes to the document? (y/n): ")
            if apply_changes.lower() == 'y' or apply_changes.lower() == 'yes' or apply_changes.lower() == 'apply':
                update_google_doc(doc_id, updated_content)
                print("Document updated successfully!")
            else: 
                print("Changes not applied.")
        except Exception as e:
            print(f"Error processing your request: {e}")
            
        continue_prompt = input("\nDo you want to make another query? (y/n): ")
        if continue_prompt.lower() not in ['y', 'yes']:
            print("Exiting the assistant.")
            break
        print("\n")

if __name__ == "__main__":
    main()