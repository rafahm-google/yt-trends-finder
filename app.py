import streamlit as st
import os
import pandas as pd
from datetime import datetime, timedelta, timezone
from google import genai
from dotenv import load_dotenv
import json
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import altair as alt
import numpy as np
import sys
import requests
import google.auth
from google.auth.transport.requests import Request

# Import logic from existing scripts
from analyzer import get_youtube_client, search_videos, get_video_details, fetch_transcript, fetch_comments, is_video_related_to_football
from generate_enhanced_report import get_report_content, format_date
from generate_html_deck import get_html_deck_content

# Cached wrappers to reduce YouTube API quota consumption
@st.cache_data(ttl=900) # Cache search results for 15 minutes
def cached_search_videos(query, published_after, region_code=None, relevance_language=None):
    try:
        youtube = get_youtube_client()
        return search_videos(youtube, query, published_after, region_code=region_code, relevance_language=relevance_language)
    except Exception as e:
        st.error(f"Erro ao buscar vídeos: {e}")
        return []

@st.cache_data(ttl=900) # Cache details for 15 minutes
def cached_get_video_details(video_ids):
    if not video_ids:
        return []
    try:
        youtube = get_youtube_client()
        return get_video_details(youtube, video_ids)
    except Exception as e:
        st.error(f"Erro ao buscar detalhes dos vídeos: {e}")
        return []

@st.cache_data(ttl=3600) # Cache comments for 1 hour
def cached_fetch_comments(video_id):
    try:
        youtube = get_youtube_client()
        return fetch_comments(youtube, video_id)
    except Exception as e:
        print(f"Erro ao buscar comentários para {video_id}: {e}")
        return ""

@st.cache_data(ttl=86400) # Cache transcripts for 24 hours
def cached_fetch_transcript(video_id):
    try:
        return fetch_transcript(video_id)
    except Exception as e:
        print(f"Erro ao buscar transcrição para {video_id}: {e}")
        return ""

def upload_to_notebooklm(notebook_id, source_name, content):
    """Uploads a text source to NotebookLM using inferred REST API."""
    try:
        # Get default credentials and token
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        credentials.refresh(Request())
        token = credentials.token
        
        url = f"https://notebooklm.googleapis.com/v1/notebooks/{notebook_id}/sources"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "source": {
                "displayName": source_name,
                "textContent": {
                    "content": content,
                    "contentType": "TEXT_CONTENT_TYPE_MARKDOWN"
                }
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"ERROR uploading to NotebookLM: {e}")
        return None
# Custom CSS for premium look
st.set_page_config(page_title="YouTube Trends Finder", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #45a049;
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
        transform: translateY(-2px);
    }
    .title {
        color: #1a73e8;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: bold;
    }
    .card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 class='title'>📊 YouTube Trends Finder</h1>", unsafe_allow_html=True)
st.write("Monitore vídeos virais no Brasil e analise sentimentos e temas com IA.")

load_dotenv()

# Initialize session state
if 'videos_data' not in st.session_state:
    st.session_state.videos_data = []
if 'enhanced_report' not in st.session_state:
    st.session_state.enhanced_report = None
if 'html_deck' not in st.session_state:
    st.session_state.html_deck = None
if 'analysis_data' not in st.session_state:
    st.session_state.analysis_data = None
if 'aggregated_text' not in st.session_state:
    st.session_state.aggregated_text = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Sidebar for inputs
st.sidebar.header("Configurações de Busca")
search_terms = st.sidebar.text_input("Termos de Busca (separe por vírgula)", "Copa do Mundo")

# CSV File Uploader
uploaded_file = st.sidebar.file_uploader("Ou carregue um arquivo CSV/TXT de termos", type=['csv', 'txt'])
st.sidebar.info("ℹ️ Formato do arquivo: Um termo por linha, sem cabeçalho.")

lookback_hours = st.sidebar.slider("Período de busca (horas atrás)", 1, 48, 6)
country_code = st.sidebar.text_input("Código do País (Ex: BR, US) [Opcional]", "")
language_code = st.sidebar.text_input("Código do Idioma (Ex: pt, en) [Opcional]", "")

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("🚀 Social Listening Completo (End-to-End)")
st.write("Busca vídeos, extrai conteúdos, gera relatórios visuais e chat interativo em uma única execução.")

# Max videos to analyze
max_videos_analyze = st.sidebar.slider("Quantidade de vídeos para análise aprofundada", 1, 50, 20)

if st.button("Executar Social Listening"):
    # Clear previous run data to avoid showing stale results if this run fails
    st.session_state.videos_data = []
    st.session_state.enhanced_report = None
    st.session_state.html_deck = None
    st.session_state.analysis_data = None
    st.session_state.aggregated_text = None
    st.session_state.chat_history = []
    
    with st.spinner("Executando pipeline completo..."):
        try:
            # Round current time to nearest 15 minutes to increase cache hits
            current_time_utc = datetime.now(timezone.utc)
            rounded_now = current_time_utc - timedelta(minutes=current_time_utc.minute % 15, seconds=current_time_utc.second, microseconds=current_time_utc.microsecond)
            time_ago = rounded_now - timedelta(hours=lookback_hours)
            published_after = time_ago.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Determine terms list
            if uploaded_file is not None:
                content = uploaded_file.read().decode("utf-8")
                terms_list = [line.strip() for line in content.splitlines() if line.strip()]
                st.write(f"Carregados {len(terms_list)} termos do arquivo.")
            else:
                terms_list = [term.strip() for term in search_terms.split(',')]
                
            all_videos = []
            
            for term in terms_list:
                if term:
                    st.write(f"Buscando por: **{term}**")
                else:
                    continue
                try:
                    video_ids = cached_search_videos(
                        term, 
                        published_after, 
                        region_code=country_code if country_code else None,
                        relevance_language=language_code if language_code else None
                    )
                except Exception as e:
                    st.warning(f"Erro ao buscar vídeos para o termo '{term}': {e}")
                    continue
                
                if video_ids:
                    st.write(f"✅ Encontrados {len(video_ids)} vídeos para '{term}'.")
                    try:
                        video_details = cached_get_video_details(video_ids)
                    except Exception as e:
                        st.warning(f"Erro ao buscar detalhes dos vídeos para o termo '{term}': {e}")
                        continue
                    
                    for item in video_details:
                        video_id = item["id"]
                        snippet = item["snippet"]
                        
                        if not is_video_related_to_football(snippet):
                            continue
                            
                        stats = item["statistics"]
                        
                        title = snippet["title"]
                        channel = snippet["channelTitle"]
                        published_at_str = snippet["publishedAt"]
                        
                        views = int(stats.get("viewCount", 0))
                        likes = int(stats.get("likeCount", 0))
                        comments = int(stats.get("commentCount", 0))
                        
                        published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                        time_diff = current_time_utc - published_at
                        minutes_since_upload = time_diff.total_seconds() / 60.0
                        
                        if minutes_since_upload <= 0:
                            minutes_since_upload = 1.0
                            
                        composite_score = (views + likes * 10 + comments * 20) / minutes_since_upload
                        
                        all_videos.append({
                            "ID": video_id,
                            "Título": title,
                            "Canal": channel,
                            "ChannelID": snippet["channelId"],
                            "Publicado Em": published_at_str,
                            "Visualizações": views,
                            "Curtidas": likes,
                            "Comentários": comments,
                            "Score": composite_score
                        })
                        
            # Deduplicate and sort
            df_temp = pd.DataFrame(all_videos)
            if not df_temp.empty:
                df_temp = df_temp.drop_duplicates(subset=['ID'])
                df_temp = df_temp.sort_values(by='Score', ascending=False)
                st.session_state.videos_data = df_temp.to_dict('records')
            else:
                st.session_state.videos_data = []
                
            if not st.session_state.videos_data:
                st.warning("Nenhum vídeo encontrado nas buscas.")
            else:
                # Now run the Map-Reduce Analysis on Top X videos
                top_videos = st.session_state.videos_data[:max_videos_analyze]
                st.write(f"Iniciando análise aprofundada de {len(top_videos)} vídeos...")
                
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
                genai_client = genai.Client(api_key=api_key)
                
                def process_video(video, g_client):
                    video_id = video["ID"]
                    title = video["Título"]
                    transcript = cached_fetch_transcript(video_id)
                    comments = cached_fetch_comments(video_id)
                    
                    if not transcript and not comments:
                        return None
                        
                    # Store in video dict for later use in enhanced report
                    video["transcript"] = transcript
                    video["comments_text"] = comments
                    
                    map_prompt = f"""
                    Resuma a discussão deste vídeo do YouTube (transcrição e comentários) em no máximo 5 frases.
                    Foque nos temas principais abordados e na reação da audiência.
                    Responda em Português do Brasil.
    
                    Título: {title}
                    Transcrição: {transcript[:2000] if transcript else 'N/A'}...
                    Comentários: {comments[:2000] if comments else 'N/A'}...
                    """
                    try:
                        response = g_client.models.generate_content(
                            model="gemini-3.5-flash",
                            contents=map_prompt,
                        )
                        return f"Vídeo: {title}\nResumo: {response.text}\n"
                    except:
                        return None

                summaries = []
                progress_bar = st.progress(0)
                
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(process_video, v, genai_client) for v in top_videos]

                    for i, future in enumerate(as_completed(futures)):
                        res = future.result()
                        if res:
                            summaries.append(res)
                        progress_bar.progress((i + 1) / len(top_videos))
                        
                if not summaries:
                    st.warning("Não foi possível extrair conteúdo para análise profunda.")
                    st.session_state.analysis_data = None
                else:
                    prompt_text = "\n".join(summaries)
                    
                    reduce_prompt = f"""
                    Você é um estrategista de conteúdo e especialista em Social Listening no Brasil analisando tendências da Copa do Mundo.
                    Analise os seguintes resumos de vídeos e extraia os temas unificados e informações sobre os criadores.
                    Você DEVE focar em identificar e mapear temas relacionados a:
                    1. **Seleções Nacionais** (favoritismo, rivalidades, debates sobre convocação).
                    2. **Jogadores de Futebol** (estrelas, revelações, lesões, expectativas).
                    3. **Memes e Humor** (piadas virais, reações engraçadas da torcida).
                    4. **Tendências e Comportamento** (estilo de vida, produtos temáticos, hábitos).
                    Além disso, gere um relatório estratégico detalhado focado em oportunidades para patrocinadores e marcas da Copa do Mundo.
                    Responda em Português do Brasil.
                    
                    Você DEVE retornar a resposta EXATAMENTE no seguinte formato JSON. Para cada tema, estime a frequência (quantos dos resumos de vídeo abordavam este tema) e retorne no campo 'frequencia' como um número inteiro.
                    Identifique também os top 5 canais (criadores) mais relevantes e preencha a seção "criadores" com detalhes sobre o que falam e tipos de vídeo.
                    **ATENÇÃO**: Use exatamente o nome do canal conforme aparece nos dados fornecidos para que o mapeamento funcione.
                    
                    {{
                      "temas": [
                        {{
                          "nome": "Nome do Tema 1",
                          "descricao": "Resumo do tema",
                          "frequencia": 5,
                          "palavras_chave": [
                            {{"palavra": "palavra1", "relevancia": 0.9}},
                            {{"palavra": "palavra2", "relevancia": 0.7}}
                          ]
                        }}
                      ],
                      "sentimento_geral": "Positivo/Neutro/Negativo",
                      "recomendacoes": ["Recomendação 1", "Recomendação 2"],
                      "relatorio_estrategista": "Texto estruturado em Markdown contendo obrigatoriamente: 1. **Deep Dive do Tópico**, 2. **Temas Emergentes**, 3. **Ações para Marcas**, 4. **Ações para Criadores**.",
                      "criadores": [
                        {{
                          "canal": "Nome do Canal Exato",
                          "perfil": "O que normalmente fala e estilo",
                          "topicos": ["Tópico 1", "Tópico 2"],
                          "tipos_video": ["Vlogs", "Shorts", "Podcast", "Transmissão ao vivo", "etc."]
                        }}
                      ]
                    }}
                    
                    Dados:
                    {prompt_text}
                    """
                    
                    st.write("Gerando dashboard final...")
                    response = genai_client.models.generate_content(
                        model="gemini-3.5-flash",
                        contents=reduce_prompt,
                        config=dict(response_mime_type="application/json")
                    )
                    
                    try:
                        response_text = response.text.strip()
                        # Remove markdown code block markers if present
                        if response_text.startswith("```json"):
                            response_text = response_text[7:]
                        if response_text.endswith("```"):
                            response_text = response_text[:-3]
                        response_text = response_text.strip()
                        
                        data = json.loads(response_text)
                        
                        # Generate word cloud frequencies locally to save tokens and improve quality
                        pt_stopwords = set([
                            "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "com", "não", "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como", "mas", "ao", "ele", "das", "à", "seu", "sua", "ou", "quando", "muito", "nos", "já", "eu", "também", "só", "pelo", "pela", "até", "isso", "ela", "entre", "depois", "sem", "mesmo", "aos", "seus", "quem", "nas", "me", "esse", "eles", "você", "essa", "num", "nem", "suas", "meu", "às", "minha", "numa", "pelos", "elas", "qual", "nós", "lhe", "deles", "essas", "esses", "pelas", "este", "dele", "tu", "te", "vocês", "vos", "lhes", "meus", "minhas", "teu", "tua", "teus", "tuas", "nosso", "nossa", "nossos", "nossas", "dela", "delas", "esta", "estes", "estas", "aquele", "aquela", "aqueles", "aquelas", "isto", "aquilo",
                            "vídeo", "vídeos", "youtube", "canal", "comentários", "transcrição", "resumo" # add some domain specific stopwords
                        ])
                        wc = WordCloud(stopwords=pt_stopwords, width=800, height=400)
                        frequencies = wc.process_text(prompt_text)
                        sorted_freq = sorted(frequencies.items(), key=lambda x: x[1], reverse=True)[:50]
                        data["palavras_nuvem"] = [{"palavra": word, "peso": count} for word, count in sorted_freq]
                        
                        st.session_state.analysis_data = data
                        st.session_state.aggregated_text = prompt_text # Store for chat context
                        st.session_state.chat_history = [] # Reset chat
                        
                        # We don't need to save social_listening_report.md to disk anymore.
                        # It is safe in st.session_state.analysis_data.
                        st.success("Análise Concluída com Sucesso!")
                            
                        # Run in-memory generation for formal report
                        st.write("---")
                        st.subheader("📦 Gerando Relatório Final...")
                        
                        try:
                            st.write("Gerando Relatório Estratégico Completo...")
                            # Prepare videos data in tuple format for get_report_content
                            videos_tuples = []
                            for v in st.session_state.videos_data[:max_videos_analyze]:
                                videos_tuples.append((
                                    v["ID"],
                                    v["Título"],
                                    v["Canal"],
                                    v["Publicado Em"],
                                    v["Score"],
                                    v["Visualizações"],
                                    v["Curtidas"],
                                    v["Comentários"],
                                    v.get("transcript", ""),
                                    v.get("comments_text", "")
                                ))
                            
                            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
                            enhanced_report = get_report_content(videos_tuples, api_key)
                            st.session_state.enhanced_report = enhanced_report
                            st.success("✅ Relatório Estratégico Gerado.")
                            
                            st.write("Gerando Apresentação em HTML...")
                            html_deck = get_html_deck_content(enhanced_report, api_key)
                            st.session_state.html_deck = html_deck
                            st.success("✅ Apresentação em HTML Gerada.")
                            
                        except Exception as e:
                            st.error(f"Erro ao gerar relatórios: {e}")

                    except Exception as e:
                        st.error(f"Erro ao processar JSON do Gemini: {e}")
                        print(f"Erro ao processar JSON do Gemini: {e}")
                        print(f"Raw Response was: {response.text}")
                        st.session_state.analysis_data = None

                        
        except Exception as e:
            st.error(f"Erro no pipeline: {e}")
st.markdown("</div>", unsafe_allow_html=True)

# --- DISPLAY SECTION ---
if "analysis_data" in st.session_state and st.session_state.analysis_data:
    data = st.session_state.analysis_data
    
    # 1. Top Section: KPIs
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("📊 Indicadores de Desempenho")
    
    df = pd.DataFrame(st.session_state.videos_data)
    total_videos = len(df)
    total_views = df["Visualizações"].sum() if not df.empty else 0
    top_channel = df.groupby('Canal')['Score'].sum().idxmax() if not df.empty else "N/A"
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Vídeos Mapeados", f"{total_videos}")
    col2.metric("Total de Visualizações", f"{total_views:,}".replace(',', '.'))
    col3.metric("Canal Top Impacto", top_channel)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 1.1) Table of videos mapped
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("📈 Ranking de Vídeos Mapeados")
    df["Publicado Em"] = df["Publicado Em"].apply(format_date)
    df["Link"] = df["ID"].apply(lambda x: f"https://www.youtube.com/watch?v={x}")
    display_cols = ["Score", "Título", "Canal", "Visualizações", "Curtidas", "Link"]
    st.dataframe(df[display_cols].head(max_videos_analyze), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 2) Wordcloud (D3.js)
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("🎯 Nuvem de Palavras")
    
    words_cloud_data = data.get("palavras_nuvem", [])
    if words_cloud_data:
        words_json = json.dumps([{"text": item["palavra"], "size": item["peso"]} for item in words_cloud_data])
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://d3js.org/d3.v7.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/d3-cloud/1.2.5/d3.layout.cloud.min.js"></script>
            <style>
                body {{ font-family: 'Helvetica Neue', sans-serif; margin: 0; overflow: hidden; background-color: #f8f9fa; }}
                text:hover {{ fill: #ff5722 !important; cursor: pointer; transition: fill 0.2s; }}
            </style>
        </head>
        <body>
            <div id="cloud" style="display: flex; justify-content: center; align-items: center; height: 400px;"></div>
            <script>
                var words = {words_json};
                var width = 800;
                var height = 400;
                var sizeScale = d3.scaleLinear()
                    .domain([d3.min(words, d => d.size), d3.max(words, d => d.size)])
                    .range([15, 60]);
                var layout = d3.layout.cloud()
                    .size([width, height])
                    .words(words)
                    .padding(3)
                    .rotate(function() {{ return ~~(Math.random() * 2) * 90; }})
                    .font("'Helvetica Neue', sans-serif")
                    .fontSize(function(d) {{ return sizeScale(d.size); }})
                    .on("end", draw);
                layout.start();
                function draw(words) {{
                    d3.select("#cloud").append("svg")
                        .attr("width", layout.size()[0])
                        .attr("height", layout.size()[1])
                        .append("g")
                        .attr("transform", "translate(" + layout.size()[0] / 2 + "," + layout.size()[1] / 2 + ")")
                        .selectAll("text")
                        .data(words)
                        .enter().append("text")
                        .style("font-size", function(d) {{ return d.size + "px"; }})
                        .style("font-family", "'Helvetica Neue', sans-serif")
                        .style("fill", function(d, i) {{ return d3.schemeCategory10[i % 10]; }})
                        .attr("text-anchor", "middle")
                        .attr("transform", function(d) {{
                            return "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")";
                        }})
                        .text(function(d) {{ return d.text; }})
                        .append("title")
                        .text(function(d) {{ return d.text + ": " + d.size; }});
                }}
            </script>
        </body>
        </html>
        """
        import streamlit.components.v1 as components
        components.html(html_content, height=420)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 3. Themes (Cards)
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("🏷️ Temas Mapeados por IA")
    
    for tema in data.get("temas", [])[:5]:
        st.markdown(f"""
        <div style="border: 1px solid #e0e3e8; border-radius: 8px; padding: 16px; margin-bottom: 10px; background-color: white;">
            <h4 style="margin-top: 0; color: #006397;">{tema.get('nome', 'Sem Nome')}</h4>
            <p style="margin-bottom: 0; color: #333;">{tema.get('descricao', '')}</p>
            <small style="color: #707881;">Frequência: {tema.get('frequencia', 1)}</small>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 3. Creators Chart
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("🏆 Top 5 Criadores Trending")
    
    df_creators = df.groupby('Canal').agg(
        Score_Total=('Score', 'sum'),
        Views_Total=('Visualizações', 'sum'),
        Qtd_Videos=('ID', 'count'),
        ChannelID=('ChannelID', 'first')
    ).reset_index().sort_values(by='Score_Total', ascending=False)
    
    creators_info = data.get("criadores", [])
    
    for index, row in df_creators.head(5).iterrows():
        canal_name = row['Canal']
        channel_id = row['ChannelID']
        ai_info = next((c for c in creators_info if c.get('canal', '').lower() == canal_name.lower()), None)
        
        html_content = f"<div style='border: 1px solid #e0e3e8; border-radius: 8px; padding: 16px; margin-bottom: 10px; background-color: white;'>"
        html_content += f"<h4 style='margin-top: 0; color: #006397;'><a href='https://www.youtube.com/channel/{channel_id}' target='_blank' style='color: #006397; text-decoration: none;'>{canal_name}</a></h4>"
        html_content += f"<p style='margin-bottom: 5px; color: #333;'><b>Score Total:</b> {row['Score_Total']:.2f}</p>"
        html_content += f"<p style='margin-bottom: 5px; color: #333;'><b>Visualizações:</b> {row['Views_Total']:,}</p>"
        html_content += f"<p style='margin-bottom: 5px; color: #333;'><b>Qtd Vídeos:</b> {row['Qtd_Videos']}</p>"
        
        if ai_info:
            html_content += f"<p style='margin-bottom: 5px; color: #333;'><b>Perfil:</b> {ai_info.get('perfil', 'N/A')}</p>"
            html_content += f"<p style='margin-bottom: 5px; color: #333;'><b>Tópicos:</b> {', '.join(ai_info.get('topicos', []))}</p>"
            html_content += f"<p style='margin-bottom: 0; color: #333;'><b>Tipos de Vídeo:</b> {', '.join(ai_info.get('tipos_video', []))}</p>"
            
        html_content += "</div>"
        
        st.markdown(html_content, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 3.1) Reports and Presentations
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("📄 Relatórios e Apresentações")
    
    if st.session_state.enhanced_report:
        st.download_button(
            label="Baixar Relatório Estratégico",
            data=st.session_state.enhanced_report,
            file_name="enhanced_social_listening_report.md",
            mime="text/markdown"
        )
            
    if st.session_state.html_deck:
        st.subheader("🖥️ Visualização da Apresentação de Oportunidades")
        import streamlit.components.v1 as components
        # Render the HTML deck in an iframe
        components.html(st.session_state.html_deck, height=600, scrolling=True)
        
        st.download_button(
            label="Baixar Apresentação (HTML)",
            data=st.session_state.html_deck,
            file_name="apresentacao_oportunidades_youtube.html",
            mime="text/html"
        )
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 4) Interactive Chat
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("💬 4. Chat Interativo com a Análise")
    st.write("Pergunte qualquer coisa sobre os resultados que o Gemini Flash irá responder com base no contexto.")
    
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    if user_query := st.chat_input("Ex: Qual o tema mais positivo? O que falaram sobre o termo X?"):
        with st.chat_message("user"):
            st.write(user_query)
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        
        with st.chat_message("assistant"):
            with st.spinner("Processando pergunta..."):
                context = st.session_state.aggregated_text
                
                # Append enhanced report content if exists
                if st.session_state.enhanced_report:
                    context += "\n\n--- RELATÓRIO ESTRATÉGICO ---\n" + st.session_state.enhanced_report
                        
                from datetime import datetime
                today_str = datetime.now().strftime('%Y-%m-%d')
                advertiser_deck_path = f"{today_str}-advertiser_deck_24h.md"
                if os.path.exists(advertiser_deck_path):
                    with open(advertiser_deck_path, "r", encoding="utf-8") as f:
                        context += "\n\n--- DECK DE ANUNCIANTES ---\n" + f.read()
                        
                prompt = f"""
                Você é um assistente especialista em Social Listening.
                Com base no seguinte resumo do conteúdo coletado:
                {context}
                
                Responda à pergunta do usuário: {user_query}
                Responda em Português do Brasil.
                """
                try:
                    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
                    g_client = genai.Client(api_key=api_key)
                    response = g_client.models.generate_content(
                        model="gemini-3.5-flash",
                        contents=prompt,
                    )
                    st.write(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Erro no chat: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

# End of display section


