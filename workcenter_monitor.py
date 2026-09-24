"""
Workcenter Monitoring — ศูนย์ปฏิบัติการเครื่องจักร (Real-time)
--------------------------------------------------------------
อ่านข้อมูลการสแกนงานรายเครื่องจากไฟล์ parquet ที่ ETL ของฝ่ายสร้างให้
(00_ETL_Pipeline/parquet/workcenter_data.parquet) แล้วแสดงผล 5 มุมมอง:
  1. สถานะสด        — บอร์ดสถานะรายเครื่อง (ทำงาน / ว่าง / หยุดเครื่อง) อัปเดตอัตโนมัติ
  2. Timeline        — Gantt กิจกรรมรายเครื่องตลอดวัน แยกสีงานปกติ/สาเหตุหยุด
  3. การหยุดเครื่อง   — Pareto สาเหตุ + เครื่องที่เสียเวลามากสุด + รายการเหตุการณ์
  4. ผลงาน           — ชิ้นงาน/Job รายเครื่อง รายพนักงาน + เวลาเดินเครื่องจริง
  5. ข้อมูลดิบ        — ตารางธุรกรรมทั้งหมด + ดาวน์โหลด CSV

ความ "real-time": แอปเฝ้าดูโฟลเดอร์ทุก 30 วินาที — พอมีไฟล์ raw ใหม่/ไฟล์ถูกอัปเดต
หน้าจอจะรีเฟรชเอง และบอร์ดสถานะคำนวณเวลาว่างใหม่ทุก 1 นาที

รันด้วย:  streamlit run workcenter_monitor.py
"""

import io
import os
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import auth
import data_paths

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

# โฟลเดอร์ฐานข้อมูลเดิมบน OneDrive (ไฟล์ดิบวางที่ 00_ข้อมูลดิบ_MOS แทนแล้ว)
DATA_DIR = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา\9.workcenter operation"
)

# ไฟล์ฐานเดิม เก็บไว้เพื่อดูเวลาแก้ไขเท่านั้น ข้อมูลจริงอ่านจาก parquet ที่ ETL สร้าง
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

# ทะเบียนเครื่องจักร — ชื่อรุ่น วันติดตั้ง อายุ สถานที่ รอบ PM สถานะ
REGISTRY_PATH = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา\5.งานทะเบียนเครื่องจักร\ทะเบียนเครื่องจักร_DataMaster_2569.xlsx"
)
# ใบงานซ่อมย้อนหลัง 2020-2026 — ค่าใช้จ่าย PM/BM Electric/Mechanical Module
# หาโฟลเดอร์เอง ไม่ฝังชื่อโฟลเดอร์ไว้ในโค้ด (ดู data_paths.py)
REPAIR_PATH = os.path.join(data_paths.repair_dir(),
                           "รายงานซ่อมบำรุง_เครื่อง_2020-2026.xlsx")

# ชั่วโมงงานมาตรฐานต่อวัน ใช้เป็นตัวหารของ % เดินเครื่อง (กะเดียว 07:00-16:00)
PLAN_MINUTES_PER_DAY = 480

# จานสีสำหรับกราฟโมดูลเครื่องจักร (ชุด colorblind-safe เดียวกับกราฟอื่น)
MODULE_COLORS = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#4a3aa7", "#008b8b", "#d03b3b",
]

# ชีตเหตุการณ์หยุดเครื่องในฐาน MTBF-MTTR → ประเภทเหตุการณ์
MTBF_SHEETS = {
    "Breakdown_B000000001": "Breakdown",
    "Maintenance_BP00000001": "Maintenance",
    "P000000001_รายละเอียด": "Planned stop",
}

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
LABEL_B = "แจ้งซ่อม-รอช่าง (B)"
LABEL_BP = "ช่างเข้าซ่อม (BP)"

# มาตรฐานสีของฝ่าย:
#   ทำงานปกติ (PROD) = เขียว · งาน P (หยุดตามแผน) = โทนเหลือง
#   แจ้งซ่อม B = แดงอ่อน · ช่างซ่อม BP = แดงเข้ม
COLOR_WORK = "#21a559"    # เขียว — ทำงานปกติ
COLOR_P = "#f2b705"       # เหลือง — งาน P
COLOR_B = "#f07575"       # แดงอ่อน — แจ้งซ่อม B
COLOR_BP = "#b31217"      # แดงเข้ม — ช่างซ่อม BP

REASON_COLORS = {
    "ทำงานปกติ": COLOR_WORK,
    LABEL_B: COLOR_B,
    LABEL_BP: COLOR_BP,
    # สาเหตุฝั่งแจ้งซ่อม (B) — โทนแดงอ่อน
    "เครื่องชำรุด": "#f07575",
    "อุปกรณ์เครื่องจักรชำรุด": "#e35d5d",
    # สาเหตุฝั่งงาน P — โทนเหลือง/ทอง ไล่เฉดให้พอแยกกันได้
    "เปลี่ยน tooling": "#f2b705",
    "ทำ PM Check/ทำความสะอาด": "#ffd23c",
    "เตรียมวัตถุดิบ": "#d9a404",
    "รองาน": "#f7e08a",
    "หยุดตามเวลาพัก": "#c9b458",
    "แก้ไขงานไม่ผ่าน": "#e0851f",
    "วัตถุดิบมีปัญหา": "#a0722e",
    "ประชุมชี้แจงภาระงาน": "#bfa100",
    "เครื่องจักรหยุด": "#8f7a1e",
    "ปรับเครื่องจักร": "#e8c547",
    "ปรับโปรแกรม": "#cdaa4e",
    "อุปกรณ์อื่นๆ ชำรุด (เครื่องจักรทำงานได้)": "#e59d3c",
    "(ไม่ระบุ)": "#898781",
    "อื่น ๆ": "#52514e",
}


# ---------------------------------------------------------------------------
# โหลดและเตรียมข้อมูล
# ---------------------------------------------------------------------------
# เวอร์ชันของตรรกะเตรียมข้อมูล — ขยับเลขนี้ทุกครั้งที่แก้ป้าย/สี/คอลัมน์ที่คำนวณไว้
# เพื่อให้ cache เก่าถูกทิ้งเอง (st.cache_data ไม่รู้จักการเปลี่ยนค่าคงที่ภายนอกฟังก์ชัน)
DATA_LOGIC_VERSION = "2026-08-04.1-std-colors"


def folder_signature() -> tuple:
    """ลายเซ็นแหล่งข้อมูล = (ชื่อไฟล์, เวลาแก้ไข) ของทุกไฟล์ที่หน้านี้อ่าน
    — ไฟล์ไหนถูก sync/อัปเดต ลายเซ็นเปลี่ยน แอปจะโหลดใหม่และรีเฟรชเอง

    รวมลายเซ็นของ parquet ที่ ETL สร้างด้วย ETL รันใหม่เมื่อไร หน้าจอรีเฟรชเมื่อนั้น"""
    files = [p for p in (MTBF_PATH, OEE_PATH, REGISTRY_PATH, REPAIR_PATH)
             if os.path.exists(p)]
    return (("logic", DATA_LOGIC_VERSION),) + data_paths.workcenter_signature() + tuple(
        (os.path.basename(p), os.path.getmtime(p)) for p in files
    )


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
    """อ่านข้อมูล Workcenter จาก parquet ที่ ETL ของฝ่ายสร้างให้

    มีแหล่งเดียว ไม่มีทางสำรอง — เดิมมีทางสำรองที่อ่านไฟล์ raw_*.xls แต่เอาออกแล้ว
    ด้วยเหตุผล 2 ข้อ หนึ่งคือมันใช้กฎจำแนกงานหยุดเครื่องคนละชุด (ดูว่ามี Reason
    กรอกไว้ไหม แทนที่จะดูหมวดJob) ซึ่งมองข้ามงานหยุดเครื่องไป 1,082 จาก 6,603 แถว
    สองคือไฟล์ที่มันจะไปอ่านไม่มีอยู่จริงแล้วตั้งแต่ย้ายมาใช้ ETL กลาง

    ห้ามกลืน exception ที่นี่ — ถ้าอ่านไม่ได้ต้องให้ error ขึ้นหน้าจอ
    ดีกว่าเงียบแล้วแสดงตัวเลขจากกฎคนละชุดโดยไม่มีใครรู้
    """
    # sig เป็นส่วนหนึ่งของ cache key — ETL รันใหม่เมื่อไร cache เก่าถูกทิ้งทันที
    # กฎการแปลงข้อมูลอยู่ใน update_mos.py ที่เดียว ห้ามเขียนซ้ำที่นี่
    df = pd.read_parquet(data_paths.workcenter_parquet())

    need = ["Machine", "พนักงาน", "Job", "หมวดJob", "Qty", "Start", "End"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(
            "ไฟล์ข้อมูล Workcenter ขาดคอลัมน์: " + ", ".join(missing) + "\n\n"
            "แปลว่าโครงสร้างที่ ETL สร้างเปลี่ยนไป ให้ตรวจ update_mos.py\n"
            f"ไฟล์ที่อ่าน: {data_paths.WC_PARQUET}"
        )

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
        df["ไฟล์ต้นทาง"] = os.path.basename(data_paths.WC_PARQUET)
    if "Group" not in df.columns:
        df["Group"] = pd.NA
    df["Group"] = df["Group"].astype("string").str.strip().replace(
        {"": pd.NA, "nan": pd.NA}
    ).fillna(
        df["Machine"].str.extract(r"^([A-Za-z]+)")[0].str.upper()
        .map(lambda g: GROUP_NAMES.get(g, g))
    )
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
    """เวลาทำงานจริง/วัน รายเครื่องจากฐาน OEE — ตัวหารของสูตร MTBF มาตรฐานฝ่าย

    ห้ามกลืน exception ในฟังก์ชันที่ถูก cache — ถ้าอ่านพลาดชั่วคราว (ไฟล์ถูกล็อก
    ระหว่าง OneDrive sync) แล้วคืนค่าว่าง ค่าว่างจะถูก cache ค้างจน TTL หมด
    ให้โยน error ออกไปแทน จุดเรียกจะจัดการเป็นค่าว่างเฉพาะรอบนั้นและลองใหม่เอง
    """
    if not os.path.exists(OEE_PATH):
        return pd.DataFrame()
    df = pd.read_excel(OEE_PATH, sheet_name="Report1",
                       usecols=["MC", "Trans_date", "เวลาทำงานจริง/วัน"])
    df["Trans_date"] = pd.to_datetime(df["Trans_date"], errors="coerce")
    df = df.dropna(subset=["Trans_date"])
    df["MC"] = df["MC"].astype(str).str.strip()
    df["เวลาทำงานจริง/วัน"] = pd.to_numeric(df["เวลาทำงานจริง/วัน"], errors="coerce").fillna(0)
    df["Date"] = df["Trans_date"].dt.date
    return df


@st.cache_data(show_spinner="กำลังอ่านทะเบียนเครื่องจักร...", ttl="2h")
def load_registry(sig: tuple) -> pd.DataFrame:
    """ทะเบียนเครื่องจักร (ชีต 'ทะเบียนหลัก' หัวตารางอยู่แถวที่ 3) → index = รหัสเครื่อง

    ห้ามกลืน exception ในฟังก์ชันที่ถูก cache (ดูเหตุผลที่ load_oee_runtime) —
    เคยเกิดเหตุไฟล์ถูกล็อกระหว่าง sync แล้วค่าว่างถูก cache ค้าง ทำให้ทุกเครื่อง
    ขึ้น "ไม่มีในทะเบียน" ทั้งที่ไฟล์ปกติ
    """
    if not os.path.exists(REGISTRY_PATH):
        return pd.DataFrame()
    df = pd.read_excel(REGISTRY_PATH, sheet_name="ทะเบียนหลัก", header=2,
                       engine="calamine")
    if "รหัสเครื่อง" not in df.columns:
        raise ValueError("ทะเบียนเครื่องจักร: ไม่พบคอลัมน์ 'รหัสเครื่อง' "
                         "(โครงชีต 'ทะเบียนหลัก' อาจถูกแก้)")
    df = df[df["รหัสเครื่อง"].notna()].copy()
    df["รหัสเครื่อง"] = df["รหัสเครื่อง"].astype(str).str.strip()
    df["วันที่ติดตั้ง"] = pd.to_datetime(df["วันที่ติดตั้ง"], errors="coerce")
    df["อายุ (ปี)"] = pd.to_numeric(df["อายุ (ปี)"], errors="coerce")
    # คอลัมน์อายุในไฟล์อาจว่าง (เช่นสูตรถูกล้างตอนแก้ไฟล์) —
    # ถ้ามีวันที่ติดตั้ง ให้คำนวณอายุเองเสมอ ไม่พึ่งค่าในไฟล์อย่างเดียว
    need = df["อายุ (ปี)"].isna() & df["วันที่ติดตั้ง"].notna()
    df.loc[need, "อายุ (ปี)"] = (
        (pd.Timestamp.now() - df.loc[need, "วันที่ติดตั้ง"]).dt.days / 365.25
    ).round(1)
    return df.drop_duplicates(subset="รหัสเครื่อง").set_index("รหัสเครื่อง")


@st.cache_data(show_spinner="กำลังอ่านใบงานซ่อม 2020-2026...", ttl="2h")
def load_repair(sig: tuple) -> pd.DataFrame:
    """ใบงานซ่อมย้อนหลังรายเครื่อง — ค่าใช้จ่าย เวลาซ่อม PM/BM Electric/Mechanical Module

    ห้ามกลืน exception ในฟังก์ชันที่ถูก cache (ดูเหตุผลที่ load_oee_runtime)
    """
    if not os.path.exists(REPAIR_PATH):
        return pd.DataFrame()
    df = pd.read_excel(REPAIR_PATH, sheet_name="ข้อมูล", engine="calamine")
    if "รหัสเครื่อง" not in df.columns:
        raise ValueError("ใบงานซ่อม: ไม่พบคอลัมน์ 'รหัสเครื่อง' "
                         "(โครงชีต 'ข้อมูล' อาจถูกแก้)")
    df = df[df["รหัสเครื่อง"].notna()].copy()
    df["รหัสเครื่อง"] = df["รหัสเครื่อง"].astype(str).str.strip()
    df["วันที่แจ้งซ่อม"] = pd.to_datetime(df["วันที่แจ้งซ่อม"], errors="coerce")
    for c in ("ค่าใช้จ่าย (บาท)", "Petty Cash (บาท)", "เวลาซ่อม (นาที)", "ปี"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["ค่าใช้จ่ายรวม"] = (df.get("ค่าใช้จ่าย (บาท)", 0)
                          + df.get("Petty Cash (บาท)", 0))
    for c in ("สถานะการซ่อม (PM/BM)", "ประเภทงาน", "Module", "ชื่อโมดูล"):
        if c in df.columns:
            df[c] = df[c].astype("string").fillna("ไม่ระบุ").str.strip()
    return df


# ---------------------------------------------------------------------------
# จับคู่เหตุการณ์ซ่อม B → BP และคิดเวลาหยุดเครื่องต่อครั้ง
# ---------------------------------------------------------------------------
PAIR_WINDOW_HOURS = 8   # BP ต้องเริ่มภายในกี่ชั่วโมงหลังใบแจ้ง B ปิด จึงถือว่าเป็นคู่กัน


def pair_repairs(b_df: pd.DataFrame, bp_df: pd.DataFrame) -> pd.DataFrame:
    """จับคู่ใบแจ้งซ่อม (B) กับงานช่าง (BP) ของเครื่องเดียวกัน

    คืน 1 แถวต่อ 1 เหตุการณ์เสีย พร้อมเวลา 3 ช่วง:
      รอช่าง    = B เริ่ม → BP เริ่ม
      ช่างซ่อม   = ระยะเวลางาน BP
      หยุดรวม   = B เริ่ม → BP จบ   ← ตัวตั้งของ MTTR (เวลาที่เครื่องหยุดผลิตจริง)

    ถ้าหาคู่ BP ไม่เจอ ใช้ระยะเวลาของใบแจ้ง B เป็นเวลาหยุดแทน
    (ประเมินต่ำกว่าความจริง แต่ดีกว่าทิ้งเหตุการณ์นั้นไป)
    """
    cols = ["Machine", "b_start", "b_end", "bp_start", "bp_end",
            "wait_min", "repair_min", "downtime_min", "matched", "Reason"]
    if b_df.empty:
        return pd.DataFrame(columns=cols)

    pool = bp_df.sort_values("Start") if not bp_df.empty else bp_df
    used, rows = set(), []
    for _, b in b_df.sort_values("Start").iterrows():
        cand = pool[
            (pool["Machine"] == b["Machine"])
            & (pool["Start"] >= b["Start"])
            & (pool["Start"] <= b["End"] + pd.Timedelta(hours=PAIR_WINDOW_HOURS))
            & (~pool.index.isin(used))
        ] if not pool.empty else pool
        if len(cand):
            bp = cand.iloc[0]
            used.add(cand.index[0])
            rows.append({
                "Machine": b["Machine"], "b_start": b["Start"], "b_end": b["End"],
                "bp_start": bp["Start"], "bp_end": bp["End"],
                "wait_min": (bp["Start"] - b["Start"]).total_seconds() / 60,
                "repair_min": (bp["End"] - bp["Start"]).total_seconds() / 60,
                "downtime_min": (bp["End"] - b["Start"]).total_seconds() / 60,
                "matched": True, "Reason": b.get("Reason"),
            })
        else:
            rows.append({
                "Machine": b["Machine"], "b_start": b["Start"], "b_end": b["End"],
                "bp_start": pd.NaT, "bp_end": pd.NaT,
                "wait_min": None, "repair_min": None,
                "downtime_min": (b["End"] - b["Start"]).total_seconds() / 60,
                "matched": False, "Reason": b.get("Reason"),
            })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False, ttl="2h")
def machine_runtime_profile(sig: tuple, mc: str) -> dict:
    """สรุปเวลาเดินเครื่อง/หยุด ของเครื่องหนึ่ง จากฐาน Workcenter

    เวลาเดินเครื่องจริง (net) = รวมช่วง Start→End ของงานผลิตแบบไม่นับซ้อนกัน
    เวลาตามแผน (plan)        = จำนวนวันที่มีบันทึก × 480 นาที (กะเดียว 8 ชม.)
    """
    g = data[data["Machine"] == mc]
    if g.empty:
        return {}
    prod = g[~g["IsDowntime"]]
    net_by_month, net_by_day, net_total = {}, {}, 0.0
    for d, dg in prod.groupby("Date"):
        # ตัดช่วงให้อยู่ในวันนั้น กันงาน batch ข้ามคืนทำให้เวลาบวมเกินจริง
        lo, hi = pd.Timestamp(d), pd.Timestamp(d) + pd.Timedelta(days=1)
        mins = merged_minutes(list(zip(dg["Start"].clip(lo, hi),
                                       dg["End"].clip(lo, hi))))
        net_total += mins
        net_by_day[d] = mins
        net_by_month[pd.Timestamp(d).to_period("M")] = (
            net_by_month.get(pd.Timestamp(d).to_period("M"), 0.0) + mins
        )

    days = g["Date"].nunique()
    last = g.loc[g["End"].idxmax()]
    out = {
        "net": net_total,
        "plan": days * PLAN_MINUTES_PER_DAY,
        "days": days,
        "d0": g["Date"].min(),
        "d1": g["Date"].max(),
        "net_by_month": net_by_month,
        "net_by_day": net_by_day,
        "qty": float(prod["Qty"].sum()),
        "jobs": int(prod["Job"].nunique()),
        # ข้อมูลกิจกรรมล่าสุด — ใช้บอกสถานะการทำงานล่าสุดของเครื่อง
        "last_end": last["End"],
        "last_start": last["Start"],
        "last_kind": last["ประเภทงาน"],
        "last_reason": last["สาเหตุ"],
        "last_name": last["Name"],
        "last_job": str(last["Job"]),
        "last_desc": str(last.get("Description", "") or ""),
        "last_prod_date": prod["Date"].max() if not prod.empty else None,
    }
    # แยกงานหยุดตามรหัส Job: P = เปลี่ยนอุปกรณ์ตามแผน, B = แจ้งซ่อม, BP = ช่างซ่อม
    for key, label in (("P", "P - หยุดตามแผน"), ("B", "B - แจ้งซ่อม (รอช่าง)"),
                       ("BP", "BP - ช่างเข้าซ่อม")):
        sub = g[g["ประเภทงาน"] == label]
        out[f"{key}_count"] = len(sub)
        out[f"{key}_min"] = float(sub["DurationMin"].sum())
        out[f"{key}_by_month"] = (
            sub.groupby(sub["Start"].dt.to_period("M")).size().to_dict()
        )
    # เวลาหยุดเครื่องจริงต่อเหตุการณ์ (แจ้งซ่อม → ซ่อมเสร็จ) — ตัวตั้งของ MTTR
    pairs = pair_repairs(g[g["ประเภทงาน"] == "B - แจ้งซ่อม (รอช่าง)"],
                         g[g["ประเภทงาน"] == "BP - ช่างเข้าซ่อม"])
    out["downtime_min"] = float(pairs["downtime_min"].sum()) if not pairs.empty else 0.0
    out["wait_min_avg"] = (float(pairs.loc[pairs["matched"], "wait_min"].mean())
                           if not pairs.empty and pairs["matched"].any() else None)
    p_rows = g[g["ประเภทงาน"] == "P - หยุดตามแผน"]
    out["p_reasons"] = (
        p_rows.groupby("สาเหตุ")["DurationMin"]
        .agg(["sum", "count"]).reset_index()
        .sort_values("sum", ascending=False)
        if not p_rows.empty else pd.DataFrame()
    )
    return out


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
def _load_or_warn(loader, label):
    """โหลดฐานเสริม — ถ้าอ่านพลาดชั่วคราว (ไฟล์ล็อก/กำลัง sync) ใช้ค่าว่างเฉพาะ
    รอบนี้ พร้อมเตือนที่ sidebar ให้รู้ตัว (จะลองอ่านใหม่เองในรอบถัดไป)"""
    try:
        return loader(folder_signature())
    except Exception:
        st.sidebar.warning(f"⚠️ อ่าน{label}ไม่ได้ชั่วคราว — "
                           "จะลองใหม่เมื่อรีเฟรช/ไฟล์ sync เสร็จ")
        return pd.DataFrame()


oee_runtime = _load_or_warn(load_oee_runtime, "ฐาน OEE")
registry = _load_or_warn(load_registry, "ทะเบียนเครื่องจักร")
repair = _load_or_warn(load_repair, "ฐานใบงานซ่อม")
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
            # entry แรกคือ ("logic", เวอร์ชันโค้ด) ไม่ใช่ไฟล์ — ข้าม
            for name, mt in files if isinstance(mt, (int, float))
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
(tab_live, tab_timeline, tab_down, tab_mtbf, tab_profile,
 tab_perf, tab_raw) = st.tabs(
    ["🟢 สถานะสด", "📅 Timeline", "⏱ การหยุดเครื่อง", "🔧 MTBF / MTTR",
     "🔍 โปรไฟล์เครื่องจักร", "📊 ผลงาน", "📋 ข้อมูลดิบ"]
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
    tl_end = day0 + pd.Timedelta(days=1)
    # ปกติเริ่มแสดงที่ 06:00 แต่ถ้าวันนั้นมีสแกนก่อนหน้านั้น ขยับกรอบตาม
    # เพื่อไม่ให้มีรายการหลุดออกจากกราฟแบบเงียบ ๆ
    _same_day = plot["Start"][(plot["Start"] >= day0) & (plot["Start"] < tl_end)]
    tl_start = min(day0 + pd.Timedelta(hours=6),
                   _same_day.min().floor("30min") if not _same_day.empty
                   else day0 + pd.Timedelta(hours=6))
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
        # width="container" ให้กราฟยืดเต็มความกว้างการ์ด — ถ้าไม่ใส่ กราฟแบบ layer
        # จะใช้ความกว้างมาตรฐานของ Vega แล้วเหลือช่องว่างค้างด้านซ้าย
        .properties(width="container",
                    height=max(320, 22 * plot["Machine"].nunique()))
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
    # ตัดช่วงก่อนกรอบเวลาแสดงผลทิ้ง — จุดที่อยู่นอก domain จะถูก Vega วาดล้น
    # ออกนอกแกนด้านซ้าย ทำให้กราฟดูเอียงทั้งการ์ด
    trend = trend[trend["slot"] >= tl_start]

    peak_line = (
        alt.Chart(trend)
        .mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=22),
                   interpolate="monotone", clip=True)
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
        alt.layer(bg_bands, shift_rules, peak_line)
        .resolve_scale(color="independent")
        .properties(width="container", height=300),
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

    # --- กราฟการยิงเริ่ม Job รายช่วงเวลา แยกตามประเภทงาน ---
    st.markdown("---")
    st.subheader("📊 การยิงเริ่ม Job รายช่วงเวลา (ทุกเครื่อง · วันที่เลือก)")

    # สีตามมาตรฐานฝ่าย: เขียว=ผลิต · เหลือง=P · แดงอ่อน=B · แดงเข้ม=BP
    JOB_KINDS = {
        "PROD - งานผลิต": ("งานผลิต", COLOR_WORK),
        "P - หยุดตามแผน": ("เปลี่ยนอุปกรณ์ P", COLOR_P),
        "B - แจ้งซ่อม (รอช่าง)": ("แจ้งเตือน B", COLOR_B),
        "BP - ช่างเข้าซ่อม": ("ช่างซ่อม BP", COLOR_BP),
    }
    starts = day_df.copy()
    starts["ประเภท"] = starts["ประเภทงาน"].map(lambda k: JOB_KINDS.get(k, (None,))[0])
    starts = starts[starts["ประเภท"].notna()]
    # จัดลงช่องเวลาละ 30 นาที ตามเวลาที่ "เริ่ม" ยิง Job
    starts = starts[(starts["Start"] >= tl_start) & (starts["Start"] < tl_end)]

    if starts.empty:
        st.caption("ไม่มีการยิง Job ในวันที่เลือก")
    else:
        starts["ช่อง"] = starts["Start"].dt.floor("30min")
        grid = pd.MultiIndex.from_product(
            [pd.date_range(tl_start, tl_end, freq="30min", inclusive="left"),
             [v[0] for v in JOB_KINDS.values()]],
            names=["ช่อง", "ประเภท"],
        )
        by_slot = (
            starts.groupby(["ช่อง", "ประเภท"]).size()
            .reindex(grid, fill_value=0).rename("job").reset_index()
        )
        totals = (
            by_slot.groupby("ช่อง")["job"].sum().reset_index()
            .rename(columns={"job": "รวมทุกหมวด"})
        )
        kind_names = [v[0] for v in JOB_KINDS.values()]
        kind_colors = [v[1] for v in JOB_KINDS.values()]

        base_j = alt.Chart(by_slot).encode(
            x=alt.X("ช่อง:T", title=None, axis=alt.Axis(format="%H:%M"),
                    scale=alt.Scale(domain=[tl_start, tl_end])))
        lines = base_j.mark_line(
            strokeWidth=2.5, interpolate="monotone", clip=True,
            point=alt.OverlayMarkDef(filled=True, size=45),
        ).encode(
            y=alt.Y("job:Q", title="จำนวน Job ที่เริ่มยิง"),
            color=alt.Color("ประเภท:N",
                            scale=alt.Scale(domain=kind_names, range=kind_colors),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("ช่อง:T", title="ช่วงเวลา", format="%H:%M"),
                     alt.Tooltip("ประเภท:N"),
                     alt.Tooltip("job:Q", title="จำนวน Job")],
        )
        total_line = (
            alt.Chart(totals)
            .mark_line(color="#9a9891", strokeWidth=1.5, strokeDash=[6, 4],
                       interpolate="monotone", clip=True)
            .encode(
                x=alt.X("ช่อง:T", scale=alt.Scale(domain=[tl_start, tl_end])),
                y=alt.Y("รวมทุกหมวด:Q"),
                tooltip=[alt.Tooltip("ช่อง:T", title="ช่วงเวลา", format="%H:%M"),
                         alt.Tooltip("รวมทุกหมวด:Q", title="รวมทุกหมวด")],
            )
        )
        st.altair_chart(
            alt.layer(bg_bands, shift_rules, total_line, lines)
            .resolve_scale(color="independent")
            .properties(width="container", height=340),
            width="stretch",
        )

        pk_row = totals.loc[totals["รวมทุกหมวด"].idxmax()]
        pk_t = pd.Timestamp(pk_row["ช่อง"])
        n_prod = int(by_slot[by_slot["ประเภท"] == "งานผลิต"]["job"].sum())
        n_shift = int(totals[(totals["ช่อง"] >= shift_start)
                             & (totals["ช่อง"] < shift_end)]["รวมทุกหมวด"].sum())
        n_ot = int(totals["รวมทุกหมวด"].sum()) - n_shift
        st.caption(
            f"รวมทั้งวัน **{int(totals['รวมทุกหมวด'].sum()):,} job** "
            f"(งานผลิต {n_prod:,}) · พีคช่วง "
            f"**{pk_t:%H:%M}–{pk_t + pd.Timedelta(minutes=30):%H:%M}** "
            f"({int(pk_row['รวมทุกหมวด']):,} job) · "
            f"ในกะ {n_shift:,} job · OT {n_ot:,} job · "
            "เส้นประเทา = รวมทุกหมวด · พื้นเขียว = กะปกติ พื้นส้ม = OT"
        )

# --- 3) การหยุดเครื่อง ---
with tab_down:
    down = day_df[day_df["IsDowntime"]]
    if down.empty:
        st.success("วันนี้ไม่มีบันทึกการหยุดเครื่อง 🎉")
    else:
        c1, c2 = st.columns(2)
        c1.metric("เหตุการณ์หยุดเครื่อง", f"{len(down)} ครั้ง", border=True)
        c2.metric("เวลาหยุดรวม", f"{down['DurationMin'].sum():,.0f} นาที", border=True)

        # เตรียมข้อมูลทั้งสองกราฟก่อน เพื่อคำนวณ "ความสูงร่วม" ให้การ์ดซ้าย-ขวาเท่ากัน
        pareto = (
            down.groupby("สาเหตุ")["DurationMin"].sum()
            .reset_index().sort_values("DurationMin", ascending=False)
        )
        _order_n = min(15, down["Machine"].nunique())
        # แถวของสองกราฟไม่เท่ากัน — ใช้ความสูงเดียวกัน แล้วให้แต่ละกราฟเกลี่ยแถบเอง
        shared_h = max(60 + 40 * len(pareto), 60 + 26 * _order_n, 320)

        col_l, col_r = st.columns(2)
        with col_l:
            with st.container(border=True):
                st.subheader("สาเหตุการหยุด (Pareto)")
                chart = (
                    alt.Chart(pareto)
                    .mark_bar(color="#d03b3b", cornerRadiusTopRight=4,
                              cornerRadiusBottomRight=4)
                    .encode(
                        y=alt.Y("สาเหตุ:N", sort="-x", title=None,
                                scale=alt.Scale(paddingInner=0.35)),
                        x=alt.X("DurationMin:Q", title="นาทีรวม"),
                        tooltip=[alt.Tooltip("สาเหตุ:N"),
                                 alt.Tooltip("DurationMin:Q", title="นาที", format=",.0f")],
                    )
                    .properties(height=shared_h)
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
                              cornerRadiusBottomRight=4)
                    .encode(
                        y=alt.Y("Machine:N", sort="-x", title=None,
                                scale=alt.Scale(paddingInner=0.35)),
                        x=alt.X("DurationMin:Q", title="นาทีรวม"),
                        tooltip=[alt.Tooltip("Machine:N"),
                                 alt.Tooltip("DurationMin:Q", title="นาที",
                                             format=",.0f")],
                    )
                    .properties(height=shared_h)
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
        repair_ev = ev[ev["ประเภท"].isin(["Breakdown", "Maintenance"])]
        bounds_src = repair_ev if not repair_ev.empty else ev
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

        # ---- เจาะจงเครื่อง (นอกเหนือจากตัวกรองกลุ่มที่แถบด้านซ้าย) ----
        mc_pool = sorted(set(ev["Machine"]) | (set(run["MC"]) if not run.empty else set()))
        sel_mcs = st.multiselect(
            "เจาะจงเครื่องจักร", mc_pool, default=[],
            placeholder="ทุกเครื่องในกลุ่มที่เลือก — เลือกได้หลายเครื่องเพื่อเทียบกัน",
            key="mtbf_machines",
            help="กรองเฉพาะเครื่องที่สนใจ ทุกตัวเลขและกราฟในแท็บนี้จะคิดใหม่ตามที่เลือก",
        )
        if sel_mcs:
            ev = ev[ev["Machine"].isin(sel_mcs)]
            if not run.empty:
                run = run[run["MC"].isin(sel_mcs)]
            scope = (f"เฉพาะเครื่อง **{', '.join(sel_mcs)}**" if len(sel_mcs) <= 4
                     else f"เฉพาะ **{len(sel_mcs)} เครื่อง** ที่เลือก")
        else:
            scope = (f"ทุกเครื่องในกลุ่ม **{', '.join(sel_groups)}**" if sel_groups
                     else f"ทุกเครื่อง (**{len(mc_pool)}** เครื่อง)")
        st.caption(f"🎯 ขอบเขตที่กำลังดู: {scope}")

        bd = ev[ev["ประเภท"] == "Breakdown"]
        mt = ev[ev["ประเภท"] == "Maintenance"]
        n_bd = len(bd)
        bd_min = bd["DurationMin"].sum()
        runtime_min = run["เวลาทำงานจริง/วัน"].sum() if not run.empty else 0.0

        # จับคู่ B→BP ครั้งเดียว แล้วใช้ผลร่วมกันทั้งแท็บ
        pr = pair_repairs(bd, mt)
        downtime_total = pr["downtime_min"].sum() if not pr.empty else 0.0
        # MTTR ตามนิยามมาตรฐาน = เวลาที่เครื่องหยุดผลิตจริง (แจ้ง → ซ่อมเสร็จ) ÷ ครั้งที่เสีย
        fleet_mttr = downtime_total / n_bd if n_bd else 0.0
        # MTBF = เวลาเดินเครื่องจริง ÷ ครั้งที่เสีย
        # (เวลาทำงานจริงจากฐาน OEE หักเวลาสูญเสียออกแล้ว จึงเป็น uptime ล้วน)
        fleet_mtbf = runtime_min / 60 / n_bd if n_bd and runtime_min else None

        net_op_h = runtime_min / 60
        down_h = downtime_total / 60
        # ป้ายเปลี่ยนตามขอบเขตที่กรอง — เลือกเครื่องเดียวแล้วยังเขียน "ทั้งฝ่าย" จะเข้าใจผิด
        if sel_mcs:
            suffix = f" — {sel_mcs[0]}" if len(sel_mcs) == 1 else f" — {len(sel_mcs)} เครื่อง"
        elif sel_groups:
            suffix = f" — กลุ่ม{sel_groups[0]}" if len(sel_groups) == 1 else " — กลุ่มที่เลือก"
        else:
            suffix = " เฉลี่ยทั้งฝ่าย"
        with st.container(horizontal=True):
            st.metric("⚙️ Net Operation Time", f"{net_op_h:,.1f} ชม.", border=True,
                      help="เวลาเดินเครื่องจริงรวมของทุกเครื่องในช่วงที่เลือก "
                           "(ฐาน OEE — หักเวลาสูญเสียออกแล้ว) · เป็นตัวตั้งของ MTBF")
            st.metric("🔴 แจ้งซ่อม (B)", f"{n_bd} ครั้ง", border=True,
                      help="Job B000000001 — ผู้คุมเครื่องแจ้งเครื่องเสีย = จำนวนครั้งที่เสีย")
            st.metric("🔧 ช่างเข้าซ่อม (BP)", f"{len(mt)} ครั้ง", border=True,
                      help="Job BP00000001 — ช่างเข้าซ่อมจริง")
            st.metric(
                f"MTBF{suffix}",
                f"{fleet_mtbf:,.1f} ชม." if fleet_mtbf else "—",
                border=True,
                help="Net Operation Time ÷ จำนวนครั้งที่เสีย · ยิ่งสูงยิ่งดี",
            )
            st.metric(f"MTTR{suffix}", f"{fleet_mttr:,.1f} นาที/ครั้ง", border=True,
                      help="เวลาหยุดเครื่องรวม (แจ้งซ่อม B เริ่ม → ช่างซ่อมเสร็จ BP จบ) "
                           "÷ จำนวนครั้งที่เสีย · ยิ่งต่ำยิ่งดี")
            st.metric("⛔ เวลาหยุดเครื่องรวม", f"{down_h:,.1f} ชม.", border=True,
                      help="ผลรวมเวลาที่เครื่องหยุดผลิตเพราะเสีย (Downtime)")
            st.metric("Availability",
                      f"{net_op_h / (net_op_h + down_h) * 100:,.1f}%"
                      if net_op_h else "—", border=True,
                      help="Net Operation Time ÷ (Net Operation Time + Downtime)")
        if fleet_mtbf:
            mttr_h = fleet_mttr / 60
            st.caption(
                f"📐 **MTBF** = Net Operation Time {net_op_h:,.1f} ชม. ÷ {n_bd} ครั้งที่เสีย "
                f"= **{fleet_mtbf:,.1f} ชม./ครั้ง**  ·  "
                f"**MTTR** = เวลาหยุดเครื่อง {down_h:,.1f} ชม. ({downtime_total:,.0f} นาที) "
                f"÷ {n_bd} ครั้งที่เสีย = **{fleet_mttr:,.1f} นาที/ครั้ง**  ·  "
                f"**Availability** = MTBF ÷ (MTBF + MTTR) = {fleet_mtbf:,.1f} ÷ "
                f"({fleet_mtbf:,.1f} + {mttr_h:,.2f}) = "
                f"**{fleet_mtbf / (fleet_mtbf + mttr_h) * 100:,.1f}%**"
            )

        # ---- เชื่อมโยงเหตุการณ์ แจ้งซ่อม (B) → ช่างเข้าซ่อม (BP) ----
        # จับคู่: BP ครั้งแรกของเครื่องเดียวกันที่เริ่มหลังการแจ้ง (ภายใน 8 ชม.หลังจบ B)
        st.markdown("---")
        st.subheader("🔗 เชื่อมโยง แจ้งซ่อม (B) → ช่างเข้าซ่อม (BP)")
        if pr.empty:
            st.info("ไม่มีเหตุการณ์แจ้งซ่อม (B) ในช่วงที่เลือก")
        else:
            matched = pr[pr["matched"]]
            with st.container(horizontal=True):
                st.metric("จับคู่ B→BP ได้", f"{len(matched)} / {len(pr)} ครั้ง",
                          border=True)
                if not matched.empty:
                    st.metric("⏳ รอช่างเฉลี่ย",
                              f"{matched['wait_min'].mean():,.1f} นาที", border=True,
                              help="แจ้งซ่อม (B เริ่ม) → ช่างเริ่มซ่อม (BP เริ่ม)")
                    st.metric("🔧 ช่างซ่อมเฉลี่ย",
                              f"{matched['repair_min'].mean():,.1f} นาที", border=True,
                              help="ระยะเวลางาน BP ต่อครั้ง")
                st.metric("⛔ หยุดเครื่องเฉลี่ย (= MTTR)",
                          f"{pr['downtime_min'].mean():,.1f} นาที", border=True,
                          help="แจ้งซ่อม (B เริ่ม) → ซ่อมเสร็จ (BP จบ) — "
                               "ค่านี้คือ MTTR ที่ใช้ทั้งระบบ")
            show_pairs = pd.DataFrame({
                "วันที่": pr["b_start"].dt.strftime("%d/%m/%Y"),
                "เครื่อง": pr["Machine"],
                "สาเหตุ (จากการแจ้ง)": pr["Reason"].astype(str),
                "แจ้งซ่อม": pr["b_start"].dt.strftime("%H:%M"),
                "ช่างเริ่มซ่อม": pr["bp_start"].dt.strftime("%H:%M").fillna("—"),
                "ซ่อมเสร็จ": pr["bp_end"].dt.strftime("%H:%M").fillna("—"),
                "รอช่าง (นาที)": pr["wait_min"].round(1),
                "ช่างซ่อม (นาที)": pr["repair_min"].round(1),
                "หยุดเครื่อง (นาที)": pr["downtime_min"].round(1),
                "จับคู่": pr["matched"].map({True: "✅", False: "⚠️ ไม่พบ BP"}),
                "_sort": pr["b_start"],
            })
            st.dataframe(
                show_pairs.sort_values("_sort", ascending=False).drop(columns="_sort"),
                width="stretch", hide_index=True, height=360,
            )
            st.caption(
                f"จับคู่จากชีต Breakdown_B000000001 กับ Maintenance_BP00000001: "
                f"เครื่องเดียวกัน และ BP เริ่มภายใน {PAIR_WINDOW_HOURS} ชม. หลังใบแจ้งปิด · "
                "⚠️ ไม่พบ BP = แจ้งเสียแล้วไม่มีบันทึกช่างเข้าซ่อม "
                "(ใช้ระยะเวลาใบแจ้งเป็นเวลาหยุดแทน ซึ่งอาจต่ำกว่าจริง)"
            )

        # ตารางรายเครื่อง
        rows = []
        run_by_mc = run.groupby("MC")["เวลาทำงานจริง/วัน"].sum() if not run.empty else pd.Series(dtype=float)
        machines_in_scope = sorted(set(ev["Machine"]) | set(run_by_mc.index))
        down_by_mc = pr.groupby("Machine")["downtime_min"].sum() if not pr.empty \
            else pd.Series(dtype=float)
        for mc in machines_in_scope:
            b = bd[bd["Machine"] == mc]
            m = mt[mt["Machine"] == mc]
            rt_min = float(run_by_mc.get(mc, 0.0))
            dt_min = float(down_by_mc.get(mc, 0.0))
            n = len(b)
            rows.append({
                "เครื่อง": mc,
                "หมวดหมู่": cat_map.get(mc, "—"),
                "Breakdown (ครั้ง)": n,
                "เวลาหยุดเครื่อง (ชั่วโมง)": round(dt_min / 60, 2),
                # MTTR = เวลาหยุดจริง (แจ้ง → ซ่อมเสร็จ) ÷ ครั้งที่เสีย
                "MTTR (นาที/ครั้ง)": round(dt_min / n, 1) if n else None,
                "เวลาทำงานจริง (ชั่วโมง)": round(rt_min / 60, 1),
                "MTBF (ชั่วโมง)": round(rt_min / 60 / n, 1) if n and rt_min else None,
                "Availability (%)": round(rt_min / (rt_min + dt_min) * 100, 1)
                                    if rt_min else None,
                "Maintenance (ครั้ง)": len(m),
            })
        mtbf_table = pd.DataFrame(rows)

        col_l, col_r = st.columns(2)
        with col_l:
            with st.container(border=True):
                st.subheader("MTBF ต่ำสุด (เสียบ่อยเทียบเวลาเดินเครื่อง)")
                worst = (
                    mtbf_table.dropna(subset=["MTBF (ชั่วโมง)"])
                    .sort_values("MTBF (ชั่วโมง)").head(15)
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
                            x=alt.X("MTBF (ชั่วโมง):Q", title="MTBF (ชั่วโมงทำงานจริง/ครั้ง)"),
                            tooltip=[alt.Tooltip("เครื่อง:N"),
                                     alt.Tooltip("MTBF (ชั่วโมง):Q", format=",.1f"),
                                     alt.Tooltip("Breakdown (ครั้ง):Q"),
                                     alt.Tooltip("เวลาทำงานจริง (ชั่วโมง):Q", format=",.1f")],
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
                        .mark_bar(color=COLOR_BP, cornerRadiusTopRight=4,
                                  cornerRadiusBottomRight=4, size=18)
                        .encode(
                            y=alt.Y("เครื่อง:N", sort="-x", title=None),
                            x=alt.X("MTTR (นาที/ครั้ง):Q", title="MTTR (นาที/ครั้ง)"),
                            tooltip=[alt.Tooltip("เครื่อง:N"),
                                     alt.Tooltip("MTTR (นาที/ครั้ง):Q", format=",.1f"),
                                     alt.Tooltip("Breakdown (ครั้ง):Q"),
                                     alt.Tooltip("เวลาหยุดเครื่อง (ชั่วโมง):Q", format=",.2f")],
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
            # % เปลี่ยนแปลงเทียบเดือนก่อน (MoM) ของแต่ละประเภท
            pv_mo = (monthly.pivot_table(index="Month", columns="ประเภท",
                                         values="ชั่วโมง", aggfunc="sum")
                     .sort_index().fillna(0))
            mom_pct = pv_mo.pct_change() * 100
            # เก็บเป็นสัดส่วน (หาร 100) เพื่อให้ d3 format "+.0%" เติมเครื่องหมาย % ให้เอง
            monthly = monthly.merge(
                (mom_pct / 100).stack().rename("เทียบเดือนก่อน (%)").reset_index(),
                on=["Month", "ประเภท"], how="left",
            )
            type_colors = {"Breakdown": COLOR_B, "Maintenance": COLOR_BP,
                           "Planned stop": COLOR_P}
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
                             alt.Tooltip("ชั่วโมง:Q", format=",.1f"),
                             alt.Tooltip("เทียบเดือนก่อน (%):Q", title="เทียบเดือนก่อน",
                                         format="+.0%")],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")

            # ---- การ์ดสรุปเดือนล่าสุด เทียบเดือนก่อน แยกประเภท ----
            if len(pv_mo) >= 2:
                cur_m, prev_m = pv_mo.index[-1], pv_mo.index[-2]
                order_types = [t for t in ("Planned stop", "Maintenance", "Breakdown")
                               if t in pv_mo.columns]
                mcols = st.columns(len(order_types))
                for c_st, typ in zip(mcols, order_types):
                    cur, prev = pv_mo.loc[cur_m, typ], pv_mo.loc[prev_m, typ]
                    if prev > 0:
                        d_txt = f"{(cur - prev) / prev * 100:+.0f}% เทียบเดือนก่อน"
                    elif cur > 0:
                        d_txt = f"+{cur:,.0f} ชม. (เดือนก่อนเป็น 0)"
                    else:
                        d_txt = "0 ทั้งสองเดือน"
                    # delta_color inverse: เวลาหยุด "เพิ่ม" = แย่ (แดง), "ลด" = ดี (เขียว)
                    c_st.metric(f"{typ} — {cur_m:%m/%Y}", f"{cur:,.0f} ชม.",
                                delta=d_txt, delta_color="inverse", border=True)
                st.caption(
                    f"⚠️ เดือน {cur_m:%m/%Y} อาจยังเก็บข้อมูลไม่ครบเดือน — "
                    f"% ที่ลดลงมากอาจมาจากจำนวนวันที่ยังน้อย ไม่ใช่ผลงานจริง"
                )
                with st.expander("📋 ตารางรายเดือนทุกประเภท + % เทียบเดือนก่อน"):
                    tbl = pd.DataFrame(index=pv_mo.index)
                    for typ in order_types:
                        tbl[typ + " (ชม.)"] = [
                            f"{v:,.0f}" + (f"  ({d:+.0f}%)" if pd.notna(d) and abs(d) != float("inf") else "")
                            for v, d in zip(pv_mo[typ], mom_pct[typ])
                        ]
                    tbl.index = tbl.index.strftime("%m/%Y")
                    tbl.index.name = "เดือน"
                    st.dataframe(tbl, width="stretch")

        st.subheader("ตาราง MTBF / MTTR รายเครื่อง")
        st.dataframe(
            mtbf_table.sort_values("เวลาหยุดเครื่อง (ชั่วโมง)", ascending=False),
            width="stretch", hide_index=True,
        )
        st.caption(
            "**MTBF** = เวลาทำงานจริงรวม (ฐาน OEE — หักเวลาสูญเสียแล้ว) ÷ จำนวนครั้งที่เสีย · "
            "**MTTR** = เวลาหยุดเครื่องรวม (แจ้งซ่อม B เริ่ม → ช่างซ่อมเสร็จ BP จบ) ÷ จำนวนครั้งที่เสีย · "
            "**Availability** = เวลาทำงานจริง ÷ (เวลาทำงานจริง + เวลาหยุดเพราะเสีย) · "
            "เครื่องที่ไม่มี Breakdown ในช่วงที่เลือก แสดงเป็นค่าว่าง"
        )

# --- 5) โปรไฟล์เครื่องจักร — รวมทุกฐานข้อมูลของเครื่องเดียวไว้หน้าเดียว ---
with tab_profile:
    prof_machines = sorted(set(data["Machine"]) | set(registry.index)
                           if not registry.empty else set(data["Machine"]))
    if sel_groups:
        prof_machines = [m for m in prof_machines
                         if (cat_map.get(m) in sel_groups
                             or m in set(day_df["Machine"]))]

    # ---------- ส่วนหัว: เลือกเครื่อง + ชื่อเครื่อง + ป้ายสถานะ ----------
    c_sel, c_info = st.columns([1, 3], vertical_alignment="center")
    with c_sel:
        default_idx = prof_machines.index("CT-51") if "CT-51" in prof_machines else 0
        mc = st.selectbox("เลือกเครื่องจักร", prof_machines, index=default_idx,
                          key="profile_machine")

    reg = registry.loc[mc] if (not registry.empty and mc in registry.index) else None
    prof = machine_runtime_profile(folder_signature(), mc)
    rep = repair[repair["รหัสเครื่อง"] == mc] if not repair.empty else pd.DataFrame()

    def _reg(field, default="—"):
        """อ่านค่าจากทะเบียนเครื่อง — คืน default ถ้าว่าง, จัดรูปแบบวันที่ให้เอง"""
        if reg is None:
            return default
        v = reg.get(field)
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return default
        if isinstance(v, pd.Timestamp):
            return f"{v:%d/%m/%Y}"
        return str(v).strip()

    grp = cat_map.get(mc) or (
        data[data["Machine"] == mc]["Group"].iloc[0]
        if mc in set(data["Machine"]) else "—")
    with c_info:
        st.markdown(f"### {mc} — {_reg('ชื่อเครื่องจักร')}")
        status_val = _reg("สถานะ", "ไม่มีในทะเบียน")
        status_badge = (f":green-badge[:material/check_circle: {status_val}]"
                        if status_val == "ปกติ"
                        else f":orange-badge[:material/warning: {status_val}]")
        st.markdown(
            f"{status_badge} "
            f":blue-badge[:material/category: {grp}] "
            f":gray-badge[:material/location_on: {_reg('สถานที่ติดตั้ง')}] "
            f":violet-badge[:material/build: PM {_reg('ความถี่ PM', 'ไม่ระบุรอบ')}]"
        )

    if not prof:
        st.warning(
            f"เครื่อง {mc} ยังไม่มีบันทึกการสแกนในฐาน Workcenter — "
            "แสดงเฉพาะข้อมูลทะเบียนและประวัติซ่อม",
            icon=":material/info:",
        )

    # ---------- แถบตัวเลขสรุป (KPI strip) ----------
    age = reg.get("อายุ (ปี)") if reg is not None else None
    bC = prof.get("B_count", 0)
    bpC = prof.get("BP_count", 0)
    net_h = prof.get("net", 0) / 60
    plan_h = prof.get("plan", 0) / 60
    pct_plan = net_h / plan_h * 100 if plan_h else 0
    mtbf = net_h / bC if bC else None
    # MTTR = เวลาหยุดเครื่องจริง (แจ้งซ่อม → ซ่อมเสร็จ) ÷ จำนวนครั้งที่เสีย
    # ใช้นิยามเดียวกับแท็บ MTBF/MTTR
    down_h = prof.get("downtime_min", 0) / 60
    mttr = prof.get("downtime_min", 0) / bC if bC else None
    availability = net_h / (net_h + down_h) * 100 if net_h else None
    cost_total = rep["ค่าใช้จ่ายรวม"].sum() if not rep.empty else 0

    # ช่วงเวลาข้อมูลที่ใช้คำนวณ — แนบไว้กับทุกตัวเลขให้คนอ่านรู้ว่าตัวเลขครอบคลุมถึงไหน
    period_txt = (f"{prof['d0']:%d/%m/%Y} – {prof['d1']:%d/%m/%Y} "
                  f"({prof['days']} วันบันทึก)") if prof else "ยังไม่มีข้อมูลสแกน"

    with st.container(horizontal=True):
        st.metric("อายุการใช้งาน",
                  f"{age:.1f} ปี" if age is not None and pd.notna(age) else "—",
                  border=True,
                  help=f"ติดตั้ง {_reg('วันที่ติดตั้ง')} นับถึงวันนี้")
        st.metric("MTBF", f"{mtbf:,.0f} ชม." if mtbf else "—", border=True,
                  help=f"ช่วงข้อมูล {period_txt} · "
                       "ชม.เดินเครื่องจริงสะสม ÷ จำนวนครั้งที่เสีย (Job B) — ยิ่งสูงยิ่งดี")
        st.metric("MTTR", f"{mttr:,.0f} นาที" if mttr else "—", border=True,
                  help=f"ช่วงข้อมูล {period_txt} · "
                       "เวลาหยุดเครื่องรวม (แจ้งซ่อม B เริ่ม → ช่างซ่อมเสร็จ BP จบ) "
                       "÷ จำนวนครั้งที่เสีย — ยิ่งต่ำยิ่งดี")
        st.metric("Availability",
                  f"{availability:,.1f}%" if availability else "—", border=True,
                  help=f"ช่วงข้อมูล {period_txt} · "
                       "เวลาเดินเครื่องจริง ÷ (เวลาเดินเครื่องจริง + เวลาหยุดเพราะเสีย)")
        st.metric("ชม.เดินเครื่องสะสม", f"{net_h:,.0f}" if prof else "—",
                  border=True,
                  help=f"ช่วงข้อมูล {period_txt} · "
                       f"{pct_plan:.0f}% ของเวลากะปกติ {plan_h:,.0f} ชม. "
                       f"({PLAN_MINUTES_PER_DAY / 60:.0f} ชม./วัน × "
                       f"{prof.get('days', 0)} วันบันทึก) — เกิน 100% = มีเดินช่วง OT")
        st.metric("ผลผลิตสะสม",
                  f"{prof['qty']:,.0f} ชิ้น" if prof else "—", border=True,
                  help=f"ช่วงข้อมูล {period_txt} · {prof.get('jobs', 0):,} Job"
                  if prof else None)
        # ราคาทุนตามบัญชีจากทะเบียนเครื่องจักร — ใช้เทียบกับค่าซ่อมสะสม
        asset_cost = None
        if reg is not None:
            _v = pd.to_numeric(reg.get("ราคาทุนตามบัญชี (บาท)"), errors="coerce")
            if pd.notna(_v) and _v > 0:
                asset_cost = float(_v)
        repair_ratio = (cost_total / asset_cost * 100
                        if asset_cost and cost_total else None)
        st.metric("ค่าซ่อมเครื่องสะสม 2020–26",
                  f"฿{cost_total:,.0f}" if not rep.empty else "—", border=True,
                  help=(f"{len(rep):,} ใบงานซ่อม · เฉพาะงานซ่อมเครื่องจักร "
                        "(ไม่รวมหมวดซ่อมสร้าง เช่น ทำรั้ว/โครงสร้างรอบเครื่อง — "
                        "หน้า Dashboard ซ่อมบำรุง 6 หมวดรวมทุกหมวด ตัวเลขจึงต่างกันได้)"
                        + (f" · คิดเป็น {repair_ratio:.1f}% ของราคาเครื่อง"
                           if repair_ratio is not None else ""))
                  if not rep.empty else None)
        st.metric("มูลค่าเครื่อง (บัญชี)",
                  f"฿{asset_cost:,.0f}" if asset_cost else "—", border=True,
                  help="ราคาทุนตามบัญชี จากทะเบียนเครื่องจักร"
                       + (f" · ASSET {_reg('เลขทรัพย์สินบัญชี (ASSET CODE)')}"
                          if reg is not None else ""))

    rep_period = ""
    if not rep.empty:
        _y = rep["ปี"].astype(int)
        rep_period = f" · ค่าซ่อม: ปี {_y.min()}–{_y.max()} ({len(rep):,} ใบงาน)"
    st.caption(
        f"📅 **ช่วงข้อมูลที่ใช้คำนวณ** — MTBF / MTTR / Availability / "
        f"ชม.เดินเครื่อง / ผลผลิต: **{period_txt}** (ฐาน Workcenter)"
        f"{rep_period} · อายุ/มูลค่าเครื่อง: ทะเบียนเครื่องจักร ณ ปัจจุบัน"
    )

    # ---------- สถานะการทำงานล่าสุด ----------
    if prof:
        st.subheader("สถานะการทำงานล่าสุด", divider="green")
        data_latest = max(dates)          # วันล่าสุดที่ทั้งฐานมีข้อมูล
        last_end = prof["last_end"]
        last_prod = prof["last_prod_date"]
        gap_days = (data_latest - prof["d1"]).days
        prod_gap = (data_latest - last_prod).days if last_prod else None

        # เหตุการณ์ซ่อมที่ยังไม่ปิด ณ เวลาสแกนสุดท้ายของเครื่อง = ยังหยุดอยู่
        mc_rows = data[data["Machine"] == mc]
        open_repair = mc_rows[
            (mc_rows["ประเภทงาน"].isin(["B - แจ้งซ่อม (รอช่าง)",
                                        "BP - ช่างเข้าซ่อม"]))
            & (mc_rows["Start"] <= last_end) & (mc_rows["End"] >= last_end)
        ]

        if not open_repair.empty:
            st_txt, st_color, st_icon = "หยุดเครื่อง (อยู่ระหว่างซ่อม)", STATUS_COLORS[STATUS_DOWN], "🔴"
            st_note = str(open_repair.iloc[-1]["สาเหตุ"])
        elif gap_days == 0:
            st_txt, st_color, st_icon = "เดินเครื่องวันล่าสุด", STATUS_COLORS[STATUS_RUN], "🟢"
            st_note = f"มีการสแกนในวันที่ {prof['d1']:%d/%m/%Y} ซึ่งเป็นวันล่าสุดของฐานข้อมูล"
        elif gap_days <= 3:
            st_txt, st_color, st_icon = f"เงียบมา {gap_days} วัน", STATUS_COLORS[STATUS_IDLE], "🟡"
            st_note = "ยังอยู่ในช่วงปกติ (วันหยุด/รอคิวงาน)"
        else:
            st_txt, st_color, st_icon = f"ไม่ได้เดินเครื่องมา {gap_days} วัน", STATUS_COLORS[STATUS_NODATA], "⚪"
            st_note = "ควรตรวจสอบว่าเครื่องหยุดใช้งาน ย้ายไลน์ หรือรอซ่อม"

        col_s, col_t = st.columns([1, 2])
        with col_s:
            # height="stretch" ใช้ได้เฉพาะแถวที่มีข้อความ/ตัวเลขเป็นหลักยึด —
            # แถวที่มีแต่กราฟ (โหลดทีหลัง) จะทำให้ทั้งแถวหดจนกราฟหาย
            with st.container(border=True, height="stretch"):
                st.markdown(
                    f"<div style='border-left:6px solid {st_color};"
                    f"background:linear-gradient(135deg,{st_color}20 0%,{st_color}06 100%);"
                    f"border-radius:10px;padding:14px 16px;'>"
                    f"<div style='font-size:1.25rem;font-weight:800;'>{st_icon} {st_txt}</div>"
                    f"<div style='font-size:0.82rem;color:#8a8a8a;margin-top:4px;'>{st_note}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"**กิจกรรมล่าสุด** {last_end:%d/%m/%Y %H:%M} · "
                    f"{prof['last_kind']}"
                    + (f" · {prof['last_reason']}"
                       if prof["last_kind"] != "PROD - งานผลิต" else "")
                )
                st.caption(
                    f"👤 {prof['last_name']} · Job {prof['last_job']}"
                    + (f" · {prof['last_desc'][:38]}" if prof["last_desc"] else "")
                )
                if prod_gap is not None:
                    st.caption(
                        f"🏭 งานผลิตล่าสุด {last_prod:%d/%m/%Y}"
                        + (" (วันล่าสุดของฐาน)" if prod_gap == 0
                           else f" — {prod_gap} วันก่อน")
                    )
                st.caption(f"ฐานข้อมูลล่าสุดถึงวันที่ {data_latest:%d/%m/%Y}")

        with col_t:
            with st.container(border=True, height="stretch"):
                st.markdown("**📅 ชั่วโมงเดินเครื่องรายวัน — 30 วันล่าสุด**")
                span = pd.date_range(pd.Timestamp(data_latest) - pd.Timedelta(days=29),
                                     pd.Timestamp(data_latest), freq="D")
                daily = pd.DataFrame({
                    "วันที่": span,
                    "ชั่วโมง": [prof["net_by_day"].get(d.date(), 0.0) / 60
                                for d in span],
                })
                daily["สถานะ"] = daily["ชั่วโมง"].map(
                    lambda v: "เดินเครื่อง" if v > 0 else "ไม่มีงาน")
                chart = (
                    alt.Chart(daily)
                    .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=14)
                    .encode(
                        x=alt.X("วันที่:T", title=None,
                                axis=alt.Axis(format="%d/%m", labelAngle=-45)),
                        y=alt.Y("ชั่วโมง:Q", title="ชม./วัน"),
                        color=alt.Color(
                            "สถานะ:N",
                            scale=alt.Scale(domain=["เดินเครื่อง", "ไม่มีงาน"],
                                            range=[COLOR_WORK, "#3a3a3a"]),
                            legend=None),
                        tooltip=[alt.Tooltip("วันที่:T", format="%d/%m/%Y"),
                                 alt.Tooltip("ชั่วโมง:Q", format=",.1f"),
                                 alt.Tooltip("สถานะ:N")],
                    )
                    .properties(width="container", height=190)
                )
                st.altair_chart(chart, width="stretch")
                run_days = int((daily["ชั่วโมง"] > 0).sum())
                tot_h = daily["ชั่วโมง"].sum()

                def fmt_dur(v_hours: float) -> str:
                    """เลือกหน่วยตามขนาดค่า — บางเครื่องสแกนแค่ไม่กี่วินาที
                    ถ้าบังคับเป็น 'ชม.' จะขึ้น 0 ทั้งที่มีงานจริง"""
                    mins = v_hours * 60
                    if mins < 1:
                        return f"{mins * 60:,.0f} วินาที"
                    if v_hours < 1:
                        return f"{mins:,.0f} นาที"
                    return f"{v_hours:,.0f} ชม."

                st.caption(
                    f"เดินเครื่อง **{run_days}/30 วัน** · รวม {fmt_dur(tot_h)} · "
                    "เฉลี่ยเฉพาะวันที่เดิน "
                    + (fmt_dur(tot_h / run_days) if run_days else "—") + "/วัน"
                )

    # ---------- ส่วนที่ 1: การใช้งานเครื่อง (ฐาน Workcenter) ----------
    if prof:
        st.subheader("การใช้งานเครื่อง", divider="blue")
        st.caption(
            f"จากฐาน Workcenter · {prof['d0']:%d/%m/%Y} → {prof['d1']:%d/%m/%Y} "
            f"({prof['days']} วันบันทึก)"
        )
        col_d, col_e, col_f = st.columns(3)

        with col_d:
            # ใบนี้เตี้ยสุดของแถว — ให้ยืดตามสองใบข้างๆ ที่สูงตามเนื้อหา (เป็นหลักยึด)
            # ห้ามใส่ stretch ทั้งแถว: กราฟโหลดช้ากว่า layout จะทำให้ทั้งแถวหดจนกราฟหาย
            with st.container(border=True, height="stretch"):
                st.markdown("**⏳ สัดส่วนเวลา: เดินจริง vs P / B / BP**")
                parts = pd.DataFrame([
                    {"ประเภท": f"เดินเครื่องจริง ({prof['net'] / 60:,.0f} ชม.)",
                     "นาที": prof["net"], "สี": COLOR_WORK},
                    {"ประเภท": f"เปลี่ยนอุปกรณ์ P ({prof['P_min'] / 60:,.1f} ชม. · "
                               f"{prof['P_count']} ครั้ง)",
                     "นาที": prof["P_min"], "สี": COLOR_P},
                    {"ประเภท": f"แจ้งซ่อม B ({prof['B_min'] / 60:,.1f} ชม. · "
                               f"{prof['B_count']} ครั้ง)",
                     "นาที": prof["B_min"], "สี": COLOR_B},
                    {"ประเภท": f"ช่างซ่อม BP ({prof['BP_min'] / 60:,.1f} ชม. · "
                               f"{prof['BP_count']} ครั้ง)",
                     "นาที": prof["BP_min"], "สี": COLOR_BP},
                ])
                parts = parts[parts["นาที"] > 0]
                total = parts["นาที"].sum()
                parts["สัดส่วน"] = parts["นาที"] / total * 100 if total else 0
                donut = (
                    alt.Chart(parts)
                    .mark_arc(innerRadius=55, stroke="#fff", strokeWidth=2)
                    .encode(
                        theta=alt.Theta("นาที:Q", stack=True),
                        color=alt.Color("ประเภท:N",
                                        scale=alt.Scale(domain=parts["ประเภท"].tolist(),
                                                        range=parts["สี"].tolist()),
                                        legend=alt.Legend(orient="bottom", columns=1,
                                                          title=None)),
                        tooltip=[alt.Tooltip("ประเภท:N"),
                                 alt.Tooltip("นาที:Q", format=",.0f"),
                                 alt.Tooltip("สัดส่วน:Q", title="สัดส่วน (%)",
                                             format=".1f")],
                    )
                    # 240 + legend ล่าง ~4 บรรทัด ≈ ความสูงกราฟ 300 ของสองการ์ดข้างๆ
                    .properties(height=240)
                )
                st.altair_chart(donut, width="stretch")

        with col_e:
            with st.container(border=True):
                st.markdown("**🔧 งาน P (เปลี่ยนอุปกรณ์/งาน operator) ทำอะไรบ้าง**")
                pr = prof.get("p_reasons")
                if pr is None or pr.empty:
                    st.info("เครื่องนี้ไม่มีงาน P ในช่วงข้อมูล")
                else:
                    pr = pr.copy()
                    # ห้ามตั้งชื่อคอลัมน์มี "." — Vega-Lite ตีความเป็น nested field
                    # แล้วกราฟจะว่างเปล่าโดยไม่มี error
                    pr.columns = ["สาเหตุ", "นาที", "ครั้ง"]
                    pr["ชั่วโมง"] = pr["นาที"] / 60
                    pr["สัดส่วน"] = pr["นาที"] / pr["นาที"].sum() * 100
                    bar = (
                        alt.Chart(pr)
                        .mark_bar(color=COLOR_P, cornerRadiusTopRight=4,
                                  cornerRadiusBottomRight=4, size=22)
                        .encode(
                            y=alt.Y("สาเหตุ:N", sort="-x", title=None),
                            x=alt.X("ชั่วโมง:Q", title="ชั่วโมงรวม"),
                            tooltip=[alt.Tooltip("สาเหตุ:N"),
                                     alt.Tooltip("ชั่วโมง:Q", format=",.1f"),
                                     alt.Tooltip("ครั้ง:Q"),
                                     alt.Tooltip("สัดส่วน:Q", format=".0f")],
                        )
                        # สูง 300 เท่ากับโดนัทและกราฟรายเดือนข้างๆ ให้ทั้งแถวเสมอกัน
                        .properties(height=300)
                    )
                    st.altair_chart(bar, width="stretch")
                    st.caption(
                        f"รวมงาน P: {pr['ชั่วโมง'].sum():,.1f} ชม. · "
                        f"{int(pr['ครั้ง'].sum()):,} ครั้ง"
                    )

        with col_f:
            with st.container(border=True):
                st.markdown("**📈 แนวโน้มรายเดือน: ชม.เดินเครื่องสะสม + แจ้งซ่อม**")
                months = sorted(set(prof["net_by_month"]) | set(prof["B_by_month"]))
                # ชื่อคอลัมน์ต้องไม่มี "." — Vega-Lite ตีความเป็น nested field แล้วแท่งหาย
                mo = pd.DataFrame([
                    {"เดือน": m.to_timestamp(),
                     "ชั่วโมงเดือนนี้": prof["net_by_month"].get(m, 0) / 60,
                     "แจ้งซ่อม (ครั้ง)": prof["B_by_month"].get(m, 0)}
                    for m in months
                ])
                mo["ชั่วโมงสะสม"] = mo["ชั่วโมงเดือนนี้"].cumsum()

                base_c = alt.Chart(mo).encode(
                    x=alt.X("yearmonth(เดือน):T", title=None,
                            axis=alt.Axis(format="%b %y", labelAngle=0)))
                bars = base_c.mark_bar(
                    color=COLOR_WORK, size=28,
                    cornerRadiusTopLeft=4, cornerRadiusTopRight=4, opacity=0.85,
                ).encode(
                    y=alt.Y("ชั่วโมงสะสม:Q", title="ชม. เดินเครื่องสะสม"),
                    tooltip=[alt.Tooltip("yearmonth(เดือน):T", title="เดือน",
                                         format="%m/%Y"),
                             alt.Tooltip("ชั่วโมงสะสม:Q", title="ชม.สะสม",
                                         format=",.0f"),
                             alt.Tooltip("ชั่วโมงเดือนนี้:Q", title="ชม.เดือนนี้",
                                         format=",.0f"),
                             alt.Tooltip("แจ้งซ่อม (ครั้ง):Q")],
                )
                line = base_c.mark_line(
                    color=COLOR_B, strokeWidth=2.5, interpolate="monotone",
                    point=alt.OverlayMarkDef(color=COLOR_B, filled=True, size=80),
                ).encode(
                    y=alt.Y("แจ้งซ่อม (ครั้ง):Q", title="ครั้งที่แจ้งซ่อม",
                            axis=alt.Axis(tickMinStep=1)),
                    tooltip=[alt.Tooltip("yearmonth(เดือน):T", title="เดือน",
                                         format="%m/%Y"),
                             alt.Tooltip("แจ้งซ่อม (ครั้ง):Q")],
                )
                st.altair_chart(
                    alt.layer(bars, line).resolve_scale(y="independent")
                    .properties(width="container", height=300),
                    width="stretch",
                )
                st.caption("แท่งเขียว = ชม.สะสม (ซ้าย) · เส้นแดง = ครั้งแจ้งซ่อม/เดือน (ขวา)")

    # ---------- ส่วนที่ 2: ทะเบียนเครื่องจักร ----------
    st.subheader("ทะเบียนเครื่องจักร", divider="gray")
    col_reg, col_rel = st.columns([3, 2])

    with col_reg:
        with st.container(border=True, height="stretch"):
            st.markdown("**🗂 ข้อมูลจากทะเบียน DataMaster**")
            if reg is None:
                st.caption("ไม่พบเครื่องนี้ในทะเบียนเครื่องจักร")
            else:
                facts = [
                    ("วันที่ติดตั้ง", _reg("วันที่ติดตั้ง")),
                    ("รุ่น", _reg("รุ่น")),
                    ("ยี่ห้อ", _reg("ยี่ห้อ")),
                    ("Serial No.", _reg("Serial No.")),
                    ("รอบ PM", _reg("ความถี่ PM")),
                    ("PM ล่าสุด", _reg("วันที่ PM ล่าสุด")),
                    ("ระบบไฟฟ้า", f"{_reg('เฟส')} · {_reg('โวลท์')}V"),
                    ("ผู้รับผิดชอบ", _reg("ผู้รับผิดชอบ")),
                ]
                fcols = st.columns(4)
                for i, (k, v) in enumerate(facts):
                    with fcols[i % 4]:
                        st.caption(k)
                        st.markdown(f"**{v}**")
                missing = _reg("ข้อมูลที่ยังขาด (สำรวจ)", "")
                if missing:
                    st.caption(f":material/warning: ข้อมูลที่ยังขาดในทะเบียน: {missing}")

    with col_rel:
        with st.container(border=True, height="stretch"):
            st.markdown("**🛡 จำนวนเหตุการณ์ (ช่วงข้อมูล Workcenter)**")
            if not prof:
                st.caption("ยังไม่มีบันทึกการสแกนของเครื่องนี้")
            else:
                e1, e2, e3 = st.columns(3)
                e1.metric("แจ้งซ่อม B", f"{bC}", border=True,
                          help="ครั้งที่ผู้คุมเครื่องแจ้งเครื่องเสีย")
                e2.metric("ช่างซ่อม BP", f"{bpC}", border=True,
                          help="ครั้งที่ช่างเข้าซ่อมจริง")
                e3.metric("งาน P", f"{prof.get('P_count', 0):,}", border=True,
                          help="เปลี่ยนอุปกรณ์/tooling/งาน operator")
                st.progress(min(pct_plan / 100, 1.0))
                st.caption(
                    f"เดินเครื่องจริง **{pct_plan:.0f}%** ของเวลากะปกติ"
                    + (" — ส่วนที่เกิน 100% คือช่วง OT" if pct_plan > 100 else "")
                )

    # ---------- ส่วนที่ 3: ประวัติการซ่อมย้อนหลัง ----------
    st.subheader("ประวัติการซ่อมย้อนหลัง 2020–2026", divider="orange")
    st.caption(
        "📌 นับเฉพาะ**งานซ่อมเครื่องจักร** (ฐานรายงานซ่อมบำรุง_เครื่อง) — "
        "ไม่รวมหมวดซ่อมสร้าง/ดัดแปลง/อื่นๆ ที่ทำกับพื้นที่รอบเครื่อง "
        "จึงอาจต่างจากหน้า Dashboard ซ่อมบำรุง 6 หมวดที่รวมทุกหมวด"
    )
    if rep.empty:
        st.caption(f"ไม่พบใบงานซ่อมของเครื่อง {mc} ในฐานข้อมูล 2020–2026")
    else:
        col_g, col_h, col_i = st.columns(3)

        with col_g:
            with st.container(border=True, height="stretch"):
                st.markdown("**🪙 มูลค่าซ่อมเครื่องสะสม**")
                cost = rep["ค่าใช้จ่ายรวม"].sum()
                n = len(rep)
                mins = rep["เวลาซ่อม (นาที)"].sum()
                st.metric("ค่าซ่อมสะสม", f"฿{cost:,.0f}", border=True)
                st.caption(
                    f"ใบงานซ่อม {n:,} ใบ · เฉลี่ย ฿{cost / n:,.0f}/ใบ · "
                    f"เวลาซ่อมรวม {mins / 60:,.0f} ชม."
                )
                pm = int((rep["สถานะการซ่อม (PM/BM)"] == "PM").sum())
                bm = int((rep["สถานะการซ่อม (PM/BM)"] == "BM").sum())
                m1, m2 = st.columns(2)
                m1.metric("PM (ป้องกัน)", f"{pm} ใบ", border=True)
                m2.metric("BM (เสียแล้วซ่อม)", f"{bm} ใบ", border=True)
                if pm + bm:
                    st.caption(
                        f"สัดส่วนป้องกัน : เสียแล้วซ่อม = "
                        f"**{pm / (pm + bm) * 100:.0f} : {bm / (pm + bm) * 100:.0f}** "
                        "— ยิ่งฝั่ง PM สูงยิ่งดี"
                    )
                yrs = rep["ปี"].astype(int)
                st.caption(f"ช่วงข้อมูล: {yrs.min()} – {yrs.max()}")

        with col_h:
            with st.container(border=True, height="stretch"):
                st.markdown("**⚡ อะไรเสีย — Electric vs Mechanical**")
                by_type = (
                    rep.groupby("ประเภทงาน")
                    .agg(ครั้ง=("เลขที่แจ้งซ่อม", "count"),
                         ค่าใช้จ่าย=("ค่าใช้จ่ายรวม", "sum"),
                         นาที=("เวลาซ่อม (นาที)", "sum"))
                    .reset_index().sort_values("ครั้ง", ascending=False)
                )
                type_colors = {"Electric": "#eda100", "Mechanical": "#2a78d6",
                               "ไม่ระบุ": "#898781"}

                # ตัวเลขใหญ่อ่านปราดเดียว: จำนวนครั้งของแต่ละประเภท
                tcols = st.columns(len(by_type))
                total_n = by_type["ครั้ง"].sum()
                for tcol, (_, r) in zip(tcols, by_type.iterrows()):
                    tcol.metric(
                        str(r["ประเภทงาน"]),
                        f"{r['ครั้ง']:,} ครั้ง", border=True,
                        help=f"{r['ครั้ง'] / total_n * 100:.0f}% ของใบงานซ่อมทั้งหมด",
                    )

                # กราฟสัดส่วน Electric vs Mechanical ใน 3 มิติ (ครั้ง/ค่าใช้จ่าย/ชั่วโมง)
                # หมายเหตุ: ห้ามใช้ row-facet ในการ์ดคอลัมน์ — Vega ไม่ยอมหดตาม
                # ความกว้างคอนเทนเนอร์ ทำให้กราฟล้นไปทับการ์ดข้างๆ
                melted = by_type.copy()
                melted["ชั่วโมงซ่อม"] = (melted["นาที"] / 60).round(1)
                melted["ค่าใช้จ่าย (พันบาท)"] = (melted["ค่าใช้จ่าย"] / 1e3).round(1)
                plot_t = melted.melt(
                    id_vars="ประเภทงาน",
                    value_vars=["ครั้ง", "ค่าใช้จ่าย (พันบาท)", "ชั่วโมงซ่อม"],
                    var_name="มิติ", value_name="ค่า",
                )
                chart = (
                    alt.Chart(plot_t)
                    .mark_bar(cornerRadius=3)
                    .encode(
                        y=alt.Y("มิติ:N", title=None,
                                scale=alt.Scale(paddingInner=0.45),
                                sort=["ครั้ง", "ค่าใช้จ่าย (พันบาท)", "ชั่วโมงซ่อม"]),
                        x=alt.X("ค่า:Q", stack="normalize", title="สัดส่วน",
                                axis=alt.Axis(format=".0%")),
                        order=alt.Order("ประเภทงาน:N"),
                        color=alt.Color(
                            "ประเภทงาน:N",
                            scale=alt.Scale(domain=list(type_colors),
                                            range=list(type_colors.values())),
                            legend=alt.Legend(orient="bottom", title=None)),
                        tooltip=[alt.Tooltip("ประเภทงาน:N"),
                                 alt.Tooltip("มิติ:N"),
                                 alt.Tooltip("ค่า:Q", format=",.1f")],
                    )
                    .properties(width="container", height=170)
                )
                st.altair_chart(chart, width="stretch")
                for _, r in by_type.iterrows():
                    st.caption(
                        f"**{r['ประเภทงาน']}**: {r['ครั้ง']:,} ครั้ง · "
                        f"฿{r['ค่าใช้จ่าย']:,.0f} · {r['นาที'] / 60:,.0f} ชม."
                    )

        with col_i:
            with st.container(border=True, height="stretch"):
                st.markdown("**🧩 เสียที่ Module ไหน (Top 8)**")
                if "Module" not in rep.columns:
                    st.info("ฐานใบงานซ่อมไม่มีคอลัมน์ Module")
                else:
                    by_mod = (
                        rep.groupby(["Module", "ชื่อโมดูล"])
                        .agg(ครั้ง=("เลขที่แจ้งซ่อม", "count"),
                             ค่าใช้จ่าย=("ค่าใช้จ่ายรวม", "sum"),
                             นาที=("เวลาซ่อม (นาที)", "sum"))
                        .reset_index().sort_values("ครั้ง", ascending=False).head(8)
                    )
                    by_mod["โมดูล"] = (by_mod["Module"] + " " +
                                       by_mod["ชื่อโมดูล"].str.slice(0, 22))
                    chart = (
                        alt.Chart(by_mod)
                        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                                  size=20)
                        .encode(
                            y=alt.Y("โมดูล:N", sort="-x", title=None),
                            x=alt.X("ครั้ง:Q", title="จำนวนครั้ง"),
                            color=alt.Color("โมดูล:N", legend=None,
                                            scale=alt.Scale(range=MODULE_COLORS)),
                            tooltip=[alt.Tooltip("Module:N"),
                                     alt.Tooltip("ชื่อโมดูล:N", title="ชื่อ"),
                                     alt.Tooltip("ครั้ง:Q"),
                                     alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f"),
                                     alt.Tooltip("นาที:Q", format=",.0f")],
                        )
                        .properties(width="container",
                                    height=max(180, 30 * len(by_mod)))
                    )
                    st.altair_chart(chart, width="stretch")
                    top = by_mod.iloc[0]
                    st.caption(
                        f"เสียบ่อยสุด: **{top['Module']} {top['ชื่อโมดูล']}** "
                        f"{top['ครั้ง']} ครั้ง · ฿{top['ค่าใช้จ่าย']:,.0f} "
                        "— ควรเน้น PM ที่โมดูลนี้"
                    )

        # ---- การ์ดเต็มแถว: เทียบค่าซ่อมสะสมกับราคาเครื่อง (ทุนตามบัญชี) ----
        with st.container(border=True):
            st.markdown("**⚖️ ค่าซ่อมสะสม เทียบราคาเครื่อง (ทุนตามบัญชี)**")
            if not asset_cost:
                st.caption("ทะเบียนเครื่องจักรยังไม่มีราคาทุนของเครื่องนี้ — "
                           "เติมคอลัมน์ 'ราคาทุนตามบัญชี (บาท)' ในทะเบียนเครื่องจักร")
            else:
                ratio = cost_total / asset_cost * 100
                if ratio < 25:
                    r_icon, r_note = "🟢", "ยังต่ำ — ซ่อมบำรุงคุ้มค่า"
                elif ratio < 50:
                    r_icon, r_note = "🟡", "เริ่มสูง — ควรติดตามแนวโน้มค่าซ่อม"
                else:
                    r_icon, r_note = ("🔴", "สูงมาก — ควรประเมินความคุ้มค่า "
                                            "ซ่อมต่อ vs เปลี่ยนเครื่อง")

                c_num, c_chart = st.columns([1, 2], vertical_alignment="center")
                with c_num:
                    st.metric("ราคาเครื่อง (บัญชี)", f"฿{asset_cost:,.0f}",
                              border=True)
                    st.metric("ค่าซ่อมเครื่องสะสม 2020–26", f"฿{cost_total:,.0f}",
                              border=True,
                              help="เฉพาะงานซ่อมเครื่องจักร ไม่รวมหมวดซ่อมสร้าง")
                    st.metric("สัดส่วนค่าซ่อม/ราคาเครื่อง", f"{ratio:.1f}%",
                              border=True,
                              help="เกณฑ์: <25% ต่ำ · 25–50% เฝ้าระวัง · >50% สูง")
                with c_chart:
                    cmp_df = pd.DataFrame([
                        {"รายการ": "ราคาเครื่อง (บัญชี)", "บาท": asset_cost,
                         "สี": "#2a78d6"},
                        {"รายการ": "ค่าซ่อมสะสม", "บาท": cost_total,
                         "สี": COLOR_BP},
                    ])
                    cmp_chart = (
                        alt.Chart(cmp_df)
                        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                                  size=34)
                        .encode(
                            y=alt.Y("รายการ:N", title=None,
                                    sort=["ราคาเครื่อง (บัญชี)", "ค่าซ่อมสะสม"]),
                            x=alt.X("บาท:Q", title="บาท",
                                    axis=alt.Axis(format="~s")),
                            color=alt.Color("รายการ:N", legend=None,
                                            scale=alt.Scale(
                                                domain=cmp_df["รายการ"].tolist(),
                                                range=cmp_df["สี"].tolist())),
                            tooltip=[alt.Tooltip("รายการ:N"),
                                     alt.Tooltip("บาท:Q", format=",.0f")],
                        )
                        .properties(width="container", height=130)
                    )
                    st.altair_chart(cmp_chart, width="stretch")
                    st.markdown(
                        f"{r_icon} ค่าซ่อมสะสมคิดเป็น **{ratio:.1f}%** "
                        f"ของราคาเครื่อง — {r_note}"
                        + (f" · เหลือวงเงินซ่อมอีก ฿{asset_cost - cost_total:,.0f} "
                           "จะเท่าราคาเครื่อง 1 ตัว" if ratio < 100 else "")
                    )

        with st.expander(f"📋 ใบงานซ่อมทั้งหมดของ {mc} ({len(rep):,} ใบ)"):
            show_cols = [c for c in [
                "วันที่แจ้งซ่อม", "เลขที่แจ้งซ่อม", "สถานะการซ่อม (PM/BM)",
                "ประเภทงาน", "Module", "ชื่อโมดูล", "ปัญหา", "วิเคราะห์สาเหตุ",
                "การแก้ไข", "เวลาซ่อม (นาที)", "ค่าใช้จ่ายรวม",
            ] if c in rep.columns]
            show_rep = rep[show_cols].sort_values("วันที่แจ้งซ่อม", ascending=False)
            st.dataframe(show_rep, width="stretch", hide_index=True, height=400)

    st.caption(
        "🔗 หน้านี้เชื่อม 5 ฐานข้อมูลด้วยรหัสเครื่อง: "
        "**ทะเบียนเครื่องจักร** (ข้อมูลทั่วไป/รอบ PM) · "
        "**Workcenter** (เวลาเดินจริง P/B/BP รายเดือน) · "
        "**MTBF-MTTR** (เหตุการณ์ซ่อม) · **OEE** (เวลาทำงานจริง) · "
        "**ใบงานซ่อม 2020–2026** (ค่าใช้จ่าย/Module/Electric-Mechanical)"
    )


# --- 6) ผลงาน ---
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
                .mark_bar(color=COLOR_WORK, cornerRadiusTopRight=4,
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

# --- 7) ข้อมูลดิบ ---
@st.cache_data(show_spinner="กำลังสร้างไฟล์ Excel...")
def _excel_bytes(df: pd.DataFrame) -> bytes:
    """แปลงตารางเป็นไฟล์ .xlsx — cache ไว้ ไม่งั้นทุกครั้งที่ขยับตัวกรองจะสร้างใหม่หลายวินาที"""
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="ข้อมูลดิบ", engine="openpyxl")
    return buf.getvalue()


# --- 7) ข้อมูลดิบ ---
# แท็บนี้มีตัวเลือกช่วงวันของตัวเอง ไม่ผูกกับ "วันที่" ในแถบข้าง เพราะอีก 6 แท็บ
# ทำงานแบบวันเดียว (สถานะสด, Timeline) ถ้าเปลี่ยนตัวเลือกกลางจะกระทบทั้งหน้า
# ค่าเริ่มต้นคือ "วันที่เลือก" เพื่อให้พฤติกรรมเดิมยังอยู่ครบ
#
# ข้อจำกัดที่ตั้งใจ
#   แสดงบนจอไม่เกิน RAW_SHOW_MAX แถว เพราะ st.dataframe ส่งทั้งตารางไปเบราว์เซอร์
#   หลายหมื่นแถวจะช้าจนหน้าค้าง แต่ไฟล์ที่ดาวน์โหลดมีครบทุกแถวเสมอ
#   ปุ่ม Excel ให้เฉพาะเมื่อไม่เกิน RAW_EXCEL_MAX แถว เกินนั้น openpyxl ใช้เวลาเป็นนาที
#   ให้ใช้ CSV แทน ซึ่งเปิดใน Excel ได้เหมือนกัน (utf-8-sig อ่านไทยถูก)
RAW_SHOW_MAX = 5_000
RAW_EXCEL_MAX = 20_000

with tab_raw:
    st.subheader("📋 ธุรกรรมทั้งหมด")

    RAW_MODES = ["วันที่เลือก", "7 วันล่าสุด", "30 วันล่าสุด", "เลือกหลายวัน", "กำหนดเอง"]
    c_mode, c_pick = st.columns([3, 2])
    with c_mode:
        raw_mode = st.segmented_control(
            "ช่วงข้อมูล", RAW_MODES, default="วันที่เลือก", key="raw_mode",
        ) or "วันที่เลือก"

    # แปลงโหมดที่เลือกเป็น "รายการวันที่" ชุดเดียว ทุกโหมดจบที่ตัวแปรนี้
    if raw_mode == "วันที่เลือก":
        chosen_days = [sel_date]
    elif raw_mode in ("7 วันล่าสุด", "30 วันล่าสุด"):
        n = 7 if raw_mode.startswith("7") else 30
        start = latest_date - timedelta(days=n - 1)
        chosen_days = [d for d in dates if start <= d <= latest_date]
    elif raw_mode == "เลือกหลายวัน":
        with c_pick:
            chosen_days = st.multiselect(
                "เลือกวัน", options=list(reversed(dates)), default=[sel_date],
                format_func=lambda d: f"{d:%d/%m/%Y}", key="raw_days",
                placeholder="เลือกได้หลายวัน",
            )
    else:  # กำหนดเอง
        with c_pick:
            default_start = max(dates[0], sel_date - timedelta(days=6))
            picked = st.date_input(
                "ช่วงวันที่", value=(default_start, sel_date),
                min_value=dates[0], max_value=latest_date, key="raw_range",
            )
        # ตอนผู้ใช้เพิ่งคลิกวันแรก date_input ส่งมาแค่ค่าเดียว ยังไม่ครบช่วง
        if isinstance(picked, tuple) and len(picked) == 2:
            r0, r1 = picked
        elif isinstance(picked, tuple) and len(picked) == 1:
            r0 = r1 = picked[0]
        else:
            r0 = r1 = picked
        chosen_days = [d for d in dates if r0 <= d <= r1]

    raw_df = data[data["Date"].isin(chosen_days)]
    if sel_groups:
        raw_df = raw_df[raw_df["Group"].isin(sel_groups)]

    # ตัวกรองเพิ่ม — ตัวเลือกมาจากข้อมูลในช่วงที่เลือกเท่านั้น จะได้ไม่มีตัวเลือกว่าง
    f1, f2 = st.columns(2)
    with f1:
        sel_machines = st.multiselect(
            "เครื่อง", sorted(raw_df["Machine"].dropna().unique()),
            default=[], placeholder="ทุกเครื่อง", key="raw_machines",
        )
    with f2:
        sel_types = st.multiselect(
            "ประเภทงาน", sorted(raw_df["ประเภทงาน"].dropna().unique()),
            default=[], placeholder="ทุกประเภท", key="raw_types",
        )
    if sel_machines:
        raw_df = raw_df[raw_df["Machine"].isin(sel_machines)]
    if sel_types:
        raw_df = raw_df[raw_df["ประเภทงาน"].isin(sel_types)]

    if raw_df.empty:
        st.info("ไม่มีธุรกรรมในช่วงและตัวกรองที่เลือก")
    else:
        display = (raw_df.drop(columns=["Date", "IsDowntime", "EndDisplay"], errors="ignore")
                   .sort_values(["Start", "Machine"]))
        d0, d1 = min(chosen_days), max(chosen_days)
        span = f"{d0:%d/%m/%Y}" if d0 == d1 else f"{d0:%d/%m/%Y} – {d1:%d/%m/%Y}"
        st.caption(
            f"**{len(display):,} แถว** · {display['Machine'].nunique()} เครื่อง · "
            f"{len(chosen_days)} วัน ({span}) · "
            f"เวลารวม {display['DurationMin'].sum() / 60:,.1f} ชม."
        )

        if len(display) > RAW_SHOW_MAX:
            st.dataframe(display.head(RAW_SHOW_MAX), width="stretch",
                         hide_index=True, height=520)
            st.caption(
                f"แสดง {RAW_SHOW_MAX:,} แถวแรกบนจอ · ไฟล์ที่ดาวน์โหลดมีครบ {len(display):,} แถว"
            )
        else:
            st.dataframe(display, width="stretch", hide_index=True, height=520)

        stem = (f"workcenter_{d0:%Y%m%d}" if d0 == d1
                else f"workcenter_{d0:%Y%m%d}-{d1:%Y%m%d}")
        csv_buf = io.BytesIO()
        display.to_csv(csv_buf, index=False, encoding="utf-8-sig")

        b1, b2, _ = st.columns([1, 1, 3])
        with b1:
            # on_click="ignore" — กดดาวน์โหลดแล้วไม่ต้อง rerun ทั้งหน้า
            st.download_button(
                "⬇️ CSV", data=csv_buf.getvalue(), file_name=stem + ".csv",
                mime="text/csv", on_click="ignore", width="stretch",
                help="เปิดใน Excel ได้ อ่านภาษาไทยถูกต้อง",
            )
        with b2:
            if len(display) <= RAW_EXCEL_MAX:
                st.download_button(
                    "⬇️ Excel", data=_excel_bytes(display), file_name=stem + ".xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    on_click="ignore", width="stretch",
                )
            else:
                st.button("⬇️ Excel", disabled=True, width="stretch",
                          help=f"เกิน {RAW_EXCEL_MAX:,} แถว สร้าง Excel จะช้ามาก — ใช้ CSV แทน")
