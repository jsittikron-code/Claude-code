"""Dashboard ภาพรวมฝ่ายวิศวกรรมกระบวนการผลิต — รวม 4 ระบบในหน้าเดียว แบบ Real-Time
=============================================================================
สรุป KPI หลักของทั้ง 4 ระบบ โดยคงสูตรคำนวณเดิมของแอปต้นทางทุกตัว:

  🟢 ศูนย์ปฏิบัติการเครื่องจักร  ← workcenter_monitor.py  (สถานะสด RUN/IDLE/DOWN)
  🛠️ ระบบบริหารใบงานซ่อม      ← maintenance_dashboard.py (งานซ่อม 6 หมวด PM/BM ค่าใช้จ่าย)
  ⚙️ ระบบบริหาร OEE            ← oee_manager.py           (A/P/Q/OEE แบบ cap เทียบเป้า)
  ⚡ ระบบบริหารพลังงานโรงงาน   ← energy_monitor.py        (บิล MEA TOU + Solar)

Real-Time: แต่ละส่วนเป็น st.fragment ที่รีเฟรชตัวเองอัตโนมัติ (30-60 วินาที)
และใช้ mtime ของไฟล์ต้นทางเป็น cache key — ไฟล์ Excel บน OneDrive ถูกแก้เมื่อไร
ตัวเลขบนจอจะโหลดใหม่เองในรอบรีเฟรชถัดไป โดยไม่ต้องกดปุ่มใดๆ

รัน: python -m streamlit run overview_dashboard.py --server.port 8507
(หรือดับเบิลคลิก run_overview.bat)
"""

import calendar
import glob
import os
import re
import time
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

import auth
import data_paths
import mos_loader

# ===========================================================================
# ค่าคงที่ร่วม — เส้นทางไฟล์ฐานข้อมูลของฝ่าย (ชุดเดียวกับแอปต้นทาง)
# ===========================================================================
DEPT_DIR = r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD\ฝ่ายซ่อมบำรุงรักษา"

TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def month_label(ts) -> str:
    """2026-03-01 → 'มี.ค. 69' (สูตรเดียวกับ oee_manager.py)"""
    return f"{TH_MONTHS[ts.month - 1]} {(ts.year + 543) % 100:02d}"


def _read_sheet(path, sheet, header=0):
    """อ่านชีตด้วย calamine (เร็ว) ถ้าไม่ได้ลอง openpyxl · ไฟล์ถูกล็อกลองซ้ำ 1 ครั้ง"""
    last_err = None
    for _ in range(2):
        for engine in ("calamine", None):
            try:
                return pd.read_excel(path, sheet_name=sheet, header=header, engine=engine)
            except PermissionError as e:
                last_err = e
                break  # ล็อกทั้งไฟล์ — เปลี่ยน engine ไปก็ไม่ช่วย
            except Exception as e:
                last_err = e
        time.sleep(1.5)
    raise last_err


def _mtime(path) -> float:
    return os.path.getmtime(path) if os.path.exists(path) else 0.0


def fmt_pct(v, digits=1) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.{digits}f}%"


# ===========================================================================
# ส่วนที่ 1: Workcenter — สถานะเครื่องจักรสด (ตรรกะจาก workcenter_monitor.py)
# ===========================================================================
WC_MASTER = os.path.join(DEPT_DIR, r"9.workcenter operation\Workcenter_ฐานข้อมูลหลัก_2569.xlsx")
WC_IDLE_MIN = 20  # นาทีที่ไม่มีสแกนใหม่แล้วถือว่า "ว่าง" (ค่าตั้งต้นเดียวกับแอปเต็ม)

GROUP_NAMES = {
    "CT": "เครื่องตัด", "DL": "เครื่องเจาะ / CNC", "EG": "เครื่องปิดขอบ",
    "CO": "บู้ทพ่นสี", "PO": "เครื่องขัดเงา", "MO": "เครื่องเพลาตั้ง",
    "MS": "งานขัดด้วยมือ", "MB": "งานปัดเงา", "LA": "เครื่องปิดผิว",
    "PR": "เครื่อง Membrane", "SF": "เครื่องห่อโค้ง", "AL": "ประกอบอลูมิเนียม",
    "AD": "หน่วยงานรับ/ส่งงาน", "SKL": "หน่วยงานฝีมือ", "RP": "ซ่อมสร้าง / ซ่อมบำรุง",
}
STATUS_RUN = "🟢 กำลังทำงาน"
STATUS_IDLE = "🟡 ว่าง / ไม่มีการสแกน"
STATUS_DOWN = "🔴 หยุดเครื่อง"
STATUS_NODATA = "⚪ ไม่มีข้อมูลวันนี้"
STATUS_COLORS = {STATUS_RUN: "#0ca30c", STATUS_IDLE: "#fab219",
                 STATUS_DOWN: "#d03b3b", STATUS_NODATA: "#9a9891"}
STATUS_ORDER = [STATUS_RUN, STATUS_IDLE, STATUS_DOWN, STATUS_NODATA]


def wc_signature() -> tuple:
    # ต้องรวมลายเซ็นโฟลเดอร์ raw ด้วย เพราะหลังย้ายมาใช้ไฟล์ดิบจาก MOS แล้ว
    # ไฟล์ master จะไม่ถูกแก้อีก ถ้าดูแต่ master แอปจะไม่รู้ว่ามีข้อมูลใหม่
    return (_mtime(WC_MASTER), tuple(tuple(x) for x in mos_loader.signature()))


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านฐานข้อมูล Workcenter...")
def load_workcenter(sig):
    """ชีต Data ของฐานหลัก → (ธุรกรรมของวันล่าสุด, รายชื่อเครื่องช่วง 30 วัน, วันล่าสุด)"""
    # อ่านผ่าน mos_loader — ตรรกะเดียวกับ workcenter_monitor.py
    df = mos_loader.load_workcenter()
    need = ["Machine", "พนักงาน", "Job", "หมวดJob", "Qty", "Start", "End"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError("ฐาน Workcenter ขาดคอลัมน์: " + ", ".join(missing))
    df = df.rename(columns={"พนักงาน": "Name", "หมวดเครื่อง": "Group"})
    df = df[df["Machine"].notna()].copy()
    df["Machine"] = df["Machine"].astype(str).str.strip()
    df["Start"] = pd.to_datetime(df["Start"], errors="coerce")
    df["End"] = pd.to_datetime(df["End"], errors="coerce")
    df = df.dropna(subset=["Start", "End"])
    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
    # ตรรกะเดียวกับแอปเต็ม: หมวดJob ที่ไม่ขึ้นต้น PROD = งานหยุดเครื่อง (P/B/BP)
    df["IsDowntime"] = ~df["หมวดJob"].astype(str).str.startswith("PROD")
    if "Reason" not in df.columns:
        df["Reason"] = pd.NA

    latest = df["Start"].dt.date.max()
    # เครื่องทั้งหมดที่เคยปรากฏในฐาน (ชุดเดียวกับแอปเต็ม —
    # ให้เครื่องที่วันนี้ยังไม่สแกนโชว์เป็น ⚪ ด้วย)
    machines = sorted(df["Machine"].unique())
    keep = [c for c in ("Machine", "Name", "Job", "Qty", "Start", "End",
                        "IsDowntime", "Reason", "Description") if c in df.columns]
    day = df[df["Start"].dt.date == latest][keep].copy()
    return day, machines, latest


def machine_status(day_df, all_machines, ref_time, idle_min) -> pd.DataFrame:
    """สถานะรายเครื่อง ณ เวลา ref_time (สูตรเดียวกับ workcenter_monitor.py)"""
    rows = []
    by_mc = dict(tuple(day_df.groupby("Machine")))
    for mc in all_machines:
        g = by_mc.get(mc)
        if g is None or g.empty:
            rows.append({"Machine": mc, "สถานะ": STATUS_NODATA})
            continue
        down = g[g["IsDowntime"]]
        last_end = g["End"].max()
        active_down = down[(down["Start"] <= ref_time) & (down["End"] >= ref_time)]
        idle_gap = (ref_time - last_end).total_seconds() / 60
        if not active_down.empty:
            status = STATUS_DOWN
        elif idle_gap <= idle_min:
            status = STATUS_RUN
        else:
            status = STATUS_IDLE
        rows.append({"Machine": mc, "สถานะ": status})
    out = pd.DataFrame(rows)
    out["Group"] = (
        out["Machine"].str.extract(r"^([A-Za-z]+)")[0].str.upper()
        .map(lambda g: GROUP_NAMES.get(g, g))
    )
    return out


# ===========================================================================
# ส่วนที่ 2: ใบงานซ่อม 6 หมวด (ตรรกะจาก maintenance_dashboard.py)
# ===========================================================================
# หาโฟลเดอร์ใบแจ้งซ่อมเอง ไม่ฝังชื่อโฟลเดอร์ไว้ในโค้ด (ดู data_paths.py)
MT_DIR = data_paths.repair_dir()
MT_FILES = {
    "เครื่องจักร": "รายงานซ่อมบำรุง_เครื่อง_2020-2026.xlsx",
    "ซ่อมสร้าง": "รายงานซ่อมบำรุง_ซ่อมสร้าง_2020-2026.xlsx",
    "ลับคม": "รายงานซ่อมบำรุง_ลับคม_2020-2026.xlsx",
    "ซ่อมรถยนต์": "รายงานซ่อมบำรุง_ซ่อมรถยนต์_2020-2026.xlsx",
    "เครื่องมือเล็ก": "รายงานซ่อมบำรุง_เครื่องมือเล็ก_2020-2026.xlsx",
    "ดัดแปลง": "รายงานซ่อมบำรุง_ดัดแปลง_2020-2026.xlsx",
}
CATS = list(MT_FILES.keys())
CAT_COLORS = {
    "เครื่องจักร": "#2a78d6", "ซ่อมสร้าง": "#eb6834", "ลับคม": "#1baf7a",
    "ซ่อมรถยนต์": "#eda100", "เครื่องมือเล็ก": "#e87ba4", "ดัดแปลง": "#008300",
}
CAT_SCALE = alt.Scale(domain=CATS, range=[CAT_COLORS[c] for c in CATS])


def mt_signature() -> tuple:
    return tuple(_mtime(os.path.join(MT_DIR, f)) for f in MT_FILES.values())


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านใบงานซ่อม 6 หมวด...")
def load_maintenance(sig):
    """ไฟล์รายงานซ่อมบำรุงทั้ง 6 หมวด → ตารางรวม (สูตร normalize เดียวกับแอปเต็ม)"""
    frames, missing = [], []
    for cat, fname in MT_FILES.items():
        path = os.path.join(MT_DIR, fname)
        if not os.path.exists(path):
            missing.append(fname)
            continue
        try:
            raw = _read_sheet(path, "ข้อมูล")
        except Exception:
            missing.append(fname + " (ไฟล์ถูกล็อกอยู่)")
            continue
        raw.columns = [str(c).strip() for c in raw.columns]

        def col(name):
            return raw[name] if name in raw.columns else pd.Series([None] * len(raw), index=raw.index)

        df = pd.DataFrame(index=raw.index)
        df["หมวด"] = cat
        df["ปี"] = pd.to_numeric(col("ปี"), errors="coerce")
        df["เดือน"] = pd.to_numeric(col("เดือน"), errors="coerce")
        df["สถานะ"] = col("สถานะการซ่อม (PM/BM)").astype(str).str.strip().str.upper()
        df["สถานะ"] = df["สถานะ"].where(df["สถานะ"].isin(["PM", "BM"]), "ไม่ระบุ")
        df["นาที"] = pd.to_numeric(col("เวลาซ่อม (นาที)"), errors="coerce").fillna(0)
        df["ค่าใช้จ่าย"] = (
            pd.to_numeric(col("ค่าใช้จ่าย (บาท)"), errors="coerce").fillna(0)
            + pd.to_numeric(col("Petty Cash (บาท)"), errors="coerce").fillna(0)
        )
        df = df[df["ปี"].between(2019, 2030) & df["เดือน"].between(1, 12)]
        df["ปี"] = df["ปี"].astype(int)
        df["เดือน"] = df["เดือน"].astype(int)
        df["เดือนปี"] = pd.to_datetime(dict(year=df["ปี"], month=df["เดือน"], day=1))
        frames.append(df)
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return data, missing


# ===========================================================================
# ส่วนที่ 3: OEE (ตรรกะจาก oee_manager.py — สูตร cap + ผลรวมเป็นตัวตั้ง/ตัวหาร)
# ===========================================================================
OEE_PATH = os.path.join(DEPT_DIR, r"3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx")
OEE_TARGETS = {"OEE": 85.0, "A": 90.0, "P": 95.0, "Q": 99.9}
METRIC_COLORS = {"OEE": "#4a3aa7", "A": "#2a78d6", "P": "#eb6834", "Q": "#1baf7a"}
# คอลัมน์หมวดการสูญเสียเวลาในชีต Report1 (ชุดเดียวกับแอปเต็ม — ใช้ตรวจแถวผิดปกติ)
OEE_LOSS_COLS = ["Break_time_b", "Break_time_bp", "Break_time_p", "Setup",
                 "Break_time_noemp", "Break_time_S", "Others"]


def oee_signature() -> tuple:
    return (_mtime(OEE_PATH),)


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านฐานข้อมูลหลัก OEE...")
def load_oee(sig):
    """ชีต Report1 → ตารางรายวันรายเครื่อง พร้อม A/P/Q/OEE ตามสูตร cap (ชุดเดียวกับแอปเต็ม)"""
    raw = _read_sheet(OEE_PATH, "Report1")
    raw.columns = [str(c).strip() for c in raw.columns]

    def col(name, default=0):
        if name in raw.columns:
            return pd.to_numeric(raw[name], errors="coerce").fillna(default)
        return pd.Series([default] * len(raw), index=raw.index, dtype="float64")

    df = pd.DataFrame(index=raw.index)
    df["Machine"] = raw["MC"].astype(str).str.strip()
    df["วันที่"] = pd.to_datetime(raw["Trans_date"], errors="coerce")
    df["PlanMin"] = col("เวลาทำงาน/วัน")
    df["RunMin"] = col("เวลาทำงานจริง/วัน")
    df["LossMin"] = col("เวลาสูญเสีย/วัน")
    df["Cap"] = col("Cap")
    df["Pieces"] = col("จำนวน(ชิ้น)/วัน")
    df["Good"] = col("ชิ้นงานดี(ชิ้น)/วัน")
    for c in OEE_LOSS_COLS:
        df[c] = col(c)
    df = df[df["วันที่"].notna() & (df["Machine"] != "") & (df["Machine"] != "nan")].copy()

    # ตรวจความสมเหตุสมผลของแถว — ชุดเดียวกับหน้า "คุณภาพข้อมูล" ของแอปเต็ม
    bad = (
        (df["PlanMin"] <= 0) | (df["RunMin"] < 0)
        | ((df["PlanMin"] > 0) & (df["RunMin"] > df["PlanMin"]))
        | (df["LossMin"] < 0)
        | (df[OEE_LOSS_COLS] < 0).any(axis=1)
        | (df["Pieces"] < 0) | (df["Good"] < 0)
        | ((df["Good"] > df["Pieces"]) & (df["Good"] >= 0))
    )
    df["ผิดปกติ"] = bad

    # ค่าที่ cap แล้ว ใช้เป็นตัวตั้ง/ตัวหารทุกระดับ
    df["RunCap"] = df["RunMin"].clip(lower=0).where(
        df["PlanMin"] <= 0, df[["RunMin", "PlanMin"]].min(axis=1).clip(lower=0))
    df["PieceCap"] = df[["Pieces", "Cap"]].min(axis=1).clip(lower=0).where(df["Cap"] > 0, 0.0)
    df["GoodCap"] = df[["Good", "Pieces"]].min(axis=1).clip(lower=0)

    df["ปี"] = df["วันที่"].dt.year
    df["เดือนปี"] = df["วันที่"].values.astype("datetime64[M]").astype("datetime64[ns]")
    df["เดือน"] = df["เดือนปี"].map(month_label)
    return df.reset_index(drop=True)


def agg_metrics(d: pd.DataFrame) -> dict:
    """สรุป A/P/Q/OEE — ผลรวมเป็นตัวตั้ง/ตัวหาร ไม่ใช่ค่าเฉลี่ยของ % (สูตรเดิมของแอปเต็ม)"""
    base = d[d["Cap"] > 0]
    if base.empty:
        base = d
    plan = float(base["PlanMin"].sum())
    run = float(base["RunCap"].sum())
    cap = float(base.loc[base["Cap"] > 0, "Cap"].sum())
    piece_cap = float(base.loc[base["Cap"] > 0, "PieceCap"].sum())
    prod = base[base["Pieces"] > 0]
    pieces_q = float(prod["Pieces"].sum())
    good_q = float(prod["GoodCap"].sum())

    a = run / plan * 100 if plan > 0 else float("nan")
    p = piece_cap / cap * 100 if cap > 0 else float("nan")
    q = good_q / pieces_q * 100 if pieces_q > 0 else float("nan")
    oee = a * p * q / 10000 if not (pd.isna(a) or pd.isna(p) or pd.isna(q)) else float("nan")
    return {"A": a, "P": p, "Q": q, "OEE": oee,
            "วัน": int(len(d)), "เครื่อง": int(d["Machine"].nunique())}


# ===========================================================================
# ส่วนที่ 4: พลังงานโรงงาน (ตรรกะจาก energy_monitor.py — บิล MEA TOU + Solar)
# ===========================================================================
ENERGY_DIR = os.path.join(DEPT_DIR, r"4.เรื่องการใช้ปริมาณไฟฟ้าภายในโรงงาน\งานระบบไฟฟ้าโรงงาน")
DEMAND_RATE = 132.93        # บาท/kW ของ Demand ช่วง On-peak
PF_PENALTY_RATE = 56.07     # บาท/kVAR ส่วนที่เกินเกณฑ์
PF_KVAR_FACTOR = 0.6197     # เกณฑ์ kVAR = 61.97% ของ Demand สูงสุด (PF 0.85)
VAT_RATE = 0.07
COLOR_COST = "#16a34a"
COLOR_SOLAR = "#f59e0b"
THAI_MONTHS_FULL = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4,
    "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8,
    "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}
THAI_MONTH_ABBR = {"มค": 1, "กพ": 2, "มีค": 3, "เมย": 4, "พค": 5, "มิย": 6,
                   "กค": 7, "สค": 8, "กย": 9, "ตค": 10, "พย": 11, "ธค": 12}
MONTH_LABEL = {i + 1: m for i, m in enumerate(TH_MONTHS)}


def _clean(text) -> str:
    return re.sub(r"[\s\u200b\.]+", "", str(text))


def _num(series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def energy_year() -> int | None:
    """ปี พ.ศ. ล่าสุดที่มีไฟล์สรุปค่าไฟแล้วจริงใต้โฟลเดอร์ Bill_33-5"""
    d = os.path.join(ENERGY_DIR, "งานระบบไฟฟ้า", "Bill_33-5")
    if not os.path.isdir(d):
        return None
    years = [int(x) for x in os.listdir(d) if x.isdigit()
             and os.path.exists(os.path.join(d, x, f"สรุปค่าไฟฟ้า {x}.xlsx"))]
    return max(years) if years else None


def bill_path(year_be: int) -> str:
    return os.path.join(ENERGY_DIR, "งานระบบไฟฟ้า", "Bill_33-5",
                        str(year_be), f"สรุปค่าไฟฟ้า {year_be}.xlsx")


def submeter_path(year_be: int) -> str | None:
    pat = os.path.join(ENERGY_DIR, "ระบบไฟฟ้าภายใน", "**", f"สรุปมิเตอร์ภายใน*{year_be}*.xlsx")
    files = glob.glob(pat, recursive=True)
    return max(files, key=os.path.getmtime) if files else None


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านบิลค่าไฟ...")
def load_bill(path: str, year_be: int, file_mtime: float | None = None) -> pd.DataFrame:
    """บิลไฟ MEA 33/5 — คำนวณโครงสร้างค่าไฟ TOU ใหม่ (สูตรเดียวกับแอปเต็ม)"""
    raw = pd.read_excel(path, sheet_name=0, header=None, engine="openpyxl")
    header_idx = None
    for i in range(min(5, len(raw))):
        if _clean(raw.iloc[i, 0]) in ("Mounth", "Month"):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("ไม่พบแถวหัวตาราง (Mounth) ในไฟล์บิล")

    header = [_clean(c) for c in raw.iloc[header_idx]]
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = header
    col_map = {
        "Mounth": "month_name", "Total/Kwh/Unit": "kwh",
        "E_On_peak": "kwh_on", "RateOnPeak": "rate_on",
        "E_Off_peak": "kwh_off", "RateOffPeak": "rate_off",
        "Demand_E_On": "demand_on", "Demand_E_Off": "demand_off",
        "กิโลวาร์(kVAR)": "kvar", "Ft/ตามสถานการณ์": "ft_rate",
        "PF/Capasister": "pf_factor", "ค่าปรับPF": "pf_penalty",
        "บริการ": "service", "Vat": "vat_rate", "ส่วนลด": "discount",
    }
    df = df.loc[:, [c for c in col_map if c in df.columns]].rename(columns=col_map)
    df["month_name"] = df["month_name"].astype(str).str.strip()
    df = df[df["month_name"].isin(THAI_MONTHS_FULL)].copy()
    df["month"] = df["month_name"].map(THAI_MONTHS_FULL)
    for c in df.columns:
        if c != "month_name":
            df[c] = _num(df[c])
    df = df.dropna(subset=["kwh"])

    df["rate_on"] = df.get("rate_on", pd.Series(dtype=float)).fillna(0)
    df["rate_off"] = df.get("rate_off", pd.Series(dtype=float)).fillna(0)
    df["energy_on"] = df["kwh_on"].fillna(0) * df["rate_on"]
    df["energy_off"] = df["kwh_off"].fillna(0) * df["rate_off"]
    df["demand_charge"] = df.get("demand_on", pd.Series(dtype=float)).fillna(0) * DEMAND_RATE
    df["ft_charge"] = df["kwh"] * df.get("ft_rate", pd.Series(dtype=float)).fillna(0)
    demand_max = df[["demand_on", "demand_off"]].max(axis=1).fillna(0)
    df["kvar_limit"] = demand_max * df.get("pf_factor", pd.Series(dtype=float)).fillna(PF_KVAR_FACTOR)
    kvar_excess = (df.get("kvar", pd.Series(dtype=float)).fillna(0) - df["kvar_limit"]).clip(lower=0)
    df["pf_penalty"] = df.get("pf_penalty", pd.Series(dtype=float)).fillna(
        kvar_excess.round() * PF_PENALTY_RATE)
    df["service"] = df.get("service", pd.Series(dtype=float)).fillna(312.24)
    df["discount"] = df.get("discount", pd.Series(dtype=float)).fillna(0)
    base = (df["energy_on"] + df["energy_off"] + df["demand_charge"]
            + df["ft_charge"] + df["pf_penalty"] + df["service"])
    df["vat"] = base * df.get("vat_rate", pd.Series(dtype=float)).fillna(VAT_RATE)
    df["total_cost"] = base + df["vat"] - df["discount"]
    df["avg_rate"] = (df["total_cost"] / df["kwh"]).where(df["kwh"] > 0)

    year_ce = year_be - 543
    hours = df["month"].map(lambda m: calendar.monthrange(year_ce, int(m))[1] * 24)
    df["load_factor"] = (df["kwh"] / (demand_max * hours) * 100).where(demand_max > 0)
    df["เดือน"] = df["month"].map(MONTH_LABEL)
    return df.sort_values("month").reset_index(drop=True)


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านมิเตอร์ภายใน...")
def load_submeters(path: str, year_be: int, file_mtime: float | None = None) -> pd.DataFrame:
    """มิเตอร์ย่อยภายใน + Solar (โครงสร้างชีตเดียวกับแอปเต็ม)"""
    raw = pd.read_excel(path, sheet_name=0, header=None, engine="openpyxl")
    header_idx = None
    for i in range(min(10, len(raw))):
        if str(raw.iloc[i, 0]).strip() == "#":
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("ไม่พบหัวตารางมิเตอร์ (#) ในชีตแรก")
    month_cols = {}
    for j in range(raw.shape[1]):
        m = THAI_MONTH_ABBR.get(_clean(raw.iloc[header_idx, j]))
        if m:
            month_cols[j] = m
    rows = []
    section = "มิเตอร์ย่อย"
    for i in range(header_idx + 1, len(raw)):
        first = str(raw.iloc[i, 0]).strip()
        if "Solar" in first:
            section = "Solar"
            continue
        if not re.fullmatch(r"\d+", first):
            continue
        station = str(raw.iloc[i, 1]).strip()
        if station in ("", "nan"):
            continue
        for j, m in month_cols.items():
            kwh = _num(pd.Series([raw.iloc[i, j]]))[0]
            if pd.notna(kwh):
                rows.append({"ประเภท": section, "สถานที่": station, "month": m,
                             "kwh": float(kwh)})
    return pd.DataFrame(rows)


# ===========================================================================
# สไตล์นำเสนอผู้บริหาร — แถบหัวเรื่อง + การ์ดสรุปภาพใหญ่ + ตัวเลขใหญ่อ่านง่ายบนจอประชุม
# (โทนเดียวกับ hero ของระบบ OEE — ใช้ได้ทั้งธีมสว่างและมืด)
# ===========================================================================
ACC_WC = "#21a559"    # เขียว — ศูนย์ปฏิบัติการเครื่องจักร
ACC_OEE = "#4a3aa7"   # ม่วง — ระบบบริหาร OEE
ACC_MT = "#eb6834"    # ส้ม — ระบบบริหารใบงานซ่อม
ACC_EN = "#2563eb"    # น้ำเงิน — ระบบบริหารพลังงานโรงงาน
PILL_OK = "#1baf7a"
PILL_WARN = "#eda100"
PILL_CRIT = "#d03b3b"
PILL_NEUTRAL = "#64748b"
PILL_SOLAR = "#f59e0b"

APP_CSS = """
<style>
/* ---- โหมดนำเสนอ: ซ่อนเมนู Streamlit + กระชับระยะขอบบน ---- */
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 3.2rem; padding-bottom: 1.6rem; }

/* ---- แถบหัวเรื่อง (hero) ---- */
.ie-hero { position: relative; overflow: hidden; display: flex; flex-wrap: wrap; gap: 16px;
  align-items: center; justify-content: space-between; padding: 20px 26px; margin: 0 0 16px 0;
  border-radius: 20px; background: linear-gradient(115deg, #141a35 0%, #1e2a63 45%, #0f5d57 100%);
  border: 1px solid rgba(255,255,255,.10); box-shadow: 0 12px 34px rgba(16,22,52,.28); }
.ie-hero::after { content: ""; position: absolute; inset: -40% -10% auto auto; width: 420px;
  height: 420px; background: radial-gradient(circle, rgba(96,165,250,.28), transparent 62%);
  pointer-events: none; }
.ie-hero-main { position: relative; z-index: 1; min-width: 260px; }
.ie-eyebrow { font-size: .72rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
  color: rgba(186,214,255,.85); margin-bottom: 4px; }
.ie-title { font-size: 1.9rem; font-weight: 800; line-height: 1.15; margin: 0;
  background: linear-gradient(90deg, #ffffff 0%, #cfe0ff 55%, #7ee7d0 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.ie-sub { font-size: .9rem; color: rgba(219,232,255,.82); margin-top: 4px; }
.ie-side { position: relative; z-index: 1; text-align: right; }
.ie-live { display: inline-flex; align-items: center; gap: 7px; font-size: .8rem; font-weight: 800;
  color: #7ee7d0; letter-spacing: .12em; }
.ie-dot { width: 9px; height: 9px; border-radius: 50%; background: #2fe6a7;
  box-shadow: 0 0 0 0 rgba(47,230,167,.6); animation: iepulse 1.8s infinite; }
@keyframes iepulse { 70% { box-shadow: 0 0 0 9px rgba(47,230,167,0); }
  100% { box-shadow: 0 0 0 0 rgba(47,230,167,0); } }
.ie-date { font-size: 1.05rem; font-weight: 700; color: #e8f1ff; margin-top: 4px; }

/* ---- การ์ดสรุปภาพใหญ่ (Executive Summary) ---- */
.exec-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(235px, 1fr));
  gap: 14px; margin: 2px 0 16px; }
.exec-card { border-radius: 16px; padding: 14px 18px 16px;
  background: var(--secondary-background-color, #f6f8fc);
  border: 1px solid color-mix(in srgb, var(--text-color, #31333f) 12%, transparent);
  border-top: 4px solid var(--acc); }
.exec-label { font-size: .8rem; font-weight: 700;
  color: color-mix(in srgb, var(--text-color, #31333f) 65%, transparent); }
.exec-value { font-size: 2.15rem; font-weight: 800; line-height: 1.15; color: var(--acc);
  margin: 2px 0 0; }
.exec-sub { font-size: .8rem; margin-top: 2px;
  color: color-mix(in srgb, var(--text-color, #31333f) 62%, transparent); }
.exec-pill { display: inline-block; margin-top: 9px; font-size: .74rem; font-weight: 700;
  color: #fff; background: var(--pc, #64748b); padding: 3px 11px; border-radius: 999px; }

/* ---- หัวข้อรายระบบ (แถบสีนำสายตา) ---- */
.sec-head { display: flex; align-items: center; gap: 9px; font-size: 1.12rem; font-weight: 800;
  margin: 0 0 10px; }
.sec-head::before { content: ""; width: 6px; height: 22px; border-radius: 3px;
  background: var(--acc); flex: none; }

/* ---- การ์ด KPI: ตัวเลขใหญ่ อ่านง่ายบนจอประชุม/โปรเจกเตอร์ ---- */
[data-testid="stMetricValue"] { font-size: 1.62rem; font-weight: 800; }
[data-testid="stMetricLabel"] p { font-size: .8rem; }
[data-testid="stMetric"] { border-radius: 14px; }

@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
"""


def sec_head(icon: str, title: str, color: str):
    """หัวข้อรายระบบพร้อมแถบสีประจำระบบ"""
    st.markdown(f'<div class="sec-head" style="--acc:{color}">{icon} {title}</div>',
                unsafe_allow_html=True)


def exec_card(label, value, sub, pill_text, pill_color, acc) -> str:
    """การ์ดสรุปภาพใหญ่ 1 ใบ (HTML บรรทัดเดียว กัน Streamlit ตีความเป็น code block)"""
    return (
        f'<div class="exec-card" style="--acc:{acc}">'
        f'<div class="exec-label">{label}</div>'
        f'<div class="exec-value">{value}</div>'
        f'<div class="exec-sub">{sub}</div>'
        f'<div class="exec-pill" style="--pc:{pill_color}">{pill_text}</div>'
        f'</div>'
    )


# ===========================================================================
# หน้าแดชบอร์ด
# ===========================================================================
def main():
    st.set_page_config(page_title="Dashboard ภาพรวมฝ่ายวิศวกรรมกระบวนการผลิต",
                       page_icon="📊", layout="wide")
    auth.check_login("Dashboard ภาพรวมฝ่ายวิศวกรรมกระบวนการผลิต")

    with st.sidebar:
        auth.sidebar_user_box()
        st.markdown("#### 🔄 การอัปเดตอัตโนมัติ")
        st.caption(
            "ทุกส่วนรีเฟรชตัวเองอัตโนมัติ (สถานะเครื่องทุก 30 วินาที · "
            "ส่วนอื่นทุก 60 วินาที) และตรวจไฟล์ต้นทางบน OneDrive ทุกรอบ — "
            "ไฟล์ถูกแก้เมื่อไรตัวเลขจะอัปเดตเองโดยไม่ต้องกดอะไร"
        )
        if st.button("🔄 โหลดข้อมูลใหม่เดี๋ยวนี้", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        # เกณฑ์เดียวกับ slider ในแอป Workcenter เต็ม — ตั้งเลขเท่ากันแล้วตัวเลขจะตรงกัน
        idle_min = st.slider("เกณฑ์ถือว่า 'ว่าง' (นาทีที่ไม่มีการสแกน)",
                             5, 60, WC_IDLE_MIN, step=5)
        st.markdown("---")
        st.markdown("#### 🔗 เปิดระบบฉบับเต็ม")
        # สร้างลิงก์จาก host ที่ผู้ใช้เปิดหน้านี้อยู่จริง — เปิดผ่าน IP เครื่องนี้
        # (เช่นเพื่อนร่วมงานใน Wi-Fi เดียวกัน) ลิงก์จะชี้ IP เดียวกัน ไม่ใช่ localhost
        try:
            _host = (st.context.headers.get("host")
                     or st.context.headers.get("Host") or "localhost:8507")
        except Exception:
            _host = "localhost:8507"
        _hostname = _host.rsplit(":", 1)[0]
        st.markdown(
            f"- [⚙️ ระบบบริหาร OEE](http://{_hostname}:8506)\n"
            f"- [🟢 ศูนย์ปฏิบัติการเครื่องจักร](http://{_hostname}:8503)\n"
            f"- [🛠️ ระบบบริหารใบงานซ่อม](http://{_hostname}:8505)\n"
            f"- [⚡ ระบบบริหารพลังงานโรงงาน](http://{_hostname}:8504)"
        )
        st.caption(
            "หมายเหตุ: ระบบย่อยจะเปิดได้ก็ต่อเมื่อแอปนั้นรันอยู่บนเครื่องแม่ "
            "(ดับเบิลคลิก run_*.bat ค้างไว้) และเปิด firewall พอร์ตนั้นแล้ว"
        )

    st.markdown(APP_CSS, unsafe_allow_html=True)
    now = pd.Timestamp.now()
    st.markdown(
        '<div class="ie-hero">'
        '<div class="ie-hero-main">'
        '<div class="ie-eyebrow">ฝ่ายวิศวกรรมกระบวนการผลิต (IE)</div>'
        '<div class="ie-title">Dashboard ภาพรวมโรงงาน</div>'
        '<div class="ie-sub">สรุปภาพใหญ่ 4 ระบบสำหรับผู้บริหาร · อัปเดตอัตโนมัติแบบ Real-Time</div>'
        '</div>'
        '<div class="ie-side">'
        '<span class="ie-live"><span class="ie-dot"></span>LIVE</span>'
        f'<div class="ie-date">{now:%d/%m/%Y}</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ---- แถบสรุปภาพใหญ่ — ผู้บริหารเห็นสถานะทั้งโรงงานได้ในแถวเดียว ----
    @st.fragment(run_every="60s")
    def exec_summary():
        def fmt0(v):
            return "—" if v is None or pd.isna(v) else f"{v:,.0f}"

        cards = []
        # ลำดับการนำเสนอ: ① OEE (ผลลัพธ์หลัก) ② เครื่องจักรสด ③ ค่าซ่อม ④ ค่าไฟ
        # 1) OEE
        try:
            df = load_oee(oee_signature())
            yr = int(df["ปี"].max())
            m = agg_metrics(df[(df["ปี"] == yr) & ~df["ผิดปกติ"]])
            gap = m["OEE"] - OEE_TARGETS["OEE"]
            if pd.isna(gap):
                pill, pc = ("ยังคำนวณไม่ได้", PILL_NEUTRAL)
            elif gap >= 0:
                pill, pc = (f"ถึงเป้า {OEE_TARGETS['OEE']:g}%", PILL_OK)
            else:
                pill, pc = (f"ต่ำกว่าเป้า {-gap:.0f} จุด",
                            PILL_CRIT if gap < -15 else PILL_WARN)
            cards.append(exec_card(
                f"① OEE ปี {yr}", fmt_pct(m["OEE"]),
                f"A {fmt0(m['A'])}% · P {fmt0(m['P'])}% · Q {fmt0(m['Q'])}%",
                pill, pc, ACC_OEE))
        except Exception:
            cards.append(exec_card("① OEE", "—", "อ่านข้อมูลไม่ได้",
                                   "รอไฟล์ต้นทาง", PILL_NEUTRAL, ACC_OEE))
        # 2) เครื่องจักร
        try:
            day, machines, latest = load_workcenter(wc_signature())
            last_scan = day["End"].max()
            ref_now = pd.Timestamp.now()
            live = (latest == date.today()
                    and (ref_now - last_scan).total_seconds() < 45 * 60)
            ref = ref_now if live else last_scan
            stat = machine_status(day, machines, ref, idle_min)
            c = stat["สถานะ"].value_counts()
            run_n = int(c.get(STATUS_RUN, 0))
            idle_n = int(c.get(STATUS_IDLE, 0))
            down_n = int(c.get(STATUS_DOWN, 0))
            nodata_n = int(c.get(STATUS_NODATA, 0))
            active = len(machines) - nodata_n
            pill, pc = ((f"หยุดเครื่อง {down_n} เครื่อง", PILL_CRIT) if down_n
                        else ("ไม่มีเครื่องหยุด", PILL_OK))
            cards.append(exec_card(
                "② เครื่องจักรกำลังทำงาน", f"{run_n} / {active}",
                f"ว่าง {idle_n} เครื่อง · ข้อมูลวันที่ {latest:%d/%m}", pill, pc, ACC_WC))
        except Exception:
            cards.append(exec_card("② เครื่องจักรกำลังทำงาน", "—", "อ่านข้อมูลไม่ได้",
                                   "รอไฟล์ต้นทาง", PILL_NEUTRAL, ACC_WC))
        # 3) ใบงานซ่อม
        try:
            data, _ = load_maintenance(mt_signature())
            yr = int(data["ปี"].max())
            d = data[data["ปี"] == yr]
            n_pm = int((d["สถานะ"] == "PM").sum())
            n_bm = int((d["สถานะ"] == "BM").sum())
            cards.append(exec_card(
                f"③ ค่าซ่อมสะสมปี {yr}", f"{d['ค่าใช้จ่าย'].sum() / 1e6:,.2f} ล้าน฿",
                f"{len(d):,} งาน · {d['นาที'].sum() / 60:,.0f} ชม.",
                f"PM {n_pm:,} · BM {n_bm:,}", PILL_NEUTRAL, ACC_MT))
        except Exception:
            cards.append(exec_card("③ ค่าซ่อมสะสม", "—", "อ่านข้อมูลไม่ได้",
                                   "รอไฟล์ต้นทาง", PILL_NEUTRAL, ACC_MT))
        # 4) พลังงาน
        try:
            year_be = energy_year()
            bpath = bill_path(year_be)
            bills = load_bill(bpath, year_be, _mtime(bpath))
            grid_kwh = bills["kwh"].sum()
            total_cost = bills["total_cost"].sum()
            avg_rate = total_cost / grid_kwh if grid_kwh > 0 else float("nan")
            solar_kwh = 0.0
            spath = submeter_path(year_be)
            if spath:
                sub = load_submeters(spath, year_be, _mtime(spath))
                solar_kwh = sub[(sub["ประเภท"] == "Solar")
                                & sub["month"].isin(set(bills["month"]))]["kwh"].sum()
            share = solar_kwh / grid_kwh * 100 if grid_kwh > 0 else 0
            cards.append(exec_card(
                f"④ ค่าไฟสะสมปี {year_be}", f"{total_cost / 1e6:,.2f} ล้าน฿",
                f"{grid_kwh / 1e6:,.2f} ล้าน kWh · เฉลี่ย {avg_rate:,.2f} ฿/kWh",
                f"Solar {share:,.0f}% ของไฟ MEA", PILL_SOLAR, ACC_EN))
        except Exception:
            cards.append(exec_card("④ ค่าไฟสะสม", "—", "อ่านข้อมูลไม่ได้",
                                   "รอไฟล์ต้นทาง", PILL_NEUTRAL, ACC_EN))

        st.markdown('<div class="exec-grid">' + "".join(cards) + "</div>",
                    unsafe_allow_html=True)

    exec_summary()

    # ---------------------------------------------------------------- 1
    @st.fragment(run_every="30s")
    def workcenter_section():
        sec_head("🟢", "② ศูนย์ปฏิบัติการเครื่องจักร — สถานะสด", ACC_WC)
        try:
            day, machines, latest = load_workcenter(wc_signature())
        except Exception as e:
            st.warning(f"อ่านฐานข้อมูล Workcenter ไม่ได้ — {e}")
            return
        if day.empty:
            st.info("ยังไม่มีธุรกรรมของวันล่าสุด")
            return
        # กฎเดียวกับแอปเต็ม: เป็น LIVE (เทียบเวลาปัจจุบัน) เมื่อดูวันล่าสุด
        # และข้อมูลใหม่กว่า 45 นาที — ไม่งั้นเทียบ ณ เวลาสแกนสุดท้ายแทน
        last_scan = day["End"].max()
        now = pd.Timestamp.now()
        is_live = (latest == date.today()
                   and (now - last_scan).total_seconds() < 45 * 60)
        ref = now if is_live else last_scan
        stat = machine_status(day, machines, ref, idle_min)
        counts = stat["สถานะ"].value_counts()
        work = day[~day["IsDowntime"]]

        with st.container(horizontal=True):
            st.metric("🟢 กำลังทำงาน", int(counts.get(STATUS_RUN, 0)),
                      f"ว่าง {int(counts.get(STATUS_IDLE, 0))}",
                      delta_arrow="off", delta_color="off", border=True)
            st.metric("🔴 หยุดเครื่อง", int(counts.get(STATUS_DOWN, 0)),
                      f"ไม่มีข้อมูล {int(counts.get(STATUS_NODATA, 0))}",
                      delta_arrow="off", delta_color="off", border=True)
            st.metric("ชิ้นงานวันนี้", f"{work['Qty'].sum():,.0f}",
                      f"สแกน {day['Machine'].nunique()} เครื่อง",
                      delta_arrow="off", delta_color="off", border=True)
            st.metric("Job วันนี้", f"{work['Job'].nunique():,}", border=True)

        by_grp = (stat.groupby(["Group", "สถานะ"]).size().rename("เครื่อง").reset_index())
        chart = (
            alt.Chart(by_grp)
            .mark_bar()
            .encode(
                x=alt.X("เครื่อง:Q", title="จำนวนเครื่อง"),
                y=alt.Y("Group:N", title=None, sort="-x"),
                color=alt.Color("สถานะ:N", title=None,
                                scale=alt.Scale(domain=STATUS_ORDER,
                                                range=[STATUS_COLORS[s] for s in STATUS_ORDER]),
                                legend=alt.Legend(orient="bottom", columns=2)),
                tooltip=["Group", "สถานะ", "เครื่อง"],
            )
            .properties(height=260)
        )
        st.altair_chart(chart, width="stretch")
        live_tag = "🔴 LIVE" if is_live else "ข้อมูลย้อนหลัง"
        st.caption(f"{live_tag} · วันที่ {latest:%d/%m/%Y} · สถานะ ณ {ref:%H:%M} "
                   f"· เกณฑ์ว่าง {idle_min} นาที · รีเฟรชทุก 30 วินาที")

    # ---------------------------------------------------------------- 2
    @st.fragment(run_every="60s")
    def maintenance_section():
        sec_head("🛠️", "③ ระบบบริหารใบงานซ่อม — ต้นทุนซ่อมบำรุง", ACC_MT)
        try:
            data, missing = load_maintenance(mt_signature())
        except Exception as e:
            st.warning(f"อ่านใบงานซ่อมไม่ได้ — {e}")
            return
        if data.empty:
            st.info("ไม่พบข้อมูลใบงานซ่อม")
            return
        yr = int(data["ปี"].max())
        d = data[data["ปี"] == yr]
        n_jobs = len(d)
        cost_total = d["ค่าใช้จ่าย"].sum()
        n_bm = int((d["สถานะ"] == "BM").sum())
        n_pm = int((d["สถานะ"] == "PM").sum())
        hours_total = d["นาที"].sum() / 60

        with st.container(horizontal=True):
            st.metric(f"งานซ่อมปี {yr}", f"{n_jobs:,}", border=True)
            st.metric("ค่าใช้จ่ายรวม", f"{cost_total:,.0f} ฿", border=True)
            st.metric("PM / BM", f"{n_pm:,} / {n_bm:,}", border=True)
            st.metric("ชั่วโมงซ่อมรวม", f"{hours_total:,.0f} ชม.", border=True)

        monthly = (d.groupby(["เดือนปี", "หมวด"]).size().rename("งาน").reset_index())
        monthly["เดือน"] = monthly["เดือนปี"].map(month_label)
        order = [month_label(ts) for ts in sorted(monthly["เดือนปี"].unique())]
        chart = (
            alt.Chart(monthly)
            .mark_bar()
            .encode(
                x=alt.X("เดือน:N", title=None, sort=order),
                y=alt.Y("งาน:Q", title="จำนวนงาน"),
                color=alt.Color("หมวด:N", title=None, scale=CAT_SCALE,
                                legend=alt.Legend(orient="bottom", columns=3)),
                tooltip=["เดือน", "หมวด", "งาน"],
            )
            .properties(height=260)
        )
        st.altair_chart(chart, width="stretch")
        note = f" · ⚠️ ขาด {len(missing)} ไฟล์" if missing else ""
        st.caption(f"งานซ่อม 6 หมวด ปี {yr} · รีเฟรชทุก 60 วินาที{note}")

    # ---------------------------------------------------------------- 3
    @st.fragment(run_every="60s")
    def oee_section():
        sec_head("⚙️", "① ระบบบริหาร OEE — ประสิทธิผลโดยรวม", ACC_OEE)
        try:
            df = load_oee(oee_signature())
        except Exception as e:
            st.warning(f"อ่านฐานข้อมูล OEE ไม่ได้ — {e}")
            return
        if df.empty:
            st.info("ไม่พบข้อมูล OEE")
            return
        yr = int(df["ปี"].max())
        d = df[(df["ปี"] == yr) & ~df["ผิดปกติ"]]  # ตัดแถวผิดปกติเหมือนค่าตั้งต้นแอปเต็ม
        m = agg_metrics(d)

        with st.container(horizontal=True):
            for k, label in (("OEE", "OEE"), ("A", "Availability"),
                             ("P", "Performance"), ("Q", "Quality")):
                delta = (None if pd.isna(m[k])
                         else f"{m[k] - OEE_TARGETS[k]:+.1f} เทียบเป้า {OEE_TARGETS[k]:g}%")
                st.metric(label, fmt_pct(m[k]), delta, border=True)

        rows = []
        for ts, g in d.groupby("เดือนปี"):
            mm = agg_metrics(g)
            rows.append({"เดือนปี": ts, "เดือน": month_label(ts), "OEE": mm["OEE"]})
        monthly = pd.DataFrame(rows).dropna(subset=["OEE"]).sort_values("เดือนปี")
        order = monthly["เดือน"].tolist()
        line = (
            alt.Chart(monthly)
            .mark_line(point=True, color=METRIC_COLORS["OEE"], strokeWidth=3)
            .encode(
                x=alt.X("เดือน:N", title=None, sort=order),
                y=alt.Y("OEE:Q", title="OEE (%)", scale=alt.Scale(domain=[0, 100])),
                tooltip=["เดือน", alt.Tooltip("OEE:Q", format=".1f")],
            )
        )
        target = (
            alt.Chart(pd.DataFrame({"เป้า": [OEE_TARGETS["OEE"]]}))
            .mark_rule(color="#d03b3b", strokeDash=[6, 4])
            .encode(y="เป้า:Q")
        )
        st.altair_chart((line + target).properties(height=300), width="stretch")
        st.caption(f"ปี {yr} · {m['เครื่อง']} เครื่อง · {m['วัน']:,} แถวข้อมูล "
                   f"(ตัดแถวผิดปกติแล้ว) · เส้นประ = เป้า OEE {OEE_TARGETS['OEE']:g}% "
                   f"· รีเฟรชทุก 60 วินาที")

    # ---------------------------------------------------------------- 4
    @st.fragment(run_every="60s")
    def energy_section():
        sec_head("⚡", "④ ระบบบริหารพลังงานโรงงาน — ต้นทุนพลังงาน", ACC_EN)
        year_be = energy_year()
        if not year_be:
            st.warning("ไม่พบโฟลเดอร์บิลค่าไฟ Bill_33-5")
            return
        bpath = bill_path(year_be)
        try:
            bills = load_bill(bpath, year_be, _mtime(bpath))
        except Exception as e:
            st.warning(f"อ่านบิลค่าไฟไม่ได้ — {e}")
            return
        if bills.empty:
            st.info("ยังไม่มีข้อมูลบิลของปีนี้")
            return

        solar_kwh = 0.0
        spath = submeter_path(year_be)
        if spath:
            try:
                sub = load_submeters(spath, year_be, _mtime(spath))
                bill_months = set(bills["month"])
                solar_kwh = sub[(sub["ประเภท"] == "Solar")
                                & sub["month"].isin(bill_months)]["kwh"].sum()
            except Exception:
                pass  # ไม่มี Solar ก็แสดงส่วนอื่นได้

        grid_kwh = bills["kwh"].sum()
        total_cost = bills["total_cost"].sum()
        avg_rate = total_cost / grid_kwh if grid_kwh > 0 else float("nan")
        peak_row = bills.loc[bills["demand_on"].idxmax()]
        solar_share = solar_kwh / grid_kwh * 100 if grid_kwh > 0 else 0

        with st.container(horizontal=True):
            st.metric("ไฟ MEA สะสม", f"{grid_kwh:,.0f} kWh", border=True)
            st.metric("ค่าไฟสะสม", f"{total_cost:,.0f} ฿",
                      f"เฉลี่ย {avg_rate:,.2f} ฿/kWh", delta_arrow="off",
                      delta_color="off", border=True)
            st.metric("Peak Demand", f"{peak_row['demand_on']:,.0f} kW",
                      f"เดือน {peak_row['เดือน']}", delta_arrow="off",
                      delta_color="off", border=True)
            st.metric("Solar สะสม", f"{solar_kwh:,.0f} kWh",
                      f"{solar_share:.1f}% ของไฟ MEA", delta_arrow="off",
                      delta_color="off", border=True)

        order = bills.sort_values("month")["เดือน"].tolist()
        chart = (
            alt.Chart(bills)
            .mark_bar(color=COLOR_COST)
            .encode(
                x=alt.X("เดือน:N", title=None, sort=order),
                y=alt.Y("total_cost:Q", title="ค่าไฟ (บาท)", axis=alt.Axis(format="~s")),
                tooltip=["เดือน",
                         alt.Tooltip("kwh:Q", title="kWh", format=",.0f"),
                         alt.Tooltip("total_cost:Q", title="ค่าไฟ (฿)", format=",.0f"),
                         alt.Tooltip("avg_rate:Q", title="฿/kWh", format=".2f")],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, width="stretch")
        st.caption(f"บิล MEA 33/5 อัตรา TOU ปี {year_be} · "
                   f"{len(bills)} เดือนที่มีบิลแล้ว · รีเฟรชทุก 60 วินาที")

    # ---- จัดวาง 2 × 2 เรียงตามลำดับการนำเสนอ (ซ้าย→ขวา บน→ล่าง) ----
    # ① OEE ② เครื่องจักรสด ③ ค่าซ่อม ④ ค่าไฟ — ล็อกความสูงเท่ากันให้แนว grid ตรง
    CARD_H = 620
    r1c1, r1c2 = st.columns(2)
    with r1c1, st.container(border=True, height=CARD_H):
        oee_section()
    with r1c2, st.container(border=True, height=CARD_H):
        workcenter_section()
    r2c1, r2c2 = st.columns(2)
    with r2c1, st.container(border=True, height=CARD_H):
        maintenance_section()
    with r2c2, st.container(border=True, height=CARD_H):
        energy_section()

    newest = max(
        [_mtime(WC_MASTER), _mtime(OEE_PATH)]
        + [_mtime(os.path.join(MT_DIR, f)) for f in MT_FILES.values()]
    )
    if newest:
        st.caption(f"ไฟล์ต้นทางอัปเดตล่าสุด {pd.Timestamp.fromtimestamp(newest):%d/%m/%Y %H:%M}")


if __name__ == "__main__":
    main()
