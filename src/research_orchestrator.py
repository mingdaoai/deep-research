import os
import json
import glob
import logging
from .planner import ResearchPlanner
from .web_searcher import WebSearchEngine
from .downloader import ContentDownloader, DownloadLink
from .summarizer import Summarizer
from .browser_manager import BrowserManager
from .indexer import ContentIndexer
from .utils import save_json_file, read_json_file

class ResearchOrchestrator:
    def __init__(self, working_dir):
        self.working_dir = working_dir
        # Create cache directory in working_dir
        self.cache_dir = os.path.join(working_dir, 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize browser manager
        BrowserManager.initialize()
        
        # Initialize components with working directory
        self.planner = ResearchPlanner(working_dir)
        self.search_engine = WebSearchEngine(working_dir)
        self.downloader = ContentDownloader(self.cache_dir)
        self.summarizer = Summarizer(working_dir)
        self.indexer = ContentIndexer(working_dir)
        
    def _read_research_topic(self):
        """Read research topic from research.md"""
        try:
            with open(os.path.join(self.working_dir, 'research.md'), 'r') as f:
                return f.read()
        except FileNotFoundError:
            raise ValueError("research.md not found in working directory")
        except Exception as e:
            raise ValueError(f"Error reading research.md: {str(e)}")
            
    def _get_remaining_queries(self, plan_json):
        """Get the list of remaining queries from the plan"""
        try:
            plan = json.loads(plan_json) if isinstance(plan_json, str) else plan_json
            return plan.get('search_queries', [])
        except (json.JSONDecodeError, AttributeError) as e:
            logging.error(f"Error parsing plan JSON: {str(e)}")
            return []
            
    def _update_plan(self, queries, current_plan=None):
        """Update the plan with remaining queries while preserving other data"""
        try:
            plan_data = (json.loads(current_plan) if isinstance(current_plan, str) else current_plan) or {}
            plan_data['search_queries'] = queries
            return json.dumps(plan_data, indent=2)
        except (json.JSONDecodeError, AttributeError) as e:
            logging.error(f"Error updating plan: {str(e)}")
            return json.dumps({'search_queries': queries})
            
    def _cleanup_old_files(self, iteration):
        """Delete files from previous runs that are no longer needed"""
        subdirs = ['plan', 'search', 'results']
        for subdir in subdirs:
            dir_path = os.path.join(self.working_dir, subdir)
            if not os.path.exists(dir_path):
                continue
                
            # Get all files in the directory
            files = glob.glob(os.path.join(dir_path, '*_*.json'))
            for file in files:
                try:
                    file_iteration = int(file.split('_')[-1].replace('.json', ''))
                    if file_iteration > iteration:
                        os.remove(file)
                except (ValueError, IndexError, OSError) as e:
                    logging.warning(f"Error cleaning up file {file}: {str(e)}")
    
    def run(self):
        """Execute the research process"""
        try:
            # Read research topic
            research_topic = self._read_research_topic()
            iteration = 1
            
            # Generate initial research plan
            logging.info("Generating research plan...")
            plan = self.planner.create_plan(research_topic)
            save_json_file(plan, os.path.join(self.working_dir, 'plan'), 'search_plan', iteration)
            
            # Accumulate all search results
            all_search_results = []
            while True:
                # Get remaining queries from the plan
                queries = self._get_remaining_queries(plan)
                if not queries:
                    break
                    
                # Execute first query
                query = queries[0]
                logging.info(f"Executing search query: {query}")
                search_results = self.search_engine.execute_searches(query)
                
                # Validate search results
                if not all(isinstance(result, DownloadLink) for result in search_results):
                    raise ValueError("Search results must be a list of DownloadLink objects")
                all_search_results.extend(search_results)
                
                # Save search results
                results_json = {
                    'query': query,
                    'results': [{'url': link.url, 'snippet': link.snippet} for link in search_results]
                }
                save_json_file(results_json, os.path.join(self.working_dir, 'search'), 'search_results', iteration)
                
                # Update plan with remaining queries
                queries = queries[1:]  # Remove processed query
                plan = self._update_plan(queries, plan)
                iteration += 1
                save_json_file(json.loads(plan), os.path.join(self.working_dir, 'plan'), 'search_plan', iteration)
            
            # Download all accumulated content
            if all_search_results:
                logging.info(f"Downloading content from {len(all_search_results)} sources...")
                downloaded_content = self.downloader.download_content(all_search_results)
                save_json_file(downloaded_content, os.path.join(self.working_dir, 'results'), 'downloaded_content', iteration - 1)
            
            # Clean up files from previous runs
            self._cleanup_old_files(iteration - 1)
            
            # Index all downloaded content
            logging.info("Indexing downloaded content...")
            self.indexer.index_content()
            
            # Generate final document
            logging.info("Generating final summary...")
            self.summarizer.summarize()
                
        except Exception as e:
            logging.error(f"Error in research process: {str(e)}", exc_info=True)
            raise
        finally:
            try:
                BrowserManager.get_instance().cleanup()
            except Exception as e:
                logging.error(f"Error cleaning up browser manager: {str(e)}")