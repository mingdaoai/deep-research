import json
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote, urljoin
import pdfplumber
from io import BytesIO
from datetime import datetime, timedelta
import time
import sys
from .browser_manager import BrowserManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class DownloadLink:
    url: str
    parent_snippet: Optional[str] = None
    snippet: Optional[str] = None

class ContentDownloader:
    def __init__(self, cache_dir):
        self.cache_dir = os.path.join(cache_dir, 'downloads')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.browser_manager = None
        
    def _get_browser_manager(self):
        if not self.browser_manager:
            BrowserManager.initialize()
            self.browser_manager = BrowserManager.get_instance()
        return self.browser_manager
        
    def _extract_urls_from_html(self, html_content: str, base_url: str, parent_link: Optional[DownloadLink] = None) -> List[DownloadLink]:
        """Extract URLs from HTML content and convert them to DownloadLink objects."""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        # Build parent context from the chain of snippets
        parent_context = ""
        if parent_link:
            if parent_link.parent_snippet:
                parent_context += parent_link.parent_snippet + " | "
            if parent_link.snippet:
                parent_context += parent_link.snippet
        
        # Find all <a> tags
        for a_tag in soup.find_all('a', href=True):
            url = a_tag.get('href', '').strip()
            if not url:
                continue
                
            # Make URL absolute if it's relative
            if not url.startswith(('http://', 'https://')):
                url = urljoin(base_url, url)
            
            # Skip unwanted URLs
            if url.startswith(('javascript:', 'mailto:', 'tel:', '#', 'about:')):
                continue
                
            # Get surrounding text as snippet
            snippet = ''
            parent = a_tag.find_parent(['p', 'div', 'section'])
            if parent:
                snippet = parent.get_text().strip()
            else:
                snippet = a_tag.get_text().strip()
            
            links.append(DownloadLink(
                url=url,
                parent_snippet=parent_context,
                snippet=snippet
            ))
        
        return links
        
    def _extract_urls_from_text(self, text: str, base_url: str, parent_link: Optional[DownloadLink] = None) -> List[DownloadLink]:
        """Extract URLs from plain text content using regex."""
        import re
        
        # Build parent context from the chain of snippets
        parent_context = ""
        if parent_link:
            if parent_link.parent_snippet:
                parent_context += parent_link.parent_snippet + " | "
            if parent_link.snippet:
                parent_context += parent_link.snippet
        
        # URL regex pattern
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
        
        links = []
        # Find all URLs in text
        for match in re.finditer(url_pattern, text):
            url = match.group(0)
            
            # Get some context around the URL (up to 200 chars)
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            snippet = text[start:end].strip()
            
            links.append(DownloadLink(
                url=url,
                parent_snippet=parent_context,
                snippet=snippet
            ))
            
        return links

    def _download_and_extract_links(self, download_links, seen_urls=None) -> tuple[dict, list]:
        """
        Download content from links and extract new links from the content.
        Returns (downloaded_content, extracted_links).
        """
        if seen_urls is None:
            seen_urls = set()
            
        downloaded_content = {
            'results': []
        }
        extracted_links = []
        successful_downloads = 0
        
        # Deduplicate download_links while preserving context
        url_to_links = {}
        for link in download_links:
            if link.url not in url_to_links:
                url_to_links[link.url] = link
            else:
                # Merge contexts if we have a duplicate URL
                existing_link = url_to_links[link.url]
                merged_parent_snippet = ""
                if existing_link.parent_snippet:
                    merged_parent_snippet += existing_link.parent_snippet
                if link.parent_snippet and link.parent_snippet not in merged_parent_snippet:
                    if merged_parent_snippet:
                        merged_parent_snippet += " | "
                    merged_parent_snippet += link.parent_snippet
                
                merged_snippet = ""
                if existing_link.snippet:
                    merged_snippet += existing_link.snippet
                if link.snippet and link.snippet not in merged_snippet:
                    if merged_snippet:
                        merged_snippet += " | "
                    merged_snippet += link.snippet
                
                url_to_links[link.url] = DownloadLink(
                    url=link.url,
                    parent_snippet=merged_parent_snippet,
                    snippet=merged_snippet
                )
        
        # Process deduplicated links
        for link in url_to_links.values():
            try:
                url = link.url
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                
                print(f"Attempting to download content from {url}")
                content = self._get_cached_content(url)
                if not content:
                    content = self._fetch_and_process_url(url)
                    if content:
                        self._cache_content(url, content)
                    time.sleep(1)  # Sleep for 1 second after downloading from the internet
                
                if content:
                    # Extract URLs from the downloaded content
                    if 'html' in content.get('content_type', '').lower():
                        new_links = self._extract_urls_from_html(content.get('text', ''), url, parent_link=link)
                    else:
                        new_links = self._extract_urls_from_text(content.get('text', ''), url, parent_link=link)
                    
                    # Add unique links to extracted_links
                    for new_link in new_links:
                        if new_link.url not in seen_urls:
                            extracted_links.append(new_link)
                            seen_urls.add(new_link.url)
                    
                    downloaded_content['results'].append({
                        'url': url,
                        'title': content.get('title', ''),
                        'text': content.get('text', ''),
                        'parent_snippet': link.parent_snippet,
                        'snippet': link.snippet,
                        'extracted_urls': [link.url for link in new_links],
                        'success': True
                    })
                    successful_downloads += 1
                    print(f"Successfully downloaded content from {url}")
                    print(f"Extracted {len(new_links)} new URLs from content")
            except Exception as e:
                print(f"Error downloading {url}: {str(e)}")
                downloaded_content['results'].append({
                    'url': url,
                    'error': str(e),
                    'parent_snippet': link.parent_snippet,
                    'snippet': link.snippet,
                    'success': False
                })
        
        if (successful_downloads == 0) and (len(url_to_links) > 0):
            print("No successful downloads. URLs attempted:")
            for link in url_to_links.values():
                print(link.url)
            raise Exception("No successful downloads")
            
        return downloaded_content, extracted_links

    def download_content(self, download_links, max_relevant_links=500):
        """
        Download and process content from a list of DownloadLink objects.
        Uses LLM to identify most relevant links at each step until we have downloaded max_relevant_links.
        Returns JSON-formatted content.
        """
        try:
            if not isinstance(download_links, list):
                raise ValueError("download_links must be a list of DownloadLink objects")
            
            for link in download_links:
                if not isinstance(link, DownloadLink):
                    raise ValueError(f"Each item must be a DownloadLink object, got {type(link)}")
            
            # Initialize LLM
            from .llm_client import LLMClientManager
            llm = LLMClientManager.get_instance()
            
            # Initialize result containers
            all_content = {
                'results': [],
                'extracted_links': []
            }
            seen_urls = set()
            all_available_links = download_links.copy()  # Start with initial links
            downloaded_count = 0
            
            while downloaded_count < max_relevant_links and all_available_links:
                # Remove already seen URLs from available links
                available_links = [link for link in all_available_links if link.url not in seen_urls]
                if not available_links:
                    break
                    
                # Prepare context for LLM - only include undownloaded links
                context = [
                    {
                        'parent_snippet': link.parent_snippet,
                        'snippet': link.snippet,
                        'url': link.url
                    } for link in available_links  # Use available_links instead of all_available_links
                ]
                
                system_prompt = """You are an expert at identifying relevant URLs for research.
Given a list of URLs with their context, identify the most relevant URLs that would provide valuable information.
Consider the context and snippets of each URL.
Return a JSON array of indices into the URL array for the most relevant URLs to process next.
Limit your selection to 10 URLs per batch."""

                user_prompt = f"""Available URLs and their context:
{json.dumps(context, indent=0)}

Return a JSON array of indices (0-based) for the most relevant URLs to download next.
Example response format: [0, 3, 5]
Respond in JSON format, not any text or markdown. Don't put in any quotes or other text.
"""

                response = llm.create_chat_completion(system_prompt, user_prompt)
                try:
                    relevant_indices = json.loads(response)
                except json.JSONDecodeError:
                    print(f"Failed to parse LLM response: {response}")
                    assert False
                
                # Validate indices
                if not isinstance(relevant_indices, list):
                    raise ValueError("LLM response is not a list")
                relevant_indices = [i for i in relevant_indices 
                                 if isinstance(i, int) 
                                 and 0 <= i < len(available_links)]  # Check against available_links length
                
                if not relevant_indices:
                    print("LLM returned no relevant indices")
                    break
                
                # Get the next batch of links to process
                batch_links = [available_links[i] for i in relevant_indices]  # Use available_links
                print(f"\nProcessing batch of {len(batch_links)} links")
                # print batch links nicely
                for link in batch_links:
                    print(f"  - URL: {link.url}")
                    print(f"    Parent Snippet: {link.parent_snippet}")
                    print(f"    Snippet: {link.snippet}")

                # Download this batch
                batch_content, new_extracted_links = self._download_and_extract_links(batch_links, seen_urls)
                
                # Update tracking
                all_content['results'].extend(batch_content['results'])
                downloaded_count += len(batch_content['results'])
                
                # Add newly discovered links to available pool
                all_available_links.extend(new_extracted_links)
                
                # Update seen URLs
                for result in batch_content['results']:
                    seen_urls.add(result['url'])
                
                print(f"Total downloaded: {downloaded_count}/{max_relevant_links}")
                print(f"Available unprocessed links: {len([l for l in all_available_links if l.url not in seen_urls])}")
            
            # Add all extracted links to the response
            all_content['extracted_links'] = [
                {'url': link.url, 'parent_snippet': link.parent_snippet, 'snippet': link.snippet}
                for link in all_available_links
            ]
            
            return all_content
            
        except Exception as e:
            print(f"Error in download_content: {str(e)}")
            raise

    def _fetch_and_process_url(self, url):
        """
        Fetch and process a single URL using either requests (for PDFs) or browser manager (for HTML).
        Returns dict with title and main text content.
        """
        try:
            # Try a direct GET request first
            print(f"\nMaking GET request to {url}")
            response = requests.get(url, timeout=30)
            print(f"GET request results:")
            print(f"Status code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type', '')}")
            print(f"Content length: {len(response.content)} bytes")
            print(f"Final URL: {response.url}")
            print(f"All headers: {dict(response.headers)}\n")
            
            # Try to detect if it's a PDF by examining the content
            content_start = response.content[:5]
            is_pdf = content_start.startswith(b'%PDF-')
            
            if is_pdf or 'application/pdf' in response.headers.get('Content-Type', '').lower():
                print("Detected as PDF document, processing content...")
                
                # Save PDF to a temporary file
                temp_pdf_path = os.path.join(self.cache_dir, 'temp.pdf')
                with open(temp_pdf_path, 'wb') as f:
                    f.write(response.content)
                print(f"Saved PDF to {temp_pdf_path}")
                
                # Get filename from Content-Disposition header if available
                content_disp = response.headers.get('Content-Disposition', '')
                if 'filename=' in content_disp:
                    title = content_disp.split('filename=')[1].strip('"')
                else:
                    title = urlparse(url).path.split('/')[-1]
                

                
                try:
                    # Try to process the saved PDF using pdfplumber
                    text = ''
                    with pdfplumber.open(temp_pdf_path) as pdf:
                        for page in pdf.pages:
                            text += page.extract_text() + '\n'
                    print(f"Successfully extracted {len(text)} characters from PDF")
                    
                    return {
                        'title': title,
                        'text': text
                    }
                except Exception as e:
                    print(f"Error processing PDF: {str(e)}")
                    # If PDF processing fails, try to use browser as fallback
                    raise
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_pdf_path):
                        os.remove(temp_pdf_path)
            
            # Process HTML content using browser manager
            browser = self._get_browser_manager().get_driver()
            browser.set_page_load_timeout(10)
            browser.get(url)
            
            # Wait for body to be present
            WebDriverWait(browser, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            time.sleep(2)  # Give JavaScript a bit more time to run
            
            # Get title
            title = browser.title
            
            # Get the page source and create BeautifulSoup object
            soup = BeautifulSoup(browser.page_source, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                element.decompose()
            
            # Get main content
            main = soup.find('main')
            article = soup.find('article')
            content = main or article or soup.body
            
            if content:
                text = content.get_text(separator='\n').strip()
            else:
                text = soup.body.get_text(separator='\n').strip() if soup.body else ''
            
            assert text, "No text content found"
            assert len(text) > 10, "Text content is too short"
            
            return {
                'title': title,
                'text': text
            }
                
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
            raise

    def _get_cached_content(self, url):
        """
        Retrieve cached content if it exists and is not stale.
        """
        cache_file = os.path.join(self.cache_dir, quote(url, safe=''))
        if os.path.exists(cache_file):
            cache_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - cache_time < timedelta(days=1):
                with open(cache_file, 'r') as f:
                    return json.load(f)
        return None

    def _cache_content(self, url, content):
        """
        Cache the content to a file based on the URL.
        """
        cache_file = os.path.join(self.cache_dir, quote(url, safe=''))
        with open(cache_file, 'w') as f:
            json.dump(content, f)

def main():
    """Test function to download and process a specific URL.
    Usage: python downloader.py --url <url>
    """
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Download and process content from a URL')
    parser.add_argument('--url', type=str, required=True,
                      help='URL to download and process')
    args = parser.parse_args()
    
    # Initialize downloader with a cache directory
    cache_dir = os.path.join('test_cache')
    os.makedirs(cache_dir, exist_ok=True)
    downloader = ContentDownloader(cache_dir)
    
    try:
        # Create a test DownloadLink
        download_link = DownloadLink(
            url=args.url,
            parent_snippet="test query",
            snippet="test snippet"
        )
        
        # Download and process the content
        result = downloader.download_content([download_link])
        print("\nDownload Result:")
        if result['results']:
            first_result = result['results'][0]
            print(f"Title: {first_result.get('title', 'No title')}")
            print(f"Parent Snippet: {first_result.get('parent_snippet', 'No parent snippet')}")
            print(f"Snippet: {first_result.get('snippet', 'No snippet')}")
            print(f"\nFirst 500 characters of text:")
            print(first_result.get('text', 'No text')[:500])
    except Exception as e:
        print(f"Error processing URL: {str(e)}")
        
if __name__ == '__main__':
    main()