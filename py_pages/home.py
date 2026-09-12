"""หน้าหลัก — สรุปความก้าวหน้าและบอกว่าควรทำอะไรต่อ"""

import streamlit as st

from pyacad import content, exercises as ex, progress as pg, ui
from pyacad.quizbank import TOTAL_QUESTIONS

d = ui.data()
done = ui.done_lessons()
solved = ui.solved_code()
pg.check_completion_badges(d, content.TOTAL_LESSONS, ex.TOTAL, ex.PROJECT_IDS)
ui.save()

st.title("Python Academy")
st.caption("เรียน → ฝึกเขียนโค้ดจริง → ระบบรันและตรวจให้ทันที → วัดผล → ทบทวนตามกำหนด")

# ---------------------------------------------------------------------------
# ตัวเลขสรุป
# ---------------------------------------------------------------------------
level_name, floor, nxt = pg.level_of(d.get("xp", 0))
ui.stat_row([
    ("บทเรียนที่จบ", f"{len(done)}/{content.TOTAL_LESSONS}", "อ่านจบและกดทำเครื่องหมายแล้ว"),
    ("แบบฝึกหัดที่ผ่าน", f"{len(solved)}/{ex.TOTAL}", "ผ่านชุดทดสอบครบทุกเคส"),
    ("XP สะสม", f"{d.get('xp', 0):,}", f"ระดับปัจจุบัน: {level_name}"),
    ("เข้าเรียนติดต่อกัน", f"{d.get('streak', 0)} วัน", f"สถิติสูงสุด {d.get('best_streak', 0)} วัน"),
])

st.divider()

left, right = st.columns([1.6, 1], gap="large")

# ---------------------------------------------------------------------------
# ทำอะไรต่อดี
# ---------------------------------------------------------------------------
with left:
    st.subheader("ทำอะไรต่อดี")

    nxt_lesson = content.next_lesson(done)
    with st.container(border=True):
        if nxt_lesson:
            st.markdown(f"**บทเรียนถัดไป · {nxt_lesson['title']}**")
            st.caption(f"{nxt_lesson['module_title']} · {nxt_lesson['minutes']} นาที · "
                       f"{nxt_lesson['goal']}")
            if st.button("ไปเรียนบทนี้", type="primary", icon=":material/menu_book:"):
                st.session_state["learn_module"] = nxt_lesson["module_id"]
                st.session_state["learn_lesson"] = nxt_lesson["id"]
                st.switch_page("py_pages/learn.py")
        else:
            st.success("เรียนจบทุกบทแล้ว — ทบทวนด้วยแบบทดสอบและลุยโจทย์งานจริงต่อได้เลย",
                       icon=":material/emoji_events:")

    nxt_ex = next((e for e in ex.EXERCISES if e["id"] not in solved), None)
    with st.container(border=True):
        if nxt_ex:
            st.markdown(f"**แบบฝึกหัดถัดไป · {nxt_ex['title']}**")
            st.caption(f"{nxt_ex['group']} · ระดับ " + "★" * nxt_ex["level"] +
                       "☆" * (4 - nxt_ex["level"]))
            if st.button("ไปเขียนโค้ด", icon=":material/code:"):
                st.session_state["lab_group"] = nxt_ex["group"]
                st.session_state["lab_ex"] = nxt_ex["id"]
                st.switch_page("py_pages/code_lab.py")
        else:
            st.success("ผ่านแบบฝึกหัดครบทุกข้อแล้ว", icon=":material/verified:")

    due = pg.due_questions(d, list(content.all_quiz_ids()))
    with st.container(border=True):
        st.markdown("**ทบทวนตามกำหนดวันนี้**")
        if due:
            st.caption(f"มีคำถามถึงกำหนดทบทวน {len(due)} ข้อ — "
                       "ทบทวนตามระยะที่ระบบกำหนดช่วยให้จำได้นานกว่าอ่านซ้ำรวดเดียว")
            if st.button(f"ทบทวน {len(due)} ข้อ", icon=":material/psychology:"):
                st.switch_page("py_pages/quiz.py")
        else:
            answered = len(d.get("quiz", {}))
            st.caption("ยังไม่มีข้อที่ถึงกำหนดทบทวนวันนี้" if answered
                       else f"ยังไม่เคยทำแบบทดสอบเลย — คลังมี {TOTAL_QUESTIONS} ข้อ")

# ---------------------------------------------------------------------------
# ความคืบหน้ารายโมดูล + เหรียญ
# ---------------------------------------------------------------------------
with right:
    st.subheader("ความคืบหน้ารายโมดูล")
    with st.container(border=True):
        for m in content.MODULES:
            n_done, n_all = content.module_progress(m, done)
            st.progress(n_done / n_all if n_all else 0.0,
                        text=f"{m['title']} ({n_done}/{n_all})")

    st.subheader("เหรียญที่ได้")
    with st.container(border=True):
        earned = d.get("badges", {})
        if not earned:
            st.caption("ยังไม่มีเหรียญ — จบบทเรียนแรกหรือผ่านแบบฝึกหัดข้อแรกก็ได้เหรียญแล้ว")
        for bid, (name, desc) in pg.BADGES.items():
            if bid in earned:
                st.markdown(f"🏅 **{name}** · {desc}")
        remain = [n for b, (n, _) in pg.BADGES.items() if b not in earned]
        if remain:
            st.caption("ยังไม่ได้: " + ", ".join(remain))

st.divider()

# ---------------------------------------------------------------------------
# ระบบนี้ทำงานอย่างไร
# ---------------------------------------------------------------------------
with st.expander("ระบบนี้ตรวจคำตอบอย่างไร", icon=":material/help:"):
    st.markdown(
        """
**ไม่ได้เทียบว่าโค้ดคุณเหมือนเฉลยไหม** แต่รันโค้ดของคุณจริง ๆ แล้วเทียบผลลัพธ์กับชุดทดสอบหลายเคส
เขียนวิธีไหนก็ได้ ถ้าผลถูกทุกเคสถือว่าผ่าน

* โค้ดถูกรันใน **โปรเซสแยก** ในโฟลเดอร์ชั่วคราวของตัวเอง มีตัวจับเวลา
  ถ้าเขียนลูปไม่รู้จบ ระบบจะหยุดให้แล้วบอกสาเหตุ — แอปไม่ค้าง
* บางข้อมี **กติกาการเขียน** เช่น "ห้ามใช้ `sum()`" ซึ่งตรวจจากโครงสร้างโค้ดจริง (AST)
  ไม่ใช่การค้นหาข้อความ — เขียน `s um` หลบไม่ได้
* ชุดทดสอบจงใจใส่ **ค่าขอบ** (ลิสต์ว่าง, หารศูนย์, ค่าที่เท่ากับเกณฑ์พอดี)
  เพราะบั๊กงานจริงเกือบทั้งหมดซ่อนอยู่ตรงนั้น

หน้า **ไล่โค้ดทีละบรรทัด** จะแสดงค่าตัวแปรทุกตัวในทุกก้าวที่โปรแกรมทำงาน
ใช้หาสาเหตุได้เร็วกว่าการใส่ `print` ทีละจุดมาก
        """
    )
