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

def run_scraping_workflow(scraper):
    """Run the main scraping workflow after authentication."""
    print("\n📋 Scraping Options:")
    print("1. Single URL scraping - Extract content from individual pages")
    print("2. Hierarchical scraping - Navigate and extract from page hierarchies (RECOMMENDED)")
    print("3. Multiple URLs from file - Scrape URLs listed in a text file")
        
    choice = input("\nSelect scraping method (1-3): ").strip()
        
    if choice == '1':
        # Single URL scraping
        test_url = input("\nEnter WeShare URL to scrape: ").strip()
        if test_url:
            print(f"🚀 Initiating single URL scraping for: {test_url}")
            results = scraper.scrape_urls([test_url], "single_url_output")
            
            if results:
                print(f"✅ Successfully scraped: {results[0]['title']}")
                print(f"📁 Output directory: single_url_output/")
                print(f"📄 Files created:")
                print(f"   - HTML: {results[0].get('html_path', 'Not created')}")
                print(f"   - Markdown: {results[0].get('markdown_path', 'Not created')}")
                print(f"   - Metadata: single_url_output/metadata.json")
                
                # Show content size comparison
                if results[0].get('markdown_content'):
                    html_size = len(results[0].get('content', ''))
                    md_size = len(results[0].get('markdown_content', ''))
                    savings = ((html_size - md_size) / html_size * 100) if html_size > 0 else 0
                    print(f"📊 Token savings: {savings:.1f}% ({html_size:,} → {md_size:,} characters)")
            else:
                print("❌ Scraping failed - check URL accessibility")
        
    elif choice == '2':
        # Hierarchical scraping (RECOMMENDED)
        hierarchical_url = input("\nEnter WeShare hierarchical page URL: ").strip()
        if not hierarchical_url:
            print("❌ URL is required")
            return
            
        # Ask for output directory
        output_dir = input("Output directory name (default: hierarchical_output): ").strip()
        if not output_dir:
            output_dir = "hierarchical_output"
        
        print(f"🚀 Initiating hierarchical scraping from: {hierarchical_url}")
        print(f"📁 Output directory: {output_dir}")
        print("📢 This may take several minutes depending on the number of pages...")
        
        results = scraper.scrape_hierarchical_pages(hierarchical_url, output_dir)
        
        if results:
            print(f"\n✅ Successfully scraped {len(results)} pages from hierarchy!")
            print(f"📁 Output directory: {output_dir}/")
            
            # Show detailed statistics
            html_files = sum(1 for r in results if r.get('html_path'))
            md_files = sum(1 for r in results if r.get('markdown_path'))
            pages_with_breadcrumbs = sum(1 for r in results if r.get('breadcrumbs'))
            
            print(f"📊 Statistics:")
            print(f"   - Total pages: {len(results)}")
            print(f"   - HTML files: {html_files}")
            print(f"   - Markdown files: {md_files}")
            print(f"   - Pages with breadcrumbs: {pages_with_breadcrumbs}")
            
            # Calculate token savings
            total_html_size = sum(len(r.get('content', '')) for r in results)
            total_md_size = sum(len(r.get('markdown_content', '')) for r in results)
            if total_html_size > 0:
                savings = ((total_html_size - total_md_size) / total_html_size * 100)
                estimated_tokens_saved = (total_html_size - total_md_size) / 4
                print(f"   - Token savings: {savings:.1f}% (~{estimated_tokens_saved:,.0f} tokens)")
            
            print(f"\n📄 Key files created:")
            print(f"   - metadata.json (for validation pipeline)")
            print(f"   - scraping_summary.json (detailed report)")
            print(f"   - {html_files} HTML files")
            print(f"   - {md_files} Markdown files")
            
            print(f"\n🎯 Next steps:")
            print(f"   1. Review the metadata.json file")
            print(f"   2. Run validation: python validate_metadata.py {output_dir}/metadata.json")
            print(f"   3. Run the validation pipeline: python runnables/run_ctx_agent.py")
            print(f"   4. Check results in your database")
            
        else:
            print("❌ Hierarchical scraping failed - check page structure or permissions")
        
    elif choice == '3':
        # Multiple URLs from file
        file_path = input("\nEnter path to text file with URLs (one per line): ").strip()
        if not file_path or not os.path.exists(file_path):
            print("❌ File not found")
            return
        
        try:
            with open(file_path, 'r') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            if not urls:
                print("❌ No valid URLs found in file")
                return
            
            output_dir = input("Output directory name (default: multi_url_output): ").strip()
            if not output_dir:
                output_dir = "multi_url_output"
            
            print(f"🚀 Scraping {len(urls)} URLs from file...")
            results = scraper.scrape_urls(urls, output_dir)
            
            if results:
                print(f"✅ Successfully scraped {len(results)} out of {len(urls)} URLs")
                print(f"📁 Output directory: {output_dir}/")
                
                # Show statistics
                successful_pages = len(results)
                failed_pages = len(urls) - successful_pages
                
                print(f"📊 Results:")
                print(f"   - Successful: {successful_pages}")
                print(f"   - Failed: {failed_pages}")
                if failed_pages > 0:
                    print(f"   - Success rate: {(successful_pages/len(urls)*100):.1f}%")
            else:
                print("❌ No URLs were successfully scraped")
                
        except Exception as e:
            print(f"❌ Error reading file: {e}")
        
    else:
        print("❌ Invalid selection. Please choose 1, 2, or 3.")
        return
        
    # Session persistence
    scraper.save_session()
    print("\n💾 Session saved for future use")
    print("Next time you can use the existing session to skip authentication")

def test_authentication():
    """Test authentication and perform scraping operations with enhanced features."""
    
    # Credential collection
    print("Authentication required for WeShare access")
    email = os.getenv('ADVANTEST_EMAIL')
    password = os.getenv('ADVANTEST_PASSWORD')
    
    if not email or not password:
        print("❌ Email and password are required")
        print("Please set ADVANTEST_EMAIL and ADVANTEST_PASSWORD environment variables")
        return
    
    print("\nInitializing browser and attempting authentication...")
    print("📢 Note: The browser window will stay open for manual MFA completion if needed")
    
    with WeShareMSSOScraper(headless=False, timeout=60) as scraper:
        print("🔐 Connecting to Microsoft SSO...")
        
        if not scraper.login_microsoft_sso(email, password):
            print("❌ Authentication failed")
            print(f"Current URL: {scraper.driver.current_url}")
            print("Please verify credentials and complete any required MFA steps")
            
            # Give user option to manually complete authentication
            retry = input("\nWould you like to manually complete authentication and continue? (y/n): ").strip().lower()
            if retry == 'y':
                print("🔧 Please complete authentication manually in the browser window")
                print("Navigate to WeShare main page when done...")
                input("Press Enter when you've reached WeShare main page: ")
                
                # Check if we're now at WeShare
                if scraper.base_url in scraper.driver.current_url:
                    scraper.authenticated = True
                    print("✅ Manual authentication successful!")
                else:
                    print("❌ Still not at WeShare - exiting")
                    return
            else:
                return
        
        print("✅ Authentication successful")
        
        # Run the main scraping workflow
        run_scraping_workflow(scraper)

def test_with_existing_session():
    """Validate and test existing authentication session."""
    print("🔄 Loading existing authentication session...")
    
    with WeShareMSSOScraper(headless=False) as scraper:
        if not scraper.load_session():
            print("❌ Session validation failed - session may be expired")
            print("Please run full authentication")
            return
            
        print("✅ Session validated successfully")
        
        # Quick test options
        print("\n🧪 Session Test Options:")
        print("1. Test with a single URL")
        print("2. Skip test and proceed to main menu")
        
        test_choice = input("Choose option (1-2): ").strip()
        
        if test_choice == '1':
            test_url = input("\nEnter WeShare URL to validate session: ").strip()
            if test_url:
                print(f"🧪 Testing session with URL: {test_url}")
                results = scraper.scrape_urls([test_url], "session_test_output")
                if results:
                    print(f"✅ Session active - successfully scraped: {results[0]['title']}")
                    print(f"📁 Output saved to: session_test_output/")
                else:
                    print("❌ Session test failed - may need to re-authenticate")
                    return
        
        # Proceed to main scraping menu
        print("\n🚀 Proceeding to scraping options...")
        run_scraping_workflow(scraper)

def show_help():
    """Show help information about the scraper."""
    print("\n" + "="*60)
    print("WeShare Content Scraper - Help")
    print("="*60)
    print("This tool extracts content from Advantest WeShare platform")
    print()
    print("📋 Features:")
    print("• Microsoft SSO authentication")
    print("• Hierarchical page tree navigation")
    print("• HTML to Markdown conversion")
    print("• Metadata generation for validation pipeline")
    print("• Session persistence")
    print("• Token usage optimization")
    print()
    print("📁 Output files:")
    print("• metadata.json - For use with validation pipeline")
    print("• scraping_summary.json - Detailed scraping report")
    print("• *.html - Original page content")
    print("• *.md - Markdown converted content")
    print()
    print("🔧 Environment Variables Required:")
    print("• ADVANTEST_EMAIL - Your Advantest email")
    print("• ADVANTEST_PASSWORD - Your password")
    print()
    print("🎯 Recommended workflow:")
    print("1. Use hierarchical scraping for page trees")
    print("2. Review metadata.json")
    print("3. Run validation: python runnables/run_ctx_agent.py")
    print("4. Check database results")
    print("="*60)

if __name__ == "__main__":
    print("=" * 60)
    print("WeShare Content Scraper - Enhanced Version")
    print("=" * 60)
    
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        show_help()
        sys.exit(0)
    
    # Check for existing session
    if os.path.exists("weshare_session.json"):
        print("🔄 Existing authentication session detected")
        use_session = input("Use existing session? (y/n): ").strip().lower()
        
        if use_session == 'y':
            test_with_existing_session()
        else:
            print("\n🔐 Proceeding with fresh authentication...")
            test_authentication()
    else:
        print("🔐 No existing session found - authentication required")
        test_authentication()
    
    print("\n✨ Scraping completed! Check your output directory for results.")