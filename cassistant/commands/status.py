import os
from .files import get_project_files
from ..utils.printer import print_info, print_error, print_success, print_warning
from ..config import load_config
from ..hasher import calculate_sha256, extract_hash_from_md

def check_status() -> dict:
    files = get_project_files()
    config = load_config()
    doc_dir = config.project_doc_dir
    docs_folder = os.path.join(doc_dir, "docs")
    
    clean_files = []
    dirty_files = []
    missing_files = []
    
    for filepath in files:
        filename_md = os.path.basename(filepath) + ".md"
        md_path = os.path.join(docs_folder, filename_md)
        
        if not os.path.exists(md_path):
            missing_files.append(filepath)
            continue
            
        current_hash = calculate_sha256(filepath)
        saved_hash = extract_hash_from_md(md_path)
        
        if current_hash == saved_hash:
            clean_files.append(filepath)
        else:
            dirty_files.append(filepath)
            
    return {
        "clean": clean_files,
        "dirty": dirty_files,
        "missing": missing_files
    }

def run_status():
    print_info("Checking documentation synchronization status...")
    status = check_status()
    
    total = len(status["clean"]) + len(status["dirty"]) + len(status["missing"])
    if total == 0:
        print_warning("No tracked source files found.")
        return

    print_info(f"Summary: {len(status['clean'])}/{total} files are up to date.")
    
    if status["clean"]:
        print_success("Up to date files:")
        for f in status["clean"]:
            print_success(f"  - {f}")
            
    if status["dirty"]:
        print_warning("Dirty files (modified but not synchronized):")
        for f in status["dirty"]:
            print_warning(f"  - {f}")
            
    if status["missing"]:
        print_error("Missing documentation files:")
        for f in status["missing"]:
            print_error(f"  - {f}")
            
    if status["dirty"] or status["missing"]:
        print_info("\nRun 'cass update --dirty' to synchronize changes.")
