# ReportCast(실시간 인공지능 검색으로 팟캐스트 및 보고서 생성 애플리케이션)

이 프로젝트는 Gemini API와 다양한 서비스를 활용하여 사용자가 입력한 쿼리를 바탕으로 팟캐스트(오디오 파일)와 PDF 보고서를 생성하는 Flask 웹 애플리케이션입니다.  
검색 결과를 기반으로 스크립트 생성, 음성 합성, 배경 음악 추가, 그리고 고퀄리티 보고서 생성을 지원합니다.


https://github.com/user-attachments/assets/48c18998-620e-4121-9dd8-63040d728005



## 주요 기능

- **검색 스트리밍**: 사용자가 입력한 쿼리에 대해 Gemini API를 통해 검색 결과를 실시간 스트리밍(SSE) 방식으로 전달합니다.
- **팟캐스트 생성**: 검색 결과를 기반으로 스크립트를 작성하고, 음성 합성을 통해 팟캐스트(오디오 파일)를 생성합니다.  
  생성된 오디오에 배경 음악을 추가할 수 있습니다.
- **보고서 생성**: 검색 결과를 참고하여 체계적이고 심도 있는 분석이 포함된 PDF 보고서를 생성합니다.  
  보고서 내 텍스트의 일부를 HTML 태그를 활용하여 강조(볼드, 폰트 크기 증가) 처리합니다.
- **캐싱**: 동일한 쿼리에 대해 Gemini API 호출 결과를 캐시하여 불필요한 중복 호출을 방지합니다.
- **한글 지원**: NanumGothic 폰트를 등록하여 PDF 보고서에서 한글이 올바르게 렌더링되도록 지원합니다.

## 프로젝트 구조

```
├── app.py                    # Flask 애플리케이션 엔트리 파일
├── services/
│   └── models.py             # generate_script, generate_audio, add_background_music 등의 서비스 함수 구현
├── utils/
│   └── text_processing.py    # 쿼리 최적화 등의 텍스트 처리 함수
├── static/
│   ├── generated_podcasts/   # 생성된 팟캐스트 파일 저장 폴더
│   ├── generated_reports/    # 생성된 PDF 보고서 저장 폴더
│   ├── fonts/
│   │   └── NanumGothic.ttf   # 한글 폰트 파일 (NanumGothic)
│   └── background.mp3        # 팟캐스트 배경 음악 파일
├── templates/
│   └── index.html            # 메인 웹 페이지 템플릿
├── .env                      # 환경 변수 파일 (GEMINI_API_KEY 등)
└── README.md                 # 프로젝트 설명 파일 (현재 파일)
```

## 설치 및 실행 방법

### 1. 요구사항

- Python 3.7 이상
- Flask
- python-dotenv
- google-genai
- reportlab
- 기타: requests 등 필요 라이브러리 (코드 내에 언급된 외부 라이브러리)

#### 예시 requirements.txt:

```
Flask
python-dotenv
google-genai
reportlab
```

### 2. 환경 변수 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고, Gemini API Key를 포함시킵니다.

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. 폰트 및 정적 파일 설정

- `static/fonts/` 폴더 내에 `NanumGothic.ttf` 폰트 파일을 추가합니다.
- 배경 음악 파일(`background.mp3`)을 `static/` 폴더에 위치시킵니다.

### 4. 애플리케이션 실행

가상환경을 활성화한 후 아래 명령어를 통해 애플리케이션을 실행합니다.
```bash
python app.py
```

## API 엔드포인트

### 1. 메인 페이지

- **URL:** `/`
- **메소드:** `GET`
- **설명:** 애플리케이션의 메인 페이지(템플릿 렌더링).

### 2. 검색 결과 스트리밍

- **URL:** `/stream_search`
- **메소드:** `GET`
- **파라미터:** `query` (검색 쿼리)
- **설명:** SSE(Server-Sent Events)를 통해 검색 결과를 실시간 스트리밍합니다.

### 3. 팟캐스트 생성

- **URL:** `/generate_podcast`
- **메소드:** `POST`
- **파라미터:** `query` (폼 데이터)
- **설명:** 검색 결과를 기반으로 팟캐스트 스크립트를 작성하고, 오디오 파일을 생성한 후 배경음악을 추가합니다.  
  생성된 팟캐스트의 URL 및 검색 결과의 소스 정보를 반환합니다.

### 4. 보고서 생성

- **URL:** `/generate_report`
- **메소드:** `POST`
- **파라미터:** `query` (폼 데이터)
- **설명:** 검색 결과를 바탕으로 고퀄리티 분석 보고서를 PDF로 생성합니다.  
  생성된 보고서의 URL과 형식을 반환합니다.

## 개발 및 커스터마이징

- **서비스 함수 구현**: `services/models.py` 내의 `generate_script`, `generate_audio`, `add_background_music` 함수는 각자의 로직에 맞게 구현되어야 합니다.
- **텍스트 처리**: `utils/text_processing.py` 내의 `process_query` 함수는 검색 쿼리 최적화를 위해 사용됩니다.
- **Gemini API**: Google Gemini API를 사용하여 콘텐츠를 생성합니다. 사용 전 [Google Gemini API 문서](https://developers.google.com/genai)를 참고하여 필요한 옵션들을 확인하세요.

## 라이선스

이 프로젝트는 MIT 라이선스에 따라 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 확인하세요.

## 문의

프로젝트와 관련된 문의사항은 이슈를 등록하거나 담당자에게 연락 주시기 바랍니다.

