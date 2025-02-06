import os
import time
from datetime import datetime
from pathlib import Path
import re

from flask import Flask, render_template, request, jsonify, url_for, Response
from dotenv import load_dotenv
from google import genai
from google.genai import types

# PDF 생성을 위한 ReportLab 라이브러리 임포트
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4  # 페이지 사이즈 설정
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer  # 텍스트 단락 및 간격
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # 스타일 시트 및 ParagraphStyle 임포트
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 서비스 함수 임포트 (generate_script, generate_audio, add_background_music는 이미 구현되어 있다고 가정)
from services.models import generate_script, generate_audio, add_background_music
from utils.text_processing import process_query

# Flask 앱 초기화
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# 환경 변수 로드 및 Gemini API 설정
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# 결과 파일 저장 디렉토리 (static/generated_podcasts)
output_dir = Path("static/generated_podcasts")
output_dir.mkdir(parents=True, exist_ok=True)

# 보고서 파일 저장 디렉토리 (static/generated_reports)
output_report_dir = Path("static/generated_reports")
output_report_dir.mkdir(parents=True, exist_ok=True)

# 전역 캐시: query를 키로 하여 Gemini API의 응답 객체를 저장합니다.
search_cache = {}

# NanumGothic 폰트 등록 (코드 시작 시점에 한 번만 실행)
font_path = os.path.join("static", "fonts", "NanumGothic.ttf")  # static 폴더 내 fonts 폴더에 폰트 파일 위치
if os.path.exists(font_path):
    try:
        pdfmetrics.registerFont(TTFont('NanumGothic', font_path))
        print("NanumGothic 폰트 등록 성공")
    except Exception as e:
        print(f"**경고: NanumGothic 폰트 등록 실패: {e}**")
else:
    print(f"**경고: 폰트 파일({font_path})을 찾을 수 없습니다. NanumGothic 폰트 등록 실패.**")


def save_outputs(script: str, audio: bytes, query: str) -> tuple:
    """스크립트와 오디오 파일을 저장"""
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
    """검색 결과에서 소스 URL, 제목, 썸네일 추출
    웹 데이터에 thumbnail 속성이 없으면 기본 placeholder 이미지를 사용합니다.
    """
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
        # 오류 발생 시 pass (로깅 제거)
        pass
    return sources

def generate_report_content(query: str, search_text: str) -> str:
    """
    Gemini API를 이용하여 검색 결과를 기반으로 고퀄리티 보고서를 생성합니다.
    프롬프트에 체계적 구성, 심도 있는 분석, 결론 요약 등을 요청하여 보고서의 퀄리티를 높입니다.
    """
    report_prompt = (
        f"주제 '{query}'에 대해 다음의 검색 결과를 참고하여 매우 체계적이고 심도 있는 분석이 포함된 고퀄리티 보고서를 작성해 주세요.\n\n"
        f"검색 결과:\n{search_text}\n\n"
        "보고서는 서론, 본론(분석 내용), 결론 및 주요 통찰 요약으로 구성되며, 독자가 내용을 쉽게 이해할 수 있도록 상세하고 명확하게 작성해 주시기 바랍니다."
    )
    report_result = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=report_prompt,
        config=types.GenerateContentConfig(
            # 추가 옵션이 필요하면 여기에 설정합니다.
        )
    )
    return report_result.text or "보고서 생성에 실패하였습니다."

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stream_search")
def stream_search():
    """SSE 방식으로 검색 결과를 스트리밍하며, Gemini API 호출 결과를 캐시에 저장"""
    query = request.args.get('query')

    def generate():
        if not query:
            yield "data: \n\n"
            return

        try:
            if query not in search_cache:
                search_result = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=query,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearchRetrieval)]
                    )
                )
                search_cache[query] = search_result
            else:
                search_result = search_cache[query]

            full_text = search_result.text or ""
            chunk_size = 100

            def format_chunk(text):
                return "\n".join("data: " + line for line in text.splitlines())

            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i:i + chunk_size]
                formatted_chunk = format_chunk(chunk)
                yield f"{formatted_chunk}\n\n"
                time.sleep(0.2)

        except Exception as e:
            # 오류 발생 시 클라이언트에 SSE 이벤트로 전송
            yield f"data: 오류: 검색 스트리밍 중 문제가 발생했습니다: {e}\n\n"

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return Response(generate(), headers=headers)

@app.route("/generate_podcast", methods=["POST"])
def generate_podcast():
    """팟캐스트 생성 및 정보 반환 (Gemini API 결과를 캐시에서 재사용)"""
    query = request.form.get("query")
    if not query:
        return jsonify({"error": "쿼리 없음"}), 400

    try:
        # 캐시에서 Gemini API 결과 재사용 (없다면 호출)
        if query in search_cache:
            search_result = search_cache[query]
            del search_cache[query]
        else:
            search_result = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearchRetrieval)]
                )
            )
        # 검색 결과의 텍스트를 기반으로 스크립트 생성 (UI에 스크립트는 전달하지 않음)
        script = generate_script(query, search_result.text, duration_minutes=3)
        audio = generate_audio(script)
        if audio:
            script_file, audio_file = save_outputs(script, audio, query)
            music_file = os.path.join("static", "background.mp3")
            output_with_music = str(output_dir / f"podcast_with_bgm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
            result_file = add_background_music(audio_file, music_file, output_with_music)
            if result_file is None:
                return jsonify({"error": "팟캐스트 생성 실패 (배경음악 추가 오류)"}), 500
            # Windows 경로 구분자를 URL용 슬래시로 변환
            relative_path = os.path.relpath(result_file, "static").replace("\\", "/")
            podcast_url = url_for('static', filename=relative_path)
            sources = extract_sources(search_result)
            return jsonify({"podcast_url": podcast_url, "sources": sources})
        else:
            return jsonify({"error": "오디오 생성 실패"}), 500
    except Exception as e:
        return jsonify({"error": "팟캐스트 생성 중 오류가 발생했습니다.", "details": str(e)}), 500

@app.route("/generate_report", methods=["POST"])
def generate_report_route():
    """검색 결과를 바탕으로 고퀄리티 보고서를 생성하고 URL을 반환합니다."""
    query = request.form.get("query")
    if not query:
        return jsonify({"error": "쿼리 없음"}), 400

    try:
        # Gemini API 호출 (캐시 처리 제외)
        if query in search_cache:
            search_result = search_cache[query]
            del search_cache[query]
        else:
            search_result = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearchRetrieval)]
                )
            )

        # 고퀄리티 보고서 생성
        report_text = generate_report_content(query, search_result.text)

        # ** 텍스트 bold 처리 및 사이즈 증가 처리
        # ** 사이의 텍스트는 <b><font size="12">태그로 감쌉니다.
        processed_text = re.sub(r'\*\*(.+?)\*\*', r'<b><font size="12">\1</font></b>', report_text)

        # 보고서 파일 저장 (PDF 형식)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"report_{timestamp}"
        report_filename = output_report_dir / f"{base_filename}.pdf"  # 확장자 .pdf

        # SimpleDocTemplate을 이용하여 PDF 생성
        doc = SimpleDocTemplate(str(report_filename), pagesize=A4)
        styles = getSampleStyleSheet()

        # 한글 폰트 스타일 적용 (NanumGothic이 등록된 경우)
        if 'NanumGothic' in pdfmetrics.getRegisteredFontNames():
            styles['Title'].fontName = 'NanumGothic'
            styles['BodyText'].fontName = 'NanumGothic'
            styles['BodyText'].leading = 14  # 줄 간격 조정
            # 소제목 스타일 (## 표시된 줄용) 추가: 폰트 사이즈 16, 볼드 처리, 가운데 정렬
            styles.add(ParagraphStyle(name='Subtitle',
                                      parent=styles['Heading2'],
                                      fontName='NanumGothic',
                                      fontSize=16,
                                      leading=18,
                                      alignment=1,  # 가운데 정렬
                                      spaceAfter=12))
            # 제목 스타일 (이미 CenterTitle를 사용하는 경우)
            styles.add(ParagraphStyle(name='CenterTitle',
                                      parent=styles['Title'],
                                      alignment=1,
                                      fontName='NanumGothic'))
            print("NanumGothic 폰트 스타일 적용 완료")
        else:
            print("**경고: NanumGothic 폰트가 등록되지 않아 기본 폰트 사용.**")

        flowables = []

        # 최적화된 쿼리 처리 (제목용)
        optimized_query = process_query(query)
        title = Paragraph(f"<b>{optimized_query}</b>", styles["CenterTitle"])
        flowables.append(title)
        flowables.append(Spacer(1, 12))

        # report_text를 줄 단위로 분리하여 처리 (소제목(##)과 일반 문단을 구분)
        lines = processed_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue  # 빈 줄은 건너뜀
            if line.startswith("##"):
                # "##"로 시작하는 경우, 소제목으로 처리
                subtitle_text = line.lstrip("#").strip()
                flowables.append(Paragraph(subtitle_text, styles["Subtitle"]))
                flowables.append(Spacer(1, 6))
            else:
                # 일반 문단: inline bold 처리는 이미 적용되어 있음
                flowables.append(Paragraph(line, styles["BodyText"]))
                flowables.append(Spacer(1, 6))

        # PDF 문서 빌드
        doc.build(flowables)

        # URL용 상대 경로 변환 (Windows 경로 구분자 처리)
        relative_path = os.path.relpath(report_filename, "static").replace("\\", "/")
        report_url = url_for('static', filename=relative_path)

        return jsonify({"report_url": report_url, "report_format": "pdf"})
    except Exception as e:
        return jsonify({"error": "보고서 생성 중 오류가 발생했습니다.", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
