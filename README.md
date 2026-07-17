# Cassistant

A local CLI coding assistant backed by **llama.cpp** (via Tailscale or local network) that builds a structured Markdown knowledge base for your codebase and drives AI-assisted development through `init`, `plan`, `build`, and more.

---

## Overview

Cassistant (`cass`) is a Python CLI tool that connects to any **OpenAI-compatible `/v1` API endpoint** — most commonly a self-hosted [llama.cpp](https://github.com/ggerganov/llama.cpp) server — and uses it to:

1. **Index** your source code into structured `.md` documentation files
2. **Maintain** the index incrementally using SHA-256 hash tracking
3. **Plan** feature implementations using context-budget-aware retrieval
4. **Build** code changes with automatic snapshot backups and a rollback path

All data is stored locally in a `.cassistant/` directory inside your project. No code ever leaves your machine except to reach your own LLM endpoint.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Language | Python ≥ 3.8 |
| CLI framework | [Click](https://click.palletsprojects.com/) |
| LLM client | [OpenAI SDK](https://github.com/openai/openai-python) (pointed at llama.cpp) |
| Output formatting | [Rich](https://github.com/Textualize/rich) |
| Config | YAML (`pyyaml`) |
| Hash tracking | SHA-256 (`hashlib`) |
| Transport | Tailscale (or any reachable IP) |

---

## Installation

```bash
# Clone the repository
git clone https://github.com/otiosum1005/Cassistant.git
cd cassistant

# Install in editable mode (exposes the `cass` entrypoint)
pip install -e .
```

After installation, the `cass` command is available globally.

---

## Quick Start

### 1. Start your llama.cpp server

```bash
# Example: local server
./llama-server -m ./models/llama-3.1-70b.gguf --port 8080

# Example: remote via Tailscale
./llama-server -m ./models/llama-3.1-70b.gguf --host 0.0.0.0 --port 8080
```

### 2. Navigate to your project root

```bash
cd /path/to/your/project
```

### 3. Run `cass init`

On first run, Cassistant auto-creates `.cassistant/config.yaml` with default settings. Edit the `base_url` to point to your server, then run:

```bash
cass init
```

---

## Configuration

Config file is located at `.cassistant/config.yaml` and is auto-generated on first use.

```yaml
llm:
  base_url: "http://100.x.x.x:8080/v1"  # Tailscale IP or localhost
  api_key: "none"                          # llama.cpp doesn't need a real key
  model: "llama-3.1-70b"
  context_limit: 128000                    # max tokens
  timeout: 120                             # seconds per request
  temperature: 0.2                         # low = more deterministic

project:
  include:
    - "**/*.py"
    - "**/*.c"
    - "**/*.cpp"
    - "**/*.h"
    - "**/*.hpp"
    - "**/*.java"
  exclude:
    - "**/node_modules/**"
    - "**/__pycache__/**"
    - "**/tests/**"
    - "**/.*/**"
    - ".cassistant/**"
  doc_dir: ".cassistant"
```

---

## Commands

### `cass init [--force]`

Scans all source files matching the configured `include`/`exclude` patterns, then:

1. Shows the matched file list and asks for confirmation
2. Analyzes each file individually with the LLM → writes `docs/<filename>.md` with YAML front-matter (source path, SHA-256 hash, tags)
3. Generates three cross-file index documents:
   - `index/api_surface.md` — all public functions/classes
   - `index/dependency.md` — inter-module dependency map
   - `index/data_flow.md` — data transformation flows
4. Generates a master `readme.md` with module table and tags

Use `--force` to overwrite existing indices.

---

### `cass status`

Rescans all tracked files, recalculates their SHA-256, and compares against the stored hashes in each `.md` front-matter.

```
✅ Up-to-date (18 files)
⚠️  Dirty (3 files):
   - src/auth.py        (last synced: 2026-07-14)
   - src/routes.py      (last synced: 2026-07-13)
   - src/new_module.py  (no .md yet)
```

Prompts you to run `cass update --dirty` to fix stale docs.

---

### `cass update [files...] [--dirty] [--all]`

Incrementally updates documentation for changed files.

| Mode | Command | Behaviour |
| --- | --- | --- |
| Specific files | `cass update src/auth.py` | Reanalyzes only listed files |
| Auto dirty | `cass update --dirty` | Detects and updates all hash-mismatched files |
| Full rebuild | `cass update --all` | Reanalyzes all tracked files |

After updating individual `.md` files, regenerates `index/` and `readme.md`.

---

### `cass plan "<query>"`

Analyzes a natural-language requirement and produces a concrete implementation plan.

```bash
cass plan "Add a JWT-based login endpoint"
```

Flow:

1. Warns if any `.md` docs are out of date (dirty check)
2. Loads `readme.md` and uses it to identify the most relevant modules via tags
3. Loads `.md` files in tag-relevance order, respecting the 128k context budget
4. If needed, prompts to load actual source code for more detail
5. Outputs: problem analysis, files to modify, step-by-step plan, and impact preview
6. Saves the plan to `.cassistant/last_plan.json`
7. Offers to immediately proceed with `cass build`

---

### `cass build ["<query>"] [--from-plan]`

Generates and applies code changes, with automatic backups.

```bash
# Use last saved plan
cass build --from-plan

# Generate a new plan inline then build
cass build "Implement the login endpoint from the plan"
```

Flow:

1. Runs or loads a plan to determine which files to modify
2. Shows a full change manifest and asks for confirmation:

   ```
   📝 [NEW]    src/auth.py
   📝 [MODIFY] src/routes.py
   ⚠️  [IMPACT] src/middleware.py may be affected
   ```

3. **Snapshots** the entire source tree to `.cassistant/snapshots/<timestamp>/`
4. Calls the LLM to generate file contents or unified diffs
5. Applies changes, then re-indexes modified files via `cass update`
6. Writes a build log entry to `.cassistant/logs/build_log.md`

---

### `cass rollback [timestamp]`

Reverts source files to a previous snapshot.

```bash
# List available snapshots and choose interactively
cass rollback

# Restore a specific snapshot
cass rollback 20260715_143022
```

Snapshots are stored at `.cassistant/snapshots/<timestamp>/`. The corresponding `.md` docs are also restored.

---

## Generated File Structure

After `cass init`, your project gains a `.cassistant/` directory:

```
.cassistant/
├── config.yaml               ← LLM + project settings
├── readme.md                 ← AI-generated project overview with module table
├── index/
│   ├── api_surface.md        ← All public APIs across the codebase
│   ├── dependency.md         ← Inter-module dependency graph
│   └── data_flow.md          ← Data transformation map
├── docs/
│   └── <filename>.md         ← One .md per source file (with YAML front-matter)
├── snapshots/
│   └── <timestamp>/          ← Full source backup before each build
├── last_plan.json            ← Most recent plan output (used by cass build --from-plan)
└── logs/
    └── build_log.md          ← Append-only log of all build sessions
```

### `.md` Front-Matter Format

Every file in `docs/` carries YAML front-matter used for hash-tracking and tag-based retrieval:

```markdown
---
source_file: src/auth.py
last_hash: sha256:abc123def456...
tags: [auth, jwt, session, user, password]
---

# auth.py

## Overview
Implements user authentication including JWT generation and session management.

## Public Functions

### `login(username: str, password: str) → Token`
- **Purpose**: Validates credentials and returns a JWT
- **Raises**: `AuthError` (invalid credentials)

## Internal Dependencies
- `db.py` → `get_user_by_name()`
- `config.py` → `JWT_SECRET`

## Used By
- `routes.py` — all authenticated endpoints
```

---

## Context Budget (128k)

Cassistant manages the LLM context window automatically:

| Slot | Reserved Tokens | Usage |
| --- | --- | --- |
| System prompt | ~2,000 | Fixed |
| `readme.md` | ~3,000 | Always loaded |
| Relevant `.md` docs | up to 60,000 | Loaded by tag-relevance score |
| Source code (on demand) | up to 40,000 | Only when `.md` is insufficient |
| User query | ~1,000 | Fixed |
| Output headroom | ~8,000 | Fixed |

The tag-relevance strategy loads the highest-scoring `.md` files first and stops when the budget is exhausted, falling back to loading partial source files only for the most relevant modules.

---

## Project Layout

```
cassistant/                    ← installable package
├── pyproject.toml
└── cassistant/
    ├── cli.py                 ← Click CLI entrypoint (`cass`)
    ├── config.py              ← Load/validate config.yaml; auto-create defaults
    ├── client.py              ← OpenAI-compatible LLM wrapper
    ├── context_budget.py      ← 128k context budget management
    ├── hasher.py              ← SHA-256 calculation; front-matter read/write
    ├── commands/
    │   ├── init.py            ← cass init
    │   ├── plan.py            ← cass plan
    │   ├── build.py           ← cass build (snapshot + diff apply + re-index)
    │   ├── update.py          ← cass update
    │   ├── rollback.py        ← cass rollback
    │   ├── status.py          ← cass status
    │   └── files.py           ← Shared glob scanner (include/exclude)
    ├── prompts/
    │   ├── analyze_file.txt   ← Per-file analysis prompt
    │   ├── build_readme.txt   ← Master readme generation prompt
    │   ├── build_index.txt    ← Index (api_surface/dependency/data_flow) prompt
    │   ├── plan.txt           ← Planning prompt
    │   ├── build.txt          ← Build guidance prompt
    │   └── generator.txt      ← Code generation prompt
    └── utils/
        ├── printer.py         ← Rich-powered coloured output helpers
        └── confirm.py         ← Human-in-the-loop confirmation utility
```

---

## Human-in-the-Loop

Every destructive or significant action requires explicit confirmation:

| Action | Prompt shown |
| --- | --- |
| `cass init` | Confirm file list before indexing |
| `cass update` | Confirm which files will be re-analyzed |
| `cass plan` | Option to load source code for deeper context |
| `cass build` | Confirm full change manifest before applying |
| `cass build` | Option to rollback after seeing the applied diff |
| `cass rollback` | Confirm overwrite warning before restoring |

---

## Dependencies

```
openai>=1.0.0
pyyaml>=6.0
rich>=12.0.0
click>=8.0.0
```

Install via `pip install -e .` or `pip install cassistant` (once published).
