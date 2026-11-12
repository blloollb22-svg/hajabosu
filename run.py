"""접수함 폴더와 DB 접수(미처리) 건을 처리해 DB 하자대장에 저장한다."""
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import ai
import db
import rules

BASE = Path(__file__).parent
입력폴더 = BASE / "data" / "접수함"


def 파일명날짜(파일명: str) -> str:
    """파일명 `01_20261102_...`의 날짜 부분을 YYYY-MM-DD로 바꾼다."""
    s = 파일명.split("_")[1]
    return date(int(s[:4]), int(s[4:6]), int(s[6:8])).isoformat()


def DB원문키(접수id: int) -> str:
    """DB 접수를 하자대장의 원문파일 칸에 적는 이름."""
    return f"DB:접수#{접수id}"


def 접수원문(접: dict) -> str:
    """접수 화면에서 들어온 한 건을 AI에게 줄 글로 만든다."""
    return "\n".join([
        "[접수 화면 입력]",
        f"발견일: {접.get('발견일') or ''}",
        f"접수자: {접.get('접수자') or ''}",
        f"부서: {접.get('부서') or ''}",
        f"위치: {접.get('위치') or ''}",
        f"내용: {접.get('내용') or ''}",
    ])


class 번호부:
    """접수번호를 겹치지 않게 준다. 이미 대장에 있는 원문은 같은 번호를 다시 쓴다."""

    def __init__(self, 기존: dict[str, str]):
        self.원문별 = dict(기존)
        self.최대 = defaultdict(int)  # YYYYMMDD → 가장 큰 순번
        for 번호 in 기존.values():
            try:
                _, ymd, 순번 = 번호.split("-")
                self.최대[ymd] = max(self.최대[ymd], int(순번))
            except ValueError:
                pass

    def 받기(self, 원문키: str, 접수일: str) -> str:
        ymd = 접수일.replace("-", "")
        이전 = self.원문별.get(원문키)
        if 이전 and 이전.split("-")[1] == ymd:
            return 이전
        self.최대[ymd] += 1
        번호 = rules.접수번호(접수일, self.최대[ymd])
        self.원문별[원문키] = 번호
        return 번호


def 처리(폴더접수: bool = True, DB접수: bool = True):
    공사목록 = rules.공사정보읽기()
    기존 = rules.대장읽기()
    번호들 = 번호부(dict(zip(기존["원문파일"], 기존["접수번호"])))

    # 할 일: (원문키, 원문, 접수일 지정값, DB 접수 id)
    할일 = []
    if 폴더접수:
        for 파일 in sorted(입력폴더.glob("*.txt")):
            할일.append((파일.name, 파일.read_text(encoding="utf-8"), None, None))
    if DB접수:
        for 접 in db.미처리접수읽기():
            발견일 = 접["발견일"] or 접["접수일시"].date()  # 발견일을 접수일로 쓴다
            할일.append((DB원문키(접["id"]), 접수원문(접), 발견일.isoformat(), 접["id"]))

    행들, 완료 = [], {}
    for 원문키, 원문, 지정일, 접수id in 할일:
        try:
            a = ai.접수정리(원문)
        except Exception as e:
            # 한 건이 실패해도 나머지는 계속한다. DB 접수는 미처리로 남아 다음에 다시 처리된다.
            print(f"경고: {원문키} 처리 실패({type(e).__name__}) - 건너뜀", file=sys.stderr)
            continue

        if 지정일:
            접수일 = 지정일
        else:
            # 접수일: 원문 날짜, 없으면 파일명 날짜
            접수일 = a["접수일"]
            try:
                date.fromisoformat(접수일)
            except (TypeError, ValueError):
                접수일 = 파일명날짜(원문키)

        번호 = 번호들.받기(원문키, 접수일)
        판정 = rules.보증판정(접수일, a["위치"], a["공종"], 공사목록)
        행 = {
            "접수번호": 번호,
            "접수일": 접수일,
            "원문파일": 원문키,
            "위치": a["위치"],
            "공종": a["공종"],
            "하자내용": a["하자내용"],
            "긴급도": a["긴급도"],
            "조치기한": rules.조치기한(접수일, a["긴급도"]),
            **판정,
            "상태": "확인필요" if 판정["보증판정"] == "확인필요" else "판정완료",
        }
        행들.append(행)
        if 접수id is not None:
            완료[접수id] = 번호
        if len(a["하자내용"]) > 40:
            print(f'경고: {원문키} 하자내용이 40자를 넘음({len(a["하자내용"])}자)', file=sys.stderr)
        print(행["접수번호"], 행["위치"], 행["공종"], 행["긴급도"], 행["보증판정"], 행["비고"])

    if 행들:
        rules.대장저장(행들)
        for 접수id, 번호 in 완료.items():  # 대장에 저장된 뒤에 접수를 처리완료로 바꾼다
            db.접수처리완료(접수id, 번호)
    print(f"{len(행들)}건 저장: DB 하자대장 (DB 접수 {len(완료)}건 처리완료)")
    return 행들


if __name__ == "__main__":
    처리()
