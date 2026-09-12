"""ความก้าวหน้า — สถิติ เหรียญตรา ประวัติการสอบ และการจัดการข้อมูลผู้เรียน"""

import altair as alt
import pandas as pd
import streamlit as st

from pbi import content, progress as pg, ui
from pbi.exercises import DAX_EXERCISES, PQ_EXERCISES, TOTAL_DAX, TOTAL_PQ
from pbi.quizbank import ALL_QUESTION_IDS, DOMAIN_LABEL, QUESTION_BY_ID

d = ui.data()
done = ui.done_lessons()
pg.check_completion_badges(d, content.TOTAL_LESSONS, TOTAL_DAX)
ui.save()

xp = d.get("xp", 0)
level, floor, nxt = pg.level_of(xp)

st.title("ความก้าวหน้า")
st.caption(f"ผู้เรียน: {ui.learner()} · เริ่มเรียนเมื่อ {d.get('created', '—')}")

dax_done = sum(1 for r in d["dax"].values() if r.get("solved"))
pq_done = sum(1 for r in d["pq"].values() if r.get("solved"))
right, wrong = d["quiz_totals"]["right"], d["quiz_totals"]["wrong"]

ui.stat_row([
    ("ระดับ", level, f"{xp:,} XP"),
    ("บทเรียน", f"{len(done)}/{content.TOTAL_LESSONS}", None),
    ("DAX", f"{dax_done}/{TOTAL_DAX}", None),
    ("Power Query", f"{pq_done}/{TOTAL_PQ}", None),
    ("วันติดต่อกัน", f"{d.get('streak', 0)}", f"สถิติสูงสุด {d.get('best_streak', 0)} วัน"),
])

st.markdown("")

# ---------------------------------------------------------------------------
# ความแม่นยำรายโดเมน
# ---------------------------------------------------------------------------
left, right_col = st.columns([1.2, 1], gap="large")

with left:
    st.subheader("ความแม่นยำรายโดเมน")
    stats: dict[str, list[int]] = {}
    for qid, rec in d["quiz"].items():
        q = QUESTION_BY_ID.get(qid)
        if not q:
            continue
        cur = stats.setdefault(q["domain"], [0, 0])
        cur[0] += rec.get("right", 0)
        cur[1] += rec.get("right", 0) + rec.get("wrong", 0)

    if not stats:
        st.caption("ยังไม่มีข้อมูล — ลองทำแบบทดสอบสักชุดก่อน")
    else:
        df = pd.DataFrame([
            {"โดเมน": DOMAIN_LABEL[k], "ถูก": v[0], "ตอบไป": v[1],
             "ความแม่นยำ": v[0] / v[1] if v[1] else 0}
            for k, v in stats.items()
        ])
        st.altair_chart(
            alt.Chart(df).mark_bar(cornerRadiusEnd=3, height=24).encode(
                x=alt.X("ความแม่นยำ:Q", axis=alt.Axis(format="%", title=None),
                        scale=alt.Scale(domain=[0, 1])),
                y=alt.Y("โดเมน:N", sort=None, title=None),
                color=alt.condition(alt.datum["ความแม่นยำ"] >= 0.7,
                                    alt.value("#2e9e5b"), alt.value("#d1495b")),
                tooltip=["โดเมน", "ถูก", "ตอบไป"],
            ).properties(height=42 * len(df))
        )

    # คิวทบทวน
    st.subheader("คิวทบทวน")
    boxes = {i: 0 for i in range(1, 6)}
    for rec in d["quiz"].values():
        boxes[rec.get("box", 1)] = boxes.get(rec.get("box", 1), 0) + 1
    due = pg.due_questions(d, ALL_QUESTION_IDS)
    st.caption(f"ถึงกำหนดวันนี้ {len(due)} ข้อ · ยังไม่เคยตอบ "
               f"{len(ALL_QUESTION_IDS) - len(d['quiz'])} ข้อ")
    st.dataframe(
        pd.DataFrame([{"กล่องที่": k, "ทบทวนทุก ๆ": f"{pg.LEITNER_DAYS[k]} วัน",
                       "จำนวนคำถาม": v} for k, v in boxes.items()]),
        hide_index=True,
    )

with right_col:
    st.subheader("เหรียญตรา")
    earned = d.get("badges", {})
    st.caption(f"ได้แล้ว {len(earned)}/{len(pg.BADGES)}")
    for bid, (name, desc) in pg.BADGES.items():
        with st.container(border=True):
            if bid in earned:
                st.markdown(f"**🏅 {name}** — {desc}")
                st.caption(f"ได้รับเมื่อ {earned[bid]}")
            else:
                st.markdown(f"**🔒 {name}**")
                st.caption(desc)

st.divider()

# ---------------------------------------------------------------------------
# รายละเอียดแบบฝึกหัด
# ---------------------------------------------------------------------------
st.subheader("รายละเอียดแบบฝึกหัด")
t1, t2, t3 = st.tabs(["DAX", "Power Query", "ประวัติข้อสอบ"])

with t1:
    rows = []
    for ex in DAX_EXERCISES:
        rec = d["dax"].get(ex["id"], {})
        rows.append({
            "ชุด": ex["group"], "ข้อ": ex["title"],
            "สถานะ": "ผ่าน" if rec.get("solved") else ("ลองแล้ว" if rec else "ยังไม่ทำ"),
            "ส่งคำตอบ": rec.get("attempts", 0),
            "เปิดคำใบ้": "ใช่" if rec.get("hint_used") else "—",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, height=430)

with t2:
    rows = []
    for ex in PQ_EXERCISES:
        rec = d["pq"].get(ex["id"], {})
        rows.append({
            "ชุด": ex["group"], "ข้อ": ex["title"],
            "สถานะ": "ผ่าน" if rec.get("solved") else ("ลองแล้ว" if rec else "ยังไม่ทำ"),
            "ส่งคำตอบ": rec.get("attempts", 0),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, height=430)

with t3:
    if not d["exams"]:
        st.caption("ยังไม่เคยทำข้อสอบจำลอง")
    else:
        hist = pd.DataFrame(d["exams"])
        st.altair_chart(
            alt.Chart(hist.assign(ครั้งที่=range(1, len(hist) + 1)))
            .mark_line(point=True)
            .encode(
                x=alt.X("ครั้งที่:O", title="ครั้งที่"),
                y=alt.Y("pct:Q", title="คะแนน (%)", scale=alt.Scale(domain=[0, 100])),
                tooltip=["date", "score", "total", "pct"],
            ).properties(height=240)
        )
        show = hist[["date", "score", "total", "pct"]]
        show.columns = ["วันที่", "ได้", "เต็ม", "ร้อยละ"]
        st.dataframe(show.iloc[::-1], hide_index=True)

st.divider()

with st.expander("จัดการข้อมูลผู้เรียน"):
    st.caption(f"ความก้าวหน้าถูกเก็บที่ `{pg.path_for(ui.learner())}` — "
               "สำรองไฟล์นี้ไว้ได้ หรือคัดลอกไปเครื่องอื่นเพื่อเรียนต่อ")
    confirm = st.text_input("พิมพ์ RESET เพื่อยืนยันการล้างความก้าวหน้าทั้งหมด",
                            placeholder="RESET")
    if st.button("ล้างความก้าวหน้า", type="secondary", disabled=confirm != "RESET",
                 icon=":material/delete:"):
        st.session_state["pbi_progress"] = pg.reset(ui.learner())
        st.success("ล้างข้อมูลเรียบร้อยแล้ว")
        st.rerun()
