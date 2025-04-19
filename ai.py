import os
from langchain.agents import initialize_agent
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.tools import Tool
from langchain.utilities import SerpAPIWrapper
from googleapiclient.discovery import build
from google.oauth2 import service_account

# pip install -r dependencies.txt

os.environ["OPENAI_API_KEY"] = "your-openai-api-key"
os.environ["SERPAPI_API_KEY"] = "your-serpapi-key"

# web search with serp
search = SerpAPIWrapper()
search_tool = Tool(
    name="Search",
    func=search.run,
    description="Useful for answering questions by finding academic sources, links, and abstracts."
)

# google doc access api
SCOPES = ['https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_FILE = 'credentials.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
docs_service = build('docs', 'v1', credentials=credentials)

def write_to_doc(doc_id, content):
    requests = [{
        'insertText': {
            'location': {'index': 1},
            'text': content + "\n\n"
        }
    }]
    docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()

# langchain agent
llm = ChatOpenAI(temperature=0)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

tools = [search_tool]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="chat-conversational-react-description",
    verbose=True,
    memory=memory
)

# insert query and model response
def handle_research_query(query, doc_id):
    response = agent.run(query)
    write_to_doc(doc_id, f"Query: {query}\nResponse: {response}")
    return response

# https://docs.google.com/document/d/1xvUOhzFJaJ1_PdhVcWhOwTwuy5GSacZ-RBT7QpBWfpU/edit?tab=t.0
# example
if __name__ == "__main__":
    doc_id = "1xvUOhzFJaJ1_PdhVcWhOwTwuy5GSacZ-RBT7QpBWfpU/edit?tab=t.0"
    query = "Summarize recent research on transformer models in NLP and cite at least 3 sources with links."
    result = handle_research_query(query, doc_id)
    print("Agent Response:\n", result)
