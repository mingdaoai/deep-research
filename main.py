#! /usr/bin/env python3
import os
import sys
import argparse
import logging
from src.research_orchestrator import ResearchOrchestrator
from src.utils import validate_working_dir

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('research_agent.log')
        ]
    )

def main():
    parser = argparse.ArgumentParser(description='Research Agent')
    parser.add_argument('working_dir', type=str,
                      help='Working directory containing research.md')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Validate and setup working directory
        validate_working_dir(args.working_dir)
        
        # Initialize and run research orchestrator
        logging.info(f"Starting research process in {args.working_dir}")
        orchestrator = ResearchOrchestrator(args.working_dir)
        orchestrator.run()
        logging.info("Research process completed successfully")
        
    except Exception as e:
        logging.error(f"Error during research process: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()