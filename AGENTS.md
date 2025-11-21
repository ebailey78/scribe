# AGENTS.md - Development Guide for AI Agents

This document provides guidance for AI agents working on the Scribe project, including architecture overview, development strategies, and lessons learned from past issues.

## Project Overview

**Scribe** is a real-time audio transcription application that captures system audio, transcribes it using OpenAI's Whisper model, and generates meeting notes using local LLMs via Ollama.

### Key Features
- System audio capture via WASAPI loopback
- Real-time transcription with Whisper (CUDA/CPU)
- Smart audio segmentation with pause detection
- AI-powered meeting synthesis with Ollama
- Logseq integration for note management
- Configurable vocabulary (jargon) and context

## Architecture

### Directory Structure
```
scribe/
├── src/scribe/
│   ├── core/                    # Core functionality (modular)
│   │   ├── __init__.py         # CUDA setup, exports
│   │   ├── session.py          # SessionManager
│   │   ├── recorder.py         # AudioRecorder
│   │   └── transcriber.py      # Transcriber
│   ├── gui/
│   │   └── app_pro.py          # GUI application
│   ├── utils/
│   │   ├── config.py           # ConfigManager
│   │   ├── paths.py            # Path utilities
│   │   └── logging.py          # Logging setup
│   ├── synthesis.py            # MeetingSynthesizer
│   ├── cli.py                  # CLI commands
│   └── __init__.py
├── config/                      # Default config templates
│   ├── jargon.txt
│   └── context_template.md
└── pyproject.toml
```

### User Config Location
```
Documents/Scribe/
├── config/
│   ├── config.yaml
│   ├── jargon.txt
│   └── context.md
└── sessions/
    └── {session-id}/
        ├── audio_chunks/
        ├── transcript_full.txt
        └── notes.md
```

## Critical Lessons Learned

### 1. File Size and Editing Safety

**❌ PROBLEM:** The original `core.py` was monolithic (~375 lines) containing SessionManager, AudioRecorder, and Transcriber. When editing one class, agents accidentally:
- Deleted critical methods (`process_audio`, `save_audio_chunk`)
- Corrupted unrelated code in the same file
- Forgot to add required imports (`logging`)

**✅ SOLUTION:** Refactored into modular `core/` package with separate files:
- `core/session.py` - SessionManager (45 lines)
- `core/recorder.py` - AudioRecorder (118 lines)  
- `core/transcriber.py` - Transcriber (229 lines)
- `core/__init__.py` - CUDA setup and exports

**GUIDELINE:** Keep files focused and small. Each file should have ONE primary responsibility.

### 2. Editing Best Practices

**❌ ANTI-PATTERNS:**
- Using `multi_replace_file_content` on large files with many changes
- Making changes to multiple unrelated sections of a file in one edit
- Not verifying the full context before/after target content

**✅ BEST PRACTICES:**
- **View before edit:** Always view the exact lines you're editing first
- **Small, focused edits:** One logical change per edit operation
- **Verify imports:** After adding code that uses a library, check imports
- **Test immediately:** Run verification after each significant change
- **Use git checkout:** When file gets corrupted, restore and start over

### 3. CUDA Setup Requirement

**CRITICAL:** CUDA DLLs must be added to PATH **before** importing `ctranslate2` or `faster_whisper`.

This is why `core/__init__.py` exists - it ensures CUDA setup happens first, then imports the classes that depend on it.

**DO NOT** move CUDA setup code out of `__init__.py` or remove it.

### 4. Configuration System

The app uses a layered configuration approach:

1. **Default values** - Hardcoded in ConfigManager
2. **config.yaml** - User overrides in `Documents/Scribe/config/`
3. **Runtime values** - Loaded at init time

**Key config values:**
```yaml
transcription:
  min_duration: 60              # Min seconds before chunking
  max_duration: 90              # Force chunk at this duration
  silence_threshold: 0.01       # Amplitude for pause detection
  silence_duration: 0.5         # Silence window to check
  max_silent_chunks: 1          # Auto-stop after N silent chunks
  silence_chunk_threshold: 0.005 # Amplitude for auto-stop
```

**IMPORTANT:** The smart pause detection uses `silence_threshold` and `silence_duration` for **intra-chunk** pause detection (finding natural breaks). The `silence_chunk_threshold` and `max_silent_chunks` are for **auto-stop** detection (ending the recording).

### 5. Audio Processing Flow

```
AudioRecorder.record_loop()
    ↓ (puts data in queue)
    
Transcriber.process_audio()  [runs in thread]
    ↓ (moves queue → buffer)
    
Smart Pause Detection:
  - Wait for min_duration (60s)
  - Look for silence_threshold in last silence_duration
  - OR force at max_duration (90s)
    ↓
    
Transcriber.transcribe_buffer()
  - Save audio chunk to WAV
  - Resample if needed
  - Run Whisper transcription
  - Save to transcript files
  - Check for auto-stop (silent chunks)
    ↓
    
If auto-stop triggered → call auto_stop_callback()
```

## Workflow Protocol

**1. One Feature Per Chat**
- **Scope:** Each chat session should focus on a SINGLE feature or bug fix.
- **Branching:** ALWAYS create a new feature branch at the start (`git checkout -b feature/name`).
- **Commits:** Make regular, meaningful commits after each logical step. Do not wait until the end.

**2. Scope Management**
- **Stay Focused:** If the user (or agent) drifts to unrelated changes, PAUSE.
- **Capture Ideas:** Offer to create a GitHub issue for the new idea instead of implementing it immediately.
- **Enforce Boundaries:** Politely suggest finishing the current task first before context switching.

**3. Git Hygiene**
- **Atomic Commits:** "Fix login bug" is better than "Fix login, update readme, and refactor core".
- **Descriptive Messages:** Explain *why* a change was made, not just *what*.

**4. Task Initiation**
- **Clarify First:** Before writing code, explicitly ask about any ambiguities or uncertainties.
- **Review Context:** Read relevant existing code to understand the request's impact and ramifications.
- **Safety Check:** It is the **agent's responsibility** to warn the user about dangerous, unwise, or anti-pattern requests. Do not blindly follow instructions that will degrade the codebase.

## Development Workflow

### Making Changes

1. **Understand the change:**
   - Read the user request carefully
   - Identify which module(s) are affected
   - Check if config values are involved

2. **Plan the edit:**
   - Create implementation plan if complex
   - Identify exact files and methods to modify
   - Consider backward compatibility

3. **Execute safely:**
   - View the exact section before editing
   - Make focused, minimal edits
   - Verify imports after adding new functionality
   - Test immediately after changes

4. **Verify:**
   - Test imports: `uv run python -c "from scribe.core import ..."`
   - Test CLI: `uv run scribe record` (short test with audio)
   - Test GUI: `uv run scribe gui`
   - Check config loading if config-related

### Testing

**Quick Import Test:**
```bash
uv run python -c "from scribe.core import SessionManager, AudioRecorder, Transcriber; print('✅ OK')"
```

**CLI Recording Test:**
```bash
uv run scribe record
# Play some audio for 10-15 seconds, then Ctrl+C
# Check that transcript_full.txt was created
```

**GUI Test:**
```bash
uv run scribe gui
# Click record, play audio, click stop
# Verify recording and transcription work
```

## Common Pitfalls

### ❌ Don't: Edit Large Sections Blindly
Using `replace_file_content` with 100+ lines of target content is error-prone.

### ✅ Do: Make Focused Changes
View → identify specific change → edit minimal target content.

### ❌ Don't: Assume Config Values
The config system loads from YAML. Always use `self.config_manager.config.get()` pattern.

### ✅ Do: Use Config Properties
The Transcriber already loads config in `__init__`. Use `self.min_duration`, `self.silence_threshold`, etc.

### ❌ Don't: Forget Daemon Threads
Audio processing runs in daemon threads. Always use `daemon=True` when creating transcriber threads.

### ✅ Do: Understand Thread Model
- `AudioRecorder.record_loop()` runs in thread (started by `start_recording()`)
- `Transcriber.process_audio()` runs in thread (started by CLI/GUI)
- Both use queues for thread-safe communication

## Quick Reference

### Key Classes & Responsibilities

**SessionManager** - Creates session directories, manages file paths
**AudioRecorder** - Captures system audio, manages recording state
**Transcriber** - Processes audio queue, transcribes via Whisper, smart segmentation
**MeetingSynthesizer** - Generates AI summaries via Ollama, exports to Logseq
**ConfigManager** - Loads and manages YAML configuration

### Key Methods to Preserve

**Transcriber:**
- `process_audio()` - Main processing loop (runs in thread)
- `transcribe_buffer()` - Transcribes current buffer
- `save_audio_chunk()` - Saves WAV files for debugging
- `load_model()` - Loads Whisper with CUDA/CPU fallback
- `load_jargon()` - Loads custom vocabulary

**AudioRecorder:**
- `record_loop()` - Main recording loop (runs in thread)
- `find_default_loopback()` - Auto-selects default speaker
- `select_device()` - Device selection with auto/manual modes

## When Things Go Wrong

### File Corrupted During Edit
```bash
git checkout src/scribe/core/transcriber.py
# Start over with smaller, more focused edit
```

### Missing Method After Refactor
1. Check if it exists: `grep -r "def method_name" src/`
2. Find it in git history: `git log -p --all -- src/scribe/core.py | grep -A 20 "def method_name"`
3. Restore from git or re-implement

### Import Errors
1. Check `__init__.py` exports
2. Verify module imports at top of file
3. Test import: `uv run python -c "from scribe.core import ClassName"`

### Config Not Loading
1. Check `Documents/Scribe/config/config.yaml` exists
2. Verify ConfigManager is initialized
3. Check config key path: `self.config_manager.config.get("section", {}).get("key", default)`

## Documentation Maintenance

**CRITICAL:** Keep documentation synchronized with code changes.

### Files to Update

**README.md** - User-facing documentation
- Update when adding/removing features
- Update configuration examples
- Update installation or usage instructions
- Keep feature list current

**AGENTS.md** - This file
- Update architecture diagrams when structure changes
- Add new lessons learned from bugs/issues
- Update quick reference when classes/methods change
- Document new patterns or anti-patterns discovered

**pyproject.toml** - Project metadata and dependencies
- **Add dependencies** when importing new libraries
- **Increment version** following semantic versioning:
  - `MAJOR.MINOR.PATCH` (e.g., `0.3.1`)
  - MAJOR: Breaking changes (rare for this project)
  - MINOR: New features, refactorings (e.g., `0.2.0` → `0.3.0`)
  - PATCH: Bug fixes, small improvements (e.g., `0.3.0` → `0.3.1`)
- Update project description if scope changes

### When to Update Documentation

**During Implementation:**
- Add new dependencies to `pyproject.toml` immediately
- Update README.md if user-facing features change
- Update AGENTS.md if architecture/patterns change

**After Completing Work:**
- Review README.md for accuracy
- Increment version in `pyproject.toml`
- Update AGENTS.md with lessons learned
- Check that all examples in docs still work

### Version Increment Guidelines

```bash
# Bug fix or small improvement
version = "0.3.1" → "0.3.2"

# New feature (jargon config, context support)
version = "0.3.2" → "0.4.0"

# Major refactor (core module split)
version = "0.4.0" → "0.5.0"

# Breaking change (API change)
version = "0.5.0" → "1.0.0"
```

**Example Commit Flow:**
1. Make code changes
2. Update README.md (if feature-related)
3. Update AGENTS.md (if architecture/lessons)
4. Increment version in `pyproject.toml`
5. Commit with descriptive message

## Summary

**Golden Rules:**
1. ✅ Keep files small and focused
2. ✅ View before you edit
3. ✅ Test after each change
4. ✅ Use config values, don't hardcode
5. ✅ Preserve thread-safe patterns
6. ✅ When in doubt, git checkout and start fresh
7. ✅ **Keep documentation and version current**
