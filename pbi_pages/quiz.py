"""แบบทดสอบ — เลือกทำตามหัวข้อ ตามโดเมน หรือทบทวนข้อที่ถึงกำหนดตามระบบเว้นระยะ"""

import random

import streamlit as st

from pbi import progress as pg, ui
from pbi.quizbank import (ALL_QUESTION_IDS, DOMAIN_LABEL, QUESTION_BY_ID,
                          QUESTIONS, by_domain, by_topic)

d = ui.data()
due = pg.due_questions(d, ALL_QUESTION_IDS)

st.title("แบบทดสอบ")
st.caption("ตอบถูกได้ XP และคำถามจะถูกจัดคิวกลับมาถามซ้ำตามระบบทบทวนแบบเว้นระยะ "
           "(ตอบถูกยิ่งหลายครั้ง ยิ่งเว้นห่างขึ้น)")

MODES = ["ทบทวนตามกำหนด", "ตามหัวข้อ", "ตามโดเมนข้อสอบ", "สุ่มทั้งหมด"]
st.session_state.setdefault("quiz_mode", "ทบทวนตามกำหนด")
if st.session_state["quiz_mode"] not in MODES:
    st.session_state["quiz_mode"] = MODES[0]

mode = st.segmented_control("โหมด", MODES, key="quiz_mode") or st.session_state["quiz_mode"]

# ---------------------------------------------------------------------------
# เลือกชุดคำถามตามโหมด
# ---------------------------------------------------------------------------
pool: list[dict] = []
if mode == "ทบทวนตามกำหนด":
    pool = [QUESTION_BY_ID[q] for q in due]
    if not pool:
        never = [q for q in QUESTIONS if q["id"] not in d["quiz"]]
        st.info(
            "ยังไม่มีข้อที่ถึงกำหนดทบทวนวันนี้ — เยี่ยมมาก" if d["quiz"]
            else "ยังไม่เคยตอบคำถามใดเลย เริ่มจากชุดนี้ได้",
            icon=":material/check_circle:")
        pool = never[:10]
    else:
        st.caption(f"ถึงกำหนดทบทวน {len(pool)} ข้อ")
elif mode == "ตามหัวข้อ":
    topics = by_topic()
    topic = st.selectbox("หัวข้อ", sorted(topics),
                         format_func=lambda t: f"{t} ({len(topics[t])} ข้อ)")
    pool = topics[topic]
elif mode == "ตามโดเมนข้อสอบ":
    dom = st.selectbox("โดเมน", list(DOMAIN_LABEL),
                       format_func=lambda k: f"{DOMAIN_LABEL[k]} ({len(by_domain(k))} ข้อ)")
    pool = by_domain(dom)
else:
    pool = list(QUESTIONS)
    if st.button("สลับชุดใหม่", icon=":material/shuffle:"):
        st.session_state["quiz_seed"] = random.randrange(10_000)
    random.Random(st.session_state.setdefault("quiz_seed", 7)).shuffle(pool)
    pool = pool[:15]

if not pool:
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# แสดงคำถามทีละข้อ พร้อมสถานะการทบทวน
# ---------------------------------------------------------------------------
for q in pool:
    rec = d["quiz"].get(q["id"], {})
    box = rec.get("box")
    key = f"quiz_{q['id']}"

    with st.container(border=True):
        head = f"**{q['q']}**"
        st.markdown(head)
        meta = [DOMAIN_LABEL[q["domain"]], q["topic"]]
        if box:
            meta.append(f"กล่องทบทวนที่ {box}/5 · ถูก {rec.get('right', 0)} ผิด {rec.get('wrong', 0)}")
        st.caption(" · ".join(meta))

        pick = st.radio("ตัวเลือก", range(len(q["options"])),
                        format_func=lambda i, o=q["options"]: o[i],
                        index=None, key=f"{key}_pick", label_visibility="collapsed")

        c1, c2 = st.columns([1, 4])
        if c1.button("ตรวจ", key=f"{key}_btn", disabled=pick is None):
            correct = pick == q["answer"]
            pg.record_quiz(d, q["id"], correct)
            ui.save()
            st.session_state[f"{key}_res"] = correct

        if f"{key}_res" in st.session_state:
            if st.session_state[f"{key}_res"]:
                st.success(f"ถูกต้อง — {q['explain']}", icon=":material/check_circle:")
            else:
                st.error(f"คำตอบที่ถูกคือ **{q['options'][q['answer']]}**\n\n{q['explain']}",
                         icon=":material/cancel:")
            nxt = d["quiz"].get(q["id"], {}).get("due")
            if nxt:
                st.caption(f"จะกลับมาถามซ้ำอีกครั้งวันที่ {nxt}")
