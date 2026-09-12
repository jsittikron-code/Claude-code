"""ข้อสอบรวม — วัดผลทั้งหลักสูตรในครั้งเดียว พร้อมรายงานว่าควรกลับไปทบทวนหมวดไหน"""

import random

import pandas as pd
import streamlit as st

from pyacad import content, progress as pg, ui
from pyacad.quizbank import QUESTION_BY_ID, TOPIC_LABEL, TOTAL_QUESTIONS, build_exam

d = ui.data()

st.title("ข้อสอบรวม")
st.caption(f"สุ่มคำถามจากคลัง {TOTAL_QUESTIONS} ข้อ ตามสัดส่วนของแต่ละหมวด "
           "ทำครั้งเดียวจบแล้วดูผลแยกหมวด · เกณฑ์ผ่าน 70%")

state = st.session_state

# ---------------------------------------------------------------------------
# เริ่มข้อสอบใหม่
# ---------------------------------------------------------------------------
if "exam_questions" not in state:
    n = st.slider("จำนวนข้อ", 10, 40, 25, step=5)
    st.caption("แนะนำ 25 ข้อ ใช้เวลาประมาณ 15 นาที")
    if st.button("เริ่มทำข้อสอบ", type="primary", icon=":material/play_arrow:"):
        state["exam_questions"] = build_exam(n, random.Random())
        state["exam_answers"] = {}
        state["exam_submitted"] = False
        st.rerun()

    if d.get("exams"):
        st.divider()
        st.subheader("ผลย้อนหลัง")
        hist = pd.DataFrame([{
            "วันที่": e["date"], "คะแนน": f"{e['score']}/{e['total']}",
            "เปอร์เซ็นต์": f"{e['pct']:.1f}%",
            "ผล": "ผ่าน" if e["pct"] >= 70 else "ยังไม่ผ่าน",
        } for e in reversed(d["exams"])])
        st.dataframe(hist, hide_index=True, width="stretch")
    st.stop()

questions = state["exam_questions"]

# ---------------------------------------------------------------------------
# ทำข้อสอบ
# ---------------------------------------------------------------------------
if not state.get("exam_submitted"):
    answered = len(state["exam_answers"])
    st.progress(answered / len(questions), text=f"ตอบแล้ว {answered}/{len(questions)} ข้อ")

    for i, q in enumerate(questions, start=1):
        with st.container(border=True):
            st.markdown(f"**ข้อ {i}.** {q['q']}")
            pick = st.radio("ตัวเลือก", range(len(q["options"])),
                            key=f"exam_pick_{q['id']}",
                            format_func=lambda j, o=q["options"]: o[j],
                            index=None, label_visibility="collapsed")
            if pick is not None:
                state["exam_answers"][q["id"]] = pick

    st.divider()
    with st.container(horizontal=True):
        if st.button("ส่งคำตอบ", type="primary", icon=":material/send:"):
            state["exam_submitted"] = True
            st.rerun()
        if st.button("ยกเลิกข้อสอบนี้", icon=":material/close:"):
            for k in ("exam_questions", "exam_answers", "exam_submitted"):
                state.pop(k, None)
            st.rerun()
    if len(state["exam_answers"]) < len(questions):
        st.caption(f"ยังไม่ได้ตอบ {len(questions) - len(state['exam_answers'])} ข้อ "
                   "— ข้อที่ไม่ตอบจะนับเป็นผิด")
    st.stop()

# ---------------------------------------------------------------------------
# ตรวจและรายงานผล
# ---------------------------------------------------------------------------
answers = state["exam_answers"]
score = 0
by_topic: dict[str, list[int]] = {}
for q in questions:
    ok = answers.get(q["id"]) == q["answer"]
    score += 1 if ok else 0
    got, total = by_topic.get(q["topic"], [0, 0])
    by_topic[q["topic"]] = [got + (1 if ok else 0), total + 1]

pct = 100 * score / len(questions)

if not state.get("exam_recorded"):
    pg.record_exam(d, score, len(questions),
                   {k: v for k, v in by_topic.items()})
    ui.save()
    state["exam_recorded"] = True

if pct >= 90:
    st.success(f"คะแนน {score}/{len(questions)} ({pct:.1f}%) — เยี่ยมมาก",
               icon=":material/emoji_events:")
    st.balloons()
elif pct >= 70:
    st.success(f"คะแนน {score}/{len(questions)} ({pct:.1f}%) — ผ่านเกณฑ์ (+{pg.XP_EXAM_PASS} XP)",
               icon=":material/check_circle:")
else:
    st.warning(f"คะแนน {score}/{len(questions)} ({pct:.1f}%) — ยังไม่ผ่านเกณฑ์ 70%",
               icon=":material/trending_down:")

st.subheader("ผลแยกตามหมวด")
rows = []
for topic, (got, total) in sorted(by_topic.items()):
    rows.append({
        "หมวด": TOPIC_LABEL.get(topic, topic),
        "ถูก": f"{got}/{total}",
        "เปอร์เซ็นต์": round(100 * got / total, 1),
    })
df = pd.DataFrame(rows)
st.dataframe(df, hide_index=True, width="stretch",
             column_config={"เปอร์เซ็นต์": st.column_config.ProgressColumn(
                 "เปอร์เซ็นต์", min_value=0, max_value=100, format="%.0f%%")})

weak = [r["หมวด"] for r in rows if r["เปอร์เซ็นต์"] < 70]
if weak:
    st.info("หมวดที่ควรกลับไปทบทวน: " + ", ".join(weak), icon=":material/menu_book:")

st.subheader("เฉลยรายข้อ")
for i, q in enumerate(questions, start=1):
    picked = answers.get(q["id"])
    ok = picked == q["answer"]
    with st.expander(f"{'✓' if ok else '✗'} ข้อ {i} · {TOPIC_LABEL.get(q['topic'], '')}",
                     expanded=not ok):
        st.markdown(q["q"])
        st.caption("คำตอบของคุณ: " +
                   (q["options"][picked] if picked is not None else "(ไม่ได้ตอบ)"))
        st.caption(f"คำตอบที่ถูก: **{q['options'][q['answer']]}**")
        st.markdown(q["explain"])
        lesson = content.LESSON_BY_ID.get(q["lesson"])
        if lesson:
            st.caption(f"อยู่ในบท: {lesson['title']} ({lesson['module_title']})")

st.divider()
if st.button("ทำข้อสอบชุดใหม่", icon=":material/refresh:"):
    for k in ("exam_questions", "exam_answers", "exam_submitted", "exam_recorded"):
        state.pop(k, None)
    for q in questions:
        state.pop(f"exam_pick_{q['id']}", None)
    st.rerun()
