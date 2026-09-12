"""ชุดข้อมูลฝึก — ดาวน์โหลดไปลองบนเครื่องตัวเอง พร้อมโครงสร้างและตัวอย่างโค้ด"""

import pandas as pd
import streamlit as st

from pyacad.sampledata import FILES, SCHEMA_DOC, preview, row_count

st.title("ชุดข้อมูลฝึก")
st.caption("ข้อมูลจำลองที่มีลักษณะเหมือนของจริงในโรงงาน — 8 เครื่องจักร 3 สายการผลิต "
           "เก็บรายกะตลอดเดือนมิถุนายน 2026 · ชุดเดียวกับที่ใช้ในแบบฝึกหัดและสนามซ้อม")

st.info("ข้อมูลถูกสร้างด้วยตัวสุ่มที่ล็อกค่าไว้ ผลจึงเหมือนกันทุกครั้ง "
        "ทำให้เฉลยของแบบฝึกหัดตรงกับข้อมูลเสมอ และมีความสัมพันธ์ที่ซ่อนไว้ให้ค้นหา "
        "(เช่น เครื่องที่ติดตั้งนานกว่ามักหยุดบ่อยกว่า)", icon=":material/dataset:")

for name in FILES:
    with st.container(border=True):
        head, dl = st.columns([3, 1])
        with head:
            st.subheader(name)
            st.caption(f"{row_count(name):,} แถว · "
                       f"{len(FILES[name].encode('utf-8')) / 1024:.1f} KB")
        with dl:
            st.download_button("ดาวน์โหลด", data=FILES[name].encode("utf-8-sig"),
                               file_name=name,
                               mime="text/csv" if name.endswith(".csv") else "text/plain",
                               icon=":material/download:", width="stretch",
                               key=f"dl_{name}")

        st.dataframe(pd.DataFrame(SCHEMA_DOC[name], columns=["คอลัมน์", "ชนิด", "ความหมาย"]),
                     hide_index=True, width="stretch")
        with st.expander("ดูตัวอย่างข้อมูล"):
            st.code(preview(name, 8), language="text")

st.divider()

st.subheader("โจทย์ที่ตอบได้จากข้อมูลชุดนี้")
st.markdown(
    """
- เครื่องไหนหยุดนานที่สุดทั้งเดือน และคิดเป็นกี่เปอร์เซ็นต์ของเวลาที่วางแผน
- สายการผลิตไหนมี downtime เฉลี่ยต่อกะสูงสุด
- กะเช้ากับกะบ่ายต่างกันจริงไหม หรือแค่รู้สึกไปเอง
- สาเหตุการเสียแบบไหนกินเวลาซ่อมรวมมากที่สุด (ไม่ใช่แค่เกิดบ่อยที่สุด)
- เครื่องที่ติดตั้งก่อนปี 2018 หยุดบ่อยกว่าเครื่องใหม่จริงหรือไม่ ต่างกันกี่นาทีต่อกะ
- ช่างคนไหนรับภาระงานซ่อมมากที่สุด
"""
)

st.subheader("โค้ดตั้งต้นสำหรับลองบนเครื่องตัวเอง")
st.code(
    '''import pandas as pd

prod = pd.read_csv("production.csv")
machines = pd.read_csv("machines.csv")
bd = pd.read_csv("breakdown.csv")

df = prod.merge(machines, on="machine_id", how="left")
df["run_min"] = df["planned_min"] - df["downtime_min"]
df["total_qty"] = df["good_qty"] + df["reject_qty"]

summary = (df.groupby(["line", "machine_id", "name"])
             .agg(downtime=("downtime_min", "sum"),
                  ชิ้นดี=("good_qty", "sum"),
                  ชิ้นเสีย=("reject_qty", "sum"))
             .reset_index()
             .sort_values("downtime", ascending=False))

print(summary.to_string(index=False))
summary.to_excel("รายงาน_downtime.xlsx", index=False)
''',
    language="python",
)
st.caption("วางไฟล์ CSV ที่ดาวน์โหลดไว้ในโฟลเดอร์เดียวกับสคริปต์ แล้วสั่ง `python ชื่อไฟล์.py`")
