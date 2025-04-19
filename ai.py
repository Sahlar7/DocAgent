import os
from langchain.agents import initialize_agent
from langchain.memory import ConversationBufferMemory
from langchain.tools import Tool
# from langchain.utilities import SerpAPIWrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from googleapiclient.discovery import build
from google.oauth2 import service_account
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

# pip install -r dependencies.txt

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
os.environ["SERPAPI_API_KEY"] = os.getenv("SERPAPI_API_KEY")

def access_fake_info(input_text):
    print(input_text)
    json = {
        "query": "Summarize recent research on transformer models in NLP and cite at least 3 sources with links.",
        "summary": "Recent research on transformer models in NLP has focused on improving efficiency, interpretability, and multilingual capabilities. One study introduced 'Sparse Transformer' techniques to reduce computational complexity while maintaining performance. Another explored 'AdapterFusion', allowing pre-trained transformers to adapt efficiently to multiple tasks. Additionally, multilingual models like 'mT5' have shown improvements in cross-lingual transfer tasks, further advancing global NLP applications.",
        "citations": [
            {
            "title": "Sparse Transformers: Scaling Transformers to 1,000 Layers",
            "authors": ["Child, R.", "Gray, S.", "Radford, A."],
            "abstract": "This paper introduces sparse attention mechanisms to reduce transformer complexity from O(n^2) to O(n√n), enabling scalability to deeper networks.",
            "url": "https://arxiv.org/abs/1904.10509"
            },
            {
            "title": "AdapterFusion: Non-Destructive Task Composition for Transfer Learning",
            "authors": ["Pfeiffer, J.", "Rücklé, A.", "Gurevych, I."],
            "abstract": "AdapterFusion enables combining multiple adapters learned from different tasks without retraining the full model.",
            "url": "https://arxiv.org/abs/2005.00247"
            },
            {
            "title": "mT5: A Massively Multilingual Pre-trained Text-to-Text Transformer",
            "authors": ["Xue, L.", "Constant, N.", "Roberts, A."],
            "abstract": "mT5 extends the T5 model to over 100 languages, enabling strong cross-lingual transfer performance on downstream NLP tasks.",
            "url": "https://arxiv.org/abs/2010.11934"
            }
        ],
        "generated_by": "Gemini+LangChain Agent (Simulated Output)"
    }
    return json

# web search with serp
# search = SerpAPIWrapper()
# search_tool = Tool(
#     name="Search",
#     func=search.run,
#     description="Useful for answering questions by finding academic sources, links, and abstracts."
# )
search_tool = Tool(
    name="Search",
    func=access_fake_info,
    description="Useful for answering questions by finding academic sources, links, and abstracts."
)

# google doc access api
SCOPES = ['https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_FILE = 'credentials.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
docs_service = build('docs', 'v1', credentials=credentials)

def write_to_doc(doc_id, content):
    requests = [{  # LLM has to create this to insert bold, etc
        'insertText': {
            'location': {'index': 1},
            'text': content + "\n\n"
        }
    }]
    docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()

# langchain agent
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0, google_api_key=os.environ["GOOGLE_API_KEY"])
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

tools = [search_tool]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="chat-conversational-react-description",
    verbose=False,
    memory=memory
)

# insert query and model response
def handle_research_query(query, doc_id):
    response = agent.run(query)
    write_to_doc(doc_id, f"Query: {query}\nResponse: {response}")
    return response

# https://docs.google.com/document/d/1xvUOhzFJaJ1_PdhVcWhOwTwuy5GSacZ-RBT7QpBWfpU/edit?tab=t.0
# need to add service account email to editor for access perms
# example
if __name__ == "__main__":
    doc_id = "1xvUOhzFJaJ1_PdhVcWhOwTwuy5GSacZ-RBT7QpBWfpU"
    query = "Summarize recent research on transformer models in NLP and cite at least 1 sources with links. Format to give me Authors: .... \n Abstract .... \n URL: .... \n Summary .... for each source. Format this for Google Docs."
    result = handle_research_query(query, doc_id)
    print("Agent Response:\n", result)
