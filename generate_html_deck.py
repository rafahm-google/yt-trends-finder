import os
import json
from google import genai
from dotenv import load_dotenv

def get_html_deck_content(report_content, api_key=None):
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
        
    if not api_key:
        raise ValueError("API Key not found.")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Você é um estrategista de conteúdo e designer sênior.
    Com base no seguinte relatório estratégico:
    {report_content}

    Gere uma apresentação de tendências e oportunidades de conteúdo em formato HTML/CSS de no máximo 5 slides.
    Esta apresentação será usada para mostrar oportunidades de formatos e engajamento para criadores do YouTube com base nas tendências reais mapeadas no relatório.

    **REGRA DE OURO DE CONTEÚDO (MANDATÓRIA):**
    Você deve basear o conteúdo dos slides **ESTRITAMENTE** no relatório estratégico fornecido.
    - NÃO invente temas ou criadores que não estejam no relatório.
    - NÃO force uma narrativa de "Copa do Mundo" se o relatório for sobre outro tema (como um técnico de clube, ex: Abel Ferreira). O título e o conteúdo do Slide 1 devem refletir **fielmente** o tema real do relatório (ex: "Tendências: Foco em Abel Ferreira" ou "O Efeito Abel Ferreira no Palmeiras").
    - **EVITE CITAR QUALQUER MARCA OU ANUNCIANTE ESPECÍFICO.** O foco deve ser totalmente no ecossistema do YouTube, nos criadores de conteúdo e em como eles podem aproveitar essas tendências.
    - Gere textos realistas, informativos e focados em estratégias de conteúdo para o YouTube, evitando termos de publicidade tradicional de marcas.

    **INSPIRAÇÃO DE ESTRUTURA E NARRATIVA (Estilo Visual de Tendências)**:
    - **Slide 1: Capa & Escala**: Use um título forte e atraente condizente com o tema real da análise (ex: "YouTube Trends: [Tema Real]") e apresente números grandes que mostram a escala da análise (ex: "Gemini analisou X vídeos nas últimas Y horas" - use dados reais do apêndice do relatório se disponíveis).
    - **Slide 2: O Pulso da Audiência**: Liste as principais paixões ou temas reais mapeados no relatório, com uma breve frase explicativa para cada um, focando no interesse do público do YouTube.
    - **Slide 3: Foco nos Temas (Cards)**: Escolha até 3 temas reais mais fortes do relatório e crie um card para cada um contendo:
        - Título curto e impactante da tendência.
        - Um parágrafo curto, completo explicando como essa tendência se comporta no YouTube.
        - Um índice de engajamento/relevância (pode usar estrelas ou barras).
    - **Slide 4: O Mapa de Criadores & Oportunidades**: Apresente os criadores reais em destaque (cite os canais reais presentes no relatório) em formato de cards. Para cada um, explique o perfil real do canal e a **oportunidade específica de formato ou conteúdo no YouTube** para ele capitalizar nessa tendência.
    - **Slide 5: A Sugestão de Formato/Projeto**: Apresente a ideia de formato de vídeo, collab ou projeto de conteúdo sugerida no relatório (mantenha os temas reais sugeridos lá) como a grande oportunidade prática para os criadores se conectarem com essa audiência no YouTube, com mecânica e benefícios claros de engajamento.

    **REQUISITOS DE CONTEÚDO**:
    - **Narrativa Persuasiva e Fiel**: O texto deve ser focado em criação de conteúdo e engajamento no YouTube. Não invente marcas patrocinadoras ou campanhas comerciais. Foco em "como o criador pode crescer e engajar".
    - **Auto-explicativo**: Escreva parágrafos curtos mas completos que expliquem a oportunidade claramente.
    - **Foco no YouTube**: Use uma linguagem que valorize a comunidade do YouTube, a fidelização de inscritos e o alcance orgânico.

    O design deve ser:
    - Visualmente rico, limpo, com cards bem definidos e bastante espaço em branco.
    - Use as cores da marca YouTube: Vermelho (#FF0000), Preto e Branco como base.
    - Cada slide deve ser uma seção <section> que caiba na tela inteira (viewport height).
    - Use fontes modernas (ex: sans-serif).
    - **NÃO inclua botões, links (tags <a>) ou qualquer elemento interativo.** A apresentação deve parecer um slide deck normal e estático.

    Retorne APENAS o código HTML completo e válido, incluindo o CSS interno (dentro da tag <style>). Não inclua blocos de código markdown (como ```html). Comece diretamente com <!DOCTYPE html>.
    **ATENÇÃO**: Mantenha o HTML puramente estático para exibição estável em um iframe e para exportação para PDF.
    """
    
    print("Solicitando geração de slides HTML ao Gemini...")
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
    )
    
    html_content = response.text.strip()
    
    # Clean up potential markdown markers if model ignored instructions
    if html_content.startswith("```html"):
        html_content = html_content[7:]
    if html_content.endswith("```"):
        html_content = html_content[:-3]
    html_content = html_content.strip()
    
    return html_content

def generate_html_deck():
    load_dotenv()
    
    report_path = "enhanced_social_listening_report.md"
    if not os.path.exists(report_path):
        print(f"Error: {report_path} not found. Run generate_enhanced_report.py first.")
        return
        
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()
        
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("YOUTUBE_API_KEY")
    
    try:
        html_content = get_html_deck_content(report_content, api_key)
        output_path = "advertiser_pitch_deck.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Sucesso: Deck HTML gerado em {output_path}")
    except Exception as e:
        print(f"Erro ao gerar deck HTML: {e}")

if __name__ == "__main__":
    generate_html_deck()
