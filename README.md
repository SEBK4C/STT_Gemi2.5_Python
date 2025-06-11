# Audio Transcription with Gemini 2.5 Pro (With outstanding accented language recognition and accuracy)

This project uses Google's Gemini 2.5 Pro model to transcribe audio files. It includes features for handling multiple speakers, different accents, multiple languages, and formats the transcript with timestamps. It can process individual audio files or all supported audio files within a directory and its subdirectories. Files longer than 59 minutes are automatically chunked, processed, and stitched back together.

## Features

-   **Transcription Engine**: Utilizes Google's Gemini 2.5 Pro model for audio-to-text conversion.
-   **Input Handling**:
    -   Accepts a single audio file path or a directory path as input via command-line argument.
    -   If a directory is provided, it recursively scans for audio files.
    -   Supported audio formats: `.m4a`, `.mp3`, `.wav`, `.flac`, `.ogg`, `.aac` (requires `ffmpeg` or `libav` for `pydub`).
-   **Long Audio Processing (Chunking)**:
    -   Automatically detects audio files longer than 59 minutes.
    -   Splits long audio files into manageable chunks (currently 59-minute segments).
    -   Transcribes each chunk individually.
    -   Normalizes timestamps across chunks to ensure a continuous timeline in the final transcript.
    -   Stitches chunk transcripts together to form one cohesive transcript.
-   **Speaker & Language Handling**:
    -   Designed to handle multiple speakers with distinct accents (configurable in the prompt template).
    -   Supports transcription of conversations involving multiple languages.
    -   Provides confidence scores for uncertain words (as per Gemini model capability).
-   **Output Format**:
    -   Generates a Markdown (`.md`) file for each processed audio file.
    -   The output file is named after the input audio file (e.g., `audio.m4a` -> `audio.md`) and saved in the same directory as the input audio file.
    -   The `.md` file includes:
        -   `## Summary`: A bullet-point summary of the entire audio content (generated from the full, potentially stitched, transcript).
        -   `## Transcript`: The full transcript formatted within a Markdown code block for readability and easy copying, with `HH:MM:SS` timestamps.
-   **Overwrite Control**:
    -   By default, skips processing an audio file if its corresponding `.md` output file already exists.
    -   Provides a `--replace` (or `-r`) command-line flag to force overwrite of existing `.md` files.
-   **Prompt Engineering**: Uses a Jinja2 template for detailed transcription instructions to the Gemini model.
-   **Server-Side File Management**: Attempts to delete uploaded audio files/chunks from Google's servers after processing to manage cloud storage.

## Setup

1.  **Google API Key**:
    *   You need a Google API Key with access to the Gemini API.
    *   Create a `.env` file in the same directory as the `Gemini_2_5_pro_audio_transcription.py` script.
    *   Add your API key to the `.env` file:
        ```
        GOOGLE_AI_STUDIO=your_actual_api_key_here
        ```

2.  **Python Environment & Dependencies**:
    *   Ensure you have Python installed (script is currently set to prefer ~=3.12, but >=3.9 should generally work).
    *   **`ffmpeg` or `libav` Requirement**: The script uses the `pydub` library for audio manipulation (like duration checking and splitting). `pydub` relies on `ffmpeg` or `libav` to handle various audio formats. **You must have `ffmpeg` (recommended) or `libav` installed on your system and available in your system's PATH.**
        -   Download `ffmpeg` from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
    *   You can manage dependencies using `uv` (or `pip`).

    **Using `uv` (Recommended Method 1 - Script-defined dependencies):**
    If your `uv` version supports PEP 723 for `uv run`:
    ```bash
    # uv will read dependencies from the /// script block at the top of the Python file.
    # Dependencies include: google-generativeai, jinja2, python-dotenv, pydub
    # No separate install step needed if you use `uv run` directly.
    ```

    **Using `uv` (Method 2 - Manual virtual environment):**
    ```bash
    # Create a virtual environment
    uv venv
    # Activate it (Linux/macOS)
    source .venv/bin/activate
    # Or (Windows)
    # .venv\Scripts\activate
    # Install dependencies
    uv pip install google-generativeai jinja2 python-dotenv pydub
    ```

    **Using `pip` (Traditional method):**
    ```bash
    # Create a virtual environment (optional but recommended)
    # python -m venv .venv
    # source .venv/bin/activate # or .venv\Scripts\activate
    pip install google-generativeai jinja2 python-dotenv pydub
    ```

## Running the Script

1.  **Prepare your audio file(s)**.
2.  **Open your terminal** and navigate to the project directory.
3.  **Execute the script**, providing the path to your audio file or a directory containing audio files.

    **Basic Usage (single file or directory):**
    ```bash
    # Using uv run (if dependencies are in the script block)
    uv run yt_gemini_2_5_pro_audio_transcription.py path/to/your/audio_or_directory

    # Using python (if you manually created a venv and installed dependencies)
    python yt_gemini_2_5_pro_audio_transcription.py path/to/your/audio_or_directory
    ```
    Examples:
    ```bash
    python yt_gemini_2_5_pro_audio_transcription.py Multi-Audio/episode1.m4a
    python yt_gemini_2_5_pro_audio_transcription.py Multi-Audio/
    ```

4.  **To Overwrite Existing Transcriptions:**
    Use the `-r` or `--replace` flag:
    ```bash
    python yt_gemini_2_5_pro_audio_transcription.py path/to/your/audio_or_directory --replace
    uv run yt_gemini_2_5_pro_audio_transcription.py path/to/your/audio_or_directory -r
    ```

5.  **Output:**
    *   The script will print progress messages to the console.
    *   For each processed audio file, an `.md` file containing the summary and transcript will be saved in the same directory as the source audio file.

## Script Overview (Key Functions)

-   `main(input_path_arg, replace_flag)`: Parses command-line arguments and orchestrates file/directory processing.
-   `process_audio_file(audio_file_path, replace_existing)`: Main logic for handling a single audio file. Checks duration, decides on chunking, calls processing functions, and manages output file creation.
-   `_get_audio_duration_ms(file_path)`: Returns the duration of an audio file in milliseconds using `pydub`.
-   `_split_audio_into_chunks(original_file_path, temp_dir_for_chunks)`: Splits a long audio file into smaller, manageable chunks.
-   `_transcribe_and_process_segment(segment_path, time_offset_ms)`: Handles uploading a single audio segment (original file or chunk) to Google, getting the transcription, applying initial formatting, and normalizing timestamps based on the given offset.
-   `_generate_summary_for_text(full_transcript_text)`: Sends the complete (potentially stitched) transcript to Gemini to generate a summary.
-   `timestamp_to_seconds(ts_str)` & `seconds_to_timestamp(total_seconds)`: Utility functions for timestamp conversions.
-   `process_transcript(input_text, max_segment_duration)`: Formats the raw transcript from Gemini (consolidates speaker lines, etc.).
-   `get_output_path(input_audio_path)`: Determines the output `.md` file path based on the input audio file path.

## Customization

-   **Prompt Template**: The `prompt_template_text` variable in the script contains the detailed instructions given to the Gemini model. You can customize this, especially the `speakers_list`, to better suit your audio content.
-   **Chunk Duration**: `MAX_CHUNK_DURATION_MINUTES` (currently 59 minutes) can be adjusted if needed, though an hour is a general guideline for many audio APIs.

## Adapting for Local Use (Outside Colab)

-   **API Key Management**: Change how `GOOGLE_API_KEY` is obtained. Environment variables are a common practice.
-   **File Paths**: Adjust `file_path` to your local file system. Remove Google Drive mounting (`drive.mount('/content/drive')`).
-   **Package Installation**: The `!pip` command is for Colab. Ensure packages are installed in your local Python environment as described in the Setup section.
-   **IPython Display**: `IPython.display.Audio` is for displaying audio in Jupyter/Colab. For a local script, this line might cause an error or simply do nothing if not in an appropriate environment. You can remove it if not needed. 