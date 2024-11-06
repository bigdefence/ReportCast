from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import time  # 청크 전송 간 지연을 위해 사용

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('models/gemini-1.5-pro-002')

app = Flask(__name__)

def extract_sources(response):
    """검색 결과에서 소스 URL 추출"""
    sources = []
    
    try:
        # response의 첫 번째 candidate에서 grounding_metadata 확인
        if hasattr(response, 'candidates') and response.candidates:
            metadata = response.candidates[0].grounding_metadata
            if hasattr(metadata, 'grounding_chunks'):
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, 'web'):
                        sources.append({
                            'url': chunk.web.uri,
                            'title': chunk.web.title
                        })
    except Exception as e:
        print(f"소스 추출 중 오류 발생: {str(e)}")
        
    return sources

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')

        # API로부터 전체 응답을 받음
        response = model.generate_content(
            contents=prompt,
            tools='google_search_retrieval',
        )

        # 응답 텍스트를 청크 단위로 나누기
        response_text = response.text
        chunk_size = 100
        chunks = [response_text[i:i+chunk_size] for i in range(0, len(response_text), chunk_size)]
        
        # 소스 추출
        sources = extract_sources(response)

        # 청크를 순차적으로 전송하는 함수
        def generate_chunks():
            for chunk in chunks:
                chunk_data = {
                    'text': chunk,
                    'done': False
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
                time.sleep(0.1)  # 청크 사이에 지연 추가
            # 최종 소스와 완료 플래그 전송
            yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"

        return Response(stream_with_context(generate_chunks()), content_type='text/event-stream')

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
