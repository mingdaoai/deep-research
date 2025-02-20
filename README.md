# Research Sync Agent

An AI-powered research assistant that helps automate the process of conducting research, analyzing sources, and generating comprehensive summaries. The agent uses advanced language models to process and synthesize information from multiple sources.

## Features

- Automated research planning and execution
- Web content search and downloading
- Local content indexing and semantic search
- AI-powered content analysis and summarization
- Multi-format output generation (Markdown, HTML, PDF)
- Chunked processing for handling large research datasets
- Source tracking and citation management
- All intermediate results saved for transparency

## Prerequisites

- Python 3.8+
- Required Python packages (see requirements.txt)
- Internet connection for web searches
- Environment variables:
  - Groq API key stored in `~/.mingdaoai/groq.key`

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create the Groq API key file:
   ```bash
   mkdir -p ~/.mingdaoai
   echo "your_api_key_here" > ~/.mingdaoai/groq.key
   ```

## Usage

1. Create a directory for your research project
2. Create a `research.md` file in that directory describing your research topic and requirements
3. Run the research agent:
   ```bash
   python main.py /path/to/your/research/directory
   ```

The agent will:
1. Create necessary subdirectories (plan, search, results, analysis)
2. Process your research requirements
3. Execute searches and download relevant content
4. Index and analyze the content
5. Generate comprehensive summaries in multiple formats:
   - Markdown (answer.md)
   - HTML (answer.html)
   - PDF (answer.pdf)

## Directory Structure