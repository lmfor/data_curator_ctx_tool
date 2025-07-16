import sys
import os
from pathlib import Path
from dotenv import load_dotenv
# Load environment variables
load_dotenv()

# Add src directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from workflow.sso_weshare_scraper import WeShareMSSOScraper

def test_authentication():
    """Test authentication and perform scraping operations."""
    
    # Credential collection
    print("Authentication required for WeShare access")
    # email = input("Advantest email: ").strip()
    # password = input("Password: ").strip()
    email = os.getenv('ADVANTEST_EMAIL')
    password = os.getenv('ADVANTEST_PASSWORD')
    
    if not email or not password:
        print("[X] Email and password are required")
        return
    
    print("\nInitializing browser and attempting authentication...")
    
    with WeShareMSSOScraper(headless=False, timeout=60) as scraper:
        print("Connecting to Microsoft SSO...")
        
        if not scraper.login_microsoft_sso(email, password):
            print("[X] Authentication failed")
            print(f"Current URL: {scraper.driver.current_url}") #type: ignore
            print("Please verify credentials and complete any required MFA steps")
            return
        print("! Authentication successful")
        
        print("\nScraping Options:")
        print("1. Single URL scraping - Extract content from individual pages")
        print("2. Hierarchical scraping - Navigate and extract from page hierarchies")
            
        choice = input("\nSelect scraping method (1 or 2): ").strip()
            
        if choice == '1':
            # Single URL scraping
            test_url = input("\nEnter WeShare URL to scrape: ").strip()
            if test_url:
                print(f"Initiating single URL scraping for: {test_url}")
                results = scraper.scrape_urls([test_url], "single_url_output")
                if results:
                    print(f"! Successfully scraped: {results[0]['title']}")
                    print(f"Output directory: single_url_output/")
                    if 'markdown_path' in results[0]:
                        print(f"Markdown file: {results[0]['markdown_path']}")
                    else:
                        print("[X] Scraping failed - check URL accessibility")
            
        elif choice == '2':
            # Hierarchical scraping
            hierarchical_url = input("\nEnter WeShare hierarchical page URL: ").strip()
            if hierarchical_url:
                print(f"Initiating hierarchical scraping from: {hierarchical_url}")
                results = scraper.scrape_hierarchical_pages(hierarchical_url, "hierarchical_output")
                if results:
                    print(f"! Successfully scraped {len(results)} pages from hierarchy")
                    print(f"Output directory: hierarchical_output/")
                    print(f"Total files: {len(results)} HTML + {sum(1 for r in results if 'markdown_path' in r)} Markdown")
                else:
                    print("[X] Hierarchical scraping failed - check page structure")
            
        else:
            print("[X] Invalid selection. Please choose 1 or 2.")
            
            # Session persistence
            scraper.save_session()
        print("\n! Session saved for future use")
        print("Next time you can use the existing session to skip authentication")

def test_with_existing_session():
    """Validate and test existing authentication session."""
    print("Loading existing authentication session...")
    
    with WeShareMSSOScraper(headless=False) as scraper:
        if not scraper.load_session():
            print("[X] Session validation failed - session may be expired")
            print("Please run full authentication")
            return
            
        print("! Session validated successfully")
        
        # Quick test
        test_url = input("\nEnter WeShare URL to validate session: ").strip()
        if test_url:
            print(f"Testing session with URL: {test_url}")
            results = scraper.scrape_urls([test_url], "session_test_output")
            if results:
                print(f"! Session active - successfully scraped: {results[0]['title']}")
                print(f"Output saved to: session_test_output/")
            else:
                print("[X] Session test failed - may need to re-authenticate")
        else:
            print("No test URL provided - session validation complete")

if __name__ == "__main__":
    print("=" * 60)
    print("WeShare Content Scraper")
    print("=" * 60)
    print("This tool extracts content from Advantest WeShare platform")
    print()
    
    # Check for existing session
    if os.path.exists("weshare_session.json"):
        print("Existing authentication session detected")
        use_session = input("Use existing session? (y/n): ").strip().lower()
        
        if use_session == 'y':
            test_with_existing_session()
        else:
            print("\nProceeding with fresh authentication...")
            test_authentication()
    else:
        print("No existing session found - authentication required")
        test_authentication()