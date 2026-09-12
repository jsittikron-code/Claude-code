# -*- coding: utf-8 -*-
"""ETL Studio — เครื่องมือ ดึง–แปลง–ส่งออก ข้อมูล (Extract / Transform / Load)

แนวคิด
  ดึงไฟล์เข้ามาเป็น "ตาราง" หลายตารางได้ → เลือกตารางตั้งต้น → ต่อ "ขั้นตอนการแปลง"
  เรียงกันเป็นสูตร (recipe) → ดูผลลัพธ์สด ๆ ทุกขั้น → ส่งออกเป็นไฟล์หรือบันทึกลงโฟลเดอร์

โครงหน้าจอ
  ① ดึงข้อมูล      — อัปโหลดไฟล์ / เลือกจากโฟลเดอร์บนเครื่อง (Excel, CSV, JSON, Parquet)
  ② แปลงข้อมูล     — ต่อขั้นตอนทีละขั้น ดูตัวอย่างผลลัพธ์ทันที ปิด/เปิด/สลับลำดับได้
  ③ ตรวจคุณภาพ     — ค่าว่าง ชนิดข้อมูล ค่าซ้ำ ค่าไม่ซ้ำ สถิติเบื้องต้น
  ④ ส่งออก         — ดาวน์โหลด Excel/CSV/JSON หรือบันทึกลงโฟลเดอร์บนเครื่อง
  ⑤ สูตรแปลง       — บันทึก/เรียกคืนชุดขั้นตอน เอาไปใช้ซ้ำกับไฟล์รอบถัดไป

หมายเหตุการคำนวณ
  ทุกขั้นตอนทำงานบนสำเนาเสมอ — ไฟล์ต้นทางไม่เคยถูกแก้ ยกเว้นผู้ใช้สั่งบันทึกในแท็บ ④
"""
import datetime
import glob
import io
import json
import os
import re

import pandas as pd
import streamlit as st

import auth

st.set_page_config(page_title="ETL Studio — Modernform", page_icon="🧪", layout="wide")

# ด่านล็อกอิน — ใช้บัญชีชุดเดียวกับแดชบอร์ดตัวอื่นในโฟลเดอร์นี้ (ดู auth.py)
auth.check_login("ETL Studio — ดึง แปลง และส่งออกข้อมูล")

# ---------------------------------------------------------------------------
# สไตล์ — แถบหัวเรื่อง (hero) ให้เข้าชุดกับแดชบอร์ดตัวอื่นในโฟลเดอร์นี้
# ใช้ได้ทั้งธีมสว่างและมืด (แถบหัวมีพื้นเข้มของตัวเอง ตัวอักษรจึงอ่านชัดเสมอ)
# ---------------------------------------------------------------------------
APP_CSS = """
<style>
.etl-hero {
    position: relative; overflow: hidden;
    display: flex; flex-wrap: wrap; gap: 18px; align-items: center; justify-content: space-between;
    padding: 22px 26px; margin: 0 0 18px 0; border-radius: 20px;
    background: linear-gradient(115deg, #141a35 0%, #1e2a63 45%, #0f5d57 100%);
    border: 1px solid rgba(255,255,255,.10);
    box-shadow: 0 12px 34px rgba(16,22,52,.28);
}
.etl-hero::after {
    content: ""; position: absolute; inset: -40% -10% auto auto; width: 460px; height: 460px;
    background: radial-gradient(circle, rgba(96,165,250,.28), transparent 62%); pointer-events: none;
}
.etl-hero-main { position: relative; z-index: 1; min-width: 280px; }
.etl-eyebrow {
    font-size: .74rem; font-weight: 700; letter-spacing: .18em; text-transform: uppercase;
    color: rgba(186,214,255,.85); margin-bottom: 6px;
}
.etl-title {
    font-size: 2.15rem; font-weight: 800; line-height: 1.15; margin: 0;
    background: linear-gradient(90deg, #ffffff 0%, #cfe0ff 55%, #7ee7d0 100%);
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.etl-sub { font-size: .93rem; color: rgba(219,232,255,.82); margin-top: 4px; }
.etl-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.etl-chip {
    font-size: .78rem; font-weight: 600; color: #e8f1ff; padding: 5px 11px; border-radius: 999px;
    background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.16); white-space: nowrap;
}
.etl-flow { position: relative; z-index: 1; min-width: 210px; text-align: right; }
.etl-flow-label { font-size: .78rem; font-weight: 600; color: rgba(203,222,255,.8); letter-spacing: .04em; }
.etl-flow-value { font-size: 2.6rem; font-weight: 800; line-height: 1.05; margin: 2px 0 6px 0; color: #ffffff; }
.etl-flow-foot { font-size: .76rem; color: rgba(203,222,255,.78); }

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

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.join(APP_DIR, "etl_recipes")   # ที่เก็บสูตรแปลงที่บันทึกไว้

# นามสกุลไฟล์ที่อ่านได้
EXCEL_EXT = (".xlsx", ".xlsm", ".xls")
CSV_EXT = (".csv", ".txt", ".tsv")
JSON_EXT = (".json",)
PARQUET_EXT = (".parquet", ".pq")
ALL_EXT = EXCEL_EXT + CSV_EXT + JSON_EXT + PARQUET_EXT

# ตัวเลือกการอ่าน CSV — ครอบคลุมไฟล์ไทยที่ยังเป็น TIS-620/Windows-874
ENCODINGS = ["utf-8-sig", "utf-8", "cp874", "tis-620", "cp1252", "latin1"]
SEPARATORS = {"auto (เดาให้)": None, ", (จุลภาค)": ",", "; (อัฒภาค)": ";",
              "Tab": "\t", "| (ขีดตั้ง)": "|"}

# ชนิดข้อมูลที่แปลงได้ในขั้นตอน "แปลงชนิดข้อมูล"
DTYPES = ["ตัวเลข (ทศนิยม)", "ตัวเลข (จำนวนเต็ม)", "วันที่-เวลา", "ข้อความ", "ใช่/ไม่ใช่"]

# ฟังก์ชันสรุปที่ใช้ได้ในขั้นตอน "จัดกลุ่มสรุป"
AGG_FUNCS = {
    "รวม (sum)": "sum", "เฉลี่ย (mean)": "mean", "นับ (count)": "count",
    "นับไม่ซ้ำ (nunique)": "nunique", "ต่ำสุด (min)": "min", "สูงสุด (max)": "max",
    "มัธยฐาน (median)": "median", "ส่วนเบี่ยงเบน (std)": "std",
    "ค่าแรก (first)": "first", "ค่าสุดท้าย (last)": "last",
}

# ทะเบียนขั้นตอนการแปลง — รหัส → (ชื่อที่แสดง, ไอคอน, กลุ่ม)
OPS = {
    "select":    ("เลือก / ตัดคอลัมน์", "🧱", "โครงสร้าง"),
    "rename":    ("เปลี่ยนชื่อคอลัมน์", "🏷️", "โครงสร้าง"),
    "astype":    ("แปลงชนิดข้อมูล", "🔡", "โครงสร้าง"),
    "reorder":   ("จัดลำดับคอลัมน์", "↔️", "โครงสร้าง"),
    "filter":    ("กรองแถว", "🔍", "กรอง & ทำความสะอาด"),
    "dropna":    ("ตัดแถวที่มีค่าว่าง", "🕳️", "กรอง & ทำความสะอาด"),
    "fillna":    ("เติมค่าว่าง", "🩹", "กรอง & ทำความสะอาด"),
    "dedup":     ("ลบแถวซ้ำ", "🧹", "กรอง & ทำความสะอาด"),
    "limit":     ("จำกัดจำนวนแถว", "✂️", "กรอง & ทำความสะอาด"),
    "text":      ("จัดข้อความ (ตัดช่องว่าง/พิมพ์ใหญ่-เล็ก)", "🔤", "แก้ค่าในเซลล์"),
    "replace":   ("ค้นหาและแทนที่", "🔁", "แก้ค่าในเซลล์"),
    "split":     ("แยกคอลัมน์", "🔱", "แก้ค่าในเซลล์"),
    "round":     ("ปัดทศนิยม", "🎯", "แก้ค่าในเซลล์"),
    "compute":   ("เพิ่มคอลัมน์คำนวณ", "🧮", "สร้างค่าใหม่"),
    "dateparts": ("แตกส่วนของวันที่", "📅", "สร้างค่าใหม่"),
    "sort":      ("เรียงลำดับ", "🔃", "สรุป & จัดรูป"),
    "group":     ("จัดกลุ่มสรุป", "📊", "สรุป & จัดรูป"),
    "melt":      ("แปลงคอลัมน์เป็นแถว (unpivot)", "📥", "สรุป & จัดรูป"),
    "pivot":     ("แปลงแถวเป็นคอลัมน์ (pivot)", "📤", "สรุป & จัดรูป"),
    "concat":    ("ต่อท้ายตารางอื่น", "➕", "รวมตาราง"),
    "merge":     ("รวมตาราง (join)", "🔗", "รวมตาราง"),
}
OP_GROUPS = ["โครงสร้าง", "กรอง & ทำความสะอาด", "แก้ค่าในเซลล์",
             "สร้างค่าใหม่", "สรุป & จัดรูป", "รวมตาราง"]


# ---------------------------------------------------------------------------
# ตัวช่วยทั่วไป
# ---------------------------------------------------------------------------
def fmt_int(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "—"


def safe_name(name: str, taken) -> str:
    """ตั้งชื่อตารางไม่ให้ชนกับที่มีอยู่แล้ว — ต่อท้ายด้วย (2), (3), ..."""
    base, i, out = name, 2, name
    while out in taken:
        out, i = f"{base} ({i})", i + 1
    return out


def col_defaults(saved, columns):
    """คัดเฉพาะคอลัมน์ที่ยังมีอยู่จริง — กันพังเวลาขั้นตอนก่อนหน้าถูกแก้"""
    return [c for c in (saved or []) if c in columns]


def one_col(saved, columns, fallback_first=True):
    """คืน index ของคอลัมน์ที่เคยเลือกไว้ สำหรับใช้เป็น index ของ selectbox"""
    if saved in columns:
        return list(columns).index(saved)
    return 0 if (fallback_first and len(columns)) else 0


def numeric_cols(df) -> list:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def datetime_cols(df) -> list:
    return [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]


# ---------------------------------------------------------------------------
# สูตรที่ผู้ใช้พิมพ์เอง (query / eval)
# -------------------------------------
# ตัวแปลสูตรของ pandas ใช้ตัวแยกคำของ Python ซึ่ง normalize ชื่อตัวแปรแบบ NFKC
# ทำให้ "ำ" (U+0E33) ถูกแตกเป็นสองอักขระ ชื่อคอลัมน์ไทยอย่าง `จำนวนชิ้น` จึงหาไม่เจอ
# ทางแก้: เปลี่ยนชื่อคอลัมน์เป็นตัวแปรกลาง (COL_0, COL_1, ...) แล้วเขียนสูตรใหม่ให้ตรงกัน
# ก่อนส่งให้ pandas — ผู้ใช้ยังพิมพ์ชื่อไทยได้ตามปกติ จะครอบ backtick หรือไม่ก็ได้
# ---------------------------------------------------------------------------
def _alias_frame(df: pd.DataFrame):
    alias = {c: f"COL_{i}" for i, c in enumerate(df.columns)}
    return df.rename(columns=alias), alias


def _rewrite_expr(expr: str, alias: dict) -> str:
    """แทนชื่อคอลัมน์ในสูตรด้วยชื่อตัวแปรกลาง — ไม่ยุ่งกับข้อความในเครื่องหมายคำพูด"""
    def sub_outside(chunk: str) -> str:
        chunk = re.sub(r"`([^`]*)`",
                       lambda m: alias.get(m.group(1).strip(), m.group(1).strip()),
                       chunk)
        # ชื่อที่พิมพ์มาโดด ๆ ไม่ได้ครอบ backtick — ไล่จากชื่อยาวไปสั้น
        # กันกรณีชื่อหนึ่งเป็นส่วนต้นของอีกชื่อ เช่น "จำนวน" กับ "จำนวนชิ้น"
        for name in sorted(alias, key=len, reverse=True):
            chunk = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", alias[name], chunk)
        return chunk

    # แยกส่วนที่อยู่ในเครื่องหมายคำพูดออกมาก่อน แล้วแทนเฉพาะส่วนนอกคำพูด
    parts = re.split(r"('[^']*'|\"[^\"]*\")", expr)
    return "".join(p if i % 2 else sub_outside(p) for i, p in enumerate(parts))


def eval_expr(df: pd.DataFrame, expr: str):
    """คำนวณสูตรแล้วคืนผลลัพธ์ (Series หรือค่าเดี่ยว) — ใช้กับขั้นตอนเพิ่มคอลัมน์คำนวณ"""
    safe, alias = _alias_frame(df)
    return safe.eval(_rewrite_expr(expr, alias), engine="python")


def query_rows(df: pd.DataFrame, expr: str) -> pd.DataFrame:
    """กรองแถวตามสูตร — คืนแถวของตารางเดิม (ชื่อคอลัมน์ยังเป็นชื่อจริง)"""
    safe, alias = _alias_frame(df)
    kept = safe.query(_rewrite_expr(expr, alias), engine="python")
    return df.loc[kept.index]


# ---------------------------------------------------------------------------
# ตัวอ่านไฟล์ — cache ตามเนื้อไฟล์ อ่านซ้ำไม่ต้องรอใหม่
# ---------------------------------------------------------------------------
def _excel_engine(filename: str):
    """ไล่ engine ตามนามสกุล — calamine เร็วสุด เหลือไว้เป็นตัวสำรองอีกสองตัว"""
    if filename.lower().endswith(".xls"):
        return ["calamine", "xlrd"]
    return ["calamine", "openpyxl"]


@st.cache_data(show_spinner=False, max_entries=30)
def list_excel_sheets(data: bytes, filename: str) -> list:
    last = None
    for eng in _excel_engine(filename):
        try:
            return list(pd.ExcelFile(io.BytesIO(data), engine=eng).sheet_names)
        except Exception as e:      # engine ไม่รองรับไฟล์นี้ → ลองตัวถัดไป
            last = e
    raise RuntimeError(f"อ่านรายชื่อชีตไม่ได้: {last}")


@st.cache_data(show_spinner="กำลังอ่านไฟล์...", max_entries=30)
def read_excel(data: bytes, filename: str, sheet, header: int) -> pd.DataFrame:
    last = None
    for eng in _excel_engine(filename):
        try:
            return pd.read_excel(io.BytesIO(data), sheet_name=sheet,
                                 header=header, engine=eng)
        except Exception as e:
            last = e
    raise RuntimeError(f"อ่านชีตไม่ได้: {last}")


@st.cache_data(show_spinner="กำลังอ่านไฟล์...", max_entries=30)
def read_csv(data: bytes, sep, encoding: str, header: int) -> pd.DataFrame:
    kw = dict(header=header, encoding=encoding, on_bad_lines="warn")
    if sep is None:
        # ให้ pandas เดาตัวคั่นเอง (ต้องใช้ engine="python")
        kw.update(sep=None, engine="python")
    else:
        kw.update(sep=sep)
    return pd.read_csv(io.BytesIO(data), **kw)


@st.cache_data(show_spinner="กำลังอ่านไฟล์...", max_entries=30)
def read_json(data: bytes) -> pd.DataFrame:
    obj = json.loads(data.decode("utf-8-sig"))
    if isinstance(obj, dict):
        # dict ชั้นเดียวที่ค่าเป็น list → ปกติคือตารางที่ห่ออยู่ในคีย์เดียว
        lists = {k: v for k, v in obj.items() if isinstance(v, list)}
        if len(lists) == 1:
            obj = next(iter(lists.values()))
    return pd.json_normalize(obj)


@st.cache_data(show_spinner="กำลังอ่านไฟล์...", max_entries=30)
def read_parquet(data: bytes) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(data))


def read_any(data: bytes, filename: str, sheet=0, header: int = 0,
             sep=None, encoding: str = "utf-8-sig") -> pd.DataFrame:
    """อ่านไฟล์ตามนามสกุล แล้วล้างชื่อคอลัมน์ให้เรียบร้อย"""
    low = filename.lower()
    if low.endswith(EXCEL_EXT):
        df = read_excel(data, filename, sheet, header)
    elif low.endswith(JSON_EXT):
        df = read_json(data)
    elif low.endswith(PARQUET_EXT):
        df = read_parquet(data)
    else:
        df = read_csv(data, sep, encoding, header)
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# สถานะของแอป
# ---------------------------------------------------------------------------
def init_state():
    ss = st.session_state
    ss.setdefault("tables", {})        # ชื่อตาราง → DataFrame ต้นทาง
    ss.setdefault("origins", {})       # ชื่อตาราง → คำอธิบายที่มา
    ss.setdefault("steps", [])         # รายการขั้นตอนการแปลง
    ss.setdefault("step_seq", 0)       # ตัวนับ id ของขั้นตอน (ใช้เป็น key ของ widget)
    ss.setdefault("base_table", None)  # ตารางตั้งต้นของสูตร
    ss.setdefault("preview_rows", 50)


init_state()
SS = st.session_state


def add_table(name: str, df: pd.DataFrame, origin: str):
    name = safe_name(name, SS["tables"])
    SS["tables"][name] = df
    SS["origins"][name] = origin
    if SS["base_table"] is None:
        SS["base_table"] = name
    return name


def new_step(op: str) -> dict:
    SS["step_seq"] += 1
    return {"id": SS["step_seq"], "op": op, "on": True, "p": {}}


# ---------------------------------------------------------------------------
# การใช้ขั้นตอนกับข้อมูล — ทุกฟังก์ชันรับ df แล้วคืน df ใหม่ (ไม่แก้ของเดิม)
# ---------------------------------------------------------------------------
def _to_number(s: pd.Series, integer: bool) -> pd.Series:
    """แปลงเป็นตัวเลข — ตัดจุลภาคคั่นหลักและช่องว่างออกก่อน ค่าที่แปลงไม่ได้เป็นว่าง"""
    if not pd.api.types.is_numeric_dtype(s):
        s = (s.astype("string")
              .str.replace(",", "", regex=False)
              .str.replace(r"\s+", "", regex=True)
              .replace({"": None, "-": None}))
    out = pd.to_numeric(s, errors="coerce")
    return out.astype("Int64") if integer else out


def _to_bool(s: pd.Series) -> pd.Series:
    truthy = {"true", "yes", "y", "1", "ใช่", "จริง", "t"}
    falsy = {"false", "no", "n", "0", "ไม่ใช่", "เท็จ", "f"}
    low = s.astype("string").str.strip().str.lower()
    return low.map(lambda v: True if v in truthy else (False if v in falsy else None)
                   ).astype("boolean")


def apply_step(df: pd.DataFrame, step: dict, tables: dict) -> pd.DataFrame:
    op, p = step["op"], step["p"]
    df = df.copy()

    # ---- โครงสร้าง ----
    if op == "select":
        cols = col_defaults(p.get("cols"), df.columns)
        if not cols:
            return df
        return df.drop(columns=cols) if p.get("mode") == "drop" else df[cols]

    if op == "rename":
        mapping = {k: v for k, v in (p.get("map") or {}).items()
                   if k in df.columns and v}
        return df.rename(columns=mapping)

    if op == "reorder":
        order = col_defaults(p.get("order"), df.columns)
        rest = [c for c in df.columns if c not in order]
        return df[order + rest]

    if op == "astype":
        for c in col_defaults(p.get("cols"), df.columns):
            to = p.get("to")
            if to == "ตัวเลข (ทศนิยม)":
                df[c] = _to_number(df[c], integer=False)
            elif to == "ตัวเลข (จำนวนเต็ม)":
                df[c] = _to_number(df[c], integer=True)
            elif to == "วันที่-เวลา":
                df[c] = pd.to_datetime(df[c], errors="coerce",
                                       dayfirst=bool(p.get("dayfirst", True)),
                                       format="mixed")
            elif to == "ใช่/ไม่ใช่":
                df[c] = _to_bool(df[c])
            else:
                df[c] = df[c].astype("string")
        return df

    # ---- กรอง & ทำความสะอาด ----
    if op == "filter":
        if p.get("mode") == "expr":
            expr = (p.get("expr") or "").strip()
            return query_rows(df, expr) if expr else df
        col, cond = p.get("col"), p.get("cond")
        if col not in df.columns:
            return df
        s, val = df[col], p.get("value", "")
        if cond in ("ว่าง", "ไม่ว่าง"):
            mask = s.isna() if cond == "ว่าง" else s.notna()
        elif cond in ("มีคำว่า", "ขึ้นต้นด้วย", "ลงท้ายด้วย"):
            txt = s.astype("string").fillna("")
            fn = {"มีคำว่า": txt.str.contains, "ขึ้นต้นด้วย": txt.str.startswith,
                  "ลงท้ายด้วย": txt.str.endswith}[cond]
            mask = (fn(str(val), case=False, regex=False) if cond == "มีคำว่า"
                    else fn(str(val))).fillna(False)
        elif cond == "อยู่ในรายการ":
            items = [v.strip() for v in str(val).split(",") if v.strip()]
            mask = s.astype("string").isin(items)
        else:
            # เทียบค่า — ถ้าคอลัมน์เป็นตัวเลข/วันที่ ให้แปลงค่าที่พิมพ์มาให้ตรงชนิดก่อน
            if pd.api.types.is_numeric_dtype(s):
                cmp = pd.to_numeric(val, errors="coerce")
            elif pd.api.types.is_datetime64_any_dtype(s):
                cmp = pd.to_datetime(val, errors="coerce", dayfirst=True)
            else:
                cmp = str(val)
            ops = {"=": s.eq, "≠": s.ne, ">": s.gt, "≥": s.ge, "<": s.lt, "≤": s.le}
            mask = ops[cond](cmp)
        mask = mask.fillna(False).astype(bool)
        return df[~mask] if p.get("action") == "drop" else df[mask]

    if op == "dropna":
        subset = col_defaults(p.get("cols"), df.columns) or None
        return df.dropna(how=p.get("how", "any"), subset=subset)

    if op == "fillna":
        cols = col_defaults(p.get("cols"), df.columns) or list(df.columns)
        how = p.get("how", "ค่าที่กำหนด")
        for c in cols:
            if how == "ค่าที่กำหนด":
                v = p.get("value", "")
                if pd.api.types.is_numeric_dtype(df[c]):
                    v = pd.to_numeric(v, errors="coerce")
                    if pd.isna(v):
                        continue
                df[c] = df[c].fillna(v)
            elif how == "ค่าก่อนหน้า":
                df[c] = df[c].ffill()
            elif how == "ค่าถัดไป":
                df[c] = df[c].bfill()
            elif how in ("ค่าเฉลี่ย", "มัธยฐาน") and pd.api.types.is_numeric_dtype(df[c]):
                df[c] = df[c].fillna(df[c].mean() if how == "ค่าเฉลี่ย" else df[c].median())
            elif how == "ค่าที่พบบ่อยสุด":
                mode = df[c].mode(dropna=True)
                if len(mode):
                    df[c] = df[c].fillna(mode.iloc[0])
        return df

    if op == "dedup":
        subset = col_defaults(p.get("cols"), df.columns) or None
        keep = {"เก็บตัวแรก": "first", "เก็บตัวสุดท้าย": "last",
                "ตัดทิ้งทั้งหมด": False}[p.get("keep", "เก็บตัวแรก")]
        return df.drop_duplicates(subset=subset, keep=keep)

    if op == "limit":
        n = int(p.get("n", 100) or 0)
        how = p.get("how", "แถวแรก")
        if n <= 0:
            return df
        if how == "แถวแรก":
            return df.head(n)
        if how == "แถวสุดท้าย":
            return df.tail(n)
        return df.sample(min(n, len(df)), random_state=0)

    # ---- แก้ค่าในเซลล์ ----
    if op == "text":
        acts = p.get("acts") or []
        for c in col_defaults(p.get("cols"), df.columns):
            s = df[c].astype("string")
            if "ตัดช่องว่างหัวท้าย" in acts:
                s = s.str.strip()
            if "ยุบช่องว่างซ้อน" in acts:
                s = s.str.replace(r"\s+", " ", regex=True)
            if "ตัวพิมพ์ใหญ่" in acts:
                s = s.str.upper()
            if "ตัวพิมพ์เล็ก" in acts:
                s = s.str.lower()
            if "ขึ้นต้นด้วยตัวใหญ่" in acts:
                s = s.str.title()
            if "เหลือเฉพาะตัวเลข" in acts:
                s = s.str.replace(r"[^0-9.\-]", "", regex=True)
            df[c] = s
        return df

    if op == "replace":
        find, repl = p.get("find", ""), p.get("repl", "")
        use_re = bool(p.get("regex"))
        for c in col_defaults(p.get("cols"), df.columns):
            df[c] = df[c].astype("string").str.replace(
                find, repl, regex=use_re,
                flags=re.IGNORECASE if (use_re and p.get("icase")) else 0)
        return df

    if op == "split":
        col = p.get("col")
        if col not in df.columns:
            return df
        parts = df[col].astype("string").str.split(p.get("sep", ","), expand=True)
        n = min(int(p.get("n", 2) or 2), parts.shape[1])
        names = [x.strip() for x in (p.get("names") or "").split(",") if x.strip()]
        for i in range(n):
            name = names[i] if i < len(names) else f"{col}_{i + 1}"
            df[name] = parts[i].str.strip()
        return df.drop(columns=[col]) if p.get("drop_src") else df

    if op == "round":
        d = int(p.get("digits", 2))
        for c in col_defaults(p.get("cols"), df.columns):
            if pd.api.types.is_numeric_dtype(df[c]):
                df[c] = df[c].round(d)
        return df

    # ---- สร้างค่าใหม่ ----
    if op == "compute":
        name = (p.get("name") or "").strip()
        if not name:
            return df
        mode = p.get("mode", "สูตรคำนวณ")
        if mode == "สูตรคำนวณ":
            expr = (p.get("expr") or "").strip()
            if expr:
                df[name] = eval_expr(df, expr)
        elif mode == "รวมข้อความ":
            cols = col_defaults(p.get("cols"), df.columns)
            if cols:
                sep = p.get("sep", " ")
                out = df[cols[0]].astype("string").fillna("")
                for c in cols[1:]:
                    out = out + sep + df[c].astype("string").fillna("")
                df[name] = out
        else:                                   # ค่าคงที่
            df[name] = p.get("const", "")
        return df

    if op == "dateparts":
        col = p.get("col")
        if col not in df.columns:
            return df
        s = pd.to_datetime(df[col], errors="coerce", dayfirst=True, format="mixed")
        parts = p.get("parts") or []
        if "ปี" in parts:
            df[f"{col}_ปี"] = s.dt.year
        if "เดือน" in parts:
            df[f"{col}_เดือน"] = s.dt.month
        if "วัน" in parts:
            df[f"{col}_วัน"] = s.dt.day
        if "ไตรมาส" in parts:
            df[f"{col}_ไตรมาส"] = s.dt.quarter
        if "ปี-เดือน" in parts:
            df[f"{col}_ปีเดือน"] = s.dt.strftime("%Y-%m")
        if "สัปดาห์" in parts:
            df[f"{col}_สัปดาห์"] = s.dt.isocalendar().week.astype("Int64")
        if "วันในสัปดาห์" in parts:
            df[f"{col}_วันในสัปดาห์"] = s.dt.day_name()
        if "ชั่วโมง" in parts:
            df[f"{col}_ชั่วโมง"] = s.dt.hour
        if "วันที่ (ไม่เอาเวลา)" in parts:
            df[f"{col}_วันที่"] = s.dt.date
        return df

    # ---- สรุป & จัดรูป ----
    if op == "sort":
        cols = col_defaults(p.get("cols"), df.columns)
        if not cols:
            return df
        return df.sort_values(cols, ascending=bool(p.get("asc", True)),
                              na_position="last")

    if op == "group":
        by = col_defaults(p.get("by"), df.columns)
        aggs = {c: f for c, f in (p.get("aggs") or {}).items() if c in df.columns}
        if not by or not aggs:
            return df
        out = df.groupby(by, dropna=False).agg(aggs).reset_index()
        out.columns = [c if isinstance(c, str) else "_".join(str(x) for x in c if x)
                       for c in out.columns]
        return out

    if op == "melt":
        ids = col_defaults(p.get("ids"), df.columns)
        vals = col_defaults(p.get("vals"), df.columns)
        return df.melt(id_vars=ids, value_vars=vals or None,
                       var_name=p.get("var_name") or "ตัวแปร",
                       value_name=p.get("value_name") or "ค่า")

    if op == "pivot":
        idx = col_defaults(p.get("index"), df.columns)
        cols = p.get("columns")
        vals = p.get("values")
        if not idx or cols not in df.columns or vals not in df.columns:
            return df
        out = df.pivot_table(index=idx, columns=cols, values=vals,
                             aggfunc=AGG_FUNCS.get(p.get("aggfunc", "รวม (sum)"), "sum"),
                             dropna=False).reset_index()
        out.columns = [c if isinstance(c, str) else str(c) for c in out.columns]
        out.columns.name = None
        return out

    # ---- รวมตาราง ----
    if op == "concat":
        others = [tables[n] for n in (p.get("others") or []) if n in tables]
        if not others:
            return df
        return pd.concat([df] + others, ignore_index=True)

    if op == "merge":
        right_name = p.get("right")
        if right_name not in tables:
            return df
        right = tables[right_name]
        lk = [c for c in (p.get("left_on") or []) if c in df.columns]
        rk = [c for c in (p.get("right_on") or []) if c in right.columns]
        if not lk or len(lk) != len(rk):
            raise ValueError("ต้องเลือกคอลัมน์กุญแจซ้าย-ขวาให้ครบและจำนวนเท่ากัน")
        how = {"ซ้ายเป็นหลัก (left)": "left", "ขวาเป็นหลัก (right)": "right",
               "เฉพาะที่ตรงกัน (inner)": "inner",
               "เอาทั้งหมด (outer)": "outer"}[p.get("how", "ซ้ายเป็นหลัก (left)")]
        return df.merge(right, how=how, left_on=lk, right_on=rk,
                        suffixes=("", f"_{right_name}"))

    return df


def describe_step(step: dict) -> str:
    """คำอธิบายสั้น ๆ ต่อท้ายหัวข้อขั้นตอน — ให้กวาดตาดูสูตรทั้งชุดได้เร็ว"""
    op, p = step["op"], step["p"]
    n = len(p.get("cols") or [])
    if op == "select":
        return f"{'ตัด' if p.get('mode') == 'drop' else 'เก็บ'} {n} คอลัมน์"
    if op == "rename":
        return f"{len({k: v for k, v in (p.get('map') or {}).items() if v})} คอลัมน์"
    if op == "astype":
        return f"{n} คอลัมน์ → {p.get('to', '')}"
    if op == "filter":
        if p.get("mode") == "expr":
            return p.get("expr", "") or "—"
        return f"{p.get('col', '—')} {p.get('cond', '')} {p.get('value', '')}".strip()
    if op == "fillna":
        return p.get("how", "")
    if op == "dedup":
        return f"ดูจาก {n or 'ทุก'} คอลัมน์"
    if op == "limit":
        return f"{p.get('how', '')} {p.get('n', '')} แถว"
    if op == "text":
        return ", ".join(p.get("acts") or []) or "—"
    if op == "replace":
        return f"‘{p.get('find', '')}’ → ‘{p.get('repl', '')}’"
    if op == "split":
        return f"{p.get('col', '—')} ด้วย ‘{p.get('sep', '')}’"
    if op == "round":
        return f"{n} คอลัมน์ ทศนิยม {p.get('digits', 2)} ตำแหน่ง"
    if op == "compute":
        return f"{p.get('name', '—')} = {p.get('expr') or p.get('const') or p.get('mode', '')}"
    if op == "dateparts":
        return f"{p.get('col', '—')} → {', '.join(p.get('parts') or [])}"
    if op == "sort":
        return f"{', '.join(p.get('cols') or [])} ({'น้อย→มาก' if p.get('asc', True) else 'มาก→น้อย'})"
    if op == "group":
        return f"ตาม {', '.join(p.get('by') or [])} • {len(p.get('aggs') or {})} ค่าสรุป"
    if op == "melt":
        return f"คง {len(p.get('ids') or [])} คอลัมน์"
    if op == "pivot":
        return f"{p.get('columns', '—')} × {p.get('values', '—')}"
    if op == "concat":
        return ", ".join(p.get("others") or []) or "—"
    if op == "merge":
        return f"{p.get('right', '—')} • {p.get('how', '')}"
    if op == "reorder":
        return f"{len(p.get('order') or [])} คอลัมน์นำหน้า"
    return ""


# ---------------------------------------------------------------------------
# ฟอร์มตั้งค่าของแต่ละขั้นตอน — เขียนค่าลง step["p"] แล้วคืนค่ากลับทันทีในรอบเดียว
# ---------------------------------------------------------------------------
def render_step_form(step: dict, df: pd.DataFrame, tables: dict):
    op, p, k = step["op"], step["p"], f"s{step['id']}"
    cols_all = list(df.columns)

    if op == "select":
        p["mode"] = "drop" if st.radio(
            "ทำอะไรกับคอลัมน์ที่เลือก", ["เก็บไว้", "ตัดออก"], horizontal=True,
            index=1 if p.get("mode") == "drop" else 0, key=f"{k}_mode") == "ตัดออก" else "keep"
        p["cols"] = st.multiselect("คอลัมน์", cols_all,
                                   default=col_defaults(p.get("cols"), cols_all),
                                   key=f"{k}_cols")

    elif op == "rename":
        saved = p.get("map") or {}
        rows = [{"คอลัมน์เดิม": o, "ชื่อใหม่": n} for o, n in saved.items() if o in cols_all]
        if not rows:
            rows = [{"คอลัมน์เดิม": None, "ชื่อใหม่": ""}]
        ed = st.data_editor(
            pd.DataFrame(rows).astype("object"), num_rows="dynamic", hide_index=True,
            width="stretch", key=f"{k}_map",
            column_config={
                "คอลัมน์เดิม": st.column_config.SelectboxColumn(options=cols_all, width="medium"),
                "ชื่อใหม่": st.column_config.TextColumn(width="medium"),
            })
        p["map"] = {r["คอลัมน์เดิม"]: str(r["ชื่อใหม่"]).strip()
                    for _, r in ed.iterrows()
                    if r["คอลัมน์เดิม"] and str(r["ชื่อใหม่"]).strip()}

    elif op == "astype":
        c1, c2 = st.columns([3, 2])
        p["cols"] = c1.multiselect("คอลัมน์", cols_all,
                                   default=col_defaults(p.get("cols"), cols_all),
                                   key=f"{k}_cols")
        p["to"] = c2.selectbox("แปลงเป็น", DTYPES,
                               index=DTYPES.index(p["to"]) if p.get("to") in DTYPES else 0,
                               key=f"{k}_to")
        if p["to"] == "วันที่-เวลา":
            p["dayfirst"] = st.checkbox("อ่านแบบ วัน/เดือน/ปี (แบบไทย)",
                                        value=p.get("dayfirst", True), key=f"{k}_df")
        st.caption("ค่าที่แปลงไม่ได้จะกลายเป็นค่าว่าง — ดูจำนวนได้ในแท็บ ③ ตรวจคุณภาพ")

    elif op == "reorder":
        p["order"] = st.multiselect(
            "เลือกคอลัมน์ตามลำดับที่ต้องการให้อยู่ข้างหน้า", cols_all,
            default=col_defaults(p.get("order"), cols_all), key=f"{k}_order")
        st.caption("คอลัมน์ที่ไม่ได้เลือกจะต่อท้ายตามลำดับเดิม")

    elif op == "filter":
        p["mode"] = "expr" if st.radio(
            "วิธีกรอง", ["เลือกเงื่อนไข", "เขียนสูตรเอง"], horizontal=True,
            index=1 if p.get("mode") == "expr" else 0, key=f"{k}_mode") == "เขียนสูตรเอง" else "ui"
        if p["mode"] == "expr":
            p["expr"] = st.text_input("สูตร (แบบ pandas query)", value=p.get("expr", ""),
                                      placeholder="`จำนวนชิ้น` > 100 and สถานะ == 'ผ่าน'",
                                      key=f"{k}_expr")
            st.caption("ชื่อคอลัมน์ที่มีช่องว่างให้ครอบด้วย backtick เช่น `ชื่อ เครื่อง` • "
                       "ต่อเงื่อนไขด้วย and / or / not")
            with st.expander("ชื่อคอลัมน์ที่ใช้ได้ในสูตร"):
                st.code("  ".join(f"`{c}`" for c in cols_all))
        else:
            conds = ["=", "≠", ">", "≥", "<", "≤", "มีคำว่า", "ขึ้นต้นด้วย",
                     "ลงท้ายด้วย", "อยู่ในรายการ", "ว่าง", "ไม่ว่าง"]
            c1, c2, c3 = st.columns([3, 2, 3])
            p["col"] = c1.selectbox("คอลัมน์", cols_all,
                                    index=one_col(p.get("col"), cols_all), key=f"{k}_col")
            p["cond"] = c2.selectbox("เงื่อนไข", conds,
                                     index=conds.index(p["cond"]) if p.get("cond") in conds else 0,
                                     key=f"{k}_cond")
            if p["cond"] not in ("ว่าง", "ไม่ว่าง"):
                p["value"] = c3.text_input("ค่า", value=str(p.get("value", "")),
                                           key=f"{k}_val",
                                           help="‘อยู่ในรายการ’ ให้คั่นหลายค่าด้วยจุลภาค")
            p["action"] = "drop" if st.radio(
                "แถวที่เข้าเงื่อนไข", ["เก็บไว้", "ตัดออก"], horizontal=True,
                index=1 if p.get("action") == "drop" else 0,
                key=f"{k}_act") == "ตัดออก" else "keep"

    elif op == "dropna":
        c1, c2 = st.columns([3, 2])
        p["cols"] = c1.multiselect("ดูค่าว่างเฉพาะคอลัมน์ (เว้นว่าง = ดูทุกคอลัมน์)", cols_all,
                                   default=col_defaults(p.get("cols"), cols_all),
                                   key=f"{k}_cols")
        p["how"] = "all" if c2.radio("ตัดเมื่อ", ["ว่างอย่างน้อย 1 ช่อง", "ว่างทุกช่อง"],
                                     index=1 if p.get("how") == "all" else 0,
                                     key=f"{k}_how") == "ว่างทุกช่อง" else "any"

    elif op == "fillna":
        hows = ["ค่าที่กำหนด", "ค่าก่อนหน้า", "ค่าถัดไป", "ค่าเฉลี่ย", "มัธยฐาน", "ค่าที่พบบ่อยสุด"]
        c1, c2 = st.columns([3, 2])
        p["cols"] = c1.multiselect("คอลัมน์ (เว้นว่าง = ทุกคอลัมน์)", cols_all,
                                   default=col_defaults(p.get("cols"), cols_all),
                                   key=f"{k}_cols")
        p["how"] = c2.selectbox("เติมด้วย", hows,
                                index=hows.index(p["how"]) if p.get("how") in hows else 0,
                                key=f"{k}_how")
        if p["how"] == "ค่าที่กำหนด":
            p["value"] = st.text_input("ค่าที่ใช้เติม", value=str(p.get("value", "")),
                                       key=f"{k}_val")

    elif op == "dedup":
        keeps = ["เก็บตัวแรก", "เก็บตัวสุดท้าย", "ตัดทิ้งทั้งหมด"]
        c1, c2 = st.columns([3, 2])
        p["cols"] = c1.multiselect("ถือว่าซ้ำเมื่อคอลัมน์เหล่านี้เหมือนกัน (เว้นว่าง = ทั้งแถว)",
                                   cols_all, default=col_defaults(p.get("cols"), cols_all),
                                   key=f"{k}_cols")
        p["keep"] = c2.selectbox("แถวที่ซ้ำ", keeps,
                                 index=keeps.index(p["keep"]) if p.get("keep") in keeps else 0,
                                 key=f"{k}_keep")

    elif op == "limit":
        hows = ["แถวแรก", "แถวสุดท้าย", "สุ่ม"]
        c1, c2 = st.columns(2)
        p["how"] = c1.selectbox("เอาแถว", hows,
                                index=hows.index(p["how"]) if p.get("how") in hows else 0,
                                key=f"{k}_how")
        p["n"] = c2.number_input("จำนวนแถว", min_value=1, value=int(p.get("n", 100)),
                                 step=10, key=f"{k}_n")

    elif op == "text":
        acts = ["ตัดช่องว่างหัวท้าย", "ยุบช่องว่างซ้อน", "ตัวพิมพ์ใหญ่",
                "ตัวพิมพ์เล็ก", "ขึ้นต้นด้วยตัวใหญ่", "เหลือเฉพาะตัวเลข"]
        p["cols"] = st.multiselect("คอลัมน์", cols_all,
                                   default=col_defaults(p.get("cols"), cols_all),
                                   key=f"{k}_cols")
        p["acts"] = st.multiselect("จัดการ", acts,
                                   default=[a for a in (p.get("acts") or []) if a in acts],
                                   key=f"{k}_acts")

    elif op == "replace":
        p["cols"] = st.multiselect("คอลัมน์", cols_all,
                                   default=col_defaults(p.get("cols"), cols_all),
                                   key=f"{k}_cols")
        c1, c2 = st.columns(2)
        p["find"] = c1.text_input("ค้นหา", value=p.get("find", ""), key=f"{k}_find")
        p["repl"] = c2.text_input("แทนที่ด้วย", value=p.get("repl", ""), key=f"{k}_repl")
        c3, c4 = st.columns(2)
        p["regex"] = c3.checkbox("ใช้ regex", value=bool(p.get("regex")), key=f"{k}_re")
        if p["regex"]:
            p["icase"] = c4.checkbox("ไม่สนตัวพิมพ์ใหญ่-เล็ก", value=bool(p.get("icase")),
                                     key=f"{k}_ic")

    elif op == "split":
        c1, c2, c3 = st.columns([3, 2, 2])
        p["col"] = c1.selectbox("คอลัมน์", cols_all,
                                index=one_col(p.get("col"), cols_all), key=f"{k}_col")
        p["sep"] = c2.text_input("ตัวคั่น", value=p.get("sep", ","), key=f"{k}_sep")
        p["n"] = c3.number_input("แยกเป็นกี่คอลัมน์", min_value=1, max_value=20,
                                 value=int(p.get("n", 2)), key=f"{k}_n")
        p["names"] = st.text_input("ชื่อคอลัมน์ใหม่ (คั่นด้วยจุลภาค — เว้นว่างได้)",
                                   value=p.get("names", ""), key=f"{k}_names")
        p["drop_src"] = st.checkbox("ลบคอลัมน์ต้นทางทิ้ง", value=bool(p.get("drop_src")),
                                    key=f"{k}_drop")

    elif op == "round":
        c1, c2 = st.columns([3, 1])
        nums = numeric_cols(df)
        p["cols"] = c1.multiselect("คอลัมน์ตัวเลข", nums,
                                   default=col_defaults(p.get("cols"), nums), key=f"{k}_cols")
        p["digits"] = c2.number_input("ทศนิยม", min_value=0, max_value=10,
                                      value=int(p.get("digits", 2)), key=f"{k}_d")

    elif op == "compute":
        modes = ["สูตรคำนวณ", "รวมข้อความ", "ค่าคงที่"]
        c1, c2 = st.columns([2, 3])
        p["name"] = c1.text_input("ชื่อคอลัมน์ใหม่", value=p.get("name", ""), key=f"{k}_name")
        p["mode"] = c2.selectbox("สร้างจาก", modes,
                                 index=modes.index(p["mode"]) if p.get("mode") in modes else 0,
                                 key=f"{k}_mode")
        if p["mode"] == "สูตรคำนวณ":
            p["expr"] = st.text_input("สูตร", value=p.get("expr", ""),
                                      placeholder="`ชิ้นงานดี` / `จำนวนชิ้น` * 100",
                                      key=f"{k}_expr")
            st.caption("ใช้ชื่อคอลัมน์ในสูตรได้ตรง ๆ (ชื่อที่มีช่องว่างครอบด้วย backtick) "
                       "รองรับ + - * / % ** และวงเล็บ")
            with st.expander("ชื่อคอลัมน์ที่ใช้ได้ในสูตร"):
                st.code("  ".join(f"`{c}`" for c in cols_all))
        elif p["mode"] == "รวมข้อความ":
            p["cols"] = st.multiselect("คอลัมน์ที่จะต่อกัน (ตามลำดับที่เลือก)", cols_all,
                                       default=col_defaults(p.get("cols"), cols_all),
                                       key=f"{k}_cols")
            p["sep"] = st.text_input("คั่นด้วย", value=p.get("sep", " "), key=f"{k}_sep")
        else:
            p["const"] = st.text_input("ค่าคงที่", value=str(p.get("const", "")), key=f"{k}_c")

    elif op == "dateparts":
        parts = ["ปี", "เดือน", "วัน", "ไตรมาส", "ปี-เดือน", "สัปดาห์",
                 "วันในสัปดาห์", "ชั่วโมง", "วันที่ (ไม่เอาเวลา)"]
        p["col"] = st.selectbox("คอลัมน์วันที่", cols_all,
                                index=one_col(p.get("col"), cols_all), key=f"{k}_col")
        p["parts"] = st.multiselect("แตกเป็น", parts,
                                    default=[x for x in (p.get("parts") or []) if x in parts],
                                    key=f"{k}_parts")

    elif op == "sort":
        c1, c2 = st.columns([3, 2])
        p["cols"] = c1.multiselect("เรียงตาม (ตามลำดับที่เลือก)", cols_all,
                                   default=col_defaults(p.get("cols"), cols_all),
                                   key=f"{k}_cols")
        p["asc"] = c2.radio("ทิศทาง", ["น้อย→มาก", "มาก→น้อย"],
                            index=0 if p.get("asc", True) else 1,
                            key=f"{k}_asc") == "น้อย→มาก"

    elif op == "group":
        p["by"] = st.multiselect("จัดกลุ่มตาม", cols_all,
                                 default=col_defaults(p.get("by"), cols_all), key=f"{k}_by")
        saved = p.get("aggs") or {}
        inv = {v: k2 for k2, v in AGG_FUNCS.items()}
        rows = [{"คอลัมน์": c, "ค่าสรุป": inv.get(f, "รวม (sum)")}
                for c, f in saved.items() if c in cols_all]
        if not rows:
            rows = [{"คอลัมน์": None, "ค่าสรุป": "รวม (sum)"}]
        ed = st.data_editor(
            pd.DataFrame(rows).astype("object"), num_rows="dynamic", hide_index=True,
            width="stretch", key=f"{k}_aggs",
            column_config={
                "คอลัมน์": st.column_config.SelectboxColumn(
                    options=[c for c in cols_all if c not in (p.get("by") or [])],
                    width="medium"),
                "ค่าสรุป": st.column_config.SelectboxColumn(
                    options=list(AGG_FUNCS), width="medium"),
            })
        p["aggs"] = {r["คอลัมน์"]: AGG_FUNCS.get(r["ค่าสรุป"], "sum")
                     for _, r in ed.iterrows() if r["คอลัมน์"]}

    elif op == "melt":
        c1, c2 = st.columns(2)
        p["ids"] = c1.multiselect("คอลัมน์ที่คงไว้เป็นหลัก", cols_all,
                                  default=col_defaults(p.get("ids"), cols_all), key=f"{k}_ids")
        p["vals"] = c2.multiselect("คอลัมน์ที่จะพับลงเป็นแถว (เว้นว่าง = ที่เหลือทั้งหมด)",
                                   [c for c in cols_all if c not in (p.get("ids") or [])],
                                   default=col_defaults(p.get("vals"), cols_all),
                                   key=f"{k}_vals")
        c3, c4 = st.columns(2)
        p["var_name"] = c3.text_input("ชื่อคอลัมน์ชื่อตัวแปร",
                                      value=p.get("var_name", "ตัวแปร"), key=f"{k}_vn")
        p["value_name"] = c4.text_input("ชื่อคอลัมน์ค่า", value=p.get("value_name", "ค่า"),
                                        key=f"{k}_cn")

    elif op == "pivot":
        p["index"] = st.multiselect("แถว (index)", cols_all,
                                    default=col_defaults(p.get("index"), cols_all),
                                    key=f"{k}_idx")
        c1, c2, c3 = st.columns(3)
        p["columns"] = c1.selectbox("กระจายเป็นคอลัมน์จาก", cols_all,
                                    index=one_col(p.get("columns"), cols_all), key=f"{k}_c")
        p["values"] = c2.selectbox("ค่าที่ใส่ในตาราง", cols_all,
                                   index=one_col(p.get("values"), cols_all), key=f"{k}_v")
        p["aggfunc"] = c3.selectbox("รวมค่าซ้ำด้วย", list(AGG_FUNCS),
                                    index=list(AGG_FUNCS).index(p["aggfunc"])
                                    if p.get("aggfunc") in AGG_FUNCS else 0, key=f"{k}_a")

    elif op == "concat":
        others = [n for n in tables if n != SS.get("base_table")]
        p["others"] = st.multiselect("ต่อท้ายด้วยตาราง", others,
                                     default=[n for n in (p.get("others") or []) if n in others],
                                     key=f"{k}_o")
        st.caption("คอลัมน์ที่ไม่ตรงกันจะถูกเติมเป็นค่าว่างให้อัตโนมัติ")

    elif op == "merge":
        names = [n for n in tables if n != SS.get("base_table")]
        if not names:
            st.info("ต้องมีตารางอื่นอย่างน้อยหนึ่งตารางในแท็บ ① ก่อน")
            return
        hows = ["ซ้ายเป็นหลัก (left)", "ขวาเป็นหลัก (right)",
                "เฉพาะที่ตรงกัน (inner)", "เอาทั้งหมด (outer)"]
        c1, c2 = st.columns(2)
        p["right"] = c1.selectbox("รวมกับตาราง", names,
                                  index=names.index(p["right"]) if p.get("right") in names else 0,
                                  key=f"{k}_r")
        p["how"] = c2.selectbox("แบบ", hows,
                                index=hows.index(p["how"]) if p.get("how") in hows else 0,
                                key=f"{k}_h")
        rcols = list(tables[p["right"]].columns)
        c3, c4 = st.columns(2)
        p["left_on"] = c3.multiselect("กุญแจฝั่งซ้าย (ตารางนี้)", cols_all,
                                      default=col_defaults(p.get("left_on"), cols_all),
                                      key=f"{k}_lo")
        p["right_on"] = c4.multiselect(f"กุญแจฝั่งขวา ({p['right']})", rcols,
                                       default=col_defaults(p.get("right_on"), rcols),
                                       key=f"{k}_ro")


# ---------------------------------------------------------------------------
# แถบหัวเรื่อง
# ---------------------------------------------------------------------------
n_tables = len(SS["tables"])
n_steps = sum(1 for s in SS["steps"] if s.get("on", True))
base_rows = len(SS["tables"][SS["base_table"]]) if SS.get("base_table") in SS["tables"] else 0
st.markdown(f"""
<div class="etl-hero">
  <div class="etl-hero-main">
    <div class="etl-eyebrow">Extract · Transform · Load</div>
    <div class="etl-title">ETL Studio</div>
    <div class="etl-sub">ดึงข้อมูลจากไฟล์ → แปลงทีละขั้นแบบเห็นผลทันที → ส่งออกเป็นไฟล์พร้อมใช้</div>
    <div class="etl-chips">
      <span class="etl-chip">📥 {n_tables} ตาราง</span>
      <span class="etl-chip">🧪 {n_steps} ขั้นตอนที่เปิดใช้</span>
      <span class="etl-chip">📄 ตารางตั้งต้น {fmt_int(base_rows)} แถว</span>
    </div>
  </div>
  <div class="etl-flow">
    <div class="etl-flow-label">ตารางตั้งต้น</div>
    <div class="etl-flow-value">{SS.get('base_table') or '—'}</div>
    <div class="etl-flow-foot">ไฟล์ต้นทางไม่ถูกแก้ไข — เขียนไฟล์เฉพาะตอนสั่งในแท็บ ④</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# แถบข้าง
# ---------------------------------------------------------------------------
with st.sidebar:
    auth.sidebar_user_box()

    st.subheader("⚙️ ตั้งค่า")
    if SS["tables"]:
        names = list(SS["tables"])
        SS["base_table"] = st.selectbox(
            "ตารางตั้งต้นของสูตร", names,
            index=names.index(SS["base_table"]) if SS.get("base_table") in names else 0)
    SS["preview_rows"] = st.slider("จำนวนแถวที่แสดงตัวอย่าง", 10, 500,
                                   int(SS["preview_rows"]), step=10)

    st.markdown("---")
    st.subheader("📥 ตารางที่ดึงเข้ามา")
    if not SS["tables"]:
        st.caption("ยังไม่มี — ไปที่แท็บ ① ดึงข้อมูล")
    for name, tdf in list(SS["tables"].items()):
        c1, c2 = st.columns([5, 1])
        c1.caption(f"**{name}** — {fmt_int(len(tdf))} แถว × {len(tdf.columns)} คอลัมน์")
        if c2.button("🗑", key=f"del_tbl_{name}", help="เอาตารางนี้ออก"):
            SS["tables"].pop(name, None)
            SS["origins"].pop(name, None)
            if SS["base_table"] == name:
                SS["base_table"] = next(iter(SS["tables"]), None)
            st.rerun()

    st.markdown("---")
    if st.button("♻️ ล้างทุกอย่าง เริ่มใหม่", width="stretch"):
        for key in ("tables", "origins", "steps", "base_table"):
            SS.pop(key, None)
        init_state()
        st.rerun()

tab_e, tab_t, tab_q, tab_l, tab_r = st.tabs([
    "① ดึงข้อมูล", "② แปลงข้อมูล", "③ ตรวจคุณภาพ", "④ ส่งออก", "⑤ สูตรแปลง"])

# ---------------------------------------------------------------------------
# ① ดึงข้อมูล (Extract)
# ---------------------------------------------------------------------------
with tab_e:
    st.subheader("ดึงข้อมูลเข้ามาเป็นตาราง")
    src = st.radio("แหล่งข้อมูล", ["อัปโหลดไฟล์", "เลือกจากโฟลเดอร์บนเครื่อง"],
                   horizontal=True)

    # ---- ตัวเลือกการอ่าน (ใช้ร่วมกันทั้งสองแหล่ง) ----
    with st.expander("ตัวเลือกการอ่านไฟล์ (ปกติไม่ต้องแตะ)", expanded=False):
        c1, c2, c3 = st.columns(3)
        header_row = c1.number_input("แถวหัวตารางอยู่บรรทัดที่", min_value=1, value=1,
                                     help="ถ้าไฟล์มีหัวเรื่องคร่อมอยู่ด้านบน ให้เลื่อนเลขนี้ลงมา")
        sep_label = c2.selectbox("ตัวคั่นของไฟล์ CSV", list(SEPARATORS))
        encoding = c3.selectbox("การเข้ารหัสอักขระ CSV", ENCODINGS,
                                help="ไฟล์ไทยที่เปิดแล้วเป็นตัวยึกยือ ให้ลอง cp874")
    header = int(header_row) - 1
    sep = SEPARATORS[sep_label]

    if src == "อัปโหลดไฟล์":
        ups = st.file_uploader(
            "ลากไฟล์มาวางได้หลายไฟล์", accept_multiple_files=True,
            type=[e.lstrip(".") for e in ALL_EXT])
        for up in ups or []:
            data = up.getvalue()
            with st.container(border=True):
                st.markdown(f"**{up.name}** · {len(data) / 1024:,.0f} KB")
                if up.name.lower().endswith(EXCEL_EXT):
                    try:
                        sheets = list_excel_sheets(data, up.name)
                    except Exception as e:
                        st.error(f"อ่านไฟล์ไม่ได้: {e}")
                        continue
                    picked = st.multiselect("เลือกชีตที่จะดึงเข้ามา", sheets,
                                            default=sheets[:1], key=f"sh_{up.name}")
                    if st.button("➕ ดึงเข้ามา", key=f"imp_{up.name}", type="primary"):
                        for sh in picked:
                            try:
                                df = read_any(data, up.name, sheet=sh, header=header)
                                base = os.path.splitext(up.name)[0]
                                nm = add_table(f"{base} · {sh}" if len(picked) > 1 else base,
                                               df, f"อัปโหลด: {up.name} (ชีต {sh})")
                                st.success(f"ดึง **{nm}** เข้ามาแล้ว — "
                                           f"{fmt_int(len(df))} แถว × {len(df.columns)} คอลัมน์")
                            except Exception as e:
                                st.error(f"ชีต {sh}: {e}")
                        st.rerun()
                else:
                    if st.button("➕ ดึงเข้ามา", key=f"imp_{up.name}", type="primary"):
                        try:
                            df = read_any(data, up.name, header=header, sep=sep,
                                          encoding=encoding)
                            nm = add_table(os.path.splitext(up.name)[0], df,
                                           f"อัปโหลด: {up.name}")
                            st.success(f"ดึง **{nm}** เข้ามาแล้ว — "
                                       f"{fmt_int(len(df))} แถว × {len(df.columns)} คอลัมน์")
                            st.rerun()
                        except Exception as e:
                            st.error(f"อ่านไฟล์ไม่ได้: {e}")

    else:
        folder = st.text_input(
            "โฟลเดอร์บนเครื่อง",
            value=SS.get("last_folder", str(os.path.join(os.path.expanduser("~"), "Desktop"))),
            help="วางเส้นทางเต็ม เช่น C:\\Users\\p\\Desktop\\ข้อมูล")
        SS["last_folder"] = folder
        if folder and os.path.isdir(folder):
            files = sorted(f for f in glob.glob(os.path.join(folder, "*"))
                           if f.lower().endswith(ALL_EXT))
            if not files:
                st.info("โฟลเดอร์นี้ไม่มีไฟล์ที่อ่านได้ (Excel / CSV / JSON / Parquet)")
            else:
                picked = st.multiselect(
                    f"ไฟล์ในโฟลเดอร์ ({len(files)} ไฟล์)", files,
                    format_func=lambda f: os.path.basename(f))
                sheet_pick = {}
                for f in picked:
                    if f.lower().endswith(EXCEL_EXT):
                        try:
                            with open(f, "rb") as fh:
                                sheets = list_excel_sheets(fh.read(), f)
                            sheet_pick[f] = st.multiselect(
                                f"ชีตของ {os.path.basename(f)}", sheets,
                                default=sheets[:1], key=f"fsh_{f}")
                        except Exception as e:
                            st.error(f"{os.path.basename(f)}: {e}")
                if picked and st.button("➕ ดึงเข้ามา", type="primary"):
                    for f in picked:
                        try:
                            with open(f, "rb") as fh:
                                data = fh.read()
                            base = os.path.splitext(os.path.basename(f))[0]
                            if f.lower().endswith(EXCEL_EXT):
                                shs = sheet_pick.get(f) or [0]
                                for sh in shs:
                                    df = read_any(data, f, sheet=sh, header=header)
                                    nm = add_table(f"{base} · {sh}" if len(shs) > 1 else base,
                                                   df, f"ไฟล์: {f} (ชีต {sh})")
                                    st.success(f"ดึง **{nm}** — {fmt_int(len(df))} แถว")
                            else:
                                df = read_any(data, f, header=header, sep=sep,
                                              encoding=encoding)
                                nm = add_table(base, df, f"ไฟล์: {f}")
                                st.success(f"ดึง **{nm}** — {fmt_int(len(df))} แถว")
                        except Exception as e:
                            st.error(f"{os.path.basename(f)}: {e}")
                    st.rerun()
        elif folder:
            st.warning("ไม่พบโฟลเดอร์นี้ — ตรวจเส้นทางอีกครั้ง")

    # ---- ตารางที่ดึงเข้ามาแล้ว ----
    if SS["tables"]:
        st.markdown("---")
        st.subheader("ตารางที่ดึงเข้ามาแล้ว")
        for name, tdf in SS["tables"].items():
            with st.expander(f"📄 {name} — {fmt_int(len(tdf))} แถว × {len(tdf.columns)} คอลัมน์"
                             + ("  ⭐ ตารางตั้งต้น" if name == SS["base_table"] else "")):
                st.caption(SS["origins"].get(name, ""))
                st.dataframe(tdf.head(SS["preview_rows"]), width="stretch", height=280)

# ---------------------------------------------------------------------------
# ② แปลงข้อมูล (Transform)
#    เรนเดอร์ฟอร์มและคำนวณสลับกันไปทีละขั้น — ฟอร์มของขั้นที่ n จึงเห็นคอลัมน์
#    ที่เป็นผลจากขั้นที่ n-1 เสมอ และผลลัพธ์ท้ายสุดสดใหม่ให้แท็บถัด ๆ ไปใช้ต่อ
# ---------------------------------------------------------------------------
result = None
step_errors = {}

with tab_t:
    if not SS["tables"]:
        st.info("ยังไม่มีข้อมูล — ไปดึงไฟล์เข้ามาที่แท็บ ① ก่อน")
    else:
        base_name = SS["base_table"]
        current = SS["tables"][base_name].copy()
        st.caption(f"เริ่มจากตาราง **{base_name}** — {fmt_int(len(current))} แถว × "
                   f"{len(current.columns)} คอลัมน์")

        drop_idx = None
        move = None
        for i, step in enumerate(SS["steps"]):
            label, icon, _ = OPS[step["op"]]
            before_rows, before_cols = len(current), len(current.columns)
            state = "" if step.get("on", True) else "  ⏸ ปิดอยู่"
            with st.expander(f"{icon} **{i + 1}. {label}** — {describe_step(step)}{state}"):
                c1, c2, c3, c4 = st.columns([6, 1, 1, 1])
                step["on"] = c1.toggle("เปิดใช้ขั้นตอนนี้", value=step.get("on", True),
                                       key=f"on_{step['id']}")
                if c2.button("▲", key=f"up_{step['id']}", disabled=i == 0, help="เลื่อนขึ้น"):
                    move = (i, i - 1)
                if c3.button("▼", key=f"dn_{step['id']}",
                             disabled=i == len(SS["steps"]) - 1, help="เลื่อนลง"):
                    move = (i, i + 1)
                if c4.button("🗑", key=f"rm_{step['id']}", help="ลบขั้นตอนนี้"):
                    drop_idx = i

                render_step_form(step, current, SS["tables"])

                if step.get("on", True):
                    try:
                        current = apply_step(current, step, SS["tables"])
                    except Exception as e:
                        step_errors[step["id"]] = str(e)
                        st.error(f"ขั้นตอนนี้ทำงานไม่สำเร็จ — ข้ามไปใช้ข้อมูลเดิม\n\n{e}")
                    d_rows = len(current) - before_rows
                    d_cols = len(current.columns) - before_cols
                    st.caption(f"ผลหลังขั้นนี้: {fmt_int(len(current))} แถว "
                               f"({d_rows:+,}) × {len(current.columns)} คอลัมน์ ({d_cols:+d})")
                    st.dataframe(current.head(SS["preview_rows"]), width="stretch", height=240)

        if move:
            a, b = move
            SS["steps"][a], SS["steps"][b] = SS["steps"][b], SS["steps"][a]
            st.rerun()
        if drop_idx is not None:
            SS["steps"].pop(drop_idx)
            st.rerun()

        result = current

        # ---- เพิ่มขั้นตอนใหม่ ----
        st.markdown("---")
        with st.container(border=True):
            st.markdown("**➕ เพิ่มขั้นตอน**")
            c1, c2, c3 = st.columns([2, 4, 1.4])
            grp = c1.selectbox("หมวด", OP_GROUPS, label_visibility="collapsed")
            choices = [k for k, (_, _, g) in OPS.items() if g == grp]
            pick = c2.selectbox("ขั้นตอน", choices, label_visibility="collapsed",
                                format_func=lambda k: f"{OPS[k][1]} {OPS[k][0]}")
            if c3.button("เพิ่ม", type="primary", width="stretch"):
                SS["steps"].append(new_step(pick))
                st.rerun()

        # ---- ผลลัพธ์สุดท้าย ----
        st.markdown("---")
        st.subheader("ผลลัพธ์สุดท้าย")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("แถว", fmt_int(len(result)),
                  delta=f"{len(result) - len(SS['tables'][base_name]):+,} จากต้นทาง")
        m2.metric("คอลัมน์", len(result.columns))
        m3.metric("ช่องที่ว่าง", fmt_int(int(result.isna().sum().sum())))
        m4.metric("ขั้นตอนที่ใช้", sum(1 for s in SS["steps"] if s.get("on", True)))
        if step_errors:
            st.warning(f"มี {len(step_errors)} ขั้นตอนที่ทำงานไม่สำเร็จ — "
                       "ผลลัพธ์ด้านล่างข้ามขั้นตอนเหล่านั้นไป")
        st.dataframe(result.head(SS["preview_rows"]), width="stretch", height=380)

# ---------------------------------------------------------------------------
# ③ ตรวจคุณภาพ
# ---------------------------------------------------------------------------
with tab_q:
    if result is None or result.empty:
        st.info("ยังไม่มีผลลัพธ์ให้ตรวจ — ดึงข้อมูลที่แท็บ ① แล้วต่อขั้นตอนที่แท็บ ②")
    else:
        n = len(result)
        dup = int(result.duplicated().sum())
        blank_cells = int(result.isna().sum().sum())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("แถวทั้งหมด", fmt_int(n))
        m2.metric("แถวซ้ำทั้งแถว", fmt_int(dup),
                  delta=f"{dup / n * 100:.1f}%" if n else None, delta_color="inverse")
        m3.metric("ช่องที่ว่าง", fmt_int(blank_cells),
                  delta=f"{blank_cells / (n * max(len(result.columns), 1)) * 100:.1f}%" if n else None,
                  delta_color="inverse")
        m4.metric("หน่วยความจำที่ใช้",
                  f"{result.memory_usage(deep=True).sum() / 1024 ** 2:,.1f} MB")

        st.markdown("#### รายคอลัมน์")
        prof = pd.DataFrame({
            "คอลัมน์": result.columns,
            "ชนิดข้อมูล": [str(result[c].dtype) for c in result.columns],
            "ค่าว่าง (%)": [round(result[c].isna().mean() * 100, 1) for c in result.columns],
            "จำนวนค่าว่าง": [int(result[c].isna().sum()) for c in result.columns],
            "ค่าไม่ซ้ำ": [int(result[c].nunique(dropna=True)) for c in result.columns],
            "ตัวอย่างค่า": [", ".join(str(v) for v in result[c].dropna().unique()[:3]) or "—"
                            for c in result.columns],
        })
        st.dataframe(
            prof, width="stretch", hide_index=True, height=min(60 + 35 * len(prof), 460),
            column_config={
                "ค่าว่าง (%)": st.column_config.ProgressColumn(
                    "ค่าว่าง", min_value=0, max_value=100, format="%.1f%%"),
                "ตัวอย่างค่า": st.column_config.TextColumn(width="large"),
            })

        cols_num = numeric_cols(result)
        if cols_num:
            st.markdown("#### สถิติของคอลัมน์ตัวเลข")
            st.dataframe(result[cols_num].describe().T, width="stretch")

        if dup:
            with st.expander(f"ดูแถวที่ซ้ำ ({fmt_int(dup)} แถว)"):
                st.dataframe(result[result.duplicated(keep=False)].head(SS["preview_rows"]),
                             width="stretch")

# ---------------------------------------------------------------------------
# ④ ส่งออก (Load)
# ---------------------------------------------------------------------------
def to_excel_bytes(df: pd.DataFrame, sheet: str = "ข้อมูล") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=sheet[:31] or "ข้อมูล")
    return buf.getvalue()


with tab_l:
    if result is None or result.empty:
        st.info("ยังไม่มีผลลัพธ์ให้ส่งออก")
    else:
        st.caption(f"กำลังจะส่งออก {fmt_int(len(result))} แถว × {len(result.columns)} คอลัมน์")
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"{SS.get('base_table', 'ข้อมูล')}_แปลงแล้ว_{stamp}"

        st.markdown("#### ดาวน์โหลดไฟล์")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("⬇️ Excel (.xlsx)", to_excel_bytes(result),
                               file_name=f"{default_name}.xlsx", width="stretch",
                               mime="application/vnd.openxmlformats-officedocument."
                                    "spreadsheetml.sheet")
        with c2:
            st.download_button("⬇️ CSV (.csv)",
                               result.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"{default_name}.csv", mime="text/csv",
                               width="stretch",
                               help="เข้ารหัส UTF-8 with BOM — เปิดใน Excel ภาษาไทยไม่เพี้ยน")
        with c3:
            st.download_button("⬇️ JSON (.json)",
                               result.to_json(orient="records", force_ascii=False,
                                              indent=2, date_format="iso").encode("utf-8"),
                               file_name=f"{default_name}.json", mime="application/json",
                               width="stretch")

        st.markdown("---")
        st.markdown("#### บันทึกลงโฟลเดอร์บนเครื่อง")
        c1, c2 = st.columns([3, 2])
        out_dir = c1.text_input("โฟลเดอร์ปลายทาง",
                                value=SS.get("last_out_dir", SS.get("last_folder", APP_DIR)))
        out_fmt = c2.selectbox("รูปแบบไฟล์", ["Excel (.xlsx)", "CSV (.csv)",
                                              "JSON (.json)", "Parquet (.parquet)"])
        ext = {"Excel (.xlsx)": ".xlsx", "CSV (.csv)": ".csv",
               "JSON (.json)": ".json", "Parquet (.parquet)": ".parquet"}[out_fmt]
        fname = st.text_input("ชื่อไฟล์", value=default_name + ext)
        SS["last_out_dir"] = out_dir

        target = os.path.join(out_dir, fname) if out_dir and fname else ""
        exists = bool(target) and os.path.exists(target)
        overwrite = False
        if exists:
            info = os.stat(target)
            st.warning(
                f"มีไฟล์ชื่อนี้อยู่แล้ว — {info.st_size / 1024:,.0f} KB "
                f"แก้ไขล่าสุด {datetime.datetime.fromtimestamp(info.st_mtime):%d/%m/%Y %H:%M}")
            overwrite = st.checkbox("ยืนยันเขียนทับไฟล์เดิม")

        if st.button("💾 บันทึกไฟล์", type="primary", disabled=exists and not overwrite):
            if not os.path.isdir(out_dir):
                st.error("ไม่พบโฟลเดอร์ปลายทาง — ตรวจเส้นทางอีกครั้ง")
            else:
                try:
                    if ext == ".xlsx":
                        result.to_excel(target, index=False)
                    elif ext == ".csv":
                        result.to_csv(target, index=False, encoding="utf-8-sig")
                    elif ext == ".json":
                        result.to_json(target, orient="records", force_ascii=False,
                                       indent=2, date_format="iso")
                    else:
                        result.to_parquet(target, index=False)
                    st.success(f"บันทึกแล้ว: {target}")
                except Exception as e:
                    st.error(f"บันทึกไม่สำเร็จ: {e}")

        st.markdown("---")
        with st.expander("บันทึกผลลัพธ์กลับเข้ามาเป็นตารางใหม่ (ใช้ต่อยอดในสูตรถัดไป)"):
            nm = st.text_input("ชื่อตารางใหม่", value=f"{SS.get('base_table', 'ผลลัพธ์')}_แปลงแล้ว")
            if st.button("➕ เพิ่มเป็นตาราง"):
                created = add_table(nm, result.copy(), "ผลลัพธ์จากสูตรแปลงในแอปนี้")
                st.success(f"เพิ่มตาราง **{created}** แล้ว — เลือกเป็นตารางตั้งต้นได้ที่แถบข้าง")

# ---------------------------------------------------------------------------
# ⑤ สูตรแปลง (Recipe)
# ---------------------------------------------------------------------------
with tab_r:
    st.subheader("สูตรแปลง — เก็บชุดขั้นตอนไว้ใช้ซ้ำกับไฟล์รอบถัดไป")
    st.caption("สูตรเก็บเฉพาะ *ขั้นตอน* ไม่ได้เก็บข้อมูล — รอบหน้าดึงไฟล์ใหม่เข้ามา "
               "แล้วเรียกสูตรกลับ ขั้นตอนทั้งชุดจะทำงานให้ทันที")

    recipe = {
        "version": 1,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "base_table": SS.get("base_table"),
        "steps": [{"op": s["op"], "on": s.get("on", True), "p": s["p"]} for s in SS["steps"]],
    }
    recipe_json = json.dumps(recipe, ensure_ascii=False, indent=2, default=str)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### บันทึกสูตร")
        st.download_button("⬇️ ดาวน์โหลดสูตร (.json)", recipe_json.encode("utf-8"),
                           file_name=f"สูตรแปลง_{datetime.datetime.now():%Y%m%d_%H%M}.json",
                           mime="application/json", width="stretch",
                           disabled=not SS["steps"])
        rname = st.text_input("หรือบันทึกเก็บไว้ในแอป — ตั้งชื่อสูตร", value="")
        if st.button("💾 บันทึกไว้ในแอป", disabled=not (SS["steps"] and rname.strip()),
                     width="stretch"):
            os.makedirs(RECIPE_DIR, exist_ok=True)
            path = os.path.join(RECIPE_DIR, f"{rname.strip()}.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(recipe_json)
            st.success(f"บันทึกแล้ว: {path}")
            st.rerun()

    with c2:
        st.markdown("#### เรียกสูตรกลับมาใช้")
        saved = sorted(glob.glob(os.path.join(RECIPE_DIR, "*.json")))
        if saved:
            pick = st.selectbox("สูตรที่บันทึกไว้ในแอป", saved,
                                format_func=lambda p: os.path.splitext(os.path.basename(p))[0])
            cc1, cc2 = st.columns([3, 1])
            if cc1.button("📂 ใช้สูตรนี้", width="stretch"):
                try:
                    with open(pick, encoding="utf-8") as f:
                        loaded = json.load(f)
                    SS["steps"] = [dict(new_step(s["op"]), on=s.get("on", True), p=s.get("p", {}))
                                   for s in loaded.get("steps", [])]
                    if loaded.get("base_table") in SS["tables"]:
                        SS["base_table"] = loaded["base_table"]
                    st.success(f"โหลด {len(SS['steps'])} ขั้นตอนแล้ว")
                    st.rerun()
                except Exception as e:
                    st.error(f"อ่านสูตรไม่ได้: {e}")
            if cc2.button("🗑", help="ลบสูตรนี้", width="stretch"):
                os.remove(pick)
                st.rerun()
        else:
            st.caption("ยังไม่มีสูตรที่บันทึกไว้ในแอป")

        up_r = st.file_uploader("หรืออัปโหลดไฟล์สูตร (.json)", type=["json"], key="up_recipe")
        if up_r and st.button("📂 ใช้สูตรจากไฟล์ที่อัปโหลด", width="stretch"):
            try:
                loaded = json.loads(up_r.getvalue().decode("utf-8"))
                SS["steps"] = [dict(new_step(s["op"]), on=s.get("on", True), p=s.get("p", {}))
                               for s in loaded.get("steps", [])]
                st.success(f"โหลด {len(SS['steps'])} ขั้นตอนแล้ว")
                st.rerun()
            except Exception as e:
                st.error(f"อ่านสูตรไม่ได้: {e}")

    if SS["steps"]:
        st.markdown("---")
        st.markdown("#### สูตรชุดปัจจุบัน")
        st.dataframe(pd.DataFrame([{
            "ลำดับ": i + 1,
            "ขั้นตอน": f"{OPS[s['op']][1]} {OPS[s['op']][0]}",
            "รายละเอียด": describe_step(s),
            "ใช้งาน": "✅" if s.get("on", True) else "⏸",
        } for i, s in enumerate(SS["steps"])]), width="stretch", hide_index=True)
        with st.expander("ดูสูตรแบบ JSON"):
            st.code(recipe_json, language="json")
