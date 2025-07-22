import sys
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional


# Load environment variables
load_dotenv()
contextual_agent_id = os.getenv("AGENT_ID")  # V93K ST8 CodeGenie A ID
contextual_api_key = os.getenv("CONTEXTUAL_API_KEY")  # V93K ST8 CodeGenie A API Key
BASE_URL = "https://api.app.contextual.ai/v1"

def parse_contextual_response(response_json: Dict[str, Any]) -> Dict[str, Any]:
    # Extract message information
    message = response_json.get("message", {})
    message_data = {
        "content": message.get("content", ""),
        "role": message.get("role", "")
    }
    
    # Extract retrieval contents with all metadata
    retrieval_contents = []
    for item in response_json.get("retrieval_contents", []):
        retrieval_item = {
            "custom_metadata": item.get("custom_metadata"),
            "custom_metadata_config": item.get("custom_metadata_config"),
            "number": item.get("number"),
            "type": item.get("type"),
            "format": item.get("format"),
            "content_id": item.get("content_id"),
            "doc_id": item.get("doc_id"),
            "doc_name": item.get("doc_name"),
            "page": item.get("page"),
            "content_text": item.get("content_text"),
            "url": item.get("url"),
            "ctxl_metadata": item.get("ctxl_metadata"),
            "score": item.get("score")
        }
        retrieval_contents.append(retrieval_item)
    
    # Extract attributions
    attributions = []
    for attr in response_json.get("attributions", []):
        attribution = {
            "start_idx": attr.get("start_idx"),
            "end_idx": attr.get("end_idx"),
            "content_ids": attr.get("content_ids", [])
        }
        attributions.append(attribution)
    
    # Extract groundedness score (if present)
    groundedness = response_json.get("groundedness_score")
    groundedness_score = None
    if groundedness:
        groundedness_score = {
            "start_idx": groundedness.get("start_idx"),
            "end_idx": groundedness.get("end_idx"),
            "content_ids": groundedness.get("content_ids", [])
        }
    
    # Create the structured response dictionary
    response_data = {
        "conversation_id": response_json.get("conversation_id"),
        "message_id": response_json.get("message_id"),
        "message": message_data,
        "retrieval_contents": retrieval_contents,
        "attributions": attributions,
        "groundedness_score": groundedness_score
    }
    
    return response_data

def query_contextual_agent(question: str, include_optional_fields: bool = False):
    # Basic required structure
    payload = {
        "messages": [
            {
                "content": question,
                "role": "user"
            }
        ]
    }
    
    # Add optional fields if needed
    if include_optional_fields:
        payload.update({
            "stream": False,
            "conversation_id": "",
            "llm_model_id": "",
            "structured_output": {
                "type": "JSON",
                "json_schema": {}
            },
            "documents_filters": {
                "filters": [
                    {
                        "field": "field1",
                        "operator": "equals",
                        "value": "value1"
                    }
                ],
                "operator": "AND"
            }
        }) #type: ignore
    
    response = requests.post(
        f"{BASE_URL}/agents/{contextual_agent_id}/query",
        json=payload,
        headers={
            "Authorization": f"Bearer {contextual_api_key}",
            "Content-Type": "application/json"
        }
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
        response.raise_for_status()


# if __name__ == "__main__":
    # Query the agent
    # response_data = query_contextual_agent("""
                                           # SYSTEM PROMPT:
                                           # You are to give a score from 0 to 1 that represents how related the prompt is to anything V93K/ST8
                                           # PROMPT:
                                           # 93k_Platform_Principles""")
    
    # if response_data:
        # Print only the message content 
        # print(response_data["message"]["content"]) 
        
        # The full response_data dictionary contains all structured information:
        # - response_data["conversation_id"]
        # - response_data["message_id"]
        # - response_data["message"]["content"]
        # - response_data["message"]["role"]
        # - response_data["retrieval_contents"] - list of retrieved documents
        # - response_data["attributions"] - list of attribution ranges
        # - response_data["groundedness_score"] - groundedness information
        
        # Example: Print additional information if needed
        # print(f"\nConversation ID: {response_data['conversation_id']}")
        # print(f"Number of retrieved documents: {len(response_data['retrieval_contents'])}")
        # print(f"Top document: {response_data['retrieval_contents'][0]['doc_name'] if response_data['retrieval_contents'] else 'None'}")
        