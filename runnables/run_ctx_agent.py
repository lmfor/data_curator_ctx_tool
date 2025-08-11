import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

'''
> ZenML
> Connect md
> Retriev context from ctxl agent + look @ other metrics
> Categorize 
> Modular calls / TDC API
'''

# Add src directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from workflow.ctx_agent import query_contextual_agent, parse_contextual_response
from db.database import DatabaseManager, db_manager  # Import the global instance
from db.models import ValidatedURL

# Configuration
RELEVANCE_THRESHOLD = 0.80
CURRENCY_THRESHOLD = 1.0
METADATA_PATH = 'hierarchical_output/metadata.json'


class ContextualValidator:
    """Handles validation of pages using contextual agent and database storage."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Initialize validator with database connection."""
        # Use the global db_manager instance if none provided
        self.db_manager = db_manager or globals()['db_manager']
        self.metadata = self._load_metadata()
        
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
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA256 hash of content for change detection."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _build_agent_prompt(self, page: Dict[str, Any]) -> str:
        """Build the prompt for the contextual agent."""
        page_title = page.get('title', '')
        page_content = page.get('content', '')
        page_breadcrumbs = page.get('breadcrumbs', [])
        page_date = page.get('formatted_date', '')
        
        return f"""
        SYSTEM PROMPT:
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
        Page Date: {page_date}
        """
    
    def _parse_agent_response(self, response_data: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """Parse the contextual agent response to extract scores."""
        try:
            parsed_response = parse_contextual_response(response_data) if response_data else None
            if not parsed_response:
                return None, None
                
            json_content = parsed_response.get('message', {}).get('content', '')
            
            # Clean up the JSON string if needed (handle code block formatting)
            if json_content.startswith('```'):
                json_content = json_content.strip('```json\n').strip('```')
            
            data = json.loads(json_content)
            return data.get("relevance_score"), data.get("currency_score")
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Error parsing agent response: {e}")
            return None, None
    
    def _save_to_database(self, page: Dict[str, Any], relevance_score: float, currency_score: float) -> bool:
        """Save validated URL to database."""
        try:
            # Prepare data for database
            url = page.get('url', '')
            if not url:
                print(f"Warning: No URL found for page {page.get('title', 'Unknown')}")
                return False
                
            title = page.get('title', '')
            content = page.get('content', '')
            content_hash = self._generate_content_hash(content) if content else None
            
            # Parse date if available
            last_modified = None
            if page.get('formatted_date'):
                try:
                    # Adjust date parsing format as needed (MM/DD/YY)
                    last_modified = datetime.strptime(page['formatted_date'], '%m/%d/%y')
                except ValueError:
                    print(f"Warning: Could not parse date {page.get('formatted_date')}")
            
            # Prepare metadata
            page_metadata = {
                'id': page.get('id'),
                'breadcrumbs': page.get('breadcrumbs', []),
                'original_date': page.get('formatted_date'),
            }
            
            # Use the add_validated_url method from DatabaseManager
            result = self.db_manager.add_validated_url(
                url=url,
                title=title,
                content_hash=content_hash, #type: ignore
                last_modified=last_modified,#type: ignore
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
                        existing.content_hash = content_hash #type: ignore
                        existing.last_modified = last_modified #type: ignore
                        existing.ctx_relevance_score = relevance_score #type: ignore
                        existing.ctx_currency_score = currency_score #type: ignore
                        existing.validation_timestamp = datetime.now() #type: ignore
                        existing.page_metadata = page_metadata #type: ignore
                        print(f"  💾 Updated existing URL in database: {title}")
                        return True
                print(f"  ⚠️  Could not save URL to database: {title}")
                return False
                
        except Exception as e:
            print(f"Error saving to database: {e}")
            return False
    
    def validate_all_pages(self) -> Dict[str, Any]:
        """Process all pages in metadata and validate them."""
        results = {
            'processed': 0,
            'validated': 0,
            'saved': 0,
            'errors': 0,
            'details': []
        }
        
        for page in self.metadata:
            page_title = page.get('title', 'Unknown')
            page_id = page.get('id', 'Unknown')
            
            print(f"\nProcessing page: {page_title} (ID: {page_id})")
            results['processed'] += 1
            
            try:
                # Query contextual agent
                prompt = self._build_agent_prompt(page)
                response_data = query_contextual_agent(prompt)
                
                # Parse response
                relevance_score, currency_score = self._parse_agent_response(response_data) #type: ignore
                
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
                        print(f"  💾 Successfully saved to database")
                    else:
                        print(f"  ❌ Failed to save to database")
                        results['errors'] += 1
                else:
                    print(f"  ❌ Page does not meet validation criteria")
                
                # Store details
                results['details'].append({
                    'title': page_title,
                    'id': page_id,
                    'relevance_score': relevance_score,
                    'currency_score': currency_score,
                    'validated': relevance_score >= RELEVANCE_THRESHOLD and currency_score >= CURRENCY_THRESHOLD
                })
                
            except Exception as e:
                print(f"  ❌ Error processing page: {e}")
                results['errors'] += 1
                continue
        
        return results
    
    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print a summary of the validation results."""
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"Total pages processed: {results['processed']}")
        print(f"Pages validated: {results['validated']}")
        print(f"Pages saved to database: {results['saved']}")
        print(f"Errors encountered: {results['errors']}")
        print(f"Validation rate: {results['validated']/results['processed']*100:.1f}%" if results['processed'] > 0 else "N/A")
        print("="*60)


def main():
    """Main execution function."""
    print("Starting Contextual Validation Process...")
    print(f"Relevance Threshold: {RELEVANCE_THRESHOLD}")
    print(f"Currency Threshold: {CURRENCY_THRESHOLD}")
    print("-"*60)
    
    # Test database connection first
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
    
    # Run validation
    results = validator.validate_all_pages()
    
    # Print summary
    validator.print_summary(results)
    
    # Optionally save detailed results to file
    with open('validation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to validation_results.json")


if __name__ == "__main__":
    main()