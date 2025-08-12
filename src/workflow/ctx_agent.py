import requests
import json
import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "https://api.app.contextual.ai/v1"

def query_contextual_agent(prompt: str, conversation_history: Optional[List[Dict]] = None) -> Optional[Dict[str, Any]]:
    """
    Query the contextual agent with proper message structure.
    
    Args:
        prompt: The user's message/prompt
        conversation_history: Optional list of previous messages in the conversation
    
    Returns:
        Response data from the API or None if error
    """
    
    # Get API key and agent ID from environment
    api_key = os.getenv("CONTEXTUAL_API_KEY_PERSONAL")
    agent_id = os.getenv("CODEGENIE_A_ID")
    
    if not api_key:
        raise ValueError("CONTEXTUAL_API_KEY_PERSONAL environment variable not set")
    
    if not agent_id:
        raise ValueError("CODEGENIE_A_ID environment variable not set")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Build messages array - REQUIRED format for the API
    messages = conversation_history if conversation_history else []
    
    # Add the current user message
    messages.append({
        "role": "user",
        "content": prompt
    })
    
    # Build the proper payload structure according to API docs
    payload = {
        "messages": messages,  # REQUIRED: array of message objects
        "stream": False,       # We want non-streamed responses
        # Optional: Add these if needed
        # "include_retrieval_content_text": False,
        # "retrievals_only": False,
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/agents/{agent_id}/query",
            headers=headers,
            json=payload,
            timeout=30  # Add timeout
        )
        
        # Log the status and response for debugging
        print(f"  📡 API Response: {response.status_code}")
        
        # Debug logging for 422 errors
        if response.status_code == 422:
            print("  ❌ Request validation failed. Details:")
            try:
                error_detail = response.json()
                print(f"  Error details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"  Raw response: {response.text}")
            return None
        
        # Handle different HTTP status codes
        if response.status_code == 429:
            # Rate limit exceeded - let the caller handle retry logic
            error_detail = response.json() if response.content else {"detail": "Rate limit exceeded"}
            print(f"  ⚠️ Rate limit exceeded: {error_detail}")
            response.raise_for_status()  # This will raise an HTTPError
            
        elif response.status_code == 401:
            print("  ❌ Authentication failed. Check your CONTEXTUAL_API_KEY_PERSONAL.")
            return None
            
        elif response.status_code == 404:
            print("  ❌ Agent not found. Check your CODEGENIE_A_ID.")
            return None
            
        elif response.status_code >= 500:
            print(f"  ❌ Server error ({response.status_code}). Try again later.")
            return None
            
        # Raise for other HTTP errors
        response.raise_for_status()
        
        # Parse JSON response
        return response.json()
        
    except requests.exceptions.Timeout:
        print("  ❌ Request timed out")
        return None
        
    except requests.exceptions.ConnectionError:
        print("  ❌ Connection error")
        return None
        
    except requests.exceptions.HTTPError as e:
        # Re-raise HTTP errors so caller can handle rate limiting
        if e.response.status_code == 429:
            raise e
        print(f"  ❌ HTTP Error: {e}")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request error: {e}")
        return None
        
    except json.JSONDecodeError:
        print("  ❌ Invalid JSON response")
        return None


def parse_contextual_response(response_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse the contextual agent response.
    
    The response structure typically includes:
    - message: The generated response
    - retrievals: Any retrieved context (if applicable)
    - metadata: Additional response metadata
    """
    try:
        if not response_data:
            return None
        
        # The API response structure may vary, but typically includes:
        # - A message or content field with the actual response
        # - Potentially retrieval information if RAG is used
        
        # Return the full response for now - adjust based on actual API response structure
        return response_data
        
    except (KeyError, TypeError) as e:
        print(f"  ❌ Error parsing contextual response: {e}")
        return None


def test_agent_connection(test_prompt: str = "Hello, are you working?") -> bool:
    """
    Test the connection to the contextual agent.
    
    Args:
        test_prompt: Simple test message to send
    
    Returns:
        True if connection successful, False otherwise
    """
    print("🧪 Testing Contextual Agent connection...")
    
    try:
        response = query_contextual_agent(test_prompt)
        if response:
            print("  ✅ Agent connection successful!")
            print(response)
            print(f"  Response preview: {str(response)[:200]}...")
            return True
        else:
            print("  ❌ Agent connection failed - no response received")
            return False
    except Exception as e:
        print(f"  ❌ Agent connection failed with error: {e}")
        return False


# Backward compatibility - keep the old function signature working
def query_contextual_agent_simple(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Simple wrapper for backward compatibility.
    Converts a simple string prompt to the required message format.
    """
    return query_contextual_agent(prompt)