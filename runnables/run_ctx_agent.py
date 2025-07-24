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
        
# Gather title (& other relevant info LATER) -> query agent -> if response > .70 then print . . .

def agent_workflow(metadata: Dict[str, Any]) -> List[Any]: # type: ignore
    # parsed_response = parse_contextual_response(metadata) # type: ignore
    # print(parsed_response['content'])
    # print(metadata[0]['title']) #type: ignore
    
    
    # Multiquery (Lots of prompts be careful.)
    for page in metadata:
        page_title = page['title'] #type: ignore
        page_id = page['id'] #type: ignore
        page_content = page['content'] if 'content' in page else '' #type: ignore
        page_breadcrumbs = page['breadcrumbs'] if 'breadcrumbs' in page else [] #type: ignore
        # print(f"Processing page: {page_title} (ID: {page_id})") #type: ignore
        
        response_data = query_contextual_agent(f"""
                                               SYSTEM PROMPT: You are to give a score from 0 to 1 that represents how related the PAGE INFO is to anything V93K/ST8 & HOW UP TO DATE THE INFORMATION IS. ONLY return the number. No other text.
                                               -----
                                               PAGE INFO: Page Title: {page_title}, Page Content: {page_content}, Page Breadcrumbs: {page_breadcrumbs}""")
        
        parsed_response = parse_contextual_response(response_data) if response_data else None
        return parsed_response['message']['content'] if parsed_response else []

    # print(response_data['message']['content'])
        
agent_workflow(metadata) # type: ignore