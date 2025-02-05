import time
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from mem0 import Memory
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams
import psycopg2
import os
import google.generativeai as genai

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

# Initialize FastAPI app
app = FastAPI()

config = {
    "embedder": {
        "provider": "gemini",
        "config": {
            "model": "models/text-embedding-004",
            "embedding_dims": 768,
            "api_key": os.getenv("GEMINI_API_KEY"),
            }
        },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": os.getenv("MEMORY_COLLECTION"),
            "host": os.getenv("QDRANT_HOST"),
            "port": int(os.getenv("QDRANT_PORT")),
              "embedding_model_dims": 768,
        },
     },
    "llm": {
        "provider": "gemini",
        "config": {
            "model": "gemini-1.5-flash-latest",
            "temperature": 0.2,
        }
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "url": os.getenv("NEO4J_URI"),
            "username": os.getenv("NEO4J_AUTH").split('/')[0],
            "password": os.getenv("NEO4J_AUTH").split('/')[1],
        },
        "llm": {
            "provider": "gemini",
            "config": {
                "model": "gemini-1.5-flash-latest",
                "temperature": 0.0,
        }
    }
    },
    "version": "v1.1"
}
memory = Memory.from_config(config)
print(memory)

def create_prompt_context(data):
    """
    Creates a context string similar to Zep format using Gemini, extracting
    information from raw facts and relations, including UTC date ranges.

    Args:
        data (dict): The JSON data representing facts and relations.
        gemini_api_key (str): The API key for the Gemini API.

    Returns:
        str: A context string summarizing the information, or None if an error occurs.
    """
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    prompt = f"""
    You are an expert at extracting key details about a user given a set of raw memories. 
    You will be provided JSON data containing `results` and `relations` arrays.

    For the `results` array, which represents facts, each item contains:
    - An ID.
    - `memory` text.
    - Scores (ignore).
    - `created_at` timestamp, which may be in any time zone.
    - An optional `updated_at` timestamp, which may be in any time zone.

    For each fact, you MUST extract the text from the `memory` property and include a date range showing its validity. 
    The date range MUST be in UTC (Coordinated Universal Time) and in the format: YYYY-MM-DDTHH:MM:SS+00:00

    - If the `updated_at` is null, then the end date is 'present'.
    - Otherwise, if the `updated_at` field exists, the end date MUST be taken from this field and MUST be converted to UTC.
    - The start date should be taken from `created_at` and must also be converted to UTC.

    The `relations` array contains relationships between the memories, however for this summary, you should not include any data about the relationships.

    You must format the output as follows:

    FACTS and ENTITIES represent relevant context to the current conversation.

    # These are the most relevant facts and their valid date ranges

    # format: FACT (Date range: from - to)

    <FACTS>
    -  [fact] ([date_from] - [date_to])
    </FACTS>

    # These are the most relevant entities

    # ENTITY_NAME: entity summary

    <ENTITIES>
    - [entity_name]: [entity_summary]
    </ENTITIES>

    You MUST provide the facts and entities sections in the correct format. If there are no facts or no entities then the respective section should not be included.

    The data is provided below:

    {data}
    """
    try:
        response = model.generate_content(prompt)
        if response.text:
             return response.text.strip()
        return None
    except Exception as e:
        print(f"Error during Gemini context creation: {e}")
        return None

def process_data_with_zep_context(data):
    """
      Takes in raw data and processes it using Gemini to produce a context string before returning the original data to the user.
        Args:
            data (dict): The JSON data representing facts and relations.
            gemini_api_key (str): The API key for the Gemini API.

        Returns:
            dict: The original JSON data with the context string included.
    """
    context = create_prompt_context(data)
    if context:
        data["context_string"] = context
    return data

def connect_with_retry(max_retries=10, retry_delay=5):
    """Connects to the database with retries."""
    retries = 0
    while retries < max_retries:
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                host=os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT"),
            )
            return conn
        except psycopg2.OperationalError as e:
            retries += 1
            print(f"Database not ready, retrying in {retry_delay} seconds ({retries}/{max_retries}). Error: {e}")
            time.sleep(retry_delay)
    raise Exception(f"Failed to connect to database after {max_retries} retries")

# Now, use the function:
conn = connect_with_retry()

# Request models for API endpoints
class AddMemoryRequest(BaseModel):
    user_id: str
    text: str


class SearchMemoryRequest(BaseModel):
    user_id: str
    query: str

@app.post("/add_memory/")
async def add_memory(request: AddMemoryRequest):
    try:
        memory_result = memory.add(request.text, user_id=request.user_id)
        print(f"Added memory with ID: {memory_result}")

        # Ensure mem0 returns a value
        if not memory_result:
           raise HTTPException(status_code=500, detail=f"Error adding/updating memory: mem0 returned no ids")

        return {"message": "Memory operation completed!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing memory event: {e}")

@app.post("/search_memory/")
async def search_memory(request: SearchMemoryRequest):
    try:
        # Search memories in Mem0 (uses Qdrant for similarity search)
        results = memory.search(query=request.query, user_id=request.user_id)
        processed_data = process_data_with_zep_context(results)
        # filtered_results = [result for result in results if result["score"] > 0.5]

        return {"query": request.query, "results": processed_data['context_string']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching memory: {e}")


@app.get("/")
async def root():
    return {"message": "Mem0 API is running locally!"}