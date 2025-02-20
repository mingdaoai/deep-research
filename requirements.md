The research agent accepts a command line argument specifying the working directory.

This directory contains a research.md file outlining the research topic. The agent creates output files in three formats:
* answer.md - Main markdown format summary
* answer.html - HTML version with responsive styling
* answer.pdf - PDF version with proper formatting and page numbers

Component Architecture:
* ResearchOrchestrator: Coordinates the research process and manages file I/O
* LLMClientManager: Manages LLM client (singleton) for inference, supports both Groq and Ollama
* ResearchPlanner: Creates search strategies using LLM
* WebSearchEngine: Performs web searches using DuckDuckGo
* ContentDownloader: Downloads and processes web content using both direct requests and browser automation
* LocalSearchEngine: Performs local content search using vector embeddings
* Summarizer: Generates final documents by analyzing and summarizing research findings, with support for markdown, HTML, and PDF output
* BrowserManager: Manages Chrome browser instance (singleton)
* ContentIndexer: Indexes downloaded content for local search

Research Process:
1. Planning Phase:
   * Use LLM to create a research plan with search queries
   * Save the plan in JSON format in the search/ subdirectory

2. Search Phase:
   * Use browser automation with Selenium to search DuckDuckGo
   * Record queries and results in JSON format within the search/ subdirectory
   * Implement rate limiting and retries for reliability

3. Content Collection:
   * Download search results using both direct requests and browser automation
   * Support both HTML and PDF content types
   * Implement content caching in cache/ directory (24-hour expiration)
   * Save downloaded content in JSON format in the results/ subdirectory

4. Content Indexing:
   * Index downloaded content for efficient local search
   * Store index files in the index/ subdirectory
   * Support vector-based semantic search

5. Document Generation:
   * Use LLM to generate comprehensive answer document
   * Process content in chunks to handle large datasets
   * Use local search to find relevant content for each key area
   * Create well-structured output in multiple formats:
     - Markdown with source links and quotes
     - HTML with responsive design and styling
     - PDF with proper pagination and formatting
   * Content includes:
     - Main findings and conclusions
     - Supporting evidence
     - Notable quotes from sources (with clickable links)
     - Areas needing further investigation

Dependencies:
* Chrome browser and ChromeDriver for web automation
* Groq API key or Ollama running locally for LLM inference
* Python packages:
  - selenium: Browser automation
  - beautifulsoup4: HTML parsing
  - requests: HTTP client
  - pdfplumber: PDF processing
  - groq: Groq API client
  - python-dotenv: Environment variable management
  - markdown: Markdown to HTML conversion
  - weasyprint: HTML to PDF conversion
  - transformers: Token counting and text processing
