import hashlib
import os
import re

def calculate_sha256(filepath: str) -> str:
    """Calculates the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_hash_from_md(md_filepath: str) -> str:
    """Extracts last_hash from markdown file front-matter."""
    if not os.path.exists(md_filepath):
        return ""
    try:
        with open(md_filepath, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"last_hash:\s*(sha256:)?([a-fA-F0-9]+)", content)
        if match:
            return match.group(2)
    except Exception:
        pass
    return ""

def write_md_with_frontmatter(md_filepath: str, source_rel_path: str, file_hash: str, tags: list, content: str):
    """Writes a markdown file with YAML front-matter."""
    os.makedirs(os.path.dirname(md_filepath), exist_ok=True)
    tags_str = ", ".join(tags)
    
    # Strip existing front-matter if it exists in content to avoid duplicates
    clean_content = content
    if content.strip().startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            clean_content = parts[2].strip()

    yaml_frontmatter = f"""---
source_file: {source_rel_path}
last_hash: sha256:{file_hash}
tags: [{tags_str}]
---

"""
    with open(md_filepath, "w", encoding="utf-8") as f:
        f.write(yaml_frontmatter + clean_content)
