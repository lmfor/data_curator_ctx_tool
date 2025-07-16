import os
import time
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

from .html_to_markdown import convert_html_file


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
            
            # Click Next button using exact XPath
            next_button = self.driver.find_element(By.XPATH, '//*[@id="idSIButton9"]')
            next_button.click()
            
            # Enter password using exact XPath
            print("Entering password...")
            password_field = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="i0118"]'))
            )
            password_field.clear()
            password_field.send_keys(password)
            
            # Click Sign in button
            signin_button = self.driver.find_element(By.XPATH, '//*[@id="idSIButton9"]')
            signin_button.click()
            
            # Handle "Stay signed in?" prompt
            try:
                stay_signed_in = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="idSIButton9"]'))
                )
                stay_signed_in.click()
                print("Clicked 'Stay signed in'")
            except TimeoutException:
                print("No 'Stay signed in' prompt found, continuing...")
            
            print("Waiting for redirect back to WeShare...")
            self.wait.until(
                lambda driver: self.base_url in driver.current_url and 
                              "login" not in driver.current_url.lower()
            )
            
            # Check if we're back at WeShare
            print(f"Current URL after authentication: {self.driver.current_url}")
            
            if self.base_url in self.driver.current_url and "login" not in self.driver.current_url.lower():
                self.authenticated = True
                print("Successfully authenticated with Microsoft SSO")
                return True
            else:
                print("Login may have failed - not at expected URL")
                return False
                
        except TimeoutException as e:
            print(f"Timeout during authentication: {e}")
            print(f"Current URL: {self.driver.current_url}")
            return False
        except Exception as e:
            print(f"Authentication error: {e}")
            print(f"Current URL: {self.driver.current_url}")
            return False

    def scrape_hierarchical_pages(self, start_url: str, output_dir: str = "scraped_content") -> List[Dict[str, str]]:
        """
        Args:
            start_url (str): Starting URL (like your Tips & Tricks page)
            output_dir (str): Directory to save scraped content
            
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
                # Try alt selectors for dif page structures
                alternative_selectors = [
                    "//ul[contains(@id, 'child_ul')]",
                    "//div[@class='wiki-content']//ul",
                    "//div[@id='content']//ul",
                    "//ul[contains(@class, 'content-tree')]"
                ]
                
                list_element = None
                for selector in alternative_selectors:
                    try:
                        list_element = self.driver.find_element(By.XPATH, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if not list_element:
                    print("Could not find hierarchical list on the page")
                    return []
            

            list_items = list_element.find_elements(By.TAG_NAME, "li")
            page_data = self._expand_and_scrape(list_items)
            
            print(f"Found {len(page_data)} pages to scrape")
            
            # Scrape each page
            scraped_content = []
            for i, (href, title) in enumerate(page_data):
                try:
                    print(f"Scraping page {i+1}/{len(page_data)}: {title}")
                    content = self._scrape_single_page(href, title)
                    
                    if content:

                        filename = f"page_{self.current_id:04d}_{self._clean_filename(title)}.html"
                        html_path = Path(output_dir) / filename
                        
                        with open(html_path, 'w', encoding='utf-8') as f:
                            f.write(content['content'])
                        

                        md_path = html_path.with_suffix('.md')
                        try:
                            convert_html_file(str(html_path), str(md_path))
                            content['markdown_path'] = str(md_path)
                            print(f"  ✓ Converted to markdown: {md_path}")
                        except Exception as e:
                            print(f"  ✗ Error converting to markdown: {e}")
                        
                        content['html_path'] = str(html_path)
                        scraped_content.append(content)
                        self.current_id += 1
                        
                        time.sleep(2) # respect delay !
                    
                except Exception as e:
                    print(f"Error scraping page {title}: {e}")
                    continue
            
            metadata_path = Path(output_dir) / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(scraped_content, f, indent=2)
            
            return scraped_content
            
        except Exception as e:
            print(f"Error in hierarchical scraping: {e}")
            return []

    def _expand_and_scrape(self, items):
        item_data = []
        for item in items:
            try:
                anchors = item.find_elements(By.XPATH, ".//a")
                
                if len(anchors) > 1:
                    # Use the second <a> element that contains the title and href
                    anchor = anchors[1]
                    href = anchor.get_attribute("href")
                    title = anchor.text
                    if href and title:
                        item_data.append((href, title))
                    
                    try:
                        # Click drop-down toggle
                        toggle = anchors[0]
                        toggle.click()
                        time.sleep(1)  # Wait for expansion
                        
                        # Recursively scrape children <li> elements
                        try:
                            child_list = item.find_element(By.TAG_NAME, "ul")
                            child_items = child_list.find_elements(By.TAG_NAME, "li")
                            item_data.extend(self._expand_and_scrape(child_items))
                        except NoSuchElementException:
                            pass  # No children found
                            
                    except Exception as e:
                        print(f"Could not expand item {title}: {e}")
                
                elif len(anchors) == 1:
                    # Use the first and only <a> element
                    anchor = anchors[0]
                    href = anchor.get_attribute("href")
                    title = anchor.text
                    if href and title:
                        item_data.append((href, title))
                        
            except Exception as e:
                print(f"Error processing list item: {e}")
                continue
        
        return item_data

    def _scrape_single_page(self, href: str, title: str) -> Optional[Dict[str, str]]:
        try:
            # Navigate to the page
            self.driver.get(href)
            
           
            breadcrumbs = []
            try:
                breadcrumb_elements = self.driver.find_elements(  # Get breadcrumb path
                    By.XPATH,
                    "//content[@tag='breadcrumbs']//ol[@id='quickedit-breadcrumbs']/li/span/a"
                )
                breadcrumbs = [elem.get_attribute("innerText") for elem in breadcrumb_elements]
            except Exception:
                print(f"Could not get breadcrumbs for {title}")
            
            breadcrumb_path = " > ".join(breadcrumbs) if breadcrumbs else ""
            
            # Try to access View Source 
            try:
                # Click  the 3 dots menu button
                menu_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="action-menu-link"]'))
                )
                menu_button.click()
                
                # Click view Source
                view_source = self.driver.find_element(By.XPATH, '//*[@id="action-view-source-link"]')
                view_source_href = view_source.get_attribute("href")
                self.driver.get(view_source_href)
                
                content = self.driver.page_source
                
            except Exception as e:
                print(f"Could not access View Source for {title}, using page content: {e}")
                # fallback to regular page content
                content = self.driver.page_source
            
            return {
                'id': f"{self.current_id:04d}",
                'url': href,
                'title': title,
                'content': content,
                'breadcrumbs': breadcrumb_path,
                'timestamp': time.time()
            } #type: ignore
            
        except Exception as e:
            print(f"Error scraping single page {title}: {e}")
            return None

    def _clean_filename(self, title: str) -> str:
        import re
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', title) # Remove invalid filename characters & Limit length
        return cleaned[:50]

    def scrape_urls(self, urls: List[str], output_dir: str = "scraped_content") -> List[Dict[str, str]]:
        
        # 
        """
        Args:
            urls (List[str]): List of URLs to scrape
            output_dir (str): Directory to save scraped content
            
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
                
                # Extract content
                content = {
                    'id': f"{i:04d}",
                    'url': url,
                    'title': self.driver.title,
                    'content': self.driver.page_source,
                    'timestamp': time.time()
                }
                
                # Save files
                filename = f"page_{i:04d}_{self._clean_filename(content['title'])}.html"
                html_path = Path(output_dir) / filename
                
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(content['content'])
                
                # --> MD
                md_path = html_path.with_suffix('.md')
                try:
                    convert_html_file(str(html_path), str(md_path))
                    content['markdown_path'] = str(md_path)
                except Exception as e:
                    print(f"Error converting to markdown: {e}")
                
                content['html_path'] = str(html_path)
                scraped_content.append(content)
                
                time.sleep(3)
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
                continue
        
        
        metadata_path = Path(output_dir) / "metadata.json" # save metadata
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(scraped_content, f, indent=2)
        
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