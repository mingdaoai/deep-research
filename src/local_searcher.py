import os
import json
import argparse
from typing import Dict, List, Any
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.schema import Document

class LocalSearchEngine:
    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.index_dir = os.path.join(working_dir, 'index')
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
    def search_similar(self, query: str, k: int = 20) -> List[Dict[str, Any]]:
        """Search for similar content in the index."""
        index_path = os.path.join(self.index_dir, 'faiss')
        if not os.path.exists(index_path):
            raise ValueError("No index found. Please run indexing first.")
            
        vector_store = FAISS.load_local(
            index_path, 
            self.embeddings,
            allow_dangerous_deserialization=True  # Safe since we created the index ourselves
        )
        results = vector_store.similarity_search_with_score(query, k=k)
        
        return [{
            'content': doc.page_content,
            'metadata': doc.metadata,
            'url': doc.metadata['url'],  # Add direct URL access
            'score': float(score)  # Convert numpy.float32 to Python float
        } for doc, score in results]

def main():
    parser = argparse.ArgumentParser(description='Search local research content')
    parser.add_argument('--working-dir', type=str, required=True,
                      help='Working directory containing indexed content')
    parser.add_argument('--query', type=str, required=True,
                      help='Search query')
    parser.add_argument('--num-results', type=int, default=5,
                      help='Number of results to return')
    args = parser.parse_args()
    
    # Validate working directory
    if not os.path.exists(args.working_dir):
        raise ValueError(f"Working directory {args.working_dir} does not exist")
        
    index_dir = os.path.join(args.working_dir, 'index')
    if not os.path.exists(index_dir):
        raise ValueError(f"Index directory not found: {index_dir}")
    
    # Initialize and run search
    searcher = LocalSearchEngine(args.working_dir)
    results = searcher.search_similar(args.query, args.num_results)
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main() 