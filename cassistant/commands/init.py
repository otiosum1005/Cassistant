import os
from .files import get_project_files
from ..utils.printer import print_info, print_error, print_success, print_warning
from ..utils.confirm import confirm_action
from ..config import load_config
from ..client import LLMClient
from ..hasher import calculate_sha256, write_md_with_frontmatter
import pkg_resources

def read_prompt_template(name: str) -> str:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", f"{name}.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def run_init(force: bool):
    print_info("Scanning project directories...")
    files = get_project_files()
    if not files:
        print_warning("No source files found matching configured include patterns.")
        return

    print_info(f"Found {len(files)} source files to index:")
    for f in files:
        print_info(f"  - {f}")

    if not confirm_action(f"Do you want to initialize documentation for these {len(files)} files?"):
        print_info("Initialization cancelled.")
        return

    config = load_config()
    doc_dir = config.project_doc_dir
    docs_folder = os.path.join(doc_dir, "docs")
    os.makedirs(docs_folder, exist_ok=True)

    client = LLMClient()
    analyze_template = read_prompt_template("analyze_file")

    doc_summaries = []

    for idx, filepath in enumerate(files, 1):
        print_info(f"[{idx}/{len(files)}] Processing {filepath}...")
        try:
            file_hash = calculate_sha256(filepath)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Format analyzer prompt
            prompt = analyze_template.format(file_path=filepath, file_content=content)
            messages = [{"role": "user", "content": prompt}]
            
            response = client.completion(messages)
            llm_content = response.choices[0].message.content

            # Naive tag extraction or request LLM for tags
            # Let's generate simple extension tags for now + parse keywords
            ext = os.path.splitext(filepath)[1].replace(".", "")
            tags = [ext]
            if "auth" in content.lower(): tags.append("auth")
            if "db" in content.lower() or "database" in content.lower(): tags.append("db")
            if "server" in content.lower() or "http" in content.lower(): tags.append("http")

            # Write individual md
            filename_md = os.path.basename(filepath) + ".md"
            md_path = os.path.join(docs_folder, filename_md)
            write_md_with_frontmatter(md_path, filepath, file_hash, tags, llm_content)
            print_success(f"Generated {md_path}")
            
            doc_summaries.append(f"### {filepath}\n{llm_content}\n")

        except Exception as e:
            print_error(f"Failed to analyze {filepath}: {e}")

    # Build index and readme
    if doc_summaries:
        print_info("Building system index files and Readme...")
        docs_joined = "\n".join(doc_summaries)
        
        index_folder = os.path.join(doc_dir, "index")
        os.makedirs(index_folder, exist_ok=True)
        
        build_index_template = read_prompt_template("build_index")
        build_readme_template = read_prompt_template("build_readme")

        for idx_type in ["api_surface", "dependency", "data_flow"]:
            try:
                print_info(f"Generating index/{idx_type}.md...")
                prompt = build_index_template.format(index_type=idx_type, docs_content=docs_joined)
                res = client.completion([{"role": "user", "content": prompt}])
                idx_path = os.path.join(index_folder, f"{idx_type}.md")
                with open(idx_path, "w", encoding="utf-8") as f:
                    f.write(res.choices[0].message.content)
                print_success(f"Generated {idx_path}")
            except Exception as e:
                print_error(f"Failed to build index {idx_type}: {e}")

        try:
            print_info("Generating master readme.md...")
            prompt = build_readme_template.format(docs_content=docs_joined)
            res = client.completion([{"role": "user", "content": prompt}])
            readme_path = os.path.join(doc_dir, "readme.md")
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(res.choices[0].message.content)
            print_success(f"Generated {readme_path}")
        except Exception as e:
            print_error(f"Failed to build master readme.md: {e}")

    print_success("Initialization complete.")
