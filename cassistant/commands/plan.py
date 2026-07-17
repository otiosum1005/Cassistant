import os
import json
import re
from ..config import load_config
from ..client import LLMClient
from ..utils.printer import print_info, print_error, print_success, print_warning
from ..utils.confirm import confirm_action
from .status import check_status
from .init import read_prompt_template

def run_plan(query: str, return_data: bool = False):
    config = load_config()
    doc_dir = config.project_doc_dir
    
    # 1. Hash verification and warning
    status = check_status()
    if status["dirty"] or status["missing"]:
        print_warning("The following files are modified or missing index files:")
        for f in status["dirty"] + status["missing"]:
            print_warning(f"  - {f}")
        if not confirm_action("Indices might be out of date. Do you want to continue planning anyway?"):
            print_info("Cancelled planning.")
            return None

    # Load master readme
    readme_path = os.path.join(doc_dir, "readme.md")
    if not os.path.exists(readme_path):
        print_error("Project has not been initialized. Please run 'cass init' first.")
        return None
        
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()

    client = LLMClient()
    plan_template = read_prompt_template("plan")
    
    print_info("Analyzing user requirement and project index...")
    prompt = plan_template.format(readme_content=readme_content, query=query)
    
    res = client.completion([{"role": "user", "content": prompt}])
    llm_out = res.choices[0].message.content
    print_info(llm_out)
    
    # Parse relevant docs
    relevant_files = []
    match = re.search(r"RELEVANT_FILES:\s*\[(.*?)\]", llm_out)
    if match:
        files_str = match.group(1)
        relevant_files = [f.strip() for f in files_str.split(",") if f.strip()]
        
    # Load detailed docs content
    detailed_docs_content = ""
    docs_folder = os.path.join(doc_dir, "docs")
    for r_file in relevant_files:
        # Resolve path
        doc_path = os.path.join(docs_folder, r_file)
        if not os.path.exists(doc_path):
            # Try appending .md if not present
            if not r_file.endswith(".md"):
                doc_path = os.path.join(docs_folder, r_file + ".md")
        if os.path.exists(doc_path):
            with open(doc_path, "r", encoding="utf-8") as f:
                detailed_docs_content += f"## Document: {r_file}\n" + f.read() + "\n"
        else:
            print_warning(f"Doc file {r_file} not found under .cassistant/docs/")

    # Prompt user if source code is needed
    source_code_content = ""
    needed_sources = []
    
    build_template = read_prompt_template("build")
    build_prompt = build_template.format(
        readme_content=readme_content,
        detailed_docs_content=detailed_docs_content,
        source_code_content="None loaded yet.",
        query=query
    )
    
    print_info("Formulating plan using relevant modules documentation...")
    res2 = client.completion([{"role": "user", "content": build_prompt}])
    llm_plan_out = res2.choices[0].message.content
    print_info("\n=== Formulation Plan ===")
    print_info(llm_plan_out)

    # Check if raw source code is required
    match_source = re.search(r"NEED_SOURCE_CODE:\s*\[(.*?)\]", llm_plan_out)
    if match_source:
        source_files_str = match_source.group(1)
        needed_sources = [s.strip() for s in source_files_str.split(",") if s.strip()]
        
        if needed_sources:
            print_warning(f"AI requests to read raw source code of: {needed_sources}")
            if confirm_action("Allow AI to read raw source code of these files?"):
                for src in needed_sources:
                    if os.path.exists(src):
                        with open(src, "r", encoding="utf-8", errors="ignore") as f:
                            source_code_content += f"=== Source File: {src} ===\n" + f.read() + "\n"
                    else:
                        print_error(f"Source file {src} not found.")
                
                # Re-run plan with source code
                print_info("Re-formulating plan with loaded source code...")
                build_prompt_with_src = build_template.format(
                    readme_content=readme_content,
                    detailed_docs_content=detailed_docs_content,
                    source_code_content=source_code_content,
                    query=query
                )
                res3 = client.completion([{"role": "user", "content": build_prompt_with_src}])
                llm_plan_out = res3.choices[0].message.content
                print_info("\n=== Final Plan (with Source Code) ===")
                print_info(llm_plan_out)

    # Save plan state
    plan_data = {
        "query": query,
        "plan_detail": llm_plan_out,
        "relevant_docs": relevant_files,
        "needed_sources": needed_sources
    }
    
    plan_save_path = os.path.join(doc_dir, "last_plan.json")
    with open(plan_save_path, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2, ensure_ascii=False)
    print_success(f"Plan saved to {plan_save_path}")

    if return_data:
        return plan_data
