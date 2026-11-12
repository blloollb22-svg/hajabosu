"""저장은 이 파일에서만 한다. 연결 정보는 .env의 DATABASE_URL(웹 배포는 Streamlit Secrets)."""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import (CheckConstraint, Column, Date, DateTime, Integer, MetaData, Table,
                        Text, create_engine, func, select, text, update)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url

load_dotenv(Path(__file__).parent / ".env")

# 업무설명 §2 하자대장 항목 순서 (data/하자대장.csv와 같은 열)
칸 = ["접수번호", "접수일", "원문파일", "위치", "공종", "하자내용", "긴급도", "조치기한",
     "공사번호", "시공업체", "준공일", "보증만료일", "보증판정", "책임구분", "상태", "비고"]

메타 = MetaData()

접수 = Table(
    "접수", 메타,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("접수일시", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("발견일", Date),
    Column("접수자", Text),
    Column("부서", Text),
    Column("위치", Text),
    Column("내용", Text),
    Column("처리상태", Text, nullable=False, server_default="미처리"),
    Column("접수번호", Text),
    CheckConstraint("\"처리상태\" IN ('미처리', '처리완료')", name="접수_처리상태_확인"),
)

하자대장 = Table(
    "하자대장", 메타,
    *[Column(c, Text, primary_key=(c == "접수번호"), nullable=False, server_default="") for c in 칸],
)

_엔진 = None
_준비됨 = False


def _가리기(메시지: str) -> str:
    """오류 글에 연결 주소나 비밀번호가 섞여 있으면 지운다."""
    주소 = os.getenv("DATABASE_URL", "")
    비번 = ""
    try:
        비번 = make_url(주소).password or ""
    except Exception:
        pass
    for 비밀 in (주소, 비번):
        if 비밀:
            메시지 = 메시지.replace(비밀, "***")
    return 메시지


def 엔진():
    global _엔진
    if _엔진 is None:
        주소 = os.getenv("DATABASE_URL", "").strip()
        if not 주소:
            raise RuntimeError(".env에 DATABASE_URL이 없습니다.")
        if 주소.startswith("postgres://"):
            주소 = "postgresql://" + 주소[len("postgres://"):]
        if 주소.startswith("postgresql://"):
            주소 = "postgresql+psycopg://" + 주소[len("postgresql://"):]  # psycopg 3용
        _엔진 = create_engine(주소, pool_pre_ping=True)
    return _엔진


def 초기화():
    """테이블 2개가 없으면 만들고, 두 테이블 모두 RLS(행 수준 보안)를 켠다. 여러 번 불러도 된다."""
    global _준비됨
    if _준비됨:
        return
    try:
        with 엔진().begin() as 연결:
            메타.create_all(연결)
            for 표 in (접수, 하자대장):
                연결.execute(text(f'ALTER TABLE "{표.name}" ENABLE ROW LEVEL SECURITY'))
    except Exception as e:
        raise RuntimeError(f"DB 연결·초기화 실패: {type(e).__name__}: {_가리기(str(e))}") from None
    _준비됨 = True


def 대장저장(행들: list[dict]) -> int:
    """하자대장에 넣는다. 접수번호가 이미 있으면 그 줄을 덮어쓴다."""
    if not 행들:
        return 0
    초기화()
    값들 = [{c: str(행.get(c, "") or "") for c in 칸} for 행 in 행들]
    문장 = insert(하자대장).values(값들)
    문장 = 문장.on_conflict_do_update(
        index_elements=["접수번호"],
        set_={c: 문장.excluded[c] for c in 칸 if c != "접수번호"},
    )
    with 엔진().begin() as 연결:
        연결.execute(문장)
    return len(값들)


def 접수저장(발견일, 접수자: str, 부서: str, 위치: str, 내용: str) -> int:
    """접수 화면에서 들어온 한 건을 저장하고 id를 돌려준다. 처리상태는 미처리, 접수번호는 비워 둔다."""
    초기화()
    문장 = insert(접수).values(발견일=발견일, 접수자=접수자, 부서=부서, 위치=위치, 내용=내용).returning(접수.c.id)
    with 엔진().begin() as 연결:
        return 연결.execute(문장).scalar_one()


def 미처리접수읽기() -> list[dict]:
    """처리상태가 미처리인 접수를 들어온 순서(id)로 읽는다."""
    초기화()
    문장 = select(접수).where(접수.c.처리상태 == "미처리").order_by(접수.c.id)
    with 엔진().connect() as 연결:
        return [dict(행._mapping) for 행 in 연결.execute(문장)]


def 접수읽기(접수id: int) -> dict | None:
    초기화()
    with 엔진().connect() as 연결:
        행 = 연결.execute(select(접수).where(접수.c.id == 접수id)).first()
    return dict(행._mapping) if 행 else None


def 접수처리완료(접수id: int, 접수번호: str) -> None:
    """접수에 접수번호를 적고 처리완료로 바꾼다."""
    초기화()
    with 엔진().begin() as 연결:
        연결.execute(update(접수).where(접수.c.id == 접수id).values(접수번호=접수번호, 처리상태="처리완료"))


def 미처리건수() -> int:
    초기화()
    with 엔진().connect() as 연결:
        return 연결.execute(
            select(func.count()).select_from(접수).where(접수.c.처리상태 == "미처리")
        ).scalar_one()


def 대장읽기() -> pd.DataFrame:
    """하자대장 전체를 접수번호 순서로 읽는다. 모든 칸은 글자다."""
    초기화()
    with 엔진().connect() as 연결:
        df = pd.read_sql(select(하자대장).order_by(하자대장.c.접수번호), 연결)
    return df[칸].fillna("").astype(str)


def 건수() -> dict:
    """테이블별 건수."""
    초기화()
    with 엔진().connect() as 연결:
        return {표.name: 연결.execute(select(func.count()).select_from(표)).scalar_one()
                for 표 in (접수, 하자대장)}
