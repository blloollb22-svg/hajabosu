"""입력 폴더(data/접수함)를 일괄 처리해 하자대장.csv로 저장한다."""
import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import ai
import rules

BASE = Path(__file__).parent
입력폴더 = BASE / "data" / "접수함"
출력파일 = BASE / "data" / "하자대장.csv"

# 업무설명 §2 하자대장 항목 순서
칸 = ["접수번호", "접수일", "원문파일", "위치", "공종", "하자내용", "긴급도", "조치기한",
     "공사번호", "시공업체", "준공일", "보증만료일", "보증판정", "책임구분", "상태", "비고"]


def 파일명날짜(파일명: str) -> str:
    """파일명 `01_20261102_...`의 날짜 부분을 YYYY-MM-DD로 바꾼다."""
    s = 파일명.split("_")[1]
    return date(int(s[:4]), int(s[4:6]), int(s[6:8])).isoformat()


def 처리():
    공사목록 = rules.공사정보읽기()
    순번 = defaultdict(int)
    행들 = []
    for 파일 in sorted(입력폴더.glob("*.txt")):
        원문 = 파일.read_text(encoding="utf-8")
        a = ai.접수정리(원문)

        # 접수일: 원문 날짜, 없으면 파일명 날짜
        접수일 = a["접수일"]
        try:
            date.fromisoformat(접수일)
        except (TypeError, ValueError):
            접수일 = 파일명날짜(파일.name)

        순번[접수일] += 1
        판정 = rules.보증판정(접수일, a["위치"], a["공종"], 공사목록)
        행 = {
            "접수번호": rules.접수번호(접수일, 순번[접수일]),
            "접수일": 접수일,
            "원문파일": 파일.name,
            "위치": a["위치"],
            "공종": a["공종"],
            "하자내용": a["하자내용"],
            "긴급도": a["긴급도"],
            "조치기한": rules.조치기한(접수일, a["긴급도"]),
            **판정,
            "상태": "확인필요" if 판정["보증판정"] == "확인필요" else "판정완료",
        }
        행들.append(행)
        if len(a["하자내용"]) > 40:
            print(f'경고: {파일.name} 하자내용이 40자를 넘음({len(a["하자내용"])}자)', file=sys.stderr)
        print(행["접수번호"], 행["위치"], 행["공종"], 행["긴급도"], 행["보증판정"], 행["비고"])

    with open(출력파일, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=칸)
        w.writeheader()
        w.writerows(행들)
    print(f"{len(행들)}건 저장: {출력파일}")
    return 행들


if __name__ == "__main__":
    처리()
