import os
import sys
import json
import hashlib
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

# Add src directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from workflow.ctx_agent import query_contextual_agent, parse_contextual_response
from db.database import DatabaseManager, db_manager
from db.models import ValidatedURL

# Configuration
RELEVANCE_THRESHOLD = 0.80
CURRENCY_THRESHOLD = 1.0
METADATA_PATH = 'hierarchical_output/metadata.json'

# Rate limiting configuration
REQUEST_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 3
BACKOFF_FACTOR = 2  # exponential backoff multiplier


class ContextualValidator:
    """Handles validation of pages using contextual agent and database storage."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Initialize validator with database connection."""
        self.db_manager = db_manager or globals()['db_manager']
        self.metadata = self._load_metadata()
        self.last_request_time = 0
        
    def _load_metadata(self) -> List[Dict[str, Any]]:
        """Load metadata from JSON file."""
        try:
            with open(METADATA_PATH, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Metadata file not found at {METADATA_PATH}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing metadata JSON: {e}")
            return []
    
    def _rate_limit_delay(self):
        """Ensure we don't exceed rate limits."""
        time_since_last = time.time() - self.last_request_time
        if time_since_last < REQUEST_DELAY:
            sleep_time = REQUEST_DELAY - time_since_last
            print(f"  ⏳ Rate limiting: sleeping for {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _query_with_retry(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Query contextual agent with retry logic for rate limiting."""
        for attempt in range(MAX_RETRIES):
            try:
                # Apply rate limiting
                self._rate_limit_delay()
                
                # Make the request using the updated function
                response_data = query_contextual_agent(prompt)
                return response_data
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit exceeded
                    wait_time = REQUEST_DELAY * (BACKOFF_FACTOR ** attempt)
                    print(f"  ⚠️  Rate limited (attempt {attempt + 1}/{MAX_RETRIES}). Waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  ❌ HTTP Error {e.response.status_code}: {e}")
                    return None
            except Exception as e:
                print(f"  ❌ Unexpected error: {e}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = REQUEST_DELAY * (BACKOFF_FACTOR ** attempt)
                    print(f"  ⏳ Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                return None
        
        print(f"  ❌ Failed after {MAX_RETRIES} attempts")
        return None
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA256 hash of content for change detection."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _build_agent_prompt(self, page: Dict[str, Any]) -> str:
        """Build the prompt for the contextual agent."""
        page_title = page.get('title', '')
        page_content = page.get('content', '')
        page_breadcrumbs = page.get('breadcrumbs', '')
        page_date = page.get('formatted_date', '')
        
        # Ensure content is not too long (truncate if necessary)
        max_content_length = 10000  # Adjust based on your needs
        if len(page_content) > max_content_length:
            page_content = page_content[:max_content_length] + "... [truncated]"
        
        return f"""SYSTEM PROMPT:
You are to give a score from 0 to 1 for the following. Make sure your score is as accurate as you can make it to be.

1. How relevant the PAGE INFO is to anything V93/SmarTest8
2. How up to date the information is.

Naturally, if the content you are prompted with is newer/more current than your knowledge cutoff date, then the currency score should be 1.0.

ONLY RETURN: You will return a JSON OBJECT with the following structure:
{{
    "relevance_score": <float>,
    "currency_score": <float>
}}

NOTES: The date will be given to you in the format of MM/DD/YY. Do not return any other information, just the JSON object.
-----
PAGE INFO/PROMPT: 
Page Title: {page_title}
Page Content: {page_content}
Page Breadcrumbs: {page_breadcrumbs}
Page Date: {page_date}"""
    
    def _parse_agent_response(self, response_data: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """Parse the contextual agent response to extract scores."""
        try:
            if not response_data:
                print("  ⚠️  No response data to parse")
                return None, None
            
            # The response structure from Contextual AI typically has the message in 'message' field
            message_content = None
            
            # Try different possible response structures
            if 'message' in response_data:
                message_content = response_data['message']
            elif 'content' in response_data:
                message_content = response_data['content']
            elif 'response' in response_data:
                message_content = response_data['response']
            else:
                # If the response IS the message (string response)
                if isinstance(response_data, str):
                    message_content = response_data
                else:
                    print(f"  ⚠️  Unexpected response structure: {list(response_data.keys())}")
                    return None, None
            
            if not message_content:
                print("  ⚠️  No message content in response")
                return None, None
            
            # Clean up the JSON content if it has markdown code blocks
            json_content = message_content
            if isinstance(json_content, str):
                # Remove markdown code blocks if present
                if '```json' in json_content:
                    json_content = json_content.split('```json')[1].split('```')[0].strip()
                elif '```' in json_content:
                    json_content = json_content.split('```')[1].split('```')[0].strip()
                
                # Parse the JSON
                data = json.loads(json_content)
            else:
                # If it's already a dict
                data = json_content
            
            relevance_score = data.get("relevance_score")
            currency_score = data.get("currency_score")
            
            # Validate scores are floats between 0 and 1
            if relevance_score is not None:
                relevance_score = float(relevance_score)
                if not 0 <= relevance_score <= 1:
                    print(f"  ⚠️  Invalid relevance score: {relevance_score}")
                    relevance_score = None
            
            if currency_score is not None:
                currency_score = float(currency_score)
                if not 0 <= currency_score <= 1:
                    print(f"  ⚠️  Invalid currency score: {currency_score}")
                    currency_score = None
            
            return relevance_score, currency_score
            
        except json.JSONDecodeError as e:
            print(f"  ❌ JSON decode error: {e}")
            if message_content:
                print(f"  📝 Raw message content: {message_content[:200]}...")
            return None, None
        except (KeyError, TypeError, ValueError) as e:
            print(f"  ❌ Error parsing agent response: {e}")
            return None, None
    
    def _save_to_database(self, page: Dict[str, Any], relevance_score: float, currency_score: float) -> bool:
        """Save validated URL to database."""
        try:
            # Prepare data for database
            url = page.get('url', '')
            if not url:
                print(f"  ⚠️  No URL found for page {page.get('title', 'Unknown')}")
                return False
                
            title = page.get('title', '')
            content = page.get('content', '')
            content_hash = self._generate_content_hash(content) if content else None
            
            # Parse date if available
            last_modified = None
            if page.get('formatted_date'):
                try:
                    last_modified = datetime.strptime(page['formatted_date'], '%m/%d/%y')
                except ValueError:
                    print(f"  ⚠️  Could not parse date {page.get('formatted_date')}")
            
            # Prepare metadata
            page_metadata = {
                'id': page.get('id'),
                'breadcrumbs': page.get('breadcrumbs', ''),
                'original_date': page.get('formatted_date'),
            }
            
            # Use the add_validated_url method from DatabaseManager
            result = self.db_manager.add_validated_url(
                url=url,
                title=title,
                content_hash=content_hash,
                last_modified=last_modified,
                ctx_relevance_score=relevance_score,
                ctx_currency_score=currency_score,
                page_metadata=page_metadata
            )
            
            if result:
                print(f"  💾 Successfully saved to database: {title}")
                return True
            else:
                # URL might already exist, try to update it
                with self.db_manager.get_db_session() as session:
                    existing = session.query(ValidatedURL).filter(ValidatedURL.url == url).first()
                    if existing:
                        # Update existing record
                        existing.title = title
                        existing.content_hash = content_hash
                        existing.last_modified = last_modified
                        existing.ctx_relevance_score = relevance_score
                        existing.ctx_currency_score = currency_score
                        existing.validation_timestamp = datetime.now()
                        existing.page_metadata = page_metadata
                        print(f"  💾 Updated existing URL in database: {title}")
                        return True
                print(f"  ⚠️  Could not save URL to database: {title}")
                return False
                
        except Exception as e:
            print(f"  ❌ Error saving to database: {e}")
            return False
    
    def validate_all_pages(self, start_index: int = 0, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """Process all pages in metadata and validate them with resumption support."""
        results = {
            'processed': 0,
            'validated': 0,
            'saved': 0,
            'errors': 0,
            'skipped': start_index,
            'details': []
        }
        
        # Determine which pages to process
        pages_to_process = self.metadata[start_index:]
        if batch_size:
            pages_to_process = pages_to_process[:batch_size]
        
        total_pages = len(pages_to_process)
        print(f"Processing {total_pages} pages (starting from index {start_index})")
        
        for i, page in enumerate(pages_to_process):
            page_title = page.get('title', 'Unknown')
            page_id = page.get('id', 'Unknown')
            current_index = start_index + i
            
            print(f"\n[{current_index + 1}/{len(self.metadata)}] Processing: {page_title} (ID: {page_id})")
            results['processed'] += 1
            
            try:
                # Query contextual agent with retry logic
                prompt = self._build_agent_prompt(page)
                response_data = self._query_with_retry(prompt)
                # print(response_data['message']['content']) #type: ignore
                '''
                RETRIEVAL CONTENTS:
                !!! Essentially what documents the agent used to generate the response. Will use these in the future in the prompt !!!
                
                print(response_data['retrieval_contents']) #type: ignore
                '''
                if response_data is None:
                    print(f"  ❌ Failed to get response for page: {page_title}")
                    results['errors'] += 1
                    continue
                
                # Parse response
                
                relevance_score, currency_score = self._parse_agent_response(response_data['message']['content'])  # type: ignore
                
                if relevance_score is None or currency_score is None:
                    print(f"  ⚠️  Failed to get scores for page: {page_title}")
                    results['errors'] += 1
                    continue
                
                print(f"  📊 Scores - Relevance: {relevance_score:.2f}, Currency: {currency_score:.2f}")
                
                # Check if meets thresholds
                if relevance_score >= RELEVANCE_THRESHOLD and currency_score >= CURRENCY_THRESHOLD:
                    results['validated'] += 1
                    print(f"  ✅ Page meets validation criteria!")
                    
                    # Save to database
                    if self._save_to_database(page, relevance_score, currency_score):
                        results['saved'] += 1
                    else:
                        results['errors'] += 1
                else:
                    print(f"  ❌ Page does not meet validation criteria")
                
                # Store details
                results['details'].append({
                    'index': current_index,
                    'title': page_title,
                    'id': page_id,
                    'relevance_score': relevance_score,
                    'currency_score': currency_score,
                    'validated': relevance_score >= RELEVANCE_THRESHOLD and currency_score >= CURRENCY_THRESHOLD
                })
                
                # Save progress periodically
                if (i + 1) % 10 == 0:
                    self._save_progress(results, current_index + 1)
                
            except KeyboardInterrupt:
                print(f"\n⚠️  Interrupted by user. Processed {results['processed']} pages.")
                print(f"To resume, use start_index={current_index}")
                self._save_progress(results, current_index)
                break
            except Exception as e:
                print(f"  ❌ Unexpected error processing page: {e}")
                results['errors'] += 1
                continue
        
        return results
    
    def _save_progress(self, results: Dict[str, Any], next_index: int):
        """Save progress to file for resumption."""
        progress = {
            'next_index': next_index,
            'timestamp': datetime.now().isoformat(),
            'results': results
        }
        with open('validation_progress.json', 'w') as f:
            json.dump(progress, f, indent=2)
        print(f"  💾 Progress saved. Resume with start_index={next_index}")
    
    def load_progress(self) -> Optional[int]:
        """Load progress from file."""
        try:
            with open('validation_progress.json', 'r') as f:
                progress = json.load(f)
                return progress.get('next_index', 0)
        except FileNotFoundError:
            return None
    
    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print a summary of the validation results."""
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"Total pages processed: {results['processed']}")
        print(f"Pages skipped (resumed): {results['skipped']}")
        print(f"Pages validated: {results['validated']}")
        print(f"Pages saved to database: {results['saved']}")
        print(f"Errors encountered: {results['errors']}")
        if results['processed'] > 0:
            print(f"Validation rate: {results['validated']/results['processed']*100:.1f}%")
        print("="*60)


def test_single_page():
    """Test function to validate API connection with a simple query."""
    print("\n" + "="*60)
    print("TESTING CONTEXTUAL AGENT CONNECTION")
    print("="*60)
    
    test_prompt = """Return this exact JSON:
{
    "relevance_score": 0.5,
    "currency_score": 0.5
}"""
    
    print("Sending test query...")
    try:
        from workflow.ctx_agent import query_contextual_agent
        response = query_contextual_agent(test_prompt)
        
        if response:
            print("✅ Successfully connected to Contextual Agent!")
            print(f"Response keys: {list(response.keys())}")
            print(response['message']['content'])
            #if 'message' in response:
            #    print(f"Message content: {response['message'][:200]}...")
            return True
        else:
            print("❌ Failed to get response from agent")
            return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


def main():
    """Main execution function."""
    print("Starting Contextual Validation Process...")
    print(f"Relevance Threshold: {RELEVANCE_THRESHOLD}")
    print(f"Currency Threshold: {CURRENCY_THRESHOLD}")
    print(f"Request Delay: {REQUEST_DELAY}s")
    print("-"*60)
    
    # Test API connection first
    if not test_single_page():
        print("\n⚠️  API test failed. Please check your configuration:")
        print("  1. Verify CONTEXTUAL_API_KEY_PERSONAL is set correctly")
        print("  2. Verify CODEGENIE_A_ID is set correctly")
        print("  3. Check that the agent exists and is accessible")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Test database connection
    if not db_manager.test_connection():
        print("❌ Failed to connect to database. Please check your DATABASE_URL.")
        return
    
    print("✅ Database connection successful")
    
    # Initialize validator using the global db_manager instance
    validator = ContextualValidator(db_manager=db_manager)
    
    if not validator.metadata:
        print("No metadata to process. Exiting.")
        return
    
    print(f"Found {len(validator.metadata)} pages to process")
    
    # Check for existing progress
    start_index = 0
    saved_progress = validator.load_progress()
    if saved_progress is not None:
        response = input(f"Found saved progress at index {saved_progress}. Resume? (y/n): ")
        if response.lower() == 'y':
            start_index = saved_progress
    
    # Run validation
    try:
        results = validator.validate_all_pages(start_index=start_index)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Print summary
    validator.print_summary(results)
    
    # Save detailed results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_filename = f'validation_results_{timestamp}.json'
    with open(results_filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to {results_filename}")


if __name__ == "__main__":
    main()