"""แบบทดสอบและการทบทวนแบบเว้นระยะ — ถามเฉพาะข้อที่ถึงกำหนดหรือข้อที่ยังไม่เคยทำ"""

import random

import streamlit as st

from pyacad import content, progress as pg, ui
from pyacad.quizbank import QUESTION_BY_ID, QUESTIONS, TOPIC_LABEL, TOTAL_QUESTIONS

d = ui.data()
all_ids = list(QUESTION_BY_ID)

st.title("แบบทดสอบ")
st.caption("ระบบใช้การทบทวนแบบเว้นระยะ (Leitner 5 กล่อง) — ตอบถูกจะทิ้งช่วงนานขึ้น "
           "ตอบผิดจะกลับมาถามพรุ่งนี้ วิธีนี้ทำให้จำได้นานกว่าการอ่านซ้ำรวดเดียว")

due = pg.due_questions(d, all_ids)
never = [q for q in all_ids if q not in d.get("quiz", {})]

ui.stat_row([
    ("ถึงกำหนดทบทวน", f"{len(due)} ข้อ", "ข้อที่เคยตอบแล้วและถึงรอบทบทวน"),
    ("ยังไม่เคยทำ", f"{len(never)} ข้อ", f"จากคลังทั้งหมด {TOTAL_QUESTIONS} ข้อ"),
    ("ตอบถูกสะสม", f"{d['quiz_totals']['right']:,}", None),
    ("ตอบผิดสะสม", f"{d['quiz_totals']['wrong']:,}", None),
])

st.divider()

# ---------------------------------------------------------------------------
# เลือกชุดคำถาม
# ---------------------------------------------------------------------------
mode = st.segmented_control(
    "เลือกชุด", ["ทบทวนที่ถึงกำหนด", "ข้อใหม่ที่ยังไม่เคยทำ", "เลือกตามหมวด"],
    key="quiz_mode", default="ทบทวนที่ถึงกำหนด",
) or "ทบทวนที่ถึงกำหนด"

if mode == "ทบทวนที่ถึงกำหนด":
    pool = due
    empty_msg = ("ยังไม่มีข้อที่ถึงกำหนดทบทวนวันนี้ — เลือก 'ข้อใหม่ที่ยังไม่เคยทำ' "
                 "หรือกลับมาพรุ่งนี้")
elif mode == "ข้อใหม่ที่ยังไม่เคยทำ":
    pool = never
    empty_msg = "ทำครบทุกข้อในคลังแล้ว เหลือแค่รอรอบทบทวน"
else:
    topic = st.selectbox("หมวด", list(TOPIC_LABEL), key="quiz_topic",
                         format_func=lambda t: TOPIC_LABEL[t])
    pool = [q["id"] for q in QUESTIONS if q["topic"] == topic]
    empty_msg = "หมวดนี้ยังไม่มีคำถาม"

if not pool:
    st.info(empty_msg, icon=":material/info:")
    st.stop()

# สุ่มลำดับครั้งเดียวต่อชุด เพื่อไม่ให้สลับไปมาทุกครั้งที่กดตอบ
sig = f"{mode}:{len(pool)}:{pool[0] if pool else ''}"
if st.session_state.get("quiz_sig") != sig:
    order = list(pool)
    random.shuffle(order)
    st.session_state["quiz_sig"] = sig
    st.session_state["quiz_order"] = order
    st.session_state["quiz_pos"] = 0

order = st.session_state["quiz_order"]
pos = min(st.session_state.get("quiz_pos", 0), len(order) - 1)
qid = order[pos]
q = QUESTION_BY_ID[qid]
rec = d.get("quiz", {}).get(qid)

st.progress((pos + 1) / len(order), text=f"ข้อ {pos + 1} จาก {len(order)}")

with st.container(border=True):
    st.caption(f"หมวด {TOPIC_LABEL[q['topic']]} · "
               + (f"อยู่กล่องทบทวนที่ {rec['box']}/5" if rec else "ข้อใหม่"))
    st.markdown(q["q"])

    answered_key = f"quiz_done_{qid}"
    choice = st.radio("ตัวเลือก", range(len(q["options"])), key=f"quiz_pick_{qid}",
                      format_func=lambda i: q["options"][i], index=None,
                      label_visibility="collapsed",
                      disabled=st.session_state.get(answered_key, False))

    with st.container(horizontal=True):
        if st.button("ตอบ", type="primary", disabled=choice is None
                     or st.session_state.get(answered_key, False)):
            correct = choice == q["answer"]
            pg.record_quiz(d, qid, correct)
            ui.save()
            st.session_state[answered_key] = True
            st.session_state[f"quiz_res_{qid}"] = correct
            st.rerun()

        if st.session_state.get(answered_key) and pos + 1 < len(order):
            if st.button("ข้อถัดไป", icon=":material/arrow_forward:"):
                st.session_state["quiz_pos"] = pos + 1
                st.rerun()

    if st.session_state.get(answered_key):
        if st.session_state.get(f"quiz_res_{qid}"):
            st.success(f"ถูกต้อง (+{pg.XP_QUIZ_CORRECT} XP) — {q['explain']}",
                       icon=":material/check_circle:")
        else:
            st.error(f"ยังไม่ใช่ · คำตอบที่ถูกคือ **{q['options'][q['answer']]}**\n\n{q['explain']}",
                     icon=":material/cancel:")
        lesson = content.LESSON_BY_ID.get(q["lesson"])
        if lesson and st.button(f"กลับไปอ่าน: {lesson['title']}", key=f"back_{qid}"):
            st.session_state["learn_module"] = lesson["module_id"]
            st.session_state["learn_lesson"] = lesson["id"]
            st.switch_page("py_pages/learn.py")

        if pos + 1 >= len(order):
            st.info("ทำครบทุกข้อในชุดนี้แล้ว", icon=":material/done_all:")
