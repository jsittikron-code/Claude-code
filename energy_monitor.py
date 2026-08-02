"""
ระบบบริหารพลังงานโรงงาน — Modernform (บ้านเลขที่ 33/5)
-------------------------------------------------
เฉพาะระบบไฟฟ้าของโรงงาน (หม้อแปลง 33/5, อัตรา TOU) อ่านข้อมูลจาก OneDrive:
  1. บิลไฟ MEA บ้านเลขที่ 33/5 (TOU 4.2.2)  — สรุปค่าไฟฟ้า <ปี>.xlsx
  2. มิเตอร์ย่อยภายใน + Solar Rooftop         — สรุปมิเตอร์ภายใน_*_<ปี>.xlsx
และเชื่อมผลผลิตจาก OEE_ฐานข้อมูลหลัก_<ปี>.xlsx (ถ้ามี) เพื่อคิด kWh ต่อชิ้นงานดี

แสดงผล 6 มุมมอง:
  1. ภาพรวมพลังงาน   — KPI รวม + สัดส่วน Grid/Solar + แนวโน้มค่าไฟ
  2. บิล & ต้นทุน      — โครงสร้างค่าไฟ TOU รายเดือน (Energy/Demand/Ft/PF/Vat)
  3. มิเตอร์ย่อย       — Pareto พื้นที่กินไฟ + Heatmap + ตรวจกระทบยอดกับบิล
  4. Solar             — ผลิตได้เท่าไร ช่วยลดค่าไฟประมาณกี่บาท
  5. แจ้งเตือน         — ค่าปรับ PF / Demand พุ่ง / มิเตอร์ผิดปกติ / ยอดไม่ตรง
  6. ข้อมูล            — ตารางดิบ + ดาวน์โหลด CSV

รันด้วย:  streamlit run energy_monitor.py
"""

import calendar
import glob
import os
import re

import altair as alt
import pandas as pd
import streamlit as st

import auth

# ---------------------------------------------------------------------------
# ตั้งค่าหน้าเพจ
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Energy Management — โรงงาน Modernform",
    page_icon="⚡",
    layout="wide",
)

# ---------------------------------------------------------------------------
# CSS Custom Styling — ธีม Cyberpunk / Industrial Smart Factory (Dark + Neon)
# ---------------------------------------------------------------------------
NEON_CSS = """
<style>
/* ============ ตัวแปรสีนีออน ============ */
:root {
    --bg-deep:    #0e1117;
    --neon-blue:  #00f2fe;   /* Electric Blue  — เส้นขอบ/ไฮไลต์หลัก */
    --neon-cyan:  #4facfe;   /* Soft Neon      — หัวข้อ/รอง         */
    --neon-alert: #ff0844;   /* Glowing Red    — แจ้งเตือน           */
    --glass-bg:   rgba(20, 27, 45, 0.55);
    --glass-line: rgba(0, 242, 254, 0.18);
}

/* ============ พื้นหลังโรงงานอนาคต: ไล่เฉดลึก + เส้นกริดจางๆ ============ */
.stApp {
    background:
        repeating-linear-gradient(0deg,  rgba(0,242,254,.025) 0 1px, transparent 1px 48px),
        repeating-linear-gradient(90deg, rgba(0,242,254,.025) 0 1px, transparent 1px 48px),
        radial-gradient(ellipse 80% 60% at 70% -10%, rgba(79,172,254,.12), transparent 60%),
        radial-gradient(ellipse 60% 50% at 10% 110%, rgba(0,242,254,.07), transparent 60%),
        var(--bg-deep);
}
html { scroll-behavior: smooth; }

/* ============ หัวเรื่อง: ตัวอักษรไล่เฉดนีออน + เรืองแสง ============ */
h1 {
    background: linear-gradient(90deg, var(--neon-blue), var(--neon-cyan) 60%, #a78bfa);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 0 18px rgba(0, 242, 254, .35));
}
h2, h3 { text-shadow: 0 0 24px rgba(79, 172, 254, .25); }

/* ============ Sidebar: กระจกเข้ม + เส้นขอบเรืองแสง ============ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(13,18,30,.92), rgba(9,13,24,.96));
    border-right: 1px solid var(--glass-line);
    backdrop-filter: blur(14px);
}

/* ============ Glassmorphism: กล่อง/การ์ดทุกใบ ============
   ทุก st.container(border=True) ในแอปตั้ง key="card_*" ไว้ Streamlit จึงติดคลาส
   st-key-card_* ให้ — เสถียรกว่าอิง testid ภายในที่เปลี่ยนตามเวอร์ชัน */
div[data-testid="stVerticalBlock"][class*="st-key-card_"] {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(0, 242, 254, 0.18) !important;
    border-radius: 16px !important;
    transition: border-color .3s ease, box-shadow .3s ease, transform .3s ease;
}
div[data-testid="stVerticalBlock"][class*="st-key-card_"]:hover {
    border-color: rgba(0, 242, 254, 0.5) !important;
    box-shadow: 0 0 20px rgba(0,242,254,.14), 0 0 60px rgba(0,242,254,.06),
                inset 0 0 24px rgba(0,242,254,.04);
    transform: translateY(-2px);
}

/* ============ KPI การ์ด (คลาสจาก kpi_card) ============ */
.kpi-card {
    --kpi-color: var(--neon-blue);
    background: linear-gradient(135deg,
        color-mix(in srgb, var(--kpi-color) 13%, transparent),
        rgba(255,255,255,.02));
    border: 1px solid color-mix(in srgb, var(--kpi-color) 35%, transparent);
    border-left: 4px solid var(--kpi-color);
    border-radius: 14px;
    padding: 16px 20px;
    backdrop-filter: blur(10px);
    transition: box-shadow .3s ease, transform .3s ease, border-color .3s ease;
}
.kpi-card:hover {
    transform: translateY(-3px);
    border-color: var(--kpi-color);
    box-shadow: 0 0 18px color-mix(in srgb, var(--kpi-color) 55%, transparent),
                0 0 48px color-mix(in srgb, var(--kpi-color) 22%, transparent);
}
.kpi-title { font-size: .9rem; font-weight: 600; color: #9aa8bf; letter-spacing: .02em; }
.kpi-value {
    font-size: 1.9rem; font-weight: 800; line-height: 1.2;
    color: var(--kpi-color);
    text-shadow: 0 0 14px color-mix(in srgb, var(--kpi-color) 65%, transparent);
}
.kpi-sub { font-size: .8rem; color: #7c8aa0; margin-top: 4px; }

/* ============ แท็บ: แถบเรืองแสง + เนื้อหาเฟดเข้า ============ */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 1px solid rgba(0,242,254,.15);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px 10px 0 0;
    transition: background .25s ease, color .25s ease, text-shadow .25s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    background: rgba(0,242,254,.06);
    text-shadow: 0 0 12px rgba(0,242,254,.6);
}
.stTabs [aria-selected="true"] { text-shadow: 0 0 14px rgba(0,242,254,.7); }
.stTabs [data-baseweb="tab-highlight"] {
    background: linear-gradient(90deg, var(--neon-blue), var(--neon-cyan));
    box-shadow: 0 0 12px rgba(0,242,254,.8);
    height: 3px; border-radius: 3px;
}
.stTabs [data-baseweb="tab-panel"] { animation: fadeSlide .35s ease; }
@keyframes fadeSlide {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: none; }
}

/* ============ แจ้งเตือน: ไฟหายใจนีออน (Neon Breathing) ============ */
div[data-testid="stAlertContainer"] { border-radius: 12px; backdrop-filter: blur(8px); }
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
    border: 1px solid rgba(255,8,68,.45);
    animation: breathRed 2.6s ease-in-out infinite;
}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
    border: 1px solid rgba(255,176,32,.4);
    animation: breathAmber 3.2s ease-in-out infinite;
}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
    border: 1px solid rgba(33,195,140,.35);
    box-shadow: 0 0 14px rgba(33,195,140,.12);
}
@keyframes breathRed {
    0%, 100% { box-shadow: 0 0 6px rgba(255,8,68,.25); }
    50%      { box-shadow: 0 0 22px rgba(255,8,68,.55), 0 0 44px rgba(255,8,68,.18); }
}
@keyframes breathAmber {
    0%, 100% { box-shadow: 0 0 5px rgba(255,176,32,.2); }
    50%      { box-shadow: 0 0 18px rgba(255,176,32,.45); }
}

/* ============ ปุ่ม + Expander + ตาราง + Slider ============ */
.stButton button, .stDownloadButton button {
    border: 1px solid rgba(0,242,254,.35);
    background: rgba(0,242,254,.05);
    border-radius: 10px;
    transition: box-shadow .25s ease, border-color .25s ease, color .25s ease;
}
.stButton button:hover, .stDownloadButton button:hover {
    border-color: var(--neon-blue);
    color: var(--neon-blue);
    box-shadow: 0 0 16px rgba(0,242,254,.35);
}
div[data-testid="stExpander"] details {
    background: rgba(20,27,45,.5);
    border: 1px solid var(--glass-line);
    border-radius: 12px;
    backdrop-filter: blur(10px);
    transition: border-color .3s ease, box-shadow .3s ease;
}
div[data-testid="stExpander"] details:hover {
    border-color: rgba(0,242,254,.4);
    box-shadow: 0 0 16px rgba(0,242,254,.1);
}
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(0,242,254,.15);
    border-radius: 12px;
    transition: border-color .3s ease, box-shadow .3s ease;
}
div[data-testid="stDataFrame"]:hover {
    border-color: rgba(0,242,254,.35);
    box-shadow: 0 0 18px rgba(0,242,254,.08);
}
[data-testid="stSlider"] div[role="slider"] {
    background: var(--neon-blue);
    box-shadow: 0 0 10px rgba(0,242,254,.8);
}

/* ============ Scrollbar อุตสาหกรรม ============ */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: #0a0e18; }
::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, rgba(0,242,254,.35), rgba(79,172,254,.25));
    border-radius: 6px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(0,242,254,.6); }

/* ============ เคารพผู้ใช้ที่ปิดแอนิเมชัน ============ */
@media (prefers-reduced-motion: reduce) {
    * { animation: none !important; transition: none !important; }
}
</style>
"""
st.markdown(NEON_CSS, unsafe_allow_html=True)


# ด่านล็อกอิน — รายชื่อผู้ใช้อยู่ใน .streamlit/secrets.toml (ไม่ push ขึ้น git)
# ใช้บัญชีชุดเดียวกับแดชบอร์ดตัวอื่นในโฟลเดอร์นี้ ดูโมดูล auth.py
auth.check_login("ระบบบริหารพลังงานโรงงาน — Modernform (33/5)")

# ---------------------------------------------------------------------------
# แหล่งข้อมูลบน OneDrive — อัปเดตไฟล์แล้วหน้าจอทุกคนรีเฟรชเองภายใน ~30 วินาที
# ---------------------------------------------------------------------------
ENERGY_DIR = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD\ฝ่ายซ่อมบำรุงรักษา"
    r"\4.เรื่องการใช้ปริมาณไฟฟ้าภายในโรงงาน\งานระบบไฟฟ้าโรงงาน"
)
OEE_FILE = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD\ฝ่ายซ่อมบำรุงรักษา"
    r"\3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx"
)

# เฉพาะบิลของโรงงาน — บ้านเลขที่ 33/5
BILL_METERS = {
    "33/5 โรงงาน": ("Bill_33-5", "หม้อแปลงโรงงาน · แรงดัน 22-33 kV"),
}
MAIN_BILL = "33/5 โรงงาน"

# ข้อมูลผู้ใช้ไฟฟ้าจากใบแจ้งค่าไฟฟ้า MEA (ข้อมูลประจำมิเตอร์ ไม่เปลี่ยนรายเดือน)
BILL_INFO = {
    "ชื่อผู้ใช้ไฟฟ้า": "บริษัท โมเดอร์นฟอร์ม กรุ๊ป จำกัด (มหาชน)",
    "สถานที่ใช้ไฟฟ้า": "33/5 ม.7 ซ.โรงเหล็ก ถ.บางนา-ตราด ต.บางโฉลง อ.บางพลี สมุทรปราการ 10540",
    "การไฟฟ้า": "การไฟฟ้านครหลวง (MEA) เขตบางพลี · Call Center 1130",
    "บัญชีแสดงสัญญา (CA/Ref No.1)": "010550607",
    "รหัสเครื่องวัดฯ (Installation)": "36010842",
    "ตัวคูณมิเตอร์ (Multiplier)": "×1,000",
    "ประเภทอัตรา (Type)": "4.2.2 (TOU)",
}
DEFAULT_TOU_TYPE = "TOU 4.2.2"   # ใช้เมื่อหาในไฟล์ไม่เจอ

# ช่วงเวลาอัตรา TOU ของ MEA
TOU_ON_MEAK_TIME = "จันทร์–ศุกร์ 09:00–22:00 น."
TOU_OFF_MEAK_TIME = "จันทร์–ศุกร์ 22:00–09:00 น. · เสาร์–อาทิตย์/วันหยุดราชการ ทั้งวัน"

# อัตราค่าไฟ TOU ระดับแรงดัน 22-33 kV ของ MEA (ใช้เมื่อไฟล์ไม่ได้ระบุ)
DEMAND_RATE = 132.93        # บาท/kW ของ Demand ช่วง On-peak
PF_PENALTY_RATE = 56.07     # บาท/kVAR ส่วนที่เกินเกณฑ์
PF_KVAR_FACTOR = 0.6197     # เกณฑ์ kVAR = 61.97% ของ Demand สูงสุด (เท่ากับ PF 0.85)
VAT_RATE = 0.07

THAI_MONTHS = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4,
    "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8,
    "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}
# ตัวย่อในชีตมิเตอร์ (ตัดจุด/ช่องว่างออกก่อนเทียบ)
THAI_MONTH_ABBR = {
    "มค": 1, "กพ": 2, "มีค": 3, "เมย": 4, "พค": 5, "มิย": 6,
    "กค": 7, "สค": 8, "กย": 9, "ตค": 10, "พย": 11, "ธค": 12,
}
MONTH_LABEL = {1: "ม.ค.", 2: "ก.พ.", 3: "มี.ค.", 4: "เม.ย.", 5: "พ.ค.", 6: "มิ.ย.",
               7: "ก.ค.", 8: "ส.ค.", 9: "ก.ย.", 10: "ต.ค.", 11: "พ.ย.", 12: "ธ.ค."}

# สีธีมของแดชบอร์ด
COLOR_GRID = "#2563eb"      # น้ำเงิน — ไฟจาก MEA (33/5)
COLOR_GRID2 = "#0ea5e9"     # ฟ้า — ไฟจาก MEA (33/2)
COLOR_SOLAR = "#f59e0b"     # ส้มทอง — Solar
COLOR_COST = "#16a34a"      # เขียว — เงิน
COLOR_ALERT = "#dc2626"     # แดง — แจ้งเตือน
STATUS_CRITICAL = "#d33f49"

# สีองค์ประกอบค่าไฟ (เรียงตามลำดับใน stacked bar)
COST_COMPONENTS = {
    "ค่าพลังงาน On-peak": "#ef4444",
    "ค่าพลังงาน Off-peak": "#3b82f6",
    "ค่า Demand": "#8b5cf6",
    "ค่า Ft": "#f59e0b",
    "ค่าปรับ PF": "#e11d48",
    "ค่าบริการ": "#94a3b8",
    "VAT 7%": "#64748b",
}


def _clean(text) -> str:
    """ตัดช่องว่าง/อักขระ zero-width ออกจากหัวคอลัมน์ (ไฟล์ 33-5 มี \u200b ปน)"""
    return re.sub(r"[\s\u200b\.]+", "", str(text))


def _num(series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


# ---------------------------------------------------------------------------
# โหลดข้อมูล — บิลไฟ MEA
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="กำลังอ่านบิลค่าไฟ...")
def load_bill(path: str, year_be: int, file_mtime: float | None = None) -> pd.DataFrame:
    # file_mtime เป็นส่วนหนึ่งของ cache key — ไฟล์เปลี่ยนเมื่อไรอ่านใหม่เมื่อนั้น
    raw = pd.read_excel(path, sheet_name=0, header=None, engine="openpyxl")

    # หาแถวหัวตาราง (แถวที่คอลัมน์แรกคือ "Mounth")
    header_idx = None
    for i in range(min(5, len(raw))):
        if _clean(raw.iloc[i, 0]) in ("Mounth", "Month"):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("ไม่พบแถวหัวตาราง (Mounth) — รูปแบบชีตไม่ตรงกับ Bill_of_Electric")

    # ดึงประเภทอัตรา TOU จากแถวหัวไฟล์ (เช่น "TOU 4.2.2")
    tou_type = DEFAULT_TOU_TYPE
    for i in range(header_idx + 1):
        for cell in raw.iloc[i]:
            m = re.search(r"TOU\s*[\d.]+", str(cell))
            if m:
                tou_type = m.group(0).strip().rstrip(".")
                break

    header = [_clean(c) for c in raw.iloc[header_idx]]
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = header

    # map ชื่อคอลัมน์ในไฟล์ → ชื่อมาตรฐาน
    col_map = {
        "Mounth": "month_name",
        "Total/Kwh/Unit": "kwh",
        "E_On_peak": "kwh_on",
        "RateOnPeak": "rate_on",
        "E_Off_peak": "kwh_off",
        "RateOffPeak": "rate_off",
        "Demand_E_On": "demand_on",
        "Demand_E_Off": "demand_off",
        "กิโลวาร์(kVAR)": "kvar",
        "Ft/ตามสถานการณ์": "ft_rate",
        "PF/Capasister": "pf_factor",
        "ค่าปรับPF": "pf_penalty",
        "บริการ": "service",
        "Vat": "vat_rate",
        "ส่วนลด": "discount",
    }
    missing = [k for k in ("Mounth", "Total/Kwh/Unit", "E_On_peak", "E_Off_peak")
               if k not in df.columns]
    if missing:
        raise ValueError("ไฟล์บิลขาดคอลัมน์: " + ", ".join(missing))
    df = df.loc[:, [c for c in col_map if c in df.columns]].rename(columns=col_map)

    # เก็บเฉพาะแถวที่เป็นชื่อเดือนจริง (ตัดแถว Total / แถวว่าง)
    df["month_name"] = df["month_name"].astype(str).str.strip()
    df = df[df["month_name"].isin(THAI_MONTHS)].copy()
    df["month"] = df["month_name"].map(THAI_MONTHS)

    for c in df.columns:
        if c not in ("month_name",):
            df[c] = _num(df[c])
    df = df.dropna(subset=["kwh"])

    # ---- คำนวณโครงสร้างค่าไฟ TOU (ช่องคำนวณในไฟล์ Excel ว่าง จึงคิดเองที่นี่) ----
    df["rate_on"] = df.get("rate_on", pd.Series(dtype=float)).fillna(0)
    df["rate_off"] = df.get("rate_off", pd.Series(dtype=float)).fillna(0)
    df["energy_on"] = df["kwh_on"].fillna(0) * df["rate_on"]
    df["energy_off"] = df["kwh_off"].fillna(0) * df["rate_off"]
    df["demand_charge"] = df.get("demand_on", pd.Series(dtype=float)).fillna(0) * DEMAND_RATE
    df["ft_charge"] = df["kwh"] * df.get("ft_rate", pd.Series(dtype=float)).fillna(0)

    # ค่าปรับ PF: ใช้ตัวเลขจากบิลก่อน ถ้าไม่มีค่อยคำนวณจาก kVAR ส่วนเกิน
    demand_max = df[["demand_on", "demand_off"]].max(axis=1).fillna(0)
    df["kvar_limit"] = demand_max * df.get("pf_factor", pd.Series(dtype=float)).fillna(PF_KVAR_FACTOR)
    kvar_excess = (df.get("kvar", pd.Series(dtype=float)).fillna(0) - df["kvar_limit"]).clip(lower=0)
    df["pf_penalty"] = df.get("pf_penalty", pd.Series(dtype=float)).fillna(
        kvar_excess.round() * PF_PENALTY_RATE
    )
    df["service"] = df.get("service", pd.Series(dtype=float)).fillna(312.24)
    df["discount"] = df.get("discount", pd.Series(dtype=float)).fillna(0)

    base = (df["energy_on"] + df["energy_off"] + df["demand_charge"]
            + df["ft_charge"] + df["pf_penalty"] + df["service"] - df["discount"])
    df["vat"] = base * df.get("vat_rate", pd.Series(dtype=float)).fillna(VAT_RATE)
    df["total_cost"] = base + df["vat"]
    df["avg_rate"] = (df["total_cost"] / df["kwh"]).where(df["kwh"] > 0)

    # Load Factor = kWh ÷ (Demand สูงสุด × ชั่วโมงทั้งเดือน)
    year_ce = year_be - 543
    hours = df["month"].map(lambda m: calendar.monthrange(year_ce, int(m))[1] * 24)
    df["load_factor"] = (df["kwh"] / (demand_max * hours) * 100).where(demand_max > 0)

    df["date"] = pd.to_datetime({"year": year_ce, "month": df["month"], "day": 1})
    df["เดือน"] = df["month"].map(MONTH_LABEL)
    df["tou_type"] = tou_type
    return df.sort_values("month").reset_index(drop=True)


# ---------------------------------------------------------------------------
# โหลดข้อมูล — มิเตอร์ย่อยภายใน + Solar
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="กำลังอ่านมิเตอร์ภายใน...")
def load_submeters(path: str, year_be: int, file_mtime: float | None = None) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=0, header=None, engine="openpyxl")

    # หาแถวหัวตาราง (คอลัมน์แรกเป็น "#")
    header_idx = None
    for i in range(min(10, len(raw))):
        if str(raw.iloc[i, 0]).strip() == "#":
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("ไม่พบหัวตารางมิเตอร์ (#) ในชีตแรก")

    # คอลัมน์เดือน: หัวเป็นตัวย่อไทย เช่น ม.ค. ก.พ. ...
    month_cols = {}
    for j in range(raw.shape[1]):
        m = THAI_MONTH_ABBR.get(_clean(raw.iloc[header_idx, j]))
        if m:
            month_cols[j] = m

    rows = []
    section = "มิเตอร์ย่อย"
    for i in range(header_idx + 1, len(raw)):
        first = str(raw.iloc[i, 0]).strip()
        if "Solar" in first:                     # ขึ้นหัวข้อ ☀ Solar Rooftop
            section = "Solar"
            continue
        if not re.fullmatch(r"\d+", first):      # แถวรวม/แถวว่าง/หัวข้ออื่น — ข้าม
            continue
        station = str(raw.iloc[i, 1]).strip()
        meter_no = str(raw.iloc[i, 2]).strip()
        if station in ("", "nan"):
            continue
        for j, m in month_cols.items():
            kwh = _num(pd.Series([raw.iloc[i, j]]))[0]
            if pd.notna(kwh):
                rows.append({
                    "ประเภท": section,
                    "สถานที่": station,
                    "เลขมิเตอร์": "" if meter_no == "nan" else meter_no,
                    "month": m,
                    "kwh": float(kwh),
                })
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("อ่านข้อมูลมิเตอร์ไม่ได้ — ไม่พบแถวข้อมูลใต้หัวตาราง")
    df["เดือน"] = df["month"].map(MONTH_LABEL)
    df["date"] = pd.to_datetime({"year": year_be - 543, "month": df["month"], "day": 1})
    return df.sort_values(["ประเภท", "สถานที่", "month"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# โหลดข้อมูล — ผลผลิตจากฐาน OEE (ถ้ามี) เพื่อคิด kWh ต่อชิ้นงานดี
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="กำลังอ่านข้อมูลผลผลิต (OEE)...")
def load_production(path: str, file_mtime: float | None = None) -> pd.DataFrame:
    xl = pd.ExcelFile(path, engine="openpyxl")
    sheet = "Report1" if "Report1" in xl.sheet_names else 0
    df = pd.read_excel(xl, sheet_name=sheet,
                       usecols=lambda c: c in ("Trans_date", "ชิ้นงานดี(ชิ้น)/วัน"))
    df["Trans_date"] = pd.to_datetime(df["Trans_date"], errors="coerce")
    df = df.dropna(subset=["Trans_date"])
    df["ชิ้นงานดี(ชิ้น)/วัน"] = _num(df["ชิ้นงานดี(ชิ้น)/วัน"]).fillna(0)
    out = (
        df.groupby(df["Trans_date"].dt.month)["ชิ้นงานดี(ชิ้น)/วัน"].sum()
        .rename("good_pieces").reset_index()
        .rename(columns={"Trans_date": "month"})
    )
    return out


# ---------------------------------------------------------------------------
# ส่วนหัว + แถบควบคุมด้านข้าง
# ---------------------------------------------------------------------------
st.title("⚡ ระบบบริหารพลังงานโรงงาน — Modernform (33/5)")
st.caption("บิลไฟ MEA บ้านเลขที่ 33/5 อัตรา TOU · มิเตอร์ย่อยภายใน · Solar Rooftop · แจ้งเตือนอัตโนมัติ")

with st.expander("🧾 ข้อมูลผู้ใช้ไฟฟ้า (จากใบแจ้งค่าไฟฟ้า MEA)"):
    info_l, info_r = st.columns(2)
    items = list(BILL_INFO.items())
    for col, chunk in ((info_l, items[:3]), (info_r, items[3:])):
        with col:
            for k, v in chunk:
                st.markdown(f"**{k}:** {v}")

# ค้นหาปีที่มีข้อมูล — เอาเฉพาะโฟลเดอร์ปี พ.ศ. ใต้ Bill_33-5 ที่มีไฟล์สรุปแล้วจริง
main_bill_dir = os.path.join(ENERGY_DIR, "งานระบบไฟฟ้า", BILL_METERS[MAIN_BILL][0])
years = sorted(
    (
        int(d) for d in os.listdir(main_bill_dir)
        if d.isdigit()
        and os.path.exists(os.path.join(main_bill_dir, d, f"สรุปค่าไฟฟ้า {d}.xlsx"))
    ),
    reverse=True,
) if os.path.isdir(main_bill_dir) else []

with st.sidebar:
    col_u, col_out = st.columns([3, 1])
    col_u.caption(f":material/account_circle: {auth.current_user()}")
    if col_out.button(":material/logout:", help="ออกจากระบบ"):
        auth.logout()
        st.rerun()
    st.header("⚙️ ข้อมูลนำเข้า")
    if not years:
        st.error(f"ไม่พบโฟลเดอร์ปีใน\n{main_bill_dir}\n\nตรวจสอบว่า OneDrive ซิงก์อยู่")
        st.stop()
    year_be = st.selectbox("ปีข้อมูล (พ.ศ.)", years, index=0)

# --- อ่านบิลทุกหม้อแปลง ---
bills = {}
bill_paths = {}
load_errors = []
for name, (folder, _desc) in BILL_METERS.items():
    path = os.path.join(ENERGY_DIR, "งานระบบไฟฟ้า", folder, str(year_be),
                        f"สรุปค่าไฟฟ้า {year_be}.xlsx")
    if not os.path.exists(path):
        load_errors.append(f"{name}: ไม่พบไฟล์ {os.path.basename(path)}")
        continue
    try:
        bills[name] = load_bill(path, year_be, os.path.getmtime(path))
        bill_paths[name] = path
    except Exception as e:
        load_errors.append(f"{name}: {e}")

if MAIN_BILL not in bills:
    st.error("อ่านบิลหม้อแปลงหลัก 33/5 ไม่ได้ — ระบบต้องมีไฟล์นี้เป็นอย่างน้อย\n\n"
             + "\n".join(load_errors))
    st.stop()

# --- อ่านมิเตอร์ย่อย (ชื่อไฟล์ผูกช่วงเดือน จึงใช้ glob หาไฟล์ล่าสุดของปีนั้น) ---
sub = None
sub_path = None
pattern = os.path.join(ENERGY_DIR, "ระบบไฟฟ้าภายใน", "**",
                       f"สรุปมิเตอร์ภายใน*{year_be}*.xlsx")
candidates = sorted(glob.glob(pattern, recursive=True),
                    key=os.path.getmtime, reverse=True)
for path in candidates:
    try:
        sub = load_submeters(path, year_be, os.path.getmtime(path))
        sub_path = path
        break
    except Exception as e:
        load_errors.append(f"มิเตอร์ภายใน ({os.path.basename(path)}): {e}")
if sub is None:
    load_errors.append(f"มิเตอร์ภายใน: ไม่พบไฟล์ สรุปมิเตอร์ภายใน*{year_be}*.xlsx")

# --- อ่านผลผลิตจาก OEE (ไม่บังคับ) ---
production = None
if os.path.exists(OEE_FILE):
    try:
        production = load_production(OEE_FILE, os.path.getmtime(OEE_FILE))
    except Exception as e:
        load_errors.append(f"OEE: {e}")


@st.fragment(run_every="30s")
def watch_data_files():
    """เช็คทุก 30 วินาที — ไฟล์ต้นทางบน OneDrive เปลี่ยนเมื่อไร รีเฟรชหน้าอัตโนมัติ"""
    paths = list(bill_paths.values()) + ([sub_path] if sub_path else []) + [OEE_FILE]
    sig = tuple(os.path.getmtime(p) if p and os.path.exists(p) else None for p in paths)
    prev = st.session_state.get("_energy_sig")
    st.session_state["_energy_sig"] = sig
    if prev is not None and sig != prev:
        st.rerun(scope="app")


watch_data_files()

with st.sidebar:
    ok_lines = [f"✓ บิล {n}" for n in bills]
    if sub is not None:
        n_sub = sub.loc[sub["ประเภท"] == "มิเตอร์ย่อย", "สถานที่"].nunique()
        n_sol = sub.loc[sub["ประเภท"] == "Solar", "สถานที่"].nunique()
        ok_lines.append(f"✓ มิเตอร์ย่อย {n_sub} จุด + Solar {n_sol} ชุด")
    if production is not None:
        ok_lines.append("✓ ผลผลิต (OEE)")
    st.success("\n\n".join(ok_lines))
    if load_errors:
        st.warning("อ่านไม่ได้บางส่วน:\n\n" + "\n".join(f"- {e}" for e in load_errors))
    if st.button("🔄 โหลดข้อมูลใหม่", help="ล้าง cache แล้วอ่านไฟล์จากดิสก์ใหม่ทันที"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.header("🔔 เกณฑ์แจ้งเตือน")
    th_demand = st.slider("Demand พุ่งเกินค่าเฉลี่ย 3 เดือน (%)", 5, 50, 10, step=5)
    th_meter = st.slider("มิเตอร์ย่อยเปลี่ยนผิดปกติ (% ต่อเดือน)", 20, 200, 50, step=10)
    th_recon = st.slider("ยอดมิเตอร์ย่อยต่างจากบิล+Solar เกิน (%)", 5, 50, 15, step=5)

# ---------------------------------------------------------------------------
# เตรียมตารางรวมสำหรับทุกแท็บ
# ---------------------------------------------------------------------------
main = bills[MAIN_BILL]

# พลังงานรายเดือน: ไฟจาก MEA แต่ละหม้อแปลง + Solar (long format สำหรับ stacked bar)
mix_rows = []
for name, b in bills.items():
    src = "MEA 33/5" if name == MAIN_BILL else f"MEA {name}"
    for _, r in b.iterrows():
        mix_rows.append({"month": r["month"], "แหล่ง": src, "kwh": r["kwh"]})
solar = None
if sub is not None:
    solar = (sub[sub["ประเภท"] == "Solar"].groupby("month")["kwh"].sum()
             .rename("solar_kwh").reset_index())
    for _, r in solar.iterrows():
        mix_rows.append({"month": r["month"], "แหล่ง": "Solar Rooftop", "kwh": r["solar_kwh"]})
mix = pd.DataFrame(mix_rows)
mix["เดือน"] = mix["month"].map(MONTH_LABEL)
mix["รวมทั้งเดือน"] = mix.groupby("month")["kwh"].transform("sum")
mix["สัดส่วน"] = mix["kwh"] / mix["รวมทั้งเดือน"] * 100

month_order = [MONTH_LABEL[m] for m in sorted(mix["month"].unique())]
SRC_COLORS = {"MEA 33/5": COLOR_GRID, "MEA 33/2": COLOR_GRID2, "Solar Rooftop": COLOR_SOLAR}
src_domain = [s for s in SRC_COLORS if s in mix["แหล่ง"].unique()]
src_scale = alt.Scale(domain=src_domain, range=[SRC_COLORS[s] for s in src_domain])


def kpi_card(title: str, value_text: str, color: str, sub_text: str = ""):
    """การ์ด KPI แบบ glassmorphism — สไตล์อยู่ใน NEON_CSS (คลาส .kpi-card)
    เขียน HTML บรรทัดเดียว ห้ามมี indent มิฉะนั้น Streamlit จะโชว์เป็น code block"""
    sub_html = f'<div class="kpi-sub">{sub_text}</div>' if sub_text else ""
    card_html = (
        f'<div class="kpi-card" style="--kpi-color:{color};">'
        f'<div class="kpi-title">{title}</div>'
        f'<div class="kpi-value">{value_text}</div>'
        f'{sub_html}'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


def month_axis():
    return alt.X("เดือน:N", sort=month_order, title="เดือน")


# ---------------------------------------------------------------------------
# แท็บหลัก
# ---------------------------------------------------------------------------
tab_over, tab_bill, tab_sub, tab_solar, tab_alert, tab_data = st.tabs([
    ":material/factory: ภาพรวมพลังงาน",
    ":material/payments: บิล & ต้นทุน",
    ":material/electric_meter: มิเตอร์ย่อย",
    ":material/solar_power: Solar",
    ":material/notification_important: แจ้งเตือน",
    ":material/table_view: ข้อมูล",
])

# --- 1) ภาพรวมพลังงาน ---
with tab_over:
    grid_kwh = sum(b["kwh"].sum() for b in bills.values())
    solar_kwh = float(solar["solar_kwh"].sum()) if solar is not None else 0.0
    total_kwh = grid_kwh + solar_kwh
    total_cost = sum(b["total_cost"].sum() for b in bills.values())
    avg_rate = total_cost / grid_kwh if grid_kwh > 0 else 0
    peak_row = main.loc[main["demand_on"].idxmax()] if main["demand_on"].notna().any() else None

    n_months = main["month"].nunique()
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("ค่าไฟรวม (คำนวณ)", f"{total_cost:,.0f} ฿",
                 COLOR_COST, f"{n_months} เดือน · เฉลี่ย {total_cost / max(n_months, 1):,.0f} ฿/เดือน")
    with c2:
        kpi_card("ไฟจาก MEA", f"{grid_kwh:,.0f} kWh",
                 COLOR_GRID, f"บ้านเลขที่ 33/5 · อัตรา {main['tou_type'].iloc[0]}")
    with c3:
        kpi_card("Solar ผลิตได้", f"{solar_kwh:,.0f} kWh",
                 COLOR_SOLAR,
                 f"{solar_kwh / total_kwh * 100:.1f}% ของพลังงานทั้งหมด" if total_kwh else "—")
    with c4:
        kpi_card("ค่าไฟเฉลี่ย", f"{avg_rate:,.2f} ฿/kWh", COLOR_GRID2, "รวม Demand + Ft + VAT")
    with c5:
        if peak_row is not None:
            kpi_card("Demand สูงสุด (On-peak)", f"{peak_row['demand_on']:,.0f} kW",
                     COLOR_ALERT, f"เดือน{peak_row['month_name']}")

    st.markdown("")
    col_l, col_r = st.columns([3, 2])
    with col_l:
        with st.container(border=True, key="card_mix"):
            st.subheader("พลังงานที่ใช้รายเดือน — แยกตามแหล่ง")
            chart = (
                alt.Chart(mix)
                .mark_bar()
                .encode(
                    x=month_axis(),
                    y=alt.Y("kwh:Q", title="พลังงาน (kWh)"),
                    color=alt.Color("แหล่ง:N", scale=src_scale, title="แหล่งพลังงาน"),
                    tooltip=[
                        "เดือน", "แหล่ง",
                        alt.Tooltip("kwh:Q", title="พลังงาน (kWh)", format=",.0f"),
                        alt.Tooltip("สัดส่วน:Q", title="สัดส่วนของเดือน (%)", format=".1f"),
                        alt.Tooltip("รวมทั้งเดือน:Q", title="รวมทั้งเดือน (kWh)", format=",.0f"),
                    ],
                )
                .properties(height=340)
            )
            st.altair_chart(chart, width="stretch")
    with col_r:
        with st.container(border=True, key="card_01"):
            st.subheader("ค่าไฟรายเดือน (คำนวณ)")
            cost_plot = main.assign(
                energy_total=main["energy_on"] + main["energy_off"],
                mom=main["total_cost"].pct_change() * 100,
            )
            chart = (
                alt.Chart(cost_plot)
                .mark_bar(color=COLOR_COST)
                .encode(
                    x=month_axis(),
                    y=alt.Y("total_cost:Q", title="ค่าไฟ (บาท)"),
                    tooltip=[
                        "เดือน",
                        alt.Tooltip("total_cost:Q", title="ค่าไฟรวม (฿)", format=",.0f"),
                        alt.Tooltip("mom:Q", title="เทียบเดือนก่อน (%)", format="+.1f"),
                        alt.Tooltip("avg_rate:Q", title="เฉลี่ย (฿/kWh)", format=".2f"),
                        alt.Tooltip("kwh:Q", title="หน่วยรวม (kWh)", format=",.0f"),
                        alt.Tooltip("energy_total:Q", title="ค่าพลังงาน (฿)", format=",.0f"),
                        alt.Tooltip("demand_charge:Q", title="ค่า Demand (฿)", format=",.0f"),
                        alt.Tooltip("ft_charge:Q", title="ค่า Ft (฿)", format=",.0f"),
                        alt.Tooltip("vat:Q", title="VAT (฿)", format=",.0f"),
                    ],
                )
                .properties(height=340)
            )
            st.altair_chart(chart, width="stretch")

    col_l2, col_r2 = st.columns(2)
    with col_l2:
        with st.container(border=True, key="card_02"):
            st.subheader("สัดส่วน On-peak : Off-peak (หม้อแปลง 33/5)")
            peak_df = pd.concat([
                main[["เดือน"]].assign(**{"ช่วงเวลา": "On-peak (แพง)"},
                                       kwh=main["kwh_on"], บาท=main["energy_on"],
                                       อัตรา=main["rate_on"]),
                main[["เดือน"]].assign(**{"ช่วงเวลา": "Off-peak (ถูก)"},
                                       kwh=main["kwh_off"], บาท=main["energy_off"],
                                       อัตรา=main["rate_off"]),
            ])
            peak_df["สัดส่วน"] = (
                peak_df["kwh"] / peak_df.groupby("เดือน")["kwh"].transform("sum") * 100
            )
            chart = (
                alt.Chart(peak_df)
                .mark_bar()
                .encode(
                    x=month_axis(),
                    y=alt.Y("kwh:Q", stack="normalize", title="สัดส่วน",
                            axis=alt.Axis(format="%")),
                    color=alt.Color("ช่วงเวลา:N",
                                    scale=alt.Scale(domain=["On-peak (แพง)", "Off-peak (ถูก)"],
                                                    range=["#ef4444", "#3b82f6"]),
                                    title="ช่วงเวลา"),
                    tooltip=[
                        "เดือน", "ช่วงเวลา",
                        alt.Tooltip("kwh:Q", title="หน่วย (kWh)", format=",.0f"),
                        alt.Tooltip("สัดส่วน:Q", title="สัดส่วน (%)", format=".1f"),
                        alt.Tooltip("บาท:Q", title="ค่าพลังงาน (฿)", format=",.0f"),
                        alt.Tooltip("อัตรา:Q", title="อัตรา (฿/kWh)", format=".4f"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")
            on_share = main["kwh_on"].sum() / main["kwh"].sum() * 100 if main["kwh"].sum() else 0
            st.caption(
                f"ทั้งปีใช้ On-peak {on_share:.0f}% — ทุก 1% ที่ย้ายไป Off-peak ได้ "
                f"ประหยัด ≈ {main['kwh'].sum() * 0.01 * (main['rate_on'].mean() - main['rate_off'].mean()):,.0f} บาท/ปี"
            )
    with col_r2:
        with st.container(border=True, key="card_03"):
            st.subheader("พลังงานต่อผลผลิต (kWh ต่อชิ้นงานดี)")
            if production is not None and solar is not None:
                spec = main[["month", "เดือน", "kwh"]].merge(solar, on="month", how="left")
                spec["solar_kwh"] = spec["solar_kwh"].fillna(0)
                spec = spec.merge(production, on="month", how="inner")
                spec["kwh_per_piece"] = (
                    (spec["kwh"] + spec["solar_kwh"]) / spec["good_pieces"]
                ).where(spec["good_pieces"] > 0)
                spec["รวมพลังงาน"] = spec["kwh"] + spec["solar_kwh"]
                spec["mom"] = spec["kwh_per_piece"].pct_change() * 100
                chart = (
                    alt.Chart(spec.dropna(subset=["kwh_per_piece"]))
                    .mark_line(strokeWidth=3, point=alt.OverlayMarkDef(size=60), color="#9333ea")
                    .encode(
                        x=month_axis(),
                        y=alt.Y("kwh_per_piece:Q", title="kWh / ชิ้นงานดี"),
                        tooltip=[
                            "เดือน",
                            alt.Tooltip("kwh_per_piece:Q", title="kWh/ชิ้น", format=".2f"),
                            alt.Tooltip("mom:Q", title="เทียบเดือนก่อน (%)", format="+.1f"),
                            alt.Tooltip("good_pieces:Q", title="ชิ้นงานดี (ชิ้น)", format=",.0f"),
                            alt.Tooltip("รวมพลังงาน:Q", title="พลังงานรวม (kWh)", format=",.0f"),
                            alt.Tooltip("solar_kwh:Q", title="จาก Solar (kWh)", format=",.0f"),
                        ],
                    )
                    .properties(height=300)
                )
                st.altair_chart(chart, width="stretch")
                st.caption("ยิ่งต่ำยิ่งดี — ใช้ (ไฟ MEA 33/5 + Solar) ÷ ชิ้นงานดีจากฐาน OEE")
            else:
                st.info("ต้องอ่านไฟล์ OEE และมิเตอร์ Solar ได้ก่อน จึงจะคำนวณได้")

# --- 2) บิล & ต้นทุน ---
with tab_bill:
    b = main
    tou = b["tou_type"].iloc[0]

    # โครงสร้างอัตรา TOU ของบิลนี้ (อัตราพลังงานอ่านจากไฟล์จริง)
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        kpi_card("ประเภทอัตรา", tou, COLOR_GRID,
                 BILL_METERS[MAIN_BILL][1])
    with t2:
        kpi_card("On-peak", f"{b['rate_on'].iloc[-1]:.4f} ฿/kWh", "#ef4444",
                 TOU_ON_MEAK_TIME)
    with t3:
        kpi_card("Off-peak", f"{b['rate_off'].iloc[-1]:.4f} ฿/kWh", "#3b82f6",
                 TOU_OFF_MEAK_TIME)
    with t4:
        kpi_card("ค่า Demand", f"{DEMAND_RATE:,.2f} ฿/kW", "#8b5cf6",
                 f"เฉพาะ On-peak · บริการ {b['service'].iloc[-1]:,.2f} ฿/เดือน")
    st.markdown("")

    comp_map = {
        "ค่าพลังงาน On-peak": "energy_on",
        "ค่าพลังงาน Off-peak": "energy_off",
        "ค่า Demand": "demand_charge",
        "ค่า Ft": "ft_charge",
        "ค่าปรับ PF": "pf_penalty",
        "ค่าบริการ": "service",
        "VAT 7%": "vat",
    }
    comp_rows = [
        {"เดือน": r["เดือน"], "month": r["month"], "องค์ประกอบ": label, "บาท": r[col]}
        for _, r in b.iterrows() for label, col in comp_map.items()
    ]
    comp = pd.DataFrame(comp_rows)
    comp["รวมทั้งเดือน"] = comp.groupby("month")["บาท"].transform("sum")
    comp["สัดส่วน"] = comp["บาท"] / comp["รวมทั้งเดือน"] * 100

    with st.container(border=True, key="card_04"):
        st.subheader("โครงสร้างค่าไฟรายเดือน")
        chart = (
            alt.Chart(comp)
            .mark_bar()
            .encode(
                x=month_axis(),
                y=alt.Y("บาท:Q", title="ค่าไฟ (บาท)"),
                color=alt.Color("องค์ประกอบ:N",
                                scale=alt.Scale(domain=list(COST_COMPONENTS),
                                                range=list(COST_COMPONENTS.values())),
                                title="องค์ประกอบ"),
                order=alt.Order("องค์ประกอบ:N"),
                tooltip=[
                    "เดือน", "องค์ประกอบ",
                    alt.Tooltip("บาท:Q", title="จำนวนเงิน (฿)", format=",.0f"),
                    alt.Tooltip("สัดส่วน:Q", title="สัดส่วนของบิล (%)", format=".1f"),
                    alt.Tooltip("รวมทั้งเดือน:Q", title="บิลทั้งเดือน (฿)", format=",.0f"),
                ],
            )
            .properties(height=380)
        )
        st.altair_chart(chart, width="stretch")
        share = comp.groupby("องค์ประกอบ")["บาท"].sum()
        top = share.idxmax()
        st.caption(
            f"สัดส่วนสะสมทั้งปี: " + " · ".join(
                f"{k} {v / share.sum() * 100:.0f}%" for k, v in
                share.sort_values(ascending=False).items() if v > 0
            ) + f" — ก้อนใหญ่สุดคือ **{top}**"
        )

    col_l, col_r = st.columns(2)
    with col_l:
        with st.container(border=True, key="card_05"):
            st.subheader("Demand รายเดือน (kW)")
            dem = b[["เดือน", "demand_on", "demand_off"]].melt(
                id_vars="เดือน", var_name="ช่วง", value_name="kW").replace(
                {"demand_on": "On-peak", "demand_off": "Off-peak"})
            # จ่ายเงินเฉพาะ Demand ช่วง On-peak
            dem["ค่า Demand"] = (dem["kW"] * DEMAND_RATE).where(dem["ช่วง"] == "On-peak", 0)
            chart = (
                alt.Chart(dem)
                .mark_bar()
                .encode(
                    x=month_axis(),
                    xOffset="ช่วง:N",
                    y=alt.Y("kW:Q", title="Demand (kW)"),
                    color=alt.Color("ช่วง:N",
                                    scale=alt.Scale(domain=["On-peak", "Off-peak"],
                                                    range=["#8b5cf6", "#c4b5fd"])),
                    tooltip=[
                        "เดือน", "ช่วง",
                        alt.Tooltip("kW:Q", title="Demand (kW)", format=",.0f"),
                        alt.Tooltip("ค่า Demand:Q", title="คิดเป็นเงิน (฿)", format=",.0f"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")
            st.caption(f"จ่ายค่า Demand เฉพาะ On-peak × {DEMAND_RATE} ฿/kW — คุม peak ตอนกลางวันคือคุมเงินก้อนนี้")
    with col_r:
        with st.container(border=True, key="card_06"):
            st.subheader("Load Factor (%)")
            chart = (
                alt.Chart(b.dropna(subset=["load_factor"]))
                .mark_line(strokeWidth=3, point=alt.OverlayMarkDef(size=60), color=COLOR_GRID)
                .encode(
                    x=month_axis(),
                    y=alt.Y("load_factor:Q", title="Load Factor (%)",
                            scale=alt.Scale(domain=[0, 100])),
                    tooltip=[
                        "เดือน",
                        alt.Tooltip("load_factor:Q", title="Load Factor (%)", format=".1f"),
                        alt.Tooltip("kwh:Q", title="หน่วยรวม (kWh)", format=",.0f"),
                        alt.Tooltip("demand_on:Q", title="Demand On-peak (kW)", format=",.0f"),
                        alt.Tooltip("demand_off:Q", title="Demand Off-peak (kW)", format=",.0f"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")
            st.caption("kWh ÷ (Demand สูงสุด × ชม.ทั้งเดือน) — ยิ่งสูงยิ่งใช้หม้อแปลงคุ้ม peak ไม่โด่ง")

    with st.container(border=True, key="card_07"):
        st.subheader("ตารางบิลรายเดือน (คำนวณจากข้อมูลดิบ)")
        show = b[["เดือน", "kwh", "kwh_on", "kwh_off", "demand_on", "kvar",
                  "energy_on", "energy_off", "demand_charge", "ft_charge",
                  "pf_penalty", "service", "vat", "total_cost", "avg_rate", "load_factor"]].copy()

        def mom_text(series: pd.Series) -> pd.Series:
            """ลูกศร ▲▼ พร้อม % เทียบเดือนก่อนหน้า (เดือนแรกไม่มีตัวเทียบ = —)"""
            def fmt(v):
                if pd.isna(v):
                    return "—"
                arrow = "▲" if v > 0 else ("▼" if v < 0 else "＝")
                return f"{arrow} {v:+.1f}%"
            return (series.pct_change() * 100).map(fmt)

        show.insert(show.columns.get_loc("kwh") + 1, "d_kwh", mom_text(b["kwh"]))
        show.insert(show.columns.get_loc("demand_on") + 1, "d_demand", mom_text(b["demand_on"]))
        show.insert(show.columns.get_loc("total_cost") + 1, "d_cost", mom_text(b["total_cost"]))
        # ปัดเศษคอลัมน์เงินเป็นบาทถ้วนให้ตารางอ่านง่าย (ยอดเป๊ะดูได้ในแท็บข้อมูล)
        for c in ["energy_on", "energy_off", "demand_charge", "ft_charge",
                  "pf_penalty", "vat", "total_cost"]:
            show[c] = show[c].round(0)

        def color_delta(val: str) -> str:
            """แดง = เพิ่มขึ้น (ใช้/จ่ายมากขึ้น) · เขียว = ลดลง"""
            if isinstance(val, str):
                if val.startswith("▲"):
                    return "color:#ef4444;font-weight:700"
                if val.startswith("▼"):
                    return "color:#22c55e;font-weight:700"
            return ""

        delta_cols = ["d_kwh", "d_demand", "d_cost"]
        styler = show.style
        # pandas ≥2.1 เปลี่ยนชื่อ applymap → map
        styler = (styler.map(color_delta, subset=delta_cols)
                  if hasattr(styler, "map")
                  else styler.applymap(color_delta, subset=delta_cols))
        st.dataframe(
            styler, hide_index=True, width="stretch",
            column_config={
                "kwh": st.column_config.NumberColumn("kWh รวม", format="localized"),
                "d_kwh": st.column_config.TextColumn(
                    "± หน่วย", help="เทียบเดือนก่อนหน้า — เดือนแรกแสดง — เพราะไม่มีตัวเทียบ"),
                "d_demand": st.column_config.TextColumn(
                    "± Demand", help="เทียบเดือนก่อนหน้า — เดือนแรกแสดง — เพราะไม่มีตัวเทียบ"),
                "d_cost": st.column_config.TextColumn(
                    "± ค่าไฟ", help="เทียบเดือนก่อนหน้า — เดือนแรกแสดง — เพราะไม่มีตัวเทียบ"),
                "kwh_on": st.column_config.NumberColumn("On-peak", format="localized"),
                "kwh_off": st.column_config.NumberColumn("Off-peak", format="localized"),
                "demand_on": st.column_config.NumberColumn("Demand kW", format="localized"),
                "kvar": st.column_config.NumberColumn("kVAR", format="localized"),
                "energy_on": st.column_config.NumberColumn("฿ On-peak", format="localized"),
                "energy_off": st.column_config.NumberColumn("฿ Off-peak", format="localized"),
                "demand_charge": st.column_config.NumberColumn("฿ Demand", format="localized"),
                "ft_charge": st.column_config.NumberColumn("฿ Ft", format="localized"),
                "pf_penalty": st.column_config.NumberColumn("฿ ปรับ PF", format="localized"),
                "service": st.column_config.NumberColumn("฿ บริการ", format="localized"),
                "vat": st.column_config.NumberColumn("฿ VAT", format="localized"),
                "total_cost": st.column_config.NumberColumn("฿ รวม", format="localized"),
                "avg_rate": st.column_config.NumberColumn("฿/kWh", format="%.2f"),
                "load_factor": st.column_config.NumberColumn("LF %", format="%.1f"),
            },
        )
        st.caption("หมายเหตุ: ช่องคำนวณในไฟล์ Excel ว่าง ระบบจึงคำนวณตามโครงสร้าง TOU ให้ — "
                   "สูตรตรวจสอบแล้วตรงกับใบแจ้งค่าไฟฟ้า MEA จริงเดือน มิ.ย. 69 "
                   "(871,082.02 บาท) ทุกบรรทัด")

    with st.expander(f"📖 วิธีคิดบิลอัตรา {tou} (TOU — Time of Use)"):
        st.markdown(f"""
| องค์ประกอบ | วิธีคิด |
|---|---|
| ค่าพลังงาน On-peak | หน่วย On-peak × {b['rate_on'].iloc[-1]:.4f} ฿/kWh ({TOU_ON_MEAK_TIME}) |
| ค่าพลังงาน Off-peak | หน่วย Off-peak × {b['rate_off'].iloc[-1]:.4f} ฿/kWh ({TOU_OFF_MEAK_TIME}) |
| ค่า Demand | ความต้องการไฟฟ้าสูงสุดช่วง On-peak (kW) × {DEMAND_RATE} ฿/kW |
| ค่า Ft | หน่วยรวม × Ft ตามประกาศ กกพ. (ปรับทุก 4 เดือน) |
| ค่าปรับ PF | kVAR ส่วนที่เกิน {PF_KVAR_FACTOR:.0%} ของ Demand สูงสุด × {PF_PENALTY_RATE} ฿/kVAR |
| ค่าบริการ | {b['service'].iloc[-1]:,.2f} ฿/เดือน |
| VAT | (รวมทุกข้อข้างบน − ส่วนลด) × 7% |

**แนวทางลดค่าไฟกับอัตรา TOU:** ย้ายโหลดหนักไปเดินช่วง Off-peak/วันหยุด ·
คุม Demand ช่วง On-peak ไม่ให้เครื่องใหญ่สตาร์ทพร้อมกัน · ดูแล capacitor bank ให้ kVAR ต่ำกว่าเกณฑ์
""")

# --- 3) มิเตอร์ย่อย ---
with tab_sub:
    if sub is None:
        st.info("ยังอ่านไฟล์มิเตอร์ภายในไม่ได้ — ดูรายละเอียดที่แถบด้านซ้าย")
    else:
        meters = sub[sub["ประเภท"] == "มิเตอร์ย่อย"].copy()
        meters["สัดส่วนเดือน"] = (
            meters["kwh"] / meters.groupby("month")["kwh"].transform("sum") * 100
        )
        meters["mom"] = meters.groupby("สถานที่")["kwh"].pct_change() * 100

        with st.container(border=True, key="card_08"):
            st.subheader("Pareto — พื้นที่ไหนกินไฟสุด (สะสมทั้งช่วง)")
            pareto = (meters.groupby("สถานที่")["kwh"].sum()
                      .sort_values(ascending=False).reset_index())
            pareto["สะสม %"] = pareto["kwh"].cumsum() / pareto["kwh"].sum() * 100
            pareto["สัดส่วน"] = pareto["kwh"] / pareto["kwh"].sum() * 100
            pareto["เฉลี่ย/เดือน"] = pareto["kwh"] / max(meters["month"].nunique(), 1)
            bar = (
                alt.Chart(pareto)
                .mark_bar(color=COLOR_GRID)
                .encode(
                    x=alt.X("สถานที่:N", sort="-y", title=None,
                            axis=alt.Axis(labelAngle=-40, labelLimit=140)),
                    y=alt.Y("kwh:Q", title="พลังงานสะสม (kWh)"),
                    tooltip=[
                        "สถานที่",
                        alt.Tooltip("kwh:Q", title="สะสมทั้งช่วง (kWh)", format=",.0f"),
                        alt.Tooltip("เฉลี่ย/เดือน:Q", title="เฉลี่ย (kWh/เดือน)", format=",.0f"),
                        alt.Tooltip("สัดส่วน:Q", title="สัดส่วนทั้งหมด (%)", format=".1f"),
                        alt.Tooltip("สะสม %:Q", title="Pareto สะสม (%)", format=".0f"),
                    ],
                )
            )
            line = (
                alt.Chart(pareto)
                .mark_line(color=COLOR_ALERT, strokeWidth=2.5,
                           point=alt.OverlayMarkDef(size=40, color=COLOR_ALERT))
                .encode(
                    x=alt.X("สถานที่:N", sort=alt.EncodingSortField("kwh", order="descending")),
                    y=alt.Y("สะสม %:Q", title="สะสม (%)", scale=alt.Scale(domain=[0, 100])),
                )
            )
            st.altair_chart(
                alt.layer(bar, line).resolve_scale(y="independent").properties(height=380),
                width="stretch",
            )
            top3 = pareto.head(3)
            st.caption(
                "Top 3: " + " · ".join(
                    f"**{r['สถานที่']}** {r['kwh']:,.0f} kWh" for _, r in top3.iterrows()
                ) + f" — รวมกัน {top3['kwh'].sum() / pareto['kwh'].sum() * 100:.0f}% ของทั้งหมด"
            )

        with st.container(border=True, key="card_09"):
            st.subheader("ตารางมิเตอร์ย่อยรายเดือน (kWh)")
            pv = meters.pivot_table(index=["สถานที่", "เลขมิเตอร์"], columns="เดือน",
                                    values="kwh", aggfunc="sum")
            pv = pv.reindex(columns=[m for m in month_order if m in pv.columns])
            pv["รวม"] = pv.sum(axis=1)
            pv["สัดส่วน %"] = pv["รวม"] / pv["รวม"].sum() * 100
            pv = pv.sort_values("รวม", ascending=False).reset_index()
            # แถวรวมทุกมิเตอร์ปิดท้ายตาราง
            total_row = {c: pv[c].sum() for c in pv.columns
                         if pd.api.types.is_numeric_dtype(pv[c])}
            total_row.update({"สถานที่": "รวมทุกมิเตอร์", "เลขมิเตอร์": ""})
            pv_show = pd.concat([pv, pd.DataFrame([total_row])], ignore_index=True)

            # ฝังลูกศรเทียบเดือนก่อนไว้ในเซลล์เดียวกับตัวเลข เช่น "41,360 ▲+35%"
            month_cols = [m for m in month_order if m in pv_show.columns]
            disp = pv_show.copy()
            for i, m in enumerate(month_cols):
                vals = pv_show[m]
                if i == 0:
                    disp[m] = vals.map(lambda v: "" if pd.isna(v) else f"{v:,.0f}")
                    continue
                prev = pv_show[month_cols[i - 1]]
                pct = (vals - prev) / prev.where(prev != 0) * 100
                disp[m] = [
                    "" if pd.isna(v) else f"{v:,.0f}" + (
                        "" if pd.isna(p)
                        else f" {'▲' if p > 0 else ('▼' if p < 0 else '＝')}{p:+.0f}%"
                    )
                    for v, p in zip(vals, pct)
                ]

            def color_cell(val: str) -> str:
                if isinstance(val, str):
                    if "▲" in val:
                        return "color:#ef4444"
                    if "▼" in val:
                        return "color:#22c55e"
                return ""

            styler = disp.style
            styler = (styler.map(color_cell, subset=month_cols)
                      if hasattr(styler, "map")
                      else styler.applymap(color_cell, subset=month_cols))
            st.dataframe(
                styler, hide_index=True, width="stretch",
                column_config={
                    **{c: st.column_config.TextColumn(
                        c, help="kWh พร้อม % เทียบเดือนก่อน — แดง = เพิ่ม · เขียว = ลด")
                       for c in month_cols},
                    "รวม": st.column_config.NumberColumn("รวม", format="localized"),
                    "สัดส่วน %": st.column_config.NumberColumn("สัดส่วน %", format="%.1f"),
                },
            )
            st.download_button(
                "⬇️ ดาวน์โหลด CSV — ตารางมิเตอร์ย่อย",
                pv_show.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"submeter_table_{year_be}.csv",
                mime="text/csv",
            )

        col_l, col_r = st.columns([3, 2])
        with col_l:
            with st.container(border=True, key="card_10"):
                st.subheader("Heatmap การใช้ไฟ รายพื้นที่ × เดือน")
                chart = (
                    alt.Chart(meters)
                    .mark_rect()
                    .encode(
                        x=month_axis(),
                        y=alt.Y("สถานที่:N", title=None,
                                sort=alt.EncodingSortField("kwh", op="sum", order="descending"),
                                axis=alt.Axis(labelLimit=160)),
                        color=alt.Color("kwh:Q", title="kWh",
                                        scale=alt.Scale(type="symlog", scheme="orangered")),
                        tooltip=[
                            "สถานที่", "เลขมิเตอร์", "เดือน",
                            alt.Tooltip("kwh:Q", title="พลังงาน (kWh)", format=",.0f"),
                            alt.Tooltip("สัดส่วนเดือน:Q", title="สัดส่วนของเดือน (%)", format=".1f"),
                            alt.Tooltip("mom:Q", title="เทียบเดือนก่อน (%)", format="+.1f"),
                        ],
                    )
                    .properties(height=520)
                )
                st.altair_chart(chart, width="stretch")
        with col_r:
            with st.container(border=True, key="card_11"):
                st.subheader("แนวโน้มรายพื้นที่")
                default_stations = pareto.head(3)["สถานที่"].tolist()
                sel_st = st.multiselect("เลือกพื้นที่", pareto["สถานที่"].tolist(),
                                        default=default_stations,
                                        label_visibility="collapsed")
                if sel_st:
                    chart = (
                        alt.Chart(meters[meters["สถานที่"].isin(sel_st)])
                        .mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=50))
                        .encode(
                            x=month_axis(),
                            y=alt.Y("kwh:Q", title="kWh"),
                            color=alt.Color("สถานที่:N", title=None,
                                            legend=alt.Legend(orient="bottom", columns=1)),
                            tooltip=[
                                "สถานที่", "เลขมิเตอร์", "เดือน",
                                alt.Tooltip("kwh:Q", title="พลังงาน (kWh)", format=",.0f"),
                                alt.Tooltip("mom:Q", title="เทียบเดือนก่อน (%)", format="+.1f"),
                                alt.Tooltip("สัดส่วนเดือน:Q", title="สัดส่วนของเดือน (%)", format=".1f"),
                            ],
                        )
                        .properties(height=430)
                    )
                    st.altair_chart(chart, width="stretch")

        with st.container(border=True, key="card_12"):
            st.subheader("ตรวจกระทบยอด — Σ มิเตอร์ย่อย เทียบ (บิล MEA + Solar)")
            recon = meters.groupby("month")["kwh"].sum().rename("submeter").reset_index()
            grid_m = pd.concat(bills.values()).groupby("month")["kwh"].sum().rename("grid")
            recon = recon.merge(grid_m, on="month", how="outer")
            if solar is not None:
                recon = recon.merge(solar, on="month", how="left")
            recon["solar_kwh"] = recon.get("solar_kwh", pd.Series(dtype=float)).fillna(0)
            recon["supply"] = recon["grid"].fillna(0) + recon["solar_kwh"]
            recon["coverage_pct"] = (recon["submeter"] / recon["supply"] * 100).where(recon["supply"] > 0)
            recon["เดือน"] = recon["month"].map(MONTH_LABEL)

            recon["ต่าง"] = recon["submeter"] - recon["supply"]
            recon["ต่าง %"] = recon["coverage_pct"] - 100
            rec_long = recon.melt(
                id_vars=["เดือน", "ต่าง", "ต่าง %"], value_vars=["submeter", "supply"],
                var_name="ฝั่ง", value_name="kwh",
            ).replace({"submeter": "Σ มิเตอร์ย่อย", "supply": "บิล MEA + Solar"})
            chart = (
                alt.Chart(rec_long)
                .mark_bar()
                .encode(
                    x=month_axis(),
                    xOffset="ฝั่ง:N",
                    y=alt.Y("kwh:Q", title="kWh"),
                    color=alt.Color("ฝั่ง:N",
                                    scale=alt.Scale(domain=["Σ มิเตอร์ย่อย", "บิล MEA + Solar"],
                                                    range=["#64748b", COLOR_GRID])),
                    tooltip=[
                        "เดือน", "ฝั่ง",
                        alt.Tooltip("kwh:Q", title="พลังงาน (kWh)", format=",.0f"),
                        alt.Tooltip("ต่าง:Q", title="ส่วนต่าง (kWh)", format="+,.0f"),
                        alt.Tooltip("ต่าง %:Q", title="ส่วนต่าง (%)", format="+.1f"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")
            st.caption(
                "สองแท่งควรใกล้กัน — ถ้ามิเตอร์ย่อยสูง/ต่ำกว่ามาก แปลว่ามีจุดจดผิด มิเตอร์เสีย "
                "หรือโหลดที่ยังไม่มีมิเตอร์ครอบคลุม (ดูรายเดือนที่เกินเกณฑ์ในแท็บแจ้งเตือน)"
            )

# --- 4) Solar ---
with tab_solar:
    if solar is None or solar.empty:
        st.info("ยังไม่มีข้อมูล Solar ในไฟล์มิเตอร์ภายใน")
    else:
        solar_detail = sub[sub["ประเภท"] == "Solar"].copy()
        solar_total = solar["solar_kwh"].sum()
        # ประเมินมูลค่า: โซลาร์ผลิตช่วงกลางวันซึ่งส่วนใหญ่เป็น On-peak
        # → ใช้ (อัตรา On-peak + Ft) ของ 33/5 เป็นตัวคูณ (ประมาณการ)
        rate_map = main.set_index("month")
        sv = solar.copy()
        sv["มูลค่า"] = sv.apply(
            lambda r: r["solar_kwh"] * (
                rate_map.loc[r["month"], "rate_on"] + rate_map.loc[r["month"], "ft_rate"]
            ) if r["month"] in rate_map.index else pd.NA,
            axis=1,
        )
        saving = float(pd.to_numeric(sv["มูลค่า"], errors="coerce").sum())

        # มูลค่าประมาณรายแถวสำหรับ tooltip (อัตรา On-peak + Ft ของเดือนนั้น)
        solar_detail["มูลค่า"] = solar_detail.apply(
            lambda r: r["kwh"] * (
                rate_map.loc[r["month"], "rate_on"] + rate_map.loc[r["month"], "ft_rate"]
            ) if r["month"] in rate_map.index else 0,
            axis=1,
        )
        solar_detail["สัดส่วนชุด"] = (
            solar_detail["kwh"] / solar_detail.groupby("month")["kwh"].transform("sum") * 100
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Solar ผลิตรวม", f"{solar_total:,.0f} kWh", COLOR_SOLAR,
                     f"เฉลี่ย {solar_total / max(solar['month'].nunique(), 1):,.0f} kWh/เดือน")
        with c2:
            share = solar_total / (solar_total + main["kwh"].sum()) * 100
            kpi_card("สัดส่วนช่วยโรงงาน", f"{share:.1f}%", COLOR_SOLAR,
                     "ของพลังงานโรงงาน (33/5 + Solar)")
        with c3:
            kpi_card("ประหยัดค่าไฟ (ประมาณ)", f"{saving:,.0f} ฿", COLOR_COST,
                     "คิดที่อัตรา On-peak + Ft")

        st.markdown("")
        col_l, col_r = st.columns(2)
        with col_l:
            with st.container(border=True, key="card_13"):
                st.subheader("ผลิตได้รายเดือน แยกชุด")
                chart = (
                    alt.Chart(solar_detail)
                    .mark_bar()
                    .encode(
                        x=month_axis(),
                        y=alt.Y("kwh:Q", title="kWh"),
                        color=alt.Color("สถานที่:N", title=None,
                                        scale=alt.Scale(scheme="oranges"),
                                        legend=alt.Legend(orient="bottom")),
                        tooltip=[
                            "สถานที่", "เดือน",
                            alt.Tooltip("kwh:Q", title="ผลิตได้ (kWh)", format=",.0f"),
                            alt.Tooltip("มูลค่า:Q", title="ประหยัด ≈ (฿)", format=",.0f"),
                            alt.Tooltip("สัดส่วนชุด:Q", title="สัดส่วนของเดือน (%)", format=".1f"),
                        ],
                    )
                    .properties(height=320)
                )
                st.altair_chart(chart, width="stretch")
        with col_r:
            with st.container(border=True, key="card_14"):
                st.subheader("Solar ทดแทนไฟ MEA ได้กี่ % ในแต่ละเดือน")
                sh = solar.merge(main[["month", "kwh", "เดือน"]], on="month", how="inner")
                sh["share"] = sh["solar_kwh"] / (sh["solar_kwh"] + sh["kwh"]) * 100
                chart = (
                    alt.Chart(sh)
                    .mark_line(strokeWidth=3, color=COLOR_SOLAR,
                               point=alt.OverlayMarkDef(size=60, color=COLOR_SOLAR))
                    .encode(
                        x=month_axis(),
                        y=alt.Y("share:Q", title="สัดส่วน Solar (%)",
                                scale=alt.Scale(domain=[0, 60])),
                        tooltip=[
                            "เดือน",
                            alt.Tooltip("share:Q", title="สัดส่วน Solar (%)", format=".1f"),
                            alt.Tooltip("solar_kwh:Q", title="Solar ผลิต (kWh)", format=",.0f"),
                            alt.Tooltip("kwh:Q", title="ไฟจาก MEA (kWh)", format=",.0f"),
                        ],
                    )
                    .properties(height=320)
                )
                st.altair_chart(chart, width="stretch")
        st.caption(
            "⚠️ มูลค่าที่ประหยัดเป็นการประมาณ — สมมุติว่าไฟ Solar ทั้งหมดถูกใช้ทดแทนหน่วย On-peak "
            "(โซลาร์ผลิตกลางวันตรงกับช่วง On-peak จันทร์–ศุกร์) และยังไม่รวมผลลด Demand"
        )

# --- 5) แจ้งเตือน ---
with tab_alert:
    alerts_found = 0

    st.subheader("🔌 Power Factor / kVAR")
    pf_bad = main[main["pf_penalty"] > 0]
    kvar_near = main[(main["pf_penalty"] <= 0)
                     & (main["kvar"] >= main["kvar_limit"] * 0.9)
                     & main["kvar_limit"].gt(0)]
    for _, r in pf_bad.iterrows():
        alerts_found += 1
        st.error(
            f"เดือน{r['month_name']}: โดนค่าปรับ PF **{r['pf_penalty']:,.2f} บาท** "
            f"(kVAR {r['kvar']:,.0f} เกินเกณฑ์ {r['kvar_limit']:,.0f}) — "
            f"ตรวจสอบ capacitor bank ว่าตัดการทำงานหรือเสื่อม"
        )
    for _, r in kvar_near.iterrows():
        alerts_found += 1
        st.warning(
            f"เดือน{r['month_name']}: kVAR {r['kvar']:,.0f} ใกล้เกณฑ์ {r['kvar_limit']:,.0f} "
            f"(เกิน 90%) — เสี่ยงโดนค่าปรับ {PF_PENALTY_RATE} ฿/kVAR เดือนถัดไป"
        )
    if pf_bad.empty and kvar_near.empty:
        st.success("PF ทุกเดือนอยู่ในเกณฑ์ ไม่มีค่าปรับ")

    st.subheader("📈 Demand On-peak พุ่งผิดปกติ")
    d = main.dropna(subset=["demand_on"]).sort_values("month")
    demand_alerts = []
    for i in range(1, len(d)):
        baseline = d["demand_on"].iloc[max(0, i - 3):i].mean()
        cur = d["demand_on"].iloc[i]
        if baseline > 0 and cur > baseline * (1 + th_demand / 100):
            demand_alerts.append((d["month_name"].iloc[i], cur, baseline))
    for mn, cur, base in demand_alerts:
        alerts_found += 1
        extra_cost = (cur - base) * DEMAND_RATE
        st.warning(
            f"เดือน{mn}: Demand {cur:,.0f} kW สูงกว่าค่าเฉลี่ย 3 เดือนก่อน ({base:,.0f} kW) "
            f"เกิน {th_demand}% — ค่า Demand เพิ่ม ≈ {extra_cost:,.0f} บาท "
            f"ลองเช็คว่าเดินเครื่องใหญ่พร้อมกันช่วง On-peak หรือไม่"
        )
    if not demand_alerts:
        st.success(f"Demand ไม่มีเดือนไหนพุ่งเกินเกณฑ์ +{th_demand}%")

    st.subheader("⚡ ค่า Ft เปลี่ยน")
    ft = main.dropna(subset=["ft_rate"]).sort_values("month")
    ft_changes = ft[ft["ft_rate"].diff().fillna(0) != 0]
    for _, r in ft_changes.iterrows():
        impact = (r["ft_rate"] - ft["ft_rate"].shift().loc[r.name]) * main["kwh"].mean()
        st.info(
            f"เดือน{r['month_name']}: Ft เปลี่ยนเป็น {r['ft_rate']:.4f} ฿/kWh "
            f"— กระทบค่าไฟ ≈ {impact:+,.0f} บาท/เดือน (ที่การใช้เฉลี่ยปัจจุบัน)"
        )

    st.subheader("🏢 มิเตอร์ย่อยผิดปกติ")
    if sub is None:
        st.info("ไม่มีข้อมูลมิเตอร์ย่อย")
    else:
        meters = sub[sub["ประเภท"] == "มิเตอร์ย่อย"]
        meter_alerts = []
        for station, g in meters.groupby("สถานที่"):
            g = g.sort_values("month")
            prev_kwh, prev_m = None, None
            for _, r in g.iterrows():
                if prev_kwh is not None:
                    # ค่ากระโดด (เฉพาะมิเตอร์ที่ใช้เกิน 100 kWh/เดือน กันสัญญาณรบกวนจากจุดเล็ก ๆ)
                    if prev_kwh >= 100 and abs(r["kwh"] - prev_kwh) / prev_kwh * 100 > th_meter:
                        meter_alerts.append(
                            f"**{station}** เดือน{MONTH_LABEL[r['month']]}: "
                            f"{r['kwh']:,.0f} kWh (เดือนก่อน {prev_kwh:,.0f}) "
                            f"เปลี่ยน {(r['kwh'] - prev_kwh) / prev_kwh * 100:+.0f}%"
                        )
                    # ค่าค้างเท่าเดิมเป๊ะ — อาจลืมจดหรือมิเตอร์ค้าง
                    elif r["kwh"] == prev_kwh and r["kwh"] > 0:
                        meter_alerts.append(
                            f"**{station}**: ค่าเดือน{MONTH_LABEL[prev_m]} กับ {MONTH_LABEL[r['month']]} "
                            f"เท่ากันเป๊ะ ({r['kwh']:,.0f} kWh) — เช็คว่าลืมจดหรือมิเตอร์ค้าง"
                        )
                prev_kwh, prev_m = r["kwh"], r["month"]
        if meter_alerts:
            alerts_found += len(meter_alerts)
            for a in meter_alerts:
                st.warning(a)
        else:
            st.success(f"ไม่มีมิเตอร์ที่ค่าเปลี่ยนเกิน ±{th_meter}% หรือค่าค้าง")

        st.subheader("🧮 กระทบยอดมิเตอร์ย่อย vs บิล+Solar")
        recon_alerts = []
        grid_m = pd.concat(bills.values()).groupby("month")["kwh"].sum()
        sol_m = (solar.set_index("month")["solar_kwh"] if solar is not None
                 else pd.Series(dtype=float))
        for m, g in meters.groupby("month"):
            supply = grid_m.get(m, 0) + sol_m.get(m, 0)
            if supply <= 0:
                continue
            diff_pct = (g["kwh"].sum() - supply) / supply * 100
            if abs(diff_pct) > th_recon:
                recon_alerts.append(
                    f"เดือน{MONTH_LABEL[m]}: Σ มิเตอร์ย่อย {g['kwh'].sum():,.0f} kWh "
                    f"ต่างจากบิล+Solar ({supply:,.0f} kWh) อยู่ {diff_pct:+.0f}%"
                )
        if recon_alerts:
            alerts_found += len(recon_alerts)
            for a in recon_alerts:
                st.warning(a)
        else:
            st.success(f"ยอดทุกเดือนต่างกันไม่เกิน ±{th_recon}%")

    if alerts_found == 0:
        st.balloons()

# --- 6) ข้อมูล + ดาวน์โหลด ---
with tab_data:
    def _fmt_num(v: float) -> str:
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        if abs(v) >= 10:
            return f"{v:,.2f}"
        return f"{v:,.4f}"

    def with_arrows(df: pd.DataFrame, skip: tuple = ("month",)):
        """Styler: คอลัมน์ตัวเลขทุกคอลัมน์ต่อท้ายด้วย ▲▼% เทียบแถว (เดือน) ก่อนหน้า
        แดง = เพิ่ม · เขียว = ลด · ค่าเท่าเดิม/แถวแรกไม่ใส่ลูกศร"""
        INF = float("inf")

        def suffix(p) -> str:
            if pd.isna(p) or p == 0:
                return ""
            if p in (INF, -INF):          # เดือนก่อนเป็น 0 เช่น ค่าปรับ PF เพิ่งโผล่
                return " ▲ใหม่"
            return f" {'▲' if p > 0 else '▼'}{p:+.1f}%"

        disp = df.copy()
        arrow_cols = []
        for c in df.columns:
            if c in skip or not pd.api.types.is_numeric_dtype(df[c]):
                continue
            pct = df[c].pct_change() * 100
            disp[c] = ["" if pd.isna(v) else _fmt_num(v) + suffix(p)
                       for v, p in zip(df[c], pct)]
            arrow_cols.append(c)

        def paint(val: str) -> str:
            if isinstance(val, str):
                if "▲" in val:
                    return "color:#ef4444;font-weight:600"
                if "▼" in val:
                    return "color:#22c55e;font-weight:600"
            return ""

        s = disp.style
        return (s.map(paint, subset=arrow_cols) if hasattr(s, "map")
                else s.applymap(paint, subset=arrow_cols))

    for name, b in bills.items():
        with st.expander(f"บิล {name} — {len(b)} เดือน", expanded=(name == MAIN_BILL)):
            st.dataframe(with_arrows(b), hide_index=True, width="stretch")
            st.download_button(
                f"⬇️ ดาวน์โหลด CSV — บิล {name}",
                b.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"bill_{name.replace('/', '-').replace(' ', '_')}_{year_be}.csv",
                mime="text/csv",
            )
    if sub is not None:
        with st.expander(f"มิเตอร์ภายใน + Solar — {sub['สถานที่'].nunique()} จุด"):
            st.dataframe(sub, hide_index=True, width="stretch")
            st.download_button(
                "⬇️ ดาวน์โหลด CSV — มิเตอร์ภายใน",
                sub.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"submeters_{year_be}.csv",
                mime="text/csv",
            )
    st.caption(
        f"แหล่งข้อมูล: {ENERGY_DIR}\n\n"
        "อัปเดตไฟล์ Excel บน OneDrive แล้วหน้าจอจะรีเฟรชเองภายใน ~30 วินาที "
        "(หรือกดปุ่ม 🔄 ที่แถบด้านซ้าย)"
    )
