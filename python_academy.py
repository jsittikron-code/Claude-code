"""Python Academy — ระบบเรียนและฝึกเขียน Python สำหรับงานโรงงาน
================================================================

เรียน → ฝึกเขียนโค้ด → ระบบรันจริงและตรวจให้ทันที → วัดผล → ทบทวนตามกำหนด

จุดต่างจากคอร์สทั่วไปคือ **ตัวรันโค้ดจริง** (pyacad/runner.py)
ผู้เรียนเขียนโค้ดแล้วระบบรันในโปรเซสแยกพร้อมชุดทดสอบหลายเคส
เขียนวิธีไหนก็ได้ถ้าผลถูก — และมี "ตัวไล่โค้ดทีละบรรทัด" ที่แสดงค่าตัวแปรทุกก้าว
ซึ่งเป็นเครื่องมือหาบั๊กที่ได้ผลที่สุดสำหรับผู้เริ่มต้น

รัน: python -m streamlit run python_academy.py --server.port 8509
(หรือดับเบิลคลิก run_python.bat)
"""

import streamlit as st

st.set_page_config(
    page_title="Python Academy",
    page_icon=":material/code:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from pyacad import ui  # noqa: E402  — ต้องมาหลัง set_page_config

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
    auth.check_login("Python Academy")
    st.session_state["py_user"] = auth.current_user()
else:
    st.session_state.setdefault("py_user", "guest")

pages = {
    "": [
        st.Page("py_pages/home.py", title="หน้าหลัก", icon=":material/home:", default=True),
    ],
    "เรียน": [
        st.Page("py_pages/learn.py", title="หลักสูตร", icon=":material/menu_book:"),
        st.Page("py_pages/reference.py", title="คู่มืออ้างอิง", icon=":material/library_books:"),
    ],
    "ฝึก": [
        st.Page("py_pages/code_lab.py", title="ฝึกเขียนโค้ด", icon=":material/code:"),
        st.Page("py_pages/playground.py", title="สนามซ้อม", icon=":material/science:"),
        st.Page("py_pages/tracer.py", title="ไล่โค้ดทีละบรรทัด", icon=":material/step:"),
    ],
    "วัดผล": [
        st.Page("py_pages/quiz.py", title="แบบทดสอบ", icon=":material/quiz:"),
        st.Page("py_pages/exam.py", title="ข้อสอบรวม", icon=":material/military_tech:"),
        st.Page("py_pages/progress_page.py", title="ความก้าวหน้า", icon=":material/trending_up:"),
    ],
    "ลงมือทำจริง": [
        st.Page("py_pages/datasets.py", title="ชุดข้อมูลฝึก", icon=":material/download:"),
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
                st.session_state["py_user"] = name.strip()
                st.rerun()
    elif auth is not None:
        auth.sidebar_user_box()

page.run()
