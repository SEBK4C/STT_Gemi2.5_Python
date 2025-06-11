# /// script
# requires-python = "~=3.12"
# dependencies = [
#   "google-generativeai",
#   "jinja2",
#   "python-dotenv",
#   "pydub"
# ]
# ///
# -*- coding: utf-8 -*-
"""YT Gemini 2.5 Pro Podcast Audio transcription

This script is designed to run locally.
It can process a single audio file or all audio files within a directory (and its subdirectories).
By default, it will skip processing if an output .md file already exists for an audio file.
Use the --replace flag to overwrite existing .md files.

Files longer than 59 minutes will be split into chunks, processed individually, 
and then stitched back together with normalized timestamps. The summary will be for the entire content.

NOTE: This script uses 'pydub' for audio processing, which relies on 'ffmpeg' or 'libav'
      for handling various audio formats. Ensure ffmpeg (or libav) is installed on your
      system and accessible in your PATH for full functionality.

Supported audio file extensions: .m4a, .mp3, .wav, .flac, .ogg, .aac

Method 1: Using uv with embedded dependencies:
1. Create a .env file in the same directory as this script with your Google API Key:
   GOOGLE_AI_STUDIO=your_api_key_here
2. Run the script:
   uv run Gemini_2_5_pro_audio_transcription.py path/to/your/audiofile_or_directory
   To overwrite existing transcriptions:
   uv run Gemini_2_5_pro_audio_transcription.py path/to/your/audiofile_or_directory --replace

Method 2: Using uv with manual virtual environment setup:
1. Create a virtual environment:
   uv venv
2. Activate the virtual environment:
   source .venv/bin/activate  # For Linux/macOS
   .venv\Scripts\activate    # For Windows
3. Install dependencies:
   uv pip install google-generativeai jinja2 python-dotenv pydub
4. Create a .env file as described in Method 1.
5. Run the script:
   python Gemini_2_5_pro_audio_transcription.py path/to/your/audiofile_or_directory
   To overwrite existing transcriptions:
   python Gemini_2_5_pro_audio_transcription.py path/to/your/audiofile_or_directory --replace

Original file was located at
    https://colab.research.google.com/drive/1p3VB7BIcZ0gRP--6BCqW_dRRGHZrtguM

# Google Gemini 2.5 Pro for Audio Understanding & Transcription
"""

# #!pip -q install google-generativeai jinja2 # This line is for Colab, dependencies should be installed via uv pip install or handled by `uv run`

import sys
print(f"DEBUG: Python version for script execution: {sys.version}")

import os
import argparse
import tempfile # For temporary chunk files
import shutil # For removing temp directory
from dotenv import load_dotenv
from google import genai
from google.genai import types
from jinja2 import Template
import re
import datetime
from pydub import AudioSegment # For audio duration and splitting
from pydub.exceptions import CouldntDecodeError

# Supported audio file extensions
AUDIO_EXTENSIONS = [".m4a", ".mp3", ".wav", ".flac", ".ogg", ".aac"]
MAX_CHUNK_DURATION_MINUTES = 59 # Max duration for a single chunk sent to API
MAX_CHUNK_DURATION_MS = MAX_CHUNK_DURATION_MINUTES * 60 * 1000
# MAX_CHUNK_DURATION_MS = 10 * 60 * 1000 # Using 10 minutes for easier testing, change to 59 later
CHUNK_EXPORT_FORMAT = "wav" # WAV is good for quality and compatibility

# Load environment variables from .env file
load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_AI_STUDIO')

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_AI_STUDIO key not found. Make sure it's set in your .env file.")

# Initialize GenAI Client (do this once)
try:
    client = genai.Client(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"Failed to initialize Google GenAI Client: {e}")
    print("Please ensure your GOOGLE_AI_STUDIO key is correct and has access.")
    exit(1)

"""## Podcast Example

"""

# --- Helper function to derive output path ---
def get_output_path(input_audio_path):
    directory = os.path.dirname(input_audio_path)
    base_name = os.path.basename(input_audio_path)
    file_name_without_ext = os.path.splitext(base_name)[0]
    output_filename = f"{file_name_without_ext}.md"
    return os.path.join(directory, output_filename)

# --- Jinja2 Prompt Template ---
prompt_template_text = """Generate a transcript of the episode.

**Important Context & Instructions:**

* **Primary Speakers & Accents:** Be aware of two likely primary speakers:
    * **Declan Kennedy:** Speaks with a strong Irish accent.
    * **Interviewer:** Speaks with a strong German accent.

* **Languages:** Conversations may be in German, English, Gaelic, and other languages. There will be a wide variety of accents.

* **Unclear Words:** If you are uncertain about a word, provide your best guess followed by a percentage confidence score in brackets.
    eg: I think it was about the subsidiarity [70% confidence].

* **Multiple Speakers:** There will potentially be multiple other speakers. If you really don't know the speaker's name, identify them with a letter of the alphabet (e.g., Speaker A, Speaker B).

**Transcript Formatting:**

Include timestamps and identify speakers.

Speakers are:
{% for speaker in speakers %}- {{ speaker }}{% if not loop.last %}\n{% endif %}{% endfor %}

eg:
[00:00] Declan: Hello there.
[00:02] Interviewer: Hi Declan.

It is important to include the correct speaker names. Use the names you identified earlier.

If there is music or a short jingle playing, signify like so:
[01:02] [MUSIC] or [01:02] [JINGLE]

If you can identify the name of the music or jingle playing then use that instead, eg:
[01:02] [Firework by Katy Perry] or [01:02] [The Sofa Shop jingle]

If there is some other sound playing try to identify the sound, eg:
[01:02] [Bell ringing]

Each individual caption should be quite short, a few short sentences at most.

Signify the end of the episode with [END].

Don't use any markdown formatting, like bolding or italics.

Only use characters from the English alphabet, unless you genuinely believe foreign characters are correct.

It is important that you use the correct words and spell everything correctly. Use the context of the podcast to help.
If the hosts discuss something like a movie, book or celebrity, make sure the movie, book, or celebrity name is spelled correctly."""
prompt_template = Template(prompt_template_text)

# Example of how to render the template (optional, can be customized per audio if needed)
speakers_list = ["Declan", "Interviewer", "Guest"]
rendered_prompt = prompt_template.render(speakers=speakers_list)
# print(rendered_prompt) # Keep commented unless debugging prompt

"""## Uploading the MP3"""

# from google.colab import drive # Colab specific
# drive.mount('/content/drive') # Colab specific

# path to the file to upload will now come from CLI
# file_path = "/path/to/your/audiofile.m4a"

# --- Audio Processing Helper Functions ---
def _get_audio_duration_ms(file_path):
    try:
        audio = AudioSegment.from_file(file_path)
        return len(audio)
    except CouldntDecodeError:
        print(f"Error: Could not decode audio file (pydub): {file_path}. Ensure ffmpeg is installed and the file is not corrupt.")
        return None
    except FileNotFoundError:
        print(f"Error: Audio file not found (pydub): {file_path}")
        return None
    except Exception as e:
        print(f"Error getting audio duration for {file_path}: {e}")
        return None

def _split_audio_into_chunks(original_file_path, temp_dir_for_chunks):
    print(f"Splitting {original_file_path} into chunks...")
    chunks_info = []
    try:
        audio = AudioSegment.from_file(original_file_path)
        total_duration_ms = len(audio)

        for i, start_ms in enumerate(range(0, total_duration_ms, MAX_CHUNK_DURATION_MS)):
            end_ms = min(start_ms + MAX_CHUNK_DURATION_MS, total_duration_ms)
            chunk_audio = audio[start_ms:end_ms]
            chunk_filename = f"chunk_{i+1}.{CHUNK_EXPORT_FORMAT}"
            chunk_path = os.path.join(temp_dir_for_chunks, chunk_filename)
            chunk_audio.export(chunk_path, format=CHUNK_EXPORT_FORMAT)
            chunks_info.append({"path": chunk_path, "duration_ms": len(chunk_audio)})
            print(f"  Created chunk: {chunk_path} (duration: {len(chunk_audio)/1000:.2f}s)")
        return chunks_info
    except Exception as e:
        print(f"Error splitting audio file {original_file_path}: {e}")
        return [] # Return empty list on failure

def _transcribe_and_process_segment(segment_path, time_offset_ms=0):
    print(f"  Processing segment: {segment_path} with time offset: {time_offset_ms/1000:.2f}s")
    uploaded_file_server_obj = None
    try:
        print(f"    Uploading {os.path.basename(segment_path)} to Google...")
        uploaded_file_server_obj = client.files.upload(file=segment_path)
        print(f"    Uploaded {os.path.basename(segment_path)} as server file: {uploaded_file_server_obj.name}")

        print("    Generating raw transcript from model...")
        response_transcript = client.models.generate_content(
            model="gemini-2.5-pro-preview-06-05",
            contents=[rendered_prompt, uploaded_file_server_obj],
        )
        raw_transcript_text = response_transcript.text
        
        # Process the raw transcript (e.g., join lines, format speakers)
        processed_segment_transcript = process_transcript(raw_transcript_text, max_segment_duration=30) # Using existing function

        # Normalize timestamps for this segment
        normalized_transcript_lines = []
        for line in processed_segment_transcript.splitlines():
            match = re.match(r'^(\[(?:\d{2}:)?\d{2}:\d{2}(?:\.\d+)?\])(.*)$', line)
            if match:
                ts_str = match.group(1).strip('[]')
                rest_of_line = match.group(2)
                original_seconds = timestamp_to_seconds(ts_str)
                if original_seconds is not None:
                    normalized_seconds = original_seconds + (time_offset_ms / 1000)
                    new_ts_str = seconds_to_timestamp(normalized_seconds)
                    normalized_transcript_lines.append(f"[{new_ts_str}]{rest_of_line}")
                else:
                    normalized_transcript_lines.append(line) # Keep line as is if timestamp parsing fails
            else:
                normalized_transcript_lines.append(line) # Non-timestamped lines (e.g., [MUSIC])
        
        return "\n".join(normalized_transcript_lines)

    except Exception as e:
        print(f"    Error processing segment {segment_path}: {e}")
        return None
    finally:
        if uploaded_file_server_obj:
            print(f"    Attempting to delete {uploaded_file_server_obj.name} from server...")
            try:
                client.files.delete(name=uploaded_file_server_obj.name)
                print(f"    Successfully deleted {uploaded_file_server_obj.name}.")
            except Exception as delete_err:
                print(f"    Could not delete {uploaded_file_server_obj.name}: {delete_err}")

def _generate_summary_for_text(full_transcript_text):
    print("Generating overall summary...")
    summary_prompt_template_text = """Make me a set of notes in the form of bullet points  \
(with time stamps at end of each idea (in the form HH:MM:SS)) to summarize this podcast \
The bullets should be based on the idea and don't need to be sequential.
Structure the ideas with a heading and subheadings. Don't include any prefix. here is transcript below :\n\n"""
    try:
        response_summary = client.models.generate_content(
            model="gemini-2.5-pro-preview-06-05",
            contents=[summary_prompt_template_text + full_transcript_text],
        )
        return response_summary.text
    except Exception as e:
        print(f"An error occurred during summary generation: {e}")
        return "Error: Could not generate summary."

# --- Core processing logic for a single audio file (handles chunking) ---
def process_audio_file(audio_file_path, replace_existing):
    output_file_path = get_output_path(audio_file_path)
    print(f"\n--- Evaluating Audio File: {audio_file_path} ---")

    if os.path.exists(output_file_path) and not replace_existing:
        print(f"Output file {output_file_path} already exists. Skipping. Use --replace to overwrite.")
        print(f"--- Finished (skipped): {audio_file_path} ---")
        return
    elif os.path.exists(output_file_path) and replace_existing:
        print(f"Output file {output_file_path} already exists. Overwriting as --replace is set.")

    file_duration_ms = _get_audio_duration_ms(audio_file_path)
    if file_duration_ms is None:
        print(f"Could not determine duration for {audio_file_path}. Skipping.")
        print(f"--- Finished (error determining duration): {audio_file_path} ---")
        return

    print(f"Duration: {file_duration_ms / 1000 / 60:.2f} minutes.")
    final_transcript_text = ""
    
    if file_duration_ms <= MAX_CHUNK_DURATION_MS:
        print("Processing as a single segment.")
        final_transcript_text = _transcribe_and_process_segment(audio_file_path, time_offset_ms=0)
        if final_transcript_text is None:
            print(f"Failed to transcribe single segment for {audio_file_path}. Skipping file.")
            print(f"--- Finished (error): {audio_file_path} ---")
            return
    else:
        print(f"Audio exceeds {MAX_CHUNK_DURATION_MINUTES} minutes. Splitting into chunks.")
        temp_chunk_dir = tempfile.mkdtemp()
        print(f"Created temporary directory for chunks: {temp_chunk_dir}")
        chunk_infos = _split_audio_into_chunks(audio_file_path, temp_chunk_dir)

        if not chunk_infos: # Splitting failed
            print(f"Failed to split {audio_file_path} into chunks. Skipping file.")
            shutil.rmtree(temp_chunk_dir)
            print(f"Removed temporary directory: {temp_chunk_dir}")
            print(f"--- Finished (error splitting): {audio_file_path} ---")
            return

        all_stitched_transcripts = []
        current_time_offset_ms = 0
        chunk_processing_successful = True

        for chunk_info in chunk_infos:
            normalized_chunk_transcript = _transcribe_and_process_segment(chunk_info["path"], current_time_offset_ms)
            if normalized_chunk_transcript is None:
                chunk_processing_successful = False
                break # Stop processing further chunks for this file
            all_stitched_transcripts.append(normalized_chunk_transcript)
            current_time_offset_ms += chunk_info["duration_ms"]
        
        shutil.rmtree(temp_chunk_dir) # Clean up temp chunks
        print(f"Removed temporary directory: {temp_chunk_dir}")

        if not chunk_processing_successful:
            print(f"Failed to process one or more chunks for {audio_file_path}. Skipping final output for this file.")
            print(f"--- Finished (error in chunk processing): {audio_file_path} ---")
            return
        
        final_transcript_text = "\n".join(all_stitched_transcripts)

    # Generate overall summary from the final (potentially stitched) transcript
    summary_text = _generate_summary_for_text(final_transcript_text)

    # Write to output file
    try:
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("## Summary\n\n")
            f.write(summary_text)
            f.write("\n\n## Transcript\n\n")
            f.write("```text\n")
            f.write(final_transcript_text)
            f.write("\n```\n")
        print(f"Successfully wrote summary and transcript to: {output_file_path}")
    except Exception as e:
        print(f"Error writing to output file {output_file_path}: {e}")

    print(f"--- Finished processing: {audio_file_path} ---")

def timestamp_to_seconds(ts_str):
    """
    Converts an HH:MM:SS or MM:SS timestamp string to total seconds.

    Args:
        ts_str (str): Timestamp string in HH:MM:SS or MM:SS format.

    Returns:
        int or None: Total seconds from midnight, or None if parsing fails.
    """
    try:
        # Remove milliseconds if present
        ts_str = ts_str.split('.')[0]
        # Split timestamp into parts
        parts = list(map(int, ts_str.split(':')))

        if len(parts) == 3: # HH:MM:SS format
            h, m, s = parts
            return h * 3600 + m * 60 + s
        elif len(parts) == 2: # MM:SS format
            m, s = parts
            return m * 60 + s
        else:
            # Invalid number of parts
            return None
    except (ValueError, AttributeError, IndexError):
        # Return None if parsing fails for any reason
        return None

def seconds_to_timestamp(total_seconds):
    """
    Converts total seconds to an HH:MM:SS timestamp string.
    (No changes needed here, always outputs full format)

    Args:
        total_seconds (int): Total seconds from midnight.

    Returns:
        str: Timestamp string in HH:MM:SS format.
    """
    if total_seconds is None or total_seconds < 0:
        total_seconds = 0 # Default to 0 if input is invalid or negative
    # Calculate hours, minutes, and seconds
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    # Format as HH:MM:SS with leading zeros
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

def process_transcript(input_text, max_segment_duration=30):
    """
    Processes transcript text to join lines based on speaker and time.

    Joins consecutive lines if the speaker is the same AND the time elapsed
    since the start of the current segment is within max_segment_duration.
    Starts a new segment if the speaker changes OR the time limit is exceeded.
    Includes non-dialogue lines (like [MUSIC]) as separate lines.

    Args:
        input_text (str): The raw transcript text (multiline string).
        max_segment_duration (int): Maximum duration in seconds for a single
                                     speaker's segment before forcing a new
                                     timestamp. Defaults to 30.

    Returns:
        str: The processed transcript text as a multiline string.
    """
    # Use splitlines() for more robust handling of different newline characters
    lines = input_text.strip().splitlines()
    output_lines = [] # List to store the processed output lines

    # Variables to keep track of the current segment being built
    current_segment_start_ts_str = None # Timestamp string of the segment start
    current_segment_start_seconds = None # Timestamp in seconds of the segment start
    current_speaker = None               # Speaker of the current segment
    current_text_parts = []              # List of text pieces in the current segment

    # --- UPDATED Regex ---
    # Capture timestamp [HH:MM:SS] or [MM:SS], speaker, and text content.
    # Made the HH: part optional using (?:...)?
    line_regex = re.compile(r'^\[((?:\d{2}:)?\d{2}:\d{2}(?:\.\d+)?)\]\s*([^:]+?):\s*(.*)$')
    # Breakdown of timestamp part: ((?:\d{2}:)?\d{2}:\d{2}(?:\.\d+)?)
    # (                    - Start capture group 1 (full timestamp)
    #  (?:               - Start non-capturing group for HH:
    #   \d{2}:            - Match two digits and a colon (HH:)
    #  )?                - End non-capturing group, make it optional
    #  \d{2}:\d{2}        - Match MM:SS (required)
    #  (?:\.\d+)?        - Optionally match milliseconds (non-capturing)
    # )                    - End capture group 1

    for i, line in enumerate(lines):
        line = line.strip() # Remove leading/trailing whitespace
        if not line:
            continue # Skip empty lines

        match = line_regex.match(line)

        # --- Debugging Prints (Keep commented unless needed) ---
        # print(f"\nProcessing Line {i+1}: {line}")
        # if match:
        #     _ts, _spk, _txt = match.groups()
        #     _sec = timestamp_to_seconds(_ts)
        #     print(f"  Parsed: ts={_ts}, speaker='{_spk.strip()}', text='{_txt.strip()}', seconds={_sec}")
        # else:
        #     print(f"  No Match: Treating as non-dialogue.")
        # print(f"  Current Segment State: speaker='{current_speaker}', start_ts='{current_segment_start_ts_str}', start_sec={current_segment_start_seconds}")
        # --- End Debugging Prints ---

        if not match:
            # --- Handle non-standard lines ---
            if current_speaker is not None:
                segment_text = ' '.join(filter(None, current_text_parts))
                # print(f"  Finalizing previous (due to non-match): [{current_segment_start_ts_str}] {current_speaker}: {segment_text}") # DEBUG
                output_lines.append(f"[{current_segment_start_ts_str}] {current_speaker}: {segment_text}")
                current_speaker = None
                current_text_parts = []
                current_segment_start_ts_str = None
                current_segment_start_seconds = None
            # print(f"  Adding non-dialogue line: {line}") # DEBUG
            output_lines.append(line)
            continue

        # --- Process standard dialogue lines ---
        ts_str, speaker, text = match.groups()
        speaker = speaker.strip()
        text = text.strip()
        # Use the updated function to parse timestamp
        current_seconds = timestamp_to_seconds(ts_str)

        if current_seconds is None:
             print(f"Warning: Skipping line {i+1} due to invalid timestamp format: {line}")
             continue

        # --- Logic to decide whether to start a new segment ---
        start_new_segment = False
        reason = "" # DEBUG
        if current_speaker is None:
            start_new_segment = True
            reason = "No active segment" # DEBUG
        elif speaker != current_speaker:
            start_new_segment = True
            reason = f"Speaker changed ('{speaker}' != '{current_speaker}')" # DEBUG
        # Ensure start_seconds is not None before comparison
        elif current_segment_start_seconds is not None and \
             current_seconds - current_segment_start_seconds > max_segment_duration:
            start_new_segment = True
            reason = f"Time limit exceeded ({current_seconds - current_segment_start_seconds}s > {max_segment_duration}s)" # DEBUG
        else:
            reason = "Continuing segment" # DEBUG

        # print(f"  Decision: {'Start new segment' if start_new_segment else 'Continue segment'}. Reason: {reason}") # DEBUG

        # --- Process based on the decision ---
        if start_new_segment:
            if current_speaker is not None:
                segment_text = ' '.join(filter(None, current_text_parts))
                # print(f"  Finalizing previous (due to new segment): [{current_segment_start_ts_str}] {current_speaker}: {segment_text}") # DEBUG
                output_lines.append(f"[{current_segment_start_ts_str}] {current_speaker}: {segment_text}")

            # Use seconds_to_timestamp to ensure consistent HH:MM:SS output format
            current_segment_start_ts_str = seconds_to_timestamp(current_seconds)
            current_segment_start_seconds = current_seconds
            current_speaker = speaker
            current_text_parts = [text]
            # print(f"  Starting new segment: speaker='{speaker}', start_ts='{current_segment_start_ts_str}', start_sec={current_segment_start_seconds}, text='{text}'") # DEBUG
        else:
            # Continue the current segment
            if text:
                # print(f"  Appending text: '{text}'") # DEBUG
                current_text_parts.append(text)
            # else: # DEBUG
                # print(f"  Skipping empty text append.") # DEBUG

    # --- Finalize the very last segment ---
    if current_speaker is not None:
        segment_text = ' '.join(filter(None, current_text_parts))
        # print(f"Finalizing last segment: [{current_segment_start_ts_str}] {current_speaker}: {segment_text}") # DEBUG
        output_lines.append(f"[{current_segment_start_ts_str}] {current_speaker}: {segment_text}")

    return "\n".join(output_lines)

# --- Main execution block ---
def main(input_path_arg, replace_flag):
    if not os.path.exists(input_path_arg):
        print(f"Error: Input path does not exist: {input_path_arg}")
        return

    if os.path.isfile(input_path_arg):
        # Check if the single file is a supported audio type
        _, file_ext = os.path.splitext(input_path_arg)
        if file_ext.lower() in AUDIO_EXTENSIONS:
            process_audio_file(input_path_arg, replace_flag)
        else:
            print(f"Skipping non-audio file: {input_path_arg} (supported: {AUDIO_EXTENSIONS})")
    elif os.path.isdir(input_path_arg):
        print(f"Scanning directory: {input_path_arg} for audio files...")
        found_audio_files = False
        for root, _, files in os.walk(input_path_arg):
            for file in files:
                _, file_ext = os.path.splitext(file)
                if file_ext.lower() in AUDIO_EXTENSIONS:
                    found_audio_files = True
                    audio_file_full_path = os.path.join(root, file)
                    process_audio_file(audio_file_full_path, replace_flag)
        if not found_audio_files:
            print(f"No audio files found in {input_path_arg} (supported extensions: {AUDIO_EXTENSIONS})")
    else:
        print(f"Error: Input path is not a valid file or directory: {input_path_arg}")

    print("\nAll tasks finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transcribe and summarize audio file(s) using Gemini 2.5 Pro. Accepts a single audio file or a directory to scan for audio files.",
        formatter_class=argparse.RawTextHelpFormatter # For better help text formatting
    )
    parser.add_argument(
        "input_path", 
        help="Path to the audio file or directory to process.\nSupported audio extensions: " + ", ".join(AUDIO_EXTENSIONS)
    )
    parser.add_argument(
        "-r", "--replace",
        action="store_true",
        help="Replace (overwrite) existing .md transcription files. Default is to skip if .md exists."
    )
    args = parser.parse_args()
    
    main(args.input_path, args.replace)

