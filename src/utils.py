import os
import json

REQUIRED_SUBDIRS = ['plan', 'search', 'results', 'analysis', 'index', 'cache']

def validate_working_dir(working_dir):
    """Validate and setup the working directory structure."""
    if not os.path.exists(working_dir):
        raise ValueError(f"Working directory {working_dir} does not exist")
        
    research_path = os.path.join(working_dir, 'research.md')
    if not os.path.exists(research_path):
        raise ValueError(f"research.md not found in {working_dir}")
    
    # Create all required subdirectories
    for subdir in REQUIRED_SUBDIRS:
        os.makedirs(os.path.join(working_dir, subdir), exist_ok=True)
        
    return research_path

def get_output_paths(working_dir):
    """Get paths for output files."""
    return {
        'markdown': os.path.join(working_dir, 'answer.md'),
        'html': os.path.join(working_dir, 'answer.html'),
        'pdf': os.path.join(working_dir, 'answer.pdf')
    }

def save_json_file(data, directory, filename, iteration=None):
    """Save JSON data to a file with optional iteration number."""
    os.makedirs(directory, exist_ok=True)
    if iteration is not None:
        filename = f"{filename}_{iteration}.json"
    with open(os.path.join(directory, filename), 'w') as f:
        json.dump(data, f, indent=2)

def read_json_file(filepath):
    """Read JSON data from a file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None 