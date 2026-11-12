"""AI 호출은 이 파일에서만 한다. 키와 모델은 .env에서 읽는다."""
import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

KEYS = ["접수일", "위치", "공종", "하자내용", "긴급도"]


def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(".env에 ANTHROPIC_API_KEY가 없습니다.")
    return anthropic.Anthropic(api_key=key)


def 접수정리(원문: str) -> dict:
    """접수 원문 1건을 지침/접수정리.md대로 정리해 5개 칸의 dict로 돌려준다."""
    지침 = (BASE / "지침" / "접수정리.md").read_text(encoding="utf-8")
    응답 = _client().messages.create(
        model=os.getenv("MODEL", "claude-haiku-5-5"),
        max_tokens=4000,  # 모델이 글자 수를 세며 생각하는 데도 토큰을 쓴다
        system=지침,
        messages=[{"role": "user", "content": 원문}],
    )
    # 모델이 생각 블록을 함께 보낼 수 있어서 글 블록만 모은다.
    글 = "".join(b.text for b in 응답.content if b.type == "text").strip()
    if not 글:
        raise ValueError(f"AI가 답을 비워 보냈습니다(종료 사유: {응답.stop_reason}). max_tokens를 확인하세요.")
    # 모델이 ```json 표시를 붙여도 JSON 부분만 꺼낸다.
    글 = 글[글.find("{"): 글.rfind("}") + 1]
    결과 = json.loads(글)
    빠진칸 = [k for k in KEYS if k not in 결과]
    if 빠진칸:
        raise ValueError(f"AI 답에 빠진 칸: {빠진칸}")
    return {k: 결과[k] for k in KEYS}
