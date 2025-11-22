# AGENTS.md — Engineering Guide for Autonomous Coding Agents

This document defines how AI agents must operate when modifying the Scribe codebase. It encodes architectural invariants, safe‑editing rules, workflows, and recovery procedures. The goal is simple: **agents must never degrade the stability, performance, or architecture of Scribe.**

---

# 1. Purpose & Scope

This guide exists to guarantee **predictable, safe, reversible edits** when autonomous agents modify Scribe. It establishes:

* How to reason about changes
* What architectural rules can never be violated
* Required editing workflows
* Error‑recovery mechanisms
* Module‑level interfaces and expectations

It is written for:

* AI coding agents performing code modifications
* Human maintainers reviewing agent output

---

# 2. Mental Model: How Scribe Works

Scribe is a real‑time transcription + post‑processing application built around three pillars:

1. **Audio ingestion** via WASAPI loopback
2. **Transcription & segmentation** via `faster-whisper`
3. **Meeting synthesis** using local LLMs (via Ollama)

The pipeline is threaded and modular:

```
AudioRecorder → Queue → Transcriber → transcript_full.txt → MeetingSynthesizer
```

Every agent edit must preserve this flow.

---

# 3. Non‑Negotiable Architectural Invariants

Breaking any of these invariants is considered a critical failure.

## 3.1 CUDA Initialization Order

* CUDA DLL setup **must occur before** any import of `ctranslate2` or `faster_whisper`.
* This logic **must remain** in `core/__init__.py`.

## 3.2 Thread Model

* AudioRecorder runs in a **daemon thread**.
* Transcriber runs in a **daemon thread**.
* They communicate **only** via a `queue.Queue`.
* Agents must not introduce shared mutable state between them.

## 3.3 Config Access Pattern

* All config values must come from `ConfigManager`.
* No hardcoded thresholds.
* Never invent new config keys unless explicitly requested.

## 3.4 Session Directory Contract

Each recording session **must** generate:

```
<session>/audio_chunks/*.wav
<session>/transcript_full.txt
<session>/notes_logseq.md
```

Paths come **only** from `SessionManager`.

## 3.5 MeetingSynthesizer Contract

* Must read `transcript_full.txt` exactly
* Must respect user context file if present
* Must produce structured markdown summary

---

# 4. Safe Editing Workflow (Required)

Autonomous agents must follow this exact procedure for any code change.

## Step 1 — Understand the request

* Identify *exactly* which module(s) are affected.
* Determine if any config values influence the change.
* Check if threading, audio loops, or CUDA init are in the blast radius.

## Step 2 — Plan the edit

* Write a minimal plan before modifying code.
* Confirm whether the change touches **one file** or **multiple**.
* Identify imports required.

## Step 3 — Execute safely

* View target lines **before** editing.
* Perform minimal, isolated edits.
* Do not refactor unless explicitly instructed.
* After adding a library call, verify imports.

## Step 4 — Validate immediately

Use these commands:

```
uv run python -c "from scribe.core import SessionManager, AudioRecorder, Transcriber"
uv run scribe record       # 10–15s audio
uv run scribe gui           # GUI sanity check
```

## Step 5 — Update docs & version

If code changes behavior or user‑facing features:

* Update README.md
* Update AGENTS.md (this file)
* Increment `pyproject.toml` version

---

# 5. File Editing Rules

These rules prevent catastrophic file corruption.

## 5.1 Only Edit What You Viewed

Never call a replace operation on code you haven't viewed in the same turn.

## 5.2 Never Use Large Blind Replacements

Avoid changing more than ~20 contiguous lines unless explicitly instructed.

## 5.3 One Logical Change Per Edit

Examples:

* "Add a method" → 1 change
* "Fix two unrelated bugs" → must be separate edits

## 5.4 Preserve Existing Imports Unless Sure

Deleting imports risks silently breaking runtime behavior.

## 5.5 Never Remove Error Handling

Unless the user explicitly requests a removal or redesign.

---

# 6. Module Reference (Interfaces to Preserve)

## 6.1 SessionManager

**Responsibilities:**

* Create session directories
* Provide canonical paths

**Key methods:**

* `__init__()`
* Path builders for transcripts and audio chunks

## 6.2 AudioRecorder

**Responsibilities:**

* Capture loopback audio
* Optional mic mixing

**Key methods:**

* `record_loop()` — main audio capture
* `select_device()`
* `start_recording()` / `stop_recording()`

**Constraints:**

* Writes only to queue & WAV helpers
* Must not block main thread

## 6.3 Transcriber

**Responsibilities:**

* Consume queue
* Chunking via pause detection
* Whisper transcription

**Key methods:**

* `process_audio()` — main loop
* `transcribe_buffer()`
* `save_audio_chunk()`

**Constraints:**

* Whisper model must load after CUDA init
* Must respect config thresholds

## 6.4 MeetingSynthesizer

**Responsibilities:**

* Load context
* Split transcript into blocks
* Produce structured meeting notes

**Constraints:**

* Must call Ollama using configured model

---

# 7. Configuration Principles

* All defaults live in ConfigManager.
* YAML overrides live in `Documents/Scribe/config/`.
* Access pattern:

```
self.config_manager.config.get("section", {}).get("key", default)
```

---

# 8. Testing Matrix

Agents must run these tests after any change touching:

* Transcriber
* AudioRecorder
* MeetingSynthesizer
* Config system

### Import Test

```
uv run python -c "from scribe.core import SessionManager, AudioRecorder, Transcriber"
```

### CLI Path

```
uv run scribe record
```

### GUI Path

```
uv run scribe gui
```

---

# 9. Common Failure Modes & Recovery

## 9.1 File Corruption

If a file becomes malformed:

```
git checkout -- src/scribe/<path>
```

Then re‑attempt edit with smaller modifications.

## 9.2 Missing Method Errors

Check history:

```
grep -R "def method_name" -n src/
```

## 9.3 Import Failures

* Check `core/__init__.py`
* Re‑add missing imports
* Re‑run import test

## 9.4 Config Not Loading

* Confirm YAML exists
* Ensure `ConfigManager` is instantiated
* Validate key path

---

# 10. Documentation & Versioning Rules

## When to Update README.md

* Feature added
* Behavior changed
* Config changed
* Models updated

## When to Update AGENTS.md

* Architecture changes
* New bugs/lessons learned
* Workflow changes

## When to Increment Version

* PATCH: bug fixes
* MINOR: feature additions
* MAJOR: breaking changes

---

# 11. Mandatory Change Logging (`AGENT_LOG.md`)

All agents must record every code modification in a single append-only file at the project root named `AGENT_LOG.md`.

## 11.1 Logging Rules

* You MUST append a new entry at the **top** of `AGENT_LOG.md` for every code-modifying request.
* If you cannot update the log, you MUST NOT modify any other file.
* The log MUST remain append-only; never modify or delete prior entries.

## 11.2 Required Entry Structure

Each entry MUST follow this exact structure:

```markdown
## <ISO-8601 UTC timestamp> — Agent: <agent-id>

### User request
<1–2 sentence paraphrase>

### Plan
- Step 1: ...
- Step 2: ...
- Step 3: ...

### Files changed
- `path/to/file.py` — reason
- ...

### Code changes (high-level)
- Bullet-point summary of functional behavior changes

### Tests run
- [x] <command> — ran
- [ ] <command> — skipped (reason)

### Known limitations / follow-ups
- ...
```

## 11.3 Optional Machine-Readable Footer

Agents may include a JSON footer for tooling:

```markdown
<!-- AGENT_SUMMARY
{"timestamp": "<ISO-8601>",
 "agent": "<agent-id>",
 "files_changed": [...],
 "risk": "low|medium|high"}
-->
```

## 11.4 Granularity Requirement

* One log entry per user request that leads to code changes.
* Multiple related file edits for the same request belong in a single entry.

---

# 12. Golden Rules (TL;DR)

1. **View before you edit.**
2. **Never break CUDA init order.**
3. **Never hardcode config values.**
4. **Threads must remain daemon threads.**
5. **Use queues for all thread communication.**
6. **One logical change per edit.**
7. **Test immediately after modifying code.**
8. **Update docs + version when behavior changes.**
9. **When in doubt: stop, inspect, recover, retry.**

# 13. Validation & Enforcement

These mechanisms are optional for humans but describe how to enforce the rules in this document.

## 13.1 Suggested Log Validator Script (Git Bash / POSIX Shell)

On Windows with Git for Windows, Git hooks run via the bundled POSIX shell (Git Bash). The following script works on Windows and Linux as long as `bash` is available.

Create `scripts/check_agent_log.sh` and make it executable (on Windows this typically just needs the correct shebang; execute bit is optional):

```bash
#!/usr/bin/env bash
set -euo pipefail

# Files changed in the staged set
CHANGED_FILES=$(git diff --cached --name-only)

# If no staged changes, nothing to do
if [[ -z "$CHANGED_FILES" ]]; then
  exit 0
fi

# Determine if any tracked code/config files changed (heuristic)
NEEDS_LOG=0
while IFS= read -r file; do
  case "$file" in
    src/*|config/*|pyproject.toml|AGENTS.md|README.md)
      NEEDS_LOG=1
      ;;
  esac
done <<< "$CHANGED_FILES"

if [[ "$NEEDS_LOG" -eq 0 ]]; then
  exit 0
fi

# Check whether AGENT_LOG.md is staged
if ! grep -q "^AGENT_LOG.md$" <<< "$CHANGED_FILES"; then
  echo "ERROR: Code/config/docs changes detected but AGENT_LOG.md is not updated." >&2
  echo "       Please add an entry at the top of AGENT_LOG.md describing this change." >&2
  exit 1
fi
```

## 13.2 Git Hook Integration (Git Bash)

To enforce logging locally with the default Git for Windows / Git Bash setup:

1. Save the script above as `scripts/check_agent_log.sh`.
2. Create `.git/hooks/pre-commit` with:

   ```bash
   #!/usr/bin/env bash
   scripts/check_agent_log.sh
   ```
3. (Optional on Windows) Mark the hook executable:

   ```bash
   chmod +x .git/hooks/pre-commit
   ```

Developers who enable this hook will be blocked from committing code/config/doc changes unless `AGENT_LOG.md` has been updated and staged.

## 13.3 Optional PowerShell Variant (Windows)

If you prefer to use PowerShell directly as your hook on Windows, you can instead create `scripts/check_agent_log.ps1`:

```powershell
param()

# Get staged files
$changedFiles = git diff --cached --name-only
if (-not $changedFiles) {
    exit 0
}

$needsLog = $false
foreach ($file in $changedFiles) {
    switch -Wildcard ($file) {
        'src/*' { $needsLog = $true }
        'config/*' { $needsLog = $true }
        'pyproject.toml' { $needsLog = $true }
        'AGENTS.md' { $needsLog = $true }
        'README.md' { $needsLog = $true }
    }
}

if (-not $needsLog) {
    exit 0
}

if (-not ($changedFiles -contains 'AGENT_LOG.md')) {
    Write-Error 'Code/config/docs changes detected but AGENT_LOG.md is not updated.'
    Write-Error 'Please add an entry at the top of AGENT_LOG.md describing this change.'
    exit 1
}
```

Then create `.git/hooks/pre-commit` as a small wrapper to call PowerShell:

```bash
#!/usr/bin/env bash
pwsh -NoLogo -NoProfile -File "scripts/check_agent_log.ps1"
```

(If you use `powershell.exe` instead of `pwsh`, adjust the command accordingly.)

This achieves the same enforcement but leverages your native Windows PowerShell environment.
