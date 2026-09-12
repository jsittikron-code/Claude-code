"""ฝึกเขียนโค้ด — เขียนแล้วระบบรันจริงและตรวจด้วยชุดทดสอบทันที"""

import pandas as pd
import streamlit as st

from pyacad import progress as pg, runner, ui
from pyacad.exercises import EXERCISES, EX_BY_ID, GROUPS, TOTAL, in_group

d = ui.data()
solved = ui.solved_code()

st.title("ฝึกเขียนโค้ด")
st.caption(f"ผ่านแล้ว {len(solved)}/{TOTAL} ข้อ · "
           "ระบบรันโค้ดของคุณจริงในโปรเซสแยก แล้วเทียบผลกับชุดทดสอบหลายเคส "
           "เขียนวิธีไหนก็ได้ถ้าผลถูกครบทุกเคส")

# ---------------------------------------------------------------------------
# เลือกข้อ
# ---------------------------------------------------------------------------
st.session_state.setdefault("lab_group", GROUPS[0])
if st.session_state["lab_group"] not in GROUPS:
    st.session_state["lab_group"] = GROUPS[0]

group = st.segmented_control(
    "ชุดแบบฝึกหัด", GROUPS, key="lab_group",
    format_func=lambda g: f"{g} ({sum(1 for e in in_group(g) if e['id'] in solved)}"
                          f"/{len(in_group(g))})",
) or st.session_state["lab_group"]

ids = [e["id"] for e in in_group(group)]
if st.session_state.get("lab_ex") not in ids:
    st.session_state["lab_ex"] = next((i for i in ids if i not in solved), ids[0])

ex_id = st.selectbox("ข้อที่", ids, key="lab_ex",
                     format_func=lambda i: ("✓ " if i in solved else "") + EX_BY_ID[i]["title"])
ex = EX_BY_ID[ex_id]

st.divider()

work, helper = st.columns([1.9, 1], gap="large")

# ---------------------------------------------------------------------------
# โจทย์และช่องเขียนโค้ด
# ---------------------------------------------------------------------------
with work:
    st.subheader(ex["title"])
    if ex.get("project"):
        st.caption(":material/workspace_premium: โจทย์งานจริง — ได้ XP มากกว่าปกติ")
    st.markdown(ex["prompt"])
    st.caption("ระดับความยาก " + "★" * ex["level"] + "☆" * (4 - ex["level"]))

    if ex.get("must_use") or ex.get("banned"):
        rules = []
        if ex.get("must_use"):
            rules.append("ต้องใช้: " + runner.rule_text(ex["must_use"]))
        if ex.get("banned"):
            rules.append("ห้ามใช้: " + runner.rule_text(ex["banned"]))
        st.info(" · ".join(rules), icon=":material/rule:")

    code = ui.code_box("โค้ดของคุณ", key=f"lab_code_{ex_id}",
                       default=ex.get("starter", ""), height=300,
                       help="กด Ctrl+Enter เพื่อบันทึกข้อความในช่องก่อนกดปุ่มตรวจ")

    with st.container(horizontal=True):
        check = st.button("ตรวจคำตอบ", type="primary", icon=":material/play_arrow:",
                          disabled=not code.strip())
        just_run = st.button("ลองรันเฉย ๆ", icon=":material/terminal:",
                             disabled=not code.strip())
        trace_it = st.button("ไล่ทีละบรรทัด", icon=":material/step:",
                             disabled=not code.strip())
        hint_open = st.toggle("ดูคำใบ้", key=f"lab_hint_{ex_id}",
                              help="เปิดคำใบ้แล้วจะได้ XP ครึ่งเดียว")
        show_answer = st.toggle("ดูเฉลย", key=f"lab_ans_{ex_id}")

    if hint_open:
        st.info(ex["hint"], icon=":material/lightbulb:")

    if show_answer:
        st.code(ex["solution"], language="python", line_numbers=True)
        st.caption(ex["teach"])

    if trace_it:
        st.session_state["trace_code"] = code
        st.session_state["trace_autorun"] = True
        st.switch_page("py_pages/tracer.py")

    # -- รันเฉย ๆ ----------------------------------------------------------
    if just_run:
        res = runner.run(code, files=ex.get("files"))
        with st.container(border=True):
            st.markdown("**ผลการรัน** (ยังไม่ได้ตรวจคำตอบ)")
            if ex.get("kind", "func") == "func":
                st.caption(f"หมายเหตุ: ข้อนี้ให้เขียนฟังก์ชัน `{ex['func']}()` "
                           "การกดรันเฉย ๆ จะเห็นผลก็ต่อเมื่อคุณเรียกใช้ฟังก์ชันเองในโค้ด")
            ui.show_output(res)

    # -- ตรวจคำตอบ ---------------------------------------------------------
    if check:
        result = runner.grade(ex, code)
        first = pg.record_code(d, ex_id, result["ok"], bool(hint_open), code,
                               project=bool(ex.get("project")))
        ui.save()

        if result["error"]:
            st.error(f"**โค้ดทำงานไม่ผ่าน**\n\n{result['error']}", icon=":material/error:")
            st.caption(ui.explain_error(result["error"]))
        for problem in result["rules"]:
            st.warning(problem, icon=":material/rule:")

        if result["ok"]:
            base = pg.XP_PROJECT_SOLVED if ex.get("project") else pg.XP_CODE_SOLVED
            gained = base // (2 if hint_open else 1)
            if first:
                st.success(f"ผ่านครบทุกเคส — ได้รับ {gained} XP", icon=":material/check_circle:")
                st.balloons()
            else:
                st.success("ผ่านครบทุกเคส", icon=":material/check_circle:")
            st.caption(ex["teach"])
        elif not result["error"] and result["rows"]:
            n_pass = sum(1 for r in result["rows"] if r["pass"])
            st.error(f"ผ่าน {n_pass}/{len(result['rows'])} เคส — ดูตารางด้านล่างว่าเคสไหนยังไม่ตรง",
                     icon=":material/cancel:")

        if result["rows"]:
            df = pd.DataFrame([{
                "เคสทดสอบ": r["case"],
                "ผลของคุณ": r["got"],
                "ผลที่ควรได้": r["expect"],
                "ผ่าน": "✓" if r["pass"] else "✗",
            } for r in result["rows"]])
            st.dataframe(df, hide_index=True, width="stretch")

        if result["stdout"]:
            with st.expander("สิ่งที่โค้ดพิมพ์ออกมาระหว่างตรวจ"):
                st.code(result["stdout"], language="text")

    rec = d["code"].get(ex_id)
    if rec:
        st.caption(f"ส่งคำตอบมาแล้ว {rec['attempts']} ครั้ง"
                   + (f" · ผ่านครั้งแรกเมื่อ {rec['first_solved']}"
                      if rec.get("first_solved") else ""))

# ---------------------------------------------------------------------------
# แถบข้าง — ข้อมูลประกอบ
# ---------------------------------------------------------------------------
with helper:
    if ex.get("files"):
        with st.container(border=True):
            st.markdown("**ไฟล์ที่มีให้ใช้ในข้อนี้**")
            st.caption("ไฟล์เหล่านี้ถูกวางไว้ในโฟลเดอร์เดียวกับโค้ดของคุณตอนรัน "
                       "เปิดด้วยชื่อไฟล์สั้น ๆ ได้เลย")
            for name, text in ex["files"].items():
                with st.expander(name):
                    head = "\n".join(text.splitlines()[:6])
                    st.code(head + "\n...", language="text")

    with st.container(border=True):
        st.markdown("**เคสทดสอบที่จะใช้ตรวจ**")
        st.caption("ระบบจะเรียกโค้ดของคุณด้วยค่าเหล่านี้และเทียบผลลัพธ์")
        for c in ex["cases"]:
            if ex.get("kind", "func") == "func":
                label = c.get("label") or (
                    f"{ex['func']}({', '.join(repr(a) for a in c.get('args', []))})")
                st.caption(f"`{label}` → `{c['expect']!r}`")
            else:
                stdin = (c.get("stdin") or "").replace("\n", " ⏎ ").strip()
                st.caption(f"ป้อน `{stdin or '(ไม่มี)'}` → พิมพ์ `{c['expect']}`")

    with st.container(border=True):
        st.markdown("**เคล็ดลับตอนติด**")
        st.caption(
            "1. กด 'ลองรันเฉย ๆ' แล้ว print ค่าระหว่างทางออกมาดู\n\n"
            "2. กด 'ไล่ทีละบรรทัด' เพื่อดูว่าตัวแปรเปลี่ยนค่าที่ก้าวไหน\n\n"
            "3. อ่านชื่อชนิดข้อผิดพลาดก่อนเสมอ — มันบอกสาเหตุไว้แล้ว"
        )

    with st.container(border=True):
        st.markdown("**ความคืบหน้าทุกชุด**")
        for g in GROUPS:
            items = in_group(g)
            n = sum(1 for e in items if e["id"] in solved)
            st.progress(n / len(items), text=f"{g} ({n}/{len(items)})")
