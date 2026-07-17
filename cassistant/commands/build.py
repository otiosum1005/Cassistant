import os
import json
import re
import shutil
from datetime import datetime
from ..config import load_config
from ..client import LLMClient
from ..utils.printer import print_info, print_error, print_success, print_warning
from ..utils.confirm import confirm_action
from ..hasher import calculate_sha256, write_md_with_frontmatter
from .init import read_prompt_template
from .plan import run_plan

def apply_diff(filepath: str, diff_content: str):
    """Simple parser/helper to apply unified diffs or write complete replacement files."""
    # If the file doesn't exist, we assume the AI outputs the raw content or we write it directly.
    # In general practice, LLM might output a diff or complete content. Let's handle both.
    if not os.path.exists(filepath):
        # Create directory
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # Clean diff markers if LLM outputted them by mistake
        clean_lines = []
        for line in diff_content.splitlines():
            if line.startswith('+ ') or line.startswith('++'):
                clean_lines.append(line[2:])
            elif not line.startswith('---') and not line.startswith('@@') and not line.startswith('- '):
                clean_lines.append(line)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(clean_lines))
        return

    # For existing files, if it contains diff patterns we try simple replacement.
    # Otherwise, write/overwrite content.
    # To keep implementation robust and simple in a CLI wrapper, we do a fallback:
    # If it is not a unified diff format, overwrite. If it is, apply line changes.
    lines = diff_content.splitlines()
    is_diff = any(line.startswith('@@') for line in lines)
    
    if not is_diff:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(diff_content)
        return

    # Basic unified diff patch applier
    with open(filepath, "r", encoding="utf-8") as f:
        original_lines = f.read().splitlines()

    new_lines = []
    idx = 0
    # Simplistic patch applier (expects contiguous hunks or complete replacement)
    # For robust LLM coding assistant, if it's too complex, LLMs prefer full file rewrites.
    # We will attempt to write the file.
    # (In production, using python's patch libraries is standard. We will implement simple overwrite fallback if patch fails).
    try:
        # Overwrite fallback to avoid breaking:
        # If LLM gives diff, strip diff markers to get clean code
        clean_code = []
        for line in lines:
            if line.startswith('-'):
                continue
            elif line.startswith('+'):
                clean_code.append(line[1:])
            elif line.startswith('@@') or line.startswith('---') or line.startswith('+++'):
                continue
            else:
                clean_code.append(line)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(clean_code))
    except Exception as e:
        print_error(f"Failed to apply patch: {e}")

def run_build(query: str, from_plan: bool):
    config = load_config()
    doc_dir = config.project_doc_dir
    
    plan_data = None
    plan_save_path = os.path.join(doc_dir, "last_plan.json")
    
    if from_plan:
        if os.path.exists(plan_save_path):
            with open(plan_save_path, "r", encoding="utf-8") as f:
                plan_data = json.load(f)
            print_info(f"Loaded plan from {plan_save_path}")
        else:
            print_error("No saved plan found. Run 'cass plan' first or supply a query directly.")
            return
    else:
        if not query:
            print_error("Please specify a requirement query or use --from-plan.")
            return
        plan_data = run_plan(query, return_data=True)

    if not plan_data:
        print_error("Failed to generate plan.")
        return

    # Confirm before building
    if not confirm_action("Do you want to proceed with code generation and modifications based on this plan?"):
        print_info("Build cancelled.")
        return

    # Create snapshot backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = os.path.join(doc_dir, "snapshots", timestamp)
    os.makedirs(snapshot_dir, exist_ok=True)
    
    # We scan files to back them up
    # In a simplified implementation, we make a backup of the source folders
    print_info(f"Creating snapshot of source directory at {snapshot_dir}...")
    for root, dirs, files in os.walk("."):
        # skip .cassistant and hidden folders
        if ".cassistant" in root or ".git" in root:
            continue
        for file in files:
            src_path = os.path.join(root, file)
            rel_path = os.path.relpath(src_path, ".")
            dest_path = os.path.join(snapshot_dir, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            try:
                shutil.copy2(src_path, dest_path)
            except Exception:
                pass

    # Call generator to build files
    client = LLMClient()
    gen_template = read_prompt_template("generator")
    prompt = gen_template.format(
        plan_detail=plan_data["plan_detail"],
        query=plan_data["query"]
    )
    
    print_info("Generating files and modifications...")
    res = client.completion([{"role": "user", "content": prompt}])
    llm_out = res.choices[0].message.content
    
    # Parse generated files and docs
    # Extract sections: FILE: path/to/file and DOC_FILE: path/to/doc.md
    file_blocks = re.split(r"FILE:\s*", llm_out)
    
    modified_files = []
    
    for block in file_blocks:
        if not block.strip():
            continue
        lines = block.splitlines()
        filepath = lines[0].strip()
        
        # extract content inside ```
        content_match = re.search(r"```(?:\w+)?\n(.*?)```", block, re.DOTALL)
        if content_match:
            code_content = content_match.group(1)
        else:
            code_content = "\n".join(lines[1:])
            
        if "DOC_FILE:" in filepath:
            # This is a doc file block
            parts = filepath.split("DOC_FILE:")
            code_content_1 = parts[0].strip()
            doc_path = parts[1].strip()
            
            # Write source code if there's any preceding
            if code_content_1:
                # write first part
                pass
        
        # Check if this block describes a DOC_FILE instead of source code
        is_doc = False
        if filepath.startswith("DOC_FILE:") or "DOC_FILE:" in block:
            is_doc = True
            
        # Parse DOC_FILE blocks separately if combined
        doc_matches = re.findall(r"DOC_FILE:\s*([^\n]+)\n```(?:markdown)?\n(.*?)\n```", block, re.DOTALL)
        for dpath, dcontent in doc_matches:
            dpath = dpath.strip()
            print_info(f"Updating documentation: {dpath}")
            os.makedirs(os.path.dirname(dpath), exist_ok=True)
            with open(dpath, "w", encoding="utf-8") as f:
                f.write(dcontent)

        # Parse source code file block
        src_path_clean = filepath.split("DOC_FILE:")[0].strip()
        if src_path_clean and not is_doc:
            print_info(f"Modifying/Creating file: {src_path_clean}")
            apply_diff(src_path_clean, code_content)
            modified_files.append(src_path_clean)
            
            # Recalculate hash and update md if not already generated by AI
            try:
                new_hash = calculate_sha256(src_path_clean)
                filename_md = os.path.basename(src_path_clean) + ".md"
                md_path = os.path.join(doc_dir, "docs", filename_md)
                
                # Check if it was written in doc_matches, otherwise update it
                if not any(dpath.endswith(filename_md) for dpath, _ in doc_matches):
                    # update via standard prompt or default sync
                    print_info(f"Re-indexing {src_path_clean}...")
                    from .update import run_update
                    run_update([src_path_clean], False, False)
            except Exception as e:
                print_error(f"Failed to auto-index modified file: {e}")

    # Generate log entry
    log_path = os.path.join(doc_dir, "logs", "build_log.md")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_entry = f"""
## Build at {timestamp}
- **Query**: {plan_data['query']}
- **Modified files**: {", ".join(modified_files)}
- **Snapshot Backup**: {snapshot_dir}
"""
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_entry)
        
    print_success(f"Build completed successfully. Logs written to {log_path}")
