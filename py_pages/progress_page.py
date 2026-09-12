"""ความก้าวหน้า — ดูภาพรวมของตัวเอง ส่งออกข้อมูล และรีเซ็ตเมื่อต้องการเริ่มใหม่"""

import json

import pandas as pd
import streamlit as st

from pyacad import content, exercises as ex, progress as pg, ui
from pyacad.quizbank import QUESTION_BY_ID, TOPIC_LABEL, TOTAL_QUESTIONS

d = ui.data()
done = ui.done_lessons()
solved = ui.solved_code()

st.title("ความก้าวหน้า")
st.caption(f"ผู้เรียน: {ui.learner()} · เริ่มเรียนเมื่อ {d.get('created', '-')} · "
           f"ข้อมูลเก็บที่ py_progress/{ui.learner()}.json")

level_name, floor, nxt = pg.level_of(d.get("xp", 0))
ui.stat_row([
    ("ระดับ", level_name, f"XP สะสม {d.get('xp', 0):,}"),
    ("บทเรียน", f"{len(done)}/{content.TOTAL_LESSONS}", None),
    ("แบบฝึกหัด", f"{len(solved)}/{ex.TOTAL}", None),
    ("ใช้ตัวไล่โค้ด", f"{d.get('traces', 0)} ครั้ง", "เครื่องมือหาบั๊กทีละบรรทัด"),
])

tab_lesson, tab_code, tab_quiz, tab_data = st.tabs(
    ["บทเรียน", "แบบฝึกหัด", "แบบทดสอบ", "ข้อมูลดิบ"])

# ---------------------------------------------------------------------------
with tab_lesson:
    rows = []
    for m in content.MODULES:
        n_done, n_all = content.module_progress(m, done)
        rows.append({
            "โมดูล": m["title"],
            "จบแล้ว": f"{n_done}/{n_all}",
            "ความคืบหน้า": round(100 * n_done / n_all, 1) if n_all else 0.0,
            "เวลารวม (นาที)": sum(le["minutes"] for le in m["lessons"]),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={"ความคืบหน้า": st.column_config.ProgressColumn(
                     "ความคืบหน้า", min_value=0, max_value=100, format="%.0f%%")})

    remain = [le for le in content.ALL_LESSONS if le["id"] not in done]
    if remain:
        st.caption(f"เหลืออีก {len(remain)} บท ประมาณ "
                   f"{sum(le['minutes'] for le in remain)} นาที")
        with st.expander("บทที่ยังไม่จบ"):
            for le in remain:
                st.caption(f"○ {le['module_title']} · {le['title']} ({le['minutes']} นาที)")
    else:
        st.success("เรียนจบทุกบทแล้ว", icon=":material/check_circle:")

# ---------------------------------------------------------------------------
with tab_code:
    rows = []
    for e in ex.EXERCISES:
        rec = d.get("code", {}).get(e["id"], {})
        rows.append({
            "ชุด": e["group"],
            "ข้อ": e["title"],
            "ระดับ": "★" * e["level"],
            "สถานะ": "✓ ผ่าน" if rec.get("solved") else ("กำลังทำ" if rec else "-"),
            "ส่งไปแล้ว": rec.get("attempts", 0),
            "เปิดคำใบ้": "ใช่" if rec.get("hint_used") else "",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=430)

    attempts = sum(r.get("attempts", 0) for r in d.get("code", {}).values())
    if attempts:
        st.caption(f"ส่งคำตอบทั้งหมด {attempts} ครั้ง · ผ่านตั้งแต่ครั้งแรกโดยไม่เปิดคำใบ้ "
                   f"{d.get('one_shots', 0)} ข้อ")

# ---------------------------------------------------------------------------
with tab_quiz:
    quiz = d.get("quiz", {})
    if not quiz:
        st.info("ยังไม่เคยทำแบบทดสอบ", icon=":material/info:")
    else:
        by_topic: dict[str, list[int]] = {}
        for qid, rec in quiz.items():
            q = QUESTION_BY_ID.get(qid)
            if not q:
                continue
            got, total = by_topic.get(q["topic"], [0, 0])
            by_topic[q["topic"]] = [got + rec.get("right", 0),
                                    total + rec.get("right", 0) + rec.get("wrong", 0)]
        rows = [{
            "หมวด": TOPIC_LABEL.get(t, t),
            "ตอบถูก": f"{got}/{total}",
            "ความแม่นยำ": round(100 * got / total, 1) if total else 0.0,
        } for t, (got, total) in sorted(by_topic.items())]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={"ความแม่นยำ": st.column_config.ProgressColumn(
                         "ความแม่นยำ", min_value=0, max_value=100, format="%.0f%%")})

        boxes = pd.Series([r.get("box", 1) for r in quiz.values()]).value_counts().sort_index()
        st.caption("กระจายตามกล่องทบทวน (กล่องยิ่งสูง = จำได้แม่นและทิ้งช่วงนานขึ้น)")
        st.bar_chart(pd.DataFrame({"จำนวนข้อ": boxes}))
        st.caption(f"ทำไปแล้ว {len(quiz)}/{TOTAL_QUESTIONS} ข้อของคลัง")

    if d.get("exams"):
        st.subheader("ประวัติข้อสอบรวม")
        st.dataframe(pd.DataFrame([{
            "วันที่": e["date"], "คะแนน": f"{e['score']}/{e['total']}",
            "เปอร์เซ็นต์": e["pct"],
        } for e in reversed(d["exams"])]), hide_index=True, width="stretch")

# ---------------------------------------------------------------------------
with tab_data:
    st.caption("ไฟล์ความก้าวหน้าของคุณเป็น JSON ธรรมดา คัดลอกไปเก็บหรือย้ายเครื่องได้")
    st.download_button(
        "ดาวน์โหลดไฟล์ความก้าวหน้า",
        data=json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8"),
        file_name=f"python_academy_{ui.learner()}.json",
        mime="application/json", icon=":material/download:",
    )
    with st.expander("ดูข้อมูลดิบ"):
        st.json(d, expanded=False)

    st.divider()
    st.markdown("**เริ่มใหม่ทั้งหมด**")
    st.caption("ล้าง XP บทเรียนที่จบ แบบฝึกหัดที่ผ่าน และประวัติแบบทดสอบทั้งหมดของผู้เรียนคนนี้")
    confirm = st.text_input("พิมพ์คำว่า RESET เพื่อยืนยัน", key="reset_confirm")
    if st.button("รีเซ็ตความก้าวหน้า", type="secondary", icon=":material/restart_alt:",
                 disabled=confirm.strip().upper() != "RESET"):
        st.session_state["py_progress"] = pg.reset(ui.learner())
        st.session_state["py_progress_user"] = ui.learner()
        st.success("รีเซ็ตเรียบร้อย")
        st.rerun()
