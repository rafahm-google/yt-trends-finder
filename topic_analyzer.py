import os
import sqlite3
from dotenv import load_dotenv
from google import genai
from google.genai import types

def get_top_videos_content(db_path, limit=100):
    """Fetches title, transcript, and comments for top videos."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT v.video_id, v.title, c.transcript, c.comments
        FROM videos v
        JOIN video_content c ON v.video_id = c.video_id
        ORDER BY v.composite_score DESC
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return rows

def analyze_topics():
    load_dotenv()
    
    # The rule says to use gemini-2.5-pro unless specified. The user specified gemini-3.5-flash.
    model_name = "gemini-3.5-flash"
    
    # We assume GEMINI_API_KEY is set in .env or environment.
    # If not, we fall back to reading YOUTUBE_API_KEY if it happens to be the same.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
    
    if not api_key:
        print("Warning: GEMINI_API_KEY not found. Trying default credentials.")
        client = genai.Client()
    else:
        client = genai.Client(api_key=api_key)
        
    db_path = "trends_br.db"
    print(f"Reading data from {db_path}...")
    videos_data = get_top_videos_content(db_path, limit=100)
    
    if not videos_data:
        print("No content found in database to analyze.")
        return
        
    print(f"Loaded content for {len(videos_data)} videos.")
    
    # Prepare the content for the prompt
    aggregated_content = []
    for i, (video_id, title, transcript, comments) in enumerate(videos_data, 1):
        video_text = f"--- Video {i}: {title} (ID: {video_id}) ---\n"
        if transcript:
            video_text += f"Transcript: {transcript}\n"
        else:
            video_text += "Transcript: Not available.\n"
            
        if comments:
            video_text += f"Top Comments:\n{comments}\n"
        else:
            video_text += "Comments: Not available.\n"
            
        aggregated_content.append(video_text)
        
    full_text = "\n".join(aggregated_content)
    
    prompt = f"""
    You are a social listening expert analyzing YouTube trends in Brazil.
    I am providing you with transcripts and top comments for the top {len(videos_data)} viral videos about 'Copa do Mundo' or related topics.
    
    Please perform a thorough analysis and provide:
    1. The top 5 trending themes or topics discussed across these videos.
    2. The general sentiment of the audience in the comments.
    3. Key takeaways or surprising findings.
    4. Recommendations for content creators based on what is trending.
    
    Here is the data:
    {full_text}
    """
    
    print(f"Sending request to Gemini ({model_name})...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        report_text = response.text
        print("\n=== Social Listening Report ===")
        print(report_text)
        print("===============================")
        
        # Save to markdown file
        report_path = "social_listening_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"Report saved to {report_path}")
        
    except Exception as e:
        print(f"Failed to call Gemini: {e}")

if __name__ == "__main__":
    analyze_topics()
