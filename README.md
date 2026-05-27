# YouTube Trends Finder

A Python-based tool to monitor, score, and analyze trending YouTube videos about specific topics. It calculates a real-time "views per minute" score to identify rapidly rising videos and uses the Gemini API to generate strategic social listening reports and advertiser decks.

## Features

*   **YouTube Scraper**: Fetches videos based on search queries or Topic IDs (Knowledge Graph) within a specific lookback window (e.g., last 6 hours).
*   **Composite Scoring**: Ranks videos based on a combination of views per minute, likes, and comment activity.
*   **Content Extraction**: Automatically fetches video comments and attempts to retrieve/generate transcripts.
*   **AI-Powered Insights (Gemini)**:
    *   Generates **Social Listening Reports** detailing top themes, audience sentiment, and key takeaways.
    *   Creates **Advertiser Pitch Decks** highlighting what is trending in the last 24 hours with strategic brand opportunities.
*   **Interactive Dashboard**: A Streamlit-based web application to visualize trends, explore video details, view word clouds, and interact with the data.

## Project Structure

```
yt-trends-finder/
├── analyzer.py                 # Core CLI tool to scrape and score videos
├── app.py                      # Streamlit web dashboard
├── finalize_run.py             # Utility to export data and upload to Google Drive
├── generate_advertiser_deck.py # Script to generate the advertiser deck via Gemini
├── generate_enhanced_report.py # Script to generate enhanced social listening reports
├── generate_final_report.py    # Helper to format final reports
├── generate_html_deck.py       # Helper to generate HTML presentations
├── topic_analyzer.py           # Script to analyze topics using Gemini
└── requirements.txt            # Python dependencies
```

## Setup Instructions

### Prerequisites

*   Python 3.8 or higher
*   A Google Cloud Project with the **YouTube Data API v3** enabled.
*   A YouTube API Key.
*   A Gemini API Key (you can use the same Google Cloud project or a separate Google AI Studio key).

### Installation

1.  Clone this repository.
2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3.  Create a `.env` file in the root directory and populate it with your API keys:

    ```env
    YOUTUBE_API_KEY=your_youtube_api_key_here
    GEMINI_API_KEY=your_gemini_api_key_here

    # Optional: Google Drive Folder ID if using finalize_run.py
    GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id_here
    ```

## How to Use

### 1. Run the Scraper (CLI)

To scrape and analyze videos from the command line:

```bash
# Search for "World Cup" videos uploaded in the last 6 hours (defaults)
python analyzer.py

# Search for "Futebol" videos uploaded in the last 12 hours, saving to a custom DB
python analyzer.py --query "Futebol" --hours 12 --db futebol_trends.db
```

This will:
1.  Search YouTube for matching videos.
2.  Fetch details (views, likes, comments) for those videos.
3.  Calculate scores and save them to a local SQLite database (`trends_br.db` by default).
4.  Fetch transcripts and comments for the top 20 videos.

### 2. Run the Dashboard (GUI)

Launch the Streamlit dashboard to visualize the results:

```bash
streamlit run app.py
```

The dashboard allows you to:
*   View top trending videos and channels.
*   See word clouds of comments.
*   Generate on-demand reports using Gemini.

### 3. Generate Reports manually

You can also run the individual analysis scripts:

```bash
# Generate a social listening report based on the database
python topic_analyzer.py

# Generate a 2-page advertiser deck for the last 24 hours of data
python generate_advertiser_deck.py
```

---
*Note: The user interface and default AI prompts are optimized for Portuguese (Brazil).*
