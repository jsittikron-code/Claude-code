"""
Workcenter Monitoring — ศูนย์ปฏิบัติการเครื่องจักร (Real-time)
--------------------------------------------------------------
อ่านไฟล์ log การสแกนงานรายเครื่อง (raw_*.xls รูปแบบ r-jobtran-mc) จากโฟลเดอร์
"9.workcenter operation" บน OneDrive แล้วแสดงผล 5 มุมมอง:
  1. สถานะสด        — บอร์ดสถานะรายเครื่อง (ทำงาน / ว่าง / หยุดเครื่อง) อัปเดตอัตโนมัติ
  2. Timeline        — Gantt กิจกรรมรายเครื่องตลอดวัน แยกสีงานปกติ/สาเหตุหยุด
  3. การหยุดเครื่อง   — Pareto สาเหตุ + เครื่องที่เสียเวลามากสุด + รายการเหตุการณ์
  4. ผลงาน           — ชิ้นงาน/Job รายเครื่อง รายพนักงาน + เวลาเดินเครื่องจริง
  5. ข้อมูลดิบ        — ตารางธุรกรรมทั้งหมด + ดาวน์โหลด CSV

ความ "real-time": แอปเฝ้าดูโฟลเดอร์ทุก 30 วินาที — พอมีไฟล์ raw ใหม่/ไฟล์ถูกอัปเดต
หน้าจอจะรีเฟรชเอง และบอร์ดสถานะคำนวณเวลาว่างใหม่ทุก 1 นาที

รันด้วย:  streamlit run workcenter_monitor.py
"""

import glob
import io
import os
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import auth

# ---------------------------------------------------------------------------
# ตั้งค่าหน้าเพจ
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Workcenter Monitoring — ศูนย์ปฏิบัติการเครื่องจักร",
    page_icon="🏭",
    layout="wide",
)


# ด่านล็อกอิน — รายชื่อผู้ใช้อยู่ใน .streamlit/secrets.toml (ไม่ push ขึ้น git)
# ใช้บัญชีชุดเดียวกับแดชบอร์ดตัวอื่นในโฟลเดอร์นี้ ดูโมดูล auth.py
auth.check_login("Workcenter Monitoring — ศูนย์ปฏิบัติการเครื่องจักร")

# โฟลเดอร์ข้อมูลหลักบน OneDrive — วางไฟล์ raw ใหม่ที่นี่ หน้าจอจะอัปเดตเอง
DATA_DIR = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา\9.workcenter operation"
)
FILE_PATTERN = "raw_*.xls*"

# ฐานข้อมูลหลัก Workcenter (ชีต Data รวมธุรกรรมทุกวันตั้งแต่ต้นปี) — แหล่งข้อมูลอันดับ 1
# ถ้าไฟล์นี้ไม่มี/อ่านไม่ได้ ค่อยถอยไปอ่านไฟล์ raw_*.xls รายวันแบบเดิม
MASTER_PATH = os.path.join(DATA_DIR, "Workcenter_ฐานข้อมูลหลัก_2569.xlsx")

# ฐานข้อมูลหลักของฝ่ายซ่อมบำรุง — แอปเฝ้าดูไฟล์พวกนี้ด้วย อัปเดตเมื่อไรรีเฟรชเอง
MTBF_PATH = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา\2.เรื่องMTBF-MTTR\รายละเอียด\MTBF-MTTR_ฐานข้อมูลหลัก_2569.xlsx"
)
OEE_PATH = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา\3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx"
)

# ชีตเหตุการณ์หยุดเครื่องในฐาน MTBF-MTTR → ประเภทเหตุการณ์
MTBF_SHEETS = {
    "Breakdown_B000000001": "Breakdown",
    "Maintenance_BP00000001": "Maintenance",
    "P000000001_รายละเอียด": "Planned stop",
}

# คอลัมน์ที่ต้องมี (แถวหัวตารางอยู่บรรทัดที่ 3 ของชีต Report2)
REQUIRED_COLUMNS = ["Machine", "Name", "Job", "Qty", "Start", "End", "Reason"]

# กลุ่มเครื่องจักรตามรหัสนำหน้า (ชุดเดียวกับ monitor.py)
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

# สถานะเครื่อง ณ เวลาปัจจุบัน
STATUS_RUN = "🟢 กำลังทำงาน"
STATUS_IDLE = "🟡 ว่าง / ไม่มีการสแกน"
STATUS_DOWN = "🔴 หยุดเครื่อง"
STATUS_NODATA = "⚪ ไม่มีข้อมูลวันนี้"
STATUS_COLORS = {
    STATUS_RUN: "#0ca30c",
    STATUS_IDLE: "#fab219",
    STATUS_DOWN: "#d03b3b",
    STATUS_NODATA: "#9a9891",
}

# ป้ายเหตุการณ์ซ่อม ตามรหัส Job ในฐาน MTBF-MTTR:
#   B000000001  = ผู้คุมเครื่องแจ้งเครื่องเสีย → ช่วงรอช่างเข้ามา
#   BP00000001  = ช่างเข้าซ่อมจริง
LABEL_B = "🔴 แจ้งซ่อม-รอช่าง (B)"
LABEL_BP = "🔧 ช่างเข้าซ่อม (BP)"

# สีงานปกติ + สาเหตุหยุดเครื่องบน Timeline (palette colorblind-safe ชุดเดียวกับ monitor.py)
COLOR_WORK = "#2a78d6"
REASON_COLORS = {
    "ทำงานปกติ": COLOR_WORK,
    LABEL_B: "#d03b3b",
    LABEL_BP: "#7a5bd6",
    "เครื่องชำรุด": "#e34948",
    "อุปกรณ์เครื่องจักรชำรุด": "#d03b3b",
    "ทำ PM Check/ทำความสะอาด": "#1baf7a",
    "เปลี่ยน tooling": "#eb6834",
    "เตรียมวัตถุดิบ": "#eda100",
    "รองาน": "#e87ba4",
    "หยุดตามเวลาพัก": "#7f9db9",
    "แก้ไขงานไม่ผ่าน": "#c2185b",
    "วัตถุดิบมีปัญหา": "#a0722e",
    "ประชุมชี้แจงภาระงาน": "#008b8b",
    "เครื่องจักรหยุด": "#b03060",
    "ปรับเครื่องจักร": "#e29b3d",
    "ปรับโปรแกรม": "#4a3aa7",
    "อุปกรณ์อื่นๆ ชำรุด (เครื่องจักรทำงานได้)": "#e8837a",
    "(ไม่ระบุ)": "#898781",
    "อื่น ๆ": "#52514e",
}


# ---------------------------------------------------------------------------
# โหลดและเตรียมข้อมูล
# ---------------------------------------------------------------------------
def folder_signature() -> tuple:
    """ลายเซ็นแหล่งข้อมูล = (ชื่อไฟล์, เวลาแก้ไข) ของไฟล์ raw ทุกไฟล์ + ฐาน MTBF/OEE
    — ไฟล์ไหนถูก sync/อัปเดต ลายเซ็นเปลี่ยน แอปจะโหลดใหม่และรีเฟรชเอง"""
    files = sorted(glob.glob(os.path.join(DATA_DIR, FILE_PATTERN)))
    files += [p for p in (MASTER_PATH, MTBF_PATH, OEE_PATH) if os.path.exists(p)]
    return tuple((os.path.basename(p), os.path.getmtime(p)) for p in files)


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    """คอลัมน์อนุพันธ์ที่ทุกแหล่งข้อมูลต้องมีเหมือนกัน"""
    df["Date"] = df["Start"].dt.date
    df["Name"] = (
        df["Name"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        .replace({"nan": "ไม่ระบุชื่อ", "": "ไม่ระบุชื่อ"})
    )
    # แยกประเภทงานซ่อมจากรหัส Job: B = แจ้งซ่อม-รอช่าง, BP = ช่างเข้าซ่อม
    job = df["Job"].astype(str)
    is_bp = job.str.startswith("BP") & df["IsDowntime"]
    is_b = job.str.startswith("B") & ~is_bp & df["IsDowntime"]

    # ป้ายกิจกรรมสำหรับ Timeline/บอร์ดสถานะ: งานผลิต → "ทำงานปกติ",
    # งานซ่อม B/BP → ป้ายเฉพาะ (สาเหตุละเอียดอยู่ในคอลัมน์ "สาเหตุ"),
    # งานหยุดตามแผน (P) → ตาม Reason, ค่าแปลก → "อื่น ๆ"
    reason = df["Reason"].astype("string")
    act = reason.fillna("(ไม่ระบุ)")
    act = act.where(act.isin(REASON_COLORS), "อื่น ๆ")
    act = act.mask(is_b, LABEL_B).mask(is_bp, LABEL_BP)
    df["กิจกรรม"] = act.where(df["IsDowntime"], "ทำงานปกติ")

    df["ประเภทงาน"] = "PROD - งานผลิต"
    df.loc[df["IsDowntime"], "ประเภทงาน"] = "P - หยุดตามแผน"
    df.loc[is_b, "ประเภทงาน"] = "B - แจ้งซ่อม (รอช่าง)"
    df.loc[is_bp, "ประเภทงาน"] = "BP - ช่างเข้าซ่อม"
    df["สาเหตุ"] = reason.fillna(df["ประเภทงาน"])
    return df.sort_values(["Machine", "Start"]).reset_index(drop=True)


@st.cache_data(show_spinner="กำลังอ่านฐานข้อมูล Workcenter จาก OneDrive...", ttl="2h")
def load_data(sig: tuple) -> pd.DataFrame:
    # sig เป็นส่วนหนึ่งของ cache key — ไฟล์ในโฟลเดอร์เปลี่ยนเมื่อไร cache เก่าถูกทิ้งทันที
    # --- แหล่งที่ 1: ฐานข้อมูลหลัก (ชีต Data ~3 แสนแถว ใช้ calamine อ่านในสิบกว่าวินาที) ---
    if os.path.exists(MASTER_PATH):
        try:
            df = pd.read_excel(MASTER_PATH, sheet_name="Data", engine="calamine")
            need = ["Machine", "พนักงาน", "Job", "หมวดJob", "Qty", "Start", "End"]
            if all(c in df.columns for c in need):
                df = df.rename(columns={
                    "พนักงาน": "Name",
                    "หมวดเครื่อง": "Group",
                    "Duration(นาที)": "DurationMin",
                    "แหล่งข้อมูล": "ไฟล์ต้นทาง",
                })
                df = df[df["Machine"].notna()].copy()
                df["Machine"] = df["Machine"].astype(str).str.strip()
                df["Start"] = pd.to_datetime(df["Start"], errors="coerce")
                df["End"] = pd.to_datetime(df["End"], errors="coerce")
                df = df.dropna(subset=["Start", "End"])
                df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
                if "DurationMin" in df.columns:
                    df["DurationMin"] = pd.to_numeric(df["DurationMin"], errors="coerce")
                    df["DurationMin"] = df["DurationMin"].fillna(
                        (df["End"] - df["Start"]).dt.total_seconds() / 60)
                else:
                    df["DurationMin"] = (df["End"] - df["Start"]).dt.total_seconds() / 60
                df["IsDowntime"] = ~df["หมวดJob"].astype(str).str.startswith("PROD")
                if "Reason" not in df.columns:
                    df["Reason"] = pd.NA
                if "ไฟล์ต้นทาง" not in df.columns:
                    df["ไฟล์ต้นทาง"] = os.path.basename(MASTER_PATH)
                if "Group" not in df.columns:
                    df["Group"] = pd.NA
                df["Group"] = df["Group"].astype("string").str.strip().replace(
                    {"": pd.NA, "nan": pd.NA}
                ).fillna(
                    df["Machine"].str.extract(r"^([A-Za-z]+)")[0].str.upper()
                    .map(lambda g: GROUP_NAMES.get(g, g))
                )
                return _finish(df)
        except Exception:
            pass  # อ่านฐานหลักไม่ได้ (เช่นถูกล็อกระหว่าง sync) — ถอยไปไฟล์ raw

    # --- แหล่งที่ 2 (สำรอง): ไฟล์ raw_*.xls รายวันแบบเดิม ---
    frames = []
    for path in glob.glob(os.path.join(DATA_DIR, FILE_PATTERN)):
        try:
            df = pd.read_excel(path, sheet_name=0, header=2)
        except Exception:
            continue  # ข้ามไฟล์ที่เปิดล็อกอยู่หรือรูปแบบไม่ตรง
        if not all(c in df.columns for c in REQUIRED_COLUMNS):
            continue
        df["ไฟล์ต้นทาง"] = os.path.basename(path)
        frames.append(df)
    if not frames:
        raise ValueError(
            f"อ่านฐานข้อมูลไม่ได้เลย — ตรวจโฟลเดอร์\n{DATA_DIR}\n\n"
            f"ลำดับที่ลองอ่าน: 1) {os.path.basename(MASTER_PATH)} (ชีต Data) "
            f"2) ไฟล์ {FILE_PATTERN} (รายงาน r-jobtran-mc ชีต Report2)\n"
            "ถ้าไฟล์กำลัง sync จาก OneDrive อยู่ รอสักครู่แล้วกด 'โหลดข้อมูลใหม่'"
        )

    df = pd.concat(frames, ignore_index=True)
    df = df[df["Machine"].notna()].copy()
    df["Start"] = pd.to_datetime(df["Start"], errors="coerce")
    df["End"] = pd.to_datetime(df["End"], errors="coerce")
    df = df.dropna(subset=["Start", "End"])
    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)

    # ไฟล์ raw หลายไฟล์มีข้อมูลซ้อนวันกัน — ตัดแถวซ้ำออก
    df = df.drop_duplicates(subset=["Machine", "Job", "Item", "Start", "End"], keep="last")

    df["Machine"] = df["Machine"].astype(str).str.strip()
    prefix = df["Machine"].str.extract(r"^([A-Za-z]+)")[0].str.upper()
    df["Group"] = prefix.map(lambda g: GROUP_NAMES.get(g, g))
    df["DurationMin"] = (df["End"] - df["Start"]).dt.total_seconds() / 60
    df["IsDowntime"] = df["Reason"].notna()
    return _finish(df)


@st.cache_data(show_spinner="กำลังอ่านฐานข้อมูล MTBF-MTTR...", ttl="2h")
def load_mtbf(sig: tuple) -> tuple[dict, pd.DataFrame]:
    """อ่านฐาน MTBF-MTTR → (หมวดหมู่เครื่องจักร, เหตุการณ์หยุดเครื่องทุกประเภท)"""
    if not os.path.exists(MTBF_PATH):
        return {}, pd.DataFrame()
    # ถ้าไฟล์ถูกล็อก (เปิดใน Excel / กำลัง sync) ปล่อย exception ให้จุดเรียกจัดการ —
    # st.cache_data ไม่เก็บผลที่ error ไว้ รอบรีเฟรชถัดไปจะลองอ่านใหม่เอง
    xl = pd.ExcelFile(MTBF_PATH, engine="openpyxl")

    cat_map = {}
    if "หมวดหมู่เครื่องจักร" in xl.sheet_names:
        cat = xl.parse("หมวดหมู่เครื่องจักร")
        cat_map = dict(
            zip(cat["รหัสเครื่อง"].astype(str).str.strip(),
                cat["หมวดหมู่เครื่อง"].astype(str).str.strip())
        )

    frames = []
    for sheet, typ in MTBF_SHEETS.items():
        if sheet not in xl.sheet_names:
            continue
        df = xl.parse(sheet)
        df = df[df["Machine"].notna()].copy()
        df["Start"] = pd.to_datetime(df["Start"], errors="coerce")
        df["End"] = pd.to_datetime(df["End"], errors="coerce")
        df = df.dropna(subset=["Start", "End"])
        out = pd.DataFrame({
            "Machine": df["Machine"].astype(str).str.strip(),
            "Name": df.get("ชื่อพนักงาน", pd.Series(dtype=str)).astype(str)
                    .str.replace(r"\s+", " ", regex=True).str.strip(),
            "Start": df["Start"],
            "End": df["End"],
            "DurationMin": pd.to_numeric(df["ระยะเวลา (นาที)"], errors="coerce").fillna(0),
            "Reason": df["Reason"] if "Reason" in df.columns else pd.NA,
            "ประเภท": typ,
        })
        frames.append(out)
    if not frames:
        return cat_map, pd.DataFrame()

    ev = pd.concat(frames, ignore_index=True)
    # ป้ายกิจกรรมตามชีตต้นทาง: Breakdown = แจ้งซ่อม-รอช่าง (B), Maintenance = ช่างเข้าซ่อม (BP)
    ev["กิจกรรม"] = ev["Reason"].astype("string").fillna("(ไม่ระบุ)")
    ev["กิจกรรม"] = ev["กิจกรรม"].where(ev["กิจกรรม"].isin(REASON_COLORS), "อื่น ๆ")
    ev.loc[ev["ประเภท"] == "Breakdown", "กิจกรรม"] = LABEL_B
    ev.loc[ev["ประเภท"] == "Maintenance", "กิจกรรม"] = LABEL_BP
    ev["ประเภทงาน"] = ev["ประเภท"].map({
        "Breakdown": "B - แจ้งซ่อม (รอช่าง)",
        "Maintenance": "BP - ช่างเข้าซ่อม",
        "Planned stop": "P - หยุดตามแผน",
    })
    ev["สาเหตุ"] = ev["Reason"].astype("string").fillna(ev["ประเภทงาน"])
    ev["Date"] = ev["Start"].dt.date
    ev["Month"] = ev["Start"].dt.to_period("M").dt.to_timestamp()
    ev["Group"] = ev["Machine"].map(cat_map).fillna(
        ev["Machine"].str.extract(r"^([A-Za-z]+)")[0].str.upper()
        .map(lambda g: GROUP_NAMES.get(g, g))
    )
    return cat_map, ev.sort_values(["Machine", "Start"]).reset_index(drop=True)


@st.cache_data(show_spinner="กำลังอ่านฐานข้อมูล OEE (เวลาทำงานจริง)...", ttl="2h")
def load_oee_runtime(sig: tuple) -> pd.DataFrame:
    """เวลาทำงานจริง/วัน รายเครื่องจากฐาน OEE — ตัวหารของสูตร MTBF มาตรฐานฝ่าย"""
    if not os.path.exists(OEE_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_excel(OEE_PATH, sheet_name="Report1",
                           usecols=["MC", "Trans_date", "เวลาทำงานจริง/วัน"])
    except Exception:
        return pd.DataFrame()
    df["Trans_date"] = pd.to_datetime(df["Trans_date"], errors="coerce")
    df = df.dropna(subset=["Trans_date"])
    df["MC"] = df["MC"].astype(str).str.strip()
    df["เวลาทำงานจริง/วัน"] = pd.to_numeric(df["เวลาทำงานจริง/วัน"], errors="coerce").fillna(0)
    df["Date"] = df["Trans_date"].dt.date
    return df


def merged_minutes(intervals: list[tuple]) -> float:
    """รวมนาทีของช่วงเวลาแบบไม่นับซ้ำ (สแกนหลายงานเวลาเดียวกันนับครั้งเดียว)"""
    if not intervals:
        return 0.0
    total = 0.0
    cur_s, cur_e = None, None
    for s, e in sorted(intervals):
        if cur_s is None:
            cur_s, cur_e = s, e
        elif s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += (cur_e - cur_s).total_seconds()
            cur_s, cur_e = s, e
    total += (cur_e - cur_s).total_seconds()
    return total / 60


def machine_status(day_df: pd.DataFrame, all_machines: list[str],
                   ref_time: pd.Timestamp, idle_min: int) -> pd.DataFrame:
    """สถานะรายเครื่อง ณ เวลา ref_time ของวันที่เลือก"""
    rows = []
    by_mc = dict(tuple(day_df.groupby("Machine")))
    for mc in all_machines:
        g = by_mc.get(mc)
        if g is None or g.empty:
            rows.append({"Machine": mc, "สถานะ": STATUS_NODATA, "รายละเอียด": "—",
                         "พนักงาน": "—", "กิจกรรมล่าสุด": None, "Job": 0, "ชิ้น": 0.0,
                         "ว่างมาแล้ว (นาที)": None})
            continue

        work = g[~g["IsDowntime"]]
        down = g[g["IsDowntime"]]
        last_end = g["End"].max()
        last_row = g.loc[g["End"].idxmax()]

        # เหตุการณ์หยุดเครื่องที่คร่อมเวลาปัจจุบันอยู่ → ถือว่ายังหยุด
        active_down = down[(down["Start"] <= ref_time) & (down["End"] >= ref_time)]
        idle_gap = (ref_time - last_end).total_seconds() / 60

        if not active_down.empty:
            status = STATUS_DOWN
            last_down = active_down.iloc[-1]
            detail = str(last_down.get("สาเหตุ") or last_down.get("Reason") or "ไม่ระบุ")
        elif idle_gap <= idle_min:
            status = STATUS_RUN
            detail = str(last_row.get("Description", ""))[:40]
        else:
            status = STATUS_IDLE
            detail = f"สแกนล่าสุด {last_end:%H:%M}"

        rows.append({
            "Machine": mc,
            "สถานะ": status,
            "รายละเอียด": detail,
            "พนักงาน": str(last_row["Name"]),
            "กิจกรรมล่าสุด": last_end,
            "Job": int(work["Job"].nunique()),
            "ชิ้น": float(work["Qty"].sum()),
            "ว่างมาแล้ว (นาที)": max(0.0, idle_gap),
        })
    out = pd.DataFrame(rows)
    out["Group"] = (
        out["Machine"].str.extract(r"^([A-Za-z]+)")[0].str.upper()
        .map(lambda g: GROUP_NAMES.get(g, g))
    )
    return out


def status_card(row: pd.Series):
    """การ์ดสถานะเครื่อง (HTML บรรทัดเดียว กัน Streamlit ตีความเป็น code block)"""
    color = STATUS_COLORS[row["สถานะ"]]
    icon = row["สถานะ"].split()[0]
    if row["สถานะ"] == STATUS_NODATA:
        line2 = "ไม่มีการสแกนวันนี้"
        line3 = "&nbsp;"
    else:
        emp = row["พนักงาน"]
        if len(emp) > 28:  # บางเครื่องมีพนักงานหลายคนคั่นด้วยจุลภาค — ตัดให้พอดีการ์ด
            emp = emp[:26] + "…"
        line2 = f"👤 {emp} · ล่าสุด {row['กิจกรรมล่าสุด']:%H:%M}"
        line3 = f"{row['Job']} Job · {row['ชิ้น']:,.0f} ชิ้น"
        if row["สถานะ"] == STATUS_DOWN:
            line3 = f"⚠️ {row['รายละเอียด']}"
        elif row["สถานะ"] == STATUS_IDLE:
            line3 = f"ว่างมา {row['ว่างมาแล้ว (นาที)']:,.0f} นาที · {row['Job']} Job"
    html = (
        f'<div style="border-left:6px solid {color};border-radius:10px;'
        f'background:linear-gradient(135deg,{color}18 0%,{color}06 100%);'
        f'padding:10px 12px;margin-bottom:8px;min-height:86px;">'
        f'<div style="font-weight:800;font-size:1.05rem;">{icon} {row["Machine"]}</div>'
        f'<div style="font-size:0.78rem;color:#52514e;">{line2}</div>'
        f'<div style="font-size:0.78rem;color:#52514e;">{line3}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# เฝ้าดูโฟลเดอร์ — มีไฟล์ใหม่/ไฟล์ถูกอัปเดต ให้รีเฟรชทั้งแอป
# ---------------------------------------------------------------------------
@st.fragment(run_every="30s")
def watch_folder():
    sig = folder_signature()
    prev = st.session_state.get("_folder_sig")
    st.session_state["_folder_sig"] = sig
    if prev is not None and sig != prev:
        st.rerun(scope="app")


# ---------------------------------------------------------------------------
# โหลดข้อมูล + แถบควบคุมด้านข้าง
# ---------------------------------------------------------------------------
st.title("🏭 Workcenter Monitoring — ศูนย์ปฏิบัติการเครื่องจักร")

try:
    data = load_data(folder_signature())
except ValueError as e:
    st.error(str(e))
    st.stop()
try:
    cat_map, mtbf_events = load_mtbf(folder_signature())
except Exception:
    cat_map, mtbf_events = {}, pd.DataFrame()
    st.sidebar.warning(
        "⚠️ อ่านฐาน MTBF-MTTR ไม่ได้ชั่วคราว (ไฟล์ถูกเปิดอยู่/กำลัง sync) — "
        "ส่วน MTBF/MTTR จะว่างจนกว่าจะอ่านได้ แอปจะลองใหม่เมื่อรีเฟรช"
    )
try:
    oee_runtime = load_oee_runtime(folder_signature())
except Exception:
    oee_runtime = pd.DataFrame()
watch_folder()

# หมวดเครื่องจากฐาน Workcenter เป็นหลัก — ที่ขาดค่อยเติมจากฐาน MTBF-MTTR
if cat_map:
    data["Group"] = data["Group"].fillna(data["Machine"].map(cat_map))


def merge_master_events(ev: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    """เติมเหตุการณ์ B/BP/P จากฐาน Workcenter ที่ยังไม่มีในฐาน MTBF-MTTR

    ฐาน Workcenter มักถูกอัปเดตบ่อยกว่า — ถ้าไฟล์ MTBF-MTTR ยังไม่ได้ทำรอบใหม่
    แท็บ MTBF/MTTR จะยังเห็นข้อมูลวันล่าสุดเสมอ (ตัดรายการซ้ำด้วย เครื่อง+เริ่ม+จบ)
    """
    typ_map = {
        "B - แจ้งซ่อม (รอช่าง)": "Breakdown",
        "BP - ช่างเข้าซ่อม": "Maintenance",
        "P - หยุดตามแผน": "Planned stop",
    }
    m = master[master["ประเภทงาน"].isin(typ_map)].copy()
    if m.empty:
        return ev
    m["ประเภท"] = m["ประเภทงาน"].map(typ_map)
    m["Month"] = m["Start"].dt.to_period("M").dt.to_timestamp()
    cols = ["Machine", "Name", "Start", "End", "DurationMin", "Reason",
            "ประเภท", "กิจกรรม", "ประเภทงาน", "สาเหตุ", "Date", "Month", "Group"]
    m = m[[c for c in cols if c in m.columns]]

    def key(df):
        return (df["Machine"].astype(str) + "|"
                + df["Start"].dt.floor("min").astype(str) + "|"
                + df["End"].dt.floor("min").astype(str))

    if ev.empty:
        return m.sort_values(["Machine", "Start"]).reset_index(drop=True)
    extra = m[~key(m).isin(set(key(ev)))]
    if extra.empty:
        return ev
    return (pd.concat([ev, extra], ignore_index=True)
            .sort_values(["Machine", "Start"]).reset_index(drop=True))


mtbf_events = merge_master_events(mtbf_events, data)

dates = sorted(data["Date"].unique())
latest_date = dates[-1]

with st.sidebar:
    auth.sidebar_user_box()
    st.header("⚙️ การตั้งค่า")
    sel_date = st.selectbox(
        "วันที่",
        options=list(reversed(dates)),
        format_func=lambda d: f"{d:%d/%m/%Y}" + (" (ล่าสุด)" if d == latest_date else ""),
    )
    groups = sorted(data["Group"].dropna().unique())
    sel_groups = st.multiselect("กลุ่มเครื่องจักร", groups, default=[],
                                placeholder="ทั้งหมด")
    idle_min = st.slider("เกณฑ์ถือว่า 'ว่าง' (นาทีที่ไม่มีการสแกน)", 5, 60, 20, step=5)
    st.markdown("---")
    files = folder_signature()
    st.caption(
        "**ไฟล์ในโฟลเดอร์:**\n\n"
        + "\n".join(
            f"- {name} · อัปเดต {datetime.fromtimestamp(mt):%d/%m %H:%M}"
            for name, mt in files
        )
    )
    if st.button("🔄 โหลดข้อมูลใหม่", width="stretch",
                 help="ล้าง cache แล้วอ่านไฟล์จากโฟลเดอร์ใหม่ทันที"):
        st.cache_data.clear()
        st.rerun()

day_df = data[data["Date"] == sel_date]
if sel_groups:
    day_df = day_df[day_df["Group"].isin(sel_groups)]

# เหตุการณ์หยุดเครื่องจากฐาน MTBF-MTTR ของวันเดียวกัน — เติมเข้าข้อมูลวัน
# (ตัดรายการที่ซ้ำกับแถว Reason ในไฟล์ raw ออก เทียบด้วย เครื่อง+นาทีเริ่ม+นาทีจบ)
if not mtbf_events.empty:
    day_ev = mtbf_events[mtbf_events["Date"] == sel_date]
    if sel_groups:
        day_ev = day_ev[day_ev["Group"].isin(sel_groups)]
    if not day_ev.empty:
        def _key(df):
            return (df["Machine"] + "|" + df["Start"].dt.floor("min").astype(str)
                    + "|" + df["End"].dt.floor("min").astype(str))
        existing = set(_key(day_df[day_df["IsDowntime"]])) if not day_df.empty else set()
        extra = day_ev[~_key(day_ev).isin(existing)].copy()
        if not extra.empty:
            extra["Job"] = extra["ประเภท"]
            extra["Description"] = extra["Reason"]
            extra["Qty"] = 0
            extra["IsDowntime"] = True
            extra["ไฟล์ต้นทาง"] = "MTBF-MTTR_ฐานข้อมูลหลัก"
            day_df = pd.concat([day_df, extra.drop(columns=["ประเภท", "Month"])],
                               ignore_index=True)

# เครื่องทั้งหมดที่เคยปรากฏในทุกไฟล์ (ให้เครื่องที่วันนี้ยังไม่สแกนโชว์เป็น ⚪ ด้วย)
universe = data[data["Group"].isin(sel_groups)] if sel_groups else data
all_machines = sorted(universe["Machine"].unique())

if day_df.empty:
    st.warning("ไม่มีข้อมูลของวัน/กลุ่มที่เลือก — ลองปรับตัวกรอง")
    st.stop()

# เวลาอ้างอิงของบอร์ดสถานะ:
#   วันล่าสุด + ข้อมูลยังสด (< 45 นาที) → ใช้เวลาจริงตอนนี้ (นาฬิกาเดิน สถานะเปลี่ยนเอง)
#   นอกนั้น → ใช้เวลาสแกนสุดท้ายของวันนั้น (โหมดย้อนดู)
def reference_time() -> tuple[pd.Timestamp, bool]:
    now = pd.Timestamp.now()
    # ยึดเฉพาะงานผลิตที่จบภายในวันเดียวกัน — งานซ่อม/งาน batch ที่ลากข้ามคืน
    # จะดันเวลาอ้างอิงไปวันถัดไปจนทุกเครื่องกลายเป็น "ว่าง"
    day_end = pd.Timestamp(sel_date) + pd.Timedelta(days=1)
    scans = day_df[(~day_df["IsDowntime"]) & (day_df["End"] < day_end)]
    data_max = scans["End"].max() if not scans.empty else min(day_df["End"].max(), day_end)
    if sel_date == latest_date and (now - data_max) < timedelta(minutes=45):
        return now, True
    return data_max, False


# ---------------------------------------------------------------------------
# แท็บหลัก
# ---------------------------------------------------------------------------
tab_live, tab_timeline, tab_down, tab_mtbf, tab_perf, tab_raw = st.tabs(
    ["🟢 สถานะสด", "📅 Timeline", "⏱ การหยุดเครื่อง", "🔧 MTBF / MTTR",
     "📊 ผลงาน", "📋 ข้อมูลดิบ"]
)

# --- 1) สถานะสด — rerun ตัวเองทุก 1 นาที ให้เวลาว่าง/สถานะเดินเอง ---
with tab_live:
    @st.fragment(run_every="60s")
    def live_board():
        ref, is_live = reference_time()
        status_df = machine_status(day_df, all_machines, ref, idle_min)

        mode = "🔴 LIVE — อัปเดตอัตโนมัติ" if is_live else "🕐 ย้อนดู ณ เวลาสแกนสุดท้าย"
        st.caption(
            f"{mode} · เวลาอ้างอิง **{ref:%d/%m/%Y %H:%M}** · "
            f"เกณฑ์ว่าง {idle_min} นาที · ข้อมูลวันที่ {sel_date:%d/%m/%Y}"
        )

        counts = status_df["สถานะ"].value_counts()
        work_day = day_df[~day_df["IsDowntime"]]
        with st.container(horizontal=True):
            st.metric("🟢 กำลังทำงาน", f"{counts.get(STATUS_RUN, 0)} เครื่อง", border=True)
            st.metric("🟡 ว่าง", f"{counts.get(STATUS_IDLE, 0)} เครื่อง", border=True)
            st.metric("🔴 หยุดเครื่อง", f"{counts.get(STATUS_DOWN, 0)} เครื่อง", border=True)
            st.metric("⚪ ไม่มีข้อมูล", f"{counts.get(STATUS_NODATA, 0)} เครื่อง", border=True)
            st.metric("ชิ้นงานวันนี้", f"{work_day['Qty'].sum():,.0f} ชิ้น", border=True)
            st.metric("Job วันนี้", f"{work_day['Job'].nunique():,} Job", border=True)

        st.markdown("")
        only_problem = st.toggle("แสดงเฉพาะเครื่องที่ว่าง/หยุด/ไม่มีข้อมูล", value=False)
        show_df = status_df
        if only_problem:
            show_df = status_df[status_df["สถานะ"] != STATUS_RUN]

        for grp, g in show_df.groupby("Group", sort=True):
            st.subheader(f"{grp} · {len(g)} เครื่อง", divider="gray")
            cols = st.columns(5)
            for i, (_, row) in enumerate(g.iterrows()):
                with cols[i % 5]:
                    status_card(row)

    live_board()

# กะทำงานของโรงงาน: กะเดียว 07:00–16:00, หลัง 16:00 คือ OT (ไม่ข้ามวัน)
SHIFT_START_HOUR = 7
SHIFT_END_HOUR = 16
LABEL_SHIFT = "กะปกติ (07:00–16:00)"
LABEL_OT = "OT (หลัง 16:00)"


@st.cache_data(ttl="2h", show_spinner=False)
def activity_by_slot(sig: tuple, dates_tuple: tuple, groups_tuple: tuple) -> pd.DataFrame:
    """จำนวนเครื่องที่กำลังเดิน (มีงานผลิตคร่อมช่วงเวลา) ทุก 30 นาที ของแต่ละวัน"""
    rows = []
    for d in dates_tuple:
        dd = data[(data["Date"] == d) & (~data["IsDowntime"])]
        if groups_tuple:
            dd = dd[dd["Group"].isin(list(groups_tuple))]
        day0 = pd.Timestamp(d)
        for i in range(48):
            s0 = day0 + pd.Timedelta(minutes=30 * i)
            s1 = s0 + pd.Timedelta(minutes=30)
            n = dd[(dd["Start"] < s1) & (dd["End"] > s0)]["Machine"].nunique()
            rows.append({"Date": d, "slot_idx": i, "เครื่อง": n})
    return pd.DataFrame(rows)


# --- 2) Timeline (Gantt) ---
with tab_timeline:
    st.subheader(f"📅 Timeline กิจกรรมรายเครื่อง — {sel_date:%d/%m/%Y}")

    # สรุปงานในกะ vs OT ของวันนี้ (แบ่งตามเวลาเริ่มของแต่ละรายการ)
    work_rows = day_df[~day_df["IsDowntime"]]
    hr = work_rows["Start"].dt.hour
    in_shift = work_rows[(hr >= SHIFT_START_HOUR) & (hr < SHIFT_END_HOUR)]
    in_ot = work_rows[hr >= SHIFT_END_HOUR]
    pre_shift = work_rows[hr < SHIFT_START_HOUR]
    with st.container(horizontal=True):
        st.metric(f"🕗 {LABEL_SHIFT}",
                  f"{len(in_shift):,} รายการ · {in_shift['Qty'].sum():,.0f} ชิ้น",
                  border=True)
        st.metric(f"🌙 {LABEL_OT}",
                  f"{len(in_ot):,} รายการ · {in_ot['Qty'].sum():,.0f} ชิ้น",
                  border=True)
        if len(pre_shift):
            st.metric("ก่อนกะ (ก่อน 07:00)",
                      f"{len(pre_shift):,} รายการ · {pre_shift['Qty'].sum():,.0f} ชิ้น",
                      border=True)

    plot = day_df.copy()
    # งานสแกนเร็ว (ไม่กี่วินาที) มองไม่เห็นบนกราฟ — ยืดความยาวขั้นต่ำ 1 นาทีเฉพาะการแสดงผล
    plot["EndDisplay"] = plot[["End", "Start"]].max(axis=1)
    short = (plot["EndDisplay"] - plot["Start"]) < pd.Timedelta(minutes=1)
    plot.loc[short, "EndDisplay"] = plot.loc[short, "Start"] + pd.Timedelta(minutes=1)

    # กรอบเวลาของกราฟ = 06:00–24:00 ของวันที่เลือก — งาน batch ข้ามวันถูกตัดปลายที่เที่ยงคืน
    day0 = pd.Timestamp(sel_date)
    tl_start = day0 + pd.Timedelta(hours=6)
    tl_end = day0 + pd.Timedelta(days=1)
    shift_start = day0 + pd.Timedelta(hours=SHIFT_START_HOUR)
    shift_end = day0 + pd.Timedelta(hours=SHIFT_END_HOUR)

    # แถบพื้นหลังแยกช่วงกะปกติ (เขียวอ่อน) กับ OT (ส้มอ่อน) + เส้นแบ่งที่ 07:00 / 16:00
    shift_bands = pd.DataFrame([
        {"s": shift_start, "e": shift_end, "ช่วงเวลา": LABEL_SHIFT},
        {"s": shift_end, "e": tl_end, "ช่วงเวลา": LABEL_OT},
    ])
    band_scale = alt.Scale(domain=[LABEL_SHIFT, LABEL_OT], range=["#1baf7a", "#eb6834"])
    bg_bands = (
        alt.Chart(shift_bands)
        .mark_rect(opacity=0.08)
        .encode(x="s:T", x2="e:T",
                color=alt.Color("ช่วงเวลา:N", scale=band_scale,
                                legend=alt.Legend(title="ช่วงเวลา", orient="top")))
    )
    shift_rules = (
        alt.Chart(pd.DataFrame({"t": [shift_start, shift_end]}))
        .mark_rule(color="#52514e", strokeDash=[5, 4], strokeWidth=1.5)
        .encode(x="t:T")
    )

    cat_domain = [c for c in REASON_COLORS if c in set(plot["กิจกรรม"])]
    gantt = (
        alt.Chart(plot)
        .mark_bar(cornerRadius=2, height=14, clip=True)
        .encode(
            y=alt.Y("Machine:N", sort=all_machines, title=None),
            x=alt.X("Start:T", title="เวลา", axis=alt.Axis(format="%H:%M"),
                    scale=alt.Scale(domain=[tl_start, tl_end])),
            x2="EndDisplay:T",
            color=alt.Color(
                "กิจกรรม:N",
                scale=alt.Scale(domain=cat_domain,
                                range=[REASON_COLORS[c] for c in cat_domain]),
                legend=alt.Legend(title="กิจกรรม", orient="top"),
            ),
            tooltip=[
                alt.Tooltip("Machine:N", title="เครื่อง"),
                alt.Tooltip("ประเภทงาน:N", title="ประเภทงาน"),
                alt.Tooltip("สาเหตุ:N", title="สาเหตุ"),
                alt.Tooltip("Name:N", title="พนักงาน"),
                alt.Tooltip("Job:N"),
                alt.Tooltip("Description:N", title="ชิ้นงาน"),
                alt.Tooltip("Qty:Q", title="จำนวน", format=",.0f"),
                alt.Tooltip("Start:T", title="เริ่ม", format="%H:%M:%S"),
                alt.Tooltip("End:T", title="จบ", format="%H:%M:%S"),
                alt.Tooltip("DurationMin:Q", title="นาที", format=",.1f"),
            ],
        )
        .properties(height=max(320, 22 * plot["Machine"].nunique()))
    )
    layered = (
        alt.layer(bg_bands, shift_rules, gantt)
        .resolve_scale(color="independent")
        .interactive()
    )
    st.altair_chart(layered, width="stretch")
    st.caption(
        "พื้นหลังเขียว = กะปกติ 07:00–16:00 · พื้นหลังส้ม = OT หลัง 16:00 (เส้นประแนวตั้งคือรอยต่อกะ) · "
        "แท่งสั้นกว่า 1 นาทีถูกยืดให้เห็นบนกราฟ เวลาใน tooltip เป็นเวลาจริง · ลากเพื่อเลื่อน สกอลล์เพื่อซูม"
    )

    # --- กราฟเส้นแนวโน้ม: จำนวนเครื่องที่เดินตามช่วงเวลา (หา Peak) ---
    st.markdown("---")
    st.subheader("📈 แนวโน้มจำนวนเครื่องที่เดินตามช่วงเวลา (Peak)")
    prev_dates = [d for d in dates if d < sel_date][-7:]
    slot_df = activity_by_slot(folder_signature(),
                               tuple(prev_dates + [sel_date]),
                               tuple(sel_groups))
    today_lbl = f"วันที่เลือก ({sel_date:%d/%m})"
    avg_lbl = f"เฉลี่ย {len(prev_dates)} วันก่อนหน้า"
    sel_slots = (
        slot_df[slot_df["Date"] == sel_date][["slot_idx", "เครื่อง"]]
        .assign(ชุดข้อมูล=today_lbl)
    )
    series = [sel_slots]
    if prev_dates:
        avg_slots = (
            slot_df[slot_df["Date"] != sel_date]
            .groupby("slot_idx")["เครื่อง"].mean().round(1).reset_index()
            .assign(ชุดข้อมูล=avg_lbl)
        )
        series.append(avg_slots)
    trend = pd.concat(series, ignore_index=True)
    trend["slot"] = day0 + pd.to_timedelta(trend["slot_idx"] * 30, unit="m")

    peak_line = (
        alt.Chart(trend)
        .mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=22), interpolate="monotone")
        .encode(
            x=alt.X("slot:T", title="เวลา", axis=alt.Axis(format="%H:%M"),
                    scale=alt.Scale(domain=[tl_start, tl_end])),
            y=alt.Y("เครื่อง:Q", title="จำนวนเครื่องที่กำลังเดิน"),
            color=alt.Color("ชุดข้อมูล:N",
                            scale=alt.Scale(domain=[today_lbl, avg_lbl],
                                            range=[COLOR_WORK, "#9a9891"]),
                            legend=alt.Legend(title=None, orient="top")),
            strokeDash=alt.StrokeDash("ชุดข้อมูล:N",
                                      scale=alt.Scale(domain=[today_lbl, avg_lbl],
                                                      range=[[1, 0], [6, 4]]),
                                      legend=None),
            tooltip=[
                alt.Tooltip("slot:T", title="เวลา", format="%H:%M"),
                alt.Tooltip("ชุดข้อมูล:N", title="ชุดข้อมูล"),
                alt.Tooltip("เครื่อง:Q", title="เครื่องที่เดิน", format=".1f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(
        alt.layer(bg_bands, shift_rules, peak_line).resolve_scale(color="independent"),
        width="stretch",
    )
    if not sel_slots.empty and sel_slots["เครื่อง"].max() > 0:
        pk = sel_slots.loc[sel_slots["เครื่อง"].idxmax()]
        pk_time = day0 + pd.Timedelta(minutes=int(pk["slot_idx"]) * 30)
        st.caption(
            f"⛰️ ช่วง Peak ของวันที่เลือก: **{pk_time:%H:%M}–{pk_time + pd.Timedelta(minutes=30):%H:%M}** "
            f"มีเครื่องเดินพร้อมกัน **{pk['เครื่อง']:.0f} เครื่อง** · "
            "เส้นประสีเทา = ค่าเฉลี่ยวันก่อนหน้า เอาไว้เทียบว่าวันนี้เดินมาก/น้อยกว่าปกติช่วงไหน"
        )

# --- 3) การหยุดเครื่อง ---
with tab_down:
    down = day_df[day_df["IsDowntime"]]
    if down.empty:
        st.success("วันนี้ไม่มีบันทึกการหยุดเครื่อง 🎉")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("เหตุการณ์หยุดเครื่อง", f"{len(down)} ครั้ง", border=True)
        c2.metric("เวลาหยุดรวม", f"{down['DurationMin'].sum():,.0f} นาที", border=True)
        c3.metric("เครื่องที่ได้รับผลกระทบ", f"{down['Machine'].nunique()} เครื่อง", border=True)

        col_l, col_r = st.columns(2)
        with col_l:
            with st.container(border=True):
                st.subheader("สาเหตุการหยุด (Pareto)")
                pareto = (
                    down.groupby("สาเหตุ")["DurationMin"].sum()
                    .reset_index().sort_values("DurationMin", ascending=False)
                )
                chart = (
                    alt.Chart(pareto)
                    .mark_bar(color="#d03b3b", cornerRadiusTopRight=4,
                              cornerRadiusBottomRight=4, size=24)
                    .encode(
                        y=alt.Y("สาเหตุ:N", sort="-x", title=None),
                        x=alt.X("DurationMin:Q", title="นาทีรวม"),
                        tooltip=[alt.Tooltip("สาเหตุ:N"),
                                 alt.Tooltip("DurationMin:Q", title="นาที", format=",.0f")],
                    )
                    .properties(height=60 + 40 * len(pareto))
                )
                st.altair_chart(chart, width="stretch")
        with col_r:
            with st.container(border=True):
                st.subheader("เครื่องที่หยุดนานที่สุด")
                by_mc = (
                    down.groupby("Machine")["DurationMin"].sum()
                    .reset_index().sort_values("DurationMin", ascending=False).head(15)
                )
                chart = (
                    alt.Chart(by_mc)
                    .mark_bar(color="#d03b3b", cornerRadiusTopRight=4,
                              cornerRadiusBottomRight=4, size=18)
                    .encode(
                        y=alt.Y("Machine:N", sort="-x", title=None),
                        x=alt.X("DurationMin:Q", title="นาทีรวม"),
                        tooltip=[alt.Tooltip("Machine:N"),
                                 alt.Tooltip("DurationMin:Q", title="นาที", format=",.0f")],
                    )
                    .properties(height=60 + 26 * len(by_mc))
                )
                st.altair_chart(chart, width="stretch")

        st.subheader("รายการเหตุการณ์หยุดเครื่อง")
        show = down[["Machine", "ประเภทงาน", "สาเหตุ", "Name",
                     "Start", "End", "DurationMin"]].copy()
        show = show.sort_values("DurationMin", ascending=False)
        show["Start"] = show["Start"].dt.strftime("%H:%M")
        show["End"] = show["End"].dt.strftime("%H:%M")
        show["DurationMin"] = show["DurationMin"].round(1)
        show.columns = ["เครื่อง", "ประเภทงาน", "สาเหตุ", "พนักงาน", "เริ่ม", "จบ", "นาที"]
        st.dataframe(show, width="stretch", hide_index=True)

# --- 4) MTBF / MTTR (สูตรมาตรฐานฝ่าย: MTBF = เวลาทำงานจริงรวม ÷ ครั้ง Breakdown,
#                      MTTR = เวลา Breakdown รวม ÷ ครั้ง Breakdown) ---
with tab_mtbf:
    if mtbf_events.empty:
        st.info(f"อ่านฐานข้อมูล MTBF-MTTR ไม่ได้ — ตรวจไฟล์\n\n{MTBF_PATH}")
    else:
        ev = mtbf_events
        if sel_groups:
            ev = ev[ev["Group"].isin(sel_groups)]

        # ขอบเขตวันที่ = ช่วงที่ "มีเหตุการณ์ซ่อมจริง" ในฐานข้อมูล (B/BP)
        # ไม่ใช่ช่วงของไฟล์ทั้งไฟล์ — กันไม่ให้ค่าเริ่มต้นไปตกวันที่ยังไม่มีข้อมูล
        repair = ev[ev["ประเภท"].isin(["Breakdown", "Maintenance"])]
        bounds_src = repair if not repair.empty else ev
        ev_min, ev_max = bounds_src["Date"].min(), bounds_src["Date"].max()

        PRESETS = {"ทั้งหมด": None, "90 วันล่าสุด": 90, "30 วันล่าสุด": 30,
                   "7 วันล่าสุด": 7, "กำหนดเอง": "custom"}
        c_preset, c_range = st.columns([2, 1])
        with c_preset:
            preset = st.segmented_control(
                "ช่วงวันที่วิเคราะห์", list(PRESETS), default="ทั้งหมด",
                key="mtbf_preset",
            ) or "ทั้งหมด"
        if PRESETS[preset] == "custom":
            with c_range:
                picked = st.date_input(
                    "เลือกช่วงเอง", value=(ev_min, ev_max),
                    min_value=ev_min, max_value=ev_max, key="mtbf_range",
                )
            if isinstance(picked, tuple) and len(picked) == 2:
                r_start, r_end = picked
            else:  # ผู้ใช้เพิ่งคลิกวันแรก ยังไม่ครบช่วง — ใช้ทั้งช่วงไปก่อน
                r_start, r_end = ev_min, ev_max
        elif PRESETS[preset]:
            r_end = ev_max
            r_start = max(ev_min, ev_max - timedelta(days=PRESETS[preset] - 1))
        else:
            r_start, r_end = ev_min, ev_max

        # จำกัดให้อยู่ในช่วงข้อมูลจริงเสมอ แม้ฐานข้อมูลจะถูกอัปเดตช่วงใหม่
        r_start = max(min(r_start, ev_max), ev_min)
        r_end = min(max(r_end, ev_min), ev_max)
        st.caption(
            f"📅 วิเคราะห์ **{r_start:%d/%m/%Y} – {r_end:%d/%m/%Y}** · "
            f"ข้อมูลซ่อมในฐานมีถึงวันที่ {ev_max:%d/%m/%Y} "
            f"(เริ่ม {ev_min:%d/%m/%Y})"
        )
        ev = ev[(ev["Date"] >= r_start) & (ev["Date"] <= r_end)]
        if ev.empty:
            st.warning(
                f"ไม่มีเหตุการณ์ในช่วง {r_start:%d/%m/%Y} – {r_end:%d/%m/%Y} — "
                "เลือก 'ทั้งหมด' เพื่อดูทุกช่วงที่มีข้อมูล"
            )

        run = oee_runtime
        if not run.empty:
            run = run[(run["Date"] >= r_start) & (run["Date"] <= r_end)]
            if sel_groups:
                run_groups = run["MC"].map(cat_map)
                run = run[run_groups.isin(sel_groups)]

        bd = ev[ev["ประเภท"] == "Breakdown"]
        mt = ev[ev["ประเภท"] == "Maintenance"]
        n_bd = len(bd)
        bd_min = bd["DurationMin"].sum()
        runtime_min = run["เวลาทำงานจริง/วัน"].sum() if not run.empty else 0.0
        fleet_mttr = bd_min / n_bd if n_bd else 0.0
        fleet_mtbf = runtime_min / 60 / n_bd if n_bd and runtime_min else None

        with st.container(horizontal=True):
            st.metric("🔴 แจ้งซ่อม (B)", f"{n_bd} ครั้ง", border=True,
                      help="Job B000000001 — ผู้คุมเครื่องแจ้งเครื่องเสีย")
            st.metric("เวลาแจ้งซ่อมรวม (B)", f"{bd_min / 60:,.1f} ชม.", border=True)
            st.metric("MTTR เฉลี่ยทั้งฝ่าย", f"{fleet_mttr:,.1f} นาที/ครั้ง", border=True,
                      help="เวลาแจ้งซ่อม (B) รวม ÷ จำนวนครั้ง")
            st.metric(
                "MTBF เฉลี่ยทั้งฝ่าย",
                f"{fleet_mtbf:,.1f} ชม." if fleet_mtbf else "—",
                border=True,
                help="เวลาทำงานจริงรวม (จากฐาน OEE) ÷ จำนวนครั้ง Breakdown",
            )
            st.metric("🔧 ช่างเข้าซ่อม (BP)", f"{len(mt)} ครั้ง", border=True,
                      help="Job BP00000001 — ช่างเข้าซ่อมจริง")
            st.metric("เวลาช่างซ่อมรวม (BP)", f"{mt['DurationMin'].sum() / 60:,.1f} ชม.",
                      border=True)

        # ---- เชื่อมโยงเหตุการณ์ แจ้งซ่อม (B) → ช่างเข้าซ่อม (BP) ----
        # จับคู่: BP ครั้งแรกของเครื่องเดียวกันที่เริ่มหลังการแจ้ง (ภายใน 8 ชม.หลังจบ B)
        st.markdown("---")
        st.subheader("🔗 เชื่อมโยง แจ้งซ่อม (B) → ช่างเข้าซ่อม (BP)")
        bp_pool = mt.sort_values("Start")
        used_bp = set()
        pair_rows = []
        for _, b_row in bd.sort_values("Start").iterrows():
            cand = bp_pool[
                (bp_pool["Machine"] == b_row["Machine"])
                & (bp_pool["Start"] >= b_row["Start"])
                & (bp_pool["Start"] <= b_row["End"] + pd.Timedelta(hours=8))
                & (~bp_pool.index.isin(used_bp))
            ]
            if not cand.empty:
                bp_row = cand.iloc[0]
                used_bp.add(cand.index[0])
                wait_min = (bp_row["Start"] - b_row["Start"]).total_seconds() / 60
                pair_rows.append({
                    "วันที่": b_row["Start"].strftime("%d/%m/%Y"),
                    "เครื่อง": b_row["Machine"],
                    "สาเหตุ (จากการแจ้ง)": str(b_row["Reason"]),
                    "แจ้งซ่อม": b_row["Start"].strftime("%H:%M"),
                    "ช่างเริ่มซ่อม": bp_row["Start"].strftime("%H:%M"),
                    "ซ่อมเสร็จ": bp_row["End"].strftime("%H:%M"),
                    "รอช่าง (นาที)": round(wait_min, 1),
                    "ช่างซ่อม (นาที)": round(bp_row["DurationMin"], 1),
                    "รวมหยุด (นาที)": round(
                        (bp_row["End"] - b_row["Start"]).total_seconds() / 60, 1),
                    "จับคู่": "✅",
                    "_sort": b_row["Start"],
                })
            else:
                pair_rows.append({
                    "วันที่": b_row["Start"].strftime("%d/%m/%Y"),
                    "เครื่อง": b_row["Machine"],
                    "สาเหตุ (จากการแจ้ง)": str(b_row["Reason"]),
                    "แจ้งซ่อม": b_row["Start"].strftime("%H:%M"),
                    "ช่างเริ่มซ่อม": "—",
                    "ซ่อมเสร็จ": "—",
                    "รอช่าง (นาที)": None,
                    "ช่างซ่อม (นาที)": None,
                    "รวมหยุด (นาที)": round(b_row["DurationMin"], 1),
                    "จับคู่": "⚠️ ไม่พบ BP",
                    "_sort": b_row["Start"],
                })
        pairs = pd.DataFrame(pair_rows)
        if pairs.empty:
            st.info("ไม่มีเหตุการณ์แจ้งซ่อม (B) ในช่วงที่เลือก")
        else:
            matched = pairs[pairs["จับคู่"] == "✅"]
            with st.container(horizontal=True):
                st.metric("จับคู่ B→BP ได้", f"{len(matched)} / {len(pairs)} ครั้ง",
                          border=True)
                if not matched.empty:
                    st.metric("⏳ รอช่างเฉลี่ย", f"{matched['รอช่าง (นาที)'].mean():,.1f} นาที",
                              border=True,
                              help="เวลาแจ้งซ่อม (B เริ่ม) → ช่างเริ่มซ่อม (BP เริ่ม)")
                    st.metric("🔧 ช่างซ่อมเฉลี่ย", f"{matched['ช่างซ่อม (นาที)'].mean():,.1f} นาที",
                              border=True, help="ระยะเวลางาน BP ต่อครั้ง")
                    st.metric("รวมหยุดเฉลี่ยต่อเหตุการณ์",
                              f"{matched['รวมหยุด (นาที)'].mean():,.1f} นาที", border=True,
                              help="แจ้งซ่อม (B เริ่ม) → ซ่อมเสร็จ (BP จบ)")
            st.dataframe(
                pairs.sort_values("_sort", ascending=False).drop(columns="_sort"),
                width="stretch", hide_index=True, height=360,
            )
            st.caption(
                "จับคู่จากชีต Breakdown_B000000001 กับ Maintenance_BP00000001 ในฐาน MTBF-MTTR: "
                "เครื่องเดียวกัน และ BP เริ่มหลังการแจ้งภายใน 8 ชม. · "
                "⚠️ ไม่พบ BP = แจ้งเสียแล้วแต่ไม่มีบันทึกช่างเข้าซ่อมตามมา"
            )

        # ตารางรายเครื่อง
        rows = []
        run_by_mc = run.groupby("MC")["เวลาทำงานจริง/วัน"].sum() if not run.empty else pd.Series(dtype=float)
        machines_in_scope = sorted(set(ev["Machine"]) | set(run_by_mc.index))
        for mc in machines_in_scope:
            b = bd[bd["Machine"] == mc]
            m = mt[mt["Machine"] == mc]
            rt_min = float(run_by_mc.get(mc, 0.0))
            n = len(b)
            rows.append({
                "เครื่อง": mc,
                "หมวดหมู่": cat_map.get(mc, "—"),
                "Breakdown (ครั้ง)": n,
                "Breakdown (ชม.)": round(b["DurationMin"].sum() / 60, 2),
                "MTTR (นาที/ครั้ง)": round(b["DurationMin"].sum() / n, 1) if n else None,
                "เวลาทำงานจริง (ชม.)": round(rt_min / 60, 1),
                "MTBF (ชม.)": round(rt_min / 60 / n, 1) if n and rt_min else None,
                "Maintenance (ครั้ง)": len(m),
                "Maintenance (ชม.)": round(m["DurationMin"].sum() / 60, 2),
            })
        mtbf_table = pd.DataFrame(rows)

        col_l, col_r = st.columns(2)
        with col_l:
            with st.container(border=True):
                st.subheader("MTBF ต่ำสุด (เสียบ่อยเทียบเวลาเดินเครื่อง)")
                worst = (
                    mtbf_table.dropna(subset=["MTBF (ชม.)"])
                    .sort_values("MTBF (ชม.)").head(15)
                )
                if worst.empty:
                    st.info("ยังไม่มีเครื่องที่คำนวณ MTBF ได้ในช่วงนี้")
                else:
                    chart = (
                        alt.Chart(worst)
                        .mark_bar(color="#d03b3b", cornerRadiusTopRight=4,
                                  cornerRadiusBottomRight=4, size=18)
                        .encode(
                            y=alt.Y("เครื่อง:N", sort="x", title=None),
                            x=alt.X("MTBF (ชม.):Q", title="MTBF (ชั่วโมงทำงานจริง/ครั้ง)"),
                            tooltip=[alt.Tooltip("เครื่อง:N"),
                                     alt.Tooltip("MTBF (ชม.):Q", format=",.1f"),
                                     alt.Tooltip("Breakdown (ครั้ง):Q"),
                                     alt.Tooltip("เวลาทำงานจริง (ชม.):Q", format=",.1f")],
                        )
                        .properties(height=60 + 26 * len(worst))
                    )
                    st.altair_chart(chart, width="stretch")
        with col_r:
            with st.container(border=True):
                st.subheader("MTTR สูงสุด (ซ่อมนานต่อครั้ง)")
                slow = (
                    mtbf_table.dropna(subset=["MTTR (นาที/ครั้ง)"])
                    .sort_values("MTTR (นาที/ครั้ง)", ascending=False).head(15)
                )
                if slow.empty:
                    st.info("ไม่มีเหตุการณ์ Breakdown ในช่วงนี้")
                else:
                    chart = (
                        alt.Chart(slow)
                        .mark_bar(color="#eb6834", cornerRadiusTopRight=4,
                                  cornerRadiusBottomRight=4, size=18)
                        .encode(
                            y=alt.Y("เครื่อง:N", sort="-x", title=None),
                            x=alt.X("MTTR (นาที/ครั้ง):Q", title="MTTR (นาที/ครั้ง)"),
                            tooltip=[alt.Tooltip("เครื่อง:N"),
                                     alt.Tooltip("MTTR (นาที/ครั้ง):Q", format=",.1f"),
                                     alt.Tooltip("Breakdown (ครั้ง):Q"),
                                     alt.Tooltip("Breakdown (ชม.):Q", format=",.2f")],
                        )
                        .properties(height=60 + 26 * len(slow))
                    )
                    st.altair_chart(chart, width="stretch")

        with st.container(border=True):
            st.subheader("แนวโน้มรายเดือน — ชั่วโมงหยุดเครื่องแยกประเภท")
            monthly = (
                ev.groupby(["Month", "ประเภท"])["DurationMin"].sum()
                .div(60).reset_index().rename(columns={"DurationMin": "ชั่วโมง"})
            )
            type_colors = {"Breakdown": "#d03b3b", "Maintenance": "#4a3aa7",
                           "Planned stop": "#1baf7a"}
            chart = (
                alt.Chart(monthly)
                .mark_bar(size=38)
                .encode(
                    x=alt.X("yearmonth(Month):T", title="เดือน"),
                    y=alt.Y("ชั่วโมง:Q", title="ชั่วโมงรวม"),
                    color=alt.Color("ประเภท:N",
                                    scale=alt.Scale(domain=list(type_colors),
                                                    range=list(type_colors.values()))),
                    tooltip=[alt.Tooltip("yearmonth(Month):T", title="เดือน", format="%m/%Y"),
                             alt.Tooltip("ประเภท:N"),
                             alt.Tooltip("ชั่วโมง:Q", format=",.1f")],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")

        st.subheader("ตาราง MTBF / MTTR รายเครื่อง")
        st.dataframe(
            mtbf_table.sort_values("Breakdown (ชม.)", ascending=False),
            width="stretch", hide_index=True,
        )
        st.caption(
            "สูตรมาตรฐานฝ่าย: MTBF = เวลาทำงานจริงรวม (ฐาน OEE) ÷ จำนวนครั้ง Breakdown · "
            "MTTR = เวลา Breakdown รวม ÷ จำนวนครั้ง Breakdown · "
            "เครื่องที่ไม่มี Breakdown ในช่วง แสดง MTBF/MTTR เป็นค่าว่าง"
        )

# --- 5) ผลงาน ---
with tab_perf:
    work = day_df[~day_df["IsDowntime"]]
    st.subheader(f"📊 ผลงานประจำวัน — {sel_date:%d/%m/%Y}")

    # ตัดช่วงเวลาให้อยู่ในวันที่เลือก — งาน batch ข้ามวันไม่ทำให้เวลาเดินเครื่องบวม
    p_start = pd.Timestamp(sel_date)
    p_end = p_start + pd.Timedelta(days=1)
    perf_rows = []
    for mc, g in work.groupby("Machine"):
        s = g["Start"].clip(lower=p_start, upper=p_end)
        e = g["End"].clip(lower=p_start, upper=p_end)
        busy = merged_minutes(list(zip(s, e)))
        first, last = s.min(), e.max()
        span = (last - first).total_seconds() / 60
        perf_rows.append({
            "เครื่อง": mc,
            "กลุ่ม": g["Group"].iloc[0],
            "Job": g["Job"].nunique(),
            "ชิ้นงาน": g["Qty"].sum(),
            "เวลาเดินเครื่อง (นาที)": round(busy, 0),
            "ช่วงเวลาทำงาน": f"{first:%H:%M}–{last:%H:%M}",
            "% ใช้งานในช่วง": round(busy / span * 100, 1) if span > 0 else 0.0,
        })
    perf = pd.DataFrame(perf_rows).sort_values("ชิ้นงาน", ascending=False)

    col_l, col_r = st.columns(2)
    with col_l:
        with st.container(border=True):
            st.subheader("ชิ้นงานต่อเครื่อง (Top 15)")
            top = perf.head(15)
            chart = (
                alt.Chart(top)
                .mark_bar(color=COLOR_WORK, cornerRadiusTopRight=4,
                          cornerRadiusBottomRight=4, size=18)
                .encode(
                    y=alt.Y("เครื่อง:N", sort="-x", title=None),
                    x=alt.X("ชิ้นงาน:Q", title="จำนวนชิ้น"),
                    tooltip=[alt.Tooltip("เครื่อง:N"),
                             alt.Tooltip("ชิ้นงาน:Q", format=",.0f"),
                             alt.Tooltip("Job:Q")],
                )
                .properties(height=60 + 26 * len(top))
            )
            st.altair_chart(chart, width="stretch")
    with col_r:
        with st.container(border=True):
            st.subheader("ชิ้นงานต่อพนักงาน (Top 15)")
            by_emp = (
                work.groupby("Name").agg(ชิ้นงาน=("Qty", "sum"), Job=("Job", "nunique"))
                .reset_index().sort_values("ชิ้นงาน", ascending=False).head(15)
            )
            chart = (
                alt.Chart(by_emp)
                .mark_bar(color="#1baf7a", cornerRadiusTopRight=4,
                          cornerRadiusBottomRight=4, size=18)
                .encode(
                    y=alt.Y("Name:N", sort="-x", title=None),
                    x=alt.X("ชิ้นงาน:Q", title="จำนวนชิ้น"),
                    tooltip=[alt.Tooltip("Name:N", title="พนักงาน"),
                             alt.Tooltip("ชิ้นงาน:Q", format=",.0f"),
                             alt.Tooltip("Job:Q")],
                )
                .properties(height=60 + 26 * len(by_emp))
            )
            st.altair_chart(chart, width="stretch")

    st.subheader("ตารางสรุปรายเครื่อง")
    st.dataframe(
        perf, width="stretch", hide_index=True,
        column_config={
            "ชิ้นงาน": st.column_config.NumberColumn(format="%,.0f"),
            "% ใช้งานในช่วง": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=100
            ),
        },
    )
    st.caption(
        "เวลาเดินเครื่อง = รวมช่วง Start→End ของธุรกรรมงานแบบไม่นับซ้อนกัน · "
        "% ใช้งาน = เวลาเดินเครื่อง ÷ ช่วงตั้งแต่สแกนแรกถึงสแกนสุดท้ายของเครื่องนั้น"
    )

# --- 6) ข้อมูลดิบ ---
with tab_raw:
    st.subheader("📋 ธุรกรรมทั้งหมดของวันที่เลือก")
    display = day_df.drop(columns=["Date", "IsDowntime", "EndDisplay"], errors="ignore").copy()
    display = display.sort_values(["Machine", "Start"])
    st.dataframe(display, width="stretch", hide_index=True, height=520)

    csv_buf = io.BytesIO()
    display.to_csv(csv_buf, index=False, encoding="utf-8-sig")
    st.download_button(
        "⬇️ ดาวน์โหลดเป็น CSV",
        data=csv_buf.getvalue(),
        file_name=f"workcenter_{sel_date:%Y%m%d}.csv",
        mime="text/csv",
    )
