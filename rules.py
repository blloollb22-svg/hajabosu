"""번호·기한·보증 판정 규칙. 업무설명_하자보수.md §2, §4, §5를 따른다. AI는 쓰지 않는다."""
import csv
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).parent

# §4 긴급도별 조치기한(접수일 + n일)
기한일수 = {"긴급": 1, "높음": 3, "보통": 7}

임박일수 = 30  # §5 만료까지 30일 이내면 만료임박


def _날짜(글: str) -> date:
    return date.fromisoformat(글)


def 공사정보읽기(경로=None) -> list[dict]:
    경로 = Path(경로) if 경로 else BASE / "data" / "공사정보.csv"
    with open(경로, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def 접수번호(접수일: str, 순번: int) -> str:
    """HJ-접수일(YYYYMMDD)-순번(01부터). 순번은 같은 접수일 안에서 센다."""
    return f"HJ-{_날짜(접수일):%Y%m%d}-{순번:02d}"


def 조치기한(접수일: str, 긴급도: str) -> str:
    """긴급 +1일, 높음 +3일, 보통 +7일. 긴급도가 이 셋이 아니면 확인필요."""
    if 긴급도 not in 기한일수:
        return "확인필요"
    return (_날짜(접수일) + timedelta(days=기한일수[긴급도])).isoformat()


def 보증만료일(준공일: str, 보증년수: int) -> str:
    """준공일 + 하자보증기간(년). 2월 29일 준공은 해당 연도에 29일이 없으면 2월 28일로 둔다."""
    d = _날짜(준공일)
    try:
        return d.replace(year=d.year + 보증년수).isoformat()
    except ValueError:
        return d.replace(year=d.year + 보증년수, day=28).isoformat()


def _후보공종(공종: str) -> list[str] | None:
    """'설비/타일' → ['설비','타일']. 공종 미정이면 None."""
    if not 공종 or 공종 == "확인필요":
        return None
    return [x.strip() for x in 공종.split("/")]


def 후보공사(위치: str, 공종: str, 공사목록: list[dict]) -> list[dict]:
    """위치가 같고 공종이 맞는 공사들. 공종이 미정이면 위치만 같은 공사를 모두 돌려준다."""
    공종들 = _후보공종(공종)
    return [
        c for c in 공사목록
        if c["위치"] == 위치 and (공종들 is None or c["공종"] in 공종들)
    ]


def _임박(접수일: str, 만료일: str) -> bool:
    남은일 = (_날짜(만료일) - _날짜(접수일)).days
    return 0 <= 남은일 <= 임박일수


def 보증판정(접수일: str, 위치: str, 공종: str, 공사목록: list[dict]) -> dict:
    """위치와 공종이 모두 같은 공사를 찾아 보증을 판정한다. 기준은 오늘이 아니라 접수일.

    돌려주는 칸: 공사번호, 시공업체, 준공일, 보증만료일, 보증판정, 책임구분, 비고
    """
    공종들 = _후보공종(공종)
    후보 = 후보공사(위치, 공종, 공사목록)
    결과 = {"공사번호": "", "시공업체": "", "준공일": "", "보증만료일": "",
            "보증판정": "확인필요", "책임구분": "확인필요", "비고": ""}

    # 공종이 하나로 정해졌고 맞는 공사가 1건일 때만 판정한다.
    if 공종들 is not None and len(공종들) == 1 and len(후보) == 1:
        c = 후보[0]
        만료 = 보증만료일(c["준공일"], int(c["하자보증기간(년)"]))
        결과.update(공사번호=c["공사번호"], 시공업체=c["시공업체"],
                    준공일=c["준공일"], 보증만료일=만료)
        if _날짜(접수일) <= _날짜(만료):
            결과.update(보증판정="보증내", 책임구분="시공업체")
            if _임박(접수일, 만료):
                결과["비고"] = "만료임박"
        else:
            결과.update(보증판정="보증만료", 책임구분="자체보수")
        return 결과

    # 확인필요: 후보 공사가 만료임박이면 비고에 함께 적는다.
    임박후보 = []
    for c in 후보:
        만료 = 보증만료일(c["준공일"], int(c["하자보증기간(년)"]))
        if _임박(접수일, 만료):
            임박후보.append(f'{c["공사번호"]}({만료})')
    if 임박후보:
        결과["비고"] = "만료임박 후보: " + ", ".join(임박후보)
    return 결과
