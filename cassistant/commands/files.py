import os
import glob
from ..config import load_config
from ..utils.printer import print_info, print_error, print_success, print_warning

def get_project_files() -> list:
    """Scan directory for project source files based on configuration rules."""
    config = load_config()
    
    # Simple manual glob scanning supporting include patterns
    all_matched = set()
    for pattern in config.project_include:
        # Recursive glob search
        files = glob.glob(pattern, recursive=True)
        for f in files:
            # Normalize path
            norm_f = os.path.normpath(f).replace("\\", "/")
            if os.path.isfile(norm_f):
                all_matched.add(norm_f)
                
    # Filter using exclude patterns
    excluded = set()
    for pattern in config.project_exclude:
        # We can perform simple matching or use fnmatch
        import fnmatch
        for f in all_matched:
            # We match relative to current path
            if fnmatch.fnmatch(f, pattern) or any(fnmatch.fnmatch(p, pattern) for p in f.split('/')):
                excluded.add(f)
                
    final_files = sorted(list(all_matched - excluded))
    return final_files
