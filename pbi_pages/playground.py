"""สนามซ้อม DAX — เขียนสูตรอิสระ ตั้ง filter context เอง และดูผลแบบ matrix เหมือนใน Power BI

หน้านี้มีไว้ให้ "เห็นด้วยตา" ว่า filter context ทำงานอย่างไร
เพราะเป็นเรื่องที่อธิบายด้วยคำพูดแล้วเข้าใจยากที่สุดใน DAX
"""

import numpy as np
import pandas as pd
import streamlit as st

from pbi import ui
from pbi.dax_engine import DaxError, evaluate

model = ui.model()

MAX_ROWS = 40      # กันไม่ให้ matrix บานจนคำนวณนาน
MAX_COLS = 12

st.title("สนามซ้อม DAX")
st.caption("เขียนสูตรอะไรก็ได้ ตั้งตัวกรองเอง แล้วดูว่าค่าเปลี่ยนอย่างไร — "
           "เหมือนวาง measure ลงใน visual จริง")


# ---------------------------------------------------------------------------
# หาคอลัมน์ที่เอามาใช้จัดกลุ่ม/กรองได้ (ค่าที่ไม่ซ้ำต้องไม่มากเกินไป)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def groupable_columns() -> dict[str, list]:
    out: dict[str, list] = {}
    for key, arr in ui.model().arr.items():
        if np.issubdtype(arr.dtype, np.datetime64):
            continue
        vals = pd.unique(arr)
        if 1 < len(vals) <= 60:
            out[key] = sorted(vals.tolist(), key=lambda v: (v is None, str(v)))
    return out


GROUPS = groupable_columns()
GROUP_KEYS = list(GROUPS)

# ---------------------------------------------------------------------------
# สูตร
# ---------------------------------------------------------------------------
PRESETS = {
    "ยอดชิ้นดี": "SUM( Production[GoodQty] )",
    "Availability": "DIVIDE( SUM( Production[RunMin] ), SUM( Production[PlannedMin] ) )",
    "จำนวนแถวที่มองเห็น": "COUNTROWS( Production )",
    "จำนวนเครื่องที่มองเห็น": "COUNTROWS( Machine )",
    "% ของยอดทั้งหมด": "DIVIDE( SUM( Production[GoodQty] ),\n"
                        "        CALCULATE( SUM( Production[GoodQty] ), ALL( Machine ) ) )",
    "เทียบปีก่อน": "CALCULATE( SUM( Production[GoodQty] ), SAMEPERIODLASTYEAR( Date[Date] ) )",
    "ตรวจว่าบริบทเห็นอะไรอยู่":
        'CONCATENATEX( VALUES( Machine[Line] ), Machine[Line], ", " )'
        ' & "  |  แถว: " & COUNTROWS( Production )',
}

top, side = st.columns([2, 1], gap="large")

with top:
    chosen = st.pills("สูตรตัวอย่าง", list(PRESETS), selection_mode="single")
    if chosen and st.session_state.get("_last_preset") != chosen:
        st.session_state["dax_scratch"] = PRESETS[chosen]
        st.session_state["_last_preset"] = chosen
        st.rerun()

    formula = st.text_area("สูตร DAX", key="dax_scratch", height=140)

with side:
    with st.container(border=True):
        st.markdown("**ตัวกรอง (filter context)**")
        st.caption("เหมือน slicer บนหน้ารายงาน — เลือกแล้วดูว่าผลเปลี่ยนไหม")
        picked = st.multiselect("คอลัมน์ที่จะกรอง", GROUP_KEYS,
                                default=st.session_state.get("pg_filter_cols", []),
                                key="pg_filter_cols")
        selections: dict[str, list] = {}
        for key in picked:
            vals = st.multiselect(key, GROUPS[key], key=f"pg_val_{key}")
            if vals:
                selections[key] = vals

if not formula.strip():
    st.info("พิมพ์สูตรด้านบน หรือกดเลือกสูตรตัวอย่าง", icon=":material/info:")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# ผลลัพธ์ค่าเดี่ยว
# ---------------------------------------------------------------------------
try:
    value = evaluate(formula, model, selections)
    err = None
except DaxError as e:
    value, err = None, str(e)
except Exception as e:                       # กันแอปล้มจากสูตรที่คาดไม่ถึง
    value, err = None, f"{type(e).__name__}: {e}"

if err:
    st.error(f"**สูตรทำงานไม่ได้**\n\n{err}", icon=":material/error:")
else:
    with st.container(border=True):
        st.metric("ผลลัพธ์ในบริบทที่ตั้งไว้", ui.fmt_value(value))
        if selections:
            st.caption("ตัวกรองที่ใช้: " +
                       " · ".join(f"{k} = {', '.join(map(str, v))}"
                                  for k, v in selections.items()))
        else:
            st.caption("ไม่มีตัวกรอง — เห็นข้อมูลทั้งหมด")

# ---------------------------------------------------------------------------
# มุมมองแบบ matrix
# ---------------------------------------------------------------------------
st.subheader("ดูแบบ matrix")
st.caption("เลือกฟิลด์ลงแถวและคอลัมน์ แล้วระบบจะคำนวณสูตรของคุณทีละช่อง "
           "โดยเพิ่มตัวกรองของหัวแถว/หัวคอลัมน์เข้าไปในบริบท — เหมือน visual จริงทุกประการ")

c1, c2 = st.columns(2)
row_key = c1.selectbox("ฟิลด์ในแถว", ["(ไม่ใช้)"] + GROUP_KEYS,
                       index=(GROUP_KEYS.index("Machine[Line]") + 1)
                       if "Machine[Line]" in GROUP_KEYS else 0)
col_key = c2.selectbox("ฟิลด์ในคอลัมน์", ["(ไม่ใช้)"] + GROUP_KEYS, index=0)

if err or row_key == "(ไม่ใช้)":
    st.stop()

row_vals = GROUPS[row_key][:MAX_ROWS]
col_vals = GROUPS[col_key][:MAX_COLS] if col_key != "(ไม่ใช้)" else [None]
if col_key != "(ไม่ใช้)" and len(GROUPS[col_key]) > MAX_COLS:
    st.caption(f"แสดงเฉพาะ {MAX_COLS} ค่าแรกของคอลัมน์ เพื่อไม่ให้คำนวณนานเกินไป")

records = []
matrix_error = None
for rv in row_vals:
    row = {row_key: rv}
    for cv in col_vals:
        sel = dict(selections)
        sel[row_key] = [rv]
        if cv is not None:
            sel[col_key] = [cv]
        try:
            row["ค่า" if cv is None else str(cv)] = evaluate(formula, model, sel)
        except (DaxError, Exception) as e:      # noqa: B014 — ตั้งใจดักทุกกรณี
            matrix_error = str(e)
            row["ค่า" if cv is None else str(cv)] = None
    records.append(row)

if matrix_error:
    st.warning(f"บางช่องคำนวณไม่ได้: {matrix_error}", icon=":material/warning:")

df = pd.DataFrame(records)
st.dataframe(df, hide_index=True)

# แถวรวม — จุดที่ทำให้เห็นว่า "ยอดรวมไม่ใช่ผลบวกของแต่ละแถวเสมอไป"
try:
    total = evaluate(formula, model, selections)
    numeric = [v for v in df.iloc[:, 1:].to_numpy().ravel()
               if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if isinstance(total, (int, float)) and not isinstance(total, bool) and numeric:
        st.caption(
            f"ยอดรวมของทั้ง matrix (คำนวณจากบริบทที่ไม่มีหัวแถว) = **{ui.fmt_value(total)}** · "
            f"ผลบวกของทุกช่อง = **{ui.fmt_value(float(sum(numeric)))}**"
        )
        if abs(float(sum(numeric)) - float(total)) > max(1e-6, abs(total) * 1e-6):
            st.info(
                "สองค่านี้ไม่เท่ากัน — ปกติมากสำหรับสูตรประเภทอัตราส่วนหรือการนับค่าไม่ซ้ำ "
                "เพราะยอดรวมถูกคำนวณใหม่ในบริบทของตัวมันเอง ไม่ได้เอาแต่ละแถวมาบวกกัน "
                "นี่คือสาเหตุที่ 'ยอดรวมของ % ไม่เท่ากับผลบวกของ %'",
                icon=":material/lightbulb:",
            )
except (DaxError, Exception):                   # noqa: B014
    pass
