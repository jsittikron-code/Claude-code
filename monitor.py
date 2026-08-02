"""
ระบบ Monitoring กระบวนการผลิต — โรงงาน MDF
-------------------------------------------------
อ่านรายงาน OEE รายเครื่องจักรรายวัน (รูปแบบชีต Report1 เช่นไฟล์ เดือน1-6.xlsx)
แล้วแสดงผลแบบ 5 มุมมอง:
  1. ภาพรวมโรงงาน   — KPI รวม + แนวโน้มรายวัน/รายเดือน
  2. แจ้งเตือน        — เครื่องจักรที่ OEE ต่ำกว่าเกณฑ์ / แนวโน้มแย่ลง
  3. รายเครื่องจักร   — เจาะดูทีละเครื่อง
  4. เวลาสูญเสีย      — Pareto สาเหตุการหยุดเครื่อง
  5. ข้อมูลรายวัน     — ตารางดิบ + ดาวน์โหลด CSV

รันด้วย:  streamlit run monitor.py
"""

import io
import os

import altair as alt
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# ตั้งค่าหน้าเพจ
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Production Monitoring — โรงงาน MDF",
    page_icon="📡",
    layout="wide",
)

# แหล่งข้อมูลหลัก เรียงตามลำดับความสำคัญ — ใช้ไฟล์แรกที่มีอยู่และอ่านได้
# ไฟล์แรกคือฐานข้อมูลหลักบน OneDrive: อัปเดตไฟล์นั้นแล้วกดรีเฟรชหน้า ทุกคนเห็นข้อมูลใหม่ทันที
DATA_SOURCES = [
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD\ฝ่ายซ่อมบำรุงรักษา"
    r"\3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx",
    "เดือน1-6.xlsx",
]

# คอลัมน์ที่ต้องมีในไฟล์ (รูปแบบชีต Report1)
REQUIRED_COLUMNS = [
    "MC",
    "Description",
    "Trans_date",
    "เวลาทำงาน/วัน",
    "เวลาสูญเสีย/วัน",
    "เวลาทำงานจริง/วัน",
    "Avaliable (%)",
    "Performance (%)",
    "Quality (%)",
    "OEE (%)",
]

# หมวดเวลาสูญเสีย (ชื่อคอลัมน์ -> ป้ายภาษาไทย)
# ความหมายรหัสอ้างอิงจากชีต B001/BP001/P0001 ในไฟล์ฐานข้อมูลหลัก
LOSS_CATEGORIES = {
    "Setup": "ตั้งเครื่อง / เปลี่ยนรุ่น",
    "Break_time_p": "PM เชิงป้องกัน",
    "Break_time_bp": "ซ่อมแซม (Maintenance)",
    "Break_time_b": "เครื่องเสีย (Breakdown)",
    "Break_time_noemp": "ไม่มีพนักงาน",
    "Break_time_S": "เวลาหยุด (S)",
    "Others": "อื่น ๆ",
}

# กลุ่มเครื่องจักรตามรหัสนำหน้า MC
GROUP_NAMES = {
    "CT": "เครื่องตัด",
    "DL": "เครื่องเจาะ / CNC",
    "EG": "เครื่องปิดขอบ",
    "CO": "บู้ทพ่นสี",
    "PO": "เครื่องขัดเงา",
    "MO": "เครื่องเพลาตั้ง",
    "MS": "งานขัดด้วยมือ",
    "MB": "งานปัดเงา",
    "LA": "เครื่องปิดผิว",
    "PR": "เครื่อง Membrane",
    "SF": "เครื่องห่อโค้ง",
    "AL": "ประกอบอลูมิเนียม",
    "AD": "หน่วยงานรับ/ส่งงาน",
    "SKL": "หน่วยงานฝีมือ",
    "RP": "ซ่อมสร้าง / ซ่อมบำรุง",
}

# สีตามชุด palette ที่ผ่านการตรวจ colorblind-safe แล้ว
COLOR_OEE = "#2a78d6"           # น้ำเงิน
COLOR_AVAILABILITY = "#eb6834"  # ส้ม
COLOR_PERFORMANCE = "#1baf7a"   # เขียวอมฟ้า
COLOR_QUALITY = "#eda100"       # เหลือง
CAT_COLORS = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#008300", "#4a3aa7", "#e34948",
]
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_CRITICAL = "#d03b3b"

METRIC_COLS = {
    "OEE": "OEE (%)",
    "Availability": "Avaliable (%)",
    "Performance": "Performance (%)",
    "Quality": "Quality (%)",
}
METRIC_COLOR = {
    "OEE": COLOR_OEE,
    "Availability": COLOR_AVAILABILITY,
    "Performance": COLOR_PERFORMANCE,
    "Quality": COLOR_QUALITY,
}


# ---------------------------------------------------------------------------
# โหลดและเตรียมข้อมูล
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="กำลังอ่านไฟล์ข้อมูล...")
def load_data(source, file_mtime: float | None = None) -> pd.DataFrame:
    # file_mtime ไม่ได้ใช้ในฟังก์ชัน แต่เป็นส่วนหนึ่งของ cache key —
    # พอไฟล์บนดิสก์ถูกแก้ไข ค่านี้เปลี่ยน cache เก่าจะถูกทิ้งและอ่านไฟล์ใหม่
    xl = pd.ExcelFile(source, engine="openpyxl")
    sheet = "Report1" if "Report1" in xl.sheet_names else 0
    df = pd.read_excel(xl, sheet_name=sheet)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            "ไฟล์ขาดคอลัมน์: " + ", ".join(missing)
            + "\nต้องเป็นรายงานรูปแบบชีต Report1 (เหมือนไฟล์ เดือน1-6.xlsx)"
        )

    df = df.copy()
    df["Trans_date"] = pd.to_datetime(df["Trans_date"], errors="coerce")
    df = df.dropna(subset=["Trans_date"])

    numeric_cols = (
        ["เวลาทำงาน/วัน", "เวลาสูญเสีย/วัน", "เวลาทำงานจริง/วัน"]
        + list(METRIC_COLS.values())
        + [c for c in LOSS_CATEGORIES if c in df.columns]
    )
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ค่าเปอร์เซ็นต์บางแถวเกิน 100 (เช่น ผลิตได้เกิน Cap) — ตัดเพดานที่ 100
    for col in METRIC_COLS.values():
        df[col] = df[col].clip(lower=0, upper=100)

    df["Month"] = df["Trans_date"].dt.to_period("M").dt.to_timestamp()
    # ใช้หมวดหมู่เครื่องที่โรงงานจัดไว้ในไฟล์ก่อน ถ้าไม่มีค่อยเดาจากรหัสนำหน้า MC
    prefix_group = (
        df["MC"].astype(str).str.extract(r"^([A-Za-z]+)")[0].str.upper()
        .map(lambda g: GROUP_NAMES.get(g, g))
    )
    if "หมวดหมู่เครื่อง" in df.columns:
        df["Group"] = df["หมวดหมู่เครื่อง"].astype(str).str.strip().replace(
            {"": None, "nan": None}
        ).fillna(prefix_group)
    else:
        df["Group"] = prefix_group
    df["Machine"] = df["MC"].astype(str) + " — " + df["Description"].astype(str).str.strip()

    return df.sort_values(["MC", "Trans_date"]).reset_index(drop=True)


def weighted_pct(df: pd.DataFrame, col: str, wcol: str = "เวลาทำงาน/วัน") -> float:
    """ค่าเฉลี่ยถ่วงน้ำหนักด้วยเวลาทำงาน (กันวันเวลาน้อยมาบิดค่าเฉลี่ย)"""
    w = df[wcol]
    total = w.sum()
    return float((df[col] * w).sum() / total) if total > 0 else 0.0


def daily_weighted(df: pd.DataFrame) -> pd.DataFrame:
    """สรุปค่า A/P/Q/OEE ถ่วงน้ำหนักรายวัน (รวมทุกเครื่องที่กรองไว้)"""
    rows = []
    for d, g in df.groupby("Trans_date"):
        row = {"Trans_date": d}
        for name, col in METRIC_COLS.items():
            row[name] = weighted_pct(g, col)
        rows.append(row)
    return pd.DataFrame(rows)


def machine_summary(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """สรุปรายเครื่อง: OEE ถ่วงน้ำหนัก + สถานะเทียบเกณฑ์"""
    rows = []
    for (mc, machine), g in df.groupby(["MC", "Machine"]):
        row = {
            "MC": mc,
            "Machine": machine,
            "จำนวนวัน": g["Trans_date"].nunique(),
            "เวลาสูญเสียรวม (นาที)": g["เวลาสูญเสีย/วัน"].sum(),
        }
        for name, col in METRIC_COLS.items():
            row[name] = weighted_pct(g, col)
        rows.append(row)
    out = pd.DataFrame(rows)

    def status(oee: float) -> str:
        if oee >= threshold:
            return "🟢 ปกติ"
        if oee >= threshold * 0.75:
            return "🟡 เฝ้าระวัง"
        return "🔴 วิกฤต"

    out["สถานะ"] = out["OEE"].map(status)
    return out.sort_values("OEE").reset_index(drop=True)


def kpi_card(title: str, value: float, color: str,
             target: float | None = None, unit: str = "%"):
    """การ์ด KPI (เขียน HTML บรรทัดเดียว ห้ามมี indent มิฉะนั้น Streamlit จะโชว์เป็น code block)"""
    value_text = f"{value:.1f}%" if unit == "%" else f"{value:,.0f} {unit}"
    target_html = ""
    if target is not None:
        diff = value - target
        arrow = "▲" if diff >= 0 else "▼"
        diff_color = "#006300" if diff >= 0 else STATUS_CRITICAL
        target_html = (
            f"<div style='font-size:0.8rem;color:{diff_color};margin-top:4px;'>"
            f"{arrow} {abs(diff):.1f}% เทียบเกณฑ์ {target:.0f}%</div>"
        )
    card_html = (
        f'<div style="background: linear-gradient(135deg, {color}15 0%, {color}05 100%);'
        f'border-left: 6px solid {color}; border-radius: 12px; padding: 16px 20px;'
        f'box-shadow: 0 2px 8px rgba(0,0,0,0.06);">'
        f'<div style="font-size:0.9rem;color:#52514e;font-weight:600;">{title}</div>'
        f'<div style="font-size:2.2rem;font-weight:800;color:{color};line-height:1.15;">{value_text}</div>'
        f'{target_html}'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


def trend_chart(daily: pd.DataFrame, metrics: list[str], threshold: float) -> alt.Chart:
    plot_df = daily.melt(id_vars="Trans_date", value_vars=metrics,
                         var_name="ตัวชี้วัด", value_name="ค่า")
    color_scale = alt.Scale(
        domain=list(METRIC_COLS.keys()),
        range=[METRIC_COLOR[m] for m in METRIC_COLS],
    )
    line = (
        alt.Chart(plot_df)
        .mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=30))
        .encode(
            x=alt.X("Trans_date:T", title="วันที่"),
            y=alt.Y("ค่า:Q", title="เปอร์เซ็นต์ (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("ตัวชี้วัด:N", scale=color_scale, title="ตัวชี้วัด"),
            tooltip=[
                alt.Tooltip("Trans_date:T", title="วันที่", format="%d/%m/%Y"),
                alt.Tooltip("ตัวชี้วัด:N", title="ตัวชี้วัด"),
                alt.Tooltip("ค่า:Q", title="ค่า (%)", format=".1f"),
            ],
        )
        .properties(height=360)
        .interactive()
    )
    rule = (
        alt.Chart(pd.DataFrame({"y": [threshold]}))
        .mark_rule(color="#898781", strokeDash=[6, 4])
        .encode(y="y:Q")
    )
    return line + rule


# ---------------------------------------------------------------------------
# ส่วนหัว + แถบควบคุมด้านข้าง
# ---------------------------------------------------------------------------
st.title("📡 ระบบ Monitoring กระบวนการผลิต — โรงงาน MDF")
st.caption("ติดตาม OEE รายเครื่องจักร · แจ้งเตือนเครื่องต่ำกว่าเกณฑ์ · วิเคราะห์เวลาสูญเสีย")

with st.sidebar:
    st.header("⚙️ ข้อมูลนำเข้า")
    uploaded = st.file_uploader(
        "อัปโหลดรายงาน OEE (.xlsx) — ดูชั่วคราว",
        type=["xlsx"],
        help="ไฟล์ที่อัปโหลดตรงนี้เห็นเฉพาะเบราว์เซอร์ของคุณ ไม่กระทบคนอื่น "
             "ถ้าต้องการให้ทุกคนเห็น ให้บันทึกทับไฟล์ฐานข้อมูลหลักบน OneDrive",
    )

@st.fragment(run_every="30s")
def watch_data_file():
    """เช็คทุก 30 วินาทีว่าไฟล์ฐานข้อมูลถูกแก้ไขหรือยัง — ถ้าใช่ รีเฟรชหน้าอัตโนมัติ"""
    sig = tuple(
        os.path.getmtime(p) if os.path.exists(p) else None for p in DATA_SOURCES
    )
    prev = st.session_state.get("_data_sig")
    st.session_state["_data_sig"] = sig
    if prev is not None and sig != prev:
        st.rerun(scope="app")


data = None
source_name = None
source_mtime = None
load_errors = []
if uploaded is not None:
    try:
        data = load_data(uploaded)
        source_name = f"{uploaded.name} (เห็นเฉพาะคุณ)"
    except ValueError as e:
        st.error(str(e))
        st.stop()
else:
    # ไล่อ่านตามลำดับใน DATA_SOURCES — ข้ามไฟล์ที่ไม่มีหรืออ่านไม่ได้ (เช่น ถูกเปิดล็อกอยู่)
    for path in DATA_SOURCES:
        if not os.path.exists(path):
            continue
        try:
            data = load_data(path, os.path.getmtime(path))
            source_name = os.path.basename(path)
            source_mtime = pd.Timestamp.fromtimestamp(os.path.getmtime(path))
            break
        except Exception as e:
            load_errors.append(f"{os.path.basename(path)}: {e}")
    if data is None:
        st.error(
            "อ่านไฟล์ข้อมูลไม่ได้เลย — กรุณาอัปโหลดรายงานที่แถบด้านซ้าย\n\n"
            + "\n".join(load_errors)
        )
        st.stop()
    # เฝ้าดูไฟล์ฐานข้อมูล: ถ้าไฟล์ถูกอัปเดต หน้าจอทุกคนจะรีเฟรชเองภายใน ~30 วินาที
    watch_data_file()

with st.sidebar:
    st.success(f"ข้อมูล: {source_name}\n\n{len(data):,} แถว · {data['MC'].nunique()} เครื่องจักร")
    if st.button("🔄 โหลดข้อมูลใหม่", help="ล้าง cache แล้วอ่านไฟล์จากดิสก์ใหม่ทันที"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.header("🔍 ตัวกรอง")

    min_d = data["Trans_date"].min().date()
    max_d = data["Trans_date"].max().date()
    date_range = st.date_input(
        "ช่วงวันที่",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
    )

    groups = sorted(data["Group"].dropna().unique())
    sel_groups = st.multiselect("กลุ่มเครื่องจักร", groups, default=[])

    st.markdown("---")
    threshold = st.slider("เกณฑ์แจ้งเตือน OEE (%)", 20, 90, 50, step=5,
                          help="เครื่องที่ OEE ต่ำกว่าเกณฑ์นี้จะขึ้นในหน้าแจ้งเตือน")

# กรองข้อมูลตามที่เลือก
filtered = data
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["Trans_date"] >= pd.Timestamp(start))
        & (filtered["Trans_date"] <= pd.Timestamp(end))
    ]
if sel_groups:
    filtered = filtered[filtered["Group"].isin(sel_groups)]

if filtered.empty:
    st.warning("ไม่มีข้อมูลในช่วง/กลุ่มที่เลือก — ลองปรับตัวกรอง")
    st.stop()

loss_cols = [c for c in LOSS_CATEGORIES if c in filtered.columns]

# ---------------------------------------------------------------------------
# แท็บหลัก
# ---------------------------------------------------------------------------
tab_daily, tab_overview, tab_alert, tab_machine, tab_loss, tab_table = st.tabs(
    ["📅 ดูตามวัน", "🏭 ภาพรวมโรงงาน", "🚨 แจ้งเตือน", "⚙️ รายเครื่องจักร",
     "⏱ เวลาสูญเสีย", "📋 ข้อมูลรายวัน"]
)

# --- 0) ดูตามวัน — เลือกวันเดียว เห็นสถานะทุกเครื่องของวันนั้น ---
with tab_daily:
    # ใช้ข้อมูลทั้งหมด (กรองเฉพาะกลุ่มเครื่อง) เพื่อให้เลือกวันไหนก็ได้
    # ไม่ผูกกับช่วงวันที่ใน sidebar
    day_pool = data[data["Group"].isin(sel_groups)] if sel_groups else data
    available_days = sorted(day_pool["Trans_date"].dt.date.unique())
    latest_day = available_days[-1]

    # เก็บวันที่เลือกไว้ใน session state และกันไม่ให้หลุดช่วง
    # (เผื่อเปลี่ยนตัวกรองกลุ่มแล้วช่วงวันที่ที่มีข้อมูลเปลี่ยนไป)
    stored = st.session_state.get("_sel_day", latest_day)
    if not (available_days[0] <= stored <= latest_day):
        stored = latest_day
    st.session_state["_sel_day"] = stored

    head_l, head_r = st.columns([3, 2])
    with head_l:
        sel_day = st.date_input(
            "เลือกวันที่ต้องการดู",
            min_value=available_days[0],
            max_value=latest_day,
            key="_sel_day",
        )
    with head_r:
        st.markdown("")
        # ใช้ on_click: callback ทำงานก่อนสร้าง widget รอบถัดไป
        # (แก้ค่าตรง ๆ หลัง widget ถูกสร้างแล้วจะ error)
        st.button(
            "⏭ ไปวันล่าสุดในฐานข้อมูล",
            width="stretch",
            on_click=lambda: st.session_state.update(_sel_day=latest_day),
        )
        if source_mtime is not None:
            st.caption(
                f"ฐานข้อมูลอัปเดตล่าสุด: {source_mtime:%d/%m/%Y %H:%M} น. · "
                f"ข้อมูลถึงวันที่ {latest_day:%d/%m/%Y}"
            )

    day_df = day_pool[day_pool["Trans_date"].dt.date == sel_day]

    if day_df.empty:
        st.warning(
            f"ไม่มีข้อมูลของวันที่ {sel_day:%d/%m/%Y} — อาจเป็นวันหยุด "
            "หรือยังไม่ได้บันทึกข้อมูลเข้าฐานข้อมูล"
        )
    else:
        # หาวันทำงานก่อนหน้าที่มีข้อมูล เพื่อเทียบว่าดีขึ้น/แย่ลง
        prev_days = [d for d in available_days if d < sel_day]
        prev_df = (
            day_pool[day_pool["Trans_date"].dt.date == prev_days[-1]]
            if prev_days else pd.DataFrame()
        )
        prev_oee = weighted_pct(prev_df, "OEE (%)") if not prev_df.empty else None

        st.markdown(f"### สรุปผลวันที่ {sel_day:%d/%m/%Y}")
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            kpi_card("OEE วันนี้", weighted_pct(day_df, "OEE (%)"),
                     COLOR_OEE, target=threshold)
        with d2:
            kpi_card("Availability", weighted_pct(day_df, "Avaliable (%)"),
                     COLOR_AVAILABILITY)
        with d3:
            kpi_card("Performance", weighted_pct(day_df, "Performance (%)"),
                     COLOR_PERFORMANCE)
        with d4:
            kpi_card("Quality", weighted_pct(day_df, "Quality (%)"), COLOR_QUALITY)

        n1, n2, n3, n4 = st.columns(4)
        n1.metric("เครื่องที่เดินวันนี้", f"{day_df['MC'].nunique()} เครื่อง")
        n2.metric("เวลาสูญเสียรวม (ชม.)", f"{day_df['เวลาสูญเสีย/วัน'].sum() / 60:,.1f}")
        if "จำนวน(ชิ้น)/วัน" in day_df.columns:
            n3.metric("ชิ้นงานที่ผลิตได้", f"{day_df['จำนวน(ชิ้น)/วัน'].sum():,.0f}")
        if prev_oee is not None:
            today_oee = weighted_pct(day_df, "OEE (%)")
            n4.metric(
                f"เทียบ {prev_days[-1]:%d/%m}",
                f"{today_oee:.1f}%",
                delta=f"{today_oee - prev_oee:+.1f}%",
            )

        st.markdown("---")
        day_summary = machine_summary(day_df, threshold)
        s1, s2, s3 = st.columns(3)
        s1.metric("🔴 วิกฤต", f"{(day_summary['สถานะ'] == '🔴 วิกฤต').sum()} เครื่อง")
        s2.metric("🟡 เฝ้าระวัง", f"{(day_summary['สถานะ'] == '🟡 เฝ้าระวัง').sum()} เครื่อง")
        s3.metric("🟢 ปกติ", f"{(day_summary['สถานะ'] == '🟢 ปกติ').sum()} เครื่อง")

        st.subheader("📊 OEE ทุกเครื่องในวันนี้ (เรียงจากต่ำสุด)")
        status_color = alt.Scale(
            domain=["🔴 วิกฤต", "🟡 เฝ้าระวัง", "🟢 ปกติ"],
            range=[STATUS_CRITICAL, STATUS_WARNING, STATUS_GOOD],
        )
        day_bar = (
            alt.Chart(day_summary)
            .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=16)
            .encode(
                y=alt.Y("MC:N", sort=alt.EncodingSortField("OEE", order="ascending"),
                        title=None),
                x=alt.X("OEE:Q", title="OEE (%)", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("สถานะ:N", scale=status_color, title="สถานะ"),
                tooltip=[
                    alt.Tooltip("Machine:N", title="เครื่องจักร"),
                    alt.Tooltip("OEE:Q", title="OEE (%)", format=".1f"),
                    alt.Tooltip("Availability:Q", title="Availability (%)", format=".1f"),
                    alt.Tooltip("Performance:Q", title="Performance (%)", format=".1f"),
                    alt.Tooltip("เวลาสูญเสียรวม (นาที):Q", title="เวลาสูญเสีย (นาที)",
                                format=",.0f"),
                ],
            )
            .properties(height=max(300, 22 * len(day_summary)))
        )
        day_rule = alt.Chart(pd.DataFrame({"x": [threshold]})).mark_rule(
            color="#898781", strokeDash=[6, 4]
        ).encode(x="x:Q")
        st.altair_chart(day_bar + day_rule, width="stretch")

        if loss_cols:
            st.subheader("⏱ เวลาสูญเสียของวันนี้ แยกตามสาเหตุ")
            day_loss = (
                day_df[loss_cols].sum().rename(index=LOSS_CATEGORIES).reset_index()
            )
            day_loss.columns = ["สาเหตุ", "นาที"]
            day_loss = day_loss[day_loss["นาที"] > 0].sort_values("นาที", ascending=False)
            if day_loss.empty:
                st.info("วันนี้ไม่มีการบันทึกเวลาสูญเสียแยกสาเหตุ")
            else:
                day_pareto = (
                    alt.Chart(day_loss)
                    .mark_bar(color=COLOR_OEE, cornerRadiusTopRight=4,
                              cornerRadiusBottomRight=4, size=22)
                    .encode(
                        y=alt.Y("สาเหตุ:N", sort="-x", title=None),
                        x=alt.X("นาที:Q", title="นาทีรวม"),
                        tooltip=[alt.Tooltip("สาเหตุ:N"),
                                 alt.Tooltip("นาที:Q", format=",.0f")],
                    )
                    .properties(height=60 + 34 * len(day_loss))
                )
                st.altair_chart(day_pareto, width="stretch")

        st.subheader("📋 รายละเอียดรายเครื่องของวันนี้")
        day_table = day_summary[
            ["สถานะ", "MC", "Machine", "OEE", "Availability", "Performance",
             "Quality", "เวลาสูญเสียรวม (นาที)"]
        ].copy()
        for c in ["OEE", "Availability", "Performance", "Quality"]:
            day_table[c] = day_table[c].round(1)
        st.dataframe(day_table, width="stretch", hide_index=True, height=420)

        idle = sorted(set(day_pool["MC"].unique()) - set(day_df["MC"].unique()))
        if idle:
            with st.expander(f"⚪ เครื่องที่ไม่มีข้อมูลวันนี้ ({len(idle)} เครื่อง)"):
                st.write(", ".join(idle))
                st.caption("อาจเป็นเครื่องที่ไม่ได้เดิน หรือยังไม่ได้บันทึกข้อมูลเข้าระบบ")

# --- 1) ภาพรวมโรงงาน ---
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("OEE รวม", weighted_pct(filtered, "OEE (%)"), COLOR_OEE, target=threshold)
    with c2:
        kpi_card("Availability", weighted_pct(filtered, "Avaliable (%)"), COLOR_AVAILABILITY)
    with c3:
        kpi_card("Performance", weighted_pct(filtered, "Performance (%)"), COLOR_PERFORMANCE)
    with c4:
        kpi_card("Quality", weighted_pct(filtered, "Quality (%)"), COLOR_QUALITY)
    st.caption("ค่าเฉลี่ยถ่วงน้ำหนักด้วยเวลาทำงาน/วัน ของทุกเครื่องในช่วงที่กรอง")

    st.markdown("")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("เครื่องจักรที่มีข้อมูล", f"{filtered['MC'].nunique()} เครื่อง")
    m2.metric("เวลาทำงานรวม (ชม.)", f"{filtered['เวลาทำงาน/วัน'].sum() / 60:,.0f}")
    m3.metric("เวลาสูญเสียรวม (ชม.)", f"{filtered['เวลาสูญเสีย/วัน'].sum() / 60:,.0f}")
    if "จำนวน(ชิ้น)/วัน" in filtered.columns:
        m4.metric("ชิ้นงานรวม (ชิ้น)", f"{filtered['จำนวน(ชิ้น)/วัน'].sum():,.0f}")

    st.markdown("---")
    st.subheader("📈 แนวโน้มรายวัน (รวมทุกเครื่องที่กรอง)")
    show_all = st.checkbox("แสดง Availability / Performance / Quality ด้วย", value=True)
    metrics = list(METRIC_COLS.keys()) if show_all else ["OEE"]
    st.altair_chart(trend_chart(daily_weighted(filtered), metrics, threshold),
                    width="stretch")

    st.subheader("📆 OEE รายเดือน")
    monthly = []
    for m, g in filtered.groupby("Month"):
        monthly.append({"Month": m, "OEE": weighted_pct(g, "OEE (%)")})
    monthly = pd.DataFrame(monthly)
    bar = (
        alt.Chart(monthly)
        .mark_bar(color=COLOR_OEE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=42)
        .encode(
            x=alt.X("yearmonth(Month):T", title="เดือน"),
            y=alt.Y("OEE:Q", title="OEE (%)", scale=alt.Scale(domain=[0, 100])),
            tooltip=[
                alt.Tooltip("yearmonth(Month):T", title="เดือน", format="%m/%Y"),
                alt.Tooltip("OEE:Q", title="OEE (%)", format=".1f"),
            ],
        )
        .properties(height=280)
    )
    label = bar.mark_text(dy=-8, color="#0b0b0b").encode(
        text=alt.Text("OEE:Q", format=".1f")
    )
    rule = alt.Chart(pd.DataFrame({"y": [threshold]})).mark_rule(
        color="#898781", strokeDash=[6, 4]
    ).encode(y="y:Q")
    st.altair_chart(bar + label + rule, width="stretch")

# --- 2) แจ้งเตือน ---
with tab_alert:
    summary = machine_summary(filtered, threshold)
    n_crit = (summary["สถานะ"] == "🔴 วิกฤต").sum()
    n_warn = (summary["สถานะ"] == "🟡 เฝ้าระวัง").sum()
    n_ok = (summary["สถานะ"] == "🟢 ปกติ").sum()

    a1, a2, a3 = st.columns(3)
    with a1:
        kpi_card("🔴 วิกฤต (OEE < %.0f%%)" % (threshold * 0.75),
                 float(n_crit), STATUS_CRITICAL, unit="เครื่อง")
    with a2:
        kpi_card("🟡 เฝ้าระวัง", float(n_warn), STATUS_WARNING, unit="เครื่อง")
    with a3:
        kpi_card("🟢 ปกติ (≥ เกณฑ์)", float(n_ok), STATUS_GOOD, unit="เครื่อง")
    st.caption(f"เกณฑ์: OEE ≥ {threshold}% = ปกติ · {threshold * 0.75:.0f}–{threshold}% = เฝ้าระวัง · ต่ำกว่านั้น = วิกฤต")

    st.markdown("---")
    st.subheader("⚠️ เครื่องจักรที่ OEE ต่ำที่สุด 15 อันดับ")
    worst = summary.head(15).copy()
    status_color = alt.Scale(
        domain=["🔴 วิกฤต", "🟡 เฝ้าระวัง", "🟢 ปกติ"],
        range=[STATUS_CRITICAL, STATUS_WARNING, STATUS_GOOD],
    )
    worst_bar = (
        alt.Chart(worst)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=18)
        .encode(
            y=alt.Y("MC:N", sort=alt.EncodingSortField("OEE", order="ascending"),
                    title=None),
            x=alt.X("OEE:Q", title="OEE (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("สถานะ:N", scale=status_color, title="สถานะ"),
            tooltip=[
                alt.Tooltip("Machine:N", title="เครื่องจักร"),
                alt.Tooltip("OEE:Q", title="OEE (%)", format=".1f"),
                alt.Tooltip("Availability:Q", title="Availability (%)", format=".1f"),
                alt.Tooltip("Performance:Q", title="Performance (%)", format=".1f"),
                alt.Tooltip("จำนวนวัน:Q", title="จำนวนวันข้อมูล"),
            ],
        )
        .properties(height=420)
    )
    rule_v = alt.Chart(pd.DataFrame({"x": [threshold]})).mark_rule(
        color="#898781", strokeDash=[6, 4]
    ).encode(x="x:Q")
    st.altair_chart(worst_bar + rule_v, width="stretch")

    st.subheader("📋 สถานะทุกเครื่องจักร (เรียงจาก OEE ต่ำสุด)")
    show = summary[["สถานะ", "MC", "Machine", "จำนวนวัน",
                    "OEE", "Availability", "Performance", "Quality",
                    "เวลาสูญเสียรวม (นาที)"]].copy()
    for c in ["OEE", "Availability", "Performance", "Quality"]:
        show[c] = show[c].round(1)
    st.dataframe(show, width="stretch", hide_index=True, height=420)

# --- 3) รายเครื่องจักร ---
with tab_machine:
    machine_list = sorted(filtered["Machine"].unique())
    sel_machine = st.selectbox("เลือกเครื่องจักร", machine_list)
    mdf_ = filtered[filtered["Machine"] == sel_machine]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("OEE", weighted_pct(mdf_, "OEE (%)"), COLOR_OEE, target=threshold)
    with c2:
        kpi_card("Availability", weighted_pct(mdf_, "Avaliable (%)"), COLOR_AVAILABILITY)
    with c3:
        kpi_card("Performance", weighted_pct(mdf_, "Performance (%)"), COLOR_PERFORMANCE)
    with c4:
        kpi_card("Quality", weighted_pct(mdf_, "Quality (%)"), COLOR_QUALITY)

    st.markdown("")
    st.subheader("📈 แนวโน้ม OEE รายวัน")
    daily_m = mdf_[["Trans_date"] + list(METRIC_COLS.values())].rename(
        columns={v: k for k, v in METRIC_COLS.items()}
    )
    st.altair_chart(
        trend_chart(daily_m, list(METRIC_COLS.keys()), threshold),
        width="stretch",
    )

    if loss_cols:
        st.subheader("⏱ เวลาสูญเสียของเครื่องนี้ แยกตามสาเหตุ")
        loss_sum = (
            mdf_[loss_cols].sum().rename(index=LOSS_CATEGORIES)
            .reset_index()
        )
        loss_sum.columns = ["สาเหตุ", "นาที"]
        loss_sum = loss_sum[loss_sum["นาที"] > 0].sort_values("นาที", ascending=False)
        if loss_sum.empty:
            st.info("ไม่มีข้อมูลเวลาสูญเสียแยกสาเหตุของเครื่องนี้ในช่วงที่เลือก")
        else:
            pareto = (
                alt.Chart(loss_sum)
                .mark_bar(color=COLOR_OEE, cornerRadiusTopRight=4,
                          cornerRadiusBottomRight=4, size=22)
                .encode(
                    y=alt.Y("สาเหตุ:N", sort="-x", title=None),
                    x=alt.X("นาที:Q", title="นาทีรวม"),
                    tooltip=[
                        alt.Tooltip("สาเหตุ:N"),
                        alt.Tooltip("นาที:Q", format=",.0f"),
                    ],
                )
                .properties(height=60 + 34 * len(loss_sum))
            )
            st.altair_chart(pareto, width="stretch")

# --- 4) เวลาสูญเสีย ---
with tab_loss:
    if not loss_cols:
        st.info("ไฟล์นี้ไม่มีคอลัมน์เวลาสูญเสียแยกสาเหตุ")
    else:
        st.subheader("⏱ Pareto สาเหตุเวลาสูญเสีย (รวมทั้งโรงงานในช่วงที่กรอง)")
        loss_total = (
            filtered[loss_cols].sum().rename(index=LOSS_CATEGORIES).reset_index()
        )
        loss_total.columns = ["สาเหตุ", "นาที"]
        loss_total = loss_total[loss_total["นาที"] > 0].sort_values("นาที", ascending=False)
        loss_total["สัดส่วน (%)"] = loss_total["นาที"] / loss_total["นาที"].sum() * 100

        pareto = (
            alt.Chart(loss_total)
            .mark_bar(color=COLOR_OEE, cornerRadiusTopRight=4,
                      cornerRadiusBottomRight=4, size=26)
            .encode(
                y=alt.Y("สาเหตุ:N", sort="-x", title=None),
                x=alt.X("นาที:Q", title="นาทีรวม"),
                tooltip=[
                    alt.Tooltip("สาเหตุ:N"),
                    alt.Tooltip("นาที:Q", format=",.0f"),
                    alt.Tooltip("สัดส่วน (%):Q", format=".1f"),
                ],
            )
        )
        pct_label = pareto.mark_text(align="left", dx=6, color="#0b0b0b").encode(
            text=alt.Text("สัดส่วน (%):Q", format=".1f")
        )
        st.altair_chart(
            (pareto + pct_label).properties(height=60 + 36 * len(loss_total)),
            width="stretch",
        )
        st.caption("ตัวเลขท้ายแท่ง = สัดส่วนร้อยละของเวลาสูญเสียทั้งหมด")

        st.subheader("🏭 เครื่องจักรที่เสียเวลามากที่สุด 15 อันดับ")
        loss_by_mc = (
            filtered.groupby(["MC", "Machine"])["เวลาสูญเสีย/วัน"].sum()
            .reset_index()
            .rename(columns={"เวลาสูญเสีย/วัน": "นาที"})
            .sort_values("นาที", ascending=False)
            .head(15)
        )
        top_loss = (
            alt.Chart(loss_by_mc)
            .mark_bar(color=COLOR_AVAILABILITY, cornerRadiusTopRight=4,
                      cornerRadiusBottomRight=4, size=18)
            .encode(
                y=alt.Y("MC:N", sort="-x", title=None),
                x=alt.X("นาที:Q", title="เวลาสูญเสียรวม (นาที)"),
                tooltip=[
                    alt.Tooltip("Machine:N", title="เครื่องจักร"),
                    alt.Tooltip("นาที:Q", format=",.0f"),
                ],
            )
            .properties(height=420)
        )
        st.altair_chart(top_loss, width="stretch")

        st.subheader("📆 เวลาสูญเสียรายเดือน แยกตามสาเหตุ")
        monthly_loss = (
            filtered.groupby("Month")[loss_cols].sum()
            .rename(columns=LOSS_CATEGORIES)
            .reset_index()
            .melt(id_vars="Month", var_name="สาเหตุ", value_name="นาที")
        )
        cat_order = list(LOSS_CATEGORIES.values())
        stacked = (
            alt.Chart(monthly_loss)
            .mark_bar(size=42)
            .encode(
                x=alt.X("yearmonth(Month):T", title="เดือน"),
                y=alt.Y("นาที:Q", title="นาทีรวม"),
                color=alt.Color(
                    "สาเหตุ:N",
                    scale=alt.Scale(domain=cat_order, range=CAT_COLORS[: len(cat_order)]),
                    title="สาเหตุ",
                ),
                tooltip=[
                    alt.Tooltip("yearmonth(Month):T", title="เดือน", format="%m/%Y"),
                    alt.Tooltip("สาเหตุ:N"),
                    alt.Tooltip("นาที:Q", format=",.0f"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(stacked, width="stretch")

# --- 5) ข้อมูลรายวัน ---
with tab_table:
    st.subheader("📋 ข้อมูลรายวัน (ตามตัวกรองปัจจุบัน)")
    display = filtered.drop(columns=["Machine", "Month"], errors="ignore").copy()
    display["Trans_date"] = display["Trans_date"].dt.strftime("%Y-%m-%d")
    for col in METRIC_COLS.values():
        display[col] = display[col].round(1)
    st.dataframe(display, width="stretch", hide_index=True, height=520)

    csv_buf = io.BytesIO()
    display.to_csv(csv_buf, index=False, encoding="utf-8-sig")
    st.download_button(
        "⬇️ ดาวน์โหลดเป็น CSV",
        data=csv_buf.getvalue(),
        file_name="production_monitoring.csv",
        mime="text/csv",
    )
