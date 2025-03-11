# AI imports
import qdrant_client
import openai
from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
# Regular imports
import uuid
import os
import hashlib
import argparse

# Global Vars
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SPARSE_MODEL = "prithivida/Splade_PP_en_v1"
COLLECTION_NAME = "rag"
# Needed for mac to not give errors
os.environ["TOKENIZERS_PARALLELISM"] = "true"


# Helper Classes and Functions

class Rag:
    def __init__(self):
        # Setup vector database
        self.client = qdrant_client.QdrantClient(path=os.getcwd()+"/db")
        self.client.set_model(EMBED_MODEL)
        self.client.set_sparse_model(SPARSE_MODEL)

        if not self.client.collection_exists(COLLECTION_NAME):
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=self.client.get_fastembed_vector_params(),
                sparse_vectors_config=self.client.get_fastembed_sparse_vector_params(),  
            )

        # Setup docling class
        self.conv = Converter()

        # Setup openai api
        self.llm = openai.OpenAI(api_key="your-api-key", base_url="http://localhost:8080")
        self.chat_history = []  # Store chat history
    
    def insertPDF(self, file_path):
        documents, metadata, ids =  self.conv.convert(file_path)
        self.client.add(COLLECTION_NAME, documents=documents, metadata=metadata, ids=ids)
    
    def query(self, prompt):
        # Add user query to chat history
        self.chat_history.append({"role": "user", "content": prompt})
        
        # Ensure chat history does not exceed 10 messages (5 user + 5 AI)
        if len(self.chat_history) > 10:
            self.chat_history.pop(0)  # Remove the oldest message
        
        # Query the Qdrant client for relevant context
        results = self.client.query(
            collection_name="rag",
            query_text=prompt,
            limit=5,
        )
        context = "\n".join(r.document for r in results)

        # Prepare the metaprompt with chat history and context
        metaprompt = f"""
            You are an expert software architect.  
            Use the provided context and chat history to answer the question accurately and concisely.  
            If the answer is not explicitly stated, infer the most reasonable answer based on the available information.  
            If there is no relevant information, respond with "I don't know"—do not fabricate details.  

            ### Chat History:
            {self.format_chat_history()}

            ### Context:  
            {context.strip()}  

            ### Question:  
            {prompt.strip()}  

            ### Answer:
            """
        
        # Query the LLM with the metaprompt
        response = self.llm.chat.completions.create(
            model="your-model-name",
            messages=[{"role": "user", "content": metaprompt}],
            stream=True 
        )

        # Collect the AI response and add it to chat history
        full_response = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
                print(chunk.choices[0].delta.content, end="", flush=True)
        
        # Add AI response to chat history
        self.chat_history.append({"role": "assistant", "content": full_response})
        
        # Ensure chat history does not exceed 10 messages after adding the AI response
        if len(self.chat_history) > 10:
            self.chat_history.pop(0)  # Remove the oldest message
        
        print(" ")

    def format_chat_history(self):
        """Format the chat history into a string for inclusion in the metaprompt."""
        formatted_history = []
        for i in range(0, len(self.chat_history), 2):
            user_message = self.chat_history[i]["content"]
            if i + 1 < len(self.chat_history):
                ai_message = self.chat_history[i + 1]["content"]
                formatted_history.append(f"User: {user_message}\nAI: {ai_message}")
            else:
                formatted_history.append(f"User: {user_message}\nAI: ")
        return "\n".join(formatted_history)

    def run(self):
        print("> Welcome to the Rag Assistant!")
        try:
            while True:
                # User input
                user_input = input("> ").strip()

                # Skip empty queries
                if not user_input:
                    print("> Please enter a valid query.")
                    continue
                
                # Check for a specific query
                try:
                    self.query(user_input)
                except KeyboardInterrupt:
                    print("\nStream interrupted.")
                print(" ")

        except KeyboardInterrupt:
            print("\n> Exiting... Goodbye!")  # Catch any Interrupts and exit gracefully

class Converter:
    """A Class desgined to handle all document conversions using Docling"""
    def __init__(self):
        self.doc_converter = DocumentConverter()

    def convert(self, file_path):
        targets = []

        # Check if file_path is a directory or a file
        if os.path.isdir(file_path):
            targets.extend(self.walk(file_path))  # Walk directory and process all files
        elif os.path.isfile(file_path):
            targets.append(file_path)  # Process the single file
        else:
            # if the path provided is wrong just return false
            raise ValueError(f"Invalid file or file path: {file_path}")

        result = self.doc_converter.convert_all(targets)

        documents, metadatas, ids = [], [], []

        chunker = HybridChunker(tokenizer=EMBED_MODEL, max_tokens=500, overlap=100)
        for file in result:
            chunk_iter = chunker.chunk(dl_doc=file.document)
            for i, chunk in enumerate(chunk_iter):
                doc_text = chunker.serialize(chunk=chunk)
                # Extract the text and metadata from the chunk
                doc_meta = chunk.meta.export_json_dict() 

                # Append to respective lists
                documents.append(doc_text)
                metadatas.append(doc_meta)
                
                # Generate unique ID for the chunk
                doc_id = self.generate_hash(doc_text)
                ids.append(doc_id)
        return documents, metadatas, ids

    def walk(self, path):
        targets = []
        for root, dirs, files in os.walk(path, topdown=True):
            if len(files) == 0:
                continue
            for f in files:
                file = os.path.join(root, f)
                if os.path.isfile(file):
                    targets.append(file)
        return targets
    
    def generate_hash(self, document: str) -> str:
        """Generate a unique hash for a document."""
            # Generate SHA256 hash of the document text
        sha256_hash = hashlib.sha256(document.encode('utf-8')).hexdigest()
        
        # Use the first 32 characters of the hash to create a UUID
        return str(uuid.UUID(sha256_hash[:32]))

def insert(file_path):
    rag = Rag()
    rag.insertPDF(file_path)

def run_rag():
    rag = Rag()
    rag.run()


parser = argparse.ArgumentParser(description="A script that interacts with Rag.")
parser.add_argument('--insert', type=str, help='Insert a PDF file into Vector Database', metavar='FILE_PATH')
parser.add_argument('--run', action='store_true', help='Run the RAG')

args = parser.parse_args()


if args.insert:
    insert(args.insert)

if args.run:
    run_rag()