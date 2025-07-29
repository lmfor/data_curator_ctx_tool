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

def call_contextual_agent(metadata: Dict[str, Any]) -> Dict[Any, Any]: # type: ignore
    # parsed_response = parse_contextual_response(metadata) # type: ignore
    # print(parsed_response['content'])
    # print(metadata[0]['title']) #type: ignore
    
    
    # Multiquery (Lots of prompts be careful.)
    for page in metadata:
        page_title = page['title'] #type: ignore
        page_id = page['id'] #type: ignore
        page_date = page['formatted_date'] if 'formatted_date' in page else '' #type: ignore
        page_content = page['content'] if 'content' in page else '' #type: ignore
        page_breadcrumbs = page['breadcrumbs'] if 'breadcrumbs' in page else [] #type: ignore
        # print(f"Processing page: {page_title} (ID: {page_id})") #type: ignore
        
        response_data = query_contextual_agent(f"""
                                               
                                               SYSTEM PROMPT:
                                               You are to give a score from 0 to 1 for the following. Make sure your score is as accurate as you can make it to be.
                                               
                                                  1. How relevant the PAGE INFO is to anything V93/St8
                                                  2. How up to date the information is.
                                                  
                                                  
                                                Naturally, if the content you are prompted with is newer/more current than your knowledge cutoff date, then the currency score should be 1.0.
                                               
                                                ONLY REUTRN: You will return a JSON OBJECT with the following structure:
                                                  {{
                                                    "relevance_score": <float>,
                                                    "currency_score": <float>
                                                    }}
                                                .
                                               NOTES: The date will be given to you in the format of MM/DD/YY. Do not return any other information, just the JSON object.
                                               -----
                                               PAGE INFO/PROMPT: Page Title: {page_title}, 
                                                                 Page Content: {page_content}, 
                                                                 Page Breadcrumbs: {page_breadcrumbs}, 
                                                                 Page Date: {page_date}""")
        
        ### LOGIC TO HANDLE RESPONSE & INSERT INTO DB IF NEEDED ###
        
        parsed_response = parse_contextual_response(response_data) if response_data else None
        return {page_id,parsed_response['message']['content']} if parsed_response else {} #type: ignore

    # print(response_data['message']['content'])
        
call_contextual_agent(metadata) # type: ignore