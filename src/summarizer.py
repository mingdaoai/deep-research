import os
import json
import argparse
from dotenv import load_dotenv
import markdown  # Add markdown package for HTML conversion
from weasyprint import HTML, CSS  # Add weasyprint for PDF generation
from transformers import AutoTokenizer  # Add tokenizer import
from .llm_client import LLMClientManager
from .local_searcher import LocalSearchEngine
import logging

class Summarizer:
    def __init__(self, working_dir):
        self.working_dir = working_dir
        self.llm_manager = LLMClientManager.get_instance(working_dir)
        self.max_chunk_size = 8000  # Maximum tokens per chunk for processing
        self.markdown_converter = markdown.Markdown(extensions=['extra'])  # Initialize markdown converter with extra features
        # Initialize tokenizer for accurate token counting
        self.tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/deepseek-llm-7b-base")
        # Initialize requirements as None, will be set in summarize method
        self.requirements = None
        
    def _load_research_requirements(self, working_dir, research_topic):
        """Load research requirements from research topic and search plan files."""
        requirements = {
            'topic': research_topic['topic'],
            'key_areas': [],
            'search_queries': [],
            'guidelines': research_topic['guidelines']
        }

        logging.info(f"Using provided research topic: {requirements['topic']}")
        logging.info(f"Using provided guidelines: {requirements['guidelines']}")

        # Read requirements from search plan files
        search_dir = os.path.join(working_dir, 'plan')
        logging.info(f"Looking for search directory at: {search_dir}")
        if os.path.exists(search_dir):
            # Get all plan files
            plan_files = os.listdir(search_dir)
            logging.info(f"Found {len(plan_files)} files in search directory:")
            for f in plan_files:
                logging.info(f"  - {f}")
            
            # Try different patterns for search plan files
            plan_patterns = [
                lambda f: f.startswith('search_plan_') and f.endswith('.json'),
                lambda f: f.endswith('.json'),  # Accept any JSON file
                lambda f: f.endswith('.md')     # Also accept markdown files
            ]
            
            for pattern in plan_patterns:
                plan_files = [f for f in plan_files if pattern(f)]
                if plan_files:
                    logging.info(f"Found {len(plan_files)} files matching pattern: {pattern.__name__}")
                    break
            
            if not plan_files:
                logging.warning("No search plan files found with any pattern")
                return requirements
            
            for filename in plan_files:
                file_path = os.path.join(search_dir, filename)
                logging.info(f"Processing search plan file: {filename}")
                try:
                    with open(file_path, 'r') as f:
                        if filename.endswith('.json'):
                            plan_data = json.load(f)
                        else:  # For markdown files
                            content = f.read()
                            # Try to extract JSON-like content from markdown
                            import re
                            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                            if json_match:
                                plan_data = json.loads(json_match.group(1))
                            else:
                                # If no JSON found, treat the whole content as a key area
                                plan_data = {'key_areas': [content.strip()]}
                        
                        # Handle both string and dictionary inputs
                        if isinstance(plan_data, str):
                            try:
                                plan_data = json.loads(plan_data)
                            except json.JSONDecodeError:
                                logging.error(f"Failed to parse JSON in {filename}")
                                continue
                        
                        if not isinstance(plan_data, dict):
                            logging.error(f"Invalid plan data format in {filename}")
                            continue
                        
                        if 'key_areas' in plan_data:
                            new_areas = [area for area in plan_data['key_areas'] 
                                       if area not in requirements['key_areas']]
                            requirements['key_areas'].extend(new_areas)
                            logging.info(f"Added {len(new_areas)} new key areas from {filename}")
                        else:
                            logging.warning(f"No 'key_areas' found in {filename}")
                            
                        if 'search_queries' in plan_data:
                            new_queries = [query for query in plan_data['search_queries'] 
                                         if query not in requirements['search_queries']]
                            requirements['search_queries'].extend(new_queries)
                            logging.info(f"Added {len(new_queries)} new search queries from {filename}")
                        else:
                            logging.warning(f"No 'search_queries' found in {filename}")
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logging.error(f"Error reading plan file {file_path}: {str(e)}", exc_info=True)
                    continue
        else:
            logging.warning(f"Search directory not found at {search_dir}")

        logging.info(f"Final requirements loaded:")
        logging.info(f"Topic: {requirements['topic']}")
        logging.info(f"Guidelines: {requirements['guidelines']}")
        logging.info(f"Key areas: {len(requirements['key_areas'])}")
        if requirements['key_areas']:
            logging.info("Key areas:")
            for area in requirements['key_areas']:
                logging.info(f"  - {area}")
        logging.info(f"Search queries: {len(requirements['search_queries'])}")
        if requirements['search_queries']:
            logging.info("Search queries:")
            for query in requirements['search_queries']:
                logging.info(f"  - {query}")
        
        return requirements
        
    def _chunk_results(self, results):
        """Split search results into smaller chunks based on token limit."""
        chunks = []
        current_chunk = []
        current_size = 0
        total_tokens = 0
        
        logging.info(f"Starting to chunk {len(results)} results...")
        
        for result in results:
            # Accurate token count using the tokenizer
            result_tokens = len(self.tokenizer.encode(str(result)))
            total_tokens += result_tokens
            
            if current_size + result_tokens > self.max_chunk_size:
                if current_chunk:  # Save current chunk if not empty
                    chunks.append(current_chunk)
                    logging.debug(f"Created chunk {len(chunks)} with {current_size} tokens")
                current_chunk = [result]
                current_size = result_tokens
            else:
                current_chunk.append(result)
                current_size += result_tokens
        
        if current_chunk:  # Add the last chunk
            chunks.append(current_chunk)
            logging.debug(f"Created final chunk {len(chunks)} with {current_size} tokens")
            
        logging.info("Chunking complete:")
        logging.info(f"Total tokens: {total_tokens}")
        logging.info(f"Total chunks: {len(chunks)}")
        logging.info(f"Average tokens per chunk: {total_tokens // len(chunks) if chunks else 0}")
        logging.info(f"Max chunk size limit: {self.max_chunk_size}")
            
        return chunks

    def _write_area_article(self, area_name, chunks, research_topic):
        """Write an article for a specific key area by gradually merging chunks."""
        logging.info(f"Starting to write article for area: {area_name}")
        
        # Initialize with empty content
        current_content = ''
        
        for i, chunk in enumerate(chunks):
            chunk_info = f"Chunk {i+1}/{len(chunks)}"
            logging.info(f"Processing {chunk_info} for area: {area_name}")
            
            # Format the chunk data to make titles more explicit
            formatted_chunk = []
            for item in chunk:
                # Log the item structure for debugging
                logging.debug(f"Processing item: {json.dumps(item, indent=2)}")
                
                # Extract title from the item structure
                title = item.get('title', '')
                if not title:
                    # Try to get title from metadata if available
                    title = item.get('metadata', {}).get('title', '')
                if not title:
                    # If still no title, use URL as fallback
                    title = item.get('url', 'Unknown Source')
                    logging.warning(f"No title found for URL: {title}")
                
                formatted_item = {
                    'title': title,
                    'url': item['url'],
                    'excerpts': item['excerpts']
                }
                formatted_chunk.append(formatted_item)
            
            prompt = f"""
            Research Topic: {research_topic}
            Key Area: {area_name}
            
            Based on the following research findings {chunk_info}, update the article for this key area:
            
            Current Article Content:
            {current_content}
            
            New Research Findings:
            {json.dumps(formatted_chunk, indent=2)}
            
            Please update the article to include new findings. The article should:
            1. Provide a comprehensive overview of the key area
            2. Include relevant evidence and examples
            3. Cite sources using markdown links with the exact title from the metadata
               For example, if a source has title "The Future of MCP" and URL "https://example.com",
               use: [The Future of MCP](https://example.com)
               DO NOT use generic text like "Source Title" or "Article"
               If a source has no title, use a descriptive title based on the content
            4. Maintain a logical flow and structure
            5. Integrate new findings with existing content
            6. Highlight important insights and connections to the main research topic
            
            Format the response in markdown with appropriate headers, lists, and emphasis.
            Ensure the content is well-organized and directly relevant to both the key area and main research topic.
            """
            
            try:
                system_prompt = f"""You are a research writer focused on {research_topic}, specifically writing about {area_name}.
Your task is to integrate new research findings into an existing article while maintaining clarity and avoiding redundancy.
Always include source URLs as markdown links using the exact title from the source metadata.
For example, if a source has title "The Future of MCP" and URL "https://example.com",
use: [The Future of MCP](https://example.com)
DO NOT use generic text like "Source Title" or "Article" in the links.
If a source has no title, create a descriptive title based on its content.
Format source references as [Exact Title](URL) and ensure every piece of evidence is properly linked."""
                
                logging.info(f"Sending chunk to LLM for processing...")
                response = self.llm_manager.create_chat_completion(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    max_tokens=8000
                )
                current_content = response
                
                # Save intermediate result
                area_dir = os.path.join(self.working_dir, 'answer_areas')
                os.makedirs(area_dir, exist_ok=True)
                # Create a sanitized filename with numeric prefix
                area_index = self.requirements['key_areas'].index(area_name) + 1
                area_filename = f"{area_index:02d}_{area_name.lower().replace(' ', '_')}.md"
                area_file = os.path.join(area_dir, area_filename)
                self._save_content(current_content, area_file)
                logging.info(f"Saved intermediate article for {area_name} to {area_file}")
                
            except Exception as e:
                logging.error(f"Error processing chunk {i+1} for area {area_name}: {str(e)}", exc_info=True)
                continue
        
        logging.info(f"Completed article for area: {area_name}")
        return current_content

    def _save_content(self, content, target_path):
        """Save content in markdown, HTML, and PDF formats."""
        logging.debug(f"Starting to save content to: {target_path}")
        
        # If target_path is a directory, create answer.md inside it
        if os.path.isdir(target_path):
            answer_md_path = os.path.join(target_path, 'answer.md')
        else:
            # If target_path is a file, use it directly
            answer_md_path = target_path
            # Ensure the directory exists
            os.makedirs(os.path.dirname(answer_md_path), exist_ok=True)
        
        # Save markdown
        logging.debug(f"Attempting to write markdown file to: {answer_md_path}")
        try:
            with open(answer_md_path, 'w') as f:
                f.write(content)
            logging.debug(f"Successfully wrote {len(content)} characters to markdown file")
            logging.info(f"Markdown file saved at: {answer_md_path}")
        except Exception as e:
            logging.error(f"Failed to write markdown file: {str(e)}", exc_info=True)
            raise
            
        # Prepare HTML content with CSS
        css = """
            @page {
                margin: 1in;
                size: letter;
                @bottom-right {
                    content: counter(page);
                }
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                font-size: 12pt;
            }
            a {
                color: #0366d6;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            h1, h2, h3 {
                margin-top: 1.5em;
                margin-bottom: 0.5em;
                color: #24292e;
            }
            code {
                background-color: #f6f8fa;
                padding: 0.2em 0.4em;
                border-radius: 3px;
                font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
                font-size: 85%;
            }
            blockquote {
                border-left: 4px solid #dfe2e5;
                padding-left: 1em;
                color: #6a737d;
                margin: 1em 0;
            }
            @media print {
                a {
                    color: #000;
                    text-decoration: underline;
                }
                a[href]:after {
                    content: " (" attr(href) ")";
                    font-size: 90%;
                }
            }
        """
            
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Research Summary</title>
    <style>
        body {{
            padding: 2em;
            max-width: 800px;
            margin: 0 auto;
        }}
        {css}
    </style>
</head>
<body>
{self.markdown_converter.convert(content)}
</body>
</html>
"""
        # Save HTML
        answer_html_path = os.path.splitext(answer_md_path)[0] + '.html'
        logging.debug(f"Attempting to write HTML file to: {answer_html_path}")
        try:
            with open(answer_html_path, 'w') as f:
                f.write(html_content)
            logging.debug(f"Successfully wrote {len(html_content)} characters to HTML file")
            logging.info(f"HTML file saved at: {answer_html_path}")
        except Exception as e:
            logging.error(f"Failed to write HTML file: {str(e)}", exc_info=True)
            raise
            
        # Generate PDF
        answer_pdf_path = os.path.splitext(answer_md_path)[0] + '.pdf'
        logging.debug(f"Attempting to generate PDF file at: {answer_pdf_path}")
        try:
            HTML(string=html_content).write_pdf(
                answer_pdf_path,
                stylesheets=[CSS(string=css)]
            )
            logging.debug("Successfully generated PDF file")
            logging.info(f"PDF file saved at: {answer_pdf_path}")
        except Exception as e:
            logging.error(f"Failed to generate PDF file: {str(e)}", exc_info=True)
            raise
            
        logging.debug("All output files have been successfully generated")

    def summarize(self, research_topic):
        """Generate a comprehensive summary of the research findings."""
        try:
            # Load research requirements
            self.requirements = self._load_research_requirements(self.working_dir, research_topic)
            
            # Initialize local searcher
            searcher = LocalSearchEngine(self.working_dir)
            
            # Process each key area
            area_articles = {}
            logging.info(f"Processing {len(self.requirements['key_areas'])} key areas...")
            
            for i, area in enumerate(self.requirements['key_areas'], 1):
                try:
                    logging.info(f"Processing key area {i}/{len(self.requirements['key_areas'])}: {area}")
                    
                    # Search for content related to this key area
                    results = searcher.search_similar(area, k=20)
                    
                    # Group results by URL
                    url_groups = {}
                    for result in results:
                        url = result['url']
                        if url not in url_groups:
                            url_groups[url] = {
                                'key_area': area,
                                'title': result['metadata']['title'],
                                'url': url,
                                'excerpts': []
                            }
                        url_groups[url]['excerpts'].append({
                            'content': result['content'],
                            'score': result['score']
                        })
                    
                    # Split results into chunks
                    chunks = self._chunk_results(list(url_groups.values()))
                    
                    # Write article for this area
                    article_content = self._write_area_article(area, chunks, self.requirements['topic'])
                    area_articles[area] = article_content
                    
                    logging.info(f"Completed article for area: {area}")
                    
                except Exception as e:
                    logging.error(f"Error processing key area '{area}': {str(e)}", exc_info=True)
                    continue
            
            # Generate final summary by combining all area articles
            final_content = f"# Research Summary: {self.requirements['topic']}\n\n"
            
            # Add guidelines
            final_content += "## Research Guidelines\n\n"
            for guideline in self.requirements['guidelines']:
                final_content += f"- {guideline}\n"
            final_content += "\n"
            
            for area, content in area_articles.items():
                final_content += f"## {area}\n\n{content}\n\n"
            
            # Save the final summary
            self._save_content(final_content, self.working_dir)
            logging.info("Successfully generated final research summary")
                
        except Exception as e:
            logging.error(f"Error: {str(e)}", exc_info=True)

def main():
    """
    Main function to run the summarizer.
    Usage: python summarizer.py --working-dir <path>
    """
    parser = argparse.ArgumentParser(description='Research Content Summarizer')
    parser.add_argument('--working-dir', type=str, required=True,
                      help='Working directory containing research.md and analysis files')
    args = parser.parse_args()
    
    try:
        # Validate working directory
        if not os.path.exists(args.working_dir):
            raise ValueError(f"Working directory {args.working_dir} does not exist")
            
        # Check if directory has required structure
        for required_dir in ['index', 'plan']:
            dir_path = os.path.join(args.working_dir, required_dir)
            if not os.path.exists(dir_path):
                raise ValueError(f"Required directory not found: {dir_path}")
        
        research_path = os.path.join(args.working_dir, 'research.md')
        if not os.path.exists(research_path):
            raise ValueError(f"research.md not found in {args.working_dir}")
        
        # Initialize summarizer and process the directory
        summarizer = Summarizer(args.working_dir)
        logging.info(f"Processing directory: {args.working_dir}")
        summarizer.summarize()
        logging.info(f"Successfully generated document for {args.working_dir}")
                
    except Exception as e:
        logging.error(f"Error: {str(e)}", exc_info=True)
        return

if __name__ == '__main__':
    main()