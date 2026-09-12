"""ฝึกเขียน DAX — เขียนสูตรแล้วระบบตรวจให้ทันที โดยรันจริงบนโมเดลตัวอย่าง"""

import pandas as pd
import streamlit as st

from pbi import progress as pg, ui
from pbi.exercises import DAX_BY_ID, DAX_EXERCISES, DAX_GROUPS, TOTAL_DAX, grade_dax
from pbi.model_data import SCHEMA_DOC

d = ui.data()
model = ui.model()

solved = {k for k, v in d["dax"].items() if v.get("solved")}

st.title("ฝึกเขียน DAX")
st.caption(f"ผ่านแล้ว {len(solved)}/{TOTAL_DAX} ข้อ · "
           "ระบบตรวจโดยรันสูตรของคุณเทียบกับเฉลยภายใต้ตัวกรองหลายชุด "
           "สูตรที่ถูกเฉพาะตอนไม่มีตัวกรองจะไม่ผ่าน")

# ---------------------------------------------------------------------------
# เลือกข้อ
# ---------------------------------------------------------------------------
st.session_state.setdefault("dax_group", DAX_GROUPS[0])
if st.session_state["dax_group"] not in DAX_GROUPS:
    st.session_state["dax_group"] = DAX_GROUPS[0]

group = st.segmented_control(
    "ชุดแบบฝึกหัด", DAX_GROUPS, key="dax_group",
    format_func=lambda g: f"{g}  ({sum(1 for e in DAX_EXERCISES if e['group'] == g and e['id'] in solved)}"
                          f"/{sum(1 for e in DAX_EXERCISES if e['group'] == g)})",
) or st.session_state["dax_group"]

in_group = [e for e in DAX_EXERCISES if e["group"] == group]
ids = [e["id"] for e in in_group]
if st.session_state.get("dax_ex") not in ids:
    st.session_state["dax_ex"] = next((i for i in ids if i not in solved), ids[0])

ex_id = st.selectbox(
    "ข้อที่", ids, key="dax_ex",
    format_func=lambda i: ("✓ " if i in solved else "") + f"{DAX_BY_ID[i]['title']}",
)
ex = DAX_BY_ID[ex_id]

st.divider()

work, helper = st.columns([1.9, 1], gap="large")

# ---------------------------------------------------------------------------
# โจทย์และช่องเขียนสูตร
# ---------------------------------------------------------------------------
with work:
    st.subheader(ex["title"])
    st.markdown(ex["prompt"])
    st.caption("ระดับความยาก " + "★" * ex["level"] + "☆" * (4 - ex["level"]))

    formula = st.text_area(
        "สูตร DAX ของคุณ", key=f"dax_input_{ex_id}", height=170,
        placeholder="พิมพ์สูตรที่นี่ เช่น  SUM( Production[GoodQty] )\n\n"
                    "จะใส่ชื่อ measure นำหน้าแบบ  ชื่อ = สูตร  ก็ได้ ระบบตัดให้เอง",
    )

    with st.container(horizontal=True):
        check = st.button("ตรวจคำตอบ", type="primary", icon=":material/play_arrow:",
                          disabled=not formula.strip())
        hint_open = st.toggle("ดูคำใบ้", key=f"hint_{ex_id}",
                              help="เปิดคำใบ้แล้วจะได้ XP ครึ่งเดียว")
        show_answer = st.toggle("ดูเฉลย", key=f"ans_{ex_id}")

    if hint_open:
        st.info(ex["hint"], icon=":material/lightbulb:")

    if show_answer:
        st.code(ex["solution"], language="dax")
        st.caption(ex["teach"])

    if check:
        result = grade_dax(ex, formula, model)
        first = pg.record_dax(d, ex_id, result["ok"], bool(hint_open))
        ui.save()

        if result["error"]:
            st.error(f"**สูตรทำงานไม่ได้**\n\n{result['error']}", icon=":material/error:")
        elif result["ok"]:
            gained = pg.XP_DAX_SOLVED // (2 if hint_open else 1)
            if first:
                st.success(f"ถูกต้องทุกบริบท — ได้รับ {gained} XP",
                           icon=":material/check_circle:")
                st.balloons()
            else:
                st.success("ถูกต้องทุกบริบท", icon=":material/check_circle:")
            st.caption(ex["teach"])
        else:
            st.error("ผลลัพธ์ยังไม่ตรงกับเฉลย — ดูตารางด้านล่างว่าต่างกันที่บริบทใด",
                     icon=":material/cancel:")

        if result["rows"]:
            df = pd.DataFrame([{
                "บริบทที่ทดสอบ": r["ctx"],
                "ผลของคุณ": ui.fmt_value(r["user"]),
                "ผลที่ควรได้": ui.fmt_value(r["expect"]),
                "ตรงกัน": "✓" if r["pass"] else "✗",
            } for r in result["rows"]])
            st.dataframe(df, hide_index=True)
            fails = [r["ctx"] for r in result["rows"] if not r["pass"]]
            if fails and not result["ok"]:
                st.caption(
                    "สูตรที่ถูกเฉพาะบางบริบทมักแปลว่าใช้ CALCULATE หรือตระกูล ALL ไม่ตรงระดับ "
                    f"— ข้อนี้พลาดที่: {', '.join(fails)}"
                )

    rec = d["dax"].get(ex_id)
    if rec:
        st.caption(f"ส่งคำตอบมาแล้ว {rec['attempts']} ครั้ง"
                   + (f" · ผ่านครั้งแรกเมื่อ {rec['first_solved']}" if rec.get("first_solved") else ""))

# ---------------------------------------------------------------------------
# แถบข้าง — โครงสร้างข้อมูลที่ใช้อ้างอิง
# ---------------------------------------------------------------------------
with helper:
    with st.container(border=True):
        st.markdown("**ตารางและคอลัมน์ที่ใช้ได้**")
        st.caption("คลิกที่ชื่อตารางเพื่อดูคอลัมน์ทั้งหมด")
        for tname, cols in SCHEMA_DOC.items():
            with st.expander(f"{tname} ({len(cols)} คอลัมน์)"):
                st.dataframe(
                    pd.DataFrame(cols, columns=["คอลัมน์", "ชนิด", "ความหมาย"]),
                    hide_index=True, height=min(300, 36 + 35 * len(cols)),
                )

    with st.container(border=True):
        st.markdown("**measure สำเร็จรูป**")
        st.caption("อ้างถึงได้ด้วย [ชื่อ] เช่น `[Availability] * 100`")
        for name, dax in model.measures.items():
            st.caption(f"`[{name}]` = {dax}")

    with st.container(border=True):
        st.markdown("**ข้อจำกัดของเครื่องจำลอง**")
        st.caption(
            "ยังไม่รองรับ context transition (เรียก measure หรือ SUM ซ้อนใน SUMX), "
            "RANKX, TOPN และ DAX Query — สูตรกลุ่มนี้ต้องไปทดสอบบน Power BI Desktop จริง "
            "ส่วนที่เหลือให้ตัวเลขตรงกับ Power BI"
        )
