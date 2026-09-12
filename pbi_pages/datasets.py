"""ชุดข้อมูลฝึก — ดาวน์โหลดไปทำใน Power BI Desktop จริง พร้อมคู่มือแล็บทีละขั้น

ตัวเลขในไฟล์ที่ดาวน์โหลด เป็นชุดเดียวกับที่แอปนี้ใช้ตรวจแบบฝึกหัด
ผู้เรียนจึงเทียบผลของ Power BI จริงกับคำตอบในแอปได้ตรงกันทุกหลัก
"""

import pandas as pd
import streamlit as st

from pbi import ui
from pbi.dax_engine import evaluate
from pbi.model_data import SCHEMA_DOC, to_csv_bytes, to_excel_bytes

frames = ui.frames()
model = ui.model()

st.title("ชุดข้อมูลฝึก")
st.caption("โรงงานผลิตเฟอร์นิเจอร์ · star schema 1 fact + 4 dimension · "
           f"ตาราง Production {len(frames['Production']):,} แถว "
           "ครอบคลุม ม.ค. 2025 – มิ.ย. 2026")

# ---------------------------------------------------------------------------
# ดาวน์โหลด
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown("**ดาวน์โหลด**")
    st.caption("ไฟล์ Excel หนึ่งไฟล์มีครบทั้ง 5 ตาราง (แยกชีต) — เหมาะกับการฝึก Get Data → Excel "
               "ส่วนไฟล์ CSV แยกตาราง เหมาะกับการฝึกรวมไฟล์จากโฟลเดอร์")

    st.download_button(
        "ดาวน์โหลด Excel ครบทุกตาราง", to_excel_bytes(frames),
        file_name="PowerBI_Academy_ชุดข้อมูลฝึก.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary", icon=":material/download:",
    )

    with st.container(horizontal=True):
        for name, df in frames.items():
            st.download_button(
                f"{name}.csv", to_csv_bytes(df), file_name=f"{name}.csv",
                mime="text/csv", key=f"dl_{name}",
            )

# ---------------------------------------------------------------------------
# โครงสร้างข้อมูล
# ---------------------------------------------------------------------------
st.subheader("โครงสร้างข้อมูล")

st.code("""            Date  ────┐
                       │
Machine ───▶  Production  ◀─── Product
                       │
            Shift  ────┘

ความสัมพันธ์ทุกเส้นเป็นแบบ 1 : *  ทิศทางเดียว (จาก dimension ไป fact)
  Date[Date]           1 : *  Production[Date]
  Machine[MachineID]   1 : *  Production[MachineID]
  Product[ProductID]   1 : *  Production[ProductID]
  Shift[ShiftID]       1 : *  Production[ShiftID]""", language=None)

tabs = st.tabs(list(SCHEMA_DOC))
for tab, (tname, cols) in zip(tabs, SCHEMA_DOC.items()):
    with tab:
        st.dataframe(pd.DataFrame(cols, columns=["คอลัมน์", "ชนิด", "ความหมาย"]),
                     hide_index=True)
        st.caption(f"ตัวอย่างข้อมูล {len(frames[tname]):,} แถว")
        st.dataframe(frames[tname].head(8), hide_index=True)

# ---------------------------------------------------------------------------
# คู่มือแล็บ
# ---------------------------------------------------------------------------
st.subheader("คู่มือแล็บ — ทำตามทีละขั้นใน Power BI Desktop")

LABS = [
    ("แล็บ 1 · นำเข้าและตั้งโมเดล (30 นาที)", """
1. `Get Data → Excel` เลือกไฟล์ที่ดาวน์โหลด แล้วติ๊กทั้ง 5 ชีต กด **Transform Data**
2. ตรวจชนิดข้อมูลทุกคอลัมน์ โดยเฉพาะ `Date` ต้องเป็น Date และ `UnitPrice` ต้องเป็นทศนิยม
3. ตั้งชื่อ query ให้ตรงกับชื่อตาราง แล้วกด **Close & Apply**
4. ไปที่ **Model view** ตรวจว่า Power BI สร้างความสัมพันธ์ให้ครบ 4 เส้นหรือไม่
   ถ้าขาด ให้ลากเชื่อมเอง และตรวจให้เป็น 1:\\* ทิศทางเดียวทุกเส้น
5. เลือกตาราง `Date` → Table tools → **Mark as date table** เลือกคอลัมน์ `Date`
6. เลือกคอลัมน์ `MonthYear` → Column tools → **Sort by column** → เลือก `YearMonth`
7. ซ่อนคอลัมน์คีย์ทุกตัว (`MachineID`, `ProductID`, `ShiftID`, `ProdID`, `YearMonth`)
8. ปิด **Auto date/time** ที่ File → Options → Data Load

> เช็กจุดสำคัญ: สร้าง visual แบบตาราง ใส่ `Machine[Line]` กับ `SUM(GoodQty)`
> ถ้าแต่ละสายได้ตัวเลขไม่เท่ากัน แปลว่าความสัมพันธ์ทำงานถูกแล้ว
"""),
    ("แล็บ 2 · สร้าง measure ชุด OEE (45 นาที)", """
สร้างตาราง `_Measures` (Home → Enter data → ตารางเปล่า) แล้วสร้าง measure ตามลำดับนี้

```dax
Planned Minutes = SUM( Production[PlannedMin] )
Run Minutes     = SUM( Production[RunMin] )
Down Minutes    = SUM( Production[DownMin] )
Good Qty        = SUM( Production[GoodQty] )
Total Qty       = [Good Qty] + SUM( Production[RejectQty] )

Availability % = DIVIDE( [Run Minutes], [Planned Minutes] )
Theoretical Qty = SUMX( Production, Production[RunMin] * RELATED( Machine[StdRate] ) )
Performance %  = DIVIDE( [Total Qty], [Theoretical Qty] )
Quality %      = DIVIDE( [Good Qty], [Total Qty] )
OEE %          = [Availability %] * [Performance %] * [Quality %]
```

ตั้ง Format ของ measure ที่เป็น % ให้เป็น Percentage ทศนิยม 1 ตำแหน่ง

**ตรวจคำตอบ**: ตารางด้านล่างคือค่าที่ถูกต้อง คำนวณจากเอนจินของแอปนี้
ถ้าตัวเลขใน Power BI ของคุณตรงกันทุกหลัก แปลว่าโมเดลและ measure ถูกต้องแล้ว
"""),
    ("แล็บ 3 · รายงานสามหน้า (60 นาที)", """
**หน้า 1 — ภาพรวม**
- การ์ด KPI 4 ใบ: `OEE %`, `Availability %`, `Performance %`, `Quality %`
- กราฟเส้น: แกน `Date[MonthYear]` ค่า `OEE %` แล้วเพิ่ม Constant line ที่ 0.75 (Analytics pane)
- กราฟแท่งแนวนอน: แกน `Machine[MachineName]` ค่า `OEE %` **เรียงจากน้อยไปมาก**
- slicer: `Date[MonthYear]` และ `Machine[Line]`

**หน้า 2 — เจาะรายเครื่อง**
- ลาก `Machine[MachineName]` ลงช่อง **Drill through**
- กราฟเส้นรายวัน + ตาราง 10 กะที่ OEE ต่ำสุด

**หน้า 3 — วิเคราะห์เวลาหยุด**
- matrix: แถว `Production[DownReason]` คอลัมน์ `Date[MonthYear]` ค่า `Down Minutes`
- กราฟพาเรโต: แท่ง `Down Minutes` เรียงมากไปน้อย + เส้นสะสม

**เก็บงาน**
- ตั้งหัวข้อ visual ให้เป็นข้อสรุป ไม่ใช่ชื่อฟิลด์
- เพิ่มหน้า `ข้อมูลรายงาน` บอกที่มาข้อมูล นิยาม measure และเจ้าของรายงาน
"""),
    ("แล็บ 4 · เผยแพร่และความปลอดภัย (30 นาที)", """
1. **Publish** ขึ้น workspace (อย่าใช้ My workspace)
2. ตั้ง **Scheduled refresh** พร้อมใส่อีเมลแจ้งเตือนเมื่อ refresh ล้มเหลว
3. สร้าง RLS: Modeling → Manage roles → role ชื่อ `หัวหน้าสาย A`
   ใส่สูตรที่ตาราง `Machine`: `[Line] = "Line A"`
4. ทดสอบด้วย **View as** ใน Desktop แล้วตรวจซ้ำด้วย **Test as role** บน Service
5. เผยแพร่เป็น **App** แทนการเชิญคนเข้ามาที่ workspace โดยตรง

> จำไว้ว่า RLS ไม่มีผลกับคนที่มีสิทธิ์ Admin/Member/Contributor ใน workspace
> ผู้ใช้ปลายทางต้องเป็น Viewer เท่านั้น
"""),
]

for title, body in LABS:
    with st.expander(title):
        st.markdown(body)
        if title.startswith("แล็บ 2"):
            checks = {
                "Planned Minutes": "SUM( Production[PlannedMin] )",
                "Run Minutes": "SUM( Production[RunMin] )",
                "Down Minutes": "SUM( Production[DownMin] )",
                "Good Qty": "SUM( Production[GoodQty] )",
                "Total Qty": "SUM( Production[GoodQty] ) + SUM( Production[RejectQty] )",
                "Availability %": "DIVIDE( SUM( Production[RunMin] ), SUM( Production[PlannedMin] ) )",
                "Theoretical Qty": "SUMX( Production, Production[RunMin] * RELATED( Machine[StdRate] ) )",
                "Performance %": "DIVIDE( SUM( Production[GoodQty] ) + SUM( Production[RejectQty] ), "
                                 "SUMX( Production, Production[RunMin] * RELATED( Machine[StdRate] ) ) )",
                "Quality %": "DIVIDE( SUM( Production[GoodQty] ), "
                             "SUM( Production[GoodQty] ) + SUM( Production[RejectQty] ) )",
                "OEE %": ("DIVIDE( SUM( Production[RunMin] ), SUM( Production[PlannedMin] ) ) * "
                          "DIVIDE( SUM( Production[GoodQty] ) + SUM( Production[RejectQty] ), "
                          "SUMX( Production, Production[RunMin] * RELATED( Machine[StdRate] ) ) ) * "
                          "DIVIDE( SUM( Production[GoodQty] ), "
                          "SUM( Production[GoodQty] ) + SUM( Production[RejectQty] ) )"),
            }
            scopes = {"ทั้งโรงงาน (ไม่กรอง)": {}}
            for line in ("Line A", "Line B", "Line C", "Line D"):
                scopes[f"เฉพาะ {line}"] = {"Machine[Line]": [line]}
            scope = st.selectbox("ตรวจคำตอบในขอบเขต", list(scopes), key="lab2_scope")
            sel = scopes[scope]
            rows = []
            for name, dax in checks.items():
                v = evaluate(dax, model, sel)
                pct = name.endswith("%")
                rows.append({"measure": name,
                             "ค่าที่ถูกต้อง": f"{v:.2%}" if pct else f"{v:,.1f}"})
            st.dataframe(pd.DataFrame(rows), hide_index=True)
