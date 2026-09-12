"""Power BI Academy — ระบบเรียนและฝึกทักษะ Power BI แบบครบวงจร
================================================================

เรียน → ฝึก → ตรวจคำตอบอัตโนมัติ → วัดผล → ทบทวนตามกำหนด

จุดต่างจากคอร์สทั่วไปคือมี **เครื่องจำลอง DAX** อยู่ในตัว (pbi/dax_engine.py)
ผู้เรียนจึงเขียนสูตรแล้วรู้ทันทีว่าถูกหรือผิด โดยระบบจะรันสูตรของผู้เรียนเทียบกับเฉลย
ภายใต้ filter context หลายชุด — สูตรที่ใช้ CALCULATE หรือ ALL ผิดจะถูกจับได้

รัน: python -m streamlit run powerbi_academy.py --server.port 8508
(หรือดับเบิลคลิก run_powerbi.bat)
"""

import streamlit as st

st.set_page_config(
    page_title="Power BI Academy",
    page_icon=":material/school:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from pbi import ui  # noqa: E402  — ต้องมาหลัง set_page_config

# ---------------------------------------------------------------------------
# ระบุตัวผู้เรียน — ใช้ระบบล็อกอินกลางของฝ่ายถ้าตั้งค่าไว้ ไม่งั้นให้พิมพ์ชื่อเอง
# (ความก้าวหน้าถูกเก็บแยกไฟล์ต่อคน จึงต้องรู้ว่าใครกำลังเรียนอยู่)
# ---------------------------------------------------------------------------
try:
    import auth
    _creds, _ = auth._load_credentials()
except Exception:
    auth, _creds = None, {}

if _creds:
    auth.check_login("Power BI Academy")
    st.session_state["pbi_user"] = auth.current_user()
else:
    st.session_state.setdefault("pbi_user", "guest")

st.session_state.setdefault("dax_scratch", "SUM( Production[GoodQty] )")

pages = {
    "": [
        st.Page("pbi_pages/home.py", title="หน้าหลัก", icon=":material/home:", default=True),
    ],
    "เรียน": [
        st.Page("pbi_pages/learn.py", title="หลักสูตร", icon=":material/menu_book:"),
        st.Page("pbi_pages/reference.py", title="คู่มืออ้างอิง", icon=":material/menu_book:"),
    ],
    "ฝึก": [
        st.Page("pbi_pages/dax_lab.py", title="ฝึกเขียน DAX", icon=":material/function:"),
        st.Page("pbi_pages/playground.py", title="สนามซ้อม DAX", icon=":material/science:"),
        st.Page("pbi_pages/pq_lab.py", title="ฝึก Power Query", icon=":material/cleaning_services:"),
    ],
    "วัดผล": [
        st.Page("pbi_pages/quiz.py", title="แบบทดสอบ", icon=":material/quiz:"),
        st.Page("pbi_pages/exam.py", title="ข้อสอบจำลอง PL-300", icon=":material/military_tech:"),
        st.Page("pbi_pages/progress_page.py", title="ความก้าวหน้า", icon=":material/trending_up:"),
    ],
    "ลงมือทำจริง": [
        st.Page("pbi_pages/datasets.py", title="ชุดข้อมูลฝึก", icon=":material/download:"),
    ],
}

page = st.navigation(pages, position="sidebar")

with st.sidebar:
    ui.xp_header()
    if not _creds:
        with st.popover("เปลี่ยนผู้เรียน", icon=":material/switch_account:", width="stretch"):
            name = st.text_input("ชื่อผู้เรียน", value=ui.learner(),
                                 help="ความก้าวหน้าถูกเก็บแยกตามชื่อนี้")
            if st.button("เปลี่ยน", width="stretch") and name.strip():
                st.session_state["pbi_user"] = name.strip()
                st.rerun()
    elif auth is not None:
        auth.sidebar_user_box()

page.run()
