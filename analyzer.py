import os
import time
import sqlite3
import argparse
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from tqdm import tqdm

def setup_database(db_path):
    """Creates a SQLite database and the necessary tables if they don't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            title TEXT,
            channel TEXT,
            published_at TEXT,
            views INTEGER,
            likes INTEGER,
            comments INTEGER,
            scrape_time TEXT,
            minutes_since_upload REAL,
            views_per_minute REAL,
            composite_score REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_content (
            video_id TEXT PRIMARY KEY,
            transcript TEXT,
            comments TEXT,
            FOREIGN KEY(video_id) REFERENCES videos(video_id)
        )
    ''')
    conn.commit()
    return conn

def get_youtube_client():
    """Initializes the YouTube API client."""
    load_dotenv()
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY not found in .env file.")
    return build("youtube", "v3", developerKey=api_key)

def search_videos(youtube, query, published_after, region_code=None, relevance_language=None, topic_id=None):
    """Searches for videos uploaded after a specific time."""
    print(f"Searching for videos with query: '{query}', topic: '{topic_id}' after {published_after}")
    video_ids = []
    next_page_token = None
    
    # Fetch up to 2 pages of results (max 100 videos)
    for _ in range(2):
        try:
            params = {
                "part": "id",
                "type": "video",
                "order": "date",
                "maxResults": 50,
                "publishedAfter": published_after,
                "pageToken": next_page_token
            }
            if query:
                params["q"] = query
            if topic_id:
                params["topicId"] = topic_id
            if region_code:
                params["regionCode"] = region_code
            if relevance_language:
                params["relevanceLanguage"] = relevance_language
                
            search_response = youtube.search().list(**params).execute()
            
            for item in search_response.get("items", []):
                video_ids.append(item["id"]["videoId"])
                
            next_page_token = search_response.get('nextPageToken')
            if not next_page_token:
                break
        except HttpError as e:
            print(f"HTTP error during search: {e}")
            if e.resp.status in [403, 429]:
                print("Likely quota exceeded or rate limit. Stopping search.")
                break
            break
        except Exception as e:
            print(f"Error during search: {e}")
            break
            
    return video_ids

def get_video_details(youtube, video_ids):
    """Fetches statistics for a list of video IDs."""
    details = []
    for i in tqdm(range(0, len(video_ids), 50), desc="Fetching Video Details"):
        batch_ids = video_ids[i:i+50]
        try:
            response = youtube.videos().list(
                part="snippet,statistics",
                id=",".join(batch_ids)
            ).execute()
            details.extend(response.get("items", []))
        except HttpError as e:
            print(f"HTTP error fetching details: {e}")
            if e.resp.status in [403, 429]:
                print("Likely quota exceeded or rate limit. Stopping details fetch.")
                break
            break
        except Exception as e:
            print(f"Error fetching details for batch: {e}")
    return details

def is_video_related_to_football(snippet):
    title = snippet.get("title", "").lower()
    channel = snippet.get("channelTitle", "").lower()
    cat_id = str(snippet.get("categoryId", ""))
    
    if channel in ["ate glo", "impredecible", "coração sertanejo"]:
        return False
        
    unwanted_terms = [
        "gospel", "pastor ", "louvor", "culto", "pregacao", "pregação", "sertanejo", 
        "video oficial", "vídeo oficial", "clipe oficial", "ao vivo em", "dvd ao vivo",
        "novela", "bastos na lalake", "miguelito pierde"
    ]
    for term in unwanted_terms:
        if term in title or term in channel:
            return False
            
    # Filter out videos with "ao vivo" or "jogo completo" in the title as requested by user
    unwanted_title_terms = ["ao vivo", "jogo completo"]
    for term in unwanted_title_terms:
        if term in title:
            return False
            
    if cat_id in ["10", "29"]:
        football_terms = ["futebol", "copa", "seleção", "selecao", "fifa", "gol", "gols", "cbf", "jogador", "neymar", "vinicius", "mbappe", "messi"]
        if not any(ft in title for ft in football_terms):
            return False
            
    return True

def process_and_save_videos(conn, video_details, current_time_utc):
    """Processes video data, calculates scores, and saves to database."""
    cursor = conn.cursor()
    scrape_time = current_time_utc.isoformat()
    
    for video in video_details:
        video_id = video["id"]
        snippet = video["snippet"]
        stats = video.get("statistics", {})
        
        if not is_video_related_to_football(snippet):
            continue
            
        title = snippet["title"]
        channel = snippet["channelTitle"]
        published_at_str = snippet["publishedAt"]
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        
        # Calculate minutes since upload
        published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
        time_diff = current_time_utc - published_at
        minutes_since_upload = time_diff.total_seconds() / 60.0
        
        # Avoid division by zero
        if minutes_since_upload <= 0:
            minutes_since_upload = 1.0
            
        views_per_minute = views / minutes_since_upload
        
        # Composite score: Views + Likes*10 + Comments*20 per minute
        composite_score = (views + likes * 10 + comments * 20) / minutes_since_upload
        
        # Insert or replace in database
        cursor.execute('''
            INSERT OR REPLACE INTO videos 
            (video_id, title, channel, published_at, views, likes, comments, scrape_time, minutes_since_upload, views_per_minute, composite_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (video_id, title, channel, published_at_str, views, likes, comments, scrape_time, minutes_since_upload, views_per_minute, composite_score))
        
    conn.commit()

def print_top_videos(conn):
    """Prints the top videos in age categories ranked by composite score, normalized 0-10."""
    cursor = conn.cursor()
    
    # Get the maximum composite score in the database for normalization
    cursor.execute('SELECT MAX(composite_score) FROM videos')
    max_score = cursor.fetchone()[0]
    
    if not max_score:
        max_score = 1.0 # Avoid division by zero if empty
        
    # Use a window function to get the top 5 videos per age category
    cursor.execute('''
        WITH LatestScrape AS (
            SELECT MAX(scrape_time) as max_time FROM videos
        ),
        CategorizedVideos AS (
            SELECT title, views, likes, comments, composite_score, channel,
                   CASE 
                       WHEN minutes_since_upload <= 60 THEN 'Fresh (0-1h)'
                       WHEN minutes_since_upload <= 720 THEN 'Rising (1-12h)'
                       ELSE 'Established (12-24h)'
                   END as age_category,
                   ROW_NUMBER() OVER(
                       PARTITION BY CASE 
                           WHEN minutes_since_upload <= 60 THEN 'Fresh (0-1h)'
                           WHEN minutes_since_upload <= 720 THEN 'Rising (1-12h)'
                           ELSE 'Established (12-24h)'
                       END 
                       ORDER BY composite_score DESC
                   ) as rn
            FROM videos, LatestScrape
            WHERE scrape_time = max_time
        )
        SELECT title, views, likes, comments, composite_score, channel, age_category
        FROM CategorizedVideos 
        WHERE rn <= 5 
        ORDER BY 
            CASE age_category
                WHEN 'Fresh (0-1h)' THEN 1
                WHEN 'Rising (1-12h)' THEN 2
                ELSE 3
            END ASC,
            composite_score DESC
    ''')
    
    rows = cursor.fetchall()
    print("\n--- Top Trending Videos by Category (Score Normalized 0-10) ---")
    current_category = None
    for row in rows:
        title, views, likes, comments, score, channel, category = row
        
        if category != current_category:
            print(f"\n=== Category: {category} ===")
            current_category = category
            
        # Normalize score to 0-10 range
        normalized_score = (score / max_score) * 10.0
        print(f"🏆 {title}")
        print(f"   Channel: {channel}")
        print(f"   Stats: Views: {views} | Likes: {likes} | Comments: {comments}")
        print(f"   Score: {normalized_score:.2f}/10 (Composite: {score:.2f})")
        print("-" * 50)

def print_top_channels(conn):
    """Prints the top channels ranked by total composite score."""
    cursor = conn.cursor()
    
    cursor.execute('''
        WITH LatestScrape AS (
            SELECT MAX(scrape_time) as max_time FROM videos
        )
        SELECT channel, 
               SUM(composite_score) as total_score, 
               COUNT(*) as video_count,
               SUM(views) as total_views
        FROM videos, LatestScrape
        WHERE scrape_time = max_time
        GROUP BY channel
        ORDER BY total_score DESC
        LIMIT 10
    ''')
    
    rows = cursor.fetchall()
    print("\n--- Top Channels by Total Composite Score ---")
    for i, row in enumerate(rows, 1):
        channel, total_score, video_count, total_views = row
        print(f"{i}. Channel: {channel}")
        print(f"   Stats: Videos: {video_count} | Total Views: {total_views}")
        print(f"   Total Score: {total_score:.2f}")
        print("-" * 30)

def fetch_comments(youtube, video_id):
    """Fetches top comments for a given video ID."""
    comments = []
    try:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=30,
            order="relevance"
        ).execute()
        
        for item in response.get('items', []):
            comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
            comments.append(comment)
    except HttpError as e:
        print(f"Error fetching comments for {video_id}: {e}")
        if e.resp.status in [403, 429]:
            print("Quota exceeded or access denied for comments.")
            
    return "\n".join(comments)

def fetch_transcript(video_id):
    """Fetches transcript for a given video ID using fallback to Gemini if needed."""
    from google import genai
    from google.genai import types
    import os
    from youtube_transcript_api import YouTubeTranscriptApi
    
    print(f"Attempting to fetch transcript via youtube-transcript-api for {video_id}...")
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript(['pt', 'pt-BR'])
        except Exception:
            transcript = transcript_list.find_transcript(['en'])
            
        lines = transcript.fetch()
        text_lines = []
        for line in lines:
            if isinstance(line, dict):
                text_lines.append(line.get('text', ''))
            else:
                text_lines.append(getattr(line, 'text', str(line)))
        return "\n".join(text_lines)
    except Exception as e:
        print(f"youtube-transcript-api failed for {video_id}: {e}")
        print("Falling back to Gemini...")
        
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
        if api_key and "GEMINI_API_KEY" not in os.environ:
            os.environ["GEMINI_API_KEY"] = api_key

        try:
            client = genai.Client()
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            print(f"Attempting to extract content via Gemini for {video_id}...")
            
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=types.Content(
                    parts=[
                        types.Part(file_data=types.FileData(file_uri=video_url)),
                        types.Part(text='Analyze only the first 40 minutes of this video. Extract the transcript or a detailed summary of the main topics, headlines, and context discussed during these first 40 minutes in Portuguese (or English if Portuguese is not available). Return only the extracted text.')
                    ]
                )
            )
            return response.text
        except Exception as gemini_e:
            print(f"Gemini fallback also failed for {video_id}: {gemini_e}")
            return ""


def save_video_content(conn, video_id, transcript, comments):
    """Saves transcript and comments to the video_content table."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO video_content (video_id, transcript, comments)
        VALUES (?, ?, ?)
    ''', (video_id, transcript, comments))
    conn.commit()

def main():
    parser = argparse.ArgumentParser(description="YouTube Trends Finder")
    parser.add_argument("--query", type=str, default="World Cup", help="Search query for videos")
    parser.add_argument("--hours", type=int, default=6, help="Lookback period in hours")
    parser.add_argument("--db", type=str, default="trends_br.db", help="Database path")
    parser.add_argument("--topic", type=str, default=None, help="Knowledge Graph ID (Topic ID) to search for")
    args = parser.parse_args()

    db_path = args.db
    lookback_hours = args.hours
    search_query = args.query
    
    current_time_utc = datetime.now(timezone.utc)
    # Calculate the time X hours ago
    time_ago = current_time_utc - timedelta(hours=lookback_hours)
    # Format for YouTube API (RFC 3339)
    published_after = time_ago.isoformat().replace('+00:00', 'Z')
    
    conn = setup_database(db_path)
    
    try:
        youtube = get_youtube_client()
        
        video_ids = search_videos(youtube, search_query, published_after, topic_id=args.topic)
        print(f"Found {len(video_ids)} videos uploaded in the last {lookback_hours} hours.")
        
        if video_ids:
            video_details = get_video_details(youtube, video_ids)
            process_and_save_videos(conn, video_details, current_time_utc)
            print_top_videos(conn)
            print_top_channels(conn)
            
            # Fetch content for top 20 videos
            print("\nFetching comments and transcripts for top 20 videos...")
            cursor = conn.cursor()
            cursor.execute('''
                SELECT video_id, title FROM videos 
                ORDER BY composite_score DESC 
                LIMIT 20
            ''')
            top_videos = cursor.fetchall()
            
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def process_video_content(video_id, title, youtube_client, path_to_db):
                try:
                    t_conn = sqlite3.connect(path_to_db)
                    
                    # Check if already processed to save time/quota
                    t_cursor = t_conn.cursor()
                    t_cursor.execute('SELECT 1 FROM video_content WHERE video_id = ?', (video_id,))
                    if t_cursor.fetchone():
                        t_conn.close()
                        return f"Skipped {video_id} (already processed)"
                        
                    comments = fetch_comments(youtube_client, video_id)
                    transcript = fetch_transcript(video_id)
                    save_video_content(t_conn, video_id, transcript, comments)
                    t_conn.close()
                    return f"Processed {video_id}"
                except Exception as e:
                    return f"Error processing {video_id}: {e}"

            db_path = args.db
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(process_video_content, video_id, title, youtube, db_path) for video_id, title in top_videos]
                for future in as_completed(futures):
                    print(future.result())
        else:
            print("No videos found in the specified time frame.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
