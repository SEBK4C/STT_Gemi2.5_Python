# Podcast Audio Transcription with Gemini 2.5 Pro

This project uses Google's Gemini 2.5 Pro model to transcribe audio files, particularly podcasts. It includes features for handling multiple speakers with different accents and languages, and formats the transcript with timestamps.

## Features

- Transcribes audio files (e.g., M4A, MP3) using Gemini 2.5 Pro.
- Handles multiple speakers with distinct accents (configurable in the prompt).
- Supports transcription of conversations involving multiple languages.
- Provides confidence scores for uncertain words.
- Formats the output with speaker identification and timestamps.
- Processes the raw transcript to consolidate speaker segments for better readability.
- Generates a bullet-point summary of the podcast content.

## Setup

1.  **Google API Key:**
    *   You need a Google API Key with access to the Gemini API.
    *   The script expects the API key to be available via `userdata.get('GOOGLE_AI_STUDIO')` if running in Google Colab. For local execution, you will need to modify the script to load your API key, for example, from an environment variable or a configuration file.
        ```python
        # Example for local execution (replace with your key management)
        # GOOGLE_API_KEY = "YOUR_GOOGLE_API_KEY"
        # client = genai.Client(api_key=GOOGLE_API_KEY)
        ```

2.  **Python Environment:**
    *   Ensure you have Python installed.
    *   Install the necessary libraries:
        ```bash
        pip install google-genai jinja2
        ```
    *   If you are not running in Google Colab, you will also need to install `ipython` if you want to use `IPython.display` for audio playback, though this is optional for the core transcription functionality.
        ```bash
        pip install ipython
        ```

3.  **Audio File:**
    *   Place your audio file in a location accessible by the script.
    *   Update the `file_path` variable in the script to point to your audio file.
        ```python
        file_path = "/path/to/your/audiofile.m4a" # Or .mp3, etc.
        ```
    *   If running locally, you won't be using Google Drive mounting, so the path will be a local system path.

## Running the Script

1.  **Configure the Prompt:**
    *   Modify the `prompt_template` within the script if needed, especially the `speakers_list` to match the primary speakers in your audio.
        ```python
        speakers_list = ["Speaker1Name", "Speaker2Name"] # Update as needed
        rendered_prompt = prompt_template.render(speakers=speakers_list)
        ```

2.  **Execute the Python Script:**
    ```bash
    python yt_gemini_2_5_pro_podcast_audio_transcription.py
    ```

3.  **Output:**
    *   The script will print the raw transcript, the processed transcript, and a summary to the console.
    *   It will also attempt to play a sample audio file at the end if `IPython.display` is available and an audio file exists at `/content/HS4830417304.mp3` (this part is likely specific to the original Colab environment and might need adjustment or removal for local use).

## Script Overview

-   **Initialization**: Sets up the Google GenAI client with an API key.
-   **Prompt Engineering**: Uses a Jinja2 template to create a detailed prompt for the Gemini model, specifying speaker characteristics, language expectations, and formatting guidelines.
-   **File Upload**: Uploads the audio file to the Google File API.
-   **Transcription**: Sends the prompt and the uploaded file to the `gemini-2.5-pro` model to generate the transcript.
-   **Timestamp Processing**: Includes functions (`timestamp_to_seconds`, `seconds_to_timestamp`) to convert timestamps between string format and total seconds.
-   **Transcript Processing**: The `process_transcript` function refines the raw transcript. It joins consecutive lines from the same speaker if they occur within a specified time window (`max_segment_duration`), improving readability.
-   **Summarization**: Sends the processed transcript to the Gemini model again with a new prompt to generate a bullet-point summary.

## Adapting for Local Use (Outside Colab)

-   **API Key Management**: Change how `GOOGLE_API_KEY` is obtained. Environment variables are a common practice.
-   **File Paths**: Adjust `file_path` to your local file system. Remove Google Drive mounting (`drive.mount('/content/drive')`).
-   **Package Installation**: The `!pip` command is for Colab. Ensure packages are installed in your local Python environment as described in the Setup section.
-   **IPython Display**: `IPython.display.Audio` is for displaying audio in Jupyter/Colab. For a local script, this line might cause an error or simply do nothing if not in an appropriate environment. You can remove it if not needed. 