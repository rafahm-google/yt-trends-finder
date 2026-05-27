# YouTube Trends Finder

A Python-based tool to monitor, score, and analyze trending YouTube videos about specific topics. It calculates a real-time "views per minute" score to identify rapidly rising videos and uses the Gemini API to generate strategic social listening reports and advertiser decks.

## Features

*   **YouTube Scraper**: Fetches videos based on search queries or Topic IDs (Knowledge Graph) within a specific lookback window (e.g., last 6 hours).
*   **Composite Scoring**: Ranks videos based on a combination of views per minute, likes, and comment activity.
*   **Content Extraction**: Automatically fetches video comments and attempts to retrieve/generate transcripts.
*   **AI-Powered Insights (Gemini)**: Generates **Social Listening Reports** detailing top themes, audience sentiment, and key takeaways directly from the dashboard.
*   **Interactive Dashboard**: A Streamlit-based web application to visualize trends, explore video details, view word clouds, and interact with the data.

## Project Structure

```
yt-trends-finder/
├── analyzer.py                 # Scraper logic and CLI tool
├── app.py                      # Streamlit web dashboard (Main Entry Point)
├── generate_enhanced_report.py # Script to generate enhanced social listening reports
├── generate_html_deck.py       # Helper to generate HTML presentations
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



---
*Note: The user interface and default AI prompts are optimized for Portuguese (Brazil).*
