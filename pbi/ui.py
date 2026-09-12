"""ตัวช่วยที่ใช้ร่วมกันทุกหน้าของ Power BI Academy — โหลดข้อมูล จัดการ session และชิ้นส่วน UI ซ้ำ ๆ"""

from __future__ import annotations

import streamlit as st

from pbi import progress as pg
from pbi.model_data import build_frames, build_model


# ---------------------------------------------------------------------------
# ข้อมูลและโมเดล (แชร์กันทุกผู้ใช้ สร้างครั้งเดียวต่อการรันแอป)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="กำลังเตรียมชุดข้อมูลฝึก...")
def get_data():
    frames = build_frames()
    return frames, build_model(frames)


def frames():
    return get_data()[0]


def model():
    return get_data()[1]


# ---------------------------------------------------------------------------
# ความก้าวหน้าของผู้เรียน (แยกตามผู้ใช้ เก็บใน session ระหว่างใช้งาน)
# ---------------------------------------------------------------------------
def learner() -> str:
    return st.session_state.get("pbi_user", "guest")


def data() -> dict:
    """ข้อมูลความก้าวหน้าของผู้เรียนคนปัจจุบัน"""
    if st.session_state.get("pbi_progress_user") != learner():
        st.session_state["pbi_progress"] = pg.touch(pg.load(learner()))
        st.session_state["pbi_progress_user"] = learner()
        pg.save(st.session_state["pbi_progress"])
    return st.session_state["pbi_progress"]


def save() -> None:
    try:
        pg.save(data())
    except OSError as e:
        st.warning(f"บันทึกความก้าวหน้าไม่สำเร็จ: {e}")


def done_lessons() -> set[str]:
    return set(data().get("lessons", {}))


# ---------------------------------------------------------------------------
# ชิ้นส่วน UI ที่ใช้ซ้ำ
# ---------------------------------------------------------------------------
def xp_header() -> None:
    """แถบ XP + ระดับ + สถิติวันติดต่อกัน สำหรับวางในแถบข้าง"""
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


def fmt_value(v) -> str:
    """แสดงผลลัพธ์ของสูตร DAX ให้อ่านง่าย"""
    if v is None:
        return "(ว่าง)"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, str):
        return v
    if isinstance(v, float):
        if abs(v) < 1 and v != 0:
            return f"{v:,.6f}".rstrip("0")
        return f"{v:,.2f}"
    return f"{v:,}"


def stat_row(items: list[tuple[str, str, str | None]]) -> None:
    """แถวการ์ดตัวเลขสรุป — [(ป้าย, ค่า, คำอธิบายใต้ค่า)]"""
    with st.container(horizontal=True):
        for label, value, helptext in items:
            with st.container(border=True):
                st.metric(label, value, help=helptext)
