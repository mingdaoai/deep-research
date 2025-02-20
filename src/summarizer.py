import os
import json
import argparse
from dotenv import load_dotenv
import markdown  # Add markdown package for HTML conversion
from weasyprint import HTML, CSS  # Add weasyprint for PDF generation
from transformers import AutoTokenizer  # Add tokenizer import
from .llm_client import LLMClientManager
from .local_searcher import LocalSearchEngine

class Summarizer:
    def __init__(self, working_dir):
        self.llm_manager = LLMClientManager.get_instance(working_dir)
        self.max_chunk_size = 8000  # Maximum tokens per chunk for processing
        self.markdown_converter = markdown.Markdown(extensions=['extra'])  # Initialize markdown converter with extra features
        # Initialize tokenizer for accurate token counting
        self.tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/deepseek-llm-7b-base")
        
    def _load_research_requirements(self, working_dir):
        """Load research requirements from research.md and search plan files."""
        requirements = {
            'topic': '',
            'key_areas': [],
            'search_queries': []
        }

        # Read main research topic from research.md
        research_md_path = os.path.join(working_dir, 'research.md')
        if os.path.exists(research_md_path):
            with open(research_md_path, 'r') as f:
                requirements['topic'] = f.read().strip()

        # Read requirements from search plan files
        search_dir = os.path.join(working_dir, 'search')
        if os.path.exists(search_dir):
            # Get all plan files
            plan_files = os.listdir(search_dir)
            plan_files = [f for f in plan_files 
                         if f.startswith('search_plan_') and f.endswith('.json')]
            for filename in plan_files:
                file_path = os.path.join(search_dir, filename)
                try:
                    with open(file_path, 'r') as f:
                        plan_data = json.load(f)
                        if 'key_areas' in plan_data:
                            requirements['key_areas'].extend(
                                area for area in plan_data['key_areas'] 
                                if area not in requirements['key_areas']
                            )
                        if 'search_queries' in plan_data:
                            requirements['search_queries'].extend(
                                query for query in plan_data['search_queries']
                                if query not in requirements['search_queries']
                            )
                except Exception as e:
                    print(f"Error loading search plan file {filename}: {str(e)}")
                    continue

        return requirements
        
    def _chunk_results(self, results):
        """Split search results into smaller chunks based on token limit."""
        chunks = []
        current_chunk = []
        current_size = 0
        total_tokens = 0
        
        print(f"\nStarting to chunk {len(results)} results...")
        
        for result in results:
            # Accurate token count using the tokenizer
            result_tokens = len(self.tokenizer.encode(str(result)))
            total_tokens += result_tokens
            
            if current_size + result_tokens > self.max_chunk_size:
                if current_chunk:  # Save current chunk if not empty
                    chunks.append(current_chunk)
                    print(f"Created chunk {len(chunks)} with {current_size} tokens")
                current_chunk = [result]
                current_size = result_tokens
            else:
                current_chunk.append(result)
                current_size += result_tokens
        
        if current_chunk:  # Add the last chunk
            chunks.append(current_chunk)
            print(f"Created final chunk {len(chunks)} with {current_size} tokens")
            
        print(f"\nChunking complete:")
        print(f"Total tokens: {total_tokens}")
        print(f"Total chunks: {len(chunks)}")
        print(f"Average tokens per chunk: {total_tokens // len(chunks) if chunks else 0}")
        print(f"Max chunk size limit: {self.max_chunk_size}\n")
            
        return chunks

    def _save_content(self, content, working_dir):
        """Save content in markdown, HTML, and PDF formats."""
        # Save markdown
        answer_md_path = os.path.join(working_dir, 'answer.md')
        with open(answer_md_path, 'w') as f:
            f.write(content)
        print(f"Markdown file saved at: {answer_md_path}")
            
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
        answer_html_path = os.path.join(working_dir, 'answer.html')
        with open(answer_html_path, 'w') as f:
            f.write(html_content)
        print(f"HTML file saved at: {answer_html_path}")
            
        # Generate PDF
        answer_pdf_path = os.path.join(working_dir, 'answer.pdf')
        HTML(string=html_content).write_pdf(
            answer_pdf_path,
            stylesheets=[CSS(string=css)]
        )
        print(f"PDF file saved at: {answer_pdf_path}")

    def summarize(self, working_dir):
        """
        Generate or update the answer file.
        Uses local search to find relevant content.
        Takes into account research requirements from research.md and plan files.
        """
        # Remove existing output files if they exist
        for file_name in ['answer.md', 'answer.html', 'answer.pdf']:
            file_path = os.path.join(working_dir, file_name)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"Removed existing file: {file_path}")
                except Exception as e:
                    print(f"Error removing {file_path}: {str(e)}")

        # Initialize with empty content
        current_content = ''
        
        # Load research requirements
        requirements = self._load_research_requirements(working_dir)
        
        # Initialize local searcher
        searcher = LocalSearchEngine(working_dir)
        
        # Search for content related to each key area
        all_results = []
        print(f"\nSearching content for {len(requirements['key_areas'])} key areas...")
        for i, area in enumerate(requirements['key_areas'], 1):
            try:
                print(f"\nProcessing key area {i}/{len(requirements['key_areas'])}: {area}")
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
                all_results.extend(url_groups.values())
                print(f"Found {len(url_groups)} unique URLs for this key area")
            except Exception as e:
                print(f"Error searching for key area '{area}': {str(e)}")
                continue
        
        # Split results into manageable chunks
        chunks = self._chunk_results(all_results)
        
        # Process each chunk
        total_chunks = len(chunks)
        print(f"\nStarting to process {total_chunks} chunks...")
        
        for i, chunk in enumerate(chunks):
            chunk_info = f"Chunk {i+1}/{total_chunks}"
            print(f"\n{'='*20} Processing {chunk_info} {'='*20}")
            print(f"Chunk contains {len(chunk)} URL groups")
            
            prompt = f"""
            Research Topic: {requirements['topic']}
            
            Key Research Areas:
            {chr(10).join('- ' + area for area in requirements['key_areas'])}
            
            Based on the following research findings {chunk_info}, update the answer document:
            
            Current Answer Document:
            {current_content}
            
            New Research Findings:
            {json.dumps(chunk, indent=2)}
            
            Please update the document to include new findings. The document should have:
            1. Main Findings and Conclusions - specifically addressing the key research areas
            2. Supporting Evidence
            3. Notable Quotes from Sources (include source URLs as markdown links)
            4. Areas Needing Further Investigation
            
            Format the response in markdown with appropriate headers, lists, and emphasis.
            When referencing sources or quotes, always include the source URL as a markdown link.
            For example: [Source Title](URL) or quote from [Source Title](URL).
            Integrate new findings with existing content when appropriate.
            Keep the document well-organized and avoid redundancy.
            Ensure the content directly addresses the research topic and key areas.
            """
            
            try:
                system_prompt = f"""You are a research document writer focused on {requirements['topic']}. 
Your task is to integrate new research findings into an existing document while maintaining clarity and avoiding redundancy.
Always include source URLs as markdown links when referencing content or quotes from sources.
Format source references as [Source Title](URL) and ensure every piece of evidence is properly linked."""
                
                print(f"Sending chunk to LLM for processing...")
                response = self.llm_manager.create_chat_completion(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    max_tokens=8000
                )
                current_content = response
                
                # Save intermediate result
                print(f"Saving intermediate result...")
                self._save_content(current_content, working_dir)
                print(f"Completed {chunk_info} ({((i+1)/total_chunks)*100:.1f}% done)")
                    
            except Exception as e:
                print(f"Error processing chunk {i+1}: {str(e)}")
                continue
        
        print(f"\nSummarization complete! Processed {total_chunks} chunks.")

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
        print(f"\nProcessing directory: {args.working_dir}")
        summarizer.summarize(args.working_dir)
        print(f"Successfully generated document for {args.working_dir}")
                
    except Exception as e:
        print(f"Error: {str(e)}")
        return

if __name__ == '__main__':
    main()