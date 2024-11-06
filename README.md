# Gemini 기반 AI Search Engine

이 프로젝트는 **Google Gemini** API와 **Flask**를 사용하여 실시간 텍스트 응답을 생성하고, 생성된 응답을 스트리밍 방식으로 클라이언트에 전송하는 웹 애플리케이션입니다. Google의 Gemini 모델과 검색 기능을 통해 사용자가 입력한 질문에 대한 고품질 응답을 제공합니다. 텍스트는 청크 단위로 전송되므로, 사용자는 전체 응답이 완료되기 전에 일부 데이터를 먼저 확인할 수 있습니다.

## 기능 소개

- **실시간 텍스트 응답 스트리밍**: 긴 응답을 청크 단위로 클라이언트에 전송하여 사용자 경험을 개선하고, 응답이 모두 준비되기 전에 결과를 미리 확인할 수 있습니다.
- **Google 검색 기반 정보 소스 제공**: Gemini 모델의 검색 기능을 통해 신뢰할 수 있는 출처와 관련 정보가 포함된 응답을 생성하여 정확성과 신뢰성을 높입니다.
- **Flask 웹 서버**: 경량 웹 프레임워크인 Flask를 사용하여 백엔드 서버를 구현하고, 클라이언트와의 원활한 상호 작용을 제공합니다.

## 시작하기

### 필수 구성 요소
- Python 3.7 이상
- `pip` 패키지 관리자
- Google Cloud API 키

### 설치 방법

1. **저장소 클론**
   ```bash
   git clone https://github.com/bigdefence/gemini-search.git
   cd gemini-search

## 필요한 패키지 설치

### 아래 명령어를 실행하여 패키지를 설치합니다: 
```
pip install -r requirements.txt
```
requirements.txt 파일에는 Flask, google.generativeai, python-dotenv 등이 포함됩니다.

## 환경 변수 설정

Google Generative AI API 키를 사용하여 .env 파일을 생성하고 API 키를 설정합니다.
```
GOOGLE_API_KEY=your_google_api_key_here
```
#### 실행 방법
- Flask 앱 실행:
```
python main.py
```
웹 브라우저에서 http://127.0.0.1:5000에 접속하여 애플리케이션을 사용할 수 있습니다.

#### 주요 코드 설명
```plaintext
파일 구조
├── main.py                  # 메인 Flask 애플리케이션 파일
├── templates/
│   └── index.html          # 프론트엔드 HTML 파일
├── .env                    # Google API 키 설정 파일
├── requirements.txt        # 필요한 패키지 목록
└── README.md               # 프로젝트 설명 파일
```

## 요구사항
- Flask: Python을 기반으로 한 웹 애플리케이션 프레임워크입니다.
- Google Generative AI: 고품질의 텍스트를 생성하고, 검색 기능을 통해 신뢰할 수 있는 자료를 제공하는 AI API입니다.
- python-dotenv: 환경 변수 파일을 로드하기 위한 라이브러리입니다.


## 참고 자료
- Google Generative AI API
