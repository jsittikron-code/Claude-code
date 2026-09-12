"""ตัวช่วยที่ใช้ร่วมกันทุกหน้าของ Python Academy — สถานะผู้เรียน และชิ้นส่วน UI ที่ใช้ซ้ำ"""

from __future__ import annotations

import streamlit as st

from pyacad import progress as pg


# ---------------------------------------------------------------------------
# ผู้เรียนและความก้าวหน้า
# ---------------------------------------------------------------------------
def learner() -> str:
    return st.session_state.get("py_user", "guest")


def data() -> dict:
    """ความก้าวหน้าของผู้เรียนคนปัจจุบัน (โหลดใหม่เมื่อสลับผู้ใช้)"""
    if st.session_state.get("py_progress_user") != learner():
        st.session_state["py_progress"] = pg.touch(pg.load(learner()))
        st.session_state["py_progress_user"] = learner()
        pg.save(st.session_state["py_progress"])
    return st.session_state["py_progress"]


def save() -> None:
    try:
        pg.save(data())
    except OSError as e:
        st.warning(f"บันทึกความก้าวหน้าไม่สำเร็จ: {e}")


def done_lessons() -> set[str]:
    return set(data().get("lessons", {}))


def solved_code() -> set[str]:
    return pg.solved_ids(data())


# ---------------------------------------------------------------------------
# ชิ้นส่วน UI ที่ใช้ซ้ำ
# ---------------------------------------------------------------------------
def xp_header() -> None:
    """แถบ XP + ระดับ + จำนวนวันติดต่อกัน สำหรับวางในแถบข้าง"""
    d = data()
    xp = d.get("xp", 0)
    name, floor, nxt = pg.level_of(xp)
    span = max(1, nxt - floor)
    ratio = 1.0 if nxt == floor else min(1.0, (xp - floor) / span)

    st.caption(f"👤 {learner()}")
    st.progress(ratio, text=f"{name} · {xp:,} XP")
    if nxt > floor:
        st.caption(f"อีก {nxt - xp:,} XP จะขึ้นระดับถัดไป")
    streak = d.get("streak", 0)
    if streak > 1:
        st.caption(f"🔥 เข้าเรียนติดต่อกัน {streak} วัน")


def stat_row(items: list[tuple[str, str, str | None]]) -> None:
    """แถวการ์ดตัวเลขสรุป — [(ป้าย, ค่า, คำอธิบายเมื่อชี้)]"""
    with st.container(horizontal=True):
        for label, value, helptext in items:
            with st.container(border=True):
                st.metric(label, value, help=helptext)


def code_box(label: str, key: str, default: str = "", height: int = 260,
             help: str | None = None) -> str:
    """ช่องเขียนโค้ด — ใช้ text_area เพื่อให้พิมพ์ย่อหน้าและวางโค้ดยาวได้สะดวก"""
    if key not in st.session_state:
        st.session_state[key] = default
    return st.text_area(label, key=key, height=height, help=help)


def show_output(res: dict) -> None:
    """แสดงผลการรันหนึ่งครั้งให้อ่านง่าย — แยกสิ่งที่พิมพ์ออกจากข้อความผิดพลาด"""
    if res.get("timeout"):
        st.error("โค้ดทำงานนานเกินกำหนดจนถูกหยุด — มักเกิดจากลูปที่เงื่อนไขไม่มีวันเป็นเท็จ "
                 "หรือ `while` ที่ลืมเปลี่ยนค่าตัวแปรควบคุม", icon=":material/timer_off:")
    if res.get("stdout"):
        st.markdown("**ผลลัพธ์ที่พิมพ์ออกมา**")
        st.code(res["stdout"], language="text")
    elif not res.get("stderr") and not res.get("timeout"):
        st.caption("โค้ดทำงานจบโดยไม่พิมพ์อะไรออกมา")
    if res.get("stderr"):
        st.markdown("**ข้อผิดพลาด**")
        st.code(res["stderr"], language="text")
        st.caption(explain_error(res["stderr"]))
    if res.get("seconds") is not None and not res.get("timeout"):
        st.caption(f"ใช้เวลา {res['seconds']:.3f} วินาที")


# ---------------------------------------------------------------------------
# แปลข้อความผิดพลาดยอดฮิตเป็นภาษาคน
# ---------------------------------------------------------------------------
ERROR_HINTS: list[tuple[str, str]] = [
    ("SyntaxError", "ไวยากรณ์ผิด — มักลืมเครื่องหมาย : ท้ายบรรทัด if/for/def หรือวงเล็บไม่ครบ"),
    ("IndentationError", "การย่อหน้าไม่ตรงกัน — ในหนึ่งบล็อกต้องย่อหน้าเท่ากันทุกบรรทัด (แนะนำเว้น 4 ช่อง)"),
    ("TabError", "ปนกันระหว่าง Tab กับ Space — เลือกอย่างใดอย่างหนึ่ง แนะนำ Space 4 ช่อง"),
    ("NameError", "เรียกใช้ชื่อที่ยังไม่มี — สะกดผิด หรือใช้ตัวแปรก่อนกำหนดค่า"),
    ("TypeError", "เอาชนิดข้อมูลที่เข้ากันไม่ได้มาใช้ด้วยกัน เช่น เอาข้อความ + ตัวเลข หรือส่งอาร์กิวเมนต์ผิดจำนวน"),
    ("ValueError", "ชนิดถูกแต่ค่าใช้ไม่ได้ เช่น int('abc') แปลงไม่ได้"),
    ("IndexError", "อ้างตำแหน่งเกินขอบเขตของ list — จำไว้ว่าตัวแรกคือ 0 และตัวสุดท้ายคือ len(x)-1"),
    ("KeyError", "คีย์นี้ไม่มีใน dict — ตรวจการสะกด หรือใช้ .get(key, ค่าเริ่มต้น)"),
    ("ZeroDivisionError", "หารด้วยศูนย์ — ต้องตรวจตัวหารก่อนหาร (เช่น เวลาเดินเครื่องเป็น 0)"),
    ("AttributeError", "เรียกเมท็อดที่ชนิดข้อมูลนี้ไม่มี — เช็กว่าตัวแปรเป็นชนิดที่คิดไว้จริงด้วย type()"),
    ("FileNotFoundError", "หาไฟล์ไม่เจอ — ตรวจชื่อไฟล์และตำแหน่งโฟลเดอร์ที่รันอยู่"),
    ("ModuleNotFoundError", "ยังไม่ได้ติดตั้งไลบรารีนี้ หรือสะกดชื่อโมดูลผิด"),
    ("UnboundLocalError", "ใช้ตัวแปรในฟังก์ชันก่อนกำหนดค่าในฟังก์ชันนั้น"),
    ("RecursionError", "ฟังก์ชันเรียกตัวเองไม่รู้จบ — ต้องมีเงื่อนไขหยุด"),
]


def explain_error(stderr: str) -> str:
    for key, hint in ERROR_HINTS:
        if key in stderr:
            return f"**{key}** · {hint}"
    return "อ่าน traceback จากล่างขึ้นบน — บรรทัดล่างสุดคือชนิดของข้อผิดพลาด ส่วนบรรทัดเหนือขึ้นไปบอกว่าเกิดที่ไหน"
