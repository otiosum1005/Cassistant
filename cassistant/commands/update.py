import os
from .files import get_project_files
from .status import check_status
from .init import read_prompt_template
from ..utils.printer import print_info, print_error, print_success, print_warning
from ..utils.confirm import confirm_action
from ..config import load_config
from ..client import LLMClient
from ..hasher import calculate_sha256, write_md_with_frontmatter

def run_update(files, dirty, update_all):
    status = check_status()
    config = load_config()
    doc_dir = config.project_doc_dir
    docs_folder = os.path.join(doc_dir, "docs")
    
    target_files = []
    
    if update_all:
        target_files = status["clean"] + status["dirty"] + status["missing"]
    elif dirty:
        target_files = status["dirty"] + status["missing"]
    elif files:
        # User specified files manually
        for f in files:
            norm_f = os.path.normpath(f).replace("\\", "/")
            if os.path.exists(norm_f):
                target_files.append(norm_f)
            else:
                print_error(f"File {f} not found.")
    else:
        print_warning("Please specify files to update, or use --dirty / --all flags.")
        return

    if not target_files:
        print_success("No files need updating.")
        return

    print_info(f"The following {len(target_files)} files will be updated:")
    for f in target_files:
        print_info(f"  - {f}")

    if not confirm_action("Proceed with the update?"):
        print_info("Update cancelled.")
        return

    client = LLMClient()
    analyze_template = read_prompt_template("analyze_file")

    # Update individual docs
    for idx, filepath in enumerate(target_files, 1):
        print_info(f"[{idx}/{len(target_files)}] Updating {filepath}...")
        try:
            file_hash = calculate_sha256(filepath)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            prompt = analyze_template.format(file_path=filepath, file_content=content)
            res = client.completion([{"role": "user", "content": prompt}])
            llm_content = res.choices[0].message.content

            ext = os.path.splitext(filepath)[1].replace(".", "")
            tags = [ext]
            if "auth" in content.lower(): tags.append("auth")
            if "db" in content.lower(): tags.append("db")

            filename_md = os.path.basename(filepath) + ".md"
            md_path = os.path.join(docs_folder, filename_md)
            write_md_with_frontmatter(md_path, filepath, file_hash, tags, llm_content)
            print_success(f"Updated {md_path}")
        except Exception as e:
            print_error(f"Failed to update {filepath}: {e}")

    # Re-evaluate all summaries for index regeneration
    print_info("Regenerating indexes and readme.md...")
    all_source_files = get_project_files()
    doc_summaries = []
    
    for filepath in all_source_files:
        filename_md = os.path.basename(filepath) + ".md"
        md_path = os.path.join(docs_folder, filename_md)
        if os.path.exists(md_path):
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # strip frontmatter
                if content.strip().startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                doc_summaries.append(f"### {filepath}\n{content}\n")
            except Exception:
                pass

    if doc_summaries:
        docs_joined = "\n".join(doc_summaries)
        index_folder = os.path.join(doc_dir, "index")
        build_index_template = read_prompt_template("build_index")
        build_readme_template = read_prompt_template("build_readme")

        for idx_type in ["api_surface", "dependency", "data_flow"]:
            try:
                prompt = build_index_template.format(index_type=idx_type, docs_content=docs_joined)
                res = client.completion([{"role": "user", "content": prompt}])
                idx_path = os.path.join(index_folder, f"{idx_type}.md")
                with open(idx_path, "w", encoding="utf-8") as f:
                    f.write(res.choices[0].message.content)
            except Exception as e:
                print_error(f"Failed to regenerate index {idx_type}: {e}")

        try:
            prompt = build_readme_template.format(docs_content=docs_joined)
            res = client.completion([{"role": "user", "content": prompt}])
            readme_path = os.path.join(doc_dir, "readme.md")
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(res.choices[0].message.content)
            print_success("Readme and index regeneration complete.")
        except Exception as e:
            print_error(f"Failed to rebuild master readme.md: {e}")
            
    print_success("Update complete.")
