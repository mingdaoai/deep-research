import os
import sys
import argparse
import logging
from src.summarizer import Summarizer
from src.utils import validate_working_dir, get_output_paths

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('summarizer.log')
        ]
    )

def main():
    parser = argparse.ArgumentParser(description='Research Summarizer')
    parser.add_argument('--working-dir', type=str, required=True,
                      help='Working directory containing research.md')
    parser.add_argument('--format', choices=['markdown', 'html', 'pdf', 'all'],
                      default='all', help='Output format(s) to generate')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Validate working directory
        validate_working_dir(args.working_dir)
        
        # Initialize and run summarizer
        logging.info(f"Starting summarization process in {args.working_dir}")
        summarizer = Summarizer(args.working_dir)
        
        # Get output paths
        output_paths = get_output_paths(args.working_dir)
        
        # Generate requested formats
        formats = ['markdown', 'html', 'pdf'] if args.format == 'all' else [args.format]
        for fmt in formats:
            output_path = output_paths[fmt]
            logging.info(f"Generating {fmt} summary at {output_path}")
            summarizer.summarize(fmt=fmt, output_path=output_path)
            
        logging.info("Summarization completed successfully")
        
    except Exception as e:
        logging.error(f"Error during summarization: {str(e)}", exc_info=args.debug)
        sys.exit(1)

if __name__ == "__main__":
    main() 