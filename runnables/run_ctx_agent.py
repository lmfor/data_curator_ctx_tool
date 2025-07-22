import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

# Add src directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
metadata_path = os.path.join('..', 'hierarchial_output', 'metadata.json')
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from workflow.ctx_agent import query_contextual_agent, parse_contextual_response

try:
    metadata_path = 'hierarchical_output/metadata.json'
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
except:
    pass



def print_all_titles(metadata: Dict[str, Any]) -> None:
    for page in metadata:
        print(f"{page['title']}") # type: ignore
        
# Gather title (& other relevant info LATER) -> query agent -> if response > 70 then print . . .

def agent_workflow(metadata: Dict[str, Any]) -> List[Any]: # type: ignore
    for page in metadata:
        page_title = page['title'] # type: ignore
        page_id = page['id'] # type: ignore
        
        # Query the agent with the page title
        response_data = query_contextual_agent(f"""
                                               SYSTEM PROMPT: You are to give a score from 0 to 1 that represents how related the prompt is to anything V93K/ST8
                                               -----
                                               PROMPT: {page_title}""") #type: ignore
        
        if response_data:
            print(response_data["message"]["content"]) 
            
        return [response_data["message"]["content"]] if response_data else []
            
        
agent_workflow(metadata) # type: ignore