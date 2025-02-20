import json
import time
import argparse
import os
import hashlib
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .browser_manager import BrowserManager
from .downloader import DownloadLink

class WebSearchEngine:
    def __init__(self, working_dir):
        self.num_results = 5  # Number of results per query
        self.delay = 3.0  # Increased delay between searches
        self.driver = BrowserManager.get_instance().get_driver()
        
        # Set up cache directory
        self.cache_dir = os.path.join(working_dir, 'cache', 'search')
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_cache_file(self, query):
        """Generate a cache file path for a given query."""
        # Create a unique filename based on the query
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{query_hash}.json")
        
    def _get_cached_results(self, query):
        """Get cached results if they exist and are fresh (less than 1 day old)."""
        cache_file = self._get_cache_file(query)
        
        if os.path.exists(cache_file):
            # Check if cache is fresh (less than 1 day old)
            cache_age = time.time() - os.path.getmtime(cache_file)
            if cache_age < 86400:  # 1 day in seconds
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)
                        print(f"\nUsing cached results for: {query}")
                        print(f"Cache age: {int(cache_age/60)} minutes")
                        # Convert cached results to DownloadLink objects
                        results = []
                        for result in cached_data.get('results', []):
                            if result.get('url'):
                                download_link = DownloadLink(
                                    url=result['url'],
                                    parent_snippet=query,
                                    snippet=result.get('snippet', '')
                                )
                                results.append(download_link)
                        return results
                except json.JSONDecodeError:
                    print(f"Warning: Invalid cache file for query: {query}")
                    
        return None
        
    def _cache_results(self, query, download_links):
        """Cache the search results."""
        cache_file = self._get_cache_file(query)
        try:
            # Convert DownloadLink objects to serializable format
            results = {
                'query': query,
                'results': [
                    {
                        'url': link.url,
                        'snippet': link.snippet
                    } for link in download_links
                ]
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to cache results for query '{query}': {str(e)}")
        
    def execute_searches(self, query):
        """
        Execute DuckDuckGo search for a single query using Chromium.
        Returns a list of DownloadLink objects.
        Assert there is at least one result.
        """
        # Check cache first
        cached_results = self._get_cached_results(query)
        if cached_results is not None:
            return cached_results
            
        try:
            print(f"\nExecuting search for: {query}")
            
            # Navigate to DuckDuckGo
            self.driver.get("https://duckduckgo.com")
            
            # Wait for search box and enter query
            wait = WebDriverWait(self.driver, 10)
            search_box = wait.until(EC.presence_of_element_located((By.ID, "searchbox_input")))
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)
            
            # Wait for results
            time.sleep(2)  # Brief pause for results to load
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='result']")))
            
            # Get the page source and parse with BeautifulSoup
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all result containers
            result_elements = soup.select("article[data-testid='result']")
            results = []
            
            # Process found elements
            for element in result_elements:
                # Try to find the link and title
                link_tag = element.find('a', {'data-testid': 'result-title-a'})
                if not link_tag:
                    continue
                
                url = link_tag.get('href')
                title = link_tag.get_text().strip()
                
                # Try to get snippet text
                snippet = element.find('div', {'data-testid': 'result-snippet'})
                snippet_text = snippet.get_text().strip() if snippet else ""
                
                if url and title and not url.startswith('javascript:') and not url.startswith('about:') and not url.startswith('?'):
                    print(f"Found result: {title} - {url}")
                    download_link = DownloadLink(
                        url=url,
                        parent_snippet=query,
                        snippet=snippet_text
                    )
                    results.append(download_link)
                    
                if len(results) >= self.num_results:
                    break
            
            # If no results found, print debug info
            if len(results) == 0:
                print("\nNo results found. Debug information:")
                print("=" * 50)
                print("Full page content:")
                print(soup.prettify())
                print("=" * 50)
                raise ValueError(f"No search results found for query: {query}")
            
            # Print found results summary
            print(f"\nFound {len(results)} results")
            for result in results:
                print(f"URL: {result.url}")
                print(f"Snippet: {result.snippet[:100]}...\n")
            
            # Cache the results
            self._cache_results(query, results)
            
            return results
            
        except Exception as e:
            print(f"Error executing search for '{query}': {str(e)}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Test DuckDuckGo web search')
    parser.add_argument('--query', type=str, required=True,
                      help='Search query to test')
    parser.add_argument('--working-dir', type=str, default='.',
                      help='Working directory for cache')
    args = parser.parse_args()
    
    try:
        # Initialize browser
        BrowserManager.initialize('/Users/haha/mingdao/third_party/python/chromeDriver')
        
        # Create search engine and execute search
        searcher = WebSearchEngine(args.working_dir)
        results = searcher.execute_searches(args.query)
        
        print("\nSearch Results:")
        for link in results:
            print(f"\nURL: {link.url}")
            print(f"Parent Query: {link.parent_snippet}")
            print(f"Snippet: {link.snippet[:100]}...")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        BrowserManager.get_instance().cleanup()

if __name__ == '__main__':
    main() 