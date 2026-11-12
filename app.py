"""담당자 화면: 접수 원문이 하자대장 한 줄이 되기까지의 과정을 보여준다."""
import pandas as pd
import streamlit as st

import rules
import run

st.set_page_config(page_title="하자보수 대장", page_icon=":material/build:", layout="wide")

AI = ":blue-badge[AI]"
CODE = ":green-badge[코드]"
HUMAN = ":orange-badge[사람]"


@st.cache_data(ttl="1m")
def 대장읽기() -> pd.DataFrame:
    return rules.대장읽기()


@st.cache_data
def 공사정보() -> list[dict]:
    return rules.공사정보읽기()


def 원문읽기(파일명: str) -> str:
    return (run.입력폴더 / 파일명).read_text(encoding="utf-8")


st.title("하자보수 대장")
st.caption("접수 원문을 AI가 읽고, 코드가 번호·기한·보증을 계산하고, 사람이 확인필요 건을 정합니다.")

# ---- 처리 실행 ----
with st.container(horizontal=True, vertical_alignment="center"):
    다시처리 = st.button(
        "접수함 처리",
        icon=":material/play_arrow:",
        type="primary",
        help="접수함의 원문을 AI로 읽어 DB 하자대장에 저장합니다. AI를 건수만큼 호출하고, 같은 접수번호는 덮어씁니다.",
    )
    st.caption(f"원문 {len(list(run.입력폴더.glob('*.txt')))}건 · 접수함 폴더 기준")

if 다시처리:
    with st.spinner("접수 원문을 처리하는 중입니다. AI를 건수만큼 호출합니다."):
        try:
            run.처리()
        except Exception as e:
            st.error(f"처리 중 오류가 났습니다: {e}", icon=":material/error:")
    대장읽기.clear()

try:
    df = 대장읽기()
except Exception as e:
    st.error(f"하자대장을 읽지 못했습니다: {e}", icon=":material/error:")
    st.stop()

if df.empty:
    st.info("아직 하자대장이 없습니다. '접수함 처리'를 눌러 만들어 주세요.", icon=":material/info:")
    st.stop()

공사목록 = 공사정보()

# ---- 요약 ----
cols = st.columns(5)
cols[0].metric("전체", f"{len(df)}건", border=True, height="stretch")
cols[1].metric("긴급", f"{(df['긴급도'] == '긴급').sum()}건", border=True, height="stretch")
cols[2].metric("시공업체 요청", f"{(df['책임구분'] == '시공업체').sum()}건", border=True, height="stretch")
cols[3].metric("자체보수", f"{(df['책임구분'] == '자체보수').sum()}건", border=True, height="stretch")
cols[4].metric("확인필요", f"{(df['책임구분'] == '확인필요').sum()}건", border=True, height="stretch")

# ---- 대장 ----
st.subheader("하자대장")
st.caption("한 줄을 고르면 아래에 그 건의 처리 과정이 나옵니다.")
보일칸 = ["접수번호", "접수일", "위치", "공종", "하자내용", "긴급도", "조치기한", "보증판정", "책임구분", "상태", "비고"]
선택 = st.dataframe(
    df[보일칸],
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="대장표",
    alt="하자대장 목록. 한 줄을 선택하면 처리 과정이 아래에 표시됩니다.",
)
고른줄 = 선택.selection.rows[0] if 선택.selection.rows else 0
r = df.iloc[고른줄]

# ---- 처리 과정 ----
st.subheader(f"처리 과정 · {r['접수번호']}")
st.caption(f"원문 파일: {r['원문파일']}" + ("" if 선택.selection.rows else " (선택하지 않아 첫 건을 보여줍니다)"))

c1, c2, c3, c4 = st.columns(4)

with c1.container(border=True, height="stretch"):
    st.markdown("**① 접수 원문**")
    st.text(원문읽기(r["원문파일"]))

with c2.container(border=True, height="stretch"):
    st.markdown(f"**② 읽고 판단** {AI}")
    st.caption("원문을 읽고 5개 칸만 정합니다.")
    글자수 = len(r["하자내용"])
    st.table(
        {
            "접수일": r["접수일"],
            "위치": r["위치"],
            "공종": r["공종"],
            "긴급도": r["긴급도"],
            "하자내용": f"{r['하자내용']} ({글자수}자)",
        },
        border="horizontal",
    )
    if 글자수 > 40:
        st.warning("하자내용이 40자를 넘었습니다.", icon=":material/warning:")

with c3.container(border=True, height="stretch"):
    st.markdown(f"**③ 계산과 판정** {CODE}")
    st.caption("번호·기한·보증은 정해진 규칙으로 계산합니다.")
    일수 = rules.기한일수.get(r["긴급도"])
    기한근거 = f"{r['긴급도']} → 접수일 +{일수}일" if 일수 else "긴급도를 알 수 없음"
    st.markdown(f"**접수번호** `{r['접수번호']}`")
    st.markdown(f"**조치기한** {r['조치기한']}  \n:gray[{기한근거}]")

    후보 = rules.후보공사(r["위치"], r["공종"], 공사목록)
    if r["공사번호"]:
        st.markdown(f"**공사** {r['공사번호']} · {r['시공업체']}")
        st.markdown(f"**보증만료일** {r['보증만료일']}  \n:gray[준공일 {r['준공일']} + 보증기간]")
        if r["보증판정"] == "보증내":
            근거 = f"접수일 {r['접수일']} ≤ 만료일 {r['보증만료일']}"
        else:
            근거 = f"접수일 {r['접수일']} > 만료일 {r['보증만료일']}"
        st.markdown(f"**판정** {r['보증판정']} → {r['책임구분']}  \n:gray[{근거}]")
    else:
        if "/" in r["공종"] or r["공종"] == "확인필요":
            사유 = "공종이 하나로 정해지지 않았습니다."
        elif len(후보) == 0:
            사유 = "위치와 공종이 같은 공사가 없습니다."
        else:
            사유 = f"맞는 공사가 {len(후보)}건입니다."
        st.markdown(f"**판정** 확인필요  \n:gray[{사유}]")
    if r["비고"]:
        st.markdown(f"**비고** :red[{r['비고']}]")
    st.markdown(f"**상태** {r['상태']}")

with c4.container(border=True, height="stretch"):
    st.markdown(f"**④ 사람이 확인** {HUMAN}")
    if r["상태"] == "확인필요":
        st.warning("담당자가 현장을 보고 정해야 합니다.", icon=":material/person_alert:")
        if 후보:
            st.caption("후보 공사")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "공사번호": c["공사번호"],
                            "공종": c["공종"],
                            "시공업체": c["시공업체"],
                            "보증만료일": rules.보증만료일(c["준공일"], int(c["하자보증기간(년)"])),
                        }
                        for c in 후보
                    ]
                ),
                hide_index=True,
                alt="확인필요 건의 후보 공사 목록",
            )
    else:
        st.success("AI 판단(공종·긴급도)이 맞는지만 확인하면 됩니다.", icon=":material/task_alt:")
    st.caption("조치요청(공문 발송)은 사람이 정합니다.")
