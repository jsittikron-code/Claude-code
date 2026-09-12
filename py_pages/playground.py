"""สนามซ้อม — เขียนโค้ดอะไรก็ได้แล้วกดรัน พร้อมไฟล์ข้อมูลตัวอย่างให้ใช้"""

import streamlit as st

from pyacad import runner, ui
from pyacad.sampledata import FILES, SCHEMA_DOC, preview, row_count

DEFAULT = '''# สนามซ้อม — พิมพ์อะไรก็ได้แล้วกดรัน (มีไฟล์ตัวอย่างให้ใช้ ดูแถบขวา)
machines = ["M01", "M03", "M06"]
downtimes = [45, 120, 0]

for m, d in zip(machines, downtimes):
    print(f"{m}: หยุด {d} นาที")

print("รวม", sum(downtimes), "นาที")
'''

st.title("สนามซ้อม")
st.caption("โค้ดถูกรันจริงในโปรเซสแยกที่มีตัวจับเวลา — เขียนลูปไม่รู้จบก็ไม่ทำให้แอปค้าง "
           "และไฟล์ที่เขียนออกจะอยู่ในโฟลเดอร์ชั่วคราวที่ถูกลบทิ้งหลังรันเสร็จ")

work, side = st.columns([1.9, 1], gap="large")

with work:
    code = ui.code_box("โค้ด", key="pg_code", default=DEFAULT, height=340)

    stdin = st.text_area("ค่าที่ป้อนให้ input() (หนึ่งบรรทัดต่อหนึ่งครั้ง)",
                         key="pg_stdin", height=70,
                         placeholder="เว้นว่างไว้ถ้าโค้ดไม่ได้ใช้ input()")

    with st.container(horizontal=True):
        run_now = st.button("รันโค้ด", type="primary", icon=":material/play_arrow:",
                            disabled=not code.strip())
        trace_it = st.button("ไล่ทีละบรรทัด", icon=":material/step:",
                             disabled=not code.strip())
        use_files = st.toggle("แนบไฟล์ข้อมูลตัวอย่าง", key="pg_files", value=True,
                              help="วาง production.csv, machines.csv, breakdown.csv, "
                                   "machine_log.txt ไว้ข้างโค้ด")
        if st.button("ล้างโค้ด", icon=":material/delete:"):
            st.session_state["pg_code"] = DEFAULT
            st.rerun()

    if trace_it:
        st.session_state["trace_code"] = code
        st.session_state["trace_autorun"] = True
        st.switch_page("py_pages/tracer.py")

    if run_now or st.session_state.pop("pg_autorun", False):
        res = runner.run(code, stdin=stdin, files=FILES if use_files else None)
        with st.container(border=True):
            ui.show_output(res)

with side:
    with st.container(border=True):
        st.markdown("**ไฟล์ข้อมูลที่แนบให้**")
        st.caption("เปิดด้วยชื่อสั้น ๆ ได้เลย เช่น `pd.read_csv(\"production.csv\")`")
        for name in FILES:
            with st.expander(f"{name} ({row_count(name):,} แถว)"):
                st.code(preview(name, 6), language="text")
                for col, kind, desc in SCHEMA_DOC[name]:
                    st.caption(f"`{col}` · {kind} · {desc}")

    with st.container(border=True):
        st.markdown("**ตัวอย่างที่ลองได้ทันที**")
        snippets = {
            "อ่าน CSV ด้วย pandas":
                'import pandas as pd\n\n'
                'df = pd.read_csv("production.csv")\n'
                'print(df.shape)\n'
                'print(df.head())\n'
                'print(df.groupby("machine_id")["downtime_min"].sum())\n',
            "สรุปยอดด้วย dict":
                'import csv\n\n'
                'totals = {}\n'
                'with open("production.csv", encoding="utf-8", newline="") as fh:\n'
                '    for row in csv.DictReader(fh):\n'
                '        m = row["machine_id"]\n'
                '        totals[m] = totals.get(m, 0) + int(row["downtime_min"])\n\n'
                'for m, v in sorted(totals.items(), key=lambda kv: kv[1], reverse=True):\n'
                '    print(m, v)\n',
            "อ่านไฟล์ล็อก":
                'with open("machine_log.txt", encoding="utf-8") as fh:\n'
                '    for line in fh:\n'
                '        if "ALARM" in line:\n'
                '            print(line.strip())\n',
            "ดูข้อผิดพลาดว่าหน้าตาเป็นอย่างไร":
                'values = [45, 120]\n'
                'print(values[5])   # IndexError\n',
        }
        for label, snippet in snippets.items():
            if st.button(label, key=f"snip_{label}", width="stretch"):
                st.session_state["pg_code"] = snippet
                st.rerun()
