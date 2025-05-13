# AI imports
import cmd
import openai
from fastembed.rerank.cross_encoder import TextCrossEncoder
from fastembed import TextEmbedding, SparseTextEmbedding
from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from docling_core.types.doc import DoclingDocument
# Vectordb imports
import qdrant_client
from pymilvus import MilvusClient, AnnSearchRequest, RRFRanker
# Regular imports
import uuid
import os
import hashlib
import argparse
from pathlib import Path
import json
import sys

# Global Vars
EMBED_MODEL = os.getenv("EMBED_MODEL", "jinaai/jina-embeddings-v2-small-en")
SPARSE_MODEL = os.getenv("SPARSE_MODEL", "prithivida/Splade_PP_en_v1")
RANK_MODEL = os.getenv("RANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")
COLLECTION_NAME = "rag"
# Needed for mac to not give errors
os.environ["TOKENIZERS_PARALLELISM"] = "true"


def eprint(e, exit_code):
    print("Error:", str(e).strip("'\""), file=sys.stderr)
    sys.exit(exit_code)

# Helper Classes and Functions

class qdrant:
    def __init__(self, vector_path):
        self.client = qdrant_client.QdrantClient(path=vector_path)
        self.client.set_model(EMBED_MODEL)
        self.client.set_sparse_model(SPARSE_MODEL)
    
    def query(self, prompt):
        results = self.client.query(
            collection_name="rag",
            query_text=prompt,
            limit=20,
        )
        qdrant_results = [r.document for r in results] 
        return qdrant_results

class milvus:
    def __init__(self, vector_path):
        self.milvus_client = MilvusClient(uri=os.path.join(vector_path, "milvus.db"))
        self.dmodel = TextEmbedding(model_name=EMBED_MODEL)
        self.smodel = SparseTextEmbedding(model_name=SPARSE_MODEL)
    
    def query(self, prompt):
        dense_embedding = next(self.dmodel.embed([prompt]))
        sparse_embedding = next(self.smodel.embed([prompt])).as_dict()

        search_param_dense = {
            "data": [dense_embedding],
            "anns_field": "dense",
            "param": {
                "metric_type": "IP",
                "params": {"nprobe": 10}
            },
            "limit": 10
        }

        request_dense = AnnSearchRequest(**search_param_dense)

        search_param_sparse = {
            "data": [sparse_embedding],
            "anns_field": "sparse",
            "param": {
                "metric_type": "IP",
                "params": {"drop_ratio_build": 0.2}
            },
            "limit": 10
        }

        request_sparse = AnnSearchRequest(**search_param_sparse)

        reqs = [request_dense, request_sparse]

        ranker = RRFRanker(100)
        
        results = self.milvus_client.hybrid_search(
            collection_name=COLLECTION_NAME,
            reqs=reqs,
            ranker=ranker,
            limit=20,
            output_fields=["text"],
        )
        milvus_results = [hit["entity"]["text"] for hit in results[0]]
        return milvus_results

class RagService():
    def __init__(self, vector_path):
        self.reranker = TextCrossEncoder(model_name=RANK_MODEL)

        if self.is_milvus(vector_path):
            # setup mivlus
            self.vectordb = milvus(vector_path)
        else:
            # setup qdrant
            self.vectordb = qdrant(vector_path)

        self.chat_history = []  # Store chat history
    
    def is_milvus(self, vector_path):
        return any(f.suffix == ".db" and f.is_file() for f in Path(vector_path).iterdir())

    def do_EOF(self, user_content):
        print("")
        return True
    
    def setup_query(self, prompt: str) -> str:
        # Add user query to chat history
        self.chat_history.append({"role": "user", "content": prompt})
        
        # Ensure chat history does not exceed 10 messages (5 user + 5 AI)
        if len(self.chat_history) > 10:
            self.chat_history.pop(0)  # Remove the oldest message
        
        # Query the Vectordb
        result = self.vectordb.query(prompt)
        # reranker code to have the first 5 queries 
        reranked_context = " ".join(
            str(result[i]) for i, _ in sorted(
                enumerate(self.reranker.rerank(prompt, result)),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        )

        # Prepare the metaprompt with chat history and context
        metaprompt = f"""
            You are an expert software architect.  
            Use the provided context and chat history to answer the question accurately and concisely.  
            If the answer is not explicitly stated, infer the most reasonable answer based on the available information.  
            If there is no relevant information, respond with "I don't know"—do not fabricate details.  

            ### Chat History:
            {self.format_chat_history()}

            ### Context:  
            {reranked_context.strip()}  

            ### Question:  
            {prompt.strip()}  

            ### Answer:
            """
        
        return metaprompt
    
    def chat_history(self, response):
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