import os
import sqlite3
import csv
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google.auth
from dotenv import load_dotenv

load_dotenv()


def get_drive_service():
    credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/drive'])
    service = build('drive', 'v3', credentials=credentials)
    return service

def create_folder_in_drive(folder_name, parent_folder_id, resource_key=None):
    service = get_drive_service()
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder_id]
    }
    
    # Resource key handling if needed by API
    # Note: googleapiclient might handle this differently or require it in the execution
    
    try:
        # Simple create without resource key first, add support if needed
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')
    except Exception as e:
        print(f"An error occurred creating folder: {e}")
        return None

def upload_file_to_drive(file_path, folder_id, mime_type, resource_key=None):
    service = get_drive_service()
    
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [folder_id]
    }
    
    media = MediaFileUpload(file_path, mimetype=mime_type)
    
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"File ID: {file.get('id')} uploaded successfully.")
        return file.get('id')
    except Exception as e:
        print(f"An error occurred uploading file: {e}")
        return None

def export_db_to_csv(db_path, csv_path):
    """Exports the videos table to a CSV file."""
    print(f"Exporting database {db_path} to CSV {csv_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM videos")
    rows = cursor.fetchall()
    
    # Get column names
    column_names = [description[0] for description in cursor.description]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(column_names)
        writer.writerows(rows)
        
    conn.close()
    print("Database exported successfully.")

def main():
    parent_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not parent_folder_id or parent_folder_id == "YOUR_GOOGLE_DRIVE_FOLDER_ID":
        print("Error: GOOGLE_DRIVE_FOLDER_ID not set in .env file or is placeholder.")
        return
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    db_path = "trends_br.db"
    
    # 1. Create dated folder in Drive
    print(f"Creating folder '{today_str}' in Drive...")
    folder_id = create_folder_in_drive(today_str, parent_folder_id)
    
    if not folder_id:
        print("Failed to create folder in Drive. Aborting upload.")
        return
        
    # 2. Export DB to CSV
    csv_path = f"{today_str}-videos_data.csv"
    export_db_to_csv(db_path, csv_path)
    
    # 3. Upload files
    files_to_upload = [
        (f"{today_str}-enhanced_social_listening_report.md", "text/markdown"),
        (f"{today_str}-advertiser_deck_24h.md", "text/markdown"),
        (csv_path, "text/csv"),
        ("advertiser_pitch_deck.html", "text/html") # Add the new HTML presentation
    ]
    
    for file_path, mime_type in files_to_upload:
        if os.path.exists(file_path):
            upload_file_to_drive(file_path, folder_id, mime_type)
        else:
            print(f"Warning: File not found at {file_path}. Skipping upload.")

if __name__ == "__main__":
    main()
