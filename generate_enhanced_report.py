import os
import sqlite3
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from datetime import datetime

def format_date(iso_str):
    """Formats ISO date string to Brazilian format."""
    try:
        clean_str = iso_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(clean_str)
        return dt.strftime('%d/%m/%Y %H:%M')
    except Exception:
        return iso_str

def get_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Get top 20 videos with details from the latest scrape
    cursor.execute('''
        WITH LatestScrape AS (
            SELECT MAX(scrape_time) as max_time FROM videos
        )
        SELECT v.video_id, v.title, v.channel, v.published_at, v.composite_score, v.views, v.likes, v.comments as comment_count, c.transcript, c.comments as comment_text
        FROM videos v
        CROSS JOIN LatestScrape
        LEFT JOIN video_content c ON v.video_id = c.video_id
        WHERE v.scrape_time = LatestScrape.max_time
        ORDER BY v.composite_score DESC
        LIMIT 20
    ''')
    videos = cursor.fetchall()
    
    # 2. Get top 10 channels from the latest scrape
    cursor.execute('''
        WITH LatestScrape AS (
            SELECT MAX(scrape_time) as max_time FROM videos
        )
        SELECT channel, SUM(composite_score) as total_score, COUNT(video_id) as video_count
        FROM videos, LatestScrape
        WHERE scrape_time = max_time
        GROUP BY channel
        ORDER BY total_score DESC
        LIMIT 10
    ''')
    channels = cursor.fetchall()
    
    conn.close()
    return videos, channels

def get_report_content(videos, api_key=None):
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
    
    if not api_key:
        raise ValueError("API Key not found.")
        
    client = genai.Client(api_key=api_key)
    
    # Use gemini-3.5-flash for complex analysis
    model_name = "gemini-3.5-flash"
    
    # Prepare text for Gemini to analyze
    aggregated_text = []
    for i, (video_id, title, channel, pub_at, score, views, likes, comment_count, transcript, comments) in enumerate(videos, 1):
        text = f"Vídeo {i}: {title} (Canal: {channel})\n"
        if transcript:
            text += f"Transcrição: {transcript[:2000]}...\n" # Increased limit for more detail
        if comments:
            text += f"Comentários: {comments[:2000]}...\n" # Increased limit for more detail
        aggregated_text.append(text)
        
    prompt_text = "\n".join(aggregated_text)
    
    prompt = f"""
    Você é um estrategista de marketing e especialista em Social Listening no Brasil, analisando tendências do YouTube baseadas no tema dos vídeos fornecidos.
    Com base nos dados dos vídeos virais fornecidos abaixo (títulos, transcrições e comentários), gere um relatório estratégico **ALTAMENTE DETALHADO** em Português do Brasil.
    
    **REGRA DE OURO DE CONTEÚDO (MANDATÓRIA):**
    Você deve basear suas análises, temas, criadores e sugestões **ESTRITAMENTE E EXCLUSIVAMENTE** nos dados reais fornecidos abaixo. 
    - NÃO invente dados, estatísticas ou tendências que não estejam explicitamente mencionadas ou fortemente sugeridas pelos dados.
    - NÃO use clichês genéricos de marketing ou suposições infundadas.
    - Se os vídeos falarem sobre um técnico específico (ex: Abel Ferreira), foque nele e em seu contexto (Palmeiras, tática, coletivas, etc.). NÃO tente forçar o assunto para "Copa do Mundo" se esse não for o foco real dos vídeos.
    - Se o assunto for Copa do Mundo, foque em Copa do Mundo. Adapte-se ao tema real que emerge dos dados.
    
    O relatório será usado para gerar uma apresentação no NotebookLM, portanto, deve ser autoexplicativo e conter informações ricas e profundas.
    
    **DIRETRIZES DE SEGURANÇA DE MARCA E FILTRAGEM DE CONTEÚDO (BRAND SAFETY - MANDATÓRIO):**
    1. **Relevância ao Tema (Esporte/Futebol):** Utilize apenas vídeos, tópicos e insights que estejam relacionados ao futebol/esporte e aos personagens envolvidos nos dados.
    2. **Tópicos Proibidos:** Ignore completamente, descarte e NÃO inclua no relatório qualquer menção a:
       - Política, eleições, governos, políticos ou partidos.
       - Conteúdo sensual, nudez, pornografia, conotações sexuais ou conteúdo adulto.
       - Conteúdo envolvendo menores de idade de forma inadequada ou sensível.
       - Quaisquer polêmicas graves ou temas sensíveis não relacionados ao esporte.
    
    O relatório DEVE conter as seguintes seções:
    
    1. **Mapa de Criadores**: Identifique e mapeie os canais do YouTube REAIS que estão presentes nos dados fornecidos. Para cada canal, forneça uma análise detalhada do tipo de conteúdo que ele está produzindo, o tom da comunicação e por que ele está atraindo a audiência (gerando engajamento). Não invente novos criadores ou generalize perfis; baseie-se estritamente nos canais listados nos dados de suporte.
    2. **Mapa de Tópicos**: Mapeie os principais temas reais que estão em alta nos dados. Para cada tema, faça um "deep dive" detalhando os subtemas, o que especificamente as pessoas estão falando, as controvérsias e os sentimentos associados.
    3. **Oportunidades para Marcas (Hacks de Conteúdo)**: Proponha ideias de campanhas rápidas, ágeis e de fácil implementação ("hacks") para as marcas surfarem a onda dos temas reais que estão em alta. As propostas devem ser extremamente práticas, indicando exatamente qual marca ou categoria de produto se beneficiaria, qual criador específico envolver e a mecânica da ação. Foco em ações de baixo esforço, alta viralidade e conexão imediata com os tópicos do momento.
    4. **Storyboard da Campanha**: Crie um storyboard detalhado (passo a passo ou cena a cena) da campanha proposta na seção anterior, descrevendo o fluxo da ação, falas sugeridas para o criador e a interação com o público.
    
    Dados dos vídeos:
    {prompt_text}
    """
    
    print(f"Solicitando análise aprofundada ao Gemini ({model_name})...")
    ai_analysis = "Erro ao gerar análise via IA."
    success = False
    
    for attempt in range(3):
        try:
            print(f"Calling {model_name} (Attempt {attempt + 1})...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            ai_analysis = response.text
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
                ai_analysis = response.text
                success = True
                break
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    print(f"Model overloaded (503). Waiting 5 seconds to retry...")
                    time.sleep(5)
                else:
                    print(f"Erro ao chamar o Gemini: {e}")
                    break
 
    # Build the final markdown report
    report = []
    report.append("# Relatório Estratégico de Tendências - YouTube Brasil")
    report.append(f"**Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
    
    report.append(ai_analysis + "\n")
    
    report.append("## Apêndice: Dados de Suporte")
    report.append("### Ranking de Vídeos Analisados (Top 100)")
    report.append("| Pos | Título | Canal | Visualizações | Score |")
    report.append("| :--- | :--- | :--- | :--- | :--- |")
    for i, (video_id, title, channel, pub_at, score, views, *_) in enumerate(videos, 1):
        report.append(f"| {i} | {title} | {channel} | {views} | {score:.2f} |")
        
    return "\n".join(report)

def generate_enhanced_report():
    load_dotenv()
    
    db_path = "trends_br.db"
    videos, channels = get_data(db_path)
    
    if not videos:
        print("Nenhum dado encontrado no banco de dados.")
        return
        
    print(f"Dados carregados: {len(videos)} vídeos.")
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
    
    try:
        report_text = get_report_content(videos, api_key)
        report_path = "enhanced_social_listening_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"Relatório completo salvo em {report_path}")
    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")

if __name__ == "__main__":
    generate_enhanced_report()
