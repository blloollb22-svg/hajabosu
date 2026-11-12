"""접수 화면: 매장·현장에서 하자를 접수한다. 웹에 배포하며 접수만 저장하고, 저장된 내용은 보여주지 않는다."""
import os
from datetime import date

import streamlit as st

# 웹 배포에서는 .env가 없으므로 Streamlit Secrets의 DATABASE_URL을 쓴다.
try:
    if not os.getenv("DATABASE_URL") and "DATABASE_URL" in st.secrets:
        os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]
except Exception:
    pass

import db  # noqa: E402  (환경변수를 먼저 채운 뒤 불러온다)

st.set_page_config(page_title="하자 접수", page_icon=":material/edit_note:")

st.title("하자 접수")
st.caption("발견한 하자를 적어 주세요. 시설관리팀이 확인해서 처리합니다.")

with st.form("접수", clear_on_submit=True, border=True):
    발견일 = st.date_input("발견일", value=date.today(), max_value=date.today())
    접수자 = st.text_input("접수자", max_chars=50, placeholder="이름")
    부서 = st.text_input("부서", max_chars=50, placeholder="예: 3F 패션관 운영파트")
    위치 = st.text_input("위치", max_chars=100, placeholder="예: B1 푸드코트, 2F 화장실")
    내용 = st.text_area(
        "내용",
        max_chars=1000,
        height=150,
        placeholder="어디에서 무엇이 어떻게 되어 있는지, 이미 한 조치가 있으면 함께 적어 주세요.",
    )
    제출 = st.form_submit_button("접수하기", icon=":material/send:", type="primary")

if 제출:
    빠진 = [이름 for 이름, 값 in (("접수자", 접수자), ("위치", 위치), ("내용", 내용)) if not 값.strip()]
    if 빠진:
        st.error(f"입력하지 않은 칸이 있습니다: {', '.join(빠진)}", icon=":material/error:")
    else:
        try:
            접수id = db.접수저장(발견일, 접수자.strip(), 부서.strip(), 위치.strip(), 내용.strip())
        except Exception as e:
            # 화면에는 원인을 보이지 않는다(연결 정보가 섞일 수 있음). 서버 로그에만 남긴다.
            print(f"접수 저장 실패: {type(e).__name__}", flush=True)
            st.error("접수를 저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요.", icon=":material/error:")
        else:
            st.success(f"접수되었습니다. (접수 {접수id}번)", icon=":material/task_alt:")
