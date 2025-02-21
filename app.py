import os
import time
from datetime import datetime
from pathlib import Path
import re
import json

from flask import Flask, render_template, request, jsonify, url_for, Response
from dotenv import load_dotenv
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, GoogleSearchRetrieval

# PDF 생성을 위한 ReportLab 라이브러리 임포트
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from services.models import generate_script, generate_audio, add_background_music
from utils.text_processing import process_query

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


output_dir = Path("static/generated_podcasts")
output_dir.mkdir(parents=True, exist_ok=True)

output_report_dir = Path("static/generated_reports")
output_report_dir.mkdir(parents=True, exist_ok=True)

# 캐시 키에 모델 정보를 포함하도록 변경
search_cache = {}

font_path = os.path.join("static", "fonts", "NanumGothic.ttf")
if os.path.exists(font_path):
    try:
        pdfmetrics.registerFont(TTFont('NanumGothic', font_path))
        print("NanumGothic 폰트 등록 성공")
    except Exception as e:
        print(f"**경고: NanumGothic 폰트 등록 실패: {e}**")
else:
    print(f"**경고: 폰트 파일({font_path})을 찾을 수 없습니다. NanumGothic 폰트 등록 실패.**")

def save_outputs(script: str, audio: bytes, query: str) -> tuple:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"podcast_{timestamp}"

    script_filename = output_dir / f"{base_filename}.txt"
    with open(script_filename, "w", encoding="utf-8") as f:
        f.write(f"주제: {query}\n\n")
        f.write(script)

    audio_filename = output_dir / f"{base_filename}.mp3"
    with open(audio_filename, "wb") as f:
        f.write(audio)

    return script_filename, audio_filename

def extract_sources(response):
    sources = []
    try:
        if response and hasattr(response, 'candidates') and response.candidates:
            metadata = getattr(response.candidates[0], 'grounding_metadata', None)
            if metadata and hasattr(metadata, 'grounding_chunks'):
                for chunk in metadata.grounding_chunks:
                    web_data = getattr(chunk, 'web', None)
                    if web_data and hasattr(web_data, 'uri'):
                        sources.append({
                            'url': web_data.uri,
                            'title': getattr(web_data, 'title', '제목 없음'),
                        })
    except Exception as e:
        pass
    return sources

def generate_report_content(client, query: str, search_text: str, model_name: str) -> str:
    report_prompt = (
        f"주제 '{query}'에 대해 다음의 검색 결과를 참고하여 매우 체계적이고 심도 있는 분석이 포함된 고퀄리티 보고서를 작성해 주세요.\n\n"
        f"검색 결과:\n{search_text}\n\n"
        "보고서는 서론, 본론(분석 내용), 결론 및 주요 통찰 요약으로 구성되며, 독자가 내용을 쉽게 이해할 수 있도록 상세하고 명확하게 작성해 주시기 바랍니다."
    )
    report_result = client.models.generate_content(
        model=model_name,
        contents=report_prompt,
    )
    return report_result.text or "보고서 생성에 실패하였습니다."

def get_model_name(model_param: str) -> str:
    if model_param and model_param.lower() == "thinking":
        return "gemini-2.0-flash-thinking-exp"
    return "gemini-2.0-flash"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stream_search")
def stream_search():
    query = request.args.get('query')
    model_param = request.args.get("model", "flash-2.0")
    model_name = get_model_name(model_param)
    cache_key = f"{query}_{model_name}"
    print(f'쿼리: {query} / 모델: {model_name}')
    if model_name == "gemini-2.0-flash":
        client = genai.Client(api_key=GEMINI_API_KEY)
    else:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version':'v1alpha'})
    def generate():
        if not query:
            yield "data: \n\n"
            return

        try:
            if cache_key not in search_cache:
                search_result = client.models.generate_content(
                    model=model_name,
                    contents=query,
                    config=GenerateContentConfig(
                        tools=[Tool(google_search=GoogleSearch)]
                    )
                )
                search_cache[cache_key] = search_result
            else:
                search_result = search_cache[cache_key]

            full_text = search_result.text or ""
            chunk_size = 300
            sources = extract_sources(search_result)

            def format_chunk(text):
                return "\n".join("data: " + line for line in text.splitlines())

            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i:i + chunk_size]
                formatted_chunk = format_chunk(chunk)
                yield f"{formatted_chunk}\n\n"
                time.sleep(0.5)
            
            yield f"event: sources\ndata: {json.dumps({'sources': sources})}\n\n"
            yield "data: \n\n"
        except Exception as e:
            yield f"data: 오류: 검색 스트리밍 중 문제가 발생했습니다: {e}\n\n"

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return Response(generate(), headers=headers)

@app.route("/generate_podcast", methods=["POST"])
def generate_podcast():
    query = request.form.get("query")
    model_param = request.form.get("model", "flash-2.0")
    model_name = get_model_name(model_param)
    cache_key = f"{query}_{model_name}"
    if not query:
        return jsonify({"error": "쿼리 없음"}), 400

    # 선택한 모델에 따라 client 인스턴스를 생성합니다.
    if model_name == "gemini-2.0-flash":
        client_instance = genai.Client(api_key=GEMINI_API_KEY)
    else:
        client_instance = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version':'v1alpha'})

    try:
        if cache_key in search_cache:
            search_result = search_cache[cache_key]
            del search_cache[cache_key]
        else:
            search_result = client_instance.models.generate_content(
                model=model_name,
                contents=query,
                config=GenerateContentConfig(
                    tools=[Tool(google_search=GoogleSearch)]
                )
            )
        script = generate_script(query, search_result.text, duration_minutes=3)
        audio = generate_audio(script)
        if audio:
            script_file, audio_file = save_outputs(script, audio, query)
            # 배경음악 파일 경로 확인
            music_file = os.path.join("static", "background.mp3")
            if not os.path.exists(music_file):
                return jsonify({
                    "error": "배경음악 파일이 존재하지 않습니다.",
                    "details": f"파일 경로: {music_file}"
                }), 500

            output_with_music = str(output_dir / f"podcast_with_bgm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
            result_file = add_background_music(audio_file, music_file, output_with_music)
            
            if result_file is None:
                # add_background_music 함수 내부에서 자세한 오류 메시지를 로깅하도록 구현하는 것이 좋습니다.
                return jsonify({"error": "팟캐스트 생성 실패 (배경음악 추가 오류)"}), 500
            relative_path = os.path.relpath(result_file, "static").replace("\\", "/")
            podcast_url = url_for('static', filename=relative_path)
            return jsonify({"podcast_url": podcast_url})
        else:
            return jsonify({"error": "오디오 생성 실패"}), 500
    except Exception as e:
        return jsonify({"error": "팟캐스트 생성 중 오류가 발생했습니다.", "details": str(e)}), 500


@app.route("/generate_report", methods=["POST"])
def generate_report_route():
    query = request.form.get("query")
    model_param = request.form.get("model", "flash-2.0")
    model_name = get_model_name(model_param)
    cache_key = f"{query}_{model_name}"
    if not query:
        return jsonify({"error": "쿼리 없음"}), 400

    if model_name == "gemini-2.0-flash":
        client_instance = genai.Client(api_key=GEMINI_API_KEY)
    else:
        client_instance = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version':'v1alpha'})

    try:
        if cache_key in search_cache:
            search_result = search_cache[cache_key]
            del search_cache[cache_key]
        else:
            search_result = client_instance.models.generate_content(
                model=model_name,
                contents=query,
                config=GenerateContentConfig(
                    tools=[Tool(google_search=GoogleSearch)]
                )
            )
        print("검색 결과:", search_result.text)
        # client_instance를 인자로 전달합니다.
        report_text = generate_report_content(client_instance, query, search_result.text, model_name)
        processed_text = re.sub(r'\*\*(.+?)\*\*', r'<b><font size="12">\1</font></b>', report_text)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"report_{timestamp}"
        report_filename = output_report_dir / f"{base_filename}.pdf"

        doc = SimpleDocTemplate(str(report_filename), pagesize=A4)
        styles = getSampleStyleSheet()

        if 'NanumGothic' in pdfmetrics.getRegisteredFontNames():
            styles['Title'].fontName = 'NanumGothic'
            styles['BodyText'].fontName = 'NanumGothic'
            styles['BodyText'].leading = 14
            styles.add(ParagraphStyle(name='Subtitle',
                                      parent=styles['Heading2'],
                                      fontName='NanumGothic',
                                      fontSize=16,
                                      leading=18,
                                      alignment=1,
                                      spaceAfter=12))
            styles.add(ParagraphStyle(name='CenterTitle',
                                      parent=styles['Title'],
                                      alignment=1,
                                      fontName='NanumGothic'))
            print("NanumGothic 폰트 스타일 적용 완료")
        else:
            print("**경고: NanumGothic 폰트가 등록되지 않아 기본 폰트 사용.**")

        flowables = []
        optimized_query = process_query(query)
        title = Paragraph(f"<b>{optimized_query}</b>", styles["CenterTitle"])
        flowables.append(title)
        flowables.append(Spacer(1, 12))

        for line in processed_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith("##"):
                subtitle_text = line.lstrip("#").strip()
                flowables.append(Paragraph(subtitle_text, styles["Subtitle"]))
                flowables.append(Spacer(1, 6))
            else:
                flowables.append(Paragraph(line, styles["BodyText"]))
                flowables.append(Spacer(1, 6))

        doc.build(flowables)

        relative_path = os.path.relpath(report_filename, "static").replace("\\", "/")
        report_url = url_for('static', filename=relative_path)
        return jsonify({"report_url": report_url, "report_format": "pdf"})
    except Exception as e:
        return jsonify({"error": "보고서 생성 중 오류가 발생했습니다.", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
