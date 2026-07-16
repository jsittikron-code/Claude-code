"""
OEE Dashboard สำหรับโรงงานผลิตแผ่นไม้ MDF
-------------------------------------------------
คำนวณและแสดงผล OEE (Overall Equipment Effectiveness)
โดยแยกเป็นองค์ประกอบ 3 ส่วน: Availability, Performance, Quality

รันด้วย:  streamlit run app.py
"""

import pandas as pd
import streamlit as st
import altair as alt

# ---------------------------------------------------------------------------
# ตั้งค่าหน้าเพจ
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="OEE Dashboard - โรงงาน MDF",
    page_icon="🏭",
    layout="wide",
)

DEFAULT_DATA_FILE = "mock_oee_data.xlsx"
REQUIRED_COLUMNS = [
    "Date",
    "Planned_Time",
    "Downtime",
    "Target_Speed",
    "Actual_Output",
    "Defects",
]

# สีธีมของแดชบอร์ด
COLOR_OEE = "#2563eb"          # น้ำเงิน
COLOR_AVAILABILITY = "#16a34a"  # เขียว
COLOR_PERFORMANCE = "#ea580c"   # ส้ม
COLOR_QUALITY = "#9333ea"       # ม่วง


# ---------------------------------------------------------------------------
# ฟังก์ชันโหลดและคำนวณข้อมูล
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data(source) -> pd.DataFrame:
    """อ่านไฟล์ Excel แล้วคืน DataFrame ที่คำนวณ OEE เรียบร้อยแล้ว"""
    df = pd.read_excel(source, engine="openpyxl")

    # ตรวจสอบว่ามีคอลัมน์ครบ
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            "ไฟล์ Excel ขาดคอลัมน์: " + ", ".join(missing)
            + "\nต้องมีคอลัมน์: " + ", ".join(REQUIRED_COLUMNS)
        )

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    # แปลงเป็นตัวเลข และกันค่าที่ผิดปกติ
    numeric_cols = [c for c in REQUIRED_COLUMNS if c != "Date"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=numeric_cols)

    # --- คำนวณ OEE ---
    # เวลาที่เดินเครื่องจริง (Run Time) = เวลาที่วางแผน - เวลาที่หยุด
    df["Run_Time"] = (df["Planned_Time"] - df["Downtime"]).clip(lower=0)

    # 1) Availability = Run Time / Planned Time
    df["Availability"] = (df["Run_Time"] / df["Planned_Time"]).where(
        df["Planned_Time"] > 0, 0
    )

    # 2) Performance = ผลผลิตจริง / ผลผลิตอุดมคติ
    #    ผลผลิตอุดมคติ = Target_Speed (แผ่น/ชม.) x Run_Time (ชม.)
    ideal_output = df["Target_Speed"] * (df["Run_Time"] / 60.0)
    df["Ideal_Output"] = ideal_output
    df["Performance"] = (df["Actual_Output"] / ideal_output).where(
        ideal_output > 0, 0
    )

    # 3) Quality = ของดี / ผลผลิตจริง
    good_output = df["Actual_Output"] - df["Defects"]
    df["Good_Output"] = good_output
    df["Quality"] = (good_output / df["Actual_Output"]).where(
        df["Actual_Output"] > 0, 0
    )

    # OEE = A x P x Q
    df["OEE"] = df["Availability"] * df["Performance"] * df["Quality"]

    # กันค่าเกินขอบเขต 0-1 (เผื่อข้อมูลจริงมี noise)
    for col in ["Availability", "Performance", "Quality", "OEE"]:
        df[col] = df[col].clip(lower=0, upper=1)

    return df


def kpi_card(title: str, value: float, color: str, benchmark: float | None = None):
    """แสดงการ์ด KPI แบบ HTML สวย ๆ"""
    pct = value * 100
    bench_html = ""
    if benchmark is not None:
        diff = pct - benchmark * 100
        arrow = "▲" if diff >= 0 else "▼"
        diff_color = "#16a34a" if diff >= 0 else "#dc2626"
        bench_html = (
            f"<div style='font-size:0.8rem;color:{diff_color};margin-top:4px;'>"
            f"{arrow} {abs(diff):.1f}% เทียบเป้า World-Class</div>"
        )

    # หมายเหตุ: ต้องเขียน HTML แบบไม่มีการเยื้องหน้าบรรทัด (no indent)
    # มิฉะนั้น Markdown ของ Streamlit จะตีความว่าเป็น code block แล้วโชว์เป็นตัวหนังสือ
    card_html = (
        f'<div style="background: linear-gradient(135deg, {color}15 0%, {color}05 100%);'
        f'border-left: 6px solid {color}; border-radius: 12px; padding: 18px 20px;'
        f'box-shadow: 0 2px 8px rgba(0,0,0,0.06);">'
        f'<div style="font-size:0.95rem;color:#64748b;font-weight:600;">{title}</div>'
        f'<div style="font-size:2.4rem;font-weight:800;color:{color};line-height:1.1;">{pct:.1f}%</div>'
        f'{bench_html}'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# ส่วนหัว + ตัวอัปโหลดไฟล์
# ---------------------------------------------------------------------------
st.title("🏭 OEE Dashboard — โรงงานผลิตแผ่นไม้ MDF")
st.caption(
    "Overall Equipment Effectiveness = Availability × Performance × Quality"
)

with st.sidebar:
    st.header("⚙️ ข้อมูลนำเข้า")
    uploaded = st.file_uploader(
        "อัปโหลดไฟล์ Excel (.xlsx)",
        type=["xlsx"],
        help="รูปแบบคอลัมน์: " + ", ".join(REQUIRED_COLUMNS),
    )
    st.markdown("---")
    st.markdown(
        "**เกณฑ์อ้างอิง (World-Class)**\n"
        "- OEE ≥ 85%\n"
        "- Availability ≥ 90%\n"
        "- Performance ≥ 95%\n"
        "- Quality ≥ 99.9%"
    )

# เลือกแหล่งข้อมูล: ไฟล์ที่อัปโหลด หรือไฟล์ตัวอย่าง
try:
    if uploaded is not None:
        data = load_data(uploaded)
        st.success(f"โหลดไฟล์ที่อัปโหลดสำเร็จ: {uploaded.name} ({len(data)} วัน)")
    else:
        data = load_data(DEFAULT_DATA_FILE)
        st.info(
            f"กำลังแสดงข้อมูลตัวอย่างจาก `{DEFAULT_DATA_FILE}` "
            "— อัปโหลดไฟล์ของคุณที่แถบด้านซ้ายเพื่อดูข้อมูลจริง"
        )
except FileNotFoundError:
    st.error(
        f"ไม่พบไฟล์ `{DEFAULT_DATA_FILE}` — กรุณารัน `python generate_mock_data.py` "
        "เพื่อสร้างข้อมูลตัวอย่าง หรืออัปโหลดไฟล์ของคุณเอง"
    )
    st.stop()
except ValueError as e:
    st.error(str(e))
    st.stop()

# ---------------------------------------------------------------------------
# การ์ดสรุป KPI (ค่าเฉลี่ยรวมทั้งช่วง)
# ---------------------------------------------------------------------------
avg_availability = data["Availability"].mean()
avg_performance = data["Performance"].mean()
avg_quality = data["Quality"].mean()
avg_oee = data["OEE"].mean()

st.subheader("📊 สรุป KPI เฉลี่ยทั้งช่วง")
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_card("OEE รวม", avg_oee, COLOR_OEE, benchmark=0.85)
with c2:
    kpi_card("Availability", avg_availability, COLOR_AVAILABILITY, benchmark=0.90)
with c3:
    kpi_card("Performance", avg_performance, COLOR_PERFORMANCE, benchmark=0.95)
with c4:
    kpi_card("Quality", avg_quality, COLOR_QUALITY, benchmark=0.999)

# ตัวเลขสรุปการผลิต
st.markdown("")
m1, m2, m3, m4 = st.columns(4)
m1.metric("ผลผลิตรวม (แผ่น)", f"{int(data['Actual_Output'].sum()):,}")
m2.metric("ของดีรวม (แผ่น)", f"{int(data['Good_Output'].sum()):,}")
m3.metric("ของเสียรวม (แผ่น)", f"{int(data['Defects'].sum()):,}")
m4.metric("เวลาหยุดรวม (นาที)", f"{int(data['Downtime'].sum()):,}")

st.markdown("---")

# ---------------------------------------------------------------------------
# กราฟเส้นแนวโน้ม OEE รายวัน
# ---------------------------------------------------------------------------
st.subheader("📈 แนวโน้ม OEE รายวัน")

# เตรียมข้อมูลแบบ long เพื่อพล็อตหลายเส้น
plot_df = data[
    ["Date", "OEE", "Availability", "Performance", "Quality"]
].melt(id_vars="Date", var_name="ตัวชี้วัด", value_name="ค่า")
plot_df["ค่า"] = plot_df["ค่า"] * 100  # เป็นเปอร์เซ็นต์

color_scale = alt.Scale(
    domain=["OEE", "Availability", "Performance", "Quality"],
    range=[COLOR_OEE, COLOR_AVAILABILITY, COLOR_PERFORMANCE, COLOR_QUALITY],
)

show_components = st.checkbox("แสดงองค์ประกอบทั้ง 3 ส่วนบนกราฟด้วย", value=True)
if not show_components:
    plot_df = plot_df[plot_df["ตัวชี้วัด"] == "OEE"]

line = (
    alt.Chart(plot_df)
    .mark_line(point=True, strokeWidth=3)
    .encode(
        x=alt.X("Date:T", title="วันที่"),
        y=alt.Y("ค่า:Q", title="เปอร์เซ็นต์ (%)", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("ตัวชี้วัด:N", scale=color_scale, title="ตัวชี้วัด"),
        tooltip=[
            alt.Tooltip("Date:T", title="วันที่"),
            alt.Tooltip("ตัวชี้วัด:N", title="ตัวชี้วัด"),
            alt.Tooltip("ค่า:Q", title="ค่า (%)", format=".1f"),
        ],
    )
    .properties(height=380)
    .interactive()
)

# เส้นเป้าหมาย OEE 85%
target_line = (
    alt.Chart(pd.DataFrame({"y": [85]}))
    .mark_rule(color="#94a3b8", strokeDash=[6, 4])
    .encode(y="y:Q")
)

st.altair_chart(line + target_line, width="stretch")

# ---------------------------------------------------------------------------
# ตารางข้อมูลรายละเอียด
# ---------------------------------------------------------------------------
with st.expander("📋 ดูตารางข้อมูลรายวันแบบละเอียด"):
    display_df = data.copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
    for col in ["Availability", "Performance", "Quality", "OEE"]:
        display_df[col] = (display_df[col] * 100).round(1)
    st.dataframe(
        display_df[
            [
                "Date",
                "Planned_Time",
                "Downtime",
                "Run_Time",
                "Target_Speed",
                "Actual_Output",
                "Defects",
                "Availability",
                "Performance",
                "Quality",
                "OEE",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption("หน่วย: เวลาเป็นนาที, ความเร็วเป็นแผ่น/ชม., A/P/Q/OEE เป็น %")
