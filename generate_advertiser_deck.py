import os
import sqlite3
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from datetime import datetime, timedelta, timezone

def get_data_last_24h(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    current_time_utc = datetime.now(timezone.utc)
    time_24h_ago = current_time_utc - timedelta(hours=24)
    iso_24h_ago = time_24h_ago.isoformat().replace('+00:00', 'Z')
    
    print(f"Buscando vídeos publicados após: {iso_24h_ago}")
    
    # Query videos published in the last 24 hours
    cursor.execute('''
        SELECT v.video_id, v.title, v.channel, v.published_at, v.composite_score, v.views, c.transcript, c.comments
        FROM videos v
        LEFT JOIN video_content c ON v.video_id = c.video_id
        WHERE v.published_at >= ?
        ORDER BY v.composite_score DESC
    ''', (iso_24h_ago,))
    
    videos = cursor.fetchall()
    conn.close()
    return videos

def generate_advertiser_deck():
    load_dotenv()
    
    # Use gemini-3.5-flash for summary
    model_name = "gemini-3.5-flash"
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    db_path = "trends_br.db"
    videos = get_data_last_24h(db_path)
    
    if not videos:
        print("Nenhum vídeo encontrado nas últimas 24 horas.")
        return
        
    print(f"Dados carregados: {len(videos)} vídeos das últimas 24 horas.")
    
    # Prepare text for Gemini
    aggregated_text = []
    for i, (video_id, title, channel, pub_at, score, views, transcript, comments) in enumerate(videos[:50], 1): # Limit to top 50 for prompt size
        text = f"Vídeo {i}: {title} (Canal: {channel}, Views: {views})\n"
        if transcript:
            text += f"Resumo: {transcript[:300]}...\n"
        if comments:
            text += f"Comentários: {comments[:300]}...\n"
        aggregated_text.append(text)
        
    prompt_text = "\n".join(aggregated_text)
    
    prompt = f"""
    Você é um analista de tendências e está criando um deck de 2 páginas (resumo executivo) para múltiplos anunciantes.
    O objetivo é responder à pergunta: **O que está bombando no YouTube nas últimas 24 horas?**
    
    Com base nos dados fornecidos abaixo sobre os vídeos mais virais das últimas 24 horas, gere o conteúdo para esse deck de 2 páginas em Português do Brasil.
    
    O deck deve conter:
    1. **Hottest Topics**: Quais são os assuntos mais quentes do momento.
    2. **Quem está brilhando**: Mapeamento dos jogadores, times, celebridades ou personalidades que estão sendo mais falados.
    3. **Criadores em Destaque**: Uma visão detalhada de quem são os criadores do YouTube que estão bombando nas últimas 24 horas.
    
    Seja extremamente direto, visual (descreva como os dados devem ser apresentados, ex: em tópicos, tabelas mentais) e focado em insights rápidos para anunciantes.
    
    Dados dos vídeos (Top 50):
    {prompt_text}
    """
    
    print(f"Solicitando geração do deck de 2 páginas ao Gemini ({model_name})...")
    ai_output = "Erro ao gerar o deck via IA."
    
    success = False
    for attempt in range(3):
        try:
            print(f"Calling {model_name} (Attempt {attempt + 1})...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            ai_output = response.text
            success = True
            break
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"Model overloaded (503). Waiting 5 seconds to retry...")
                time.sleep(5)
            else:
                print(f"Erro ao chamar o Gemini: {e}")
                break
                
    if not success:
        print("Model failed or overloaded. Falling back to gemini-3.1-pro-preview...")
        model_name = "gemini-3.1-pro-preview"
        for attempt in range(3):
            try:
                print(f"Calling {model_name} (Attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                ai_output = response.text
                success = True
                break
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    print(f"Model overloaded (503). Waiting 5 seconds to retry...")
                    time.sleep(5)
                else:
                    print(f"Erro ao chamar o Gemini: {e}")
                    break
                
    report_path = "advertiser_deck_24h.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(ai_output)
        
    print(f"Deck de 2 páginas salvo em {report_path}")

if __name__ == "__main__":
    generate_advertiser_deck()
