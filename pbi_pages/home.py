"""หน้าหลัก — สรุปความก้าวหน้า และบอกว่าควรทำอะไรต่อ"""

import altair as alt
import pandas as pd
import streamlit as st

from pbi import content, progress as pg, ui
from pbi.exercises import DAX_EXERCISES, TOTAL_DAX, TOTAL_PQ
from pbi.quizbank import ALL_QUESTION_IDS

d = ui.data()
done = ui.done_lessons()
pg.check_completion_badges(d, content.TOTAL_LESSONS, TOTAL_DAX)

st.title("Power BI Academy")
st.caption("เรียนจากศูนย์จนทำรายงานใช้งานจริงได้ — พร้อมสนามฝึกเขียน DAX ที่ตรวจคำตอบให้ทันที")

# ---------------------------------------------------------------------------
# ตัวเลขสรุป
# ---------------------------------------------------------------------------
dax_done = sum(1 for r in d["dax"].values() if r.get("solved"))
pq_done = sum(1 for r in d["pq"].values() if r.get("solved"))
quiz_right = d["quiz_totals"]["right"]
quiz_total = quiz_right + d["quiz_totals"]["wrong"]
due = pg.due_questions(d, ALL_QUESTION_IDS)

ui.stat_row([
    ("บทเรียนที่จบ", f"{len(done)}/{content.TOTAL_LESSONS}",
     f"เนื้อหาทั้งหมดประมาณ {content.TOTAL_MINUTES} นาที"),
    ("แบบฝึกหัด DAX", f"{dax_done}/{TOTAL_DAX}", "ตรวจคำตอบด้วยการรันสูตรจริง"),
    ("แบบฝึกหัด Power Query", f"{pq_done}/{TOTAL_PQ}", None),
    ("ตอบคำถามถูก", f"{quiz_right}/{quiz_total}" if quiz_total else "—",
     "นับสะสมทุกครั้งที่ตอบ"),
])

st.markdown("")

left, right = st.columns([1.45, 1], gap="large")

# ---------------------------------------------------------------------------
# ทำอะไรต่อดี
# ---------------------------------------------------------------------------
with left:
    st.subheader("ทำอะไรต่อดี")

    nxt = content.next_lesson(done)
    if nxt:
        with st.container(border=True):
            st.markdown(f"**บทเรียนถัดไป · {nxt['module_title']}**")
            st.markdown(f"### {nxt['title']}")
            st.caption(f"{nxt['goal']} · ประมาณ {nxt['minutes']} นาที")
            if st.button("เริ่มเรียนบทนี้", type="primary", icon=":material/play_arrow:"):
                st.session_state["learn_module"] = nxt["module_id"]
                st.session_state["learn_lesson"] = nxt["id"]
                st.switch_page("pbi_pages/learn.py")
    else:
        with st.container(border=True):
            st.markdown("### เรียนจบทุกบทแล้ว")
            st.caption("ขั้นต่อไปคือลงมือทำโปรเจกต์จริงด้วยชุดข้อมูลฝึก แล้ววัดผลด้วยข้อสอบจำลอง")

    if due:
        with st.container(border=True):
            st.markdown(f"**ถึงกำหนดทบทวน {len(due)} ข้อ**")
            st.caption("ระบบทบทวนแบบเว้นระยะจะดันคำถามที่คุณเคยตอบผิดกลับมาถามซ้ำ "
                       "ในจังหวะที่กำลังจะลืมพอดี")
            if st.button("ทบทวนตอนนี้", icon=":material/refresh:"):
                st.session_state["quiz_mode"] = "ทบทวนตามกำหนด"
                st.switch_page("pbi_pages/quiz.py")

    unsolved = [e for e in DAX_EXERCISES if not d["dax"].get(e["id"], {}).get("solved")]
    if unsolved:
        with st.container(border=True):
            ex = unsolved[0]
            st.markdown(f"**แบบฝึกหัด DAX ถัดไป · {ex['group']}**")
            st.markdown(f"### {ex['title']}")
            st.caption(ex["prompt"][:120] + ("..." if len(ex["prompt"]) > 120 else ""))
            if st.button("ลงมือเขียน", icon=":material/function:"):
                st.session_state["dax_group"] = ex["group"]
                st.session_state["dax_ex"] = ex["id"]
                st.switch_page("pbi_pages/dax_lab.py")

# ---------------------------------------------------------------------------
# ความคืบหน้ารายโมดูล
# ---------------------------------------------------------------------------
with right:
    st.subheader("ความคืบหน้าตามโมดูล")
    rows = []
    for m in content.MODULES:
        n_done, n_all = content.module_progress(m, done)
        rows.append({"โมดูล": m["title"], "จบแล้ว": n_done, "ทั้งหมด": n_all,
                     "สัดส่วน": n_done / n_all})
    df = pd.DataFrame(rows)

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=3, height=16)
        .encode(
            x=alt.X("สัดส่วน:Q", axis=alt.Axis(format="%", title=None),
                    scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("โมดูล:N", sort=None, title=None),
            color=alt.condition(alt.datum["สัดส่วน"] >= 1.0,
                                alt.value("#2e9e5b"), alt.value("#4c78a8")),
            tooltip=["โมดูล", "จบแล้ว", "ทั้งหมด"],
        )
        .properties(height=32 * len(rows))
    )
    st.altair_chart(chart)

st.divider()

# ---------------------------------------------------------------------------
# แนะนำการใช้งานสำหรับคนเพิ่งเริ่ม
# ---------------------------------------------------------------------------
if not done and not dax_done:
    st.subheader("แนะนำวิธีใช้")
    a, b, c = st.columns(3)
    with a:
        with st.container(border=True):
            st.markdown("#### 1 · เรียนตามลำดับ")
            st.caption("หลักสูตร 9 โมดูล เรียงตามลำดับที่ควรเรียนจริง "
                       "คือดึงข้อมูล → ทำความสะอาด → ออกแบบโมเดล → DAX → รายงาน → เผยแพร่ "
                       "แต่ละบทมีกับดักที่คนทำงานจริงพลาดบ่อยกำกับไว้")
    with b:
        with st.container(border=True):
            st.markdown("#### 2 · ฝึกจนเขียนได้เอง")
            st.caption("แบบฝึกหัด DAX ตรวจด้วยการรันสูตรของคุณจริง ๆ เทียบกับเฉลย "
                       "ภายใต้ตัวกรองหลายชุด ถ้าเขียน CALCULATE หรือ ALL ผิด "
                       "ระบบจะชี้ให้เห็นว่าผิดที่บริบทไหน")
    with c:
        with st.container(border=True):
            st.markdown("#### 3 · ย้ายไปของจริง")
            st.caption("ดาวน์โหลดชุดข้อมูลโรงงานจากหน้า ชุดข้อมูลฝึก "
                       "ไปทำใน Power BI Desktop ตามโจทย์โปรเจกต์ในโมดูล 9 "
                       "แล้วเทียบตัวเลขกับที่แอปนี้คำนวณให้")
