import os
import json
import glob
import argparse
from pathlib import Path
from typing import Dict, List, Any
from transformers import GPT2TokenizerFast
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import TokenTextSplitter
from langchain.schema import Document

class ContentIndexer:
    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.index_dir = os.path.join(working_dir, 'index')
        os.makedirs(self.index_dir, exist_ok=True)
        
        # Initialize tokenizer and text splitter
        self.tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
        self.text_splitter = TokenTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
    def _load_downloaded_content(self) -> List[Dict[str, Any]]:
        """Load all downloaded content from results directory."""
        results = []
        results_dir = os.path.join(self.working_dir, 'results')
        if not os.path.exists(results_dir):
            return results
            
        for file_path in glob.glob(os.path.join(results_dir, 'downloaded_content_*.json')):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    if isinstance(content, dict) and 'results' in content:
                        # Extract query and requirements for context
                        query = content.get('query', '')
                        requirements = content.get('requirements', [])
                        
                        # Process each successful result
                        for result in content['results']:
                            if result.get('success', False):
                                results.append({
                                    'url': result['url'],
                                    'title': result['title'],
                                    'text': result['text'],
                                    'query': query,
                                    'requirements': requirements
                                })
            except Exception as e:
                print(f"Error loading {file_path}: {str(e)}")
                continue
        return results
        
    def _split_and_save_chunks(self, documents: List[Dict[str, Any]]) -> str:
        """Split documents into chunks and save as JSONL."""
        chunks_file = os.path.join(self.index_dir, 'chunks.jsonl')
        
        with open(chunks_file, 'w', encoding='utf-8') as f:
            for doc in documents:
                # Create a document for text splitting
                text_doc = Document(
                    page_content=doc['text'],
                    metadata={
                        'url': doc['url'],
                        'title': doc['title'],
                        'query': doc['query'],
                        'requirements': doc['requirements']
                    }
                )
                
                # Split into chunks
                chunks = self.text_splitter.split_documents([text_doc])
                
                # Save each chunk
                for chunk in chunks:
                    json.dump({
                        'text': chunk.page_content,
                        'metadata': chunk.metadata
                    }, f)
                    f.write('\n')
                    
        return chunks_file
        
    def _create_or_load_vector_store(self) -> FAISS:
        """Create new or load existing FAISS index."""
        index_path = os.path.join(self.index_dir, 'faiss')
        try:
            if os.path.exists(index_path):
                print("Loading existing FAISS index...")
                return FAISS.load_local(
                    index_path, 
                    self.embeddings,
                    allow_dangerous_deserialization=True  # Safe since we created the index ourselves
                )
        except Exception as e:
            print(f"Error loading existing index: {str(e)}")
            
        print("Creating new FAISS index...")
        return FAISS.from_documents(
            [Document(page_content="", metadata={})],  # Empty document to initialize
            self.embeddings
        )
        
    def _update_vector_store(self, chunks_file: str, vector_store: FAISS):
        """Update vector store with new chunks."""
        chunk_count = 0
        with open(chunks_file, 'r', encoding='utf-8') as f:
            batch = []
            for line in f:
                data = json.loads(line)
                doc = Document(
                    page_content=data['text'],
                    metadata=data['metadata']
                )
                batch.append(doc)
                chunk_count += 1
                
                # Process in batches of 100
                if len(batch) >= 100:
                    vector_store.add_documents(batch)
                    print(f"Processed {chunk_count} chunks...")
                    batch = []
                    
            # Process remaining documents
            if batch:
                vector_store.add_documents(batch)
                
        print(f"Total chunks processed: {chunk_count}")
        
    def index_content(self, iteration: int = None):
        """
        Main method to index all downloaded content.
        If iteration is provided, only index content from that iteration.
        """
        print("Loading downloaded content...")
        documents = self._load_downloaded_content()
        if not documents:
            print("No documents found to index.")
            return
            
        print(f"Found {len(documents)} documents to process.")
        
        print("Splitting documents into chunks...")
        chunks_file = self._split_and_save_chunks(documents)
        
        print("Initializing vector store...")
        vector_store = self._create_or_load_vector_store()
        
        print("Updating vector store with new chunks...")
        self._update_vector_store(chunks_file, vector_store)
        
        print("Saving updated index...")
        vector_store.save_local(os.path.join(self.index_dir, 'faiss'))
        
        print("Indexing complete!")

def main():
    parser = argparse.ArgumentParser(description='Index downloaded research content')
    parser.add_argument('--working-dir', type=str, required=True,
                      help='Working directory containing research content')
    args = parser.parse_args()
    
    # Validate working directory
    if not os.path.exists(args.working_dir):
        raise ValueError(f"Working directory {args.working_dir} does not exist")
        
    results_dir = os.path.join(args.working_dir, 'results')
    if not os.path.exists(results_dir):
        raise ValueError(f"Results directory not found: {results_dir}")
    
    # Initialize and run indexer
    indexer = ContentIndexer(args.working_dir)
    indexer.index_content()

if __name__ == "__main__":
    main() 