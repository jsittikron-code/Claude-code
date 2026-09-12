"""ไล่โค้ดทีละบรรทัด — ดูว่าตัวแปรทุกตัวเปลี่ยนค่าอย่างไรในทุกก้าวที่โปรแกรมทำงาน

นี่คือเครื่องมือหาบั๊กที่ได้ผลที่สุดสำหรับผู้เริ่มต้น เพราะแทนที่จะเดาว่า
"ลูปนี้น่าจะทำอะไร" ก็เห็นค่าจริงของทุกตัวแปรในทุกก้าวไปเลย
"""

import pandas as pd
import streamlit as st

from pyacad import progress as pg, runner, ui

DEFAULT = '''# ตัวอย่าง: บั๊กคลาสสิก — ลองไล่ดูว่า total ถูกรีเซ็ตที่ก้าวไหน
downtimes = [45, 120, 30]

total = 0
for d in downtimes:
    total += d
    print("สะสมแล้ว", total)

print("รวมทั้งหมด", total)
'''

d = ui.data()

st.title("ไล่โค้ดทีละบรรทัด")
st.caption("ระบบรันโค้ดพร้อมบันทึกทุกก้าว แล้วให้คุณเลื่อนดูย้อนหลังได้ว่าบรรทัดไหนทำให้ค่าเปลี่ยนอย่างไร "
           f"(บันทึกได้สูงสุด {runner.MAX_TRACE_STEPS} ก้าว)")

code = ui.code_box("โค้ดที่จะไล่", key="trace_code", default=DEFAULT, height=260)
stdin = st.text_input("ค่าที่ป้อนให้ input() (คั่นหลายค่าด้วยการเว้นบรรทัดไม่ได้ที่นี่ ใช้ค่าเดียว)",
                      key="trace_stdin", placeholder="เว้นว่างถ้าไม่ได้ใช้ input()")

with st.container(horizontal=True):
    go = st.button("เริ่มไล่โค้ด", type="primary", icon=":material/play_arrow:",
                   disabled=not code.strip())
    if st.button("ล้าง", icon=":material/delete:"):
        st.session_state["trace_code"] = DEFAULT
        st.session_state.pop("trace_result", None)
        st.rerun()

if go or st.session_state.pop("trace_autorun", False):
    with st.spinner("กำลังรันและบันทึกทุกก้าว..."):
        st.session_state["trace_result"] = runner.trace(code, stdin=stdin + "\n" if stdin else "")
        st.session_state["trace_src"] = code
        st.session_state["trace_step"] = 1
    pg.record_trace(d)
    ui.save()

result = st.session_state.get("trace_result")

if not result:
    st.info("กด **เริ่มไล่โค้ด** เพื่อดูการทำงานทีละก้าว", icon=":material/info:")
    st.stop()

if result.get("error") and not result.get("events"):
    st.error(f"รันไม่สำเร็จ: {result['error']}", icon=":material/error:")
    st.caption(ui.explain_error(result["error"]))
    st.stop()

events = result.get("events", [])
src_lines = st.session_state.get("trace_src", code).splitlines()

if not events:
    st.warning("ไม่มีก้าวการทำงานที่บันทึกได้ (โค้ดอาจไม่มีคำสั่งที่ทำงานจริง)")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# ตัวควบคุมการเลื่อนก้าว
# ---------------------------------------------------------------------------
n = len(events)
st.session_state.setdefault("trace_step", 1)
st.session_state["trace_step"] = min(max(1, st.session_state["trace_step"]), n)

with st.container(horizontal=True):
    if st.button("⏮ ก้าวแรก"):
        st.session_state["trace_step"] = 1
        st.rerun()
    if st.button("◀ ก่อนหน้า"):
        st.session_state["trace_step"] = max(1, st.session_state["trace_step"] - 1)
        st.rerun()
    if st.button("ถัดไป ▶"):
        st.session_state["trace_step"] = min(n, st.session_state["trace_step"] + 1)
        st.rerun()
    if st.button("ก้าวสุดท้าย ⏭"):
        st.session_state["trace_step"] = n
        st.rerun()

step = st.slider("ก้าวที่", 1, n, key="trace_step") if n > 1 else 1
cur = events[step - 1]
prev = events[step - 2] if step >= 2 else {"vars": {}}

if result.get("truncated"):
    st.warning(f"บันทึกได้ถึง {n} ก้าวแล้วหยุด — โค้ดอาจวนหลายรอบเกินกว่าจะเก็บครบ",
               icon=":material/warning:")

left, right = st.columns([1.4, 1], gap="large")

# ---------------------------------------------------------------------------
# โค้ดพร้อมตัวชี้บรรทัดปัจจุบัน
# ---------------------------------------------------------------------------
with left:
    where = "กำลังจะทำ" if cur["event"] == "line" else "จบฟังก์ชัน"
    scope = "โปรแกรมหลัก" if cur["func"] == "<module>" else f"ในฟังก์ชัน {cur['func']}()"
    st.markdown(f"**ก้าวที่ {step}/{n} · {where}บรรทัด {cur['line']} · {scope}**")

    annotated = []
    for i, line in enumerate(src_lines, start=1):
        mark = "▶" if i == cur["line"] else " "
        annotated.append(f"{mark} {i:>3} | {line}")
    st.code("\n".join(annotated), language="text")

    if cur["event"] == "return" and cur.get("ret"):
        st.info(f"ฟังก์ชัน `{cur['func']}()` คืนค่า `{cur['ret']}`",
                icon=":material/keyboard_return:")

    st.markdown("**สิ่งที่พิมพ์ออกมาจนถึงก้าวนี้**")
    printed = (result.get("output") or "")[:cur.get("outlen", 0)]
    st.code(printed or "(ยังไม่มีผลลัพธ์)", language="text")

# ---------------------------------------------------------------------------
# ตารางตัวแปร
# ---------------------------------------------------------------------------
with right:
    st.markdown("**ค่าของตัวแปร ณ ก้าวนี้**")
    now_vars, before = cur.get("vars", {}), prev.get("vars", {})
    if not now_vars:
        st.caption("ยังไม่มีตัวแปรในขอบเขตนี้")
    else:
        rows = []
        for name, value in now_vars.items():
            if name not in before:
                status = "🆕 เพิ่งเกิด"
            elif before[name] != value:
                status = f"🔄 เปลี่ยนจาก {before[name]}"
            else:
                status = ""
            rows.append({"ตัวแปร": name, "ค่า": value, "การเปลี่ยนแปลง": status})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    changed = [k for k, v in now_vars.items() if before.get(k) != v]
    if changed:
        st.success("ก้าวนี้ทำให้ " + ", ".join(f"`{c}`" for c in changed) + " เปลี่ยนค่า",
                   icon=":material/change_circle:")

    with st.container(border=True):
        st.markdown("**สรุปการทำงานทั้งหมด**")
        st.caption(f"ทำงานไปทั้งหมด {n} ก้าว")
        hot = pd.Series([e["line"] for e in events]).value_counts().head(5)
        st.caption("บรรทัดที่ถูกทำงานบ่อยที่สุด (มักคือบรรทัดในลูป)")
        st.dataframe(
            pd.DataFrame({"บรรทัด": hot.index, "จำนวนครั้ง": hot.values}),
            hide_index=True, width="stretch",
        )
        if result.get("error"):
            st.error(f"จบด้วยข้อผิดพลาด: {result['error']}", icon=":material/error:")
