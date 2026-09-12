"""ข้อสอบจำลอง PL-300 — จับเวลา สัดส่วนโดเมนใกล้เคียงข้อสอบจริง และรายงานผลแยกโดเมน"""

import random
import time

import altair as alt
import pandas as pd
import streamlit as st

from pbi import progress as pg, ui
from pbi.quizbank import DOMAIN_LABEL, EXAM_WEIGHTS, QUESTION_BY_ID, QUESTIONS, build_exam

d = ui.data()
PASS_MARK = 70

st.title("ข้อสอบจำลอง PL-300")

state = st.session_state.setdefault("exam", {"status": "idle"})

# ---------------------------------------------------------------------------
# หน้าเริ่มต้น
# ---------------------------------------------------------------------------
if state["status"] == "idle":
    st.caption("จำลองบรรยากาศข้อสอบจริง — จับเวลา สุ่มข้อตามสัดส่วนโดเมน "
               "และไม่เฉลยจนกว่าจะส่งคำตอบทั้งชุด")

    with st.container(border=True):
        st.markdown("**สัดส่วนโดเมนของชุดข้อสอบ**")
        for k, w in EXAM_WEIGHTS.items():
            st.caption(f"{DOMAIN_LABEL[k]} ประมาณ {w:.0%}")

    c1, c2 = st.columns(2)
    n = c1.slider("จำนวนข้อ", 10, min(50, len(QUESTIONS)), 25, step=5)
    minutes = c2.slider("เวลา (นาที)", 5, 60, max(5, n), step=5)

    if st.button("เริ่มทำข้อสอบ", type="primary", icon=":material/play_arrow:"):
        rng = random.Random()
        state.update({
            "status": "running",
            "questions": [q["id"] for q in build_exam(n, rng)],
            "answers": {},
            "started": time.time(),
            "limit": minutes * 60,
        })
        st.rerun()

    if d["exams"]:
        st.divider()
        st.subheader("ผลการสอบที่ผ่านมา")
        hist = pd.DataFrame(d["exams"])[["date", "score", "total", "pct"]]
        hist.columns = ["วันที่", "ได้", "เต็ม", "ร้อยละ"]
        st.dataframe(hist.iloc[::-1], hide_index=True)
    st.stop()

# ---------------------------------------------------------------------------
# กำลังทำข้อสอบ
# ---------------------------------------------------------------------------
if state["status"] == "running":
    qids = state["questions"]
    left = state["limit"] - (time.time() - state["started"])

    bar, act = st.columns([3, 1])
    with bar:
        if left <= 0:
            st.error("หมดเวลาแล้ว — กดส่งคำตอบเพื่อดูผล", icon=":material/timer_off:")
        else:
            st.progress(max(0.0, min(1.0, left / state["limit"])),
                        text=f"เหลือเวลา {int(left) // 60:02d}:{int(left) % 60:02d} · "
                             f"ตอบแล้ว {len(state['answers'])}/{len(qids)}")
    submit_top = act.button("ส่งคำตอบ", type="primary", width="stretch",
                            icon=":material/send:")

    for n, qid in enumerate(qids, 1):
        q = QUESTION_BY_ID[qid]
        with st.container(border=True):
            st.markdown(f"**ข้อ {n}. {q['q']}**")
            pick = st.radio(
                "ตัวเลือก", range(len(q["options"])),
                format_func=lambda i, o=q["options"]: o[i],
                index=state["answers"].get(qid), key=f"exam_{qid}",
                label_visibility="collapsed",
            )
            if pick is not None:
                state["answers"][qid] = pick

    submit_bottom = st.button("ส่งคำตอบทั้งหมด", type="primary",
                              icon=":material/send:", key="exam_submit_bottom")

    if submit_top or submit_bottom:
        score = 0
        by_dom: dict[str, list[int]] = {}
        for qid in qids:
            q = QUESTION_BY_ID[qid]
            hit = int(state["answers"].get(qid) == q["answer"])
            score += hit
            cur = by_dom.setdefault(q["domain"], [0, 0])
            cur[0] += hit
            cur[1] += 1
        state.update({"status": "done", "score": score, "by_domain": by_dom,
                      "elapsed": int(time.time() - state["started"])})
        pg.record_exam(d, score, len(qids), state["by_domain"])
        ui.save()
        st.rerun()

    # นับเวลาถอยหลังโดยไม่รบกวนคำตอบที่กรอกไว้
    if left > 0:
        st.caption("หน้าจอจะรีเฟรชเวลาที่เหลือทุกครั้งที่คุณเลือกคำตอบ")
    st.stop()

# ---------------------------------------------------------------------------
# ผลสอบ
# ---------------------------------------------------------------------------
qids = state["questions"]
score, total = state["score"], len(qids)
pct = round(100 * score / total, 1)

if pct >= PASS_MARK:
    st.success(f"ผ่านเกณฑ์ · ได้ {score}/{total} คิดเป็น {pct}%", icon=":material/military_tech:")
else:
    st.error(f"ยังไม่ผ่านเกณฑ์ {PASS_MARK}% · ได้ {score}/{total} คิดเป็น {pct}%",
             icon=":material/info:")
st.caption(f"ใช้เวลา {state['elapsed'] // 60} นาที {state['elapsed'] % 60} วินาที")

rows = [{"โดเมน": DOMAIN_LABEL[k], "ถูก": v[0], "ทั้งหมด": v[1], "ร้อยละ": v[0] / v[1]}
        for k, v in state["by_domain"].items()]
df = pd.DataFrame(rows)

c1, c2 = st.columns([1, 1], gap="large")
with c1:
    st.subheader("คะแนนแยกตามโดเมน")
    chart = (
        alt.Chart(df).mark_bar(cornerRadiusEnd=3, height=22)
        .encode(
            x=alt.X("ร้อยละ:Q", axis=alt.Axis(format="%", title=None),
                    scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("โดเมน:N", sort=None, title=None),
            color=alt.condition(alt.datum["ร้อยละ"] >= PASS_MARK / 100,
                                alt.value("#2e9e5b"), alt.value("#d1495b")),
            tooltip=["โดเมน", "ถูก", "ทั้งหมด"],
        ).properties(height=40 * len(rows))
    )
    st.altair_chart(chart)

with c2:
    st.subheader("ควรกลับไปทบทวน")
    weak = df[df["ร้อยละ"] < PASS_MARK / 100].sort_values("ร้อยละ")
    if weak.empty:
        st.caption("ทุกโดเมนผ่านเกณฑ์ — ขั้นต่อไปคือลงมือทำโปรเจกต์จริงให้ครบวงจร")
    else:
        for _, r in weak.iterrows():
            st.markdown(f"- **{r['โดเมน']}** ได้ {r['ถูก']}/{r['ทั้งหมด']} "
                        f"({r['ร้อยละ']:.0%})")
        st.caption("ไปที่หน้าแบบทดสอบ เลือกโหมด ตามโดเมนข้อสอบ เพื่อฝึกเฉพาะจุดที่อ่อน")

st.divider()
st.subheader("ทบทวนคำตอบทีละข้อ")
only_wrong = st.toggle("แสดงเฉพาะข้อที่ตอบผิด", value=True)

for n, qid in enumerate(qids, 1):
    q = QUESTION_BY_ID[qid]
    picked = state["answers"].get(qid)
    correct = picked == q["answer"]
    if only_wrong and correct:
        continue
    with st.container(border=True):
        st.markdown(f"**ข้อ {n}. {q['q']}**")
        st.caption(f"{DOMAIN_LABEL[q['domain']]} · {q['topic']}")
        if picked is None:
            st.warning("ไม่ได้ตอบข้อนี้", icon=":material/help:")
        elif correct:
            st.success(f"คุณตอบ: {q['options'][picked]}", icon=":material/check_circle:")
        else:
            st.error(f"คุณตอบ: {q['options'][picked]}", icon=":material/cancel:")
        if not correct:
            st.markdown(f"คำตอบที่ถูก: **{q['options'][q['answer']]}**")
        st.caption(q["explain"])

if st.button("ทำข้อสอบชุดใหม่", icon=":material/refresh:"):
    st.session_state["exam"] = {"status": "idle"}
    st.rerun()
