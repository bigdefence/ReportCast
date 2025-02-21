import openai
from utils.config import OPENAI_API_KEY
from typing import Optional, Dict, Any, List
from pydub import AudioSegment
openai.api_key = OPENAI_API_KEY



def generate_script(query: str, search_results: str, 
                       duration_minutes: int = 5) -> str:
    system_prompt = """You are an expert Korean podcast script writer. Your task is to create a precisely formatted script 
that follows strict formatting rules. The podcast features two AI hosts:

- 지식: The knowledgeable host who explains concepts clearly and systematically
- 호기심: The curious host who asks questions and provides engaging perspectives

CRITICAL FORMATTING RULES:
1. EVERY line must start with either "지식: " or "호기심: " (including the space after colon)
2. NO empty lines between dialogue
3. NO special characters or parentheses in speaker labels
4. NO narrative descriptions or action notes
5. Each line must contain actual dialogue text after the speaker label
6. NO line breaks within a single speaker's dialogue
7. Lines MUST alternate between speakers - no consecutive lines from the same speaker
8. ALL text must be in Korean

Example of CORRECT formatting:
지식: 안녕하세요 여러분, 오늘의 주제는 인공지능의 발전입니다.
호기심: 아, 정말 흥미로운 주제네요. 어떤 내용을 다루게 될까요?
지식: 먼저 인공지능의 기본 개념부터 설명해드리겠습니다.
호기심: 청취자분들도 궁금해하실 것 같아요.

INCORRECT formatting examples to AVOID:
(X) 지식 : 안녕하세요 (띄어쓰기 틀림)
(X) [호기심] 네, 안녕하세요 (괄호 사용)
(X) 지식: (밝은 목소리로) 안녕하세요 (지시문 포함)
(X) 진행자: 안녕하세요 (잘못된 화자 라벨)
(X) (빈 줄) (빈 줄 사용)
(X) 지식: (대사 없음)"""

    user_prompt = f"""다음 검색 결과를 바탕으로 {duration_minutes}분 길이의 팟캐스트 대본을 작성해주세요.

주제: '{query}'

시간 배분:
1. 도입부 (30초, 약 3-4개 대사)
- 인사와 주제 소개
- 청취자 흥미 유발

2. 본문 ({duration_minutes-1}분, 약 {(duration_minutes-1)*8-10}개 대사)
- 핵심 내용 단계적 설명
- 청취자 관점의 질문과 설명
- 예시와 비유를 통한 이해도 향상

3. 마무리 (30초, 약 3-4개 대사)
- 핵심 내용 정리
- 청취자 대상 마무리 인사

필수 규칙:
1. 모든 대사는 반드시 "지식: " 또는 "호기심: "으로 시작해야 함 (콜론 뒤 띄어쓰기 포함)
2. 대사는 번갈아가며 나와야 함 (같은 화자의 연속 대사 금지)
3. 실제 대사만 작성 (지시문, 괄호 설명 등 금지)
4. 빈 줄 사용 금지
5. 모든 내용은 한국어로 작성

검색 결과:
{search_results}"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        console.print(f"[red]Error generating podcast script: {str(e)}[/red]")
        return None

def generate_audio(script: str) -> Optional[bytes]:
    try:
        if not script.strip():
            print("오류: 제공된 스크립트가 비어 있습니다.")
            return None

        segments = []
        current_speaker = None
        current_text = []

        for line in script.split('\n'):
            stripped_line = line.strip()
            print(f"처리 중인 라인: {stripped_line}")

            if stripped_line.startswith('지식:'):
                if current_speaker and current_text:
                    segments.append((current_speaker, ' '.join(current_text)))
                current_speaker = "onyx"  # 권위적인 음성
                current_text = [stripped_line[3:].strip()]  # "지식:" 제거
            elif stripped_line.startswith('호기심:'):
                if current_speaker and current_text:
                    segments.append((current_speaker, ' '.join(current_text)))
                current_speaker = "nova"  # 활기찬 음성
                current_text = [stripped_line[4:].strip()]  # "호기심:" 제거
            elif stripped_line:  # 공백이 아닌 줄은 현재 스피커의 텍스트에 추가
                if current_speaker:
                    current_text.append(stripped_line)
                else:
                    print(f"[warning]현재 스피커가 없어서 해당 라인 '{stripped_line}'을 건너뜁니다.")

            else:
                # 지식, 호기심이 없거나 공백인 경우 건너뜀
                print(f"건너뜬 라인: {stripped_line}")

        # 마지막으로 남은 텍스트 세그먼트 처리
        if current_speaker and current_text:
            segments.append((current_speaker, ' '.join(current_text)))

        if not segments:
            print("오류: 세그먼트가 생성되지 않았습니다.")
            return None

        print(f"생성된 세그먼트 수: {len(segments)}")
        for i, (speaker, text) in enumerate(segments, 1):
            print(f"Segment {i} - Speaker: {speaker}, Text: {text[:50]}...")

        all_audio = []
        for i, (voice, text) in enumerate(segments, 1):
            try:
                text_parts = []
                if len(text) > 1000:
                    print(f"[yellow]Segment {i} 텍스트가 너무 깁니다. 나눕니다.[/yellow]")
                    words = text.split()
                    part = []
                    for word in words:
                        if len(' '.join(part) + ' ' + word) <= 1000:
                            part.append(word)
                        else:
                            text_parts.append(' '.join(part))
                            part = [word]
                    if part:
                        text_parts.append(' '.join(part))
                else:
                    text_parts = [text]

                # 나뉜 텍스트 각각에 대해 음성 생성
                for part in text_parts:
                    response = openai.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=part,
                        speed=1.05
                    )
                    all_audio.append(response.content)
            except Exception as e:
                print(f"[red]Segment {i} 음성 생성 실패: {str(e)}[/red]")

        # 생성된 모든 오디오 조합
        if all_audio:
            print(f"[green]총 생성된 오디오 세그먼트 수: {len(all_audio)}[/green]")
            return b''.join(all_audio)
        else:
            print("[red]오디오 세그먼트 생성 실패: 생성된 데이터 없음[/red]")
            return None

    except Exception as e:
        print(f"[red]generate_audio 오류: {str(e)}[/red]")
        return None


    except Exception as e:
        print(f"[red]generate_audio 오류: {str(e)}[/red]")
        return None
def add_background_music(audio_file: str, music_file: str, output_file: str, volume_reduction: int = -20):
    try:
        voice = AudioSegment.from_file(audio_file)

        music = AudioSegment.from_file(music_file)

        music = music - abs(volume_reduction)

        if len(music) < len(voice):
            music = music * (len(voice) // len(music) + 1)
        music = music[:len(voice)]

        combined = voice.overlay(music)

        combined.export(output_file, format="mp3")
        return output_file
    except Exception as e:
        print(f"[red]배경음악 추가 중 오류 발생: {str(e)}[/red]")
        return None