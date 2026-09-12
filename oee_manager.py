# -*- coding: utf-8 -*-
"""ระบบบริหาร OEE — อ่านสดจากฐานข้อมูลหลัก OEE_ฐานข้อมูลหลัก_2569.xlsx

โครงหน้าจอ
  ① ภาพรวม        — KPI OEE/A/P/Q เทียบเป้า, แนวโน้ม, Waterfall เวลาสูญเสีย
  ② จัดอันดับ      — เครื่องไหนควรจัดการก่อน (คิดจากนาทีที่เสียโอกาสจริง)
  ③ วิเคราะห์การสูญเสีย — Pareto หมวดการสูญเสีย + เหตุการณ์จริงจากชีต B/BP/P
  ④ เจาะรายเครื่อง  — แนวโน้มรายวัน เทียบกลุ่ม เหตุการณ์หยุดเครื่อง
  ⑤ แผนงานปรับปรุง — watchlist อัตโนมัติ + ตารางงานที่บันทึกเก็บไว้ได้
  ⑥ คุณภาพข้อมูล   — แถวที่ค่าผิดปกติ (ถูกตัดออกจากการคำนวณโดยค่าเริ่มต้น)
  ⑦ ข้อมูล & ส่งออก

สูตรยึดตามชีต "วิธีคิด OEE" (Rev.001) แบบ cap ไม่เกิน 100%:
  Availability = MIN(เวลาทำงานจริง ÷ เวลาทำงาน, 1)
  Performance  = MIN(จำนวนชิ้น ÷ Cap, 1)      (เว้นว่างถ้าไม่มี Cap)
  Quality      = MIN(ชิ้นงานดี ÷ จำนวนชิ้น, 1)
  OEE          = A × P × Q
ระดับสรุป (เดือน/เครื่อง/ทั้งฝ่าย) ใช้ผลรวมเป็นตัวตั้ง-ตัวหาร ไม่ใช่ค่าเฉลี่ยของ %
"""
import datetime
import io
import os
import re
import time

import altair as alt
import pandas as pd
import streamlit as st

import auth

st.set_page_config(page_title="ระบบบริหาร OEE — Modernform", page_icon="⚙️", layout="wide")

# ด่านล็อกอิน — ใช้บัญชีชุดเดียวกับแดชบอร์ดตัวอื่นในโฟลเดอร์นี้ (ดู auth.py)
auth.check_login("ระบบบริหาร OEE — Overall Equipment Effectiveness")

# ---------------------------------------------------------------------------
# สไตล์ — แถบหัวเรื่อง (hero) + ขัดผิวแท็บ/การ์ด KPI ให้ดูเป็นระบบเดียวกัน
# ใช้ได้ทั้งธีมสว่างและมืด (แถบหัวมีพื้นเข้มของตัวเอง ตัวอักษรจึงอ่านชัดเสมอ)
# ---------------------------------------------------------------------------
APP_CSS = """
<style>
.oee-hero {
    position: relative; overflow: hidden;
    display: flex; flex-wrap: wrap; gap: 18px; align-items: center; justify-content: space-between;
    padding: 22px 26px; margin: 0 0 18px 0; border-radius: 20px;
    background: linear-gradient(115deg, #141a35 0%, #1e2a63 45%, #0f5d57 100%);
    border: 1px solid rgba(255,255,255,.10);
    box-shadow: 0 12px 34px rgba(16,22,52,.28);
}
.oee-hero::after {
    content: ""; position: absolute; inset: -40% -10% auto auto; width: 460px; height: 460px;
    background: radial-gradient(circle, rgba(96,165,250,.28), transparent 62%); pointer-events: none;
}
.oee-hero-main { position: relative; z-index: 1; min-width: 280px; }
.oee-eyebrow {
    font-size: .74rem; font-weight: 700; letter-spacing: .18em; text-transform: uppercase;
    color: rgba(186,214,255,.85); margin-bottom: 6px;
}
.oee-title {
    font-size: 2.15rem; font-weight: 800; line-height: 1.15; margin: 0;
    background: linear-gradient(90deg, #ffffff 0%, #cfe0ff 55%, #7ee7d0 100%);
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.oee-sub { font-size: .93rem; color: rgba(219,232,255,.82); margin-top: 4px; }
.oee-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.oee-chip {
    font-size: .78rem; font-weight: 600; color: #e8f1ff; padding: 5px 11px; border-radius: 999px;
    background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.16); white-space: nowrap;
}
.oee-score { position: relative; z-index: 1; min-width: 210px; text-align: right; }
.oee-score-label { font-size: .78rem; font-weight: 600; color: rgba(203,222,255,.8); letter-spacing: .04em; }
.oee-score-value { font-size: 2.9rem; font-weight: 800; line-height: 1.05; margin: 2px 0 8px 0; }
.oee-score-bar {
    height: 8px; border-radius: 999px; background: rgba(255,255,255,.14); overflow: hidden;
}
.oee-score-bar > span { display: block; height: 100%; border-radius: 999px; }
.oee-score-foot { font-size: .76rem; color: rgba(203,222,255,.78); margin-top: 7px; }

/* การ์ด (st.container border=True) ในแถวเดียวกันยืดสูงเท่ากันเสมอ
   Streamlit 1.59: การ์ด = stLayoutWrapper ที่เป็นลูกตรงของ stVerticalBlock ในคอลัมน์ */
[data-testid="stHorizontalBlock"] { align-items: stretch; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] { height: 100%; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:only-child {
    height: 100%;
}

.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding: 6px 14px; font-weight: 600; }
.stTabs [data-baseweb="tab"]:hover { background: rgba(74,58,167,.08); }
.stTabs [data-baseweb="tab-highlight"] {
    height: 3px; border-radius: 3px;
    background: linear-gradient(90deg, #4a3aa7, #2a78d6 55%, #1baf7a);
}
[data-testid="stMetric"] {
    border-radius: 14px;
    transition: transform .18s ease, box-shadow .18s ease;
}
[data-testid="stMetric"]:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(20,26,53,.13); }
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# แหล่งข้อมูล
# ---------------------------------------------------------------------------
OEE_DIR = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา\3.เรื่องOverall Equipment Effectiveness"
)
OEE_PATH = os.path.join(OEE_DIR, "OEE_ฐานข้อมูลหลัก_2569.xlsx")
# ทะเบียนเครื่องจักร — ใช้เสริมชื่อรุ่น/สถานที่ในหน้าเจาะรายเครื่อง (ไม่มีก็ทำงานได้)
REGISTRY_PATH = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา\5.งานทะเบียนเครื่องจักร\ทะเบียนเครื่องจักร_DataMaster_2569.xlsx"
)
# แผนงานปรับปรุงเก็บไว้ข้างตัวแอป (ไม่ไปเขียนทับไฟล์ฐานข้อมูลหลัก)
PLAN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oee_action_plan.csv")

# เป้าหมายมาตรฐาน (ปรับได้จาก sidebar) — ค่าตั้งต้นตามชีต "วิธีคิด OEE"
DEFAULT_TARGETS = {"OEE": 85.0, "A": 90.0, "P": 95.0, "Q": 99.9}

# หมวดการสูญเสียเวลา (ชื่อคอลัมน์ในชีต Report1 → ชื่อที่แสดง → สี)
LOSS_DEFS = [
    ("Break_time_b", "เครื่องเสีย (Breakdown)", "#d03b3b"),
    ("Break_time_bp", "ช่างเข้าซ่อม (Maintenance)", "#eb6834"),
    ("Break_time_p", "หยุดตามแผน (Planned)", "#4a3aa7"),
    ("Setup", "ตั้งเครื่อง (Setup)", "#eda100"),
    ("Break_time_noemp", "ไม่มีพนักงาน", "#e87ba4"),
    ("Break_time_S", "หยุดพิเศษ (S)", "#008b8b"),
    ("Others", "อื่นๆ / ไม่ระบุสาเหตุ", "#8a8a8a"),
]
LOSS_COLS = [c for c, _, _ in LOSS_DEFS]
LOSS_NAME = {c: n for c, n, _ in LOSS_DEFS}
LOSS_ORDER = [n for _, n, _ in LOSS_DEFS]
LOSS_SCALE = alt.Scale(domain=LOSS_ORDER, range=[c for _, _, c in LOSS_DEFS])

# ชีตเหตุการณ์หยุดเครื่องในฐาน OEE → ประเภทเหตุการณ์
EVENT_SHEETS = {
    "B001": "เครื่องเสีย (Breakdown)",
    "BP001": "ช่างเข้าซ่อม (Maintenance)",
    "P0001": "หยุดตามแผน (Planned)",
}
EVENT_ORDER = list(EVENT_SHEETS.values())
EVENT_SCALE = alt.Scale(domain=EVENT_ORDER, range=["#d03b3b", "#eb6834", "#4a3aa7"])

METRIC_COLORS = {"OEE": "#4a3aa7", "A": "#2a78d6", "P": "#eb6834", "Q": "#1baf7a"}
GROUP_PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                 "#e87ba4", "#4a3aa7", "#008b8b", "#d03b3b", "#8a8a8a", "#008300"]

TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

# แกนเดือนแบบเดียวกันทุกกราฟ — ป้ายเดือนภาษาไทย + tick เดือนละ 1 อัน (กัน label ซ้ำ Jan Jan Feb Feb)
MONTH_AXIS = alt.Axis(
    labelAngle=0, tickCount="month",
    labelExpr=("['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.',"
               "'ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'][month(datum.value)]"),
)

# ชีต "หมวดหมู่เครื่อง" ครอบคลุมเฉพาะรหัส CT / DL / EG — เครื่องที่เหลือเดาจากรหัสนำหน้า
# (ชุดเดียวกับที่ใช้ในแดชบอร์ด Workcenter) เพื่อไม่ให้กองรวมกันเป็น "ไม่ระบุ"
PREFIX_CAT = {
    "CT": ("ตัด (จากรหัสเครื่อง)", "ตัด"),
    "DL": ("เจาะ (จากรหัสเครื่อง)", "เจาะ"),
    "EG": ("ปิดขอบ (จากรหัสเครื่อง)", "ปิดขอบ"),
    "CO": ("บู้ทพ่นสี", "พ่นสี"),
    "PO": ("เครื่องขัดเงา", "ขัด / ปัดเงา"),
    "MB": ("งานปัดเงา", "ขัด / ปัดเงา"),
    "MS": ("งานขัดด้วยมือ", "ขัด / ปัดเงา"),
    "MO": ("เครื่องเพลาตั้ง", "เพลาตั้ง"),
    "LA": ("เครื่องปิดผิว", "ปิดผิว"),
    "PR": ("เครื่อง Membrane", "ปิดผิว"),
    "SF": ("เครื่องห่อโค้ง", "ปิดผิว"),
    "AL": ("ประกอบอลูมิเนียม", "ประกอบ"),
    "AD": ("หน่วยงานรับ/ส่งงาน", "หน่วยงาน"),
    "SKL": ("หน่วยงานฝีมือ", "หน่วยงาน"),
    "RP": ("ซ่อมสร้าง / ซ่อมบำรุง", "หน่วยงาน"),
}


def prefix_cat(machine: str) -> tuple:
    m = re.match(r"^[A-Za-z]+", str(machine))
    return PREFIX_CAT.get(m.group(0).upper() if m else "", ("ไม่ระบุ", "ไม่ระบุ"))

PLAN_COLUMNS = ["รหัสเครื่อง", "หัวข้อ/ปัญหา", "สาเหตุหลัก", "แนวทางแก้ไข",
                "ผู้รับผิดชอบ", "กำหนดเสร็จ", "สถานะ", "หมายเหตุ", "อัปเดตเมื่อ", "โดย"]
PLAN_STATUS = ["ยังไม่เริ่ม", "กำลังดำเนินการ", "รอของ/รออะไหล่", "เสร็จแล้ว", "ยกเลิก"]


def month_label(ts) -> str:
    """2026-03-01 → 'มี.ค. 69'"""
    return f"{TH_MONTHS[ts.month - 1]} {(ts.year + 543) % 100:02d}"


# ---------------------------------------------------------------------------
# โหลดข้อมูล
# ---------------------------------------------------------------------------
def file_signature() -> tuple:
    """mtime ของไฟล์ต้นทาง — เปลี่ยนเมื่อไฟล์ถูกแก้ ทำให้ cache โหลดใหม่เอง"""
    return tuple(os.path.getmtime(p) if os.path.exists(p) else 0
                 for p in (OEE_PATH, REGISTRY_PATH))


def _read_sheet(path, sheet, **kw):
    """อ่านชีตด้วย calamine (เร็ว) ถ้าไม่ได้ลอง openpyxl · ไฟล์ถูกล็อกอยู่ลองซ้ำ 1 ครั้ง"""
    last_err = None
    for _ in range(2):
        for engine in ("calamine", None):
            try:
                return pd.read_excel(path, sheet_name=sheet, engine=engine, **kw)
            except PermissionError as e:
                last_err = e
                break  # ล็อกทั้งไฟล์ — เปลี่ยน engine ไปก็ไม่ช่วย
            except Exception as e:
                last_err = e
        time.sleep(1.5)
    raise last_err


@st.cache_data(ttl="1h", max_entries=3, show_spinner="กำลังอ่านฐานข้อมูลหลัก OEE...")
def load_oee(sig):
    """ชีต Report1 → ตารางรายวันรายเครื่อง พร้อมคำนวณ A/P/Q/OEE ใหม่ตามสูตร cap"""
    raw = _read_sheet(OEE_PATH, "Report1")
    raw.columns = [str(c).strip() for c in raw.columns]

    def col(name, default=0):
        if name in raw.columns:
            return pd.to_numeric(raw[name], errors="coerce").fillna(default)
        return pd.Series([default] * len(raw), index=raw.index, dtype="float64")

    df = pd.DataFrame(index=raw.index)
    df["Machine"] = raw["MC"].astype(str).str.strip()
    df["ชื่อเครื่อง"] = raw["Description"].astype(str).str.strip()
    df["วันที่"] = pd.to_datetime(raw["Trans_date"], errors="coerce")
    df["PlanMin"] = col("เวลาทำงาน/วัน")
    df["RunMin"] = col("เวลาทำงานจริง/วัน")
    df["LossMin"] = col("เวลาสูญเสีย/วัน")
    for c in LOSS_COLS:
        df[c] = col(c)
    df["Cap"] = col("Cap")
    df["Pieces"] = col("จำนวน(ชิ้น)/วัน")
    df["Good"] = col("ชิ้นงานดี(ชิ้น)/วัน")
    df["Rework"] = col("Rework(ชิ้น)/วัน")
    df["ระยะขึ้นรูป"] = col("ระยะขึ้นรูป (ที่ทำได้)")
    df["Cap ระยะขึ้นรูป"] = col("Cap ระยะขึ้นรูป (เมตรต่อวัน)")
    df["หมายเหตุ"] = (raw["หมายเหตุ"].astype(str).str.strip()
                      if "หมายเหตุ" in raw.columns else "")
    df["หมายเหตุ"] = df["หมายเหตุ"].replace({"nan": "", "None": ""})
    df = df[df["วันที่"].notna() & (df["Machine"] != "") & (df["Machine"] != "nan")].copy()

    # ---- ตรวจความสมเหตุสมผลของแถว (ใช้ตัดออกจากการคำนวณได้) ----
    checks = [
        ("ไม่มีเวลาทำงาน", df["PlanMin"] <= 0),
        ("เวลาทำงานจริงติดลบ", df["RunMin"] < 0),
        ("เวลาทำงานจริงเกินเวลาทำงาน", (df["PlanMin"] > 0) & (df["RunMin"] > df["PlanMin"])),
        ("เวลาสูญเสียติดลบ", df["LossMin"] < 0),
        ("หมวดการสูญเสียติดลบ", (df[LOSS_COLS] < 0).any(axis=1)),
        ("จำนวนชิ้นติดลบ", (df["Pieces"] < 0) | (df["Good"] < 0)),
        ("ชิ้นงานดีมากกว่าจำนวนที่ผลิต", (df["Good"] > df["Pieces"]) & (df["Good"] >= 0)),
    ]
    problems = pd.Series([""] * len(df), index=df.index)
    for label, cond in checks:
        problems = problems.where(~cond, problems.where(problems == "", problems + " · ") + label)
    df["ปัญหาข้อมูล"] = problems
    df["ผิดปกติ"] = df["ปัญหาข้อมูล"] != ""

    # ผลรวมเวลาสูญเสียรายหมวดของระบบต้นทางมักมากกว่าเวลาสูญเสียสุทธิ (plan - run)
    # เพราะช่วงหยุดหลายรายการถูกบันทึกซ้อนเวลากัน — ไม่ตัดทิ้ง แต่ทำเครื่องหมายไว้
    df["CompLoss"] = df[LOSS_COLS].clip(lower=0).sum(axis=1)
    df["ส่วนต่างหมวด"] = df["CompLoss"] - df["LossMin"]
    df["บันทึกซ้อน"] = df["ส่วนต่างหมวด"] > 1

    # ---- ค่าที่ cap แล้ว ใช้เป็นตัวตั้ง/ตัวหารทุกระดับ ----
    df["RunCap"] = df["RunMin"].clip(lower=0).where(df["PlanMin"] <= 0,
                                                    df[["RunMin", "PlanMin"]].min(axis=1).clip(lower=0))
    df["PieceCap"] = df[["Pieces", "Cap"]].min(axis=1).clip(lower=0).where(df["Cap"] > 0, 0.0)
    df["GoodCap"] = df[["Good", "Pieces"]].min(axis=1).clip(lower=0)

    df["A"] = (df["RunCap"] / df["PlanMin"].where(df["PlanMin"] > 0) * 100)
    df["P"] = (df["PieceCap"] / df["Cap"].where(df["Cap"] > 0) * 100)
    df["Q"] = (df["GoodCap"] / df["Pieces"].where(df["Pieces"] > 0) * 100)
    df["OEE"] = df["A"] * df["P"] * df["Q"] / 10000

    df["ปี"] = df["วันที่"].dt.year
    df["เดือนปี"] = df["วันที่"].values.astype("datetime64[M]").astype("datetime64[ns]")
    df["เดือน"] = df["เดือนปี"].map(month_label)
    return df.sort_values(["Machine", "วันที่"]).reset_index(drop=True)


@st.cache_data(ttl="1h", max_entries=3, show_spinner=False)
def load_categories(sig):
    """ชีต 'หมวดหมู่เครื่อง' (หัวตารางแถวที่ 4) → รหัสเครื่อง / หมวดหมู่ / กลุ่มหลัก"""
    try:
        raw = _read_sheet(OEE_PATH, "หมวดหมู่เครื่อง", header=3)
    except Exception:
        return pd.DataFrame(columns=["Machine", "หมวดหมู่", "กลุ่มหลัก"])
    raw.columns = [str(c).strip() for c in raw.columns]
    if "รหัสเครื่อง" not in raw.columns:
        return pd.DataFrame(columns=["Machine", "หมวดหมู่", "กลุ่มหลัก"])
    out = pd.DataFrame({
        "Machine": raw["รหัสเครื่อง"].astype(str).str.strip(),
        "หมวดหมู่": raw.get("หมวดหมู่", pd.Series(dtype=str)).astype(str).str.strip(),
        "กลุ่มหลัก": raw.get("กลุ่มหลัก", pd.Series(dtype=str)).astype(str).str.strip(),
    })
    out = out[out["Machine"].str.len() > 0]
    out = out[~out["Machine"].isin(["nan", "None"])]
    out = out.replace({"nan": "ไม่ระบุ", "None": "ไม่ระบุ", "": "ไม่ระบุ"})
    return out.drop_duplicates(subset="Machine")


@st.cache_data(ttl="1h", max_entries=3, show_spinner="กำลังอ่านเหตุการณ์หยุดเครื่อง...")
def load_events(sig):
    """ชีต B001 / BP001 / P0001 → เหตุการณ์หยุดเครื่องรายครั้ง"""
    frames = []
    for sheet, kind in EVENT_SHEETS.items():
        try:
            raw = _read_sheet(OEE_PATH, sheet)
        except Exception:
            continue
        raw.columns = [str(c).strip() for c in raw.columns]
        if "Machine" not in raw.columns:
            continue
        ev = pd.DataFrame(index=raw.index)
        ev["ประเภท"] = kind
        ev["Machine"] = raw["Machine"].astype(str).str.strip()
        ev["พนักงาน"] = raw.get("ชื่อพนักงาน", pd.Series(dtype=str)).astype(str).str.strip()
        ev["เริ่ม"] = pd.to_datetime(raw.get("Start"), errors="coerce")
        ev["สิ้นสุด"] = pd.to_datetime(raw.get("End"), errors="coerce")
        ev["นาที"] = pd.to_numeric(raw.get("ระยะเวลา (นาที)"), errors="coerce").fillna(0)
        reason = raw.get("หมายเหตุ (Reason)")
        ev["สาเหตุ"] = (reason.astype(str).str.strip() if reason is not None
                        else pd.Series(["(ไม่ระบุ)"] * len(raw), index=raw.index))
        ev["สาเหตุ"] = ev["สาเหตุ"].replace({"nan": "(ไม่ระบุ)", "None": "(ไม่ระบุ)", "": "(ไม่ระบุ)"})
        frames.append(ev[ev["เริ่ม"].notna()])
    if not frames:
        return pd.DataFrame(columns=["ประเภท", "Machine", "พนักงาน", "เริ่ม", "สิ้นสุด", "นาที", "สาเหตุ"])
    out = pd.concat(frames, ignore_index=True)
    out["วันที่"] = out["เริ่ม"].dt.normalize()
    out["เดือนปี"] = out["วันที่"].values.astype("datetime64[M]").astype("datetime64[ns]")
    out["เดือน"] = out["เดือนปี"].map(month_label)
    return out.sort_values("เริ่ม").reset_index(drop=True)


@st.cache_data(ttl="1h", max_entries=3, show_spinner=False)
def load_registry(sig):
    """ทะเบียนเครื่องจักร (ชีต 'ทะเบียนหลัก' หัวตารางแถวที่ 3) → index = รหัสเครื่อง"""
    if not os.path.exists(REGISTRY_PATH):
        return pd.DataFrame()
    try:
        df = _read_sheet(REGISTRY_PATH, "ทะเบียนหลัก", header=2)
    except Exception:
        return pd.DataFrame()
    df.columns = [str(c).strip() for c in df.columns]
    if "รหัสเครื่อง" not in df.columns:
        return pd.DataFrame()
    df = df[df["รหัสเครื่อง"].notna()].copy()
    df["รหัสเครื่อง"] = df["รหัสเครื่อง"].astype(str).str.strip()
    return df.drop_duplicates(subset="รหัสเครื่อง").set_index("รหัสเครื่อง")


def load_plan() -> pd.DataFrame:
    """ตารางแผนงานปรับปรุงที่บันทึกไว้ (ไฟล์ CSV ข้างตัวแอป)"""
    if os.path.exists(PLAN_PATH):
        try:
            df = pd.read_csv(PLAN_PATH, encoding="utf-8-sig")
            for c in PLAN_COLUMNS:
                if c not in df.columns:
                    df[c] = ""
            return df[PLAN_COLUMNS]
        except Exception:
            pass
    return pd.DataFrame(columns=PLAN_COLUMNS)


def save_plan(df: pd.DataFrame):
    df.to_csv(PLAN_PATH, index=False, encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# สูตรสรุป
# ---------------------------------------------------------------------------
def agg_metrics(d: pd.DataFrame) -> dict:
    """สรุป A/P/Q/OEE ของกลุ่มแถว — ใช้ผลรวมเป็นตัวตั้ง/ตัวหาร (ไม่ใช่ค่าเฉลี่ยของ %)

    A · P · Q ต้องคิดจาก "ชุดแถวเดียวกัน" ไม่งั้น OEE ≠ A × P × Q
    เครื่องที่ไม่มีค่า Cap คิด Performance ไม่ได้ จึงตัดออกจากฐานคำนวณ A/P/Q/OEE
    (แต่ยังนับรวมในตัวเลขปริมาณ เช่น เวลารับภาระ/เวลาสูญเสีย/จำนวนชิ้น)
    ถ้ากลุ่มนั้นไม่มีแถวที่มี Cap เลย จะคิด A/Q จากทุกแถว ส่วน P/OEE เว้นว่าง
    """
    plan_all = float(d["PlanMin"].sum())
    run_all = float(d["RunCap"].sum())
    base = d[d["Cap"] > 0]
    has_cap = not base.empty
    if not has_cap:
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
    return {
        "PlanMin": plan_all, "RunMin": run_all, "LossMin": max(plan_all - run_all, 0.0),
        "PlanOEE": plan if has_cap else 0.0,
        "ครอบคลุม": (plan / plan_all * 100) if (has_cap and plan_all > 0) else 0.0,
        "A ทุกเครื่อง": (run_all / plan_all * 100) if plan_all > 0 else float("nan"),
        "Cap": cap, "Pieces": float(d["Pieces"].sum()), "Good": float(d["GoodCap"].sum()),
        "A": a, "P": p, "Q": q, "OEE": oee,
        "วัน": int(len(d)), "เครื่อง": int(d["Machine"].nunique()),
    }


def by_group(d: pd.DataFrame, keys) -> pd.DataFrame:
    """สรุป A/P/Q/OEE ตาม key ที่กำหนด (คืน DataFrame แบน ๆ พร้อมใช้กับ Altair)"""
    if d.empty:
        return pd.DataFrame()
    rows = []
    for k, g in d.groupby(keys, sort=False):
        m = agg_metrics(g)
        key_vals = k if isinstance(k, tuple) else (k,)
        rows.append({**dict(zip(keys if isinstance(keys, list) else [keys], key_vals)), **m})
    return pd.DataFrame(rows)


def fmt_pct(v, digits=1) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.{digits}f}%"


def fmt_hours(minutes) -> str:
    return f"{minutes / 60:,.0f} ชม."


# ---------------------------------------------------------------------------
# โหลด + ตรวจไฟล์
# ---------------------------------------------------------------------------
if not os.path.exists(OEE_PATH):
    st.error(f"ไม่พบไฟล์ฐานข้อมูลหลัก OEE:\n\n{OEE_PATH}")
    st.stop()

sig = file_signature()
try:
    df_all = load_oee(sig)
except Exception as e:
    st.error(
        "อ่านฐานข้อมูลหลัก OEE ไม่ได้ — ถ้าเปิดไฟล์ค้างอยู่ใน Excel ให้ปิดก่อนแล้วกด "
        f"'โหลดข้อมูลใหม่'\n\n{OEE_PATH}\n\n{e}"
    )
    st.stop()

cat_map = load_categories(sig)
ev_all = load_events(sig)
registry = load_registry(sig)

if not cat_map.empty:
    df_all = df_all.merge(cat_map, on="Machine", how="left")
    ev_all = ev_all.merge(cat_map, on="Machine", how="left") if not ev_all.empty else ev_all
# เครื่องที่ยังไม่มีในชีต "หมวดหมู่เครื่อง" (ชีตมีแค่รหัส CT/DL/EG) เติมจากรหัสนำหน้าแทน
# ถ้าปล่อยว่างจะกองเป็น "ไม่ระบุ" ก้อนใหญ่จนกราฟรายกลุ่มอ่านไม่ได้
for frame in (df_all, ev_all):
    for c in ("หมวดหมู่", "กลุ่มหลัก"):
        if c not in frame.columns:
            frame[c] = None
        frame[c] = frame[c].replace({"": None, "ไม่ระบุ": None})
    if frame.empty:
        continue
    miss = frame["หมวดหมู่"].isna() | frame["กลุ่มหลัก"].isna()
    if miss.any():
        guess = frame.loc[miss, "Machine"].map(prefix_cat)
        frame.loc[miss, "หมวดหมู่"] = frame.loc[miss, "หมวดหมู่"].fillna(
            pd.Series([g[0] for g in guess], index=guess.index))
        frame.loc[miss, "กลุ่มหลัก"] = frame.loc[miss, "กลุ่มหลัก"].fillna(
            pd.Series([g[1] for g in guess], index=guess.index))
    for c in ("หมวดหมู่", "กลุ่มหลัก"):
        frame[c] = frame[c].fillna("ไม่ระบุ")

# เครื่องที่ยังไม่อยู่ในชีตหมวดหมู่ — เตือนให้ไปเติมในไฟล์ต้นทาง
_in_sheet = set(cat_map["Machine"]) if not cat_map.empty else set()
UNMAPPED = sorted(set(df_all["Machine"]) - _in_sheet)

if df_all.empty:
    st.error("ชีต Report1 ไม่มีข้อมูลที่ใช้ได้")
    st.stop()

GROUPS = sorted(df_all["กลุ่มหลัก"].unique().tolist())
GROUP_SCALE = alt.Scale(domain=GROUPS,
                        range=[GROUP_PALETTE[i % len(GROUP_PALETTE)] for i in range(len(GROUPS))])
DATE_MIN = df_all["วันที่"].min().date()
DATE_MAX = df_all["วันที่"].max().date()

# ---------------------------------------------------------------------------
# Sidebar — ตัวกรอง + เป้าหมาย
# ---------------------------------------------------------------------------
with st.sidebar:
    auth.sidebar_user_box()
    st.header("ตัวกรอง")

    period = st.segmented_control(
        "ช่วงเวลา", ["ทั้งปี", "3 เดือนล่าสุด", "เดือนล่าสุด", "กำหนดเอง"], default="ทั้งปี")
    if period == "กำหนดเอง":
        picked = st.date_input("เลือกช่วงวันที่", value=(DATE_MIN, DATE_MAX),
                               min_value=DATE_MIN, max_value=DATE_MAX, format="DD/MM/YYYY")
        if isinstance(picked, (list, tuple)) and len(picked) == 2:
            d1, d2 = picked
        else:
            d1 = d2 = picked if not isinstance(picked, (list, tuple)) else picked[0]
    elif period == "เดือนล่าสุด":
        d2 = DATE_MAX
        d1 = DATE_MAX.replace(day=1)
    elif period == "3 เดือนล่าสุด":
        d2 = DATE_MAX
        d1 = (pd.Timestamp(DATE_MAX).replace(day=1) - pd.DateOffset(months=2)).date()
    else:
        d1, d2 = DATE_MIN, DATE_MAX

    grp_sel = st.multiselect("กลุ่มหลัก", GROUPS, default=GROUPS)
    cats_avail = sorted(df_all.loc[df_all["กลุ่มหลัก"].isin(grp_sel), "หมวดหมู่"].unique().tolist())
    cat_sel = st.multiselect("หมวดหมู่เครื่อง", cats_avail, default=cats_avail)
    mc_avail = sorted(df_all.loc[df_all["กลุ่มหลัก"].isin(grp_sel)
                                 & df_all["หมวดหมู่"].isin(cat_sel), "Machine"].unique().tolist())
    mc_sel = st.multiselect("เจาะจงเครื่อง (ว่าง = ทุกเครื่อง)", mc_avail, default=[])

    st.divider()
    drop_bad = st.toggle("ตัดแถวข้อมูลผิดปกติออกจากการคำนวณ", value=True,
                         help="เช่น เวลาสูญเสียติดลบ เวลาทำงานจริงเกินเวลาทำงาน ชิ้นงานดีเกินยอดผลิต "
                              "— ดูรายการได้ในแท็บ 'คุณภาพข้อมูล'")
    only_cap = st.toggle("เฉพาะเครื่องที่มีค่ากำลังผลิต (Cap)", value=False,
                         help="เครื่องที่ไม่มี Cap (งานมือ/หน่วยงาน) คิด Performance และ OEE ไม่ได้")

    with st.expander("🎯 เป้าหมาย", expanded=False):
        t_oee = st.number_input("เป้า OEE (%)", 0.0, 100.0, DEFAULT_TARGETS["OEE"], 0.5)
        t_a = st.number_input("เป้า Availability (%)", 0.0, 100.0, DEFAULT_TARGETS["A"], 0.5)
        t_p = st.number_input("เป้า Performance (%)", 0.0, 100.0, DEFAULT_TARGETS["P"], 0.5)
        t_q = st.number_input("เป้า Quality (%)", 0.0, 100.0, DEFAULT_TARGETS["Q"], 0.1)
    TARGETS = {"OEE": t_oee, "A": t_a, "P": t_p, "Q": t_q}

    st.divider()
    if st.button("โหลดข้อมูลใหม่", icon=":material/refresh:", width="stretch"):
        load_oee.clear()
        load_categories.clear()
        load_events.clear()
        load_registry.clear()
        st.rerun()
    st.caption("ไฟล์อัปเดตล่าสุด: "
               + datetime.datetime.fromtimestamp(os.path.getmtime(OEE_PATH)).strftime("%d/%m/%Y %H:%M"))
    st.caption(f"ข้อมูล {DATE_MIN:%d/%m/%Y} – {DATE_MAX:%d/%m/%Y}")
    if UNMAPPED:
        with st.expander(f"⚠️ ยังไม่อยู่ในชีตหมวดหมู่ {len(UNMAPPED)} เครื่อง"):
            st.caption("ระบบเดาหมวดหมู่จากรหัสนำหน้าให้ชั่วคราว — เติมในชีต "
                       "**หมวดหมู่เครื่อง** ของไฟล์ฐานข้อมูลหลักเพื่อให้จัดกลุ่มได้ตรงจริง")
            st.write(", ".join(UNMAPPED))

# ---------------------------------------------------------------------------
# กรองข้อมูลตาม sidebar
# ---------------------------------------------------------------------------
mask = (df_all["วันที่"].dt.date >= d1) & (df_all["วันที่"].dt.date <= d2)
mask &= df_all["กลุ่มหลัก"].isin(grp_sel) & df_all["หมวดหมู่"].isin(cat_sel)
if mc_sel:
    mask &= df_all["Machine"].isin(mc_sel)
df_raw = df_all[mask].copy()          # ยังรวมแถวผิดปกติ (ใช้ในแท็บคุณภาพข้อมูล)
df = df_raw[~df_raw["ผิดปกติ"]].copy() if drop_bad else df_raw.copy()
if only_cap:
    df = df[df["Cap"] > 0]

ev = ev_all.copy()
if not ev.empty:
    ev = ev[(ev["วันที่"].dt.date >= d1) & (ev["วันที่"].dt.date <= d2)].copy()
    ev = ev[ev["กลุ่มหลัก"].isin(grp_sel) & ev["หมวดหมู่"].isin(cat_sel)]
    if mc_sel:
        ev = ev[ev["Machine"].isin(mc_sel)]

if df.empty:
    st.title("⚙️ ระบบบริหาร OEE")
    st.warning("ไม่มีข้อมูลตามตัวกรองที่เลือก — ลองขยายช่วงเวลาหรือเลือกกลุ่มเพิ่ม")
    st.stop()

K = agg_metrics(df)

# ---------------------------------------------------------------------------
# แถบหัวเรื่อง (hero) — ชื่อระบบ + ขอบเขตข้อมูล + คะแนน OEE ของช่วงที่กรอง
# HTML ต้องต่อเป็นบรรทัดเดียว ไม่มีช่องว่างนำหน้า ไม่งั้น Streamlit ตีความเป็น code block
# ---------------------------------------------------------------------------
_oee_val = K["OEE"] if not pd.isna(K["OEE"]) else 0.0
_ratio = _oee_val / TARGETS["OEE"] if TARGETS["OEE"] else 0
_score_color = "#34d399" if _ratio >= 1 else ("#fbbf24" if _ratio >= 0.7 else "#fb7185")
_updated = datetime.datetime.fromtimestamp(os.path.getmtime(OEE_PATH)).strftime("%d/%m/%Y %H:%M")
_chips = [
    f"📅 {d1:%d/%m/%Y} – {d2:%d/%m/%Y}",
    f"🏭 {df['Machine'].nunique():,} เครื่อง",
    f"🗂 {len(df):,} วัน-เครื่อง",
    f"🕒 ข้อมูลอัปเดต {_updated}",
]
if pd.isna(K["OEE"]):
    _chips.append("🎯 คำนวณ OEE ไม่ได้ — เครื่องในตัวกรองนี้ไม่มีค่ากำลังผลิต (Cap)")
elif K["ครอบคลุม"] < 99.5:
    _chips.append(f"🎯 OEE คิดจาก {K['ครอบคลุม']:,.0f}% ของเวลารับภาระ (เฉพาะเครื่องที่มี Cap)")
if drop_bad and df_raw["ผิดปกติ"].any():
    _chips.append(f"🧪 ตัดแถวผิดปกติ {int(df_raw['ผิดปกติ'].sum()):,} แถว")
_chip_html = "".join(f'<span class="oee-chip">{c}</span>' for c in _chips)
_gap_txt = ("ยังคำนวณไม่ได้" if pd.isna(K["OEE"])
            else "ถึงเป้าแล้ว" if _ratio >= 1
            else f"ห่างเป้า {TARGETS['OEE'] - _oee_val:,.1f} จุด")
st.markdown(
    '<div class="oee-hero"><div class="oee-hero-main">'
    '<div class="oee-eyebrow">Modernform · IE</div>'
    '<div class="oee-title">⚙️ ระบบบริหาร OEE</div>'
    '<div class="oee-sub">Overall Equipment Effectiveness — ประสิทธิผลโดยรวมของเครื่องจักร '
    '· ฐานข้อมูลหลัก OEE_ฐานข้อมูลหลัก_2569.xlsx</div>'
    f'<div class="oee-chips">{_chip_html}</div></div>'
    '<div class="oee-score"><div class="oee-score-label">OEE ช่วงที่เลือก</div>'
    f'<div class="oee-score-value" style="color:{_score_color};">{fmt_pct(K["OEE"])}</div>'
    f'<div class="oee-score-bar"><span style="width:{min(max(_ratio, 0), 1) * 100:.1f}%;'
    f'background:linear-gradient(90deg,{_score_color},#60a5fa);"></span></div>'
    f'<div class="oee-score-foot">เป้า {TARGETS["OEE"]:.0f}% · {_gap_txt}</div>'
    '</div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# แถบ KPI ด้านบน (แสดงทุกแท็บ)
# ---------------------------------------------------------------------------
with st.container(horizontal=True):
    st.metric("OEE", fmt_pct(K["OEE"]), delta=f"{K['OEE'] - TARGETS['OEE']:+.1f} จุด (เป้า {TARGETS['OEE']:.0f}%)",
              border=True,
              help="A × P × Q คิดจากผลรวมทั้งช่วงที่กรอง — นับเฉพาะเครื่องที่มีค่ากำลังผลิต (Cap) "
                   f"คิดเป็น {K['ครอบคลุม']:,.0f}% ของเวลารับภาระทั้งหมด")
    st.metric("Availability", fmt_pct(K["A"]), delta=f"{K['A'] - TARGETS['A']:+.1f} จุด", border=True,
              help="เวลาทำงานจริงรวม ÷ เวลาทำงานรวม (ชุดแถวเดียวกับ OEE) · "
                   f"ถ้านับรวมเครื่องที่ไม่มี Cap ด้วยจะได้ {fmt_pct(K['A ทุกเครื่อง'])}")
    st.metric("Performance", fmt_pct(K["P"]), delta=f"{K['P'] - TARGETS['P']:+.1f} จุด", border=True,
              help="จำนวนชิ้นที่ผลิตได้ ÷ กำลังการผลิต (Cap) — เฉพาะเครื่องที่มี Cap")
    st.metric("Quality", fmt_pct(K["Q"], 2), delta=f"{K['Q'] - TARGETS['Q']:+.2f} จุด", border=True,
              help="ชิ้นงานดี ÷ จำนวนชิ้นที่ผลิต")
    st.metric("เวลารับภาระรวม", fmt_hours(K["PlanMin"]), border=True)
    st.metric("เวลาสูญเสียรวม", fmt_hours(K["LossMin"]), border=True,
              delta=f"{K['LossMin'] / K['PlanMin'] * 100:,.0f}% ของเวลารับภาระ" if K["PlanMin"] else None,
              delta_color="inverse")
    st.metric("ชิ้นงานดี", f"{K['Good']:,.0f} ชิ้น", border=True)

tab_ov, tab_rank, tab_loss, tab_mc, tab_plan, tab_dq, tab_raw = st.tabs(
    ["📊 ภาพรวม", "🏭 จัดอันดับเครื่องจักร", "⏱ วิเคราะห์การสูญเสีย", "🔍 เจาะรายเครื่อง",
     "🎯 แผนงานปรับปรุง", "🧪 คุณภาพข้อมูล", "📋 ข้อมูล & ส่งออก"]
)

# ===========================================================================
# ① ภาพรวม
# ===========================================================================
with tab_ov:
    c1, c2 = st.columns([1, 1.4])

    with c1, st.container(border=True):
        st.subheader("เทียบเป้าหมาย")
        comp = pd.DataFrame([
            {"องค์ประกอบ": "OEE", "ค่า": K["OEE"], "เป้า": TARGETS["OEE"]},
            {"องค์ประกอบ": "Availability", "ค่า": K["A"], "เป้า": TARGETS["A"]},
            {"องค์ประกอบ": "Performance", "ค่า": K["P"], "เป้า": TARGETS["P"]},
            {"องค์ประกอบ": "Quality", "ค่า": K["Q"], "เป้า": TARGETS["Q"]},
        ]).dropna(subset=["ค่า"])
        order = ["OEE", "Availability", "Performance", "Quality"]
        base = alt.Chart(comp).encode(y=alt.Y("องค์ประกอบ:N", sort=order, title=None))
        bars = base.mark_bar(cornerRadiusEnd=4, height=34).encode(
            x=alt.X("ค่า:Q", title="%", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("องค์ประกอบ:N", legend=None,
                            scale=alt.Scale(domain=order,
                                            range=[METRIC_COLORS["OEE"], METRIC_COLORS["A"],
                                                   METRIC_COLORS["P"], METRIC_COLORS["Q"]])),
            tooltip=[alt.Tooltip("องค์ประกอบ:N"), alt.Tooltip("ค่า:Q", format=",.2f"),
                     alt.Tooltip("เป้า:Q", format=",.1f")],
        )
        txt = base.mark_text(align="left", dx=5, fontWeight="bold").encode(
            x=alt.X("ค่า:Q"), text=alt.Text("ค่า:Q", format=",.1f"))
        tick = base.mark_tick(color="#333", thickness=2, size=26).encode(x=alt.X("เป้า:Q"))
        st.altair_chart((bars + tick + txt).properties(height=300))
        st.caption("ขีดดำ = เป้าหมาย · แถบ = ผลจริงของช่วงที่กรอง")

    with c2, st.container(border=True):
        st.subheader("แนวโน้มรายเดือน")
        by_m = by_group(df, ["เดือนปี"]).sort_values("เดือนปี")
        by_m["เดือน"] = by_m["เดือนปี"].map(month_label)
        long = by_m.melt(id_vars=["เดือนปี", "เดือน"], value_vars=["OEE", "A", "P", "Q"],
                         var_name="องค์ประกอบ", value_name="ค่า").dropna(subset=["ค่า"])
        line = alt.Chart(long).mark_line(point=alt.OverlayMarkDef(size=45), strokeWidth=2.5).encode(
            x=alt.X("เดือนปี:T", title=None, axis=MONTH_AXIS),
            y=alt.Y("ค่า:Q", title="%", scale=alt.Scale(domain=[0, 105])),
            color=alt.Color("องค์ประกอบ:N",
                            scale=alt.Scale(domain=["OEE", "A", "P", "Q"],
                                            range=[METRIC_COLORS[k] for k in ("OEE", "A", "P", "Q")]),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("เดือน:N"), alt.Tooltip("องค์ประกอบ:N"),
                     alt.Tooltip("ค่า:Q", format=",.1f")],
        )
        rule = alt.Chart(pd.DataFrame({"y": [TARGETS["OEE"]]})).mark_rule(
            strokeDash=[6, 4], color="#d03b3b").encode(y="y:Q")
        st.altair_chart((line + rule).properties(height=300))
        st.caption(f"เส้นประแดง = เป้า OEE {TARGETS['OEE']:.0f}%")

    with st.container(border=True):
        st.subheader("เวลาหายไปไหน — Waterfall จากเวลารับภาระถึงเวลาที่สร้างมูลค่า")
        # ใช้ชุดแถวเดียวกับที่คิด OEE (เฉพาะเครื่องที่มี Cap) ไม่งั้นยอดจะไม่ลงตัวกับ A/P/Q
        wf_src = df[df["Cap"] > 0] if (df["Cap"] > 0).any() else df
        wf_plan = float(wf_src["PlanMin"].sum())
        wf_run = float(wf_src["RunCap"].sum())
        wf_loss = max(wf_plan - wf_run, 0.0)
        loss_sums = {LOSS_NAME[c]: float(wf_src[c].clip(lower=0).sum()) for c in LOSS_COLS}
        # ปรับยอดรายหมวดตามสัดส่วน ให้รวมแล้วเท่ากับเวลาสูญเสียสุทธิพอดี (กันบันทึกซ้อนเวลา)
        comp_total = sum(loss_sums.values())
        scale = (wf_loss / comp_total) if comp_total > 0 else 1.0
        if scale != 1.0:
            loss_sums = {k: v * scale for k, v in loss_sums.items()}
        run = wf_run
        perf_loss = run * (1 - (K["P"] / 100 if not pd.isna(K["P"]) else 1))
        qual_loss = run * (K["P"] / 100 if not pd.isna(K["P"]) else 1) * \
                    (1 - (K["Q"] / 100 if not pd.isna(K["Q"]) else 1))
        steps = [("เวลารับภาระ (Loading)", wf_plan, "รวม")]
        for name, val in sorted(loss_sums.items(), key=lambda kv: -kv[1]):
            if val > 0:
                steps.append((name, -val, "สูญเสีย"))
        steps.append(("เวลาเดินเครื่อง (Run)", run, "รวม"))
        # ไม่มีค่า Cap → คิด Performance/Quality ไม่ได้ ตัดสองขั้นท้ายทิ้ง ไม่งั้นจะดูเหมือน OEE = A
        if not pd.isna(K["OEE"]):
            steps.append(("สูญเสียจากความเร็ว (Performance)", -perf_loss, "สูญเสีย"))
            steps.append(("สูญเสียจากของเสีย (Quality)", -qual_loss, "สูญเสีย"))
            steps.append(("เวลาที่สร้างมูลค่า (Valuable)", max(run - perf_loss - qual_loss, 0.0), "รวม"))

        rows, running = [], 0.0
        for name, val, kind in steps:
            if kind == "รวม":
                start, end, running = 0.0, val, val
            else:
                start, end = running + val, running
                running = running + val
            rows.append({"ขั้นตอน": name, "เริ่ม": start / 60, "สิ้นสุด": end / 60,
                         "ชั่วโมง": abs(val) / 60, "ประเภท": kind})
        wf = pd.DataFrame(rows)
        chart = alt.Chart(wf).mark_bar(cornerRadius=3).encode(
            x=alt.X("ขั้นตอน:N", sort=[r["ขั้นตอน"] for r in rows], title=None,
                    axis=alt.Axis(labelAngle=-35, labelLimit=180)),
            y=alt.Y("เริ่ม:Q", title="ชั่วโมง"),
            y2=alt.Y2("สิ้นสุด"),
            color=alt.Color("ประเภท:N", scale=alt.Scale(domain=["รวม", "สูญเสีย"],
                                                        range=["#2a78d6", "#d03b3b"]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=[alt.Tooltip("ขั้นตอน:N"), alt.Tooltip("ชั่วโมง:Q", format=",.0f")],
        ).properties(height=330)
        st.altair_chart(chart)
        note = ""
        if scale < 0.999:
            note = (f" · ยอดรายหมวดถูกปรับตามสัดส่วน {scale * 100:,.0f}% "
                    f"เพราะระบบต้นทางบันทึกช่วงหยุดซ้อนเวลากัน (รวมดิบ {comp_total / 60:,.0f} ชม.)")
        if pd.isna(K["OEE"]):
            st.caption(f"เวลารับภาระ {fmt_hours(wf_plan)} → เดินเครื่องจริง {fmt_hours(run)} · "
                       "เครื่องกลุ่มนี้ไม่มีค่ากำลังผลิต (Cap) จึงคิดส่วนที่สูญเสียจากความเร็ว"
                       "และของเสียต่อไม่ได้" + note)
        else:
            val_pct = (run - perf_loss - qual_loss) / wf_plan * 100 if wf_plan else 0
            if K["ครอบคลุม"] < 99.5:
                note += (f" · นับเฉพาะเครื่องที่มี Cap ({K['ครอบคลุม']:,.0f}% ของเวลารับภาระ "
                         f"{fmt_hours(K['PlanMin'])})")
            st.caption(
                f"เวลารับภาระ {fmt_hours(wf_plan)} → เหลือเวลาที่สร้างมูลค่าจริง "
                f"{fmt_hours(max(run - perf_loss - qual_loss, 0))} ({val_pct:,.1f}% = OEE)" + note
            )

    c3, c4 = st.columns(2)
    with c3, st.container(border=True):
        st.subheader("OEE ตามกลุ่มหลัก")
        bg = by_group(df, ["กลุ่มหลัก"]).dropna(subset=["OEE"]).sort_values("OEE")
        if bg.empty:
            st.info("กลุ่มที่เลือกไม่มีเครื่องที่คำนวณ OEE ได้ (ไม่มีค่า Cap)")
        else:
            base = alt.Chart(bg).encode(y=alt.Y("กลุ่มหลัก:N", sort="-x", title=None))
            bars = base.mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X("OEE:Q", title="OEE (%)"),
                color=alt.Color("กลุ่มหลัก:N", scale=GROUP_SCALE, legend=None),
                tooltip=[alt.Tooltip("กลุ่มหลัก:N"), alt.Tooltip("OEE:Q", format=",.1f"),
                         alt.Tooltip("A:Q", format=",.1f", title="Availability"),
                         alt.Tooltip("P:Q", format=",.1f", title="Performance"),
                         alt.Tooltip("Q:Q", format=",.2f", title="Quality"),
                         alt.Tooltip("เครื่อง:Q")],
            )
            txt = base.mark_text(align="left", dx=4).encode(
                x="OEE:Q", text=alt.Text("OEE:Q", format=",.1f"))
            rule = alt.Chart(pd.DataFrame({"x": [TARGETS["OEE"]]})).mark_rule(
                strokeDash=[6, 4], color="#d03b3b").encode(x="x:Q")
            st.altair_chart((bars + txt + rule).properties(height=max(300, 26 * len(bg))))

    with c4, st.container(border=True):
        st.subheader("การกระจายตัวของ OEE รายวัน-เครื่อง")
        hist_src = df.dropna(subset=["OEE"])
        if hist_src.empty:
            st.info("ไม่มีแถวที่คำนวณ OEE ได้")
        else:
            ch = alt.Chart(hist_src).mark_bar(cornerRadiusEnd=2, color="#4a3aa7").encode(
                x=alt.X("OEE:Q", bin=alt.Bin(step=5), title="OEE (%)"),
                y=alt.Y("count():Q", title="จำนวนวัน-เครื่อง"),
                tooltip=[alt.Tooltip("count():Q", title="จำนวน")],
            ).properties(height=max(300, 26 * len(bg)))  # สูงเท่ากราฟกลุ่มหลักฝั่งซ้าย
            rule = alt.Chart(pd.DataFrame({"x": [TARGETS["OEE"]]})).mark_rule(
                strokeDash=[6, 4], color="#d03b3b").encode(x="x:Q")
            st.altair_chart(ch + rule)
            share = (hist_src["OEE"] >= TARGETS["OEE"]).mean() * 100
            st.caption(
                f"นับเฉพาะวัน-เครื่องที่คำนวณ OEE ได้ {len(hist_src):,} จาก {len(df):,} แถว "
                f"(ต้องมีทั้งค่า Cap และมีการผลิต) · ถึงเป้า {TARGETS['OEE']:.0f}% = {share:,.1f}%")

# ===========================================================================
# ② จัดอันดับเครื่องจักร
# ===========================================================================
with tab_rank:
    rank = by_group(df, ["Machine"])
    if rank.empty:
        st.info("ไม่มีข้อมูลตามตัวกรอง")
    else:
        name_map = df.drop_duplicates("Machine").set_index("Machine")["ชื่อเครื่อง"]
        meta = df.drop_duplicates("Machine").set_index("Machine")
        rank["ชื่อเครื่อง"] = rank["Machine"].map(name_map)
        rank["หมวดหมู่"] = rank["Machine"].map(meta["หมวดหมู่"])
        rank["กลุ่มหลัก"] = rank["Machine"].map(meta["กลุ่มหลัก"])
        # นาทีที่เสียโอกาสจริง = เวลารับภาระ × ระยะห่างจากเป้า (เฉพาะที่ยังไม่ถึงเป้า)
        # ใช้ PlanOEE (เวลารับภาระของวันที่มีค่า Cap) ให้ตรงกับฐานที่คิด OEE
        rank["ห่างเป้า"] = (TARGETS["OEE"] - rank["OEE"]).clip(lower=0)
        rank["ชั่วโมงที่เสียโอกาส"] = rank["PlanOEE"] * rank["ห่างเป้า"] / 100 / 60
        rank["ชั่วโมงรับภาระ"] = rank["PlanMin"] / 60
        rank["ชั่วโมงสูญเสีย"] = rank["LossMin"] / 60

        c1, c2 = st.columns([1.3, 1])
        with c1, st.container(border=True):
            st.subheader("คอขวด — เครื่องที่ควรจัดการก่อน")
            st.caption("เรียงตาม **ชั่วโมงที่เสียโอกาส** = เวลารับภาระ × ระยะห่างจากเป้า OEE "
                       "(เครื่อง OEE ต่ำแต่รับงานน้อย ไม่ใช่คอขวดจริง)")
            scored = rank.dropna(subset=["OEE"])
            top = scored.nlargest(15, "ชั่วโมงที่เสียโอกาส")
            if scored.empty:
                st.info("เครื่องในตัวกรองนี้ยังไม่มีค่ากำลังผลิต (Cap) จึงคำนวณ OEE ไม่ได้ "
                        "— เติมค่า Cap ในไฟล์ต้นทางก่อนจึงจะจัดอันดับได้")
            elif top["ชั่วโมงที่เสียโอกาส"].fillna(0).le(0).all():
                st.success("ทุกเครื่องในตัวกรองนี้ถึงเป้า OEE แล้ว")
            else:
                base = alt.Chart(top).encode(
                    y=alt.Y("Machine:N", sort="-x", title=None))
                bars = base.mark_bar(cornerRadiusEnd=4).encode(
                    x=alt.X("ชั่วโมงที่เสียโอกาส:Q", title="ชั่วโมงที่เสียโอกาสเทียบเป้า"),
                    color=alt.Color("กลุ่มหลัก:N", scale=GROUP_SCALE,
                                    legend=alt.Legend(orient="bottom", title=None)),
                    tooltip=[alt.Tooltip("Machine:N"), alt.Tooltip("ชื่อเครื่อง:N"),
                             alt.Tooltip("OEE:Q", format=",.1f"),
                             alt.Tooltip("ชั่วโมงที่เสียโอกาส:Q", format=",.0f"),
                             alt.Tooltip("ชั่วโมงรับภาระ:Q", format=",.0f")],
                )
                txt = base.mark_text(align="left", dx=4).encode(
                    x="ชั่วโมงที่เสียโอกาส:Q", text=alt.Text("ชั่วโมงที่เสียโอกาส:Q", format=",.0f"))
                st.altair_chart((bars + txt).properties(height=max(300, 26 * len(top))))

        with c2, st.container(border=True):
            st.subheader("Availability vs Performance")
            sc_src = rank.dropna(subset=["OEE"])
            ch = alt.Chart(sc_src).mark_circle(opacity=0.8).encode(
                x=alt.X("A:Q", title="Availability (%)", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("P:Q", title="Performance (%)", scale=alt.Scale(domain=[0, 100])),
                size=alt.Size("ชั่วโมงรับภาระ:Q", title="ชม.รับภาระ",
                              scale=alt.Scale(range=[40, 600])),
                color=alt.Color("กลุ่มหลัก:N", scale=GROUP_SCALE, legend=None),
                tooltip=[alt.Tooltip("Machine:N"), alt.Tooltip("OEE:Q", format=",.1f"),
                         alt.Tooltip("A:Q", format=",.1f"), alt.Tooltip("P:Q", format=",.1f"),
                         alt.Tooltip("ชั่วโมงรับภาระ:Q", format=",.0f")],
            ).properties(height=max(300, 26 * len(top)))  # สูงเท่ากราฟคอขวดฝั่งซ้าย
            va = alt.Chart(pd.DataFrame({"x": [TARGETS["A"]]})).mark_rule(
                strokeDash=[5, 4], color="#999").encode(x="x:Q")
            hp = alt.Chart(pd.DataFrame({"y": [TARGETS["P"]]})).mark_rule(
                strokeDash=[5, 4], color="#999").encode(y="y:Q")
            st.altair_chart(ch + va + hp)
            st.caption("มุมซ้ายล่าง = หยุดบ่อย **และ** เดินช้า · ขนาดวง = ปริมาณงานที่รับ")

        with st.container(border=True):
            st.subheader("ตารางจัดอันดับ")
            show = rank[["Machine", "ชื่อเครื่อง", "หมวดหมู่", "กลุ่มหลัก", "วัน",
                         "ชั่วโมงรับภาระ", "ชั่วโมงสูญเสีย", "A", "P", "Q", "OEE",
                         "ชั่วโมงที่เสียโอกาส", "Good"]].copy()
            show = show.rename(columns={"วัน": "จำนวนวัน", "Good": "ชิ้นงานดี"})
            show = show.sort_values("ชั่วโมงที่เสียโอกาส", ascending=False)
            st.dataframe(
                show, hide_index=True, height=430,
                column_config={
                    "ชั่วโมงรับภาระ": st.column_config.NumberColumn(format="%.0f"),
                    "ชั่วโมงสูญเสีย": st.column_config.NumberColumn(format="%.0f"),
                    "ชั่วโมงที่เสียโอกาส": st.column_config.NumberColumn(format="%.0f"),
                    "A": st.column_config.ProgressColumn("Availability", format="%.1f%%",
                                                         min_value=0, max_value=100),
                    "P": st.column_config.ProgressColumn("Performance", format="%.1f%%",
                                                         min_value=0, max_value=100),
                    "Q": st.column_config.NumberColumn("Quality", format="%.2f%%"),
                    "OEE": st.column_config.ProgressColumn("OEE", format="%.1f%%",
                                                           min_value=0, max_value=100),
                    "ชิ้นงานดี": st.column_config.NumberColumn(format="%.0f"),
                },
            )

        with st.container(border=True):
            st.subheader("Heatmap OEE — เครื่อง × เดือน")
            hm = by_group(df, ["Machine", "เดือนปี"]).dropna(subset=["OEE"])
            if hm.empty:
                st.info("ไม่มีข้อมูลพอสำหรับ heatmap")
            else:
                hm["เดือน"] = hm["เดือนปี"].map(month_label)
                order_mc = rank.dropna(subset=["OEE"]).sort_values("OEE")["Machine"].tolist()
                ch = alt.Chart(hm).mark_rect().encode(
                    x=alt.X("เดือนปี:T", title=None, axis=MONTH_AXIS),
                    y=alt.Y("Machine:N", sort=order_mc, title=None),
                    color=alt.Color("OEE:Q", title="OEE (%)",
                                    scale=alt.Scale(scheme="redyellowgreen", domain=[0, 85])),
                    tooltip=[alt.Tooltip("Machine:N"), alt.Tooltip("เดือน:N"),
                             alt.Tooltip("OEE:Q", format=",.1f"),
                             alt.Tooltip("A:Q", format=",.1f"), alt.Tooltip("P:Q", format=",.1f")],
                ).properties(height=max(300, 17 * hm["Machine"].nunique()))
                st.altair_chart(ch)
                st.caption("เขียว = ใกล้/เกินเป้า · แดง = ต่ำ · เรียงจาก OEE ต่ำสุดขึ้นบน")

# ===========================================================================
# ③ วิเคราะห์การสูญเสีย
# ===========================================================================
with tab_loss:
    loss_tot = pd.DataFrame([
        {"หมวดการสูญเสีย": LOSS_NAME[c], "นาที": float(df[c].clip(lower=0).sum())}
        for c in LOSS_COLS
    ])
    loss_tot["ชั่วโมง"] = loss_tot["นาที"] / 60
    loss_tot = loss_tot[loss_tot["นาที"] > 0].sort_values("นาที", ascending=False)
    total_loss = loss_tot["นาที"].sum()
    loss_tot["สัดส่วน"] = loss_tot["นาที"] / total_loss * 100 if total_loss else 0
    loss_tot["สะสม"] = loss_tot["สัดส่วน"].cumsum()

    c1, c2 = st.columns([1.3, 1])
    with c1, st.container(border=True):
        st.subheader("Pareto การสูญเสียเวลา")
        if loss_tot.empty:
            st.info("ไม่มีเวลาสูญเสียในช่วงที่กรอง")
        else:
            order = loss_tot["หมวดการสูญเสีย"].tolist()
            base = alt.Chart(loss_tot).encode(
                x=alt.X("หมวดการสูญเสีย:N", sort=order, title=None,
                        axis=alt.Axis(labelAngle=-30, labelLimit=160)))
            bars = base.mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("ชั่วโมง:Q", title="ชั่วโมง"),
                color=alt.Color("หมวดการสูญเสีย:N", scale=LOSS_SCALE, legend=None),
                tooltip=[alt.Tooltip("หมวดการสูญเสีย:N"), alt.Tooltip("ชั่วโมง:Q", format=",.0f"),
                         alt.Tooltip("สัดส่วน:Q", format=",.1f", title="สัดส่วน (%)")],
            )
            line = base.mark_line(color="#333", point=True, strokeWidth=2).encode(
                y=alt.Y("สะสม:Q", title="สะสม (%)", scale=alt.Scale(domain=[0, 100]),
                        axis=alt.Axis(titleColor="#333")))
            st.altair_chart(alt.layer(bars, line).resolve_scale(y="independent").properties(height=340))
            st.caption("นับทุกเครื่องในตัวกรอง (รวมเครื่องที่ไม่มี Cap ซึ่งไม่มีค่า OEE) — "
                       "จึงมากกว่ายอดใน Waterfall ของแท็บภาพรวมที่นับเฉพาะเครื่องที่มี Cap")

    with c2, st.container(border=True):
        st.subheader("สัดส่วนการสูญเสีย")
        if not loss_tot.empty:
            st.dataframe(
                loss_tot[["หมวดการสูญเสีย", "ชั่วโมง", "สัดส่วน"]],
                hide_index=True, height=250,
                column_config={
                    "ชั่วโมง": st.column_config.NumberColumn(format="%.0f"),
                    "สัดส่วน": st.column_config.ProgressColumn("สัดส่วน (%)", format="%.1f%%",
                                                              min_value=0, max_value=100),
                },
            )
            biggest = loss_tot.iloc[0]
            st.caption(f"หมวดใหญ่สุด: **{biggest['หมวดการสูญเสีย']}** "
                       f"{biggest['ชั่วโมง']:,.0f} ชม. ({biggest['สัดส่วน']:,.1f}% ของเวลาสูญเสียทั้งหมด)")
            if total_loss > K["LossMin"] * 1.001:
                st.warning(
                    f"ผลรวมรายหมวด {total_loss / 60:,.0f} ชม. มากกว่าเวลาสูญเสียสุทธิ "
                    f"{K['LossMin'] / 60:,.0f} ชม. — ระบบต้นทางบันทึกช่วงหยุดซ้อนเวลากันในบางวัน "
                    f"ตัวเลขในหน้านี้จึงใช้ **เปรียบเทียบสัดส่วนระหว่างหมวด** ได้ "
                    f"แต่อย่านำไปบวกกับเวลาเดินเครื่อง (ดูรายการในแท็บคุณภาพข้อมูล)",
                    icon=":material/info:")

    with st.container(border=True):
        st.subheader("แนวโน้มเวลาสูญเสียรายเดือน")
        mlong = df.groupby("เดือนปี")[LOSS_COLS].sum().clip(lower=0).reset_index()
        mlong = mlong.melt(id_vars="เดือนปี", var_name="cod", value_name="นาที")
        mlong["หมวดการสูญเสีย"] = mlong["cod"].map(LOSS_NAME)
        mlong["ชั่วโมง"] = mlong["นาที"] / 60
        mlong["เดือน"] = mlong["เดือนปี"].map(month_label)
        ch = alt.Chart(mlong).mark_bar().encode(
            x=alt.X("เดือนปี:T", title=None, axis=MONTH_AXIS),
            y=alt.Y("ชั่วโมง:Q", title="ชั่วโมง"),
            color=alt.Color("หมวดการสูญเสีย:N", scale=LOSS_SCALE,
                            legend=alt.Legend(orient="bottom", title=None, columns=4)),
            tooltip=[alt.Tooltip("เดือน:N"), alt.Tooltip("หมวดการสูญเสีย:N"),
                     alt.Tooltip("ชั่วโมง:Q", format=",.0f")],
        ).properties(height=300)
        st.altair_chart(ch)

    c3, c4 = st.columns(2)
    with c3, st.container(border=True):
        st.subheader("เครื่องที่สูญเสียเวลามากที่สุด")
        by_mc = df.groupby("Machine")[LOSS_COLS].sum().clip(lower=0)
        by_mc["รวม"] = by_mc.sum(axis=1)
        top_mc = by_mc.nlargest(12, "รวม").drop(columns="รวม").reset_index()
        tl = top_mc.melt(id_vars="Machine", var_name="cod", value_name="นาที")
        tl["หมวดการสูญเสีย"] = tl["cod"].map(LOSS_NAME)
        tl["ชั่วโมง"] = tl["นาที"] / 60
        ch = alt.Chart(tl).mark_bar(cornerRadiusEnd=3).encode(
            y=alt.Y("Machine:N", sort="-x", title=None),
            x=alt.X("ชั่วโมง:Q", title="ชั่วโมงสูญเสีย"),
            color=alt.Color("หมวดการสูญเสีย:N", scale=LOSS_SCALE,
                            legend=alt.Legend(orient="bottom", title=None, columns=2)),
            tooltip=[alt.Tooltip("Machine:N"), alt.Tooltip("หมวดการสูญเสีย:N"),
                     alt.Tooltip("ชั่วโมง:Q", format=",.0f")],
        ).properties(height=380)
        st.altair_chart(ch)
        st.caption("ยอดรายหมวดจากระบบต้นทาง — บางวันช่วงหยุดถูกบันทึกซ้อนกัน "
                   "ตัวเลขจึงสูงกว่าเวลาสูญเสียสุทธิของเครื่องนั้น")

    with c4, st.container(border=True):
        st.subheader("สัดส่วนการสูญเสียตามกลุ่มหลัก")
        gl = df.groupby("กลุ่มหลัก")[LOSS_COLS].sum().clip(lower=0).reset_index()
        gl = gl.melt(id_vars="กลุ่มหลัก", var_name="cod", value_name="นาที")
        gl["หมวดการสูญเสีย"] = gl["cod"].map(LOSS_NAME)
        ch = alt.Chart(gl).mark_bar().encode(
            y=alt.Y("กลุ่มหลัก:N", title=None),
            x=alt.X("นาที:Q", stack="normalize", title="สัดส่วน", axis=alt.Axis(format="%")),
            color=alt.Color("หมวดการสูญเสีย:N", scale=LOSS_SCALE,
                            legend=alt.Legend(orient="bottom", title=None, columns=2)),
            tooltip=[alt.Tooltip("กลุ่มหลัก:N"), alt.Tooltip("หมวดการสูญเสีย:N"),
                     alt.Tooltip("นาที:Q", format=",.0f")],
        ).properties(height=380)
        st.altair_chart(ch)

    st.markdown("")
    st.subheader("เหตุการณ์หยุดเครื่องรายครั้ง (ชีต B001 / BP001 / P0001)")
    if ev.empty:
        st.info("ไม่มีเหตุการณ์หยุดเครื่องในช่วงที่กรอง")
    else:
        # เหตุการณ์ที่คร่อมหลายวัน (เช่น หยุดตามแผนยาวข้ามสัปดาห์) ถูกนับทั้งก้อนที่ "วันเริ่ม"
        # ทำให้ชั่วโมงหยุดของเดือนนั้นพองผิดปกติ — เปิดสวิตช์เพื่อดูเฉพาะเหตุการณ์ที่จบในวันเดียว
        # ใช้ตัวแปรแยก (ev_view) ไม่แตะ ev เดิม ไม่งั้นแท็บเจาะรายเครื่องจะถูกกรองตามไปด้วย
        ev_view = ev.copy()
        ev_view["ข้ามวัน"] = ev_view["สิ้นสุด"].dt.normalize() > ev_view["เริ่ม"].dt.normalize()
        n_cross = int(ev_view["ข้ามวัน"].sum())
        h_cross = ev_view.loc[ev_view["ข้ามวัน"], "นาที"].sum() / 60
        if n_cross:
            same_day = st.toggle(
                f"แสดงเฉพาะเหตุการณ์ที่จบภายในวันเดียว (ตัดออก {n_cross:,} ครั้ง / {h_cross:,.0f} ชม.)",
                value=False,
                help="เหตุการณ์คร่อมหลายวันถูกบันทึกเป็นก้อนเดียวและนับที่วันเริ่ม "
                     "จึงทำให้ชั่วโมงหยุดของเดือนนั้นดูสูงเกินจริง")
            if same_day:
                ev_view = ev_view[~ev_view["ข้ามวัน"]]

        ev_sum = ev_view.groupby("ประเภท").agg(ครั้ง=("นาที", "size"), นาที=("นาที", "sum")).reset_index()
        with st.container(horizontal=True):
            for _, r in ev_sum.iterrows():
                st.metric(r["ประเภท"], f"{r['ครั้ง']:,} ครั้ง", border=True,
                          delta=f"{r['นาที'] / 60:,.0f} ชม.", delta_color="off")
            st.metric("เวลาเฉลี่ยต่อครั้ง", f"{ev_view['นาที'].mean():,.0f} นาที", border=True)
        st.caption(
            "เหตุการณ์กรองตาม **วันที่เริ่ม** · ชั่วโมงรวมนับตามที่ระบบต้นทางบันทึก "
            "จึงเทียบตรงกับหมวดการสูญเสียด้านบนไม่ได้ (คนละวิธีบันทึก)")

        c5, c6 = st.columns(2)
        with c5, st.container(border=True):
            st.subheader("เครื่องที่หยุดนานที่สุด")
            tm = (ev_view.groupby(["Machine", "ประเภท"], as_index=False)
                  .agg(นาที=("นาที", "sum"), ครั้ง=("นาที", "size")))
            tm["ชั่วโมง"] = tm["นาที"] / 60
            top10 = tm.groupby("Machine")["ชั่วโมง"].sum().nlargest(12).index
            ch = alt.Chart(tm[tm["Machine"].isin(top10)]).mark_bar(cornerRadiusEnd=3).encode(
                y=alt.Y("Machine:N", sort="-x", title=None),
                x=alt.X("ชั่วโมง:Q", title="ชั่วโมงหยุด"),
                color=alt.Color("ประเภท:N", scale=EVENT_SCALE,
                                legend=alt.Legend(orient="bottom", title=None)),
                tooltip=[alt.Tooltip("Machine:N"), alt.Tooltip("ประเภท:N"),
                         alt.Tooltip("ชั่วโมง:Q", format=",.1f"), alt.Tooltip("ครั้ง:Q")],
            ).properties(height=340)
            st.altair_chart(ch)

        with c6, st.container(border=True):
            st.subheader("สาเหตุที่บันทึกไว้ (หยุดตามแผน)")
            rs = (ev_view[ev_view["สาเหตุ"] != "(ไม่ระบุ)"]
                  .groupby("สาเหตุ", as_index=False)
                  .agg(นาที=("นาที", "sum"), ครั้ง=("นาที", "size")))
            if rs.empty:
                st.info("ไม่มีการบันทึกสาเหตุในช่วงนี้")
            else:
                rs["ชั่วโมง"] = rs["นาที"] / 60
                rs = rs.nlargest(12, "ชั่วโมง")
                base = alt.Chart(rs).encode(y=alt.Y("สาเหตุ:N", sort="-x", title=None))
                bars = base.mark_bar(cornerRadiusEnd=3, color="#4a3aa7").encode(
                    x=alt.X("ชั่วโมง:Q", title="ชั่วโมง"),
                    tooltip=[alt.Tooltip("สาเหตุ:N"), alt.Tooltip("ชั่วโมง:Q", format=",.1f"),
                             alt.Tooltip("ครั้ง:Q")])
                txt = base.mark_text(align="left", dx=4).encode(
                    x="ชั่วโมง:Q", text=alt.Text("ชั่วโมง:Q", format=",.0f"))
                st.altair_chart((bars + txt).properties(height=340))

        with st.expander("ตารางเหตุการณ์ทั้งหมด", expanded=False):
            show_ev = ev_view[["ประเภท", "Machine", "หมวดหมู่", "เริ่ม", "สิ้นสุด", "นาที",
                          "สาเหตุ", "พนักงาน"]].sort_values("นาที", ascending=False)
            st.dataframe(show_ev, hide_index=True, height=420,
                         column_config={"นาที": st.column_config.NumberColumn(format="%.0f")})

# ===========================================================================
# ④ เจาะรายเครื่อง
# ===========================================================================
with tab_mc:
    machines = sorted(df["Machine"].unique().tolist())
    sel_mc = st.selectbox("เลือกเครื่อง", machines,
                          index=0 if machines else None, key="mc_drill")
    d_mc = df[df["Machine"] == sel_mc]
    if d_mc.empty:
        st.info("ไม่มีข้อมูลของเครื่องนี้ในช่วงที่กรอง")
    else:
        m = agg_metrics(d_mc)
        info = d_mc.iloc[0]
        grp_df = df[df["หมวดหมู่"] == info["หมวดหมู่"]]
        gm = agg_metrics(grp_df)

        st.markdown(f"**{sel_mc}** — {info['ชื่อเครื่อง']}  ·  หมวดหมู่ {info['หมวดหมู่']} "
                    f"(กลุ่ม {info['กลุ่มหลัก']})")
        with st.container(horizontal=True):
            st.metric("OEE", fmt_pct(m["OEE"]), border=True,
                      delta=f"{m['OEE'] - gm['OEE']:+.1f} จุด เทียบหมวดหมู่"
                      if not pd.isna(m["OEE"]) and not pd.isna(gm["OEE"]) else None)
            st.metric("Availability", fmt_pct(m["A"]), border=True,
                      delta=f"{m['A'] - TARGETS['A']:+.1f} จุด เทียบเป้า")
            st.metric("Performance", fmt_pct(m["P"]), border=True,
                      delta=f"{m['P'] - TARGETS['P']:+.1f} จุด เทียบเป้า"
                      if not pd.isna(m["P"]) else None)
            st.metric("Quality", fmt_pct(m["Q"], 2), border=True)
            st.metric("วันที่มีข้อมูล", f"{m['วัน']:,} วัน", border=True)
            st.metric("เวลาสูญเสีย", fmt_hours(m["LossMin"]), border=True)
            st.metric("ชิ้นงานดี", f"{m['Good']:,.0f} ชิ้น", border=True)

        if not registry.empty and sel_mc in registry.index:
            reg = registry.loc[sel_mc]
            bits = []
            for c in ("ชื่อเครื่องจักร", "ยี่ห้อ/รุ่น", "สถานที่ติดตั้ง", "วันที่ติดตั้ง",
                      "อายุ (ปี)", "รอบ PM", "สถานะ"):
                if c in reg.index and pd.notna(reg[c]):
                    val = reg[c]
                    if isinstance(val, pd.Timestamp):
                        val = val.strftime("%d/%m/%Y")
                    bits.append(f"{c}: **{val}**")
            if bits:
                st.caption("ทะเบียนเครื่องจักร · " + " · ".join(bits))

        c1, c2 = st.columns([1.5, 1])
        with c1, st.container(border=True):
            st.subheader("OEE รายวัน")
            dd = d_mc[["วันที่", "OEE", "A", "P", "Q"]].copy().sort_values("วันที่")
            dd["เฉลี่ย 7 วัน"] = dd["OEE"].rolling(7, min_periods=3).mean()
            pts = alt.Chart(dd).mark_circle(size=45, opacity=0.6, color="#4a3aa7").encode(
                x=alt.X("วันที่:T", title=None),
                y=alt.Y("OEE:Q", title="OEE (%)", scale=alt.Scale(domain=[0, 105])),
                tooltip=[alt.Tooltip("วันที่:T", format="%d/%m/%Y"),
                         alt.Tooltip("OEE:Q", format=",.1f"), alt.Tooltip("A:Q", format=",.1f"),
                         alt.Tooltip("P:Q", format=",.1f"), alt.Tooltip("Q:Q", format=",.1f")],
            )
            roll = alt.Chart(dd).mark_line(color="#d03b3b", strokeWidth=2.5).encode(
                x="วันที่:T", y="เฉลี่ย 7 วัน:Q")
            rule = alt.Chart(pd.DataFrame({"y": [TARGETS["OEE"]]})).mark_rule(
                strokeDash=[6, 4], color="#1baf7a").encode(y="y:Q")
            st.altair_chart((pts + roll + rule).properties(height=320))
            st.caption("จุดม่วง = รายวัน · เส้นแดง = เฉลี่ยเคลื่อนที่ 7 วัน · เส้นเขียว = เป้า")

        with c2, st.container(border=True):
            st.subheader("เวลาสูญเสียของเครื่องนี้")
            ml = pd.DataFrame([
                {"หมวดการสูญเสีย": LOSS_NAME[c], "ชั่วโมง": float(d_mc[c].clip(lower=0).sum()) / 60}
                for c in LOSS_COLS
            ])
            ml = ml[ml["ชั่วโมง"] > 0].sort_values("ชั่วโมง", ascending=False)
            if ml.empty:
                st.info("ไม่มีเวลาสูญเสียบันทึกไว้")
            else:
                base = alt.Chart(ml).encode(y=alt.Y("หมวดการสูญเสีย:N", sort="-x", title=None))
                bars = base.mark_bar(cornerRadiusEnd=3).encode(
                    x=alt.X("ชั่วโมง:Q", title="ชั่วโมง"),
                    color=alt.Color("หมวดการสูญเสีย:N", scale=LOSS_SCALE, legend=None),
                    tooltip=[alt.Tooltip("หมวดการสูญเสีย:N"), alt.Tooltip("ชั่วโมง:Q", format=",.1f")])
                txt = base.mark_text(align="left", dx=4).encode(
                    x="ชั่วโมง:Q", text=alt.Text("ชั่วโมง:Q", format=",.0f"))
                st.altair_chart((bars + txt).properties(height=320))

        c3, c4 = st.columns(2)
        with c3, st.container(border=True):
            st.subheader("สรุปรายเดือน")
            mm = by_group(d_mc, ["เดือนปี"]).sort_values("เดือนปี")
            mm["เดือน"] = mm["เดือนปี"].map(month_label)
            mm["ชั่วโมงรับภาระ"] = mm["PlanMin"] / 60
            mm["ชั่วโมงสูญเสีย"] = mm["LossMin"] / 60
            st.dataframe(
                mm[["เดือน", "วัน", "ชั่วโมงรับภาระ", "ชั่วโมงสูญเสีย", "A", "P", "Q", "OEE"]],
                hide_index=True, height=300,
                column_config={
                    "วัน": st.column_config.NumberColumn("จำนวนวัน"),
                    "ชั่วโมงรับภาระ": st.column_config.NumberColumn(format="%.0f"),
                    "ชั่วโมงสูญเสีย": st.column_config.NumberColumn(format="%.0f"),
                    "A": st.column_config.NumberColumn("Availability", format="%.1f%%"),
                    "P": st.column_config.NumberColumn("Performance", format="%.1f%%"),
                    "Q": st.column_config.NumberColumn("Quality", format="%.2f%%"),
                    "OEE": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
                })

        with c4, st.container(border=True):
            st.subheader("เหตุการณ์หยุดเครื่องของเครื่องนี้")
            ev_mc = ev[ev["Machine"] == sel_mc] if not ev.empty else ev
            if ev_mc.empty:
                st.info("ไม่มีเหตุการณ์บันทึกไว้ในช่วงนี้")
            else:
                st.dataframe(
                    ev_mc[["ประเภท", "เริ่ม", "สิ้นสุด", "นาที", "สาเหตุ"]]
                    .sort_values("เริ่ม", ascending=False),
                    hide_index=True, height=300,
                    column_config={"นาที": st.column_config.NumberColumn(format="%.0f")})

        notes = d_mc.loc[d_mc["หมายเหตุ"].str.len() > 0, ["วันที่", "หมายเหตุ"]]
        if not notes.empty:
            with st.expander(f"หมายเหตุที่บันทึกในฐานข้อมูล ({len(notes)} รายการ)"):
                st.dataframe(notes.sort_values("วันที่", ascending=False), hide_index=True,
                             column_config={"วันที่": st.column_config.DateColumn(format="DD/MM/YYYY")})

# ===========================================================================
# ⑤ แผนงานปรับปรุง
# ===========================================================================
with tab_plan:
    st.subheader("Watchlist — เครื่องที่ยังไม่ถึงเป้า OEE")
    watch = by_group(df, ["Machine"]).dropna(subset=["OEE"])
    if watch.empty:
        st.info("ไม่มีเครื่องที่คำนวณ OEE ได้ในตัวกรองนี้")
        watch = pd.DataFrame(columns=["Machine"])
    else:
        watch = watch[watch["OEE"] < TARGETS["OEE"]].copy()
        watch["ห่างเป้า"] = TARGETS["OEE"] - watch["OEE"]
        watch["ชั่วโมงที่เสียโอกาส"] = watch["PlanOEE"] * watch["ห่างเป้า"] / 100 / 60
        # หมวดการสูญเสียที่ใหญ่ที่สุดของแต่ละเครื่อง — ใช้เติมช่อง "สาเหตุหลัก" ให้อัตโนมัติ
        big = df.groupby("Machine")[LOSS_COLS].sum().clip(lower=0)
        watch["สาเหตุหลัก"] = watch["Machine"].map(big.idxmax(axis=1).map(LOSS_NAME))
        watch["จุดอ่อน"] = watch.apply(
            lambda r: min([("Availability", r["A"] - TARGETS["A"]),
                           ("Performance", r["P"] - TARGETS["P"]),
                           ("Quality", r["Q"] - TARGETS["Q"])],
                          key=lambda t: (t[1] if pd.notna(t[1]) else 999))[0], axis=1)
        watch = watch.sort_values("ชั่วโมงที่เสียโอกาส", ascending=False)

        st.dataframe(
            watch[["Machine", "OEE", "A", "P", "Q", "จุดอ่อน", "สาเหตุหลัก", "ชั่วโมงที่เสียโอกาส"]],
            hide_index=True, height=320,
            column_config={
                "OEE": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
                "A": st.column_config.NumberColumn("Availability", format="%.1f%%"),
                "P": st.column_config.NumberColumn("Performance", format="%.1f%%"),
                "Q": st.column_config.NumberColumn("Quality", format="%.2f%%"),
                "ชั่วโมงที่เสียโอกาส": st.column_config.NumberColumn(format="%.0f"),
            })
        st.caption("จุดอ่อน = องค์ประกอบที่ห่างเป้ามากที่สุด · "
                   "สาเหตุหลัก = หมวดการสูญเสียเวลาที่มากที่สุดของเครื่องนั้น")

    plan_df = load_plan()

    with st.container(border=True):
        st.markdown("**เพิ่มเครื่องจาก watchlist เข้าตารางแผนงาน**")
        pick = st.multiselect("เลือกเครื่อง", watch["Machine"].tolist() if not watch.empty else [],
                              default=[], key="plan_pick")
        cc1, cc2 = st.columns([1, 3])
        with cc1:
            owner = st.text_input("ผู้รับผิดชอบ", value=auth.current_user())
        with cc2:
            due = st.date_input("กำหนดเสร็จ",
                                value=datetime.date.today() + datetime.timedelta(days=30),
                                format="DD/MM/YYYY")
        if st.button("➕ เพิ่มเข้าตารางแผนงาน", disabled=not pick, width="stretch"):
            now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            rows = []
            for mc in pick:
                w = watch[watch["Machine"] == mc].iloc[0]
                rows.append({
                    "รหัสเครื่อง": mc,
                    "หัวข้อ/ปัญหา": f"OEE {w['OEE']:.1f}% ต่ำกว่าเป้า {TARGETS['OEE']:.0f}% "
                                    f"(จุดอ่อน {w['จุดอ่อน']})",
                    "สาเหตุหลัก": w["สาเหตุหลัก"],
                    "แนวทางแก้ไข": "",
                    "ผู้รับผิดชอบ": owner,
                    "กำหนดเสร็จ": due.strftime("%d/%m/%Y"),
                    "สถานะ": "ยังไม่เริ่ม",
                    "หมายเหตุ": f"เสียโอกาส {w['ชั่วโมงที่เสียโอกาส']:,.0f} ชม. "
                                f"({d1:%d/%m/%Y}–{d2:%d/%m/%Y})",
                    "อัปเดตเมื่อ": now,
                    "โดย": auth.current_user(),
                })
            plan_df = pd.concat([plan_df, pd.DataFrame(rows)], ignore_index=True)
            save_plan(plan_df)
            st.success(f"เพิ่ม {len(rows)} รายการแล้ว")
            st.rerun()

    st.subheader("ตารางแผนงานปรับปรุง")
    st.caption(f"บันทึกไว้ที่ `{PLAN_PATH}` — แก้ไขในตารางแล้วกดบันทึก")
    edited = st.data_editor(
        plan_df, hide_index=True, num_rows="dynamic", height=380, key="plan_editor",
        column_config={
            "สถานะ": st.column_config.SelectboxColumn(options=PLAN_STATUS, required=False),
            "หัวข้อ/ปัญหา": st.column_config.TextColumn(width="large"),
            "แนวทางแก้ไข": st.column_config.TextColumn(width="large"),
        })
    b1, b2, _ = st.columns([1, 1, 3])
    with b1:
        if st.button("💾 บันทึกแผนงาน", type="primary", width="stretch"):
            out = edited.copy()
            now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            out["อัปเดตเมื่อ"] = out["อัปเดตเมื่อ"].fillna("").replace("", now)
            out["โดย"] = out["โดย"].fillna("").replace("", auth.current_user())
            save_plan(out[PLAN_COLUMNS])
            st.success("บันทึกแล้ว")
    with b2:
        st.download_button("⬇️ ดาวน์โหลด CSV",
                           data=edited.to_csv(index=False).encode("utf-8-sig"),
                           file_name="oee_action_plan.csv", mime="text/csv", width="stretch")

    if not edited.empty and "สถานะ" in edited:
        cnt = edited["สถานะ"].value_counts()
        with st.container(horizontal=True):
            for s in PLAN_STATUS:
                st.metric(s, f"{int(cnt.get(s, 0))} งาน", border=True)

# ===========================================================================
# ⑥ คุณภาพข้อมูล
# ===========================================================================
with tab_dq:
    bad = df_raw[df_raw["ผิดปกติ"]]
    with st.container(horizontal=True):
        st.metric("แถวทั้งหมดในช่วง", f"{len(df_raw):,}", border=True)
        st.metric("แถวผิดปกติ", f"{len(bad):,}", border=True,
                  delta=f"{len(bad) / len(df_raw) * 100:,.1f}%" if len(df_raw) else None,
                  delta_color="inverse")
        st.metric("เครื่องที่ไม่มีค่า Cap",
                  f"{df_raw.loc[df_raw['Cap'] <= 0, 'Machine'].nunique():,} เครื่อง", border=True,
                  help="เครื่องกลุ่มนี้คิด Performance และ OEE ไม่ได้ (งานมือ/หน่วยงาน)")
        st.metric("แถวที่บันทึกช่วงหยุดซ้อนกัน", f"{int(df_raw['บันทึกซ้อน'].sum()):,}", border=True,
                  help="ผลรวมเวลาสูญเสียรายหมวด > เวลาสูญเสียสุทธิของวันนั้น "
                       "— ไม่กระทบ OEE (OEE คิดจากเวลาทำงานจริง) แต่ทำให้ตัวเลขรายหมวดสูงเกินจริง")
        st.metric("สถานะการคำนวณ",
                  "ตัดแถวผิดปกติออกแล้ว" if drop_bad else "รวมทุกแถว", border=True)

    if bad.empty:
        st.success("ไม่พบแถวที่ค่าผิดปกติในช่วงที่กรอง")
    else:
        c1, c2 = st.columns([1, 1.4])
        with c1, st.container(border=True):
            st.subheader("ประเภทปัญหา")
            reasons = (bad["ปัญหาข้อมูล"].str.split(" · ").explode()
                       .value_counts().rename_axis("ปัญหา").reset_index(name="แถว"))
            base = alt.Chart(reasons).encode(y=alt.Y("ปัญหา:N", sort="-x", title=None))
            bars = base.mark_bar(cornerRadiusEnd=3, color="#d03b3b").encode(
                x=alt.X("แถว:Q", title="จำนวนแถว"),
                tooltip=[alt.Tooltip("ปัญหา:N"), alt.Tooltip("แถว:Q", format=",")])
            txt = base.mark_text(align="left", dx=4).encode(
                x="แถว:Q", text=alt.Text("แถว:Q", format=","))
            st.altair_chart((bars + txt).properties(height=260))

        with c2, st.container(border=True):
            st.subheader("เครื่องที่มีแถวผิดปกติมากที่สุด")
            bm = bad["Machine"].value_counts().nlargest(15).rename_axis("Machine").reset_index(name="แถว")
            base = alt.Chart(bm).encode(y=alt.Y("Machine:N", sort="-x", title=None))
            bars = base.mark_bar(cornerRadiusEnd=3, color="#eb6834").encode(
                x=alt.X("แถว:Q", title="จำนวนแถว"),
                tooltip=[alt.Tooltip("Machine:N"), alt.Tooltip("แถว:Q")])
            txt = base.mark_text(align="left", dx=4).encode(
                x="แถว:Q", text=alt.Text("แถว:Q", format=","))
            st.altair_chart((bars + txt).properties(height=260))

        st.subheader("รายการแถวที่ผิดปกติ")
        cols = ["วันที่", "Machine", "ชื่อเครื่อง", "PlanMin", "RunMin", "LossMin",
                "Pieces", "Good", "Cap", "ปัญหาข้อมูล"]
        show_bad = bad[cols].rename(columns={
            "PlanMin": "เวลาทำงาน (นาที)", "RunMin": "เวลาทำงานจริง (นาที)",
            "LossMin": "เวลาสูญเสีย (นาที)", "Pieces": "จำนวนชิ้น", "Good": "ชิ้นงานดี"})
        st.dataframe(show_bad.sort_values("วันที่"), hide_index=True, height=380,
                     column_config={"วันที่": st.column_config.DateColumn(format="DD/MM/YYYY")})
        st.download_button("⬇️ ดาวน์โหลดรายการผิดปกติ (CSV)",
                           data=show_bad.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"oee_ข้อมูลผิดปกติ_{d1:%Y%m%d}-{d2:%Y%m%d}.csv",
                           mime="text/csv")
        st.caption("แถวเหล่านี้มักเกิดจากการคีย์เวลา/จำนวนผิดที่ต้นทาง (ระบบ MOS) — "
                   "แก้ที่ไฟล์ต้นทางแล้วกด 'โหลดข้อมูลใหม่'")

    dup = df_raw[df_raw["บันทึกซ้อน"]]
    if not dup.empty:
        with st.expander(f"แถวที่บันทึกช่วงหยุดซ้อนเวลากัน ({len(dup):,} แถว)", expanded=False):
            st.caption("ผลรวมเวลาสูญเสียรายหมวดมากกว่าเวลาสูญเสียสุทธิของวันนั้น "
                       "— เกิดเมื่อช่วงหยุดหลายรายการทับเวลากัน ไม่กระทบค่า OEE")
            show_dup = dup[["วันที่", "Machine", "PlanMin", "RunMin", "LossMin",
                            "CompLoss", "ส่วนต่างหมวด"]].rename(columns={
                "PlanMin": "เวลาทำงาน (นาที)", "RunMin": "เวลาทำงานจริง (นาที)",
                "LossMin": "เวลาสูญเสียสุทธิ (นาที)", "CompLoss": "รวมรายหมวด (นาที)",
                "ส่วนต่างหมวด": "ส่วนเกิน (นาที)"}).sort_values("ส่วนเกิน (นาที)", ascending=False)
            st.dataframe(show_dup, hide_index=True, height=320,
                         column_config={"วันที่": st.column_config.DateColumn(format="DD/MM/YYYY")})

# ===========================================================================
# ⑦ ข้อมูล & ส่งออก
# ===========================================================================
with tab_raw:
    st.subheader("ข้อมูลรายวัน-รายเครื่อง (ตามตัวกรอง)")
    cols = (["วันที่", "Machine", "ชื่อเครื่อง", "หมวดหมู่", "กลุ่มหลัก",
             "PlanMin", "RunMin", "LossMin"] + LOSS_COLS +
            ["Cap", "Pieces", "Good", "A", "P", "Q", "OEE", "หมายเหตุ"])
    rename = {"PlanMin": "เวลาทำงาน (นาที)", "RunMin": "เวลาทำงานจริง (นาที)",
              "LossMin": "เวลาสูญเสีย (นาที)", "Pieces": "จำนวนชิ้น", "Good": "ชิ้นงานดี",
              "A": "Availability (%)", "P": "Performance (%)", "Q": "Quality (%)", "OEE": "OEE (%)"}
    rename.update({c: LOSS_NAME[c] + " (นาที)" for c in LOSS_COLS})
    table = df[cols].rename(columns=rename)
    st.dataframe(table, hide_index=True, height=430,
                 column_config={"วันที่": st.column_config.DateColumn(format="DD/MM/YYYY")})

    summary_mc = by_group(df, ["Machine"])
    summary_m = by_group(df, ["เดือนปี"]).sort_values("เดือนปี")
    if not summary_m.empty:
        summary_m["เดือน"] = summary_m["เดือนปี"].map(month_label)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        table.to_excel(xw, sheet_name="ข้อมูลรายวัน", index=False)
        summary_mc.to_excel(xw, sheet_name="สรุปรายเครื่อง", index=False)
        summary_m.to_excel(xw, sheet_name="สรุปรายเดือน", index=False)
        pd.DataFrame([K]).to_excel(xw, sheet_name="สรุปรวม", index=False)
        if not ev.empty:
            ev.drop(columns=["เดือนปี"]).to_excel(xw, sheet_name="เหตุการณ์หยุดเครื่อง", index=False)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ ส่งออก Excel (ข้อมูล + สรุป)", data=buf.getvalue(),
            file_name=f"OEE_รายงาน_{d1:%Y%m%d}-{d2:%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch", type="primary")
    with c2:
        st.download_button(
            "⬇️ ส่งออก CSV (ข้อมูลรายวัน)", data=table.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"OEE_ข้อมูลรายวัน_{d1:%Y%m%d}-{d2:%Y%m%d}.csv",
            mime="text/csv", width="stretch")

    with st.expander("วิธีคิด OEE ที่ใช้ในระบบนี้"):
        st.markdown(
            "- **Availability** = MIN(เวลาทำงานจริง ÷ เวลาทำงาน, 100%)\n"
            "- **Performance** = MIN(จำนวนชิ้นที่ผลิตได้ ÷ Cap, 100%) — เครื่องที่ไม่มี Cap จะเว้นว่าง\n"
            "- **Quality** = MIN(ชิ้นงานดี ÷ จำนวนชิ้นที่ผลิต, 100%)\n"
            "- **OEE** = A × P × Q\n"
            "- ระดับสรุป (เดือน / เครื่อง / ทั้งฝ่าย) ใช้ **ผลรวม** เป็นตัวตั้ง-ตัวหาร "
            "ไม่ใช่ค่าเฉลี่ยของเปอร์เซ็นต์รายวัน จึงถ่วงน้ำหนักตามปริมาณงานจริง\n"
            "- ตรงกับตรรกะในชีต `วิธีคิด OEE` (Rev.001) ของไฟล์ฐานข้อมูลหลัก"
        )
