"""หลักสูตร — อ่านบทเรียน ลองรันตัวอย่าง ทำแบบทดสอบท้ายบท และทำเครื่องหมายว่าเรียนจบ"""

import streamlit as st

from pyacad import content, exercises as ex, progress as pg, ui
from pyacad.quizbank import QUESTION_BY_ID

d = ui.data()
done = ui.done_lessons()

st.title("หลักสูตร Python")
st.caption(f"{content.TOTAL_LESSONS} บทเรียน · ประมาณ {content.TOTAL_MINUTES} นาที · "
           f"เรียนจบแล้ว {len(done)} บท")

# ---------------------------------------------------------------------------
# เลือกโมดูลและบทเรียน
# ---------------------------------------------------------------------------
mod_labels = {}
for m in content.MODULES:
    n_done, n_all = content.module_progress(m, done)
    tick = "✓ " if n_done == n_all else ""
    mod_labels[m["id"]] = f"{tick}{m['title']}  ({n_done}/{n_all})"

st.session_state.setdefault("learn_module", content.MODULES[0]["id"])
if st.session_state["learn_module"] not in mod_labels:
    st.session_state["learn_module"] = content.MODULES[0]["id"]

mod_id = st.selectbox("โมดูล", list(mod_labels), key="learn_module",
                      format_func=lambda k: mod_labels[k])
module = content.MODULE_BY_ID[mod_id]
st.caption(f"เป้าหมายของโมดูล: {module['goal']}")

lesson_ids = [le["id"] for le in module["lessons"]]
if st.session_state.get("learn_lesson") not in lesson_ids:
    st.session_state["learn_lesson"] = next((i for i in lesson_ids if i not in done),
                                            lesson_ids[0])

lesson_id = st.radio(
    "บทเรียน", lesson_ids, key="learn_lesson",
    format_func=lambda i: ("✓ " if i in done else "") + content.LESSON_BY_ID[i]["title"],
    horizontal=True, label_visibility="collapsed",
)
lesson = content.LESSON_BY_ID[lesson_id]

st.divider()

body, side = st.columns([2.1, 1], gap="large")

# ---------------------------------------------------------------------------
# เนื้อหาบทเรียน
# ---------------------------------------------------------------------------
with body:
    st.header(lesson["title"])
    st.caption(f"เรียนจบแล้วจะ: {lesson['goal']} · ประมาณ {lesson['minutes']} นาที")
    st.markdown(lesson["body"])

    if lesson.get("pitfalls"):
        with st.container(border=True):
            st.markdown("**กับดักที่คนทำงานจริงพลาดบ่อย**")
            for p in lesson["pitfalls"]:
                st.markdown(f"- {p}")

    # -- ตัวอย่างที่กดรันได้ ------------------------------------------------
    if lesson.get("demo"):
        st.subheader("ตัวอย่างที่รันได้จริง")
        st.code(lesson["demo"], language="python", line_numbers=True)
        with st.container(horizontal=True):
            if st.button("เปิดในสนามซ้อมแล้วรัน", icon=":material/play_arrow:", type="primary"):
                st.session_state["pg_code"] = lesson["demo"]
                st.session_state["pg_autorun"] = True
                st.switch_page("py_pages/playground.py")
            if st.button("ไล่ทีละบรรทัด", icon=":material/step:"):
                st.session_state["trace_code"] = lesson["demo"]
                st.session_state["trace_autorun"] = True
                st.switch_page("py_pages/tracer.py")

    if lesson.get("task"):
        st.info(f"**ลองทำ:** {lesson['task']}", icon=":material/task_alt:")

    # -- แบบทดสอบท้ายบท ----------------------------------------------------
    qids = [q for q in lesson.get("quiz", []) if q in QUESTION_BY_ID]
    if qids:
        st.subheader("ตรวจความเข้าใจ")
        for qid in qids:
            q = QUESTION_BY_ID[qid]
            key = f"lesson_q_{lesson_id}_{qid}"
            with st.container(border=True):
                st.markdown(q["q"])
                choice = st.radio("ตัวเลือก", range(len(q["options"])), key=f"{key}_pick",
                                  format_func=lambda i, o=q["options"]: o[i],
                                  index=None, label_visibility="collapsed")
                if st.button("ตรวจคำตอบ", key=f"{key}_btn", disabled=choice is None):
                    correct = choice == q["answer"]
                    if not st.session_state.get(f"{key}_answered"):
                        pg.record_quiz(d, qid, correct)
                        ui.save()
                        st.session_state[f"{key}_answered"] = True
                    st.session_state[f"{key}_result"] = correct

                if f"{key}_result" in st.session_state:
                    if st.session_state[f"{key}_result"]:
                        st.success(f"ถูกต้อง — {q['explain']}", icon=":material/check_circle:")
                    else:
                        st.error(f"ยังไม่ใช่ · คำตอบที่ถูกคือ **{q['options'][q['answer']]}**\n\n"
                                 f"{q['explain']}", icon=":material/cancel:")

# ---------------------------------------------------------------------------
# แถบข้าง
# ---------------------------------------------------------------------------
with side:
    with st.container(border=True):
        finished = lesson_id in done
        st.markdown("**สถานะบทนี้**")
        if finished:
            st.success(f"เรียนจบแล้วเมื่อ {d['lessons'][lesson_id]}",
                       icon=":material/check_circle:")
            if st.button("ยกเลิกการทำเครื่องหมาย", width="stretch"):
                pg.uncomplete_lesson(d, lesson_id)
                ui.save()
                st.rerun()
        else:
            st.caption(f"ทำเครื่องหมายเมื่ออ่านจบ จะได้รับ {pg.XP_LESSON} XP")
            if st.button("เรียนจบบทนี้แล้ว", type="primary", width="stretch",
                         icon=":material/check:"):
                pg.complete_lesson(d, lesson_id)
                ui.save()
                st.rerun()

        idx = content.lesson_index(lesson_id)
        if 0 <= idx < len(content.ALL_LESSONS) - 1:
            nxt = content.ALL_LESSONS[idx + 1]
            if st.button(f"บทถัดไป · {nxt['title']}", width="stretch",
                         icon=":material/arrow_forward:"):
                st.session_state["learn_module"] = nxt["module_id"]
                st.session_state["learn_lesson"] = nxt["id"]
                st.rerun()

    linked = ex.for_lesson(lesson_id)
    if linked:
        solved = ui.solved_code()
        with st.container(border=True):
            st.markdown("**ฝึกเขียนโค้ดของบทนี้**")
            for e in linked:
                mark = "✓ " if e["id"] in solved else ""
                if st.button(f"{mark}{e['title']}", key=f"go_{e['id']}", width="stretch"):
                    st.session_state["lab_group"] = e["group"]
                    st.session_state["lab_ex"] = e["id"]
                    st.switch_page("py_pages/code_lab.py")

    with st.container(border=True):
        st.markdown("**สารบัญโมดูลนี้**")
        for le in module["lessons"]:
            mark = "✓" if le["id"] in done else "○"
            st.caption(f"{mark} {le['title']} · {le['minutes']} นาที")
