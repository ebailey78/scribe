"""
Meeting synthesis and AI-powered note generation for Scribe.

This module handles post-processing of transcripts using AI to generate
structured meeting notes with summaries, titles, and detailed segments.
"""

import os
import re
import requests
import shutil
from colorama import Fore, Style
from tqdm import tqdm

# Configuration: Logseq Graph Path
# Set this to your Logseq pages folder
LOGSEQ_GRAPH_PATH = r"C:\Users\idemr\Logseq\pages"  # Update this path!


class MeetingSynthesizer:
    """Post-processing engine that transforms raw transcripts into structured Logseq notes using Qwen3:8b."""
    
    def __init__(self, session_dir):
        self.session_dir = session_dir
        self.transcript_path = os.path.join(session_dir, "transcript_full.txt")
        self.output_path = os.path.join(session_dir, "notes_logseq.md")
        self.final_path = None  # Will be set after title generation
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "qwen3:8b"
        self.system_prompt = "You are an expert technical secretary. Output strictly in Logseq Markdown format."
    
    def read_transcript(self):
        """Load the raw transcript file."""
        try:
            with open(self.transcript_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"{Fore.RED}Error: transcript_full.txt not found in {self.session_dir}{Style.RESET_ALL}")
            return ""
    
    def extract_timestamps(self, text):
        """Extract all timestamps from text in format [HH:MM:SS]."""
        pattern = r'\[(\d{2}:\d{2}:\d{2})\]'
        matches = re.findall(pattern, text)
        return matches
    
    def split_into_blocks_with_timestamps(self, text, words_per_block=1000):
        """Split transcript into blocks and extract time ranges."""
        lines = text.split('\n')
        blocks = []
        current_block = []
        current_words = 0
        
        for line in lines:
            words_in_line = len(line.split())
            current_block.append(line)
            current_words += words_in_line
            
            if current_words >= words_per_block:
                block_text = '\n'.join(current_block)
                timestamps = self.extract_timestamps(block_text)
                
                if timestamps:
                    start_time = timestamps[0][:5]  # HH:MM
                    end_time = timestamps[-1][:5]  # HH:MM
                    time_range = f"[{start_time} - {end_time}]"
                else:
                    time_range = "[Unknown Time]"
                
                blocks.append({
                    'text': block_text,
                    'time_range': time_range
                })
                current_block = []
                current_words = 0
        
        # Add remaining lines as final block
        if current_block:
            block_text = '\n'.join(current_block)
            timestamps = self.extract_timestamps(block_text)
            
            if timestamps:
                start_time = timestamps[0][:5]
                end_time = timestamps[-1][:5]
                time_range = f"[{start_time} - {end_time}]"
            else:
                time_range = "[Unknown Time]"
            
            blocks.append({
                'text': block_text,
                'time_range': time_range
            })
        
        return blocks
    
    def call_ollama(self, prompt, context=""):
        """Call Ollama API with qwen3:8b model."""
        payload = {
            "model": self.model,
            "prompt": f"{context}\n\n{prompt}",
            "stream": False,
            "system": self.system_prompt
        }
        
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Ollama API Error: {e}{Style.RESET_ALL}")
            return f"[ERROR: Could not generate content - {str(e)}]"
    
    def generate_summary(self, transcript):
        """Generate executive summary and participant list."""
        # Truncate to first 8000 tokens (~6000 words) if too large
        words = transcript.split()
        if len(words) > 6000:
            truncated = " ".join(words[:6000])
            context = truncated + "\n\n[... transcript continues ...]"
        else:
            context = transcript
        
        prompt = """Analyze this meeting transcript and provide:

1. **Executive Summary** (2-3 sentences): What was this meeting about?
2. **Participants** (if identifiable from the text, otherwise write "Unknown")
3. **Key Topics Discussed** (3-5 bullet points)

Format the output in clean Logseq Markdown."""
        
        return self.call_ollama(prompt, context)
    
    def generate_meeting_title(self, summary):
        """Generate a short, filename-safe title based on the summary."""
        prompt = """Based on the summary above, generate a short, memorable, filename-safe title (max 5 words). Use underscores. Example: 'Q3_Budget_Review' or 'Project_Alpha_Kickoff'. Output ONLY the title, no explanation."""
        
        title = self.call_ollama(prompt, summary).strip()
        
        # Clean up: remove any quotes, newlines, or invalid filename chars
        title = re.sub(r'[^\w\s-]', '', title)
        title = re.sub(r'\s+', '_', title)
        title = title[:50]  # Limit length
        
        return title if title else "Meeting_Notes"
    
    def generate_detailed_notes(self, block, block_num, time_range):
        """Generate structured notes for a transcript block."""
        prompt = f"""Summarize this segment of a meeting transcript:

Extract and organize:
- **Key Points** (bullet points)
- **Decisions Made** (if any)
- **Action Items** (if any)
- **Technical Terms / Acronyms** (define if possible)

Output in Logseq Markdown format with proper heading levels."""
        
        return self.call_ollama(prompt, block)
    
    def export_to_logseq(self, final_file_path):
        """Copy the final notes to Logseq graph if path exists."""
        if not os.path.exists(LOGSEQ_GRAPH_PATH):
            print(f"{Fore.YELLOW}⚠️  Logseq path not found. Notes saved to local session folder only.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}   Configure LOGSEQ_GRAPH_PATH in scribe/synthesis.py{Style.RESET_ALL}")
            return False
        
        try:
            dest = os.path.join(LOGSEQ_GRAPH_PATH, os.path.basename(final_file_path))
            shutil.copy2(final_file_path, dest)
            print(f"{Fore.GREEN}✅ Exported to Logseq: {dest}{Style.RESET_ALL}")
            return True
        except Exception as e:
            print(f"{Fore.RED}Failed to export to Logseq: {e}{Style.RESET_ALL}")
            return False
    
    def run(self):
        """Execute the full synthesis pipeline."""
        print(f"{Fore.CYAN}📖 Reading transcript...{Style.RESET_ALL}")
        transcript = self.read_transcript()
        
        if not transcript.strip():
            print(f"{Fore.RED}Transcript is empty. Skipping synthesis.{Style.RESET_ALL}")
            return
        
        # Step 1: Generate Executive Summary
        print(f"{Fore.CYAN}🧠 Generating Executive Summary with {self.model}...{Style.RESET_ALL}")
        summary = self.generate_summary(transcript)
        
        # Step 2: Generate Meeting Title
        print(f"{Fore.CYAN}📝 Generating meeting title...{Style.RESET_ALL}")
        title = self.generate_meeting_title(summary)
        
        # Construct final filename
        date_prefix = os.path.basename(self.session_dir).split('_')[0]  # Extract date from session_id
        final_filename = f"{date_prefix}_{title}.md"
        self.final_path = os.path.join(self.session_dir, final_filename)
        
        # Write header to file
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(f"# {title.replace('_', ' ')}\n\n")
            f.write(f"**Session**: {os.path.basename(self.session_dir)}\n\n")
            f.write(summary)
            f.write("\n\n---\n\n")
        
        # Step 3: Generate Detailed Notes with time-based headers
        blocks = self.split_into_blocks_with_timestamps(transcript)
        print(f"{Fore.CYAN}📚 Processing {len(blocks)} blocks...{Style.RESET_ALL}")
        
        with open(self.output_path, "a", encoding="utf-8") as f:
            for i, block_data in enumerate(tqdm(blocks, desc="Synthesizing blocks", unit="block", ncols=80)):
                detailed = self.generate_detailed_notes(block_data['text'], i+1, block_data['time_range'])
                f.write(f"\n## {block_data['time_range']} Discussion Segment\n\n")
                f.write(detailed)
                f.write("\n\n")
        
        # Step 4: Rename file
        try:
            os.rename(self.output_path, self.final_path)
            print(f"{Fore.GREEN}✅ Synthesis complete!{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}Could not rename file: {e}{Style.RESET_ALL}")
            self.final_path = self.output_path
        
        # Step 5: Export to Logseq
        self.export_to_logseq(self.final_path)
        
        # Final output
        print(f"\n{Fore.GREEN}📄 Final notes:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{self.final_path}{Style.RESET_ALL}")
