import os
import time
import json
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

from .html_to_markdown import convert_html_file, html_to_markdown


class WeShareMSSOScraper:
    def __init__(self, headless: bool = True, timeout: int = 60):
        self.base_url = "https://weshare.advantest.com"
        self.timeout = timeout
        self.driver = None
        self.authenticated = False
        self.current_id = 0
        
        # Setup Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(60)
        self.wait = WebDriverWait(self.driver, timeout)

    def login_microsoft_sso(self, email: str, password: str) -> bool:
        try:
            print("Navigating to WeShare...")
            self.driver.get(self.base_url)
            
            # Look for Microsoft SSO login button/link or direct redirect
            try:
                # Wait for Microsoft login page (might redirect automatically)
                print("Waiting for Microsoft login page...")
                self.wait.until(
                    lambda driver: "login.microsoftonline.com" in driver.current_url or 
                                  "login.microsoft.com" in driver.current_url or
                                  "account.microsoft.com" in driver.current_url
                )
            except TimeoutException:
                sso_selectors = [
                    "a[href*='microsoft']",
                    "a[href*='oauth']", 
                    "a[href*='sso']",
                    "//button[contains(text(), 'Microsoft')] | //a[contains(text(), 'Microsoft')] | //button[contains(text(), 'Sign in with Microsoft')] | //a[contains(text(), 'Sign in with Microsoft')]"
                ]
                
                sso_button = None
                for selector in sso_selectors:
                    try:
                        if selector.startswith("//"):
                            elements = self.driver.find_elements(By.XPATH, selector)
                            if elements:
                                sso_button = elements[0]
                                break
                        else:
                            sso_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            break
                    except NoSuchElementException:
                        continue
                
                if sso_button:
                    print("Clicking Microsoft SSO login...")
                    sso_button.click()
                    self.wait.until(
                        lambda driver: "login.microsoftonline.com" in driver.current_url or 
                                      "login.microsoft.com" in driver.current_url
                    )
                else:
                    print("Could not find SSO login button, assuming auto-redirect...")
            
            print("Entering email...")
            username_field = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="i0116"]'))
            )
            username_field.clear()
            username_field.send_keys(email)
            
            # Click Next button - wait for it to be clickable to avoid stale reference
            print("Clicking Next button...")
            next_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="idSIButton9"]'))
            )
            next_button.click()
            
            # Wait for password page to load and enter password
            print("Waiting for password page...")
            password_field = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="i0118"]'))
            )
            print("Entering password...")
            password_field.clear()
            password_field.send_keys(password)
            
            # Click Sign in button - wait for it to be clickable
            print("Clicking Sign in button...")
            signin_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="idSIButton9"]'))
            )
            signin_button.click()
            
            # Handle potential MFA or "Stay signed in?" prompts
            print("Handling post-login prompts...")
            max_attempts = 3  # Reduced from 5 to avoid getting stuck
            
            for attempt in range(max_attempts):
                try:
                    time.sleep(3)  # Give page time to load
                    current_url = self.driver.current_url
                    
                    # Check if we're back at WeShare
                    if self.base_url in current_url and "login" not in current_url.lower():
                        print("✅ Successfully redirected to WeShare!")
                        self.authenticated = True
                        return True
                    
                    print(f"  🔍 Current URL: {current_url}")
                    
                    # Check for "Stay signed in?" prompt
                    try:
                        # Look for the text content to determine what button this is
                        stay_button = self.driver.find_element(By.XPATH, '//*[@id="idSIButton9"]')
                        button_text = stay_button.get_attribute("value") or stay_button.text
                        
                        if button_text and ("yes" in button_text.lower() or "stay" in button_text.lower()):
                            stay_button.click()
                            print("✅ Clicked 'Stay signed in'")
                            time.sleep(2)
                            continue
                    except (NoSuchElementException, TimeoutException):
                        pass
                    
                    # Check for MFA prompts
                    current_url_lower = current_url.lower()
                    if any(keyword in current_url_lower for keyword in ["mfa", "authenticator", "verify", "approval"]):
                        print("🔐 MFA/Approval prompt detected. Please complete it in the browser...")
                        print("⏰ Waiting up to 60 seconds for completion...")
                        
                        # Wait for user to complete MFA/approval
                        try:
                            mfa_wait = WebDriverWait(self.driver, 60)  # 1 minute
                            mfa_wait.until(
                                lambda driver: self.base_url in driver.current_url and 
                                              "login" not in driver.current_url.lower()
                            )
                            print("✅ MFA/Approval completed successfully!")
                            self.authenticated = True
                            return True
                        except TimeoutException:
                            print("⏰ Timeout waiting for MFA/approval completion")
                            # Don't return False yet, check if user wants to continue manually
                            break
                    
                    # If we're still here after the attempt, continue to next iteration
                    if attempt < max_attempts - 1:
                        print(f"  ⏳ Attempt {attempt + 1}: Still processing authentication...")
                    
                except Exception as e:
                    print(f"  ⚠️  Error in attempt {attempt + 1}: {e}")
                    if attempt == max_attempts - 1:
                        break
            
            # If we get here, automatic authentication didn't complete
            print("\n🔧 Automatic authentication flow didn't complete successfully")
            print(f"Current URL: {self.driver.current_url}")
            
            # Check if user is actually already at WeShare
            if self.base_url in self.driver.current_url:
                print("🎉 You appear to be at WeShare already!")
                self.authenticated = True
                return True
            
            # Manual override option
            print("\nℹ️  The browser window should be open. Please check if:")
            print("   1. You're already logged into WeShare")
            print("   2. There's an MFA prompt that needs completion")
            print("   3. There's an approval/permission dialog")
            
            manual_continue = input("\nAre you at the WeShare main page now? (y/n): ").strip().lower()
            if manual_continue == 'y':
                # Verify by navigating to WeShare to double-check
                try:
                    self.driver.get(self.base_url)
                    time.sleep(3)
                    
                    if self.base_url in self.driver.current_url and "login" not in self.driver.current_url.lower():
                        print("✅ Confirmed: Successfully at WeShare!")
                        self.authenticated = True
                        return True
                    else:
                        print("❌ Still not at WeShare main page")
                        return False
                except Exception as e:
                    print(f"❌ Error verifying WeShare access: {e}")
                    return False
            else:
                print("❌ Authentication incomplete")
                return False
                
        except TimeoutException as e:
            print(f"⏰ Timeout during authentication: {e}")
            print(f"Current URL: {self.driver.current_url}")
            return False
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            print(f"Current URL: {self.driver.current_url}")
            return False

    def scrape_hierarchical_pages(self, start_url: str, output_dir: str = "scraped_content") -> List[Dict[str, str]]:
        """
        Scrape hierarchical pages with enhanced markdown integration.
        
        Args:
            start_url (str): Starting URL (like your Tips & Tricks page)
            output_dir (str): Directory to save scraped content
            
        Returns:
            List[Dict]: List of page data with markdown content in the 'content' field
        """
        if not self.authenticated:
            print("Not authenticated. Please login first.")
            return []
        
        # Create output directory
        Path(output_dir).mkdir(exist_ok=True)
        
        try:
            print(f"Navigating to starting page: {start_url}")
            self.driver.get(start_url)
            
            # Look for the hierarchical list (adapting XPath)
            try:
                list_element = self.wait.until(
                    EC.visibility_of_element_located((By.XPATH, '//*[@id="child_ul41468043-0"]'))
                )
            except TimeoutException:
                # Try alternative selectors for different page structures
                alternative_selectors = [
                    "//ul[contains(@id, 'child_ul')]",
                    "//div[@class='wiki-content']//ul",
                    "//div[@id='content']//ul",
                    "//ul[contains(@class, 'content-tree')]",
                    "//div[contains(@class, 'page-tree')]//ul"
                ]
                
                list_element = None
                for selector in alternative_selectors:
                    try:
                        list_element = self.driver.find_element(By.XPATH, selector)
                        print(f"Found hierarchical list using selector: {selector}")
                        break
                    except NoSuchElementException:
                        continue
                
                if not list_element:
                    print("Could not find hierarchical list on the page")
                    print("Available elements on page:")
                    # Debug: show some elements that might be the list
                    try:
                        all_uls = self.driver.find_elements(By.TAG_NAME, "ul")
                        for i, ul in enumerate(all_uls[:5]):  # Show first 5 UL elements
                            print(f"  UL {i}: class='{ul.get_attribute('class')}', id='{ul.get_attribute('id')}'")
                    except:
                        pass
                    return []

            # Extract all page links from the hierarchy
            list_items = list_element.find_elements(By.TAG_NAME, "li")
            page_data = self._expand_and_scrape(list_items)
            
            print(f"Found {len(page_data)} pages to scrape")
            
            if not page_data:
                print("No pages found in hierarchy. Check if the page structure has changed.")
                return []
            
            # Scrape each page with enhanced content processing
            scraped_content = []
            for i, (href, title) in enumerate(page_data):
                try:
                    print(f"Scraping page {i+1}/{len(page_data)}: {title}")
                    content = self._scrape_single_page_enhanced(href, title, output_dir)
                    
                    if content:
                        scraped_content.append(content)
                        self.current_id += 1
                        
                        # Progress indicator
                        if (i + 1) % 10 == 0:
                            print(f"  📊 Progress: {i + 1}/{len(page_data)} pages processed")
                        
                        time.sleep(2)  # Respect rate limits
                    
                except Exception as e:
                    print(f"Error scraping page {title}: {e}")
                    continue
            
            # Save comprehensive metadata with markdown content
            metadata_path = Path(output_dir) / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(scraped_content, f, indent=2, ensure_ascii=False)
            
            # Create summary report
            self._create_scraping_summary(scraped_content, output_dir)
            
            print(f"\n✅ Scraping completed!")
            print(f"📄 Total pages scraped: {len(scraped_content)}")
            print(f"📁 Output directory: {output_dir}")
            print(f"📊 Metadata saved: {metadata_path}")
            print(f"💡 Metadata.json now contains markdown content in the 'content' field")
            
            return scraped_content
            
        except Exception as e:
            print(f"Error in hierarchical scraping: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _expand_and_scrape(self, items):
        """Enhanced hierarchy expansion with better error handling."""
        item_data = []
        for item in items:
            try:
                anchors = item.find_elements(By.XPATH, ".//a")
                
                if len(anchors) > 1:
                    # Use the second <a> element that contains the title and href
                    anchor = anchors[1]
                    href = anchor.get_attribute("href")
                    title = anchor.text.strip()
                    
                    # Validate URL and title
                    if href and title and self.base_url in href:
                        item_data.append((href, title))
                        print(f"  📄 Found page: {title}")
                    
                    try:
                        # Click drop-down toggle to expand children
                        toggle = anchors[0]
                        if toggle.get_attribute("class") and "icon" in toggle.get_attribute("class"):
                            toggle.click()
                            time.sleep(1)  # Wait for expansion
                            
                            # Recursively scrape children <li> elements
                            try:
                                child_list = item.find_element(By.TAG_NAME, "ul")
                                child_items = child_list.find_elements(By.TAG_NAME, "li")
                                if child_items:
                                    print(f"  🔄 Expanding {len(child_items)} children of '{title}'")
                                    item_data.extend(self._expand_and_scrape(child_items))
                            except NoSuchElementException:
                                pass  # No children found
                                
                    except Exception as e:
                        print(f"  ⚠️  Could not expand item '{title}': {e}")
                
                elif len(anchors) == 1:
                    # Use the first and only <a> element
                    anchor = anchors[0]
                    href = anchor.get_attribute("href")
                    title = anchor.text.strip()
                    
                    # Validate URL and title
                    if href and title and self.base_url in href:
                        item_data.append((href, title))
                        print(f"  📄 Found page: {title}")
                        
            except Exception as e:
                print(f"  ❌ Error processing list item: {e}")
                continue
        
        return item_data

    def _scrape_single_page_enhanced(self, href: str, title: str, output_dir: str) -> Optional[Dict[str, str]]:
        """
        Enhanced single page scraping with markdown stored in content field.
        
        IMPORTANT: This method now stores markdown content in the 'content' field
        of the returned dictionary to ensure metadata.json contains markdown.
        """
        try:
            # Navigate to the page
            self.driver.get(href)
            
            # Extract breadcrumbs
            breadcrumbs = []
            try:
                breadcrumb_elements = self.driver.find_elements(
                    By.XPATH,
                    "//content[@tag='breadcrumbs']//ol[@id='quickedit-breadcrumbs']/li/span/a"
                )
                breadcrumbs = [elem.get_attribute("innerText").strip() for elem in breadcrumb_elements if elem.get_attribute("innerText")]
            except Exception:
                print(f"  ⚠️  Could not get breadcrumbs for {title}")
            
            breadcrumb_path = " > ".join(breadcrumbs) if breadcrumbs else ""
            
            # Try to access View Source for cleaner content
            html_content = ""
            try:
                # Click the 3 dots menu button
                menu_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="action-menu-link"]'))
                )
                menu_button.click()
                
                # Click View Source
                view_source = self.driver.find_element(By.XPATH, '//*[@id="action-view-source-link"]')
                view_source_href = view_source.get_attribute("href")
                self.driver.get(view_source_href)
                
                html_content = self.driver.page_source
                print(f"  ✅ Retrieved View Source content")
                
            except Exception as e:
                print(f"  ⚠️  Could not access View Source for {title}, using page content: {e}")
                # Fallback to regular page content
                html_content = self.driver.page_source
            
            # Extract last modified information with timeout
            last_modified_info = self._extract_last_modified_with_timeout(html_content, timeout=3.0)
            
            # Convert HTML to markdown content - THIS IS THE KEY PART
            markdown_content = ""
            try:
                markdown_content = html_to_markdown(html_content)
                print(f"  📝 Converted to markdown ({len(markdown_content)} characters)")
            except Exception as e:
                print(f"  ❌ Error converting to markdown: {e}")
                # If conversion fails, try to extract text content as fallback
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    markdown_content = soup.get_text(separator='\n', strip=True)
                    print(f"  📝 Fallback: Extracted plain text ({len(markdown_content)} characters)")
                except:
                    markdown_content = title  # Last resort: at least save the title
            
            # Create result object with MARKDOWN in the content field
            result = {
                'id': f"{self.current_id:04d}",
                'url': href,
                'title': title,
                'content': markdown_content,  # *** STORING MARKDOWN HERE FOR METADATA.JSON ***
                'markdown_content': markdown_content,  # Keep for compatibility
                'breadcrumbs': breadcrumb_path,
                'timestamp': time.time(),
                'formatted_date': datetime.now().strftime('%m/%d/%y')
            }
            
            # Add last modified info if found
            if last_modified_info:
                result['last_modified'] = last_modified_info
                print(f"  📅 Last modified: {last_modified_info.get('date', 'Unknown date')} by {last_modified_info.get('user', 'Unknown user')}")
            
            # Save files - HTML file for reference, markdown file for human reading
            filename = f"page_{self.current_id:04d}_{self._clean_filename(title)}"
            
            # Still save HTML file for reference/debugging
            html_path = Path(output_dir) / f"{filename}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)  # Save original HTML to file
            result['html_path'] = str(html_path)
            
            # Save markdown file
            if markdown_content:
                md_path = Path(output_dir) / f"{filename}.md"
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                result['markdown_path'] = str(md_path)
                print(f"  📄 Saved markdown: {md_path.name}")
            
            return result
            
        except Exception as e:
            print(f"  ❌ Error scraping single page {title}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_last_modified_with_timeout(self, content: str, timeout: float = 3.0) -> Optional[Dict[str, str]]:
        """
        Extract last modified information with a timeout to prevent hanging.
        
        Args:
            content: HTML content to search
            timeout: Maximum seconds to spend searching
            
        Returns:
            Dict with last modified info or None if not found/timeout
        """
        def extract_last_modified(html_content: str) -> Optional[Dict[str, str]]:
            # Pattern for "last modified by [user] on [date]" from WeShare
            patterns = [
                r'last\s+modified\s+by\s+([^,]+?)\s+on\s+([^,\n<]+)',
                r'last\s+modified\s+by\s+<[^>]+>([^<]+)</[^>]+>\s+on\s+([^,\n<]+)',
                # Additional patterns for flexibility
                r'modified\s+by\s+([^,]+?)\s+on\s+([^,\n<]+)',
                r'updated\s+by\s+([^,]+?)\s+on\s+([^,\n<]+)'
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    if len(groups) == 2:
                        user = groups[0].strip()
                        # Clean up user - remove any HTML tags if present
                        user = re.sub(r'<[^>]+>', '', user)
                        user = user.strip()
                        
                        date = groups[1].strip()
                        # Clean up date - remove any HTML tags if present
                        date = re.sub(r'<[^>]+>', '', date)
                        date = date.strip()
                        
                        return {
                            'user': user,
                            'date': date,
                            'raw_match': match.group(0)
                        }
            
            # Try to find in meta tags
            meta_match = re.search(r'<meta\s+(?:name|property)=["\']last-modified["\']\s+content=["\'](.*?)["\']\s*/?>',
                                   html_content, re.IGNORECASE)
            if meta_match:
                return {
                    'date': meta_match.group(1),
                    'source': 'meta_tag'
                }
            
            return None
        
        # Use ThreadPoolExecutor for timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(extract_last_modified, content)
            try:
                result = future.result(timeout=timeout)
                return result
            except FutureTimeoutError:
                print(f"  ⏱️  Timeout after {timeout} seconds searching for last modified - continuing...")
                return None
            except Exception as e:
                print(f"  ❌ Error extracting last modified: {e}")
                return None

    def _clean_filename(self, title: str) -> str:
        """Clean filename with better handling."""
        import re
        # Remove invalid filename characters & limit length
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', title)
        # Remove multiple underscores
        cleaned = re.sub(r'_{2,}', '_', cleaned)
        # Remove leading/trailing underscores
        cleaned = cleaned.strip('_')
        return cleaned[:100]  # Increased length limit

    def _create_scraping_summary(self, scraped_content: List[Dict], output_dir: str):
        """Create a summary report of the scraping results."""
        try:
            summary = {
                'scraping_timestamp': datetime.now().isoformat(),
                'total_pages': len(scraped_content),
                'pages_with_markdown': sum(1 for page in scraped_content if page.get('markdown_content')),
                'pages_with_last_modified': sum(1 for page in scraped_content if page.get('last_modified')),
                'content_type': 'MARKDOWN',  # Indicate that content field contains markdown
                'total_markdown_size': sum(len(page.get('content', '')) for page in scraped_content),
                'breadcrumb_distribution': {},
                'file_paths': {
                    'metadata': 'metadata.json',
                    'html_files': [page.get('html_path', '') for page in scraped_content],
                    'markdown_files': [page.get('markdown_path', '') for page in scraped_content if page.get('markdown_path')]
                }
            }
            
            # Analyze breadcrumb distribution
            for page in scraped_content:
                breadcrumbs = page.get('breadcrumbs', '')
                if breadcrumbs:
                    root = breadcrumbs.split(' > ')[0] if ' > ' in breadcrumbs else breadcrumbs
                    summary['breadcrumb_distribution'][root] = summary['breadcrumb_distribution'].get(root, 0) + 1
            
            # Calculate average content size
            if scraped_content:
                summary['average_content_size'] = round(summary['total_markdown_size'] / len(scraped_content))
                summary['estimated_total_tokens'] = round(summary['total_markdown_size'] / 4)
            
            # Save summary
            summary_path = Path(output_dir) / "scraping_summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            print(f"\n📊 Scraping Summary:")
            print(f"   Total pages: {summary['total_pages']}")
            print(f"   Pages with markdown: {summary['pages_with_markdown']}")
            print(f"   Content type in metadata.json: {summary['content_type']}")
            print(f"   Average content size: {summary.get('average_content_size', 0):,} characters")
            print(f"   Estimated tokens: {summary.get('estimated_total_tokens', 0):,}")
            print(f"   Summary saved: {summary_path}")
            
        except Exception as e:
            print(f"Error creating summary: {e}")

    def scrape_urls(self, urls: List[str], output_dir: str = "scraped_content") -> List[Dict[str, str]]:
        """
        Scrape individual URLs with markdown integration.
        NOTE: This method also stores markdown in the content field for consistency.
        
        Args:
            urls (List[str]): List of URLs to scrape
            output_dir (str): Directory to save scraped content
            
        Returns:
            List[Dict]: List of scraped page data with markdown in content field
        """
        if not self.authenticated:
            print("Not authenticated. Please login first.")
            return []
        
        Path(output_dir).mkdir(exist_ok=True)
        scraped_content = []
        
        for i, url in enumerate(urls):
            print(f"Processing {i+1}/{len(urls)}: {url}")
            
            try:
                self.driver.get(url)
                
                # Wait for page to load
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(3)
                
                # Extract content using enhanced method
                title = self.driver.title
                content = self._scrape_single_page_enhanced(url, title, output_dir)
                
                if content:
                    content['id'] = f"{i:04d}"
                    scraped_content.append(content)
                
                time.sleep(3)
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
                continue
        
        # Save metadata with markdown content
        metadata_path = Path(output_dir) / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(scraped_content, f, indent=2, ensure_ascii=False)
        
        # Create summary
        self._create_scraping_summary(scraped_content, output_dir)
        
        return scraped_content

    def save_session(self, filepath: str = "weshare_session.json"):
        try:
            session_data = {
                'cookies': self.driver.get_cookies(),
                'current_url': self.driver.current_url
            }
            
            with open(filepath, 'w') as f:
                json.dump(session_data, f, indent=2)
            print(f"Session saved to {filepath}")
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False

    def load_session(self, filepath: str = "weshare_session.json") -> bool:
        try:
            if not os.path.exists(filepath):
                return False
                
            with open(filepath, 'r') as f:
                session_data = json.load(f)
            
            # Navigate to base URL first
            self.driver.get(self.base_url)
            
            # Load cookies
            for cookie in session_data.get('cookies', []):
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass
            
            # Refresh page to apply session
            self.driver.refresh()
            
            # Check if we're logged in
            if self.base_url in self.driver.current_url and "login" not in self.driver.current_url.lower():
                self.authenticated = True
                print("Session loaded successfully")
                return True
            else:
                print("Session expired or invalid")
                return False
                
        except Exception as e:
            print(f"Error loading session: {e}")
            return False

    def close(self):
        if self.driver:
            self.driver.quit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()