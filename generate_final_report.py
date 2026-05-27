import os
import sqlite3
from dotenv import load_dotenv
from google import genai
from google.genai import types
from datetime import datetime

def format_date(iso_str):
    """Formats ISO date string to Brazilian format."""
    try:
        # Handle Z at the end
        clean_str = iso_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(clean_str)
        return dt.strftime('%d/%m/%Y %H:%M')
    except Exception:
        return iso_str

def get_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Get top 100 videos with details
    cursor.execute('''
        SELECT v.video_id, v.title, v.channel, v.published_at, v.composite_score, v.views, v.likes, v.comments as comment_count, c.transcript, c.comments as comment_text
        FROM videos v
        LEFT JOIN video_content c ON v.video_id = c.video_id
        ORDER BY v.composite_score DESC
        LIMIT 100
    ''')
    videos = cursor.fetchall()
    
    # 2. Get top 10 channels
    cursor.execute('''
        SELECT channel, SUM(composite_score) as total_score, COUNT(video_id) as video_count
        FROM videos
        GROUP BY channel
        ORDER BY total_score DESC
        LIMIT 10
    ''')
    channels = cursor.fetchall()
    
    conn.close()
    return videos, channels

def generate_report():
    load_dotenv()
    
    # Use gemini-3.5-flash as requested by user
    model_name = "gemini-3.5-flash"
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    db_path = "trends_br.db"
    videos, channels = get_data(db_path)
    
    if not videos:
        print("Nenhum dado encontrado no banco de dados.")
        return
        
    print(f"Dados carregados: {len(videos)} vídeos.")
    
    # Prepare text for Gemini to analyze themes
    # We truncate to keep the prompt size reasonable but still rich
    aggregated_text = []
    for i, (video_id, title, channel, pub_at, score, views, likes, comment_count, transcript, comments) in enumerate(videos, 1):
        text = f"Vídeo {i}: {title} (Canal: {channel})\n"
        if transcript:
            text += f"Transcrição: {transcript[:1000]}...\n"
        if comments:
            text += f"Comentários: {comments[:1000]}...\n"
        aggregated_text.append(text)
        
    prompt_text = "\n".join(aggregated_text)
    
    prompt = f"""
    Você é um especialista em Social Listening no Brasil.
    Analise o seguinte conteúdo de vídeos do YouTube sobre a Copa do Mundo e extraia os principais temas discutidos.
    Por favor, responda em Português do Brasil.
    
    Estruture sua resposta com:
    1. Principais Temas (extraia os 5 temas mais recorrentes).
    2. Sentimento Geral da Audiência.
    3. Insights Relevantes e Recomendações.
    
    Dados dos vídeos:
    {prompt_text}
    """
    
    print(f"Solicitando análise ao Gemini ({model_name})...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        ai_analysis = response.text
    except Exception as e:
        print(f"Erro ao chamar o Gemini: {e}")
        ai_analysis = "Erro ao gerar análise de temas via IA."
        
    # Build the final markdown report
    report = []
    report.append("# Relatório de Social Listening - YouTube Brasil")
    report.append(f"**Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
    
    report.append("## 1. Análise de Temas e Sentimento (IA)")
    report.append(ai_analysis + "\n")
    
    report.append("## 2. Ranking de Vídeos Analisados (Top 100 Viral)")
    report.append("| Pos | Título | Canal | Data/Hora de Publicação | Visualizações | Curtidas | Comentários | Score |")
    report.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for i, (video_id, title, channel, pub_at, score, views, likes, comment_count, *_) in enumerate(videos, 1):
        formatted_date = format_date(pub_at)
        report.append(f"| {i} | {title} | {channel} | {formatted_date} | {views} | {likes} | {comment_count} | {score:.2f} |")
        
    report.append("\n## 3. Ranking de Criadores/Canais (Top 10)")
    report.append("| Pos | Canal | Score Total | Qtd Vídeos |")
    report.append("| :--- | :--- | :--- | :--- |")
    for i, (channel, total_score, video_count) in enumerate(channels, 1):
        report.append(f"| {i} | {channel} | {total_score:.2f} | {video_count} |")
        
    report_text = "\n".join(report)
    
    report_path = "relatorio_social_listening_completo.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
        
    print(f"Relatório completo salvo em {report_path}")

if __name__ == "__main__":
    generate_report()
