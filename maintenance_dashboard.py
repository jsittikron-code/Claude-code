# -*- coding: utf-8 -*-
"""Dashboard งานซ่อมบำรุง 6 หมวด (2020-2026) — อ่านข้อมูลสดจากไฟล์ Excel ในโฟลเดอร์ฝ่ายซ่อมบำรุง"""
import os
import time
import datetime

import altair as alt
import pandas as pd
import streamlit as st

import auth

st.set_page_config(page_title="Dashboard งานซ่อมบำรุง 6 หมวด", page_icon="🛠️", layout="wide")

# ด่านล็อกอิน — รายชื่อผู้ใช้อยู่ใน .streamlit/secrets.toml (ไม่ push ขึ้น git)
# ใช้บัญชีชุดเดียวกับแดชบอร์ดตัวอื่นในโฟลเดอร์นี้ ดูโมดูล auth.py
auth.check_login("Dashboard งานซ่อมบำรุง 6 หมวด")

DATA_DIR = r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD\ฝ่ายซ่อมบำรุงรักษา\ทดสอบแยกข้อมูลย้อนหลัง"
FILES = {
    "เครื่องจักร": "รายงานซ่อมบำรุง_เครื่อง_2020-2026.xlsx",
    "ซ่อมสร้าง": "รายงานซ่อมบำรุง_ซ่อมสร้าง_2020-2026.xlsx",
    "ลับคม": "รายงานซ่อมบำรุง_ลับคม_2020-2026.xlsx",
    "ซ่อมรถยนต์": "รายงานซ่อมบำรุง_ซ่อมรถยนต์_2020-2026.xlsx",
    "เครื่องมือเล็ก": "รายงานซ่อมบำรุง_เครื่องมือเล็ก_2020-2026.xlsx",
    "ดัดแปลง": "รายงานซ่อมบำรุง_ดัดแปลง_2020-2026.xlsx",
}
PS_FILE = "วิเคราะห์ปัญหา-สาเหตุ_รายเครื่อง.xlsx"

# ฐานข้อมูลหลักของฝ่าย (ชุดเดียวกับที่ workcenter_monitor.py ใช้) — สำหรับแท็บโปรไฟล์เครื่องจักร
DEPT_DIR = r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD\ฝ่ายซ่อมบำรุงรักษา"
REGISTRY_PATH = os.path.join(DEPT_DIR, r"5.งานทะเบียนเครื่องจักร\ทะเบียนเครื่องจักร_DataMaster_2569.xlsx")
MTBF_PATH = os.path.join(DEPT_DIR, r"2.เรื่องMTBF-MTTR\รายละเอียด\MTBF-MTTR_ฐานข้อมูลหลัก_2569.xlsx")
OEE_PATH = os.path.join(DEPT_DIR, r"3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx")
MTBF_SHEETS = {"Breakdown_B000000001": "Breakdown", "Maintenance_BP00000001": "Maintenance"}
CATS = list(FILES.keys())
CAT_COLORS = {
    "เครื่องจักร": "#2a78d6",
    "ซ่อมสร้าง": "#eb6834",
    "ลับคม": "#1baf7a",
    "ซ่อมรถยนต์": "#eda100",
    "เครื่องมือเล็ก": "#e87ba4",
    "ดัดแปลง": "#008300",
}
CAT_SCALE = alt.Scale(domain=CATS, range=[CAT_COLORS[c] for c in CATS])
STATUS_SCALE = alt.Scale(domain=["PM", "BM", "ไม่ระบุ"], range=["#4a3aa7", "#e34948", "#c3c2b7"])
EM_SCALE = alt.Scale(domain=["Electric", "Mechanical", "อื่นๆ/ไม่ระบุ"],
                     range=["#4a3aa7", "#e34948", "#c3c2b7"])
BAD_CODES = ["", "#", "-", "nan", "None"]


def file_signature():
    """mtime ของทุกไฟล์ — เปลี่ยนเมื่อไฟล์ถูกแก้ ทำให้ cache โหลดใหม่เอง"""
    sig = []
    for fname in list(FILES.values()) + [PS_FILE]:
        p = os.path.join(DATA_DIR, fname)
        sig.append(os.path.getmtime(p) if os.path.exists(p) else 0)
    for p in (REGISTRY_PATH, MTBF_PATH, OEE_PATH):
        sig.append(os.path.getmtime(p) if os.path.exists(p) else 0)
    return tuple(sig)


def _read_sheet_at(path, sheet, header=0):
    """อ่านชีตด้วย calamine (เร็ว) ถ้าไม่ได้ลอง openpyxl · ไฟล์ถูกล็อก (เปิดใน Excel/OneDrive sync) ลองซ้ำ 1 ครั้ง"""
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


def _read_sheet(path, sheet):
    return _read_sheet_at(path, sheet)


@st.cache_data(ttl="1h", max_entries=3, show_spinner="กำลังอ่านข้อมูลจากไฟล์ Excel ทั้ง 6 ไฟล์...")
def load_data(sig):
    frames, missing = [], []
    for cat, fname in FILES.items():
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            missing.append(fname)
            continue
        try:
            raw = _read_sheet(path, "ข้อมูล")
        except Exception:
            missing.append(fname + " (ไฟล์ถูกเปิดล็อกอยู่ — ปิด Excel แล้วกดโหลดข้อมูลใหม่)")
            continue
        raw.columns = [str(c).strip() for c in raw.columns]

        def col(name):
            return raw[name] if name in raw.columns else pd.Series([None] * len(raw), index=raw.index)

        df = pd.DataFrame(index=raw.index)
        df["หมวด"] = cat
        df["ปี"] = pd.to_numeric(col("ปี"), errors="coerce")
        df["เดือน"] = pd.to_numeric(col("เดือน"), errors="coerce")
        df["หน่วยงาน"] = col("หน่วยงาน").astype(str).str.strip()
        df["รหัสเครื่อง"] = col("รหัสเครื่อง").astype(str).str.strip()
        df["สถานะ"] = col("สถานะการซ่อม (PM/BM)").astype(str).str.strip().str.upper()
        df["สถานะ"] = df["สถานะ"].where(df["สถานะ"].isin(["PM", "BM"]), "ไม่ระบุ")
        ptype = col("ประเภทงาน").astype(str).str.strip().str.lower()
        df["ประเภทงาน"] = "อื่นๆ/ไม่ระบุ"
        df.loc[ptype.str.contains("elect", na=False), "ประเภทงาน"] = "Electric"
        df.loc[ptype.str.contains("mech", na=False), "ประเภทงาน"] = "Mechanical"
        df["นาที"] = pd.to_numeric(col("เวลาซ่อม (นาที)"), errors="coerce").fillna(0)
        df["ค่าใช้จ่าย"] = (
            pd.to_numeric(col("ค่าใช้จ่าย (บาท)"), errors="coerce").fillna(0)
            + pd.to_numeric(col("Petty Cash (บาท)"), errors="coerce").fillna(0)
        )
        df["ปัญหา"] = col("ปัญหา").astype(str)
        df["โมดูล"] = col("Module").astype(str).str.strip()
        df["ชื่อโมดูล"] = col("ชื่อโมดูล").astype(str).str.strip()
        df = df[df["ปี"].between(2019, 2030) & df["เดือน"].between(1, 12)]
        df["ปี"] = df["ปี"].astype(int)
        df["เดือน"] = df["เดือน"].astype(int)
        df["เดือนปี"] = pd.to_datetime(dict(year=df["ปี"], month=df["เดือน"], day=1))
        frames.append(df)
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return data, missing


@st.cache_data(ttl="1h", max_entries=3, show_spinner="กำลังอ่านไฟล์วิเคราะห์ปัญหา-สาเหตุ...")
def load_ps(sig):
    """ชีต 'ข้อมูล' ของไฟล์วิเคราะห์ปัญหา-สาเหตุ_รายเครื่อง — ใช้เจาะประเภทปัญหา/กลุ่มสาเหตุรายเครื่อง"""
    path = os.path.join(DATA_DIR, PS_FILE)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        raw = _read_sheet(path, "ข้อมูล")
    except Exception:
        return pd.DataFrame()
    raw.columns = [str(c).strip() for c in raw.columns]

    def col(name):
        return raw[name] if name in raw.columns else pd.Series([None] * len(raw), index=raw.index)

    df = pd.DataFrame(index=raw.index)
    df["หมวด"] = col("หมวด").astype(str).str.strip()
    df["ปี"] = pd.to_numeric(col("ปี"), errors="coerce")
    df["วันที่แจ้ง"] = pd.to_datetime(col("วันที่แจ้ง"), errors="coerce")
    df["รหัสเครื่อง"] = col("รหัสเครื่อง").astype(str).str.strip()
    df["ประเภทปัญหา"] = col("ประเภทปัญหา").astype(str).str.strip()
    df["กลุ่มสาเหตุ"] = col("กลุ่มสาเหตุ").astype(str).str.strip()
    df["นาที"] = pd.to_numeric(col("เวลาซ่อม (นาที)"), errors="coerce").fillna(0)
    df["ค่าใช้จ่าย"] = pd.to_numeric(col("ค่าใช้จ่าย (บาท)"), errors="coerce").fillna(0)
    df["ปัญหา"] = col("ปัญหา").astype(str)
    df["วิเคราะห์สาเหตุ"] = col("วิเคราะห์สาเหตุ").astype(str)
    df["การแก้ไข"] = col("การแก้ไข").astype(str)
    df = df[df["ปี"].between(2019, 2030)]
    df["ปี"] = df["ปี"].astype(int)
    return df


@st.cache_data(ttl="1h", max_entries=3, show_spinner="กำลังอ่านทะเบียนเครื่องจักร...")
def load_registry(sig):
    """ทะเบียนเครื่องจักร (ชีต 'ทะเบียนหลัก' หัวตารางอยู่แถวที่ 3) → index = รหัสเครื่อง"""
    if not os.path.exists(REGISTRY_PATH):
        return pd.DataFrame()
    try:
        df = _read_sheet_at(REGISTRY_PATH, "ทะเบียนหลัก", header=2)
    except Exception:
        return pd.DataFrame()
    if "รหัสเครื่อง" not in df.columns:
        return pd.DataFrame()
    df = df[df["รหัสเครื่อง"].notna()].copy()
    df["รหัสเครื่อง"] = df["รหัสเครื่อง"].astype(str).str.strip()
    for c in ("วันที่ติดตั้ง", "วันที่ PM ล่าสุด"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    age = (pd.to_numeric(df["อายุ (ปี)"], errors="coerce")
           if "อายุ (ปี)" in df.columns else pd.Series(pd.NA, index=df.index, dtype="float64"))
    # ทะเบียนบางรอบเว้นคอลัมน์อายุไว้ว่าง — คำนวณจากวันที่ติดตั้งให้แทน
    if "วันที่ติดตั้ง" in df.columns:
        calc = (pd.Timestamp.today().normalize() - df["วันที่ติดตั้ง"]).dt.days / 365.25
        age = age.fillna(calc.round(1))
    df["อายุ (ปี)"] = age
    return df.drop_duplicates(subset="รหัสเครื่อง").set_index("รหัสเครื่อง")


@st.cache_data(ttl="1h", max_entries=3, show_spinner="กำลังอ่านฐาน MTBF-MTTR...")
def load_mtbf(sig):
    """เหตุการณ์ Breakdown (B) และช่างเข้าซ่อม (BP) รายเครื่อง จากฐาน MTBF-MTTR ของฝ่าย"""
    if not os.path.exists(MTBF_PATH):
        return pd.DataFrame()
    frames = []
    for sheet, typ in MTBF_SHEETS.items():
        try:
            d = _read_sheet_at(MTBF_PATH, sheet)
        except Exception:
            continue
        if "Machine" not in d.columns:
            continue
        d = d[d["Machine"].notna()].copy()
        out = pd.DataFrame(index=d.index)
        out["รหัสเครื่อง"] = d["Machine"].astype(str).str.strip()
        out["เริ่ม"] = pd.to_datetime(d["Start"], errors="coerce")
        out["นาที"] = pd.to_numeric(d.get("ระยะเวลา (นาที)"), errors="coerce").fillna(0)
        out["ประเภท"] = typ
        frames.append(out.dropna(subset=["เริ่ม"]))
    if not frames:
        return pd.DataFrame()
    ev = pd.concat(frames, ignore_index=True)
    ev["เดือนปี"] = ev["เริ่ม"].dt.to_period("M").dt.to_timestamp()
    return ev


@st.cache_data(ttl="1h", max_entries=3, show_spinner="กำลังอ่านฐาน OEE...")
def load_oee(sig):
    """เวลาทำงานจริง/วัน + OEE รายเครื่องรายวัน — ตัวหารของ MTBF ตามสูตรมาตรฐานฝ่าย"""
    if not os.path.exists(OEE_PATH):
        return pd.DataFrame()
    try:
        d = _read_sheet_at(OEE_PATH, "Report1")
    except Exception:
        return pd.DataFrame()
    if "MC" not in d.columns:
        return pd.DataFrame()
    out = pd.DataFrame(index=d.index)
    out["รหัสเครื่อง"] = d["MC"].astype(str).str.strip()
    out["วันที่"] = pd.to_datetime(d.get("Trans_date"), errors="coerce")
    out["เวลาทำงานจริง"] = pd.to_numeric(d.get("เวลาทำงานจริง/วัน"), errors="coerce").fillna(0)
    for src, dst in (("Avaliable (%)", "Availability"), ("Performance (%)", "Performance"),
                     ("Quality (%)", "Quality"), ("OEE (%)", "OEE")):
        v = pd.to_numeric(d.get(src), errors="coerce")
        # ฐานดิบมีค่าผิดปกติ (ติดลบ / เกิน 100%) จากการคีย์ผิด — ตัดออกก่อนเฉลี่ย
        out[dst] = v.where((v >= 0) & (v <= 100))
    out = out.dropna(subset=["วันที่"])
    out["เดือนปี"] = out["วันที่"].dt.to_period("M").dt.to_timestamp()
    return out


# ---------- โหลดข้อมูล ----------
if not os.path.isdir(DATA_DIR):
    st.error(f"ไม่พบโฟลเดอร์ข้อมูล: {DATA_DIR}")
    st.stop()

sig = file_signature()
df_all, missing = load_data(sig)
ps_all = load_ps(sig)
reg_all = load_registry(sig)
mtbf_all = load_mtbf(sig)
oee_all = load_oee(sig)
if missing:
    st.warning("ไม่พบไฟล์: " + ", ".join(missing))
if df_all.empty:
    st.error("อ่านข้อมูลไม่ได้เลยสักไฟล์ — ตรวจสอบโฟลเดอร์ข้อมูล")
    st.stop()

YEARS = sorted(df_all["ปี"].unique().tolist())

# ---------- Sidebar ----------
with st.sidebar:
    auth.sidebar_user_box()
    st.header("ตัวกรอง")
    year_sel = st.segmented_control("ปี", ["ทั้งหมด"] + YEARS, default="ทั้งหมด")
    cat_sel = st.pills("หมวดงาน", CATS, selection_mode="multi", default=CATS)
    st.divider()
    if st.button("โหลดข้อมูลใหม่", icon=":material/refresh:", width="stretch"):
        for fn in (load_data, load_ps, load_registry, load_mtbf, load_oee):
            fn.clear()
        st.rerun()
    newest = max(
        (os.path.getmtime(os.path.join(DATA_DIR, f)) for f in FILES.values()
         if os.path.exists(os.path.join(DATA_DIR, f))), default=0)
    if newest:
        st.caption("ไฟล์อัปเดตล่าสุด: " + datetime.datetime.fromtimestamp(newest).strftime("%d/%m/%Y %H:%M"))

cats = cat_sel or CATS
df = df_all[df_all["หมวด"].isin(cats)]
ps = ps_all.copy()
if year_sel != "ทั้งหมด":
    df = df[df["ปี"] == year_sel]
    if not ps.empty:
        ps = ps[ps["ปี"] == year_sel]
year_label = f"ปี {year_sel}" if year_sel != "ทั้งหมด" else f"ทุกปี ({YEARS[0]}–{YEARS[-1]})"

st.title("🛠️ Dashboard งานซ่อมบำรุง 6 หมวด")
st.caption(f"อ่านจากไฟล์รายงานซ่อมบำรุงในโฟลเดอร์ฝ่ายซ่อมบำรุงโดยตรง · {year_label} · ค่าใช้จ่ายรวม Petty Cash")

# ---------- KPI ----------
n_jobs = len(df)
cost_total = df["ค่าใช้จ่าย"].sum()
hours_total = df["นาที"].sum() / 60
n_bm = int((df["สถานะ"] == "BM").sum())
with st.container(horizontal=True):
    st.metric("งานซ่อมทั้งหมด", f"{n_jobs:,.0f} งาน", border=True)
    st.metric("ค่าใช้จ่ายรวม", f"{cost_total/1e6:,.2f} ลบ." if cost_total >= 1e6 else f"{cost_total:,.0f} บาท", border=True)
    st.metric("ชั่วโมงซ่อมรวม", f"{hours_total:,.0f} ชม.", border=True,
              help="รวมจากคอลัมน์ 'เวลาซ่อม (นาที)' ตามที่บันทึกไว้ในใบงาน — บางใบกรอกแบบเหมาเช่น "
                   "'30วัน' (43,200 นาที) ทำให้ยอดรวมสูงกว่าเวลาช่างทำงานจริง")
    st.metric("ค่าใช้จ่ายเฉลี่ย/งาน", f"{(cost_total/n_jobs if n_jobs else 0):,.0f} บาท", border=True)
    st.metric("BM ที่บันทึก", f"{n_bm:,.0f} ครั้ง", border=True)

tab_ov, tab_an, tab_mc = st.tabs(["📊 ภาพรวม", "🔍 วิเคราะห์เชิงลึก", "🏭 โปรไฟล์เครื่องจักร"])

# ==================== แท็บภาพรวม ====================
with tab_ov:
    by_cat = (df.groupby("หมวด", as_index=False)
              .agg(งาน=("หมวด", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"), นาที=("นาที", "sum")))
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.subheader("จำนวนงานซ่อมตามหมวด")
        base = alt.Chart(by_cat).encode(
            y=alt.Y("หมวด:N", sort="-x", title=None, axis=alt.Axis(labelLimit=160)),
            x=alt.X("งาน:Q", title="จำนวนงาน",
                    scale=alt.Scale(domainMax=float(by_cat["งาน"].max()) * 1.15, nice=False)),
            tooltip=[alt.Tooltip("หมวด:N"), alt.Tooltip("งาน:Q", format=","),
                     alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")],
        )
        bars = base.mark_bar(cornerRadiusEnd=4).encode(
            color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=None))
        text = base.mark_text(align="left", dx=4, fontSize=11).encode(text=alt.Text("งาน:Q", format=","))
        st.altair_chart((bars + text).properties(height=280))
    with c2, st.container(border=True):
        st.subheader("ค่าใช้จ่ายตามหมวด")
        base = alt.Chart(by_cat).encode(
            y=alt.Y("หมวด:N", sort="-x", title=None, axis=alt.Axis(labelLimit=160)),
            x=alt.X("ค่าใช้จ่าย:Q", title="บาท", axis=alt.Axis(format="~s"),
                    scale=alt.Scale(domainMax=float(by_cat["ค่าใช้จ่าย"].max()) * 1.18, nice=False)),
            tooltip=[alt.Tooltip("หมวด:N"), alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)"),
                     alt.Tooltip("งาน:Q", format=",")],
        )
        bars = base.mark_bar(cornerRadiusEnd=4).encode(
            color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=None))
        text = base.mark_text(align="left", dx=4, fontSize=11).encode(
            text=alt.Text("ค่าใช้จ่าย:Q", format=",.3~s"))
        st.altair_chart((bars + text).properties(height=280))

    c3, c4 = st.columns(2)
    with c3, st.container(border=True):
        st.subheader("จำนวนงานรายปี แยกตามหมวด")
        by_year = (df_all[df_all["หมวด"].isin(cats)]
                   .groupby(["ปี", "หมวด"], as_index=False).agg(งาน=("หมวด", "size")))
        yr_total = by_year.groupby("ปี", as_index=False).agg(รวม=("งาน", "sum"))
        bars = alt.Chart(by_year).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
            x=alt.X("ปี:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("งาน:Q", title="จำนวนงาน",
                    scale=alt.Scale(domainMax=float(yr_total["รวม"].max()) * 1.12, nice=False)
                    if not yr_total.empty else alt.Undefined),
            color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("ปี:O"), alt.Tooltip("หมวด:N"), alt.Tooltip("งาน:Q", format=",")])
        totals = alt.Chart(yr_total).mark_text(dy=-7, fontSize=11).encode(
            x=alt.X("ปี:O"), y=alt.Y("รวม:Q"), text=alt.Text("รวม:Q", format=","))
        st.altair_chart((bars + totals).properties(height=300))
        st.caption("กราฟนี้แสดงทุกปีเสมอ (ปี 2026 ถึง ก.ค.)")
    with c4, st.container(border=True):
        st.subheader("สัดส่วน PM / BM")
        by_status = (df.groupby(["หมวด", "สถานะ"], as_index=False).agg(งาน=("หมวด", "size")))
        ch = alt.Chart(by_status).mark_bar().encode(
            y=alt.Y("หมวด:N", title=None),
            x=alt.X("งาน:Q", stack="normalize", title="สัดส่วน", axis=alt.Axis(format="%")),
            color=alt.Color("สถานะ:N", scale=STATUS_SCALE,
                            legend=alt.Legend(orient="bottom", title=None)),
            order=alt.Order("color_สถานะ_sort_index:Q"),
            tooltip=[alt.Tooltip("หมวด:N"), alt.Tooltip("สถานะ:N"), alt.Tooltip("งาน:Q", format=",")],
        ).properties(height=280)
        st.altair_chart(ch)
        st.caption("PM = บำรุงรักษาตามแผน · BM = ซ่อมเมื่อเสีย · สถานะบันทึกจริงจังเฉพาะหมวดเครื่องจักร")

    with st.container(border=True):
        st.subheader("แนวโน้มจำนวนงานรายเดือน")
        by_month = df.groupby(["เดือนปี", "หมวด"], as_index=False).agg(
            งาน=("หมวด", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"))
        n_months = by_month["เดือนปี"].nunique()
        # เดือนเยอะ (ดูทุกปี) ให้ซ่อนจุดไม่ให้เส้นรก
        pt = alt.OverlayMarkDef(size=30) if n_months <= 18 else False
        ch = alt.Chart(by_month).mark_line(point=pt, strokeWidth=2).encode(
            x=alt.X("yearmonth(เดือนปี):T", title=None, axis=alt.Axis(format="%m/%Y")),
            y=alt.Y("งาน:Q", title="จำนวนงาน"),
            color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("yearmonth(เดือนปี):T", title="เดือน", format="%m/%Y"),
                     alt.Tooltip("หมวด:N"), alt.Tooltip("งาน:Q", format=","),
                     alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")],
        ).properties(height=300).interactive(bind_y=False)
        st.altair_chart(ch)

    c5, c6 = st.columns(2)
    with c5, st.container(border=True):
        st.subheader("Top 10 เครื่อง — ค่าใช้จ่ายสะสมสูงสุด")
        dfm = df[~df["รหัสเครื่อง"].isin(BAD_CODES)]
        top_m = (dfm.groupby(["รหัสเครื่อง", "หมวด"], as_index=False)
                 .agg(ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"), งาน=("หมวด", "size"))
                 .nlargest(10, "ค่าใช้จ่าย"))
        base = alt.Chart(top_m).encode(
            y=alt.Y("รหัสเครื่อง:N", sort="-x", title=None),
            x=alt.X("ค่าใช้จ่าย:Q", title="บาท", axis=alt.Axis(format="~s"),
                    scale=alt.Scale(domainMax=float(top_m["ค่าใช้จ่าย"].max()) * 1.18, nice=False)
                    if not top_m.empty else alt.Undefined),
            tooltip=[alt.Tooltip("รหัสเครื่อง:N"), alt.Tooltip("หมวด:N"),
                     alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)"),
                     alt.Tooltip("งาน:Q", format=",")])
        ch = (base.mark_bar(cornerRadiusEnd=4).encode(
                  color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)))
              + base.mark_text(align="left", dx=4, fontSize=11).encode(
                  text=alt.Text("ค่าใช้จ่าย:Q", format=",.3~s")))
        st.altair_chart(ch.properties(height=330))
    with c6, st.container(border=True):
        st.subheader("Top 10 หน่วยงานที่แจ้งซ่อม")
        dfd = df[~df["หน่วยงาน"].isin(["", "nan", "None"])]
        top_depts = dfd["หน่วยงาน"].value_counts().nlargest(10).index.tolist()
        by_dept = (dfd[dfd["หน่วยงาน"].isin(top_depts)]
                   .groupby(["หน่วยงาน", "หมวด"], as_index=False).agg(งาน=("หมวด", "size")))
        dept_total = by_dept.groupby("หน่วยงาน", as_index=False).agg(รวม=("งาน", "sum"))
        bars = alt.Chart(by_dept).mark_bar().encode(
            y=alt.Y("หน่วยงาน:N", sort=top_depts, title=None),
            x=alt.X("งาน:Q", title="จำนวนงาน",
                    scale=alt.Scale(domainMax=float(dept_total["รวม"].max()) * 1.15, nice=False)
                    if not dept_total.empty else alt.Undefined),
            color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("หน่วยงาน:N"), alt.Tooltip("หมวด:N"), alt.Tooltip("งาน:Q", format=",")])
        totals = alt.Chart(dept_total).mark_text(align="left", dx=4, fontSize=11).encode(
            y=alt.Y("หน่วยงาน:N", sort=top_depts, title=None),
            x=alt.X("รวม:Q"), text=alt.Text("รวม:Q", format=","))
        st.altair_chart((bars + totals).properties(height=330))

    with st.container(border=True):
        st.subheader("ตารางสรุปตามหมวด")
        summary = (df.groupby("หมวด")
                   .agg(งาน=("หมวด", "size"),
                        PM=("สถานะ", lambda s: int((s == "PM").sum())),
                        BM=("สถานะ", lambda s: int((s == "BM").sum())),
                        ค่าใช้จ่าย_บาท=("ค่าใช้จ่าย", "sum"),
                        เวลาซ่อม_ชม=("นาที", lambda s: s.sum() / 60),
                        มัธยฐาน_นาทีต่อใบ=("นาที", "median"))
                   .reindex([c for c in CATS if c in df["หมวด"].unique()]))
        summary["เฉลี่ย_บาทต่องาน"] = (summary["ค่าใช้จ่าย_บาท"] / summary["งาน"].replace(0, pd.NA)).fillna(0)
        total = summary.sum(numeric_only=True)
        total["เฉลี่ย_บาทต่องาน"] = total["ค่าใช้จ่าย_บาท"] / total["งาน"] if total["งาน"] else 0
        total["มัธยฐาน_นาทีต่อใบ"] = df["นาที"].median() if len(df) else 0
        summary.loc["รวม"] = total
        st.dataframe(
            summary,
            column_config={c: st.column_config.NumberColumn(c.replace("_", " "), format="localized")
                           for c in summary.columns},
        )

    with st.expander("ดูข้อมูลดิบ (ตามตัวกรอง)"):
        st.dataframe(
            df[["หมวด", "ปี", "เดือน", "หน่วยงาน", "รหัสเครื่อง", "สถานะ", "นาที", "ค่าใช้จ่าย", "ปัญหา"]],
            hide_index=True, height=400)

# ==================== แท็บวิเคราะห์เชิงลึก ====================
def yoy_frame(data, year_col, value_cols):
    """สรุปยอดรวมรายปี + %เทียบปีก่อน (YoY) พร้อมข้อความ ▲/▼ สำหรับติดบนหัวแท่ง"""
    out = (data.groupby(year_col, as_index=False)[value_cols].sum()
           .sort_values(year_col).reset_index(drop=True))
    def label(v):
        if pd.isna(v):
            return "—"                      # ปีแรก ไม่มีปีก่อนให้เทียบ
        if abs(v) < 0.005:
            return "≈ 0%"                   # เปลี่ยนแปลงน้อยมาก อย่าให้ขึ้น -0%
        digits = 1 if abs(v) < 0.1 else 0   # ต่ำกว่า 10% แสดงทศนิยม 1 ตำแหน่ง
        return ("▲ +" if v > 0 else "▼ ") + f"{v:.{digits}%}"

    for c in value_cols:
        pct = out[c].pct_change()
        out[f"YoY_{c}"] = pct
        out[f"ป้าย_{c}"] = [label(v) for v in pct]
    return out


with tab_an:
    df_cats_all_years = df_all[df_all["หมวด"].isin(cats)]

    # ---------- แนวโน้มรายปี 4 มุม ----------
    with st.container(border=True):
        st.subheader("แนวโน้มรายปี แยกตามหมวด")
        st.caption("แสดงทุกปีเสมอเพื่อดูแนวโน้ม (ปี 2026 ถึง ก.ค.) · ตามหมวดที่เลือก")
        by_year = (df_cats_all_years.groupby(["ปี", "หมวด"], as_index=False)
                   .agg(งาน=("หมวด", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"), นาที=("นาที", "sum")))
        by_year["ชั่วโมง"] = by_year["นาที"] / 60
        by_year["เฉลี่ยบาท"] = by_year["ค่าใช้จ่าย"] / by_year["งาน"].replace(0, pd.NA)
        by_year["เฉลี่ยนาที"] = by_year["นาที"] / by_year["งาน"].replace(0, pd.NA)

        a1, a2 = st.columns(2)
        with a1:
            st.markdown("**ค่าใช้จ่ายต่อปี (บาท)**")
            ch = alt.Chart(by_year).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
                x=alt.X("ปี:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("ค่าใช้จ่าย:Q", title="บาท", axis=alt.Axis(format="~s")),
                color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
                tooltip=[alt.Tooltip("ปี:O"), alt.Tooltip("หมวด:N"),
                         alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")],
            ).properties(height=260)
            st.altair_chart(ch)
        with a2:
            st.markdown("**เวลาซ่อมรวมต่อปี (ชม.)**")
            ch = alt.Chart(by_year).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
                x=alt.X("ปี:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("ชั่วโมง:Q", title="ชม.", axis=alt.Axis(format="~s")),
                color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
                tooltip=[alt.Tooltip("ปี:O"), alt.Tooltip("หมวด:N"),
                         alt.Tooltip("ชั่วโมง:Q", format=",.0f", title="เวลาซ่อม (ชม.)")],
            ).properties(height=260)
            st.altair_chart(ch)

        a3, a4 = st.columns(2)
        with a3:
            st.markdown("**ค่าใช้จ่ายเฉลี่ย/งาน รายปี (บาท)**")
            ch = alt.Chart(by_year).mark_line(point=alt.OverlayMarkDef(size=40), strokeWidth=2).encode(
                x=alt.X("ปี:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("เฉลี่ยบาท:Q", title="บาท/งาน", axis=alt.Axis(format="~s")),
                color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
                tooltip=[alt.Tooltip("ปี:O"), alt.Tooltip("หมวด:N"),
                         alt.Tooltip("เฉลี่ยบาท:Q", format=",.0f", title="เฉลี่ย (บาท/งาน)")],
            ).properties(height=260)
            st.altair_chart(ch)
        with a4:
            st.markdown("**เวลาซ่อมเฉลี่ย/งาน รายปี (นาที)**")
            ch = alt.Chart(by_year).mark_line(point=alt.OverlayMarkDef(size=40), strokeWidth=2).encode(
                x=alt.X("ปี:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("เฉลี่ยนาที:Q", title="นาที/งาน", axis=alt.Axis(format="~s")),
                color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
                tooltip=[alt.Tooltip("ปี:O"), alt.Tooltip("หมวด:N"),
                         alt.Tooltip("เฉลี่ยนาที:Q", format=",.0f", title="เฉลี่ย (นาที/งาน)")],
            ).properties(height=260)
            st.altair_chart(ch)

    # ---------- Donut สัดส่วนตามหมวด ----------
    with st.container(border=True):
        st.subheader("สัดส่วนตามหมวด — จำนวน | ค่าใช้จ่าย | เวลาซ่อม")
        st.caption(year_label)
        by_cat2 = (df.groupby("หมวด", as_index=False)
                   .agg(งาน=("หมวด", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"), นาที=("นาที", "sum")))
        by_cat2["ชั่วโมง"] = by_cat2["นาที"] / 60
        d1, d2, d3 = st.columns(3)
        for col_st, (field, fmt, label) in zip(
                (d1, d2, d3),
                [("งาน", ",", "จำนวนงาน"), ("ค่าใช้จ่าย", ",.0f", "ค่าใช้จ่าย (บาท)"), ("ชั่วโมง", ",.0f", "เวลาซ่อม (ชม.)")]):
            with col_st:
                st.markdown(f"**{label}**")
                tot_f = by_cat2[field].sum()
                dd = by_cat2.copy()
                dd["สัดส่วน"] = dd[field] / tot_f if tot_f else 0
                tips = [alt.Tooltip("หมวด:N"), alt.Tooltip(f"{field}:Q", format=fmt, title=label),
                        alt.Tooltip("สัดส่วน:Q", format=".1%")]
                arc = alt.Chart(dd).mark_arc(innerRadius=52, padAngle=0.02, cornerRadius=3).encode(
                    theta=alt.Theta(f"{field}:Q", stack=True),
                    color=alt.Color("หมวด:N", scale=CAT_SCALE,
                                    legend=alt.Legend(orient="bottom", title=None, labelLimit=140)),
                    tooltip=tips)
                # ป้าย % เฉพาะชิ้นที่ใหญ่พอ ไม่ให้ตัวเลขทับกัน
                pct = alt.Chart(dd[dd["สัดส่วน"] >= 0.06]).mark_text(radius=88, fontSize=11).encode(
                    theta=alt.Theta(f"{field}:Q", stack=True),
                    text=alt.Text("สัดส่วน:Q", format=".0%"), tooltip=tips)
                st.altair_chart((arc + pct).properties(height=260))

    # ---------- Electric / Mechanical ----------
    with st.container(border=True):
        st.subheader("ประเภทงาน Electric / Mechanical รายปี")
        df_em = df_cats_all_years[df_cats_all_years["ประเภทงาน"] != "อื่นๆ/ไม่ระบุ"]
        if df_em.empty:
            st.info("หมวดที่เลือกไม่มีการบันทึกประเภทงาน Electric/Mechanical (มีเฉพาะหมวดเครื่องจักรและซ่อมสร้าง)")
        else:
            by_em = df_em.groupby(["ปี", "ประเภทงาน"], as_index=False).agg(
                งาน=("ประเภทงาน", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"))
            # ยอดรวมรายปี + %เทียบปีก่อน (ทั้ง Electric และ Mechanical รวมกัน)
            em_yoy = yoy_frame(by_em, "ปี", ["งาน", "ค่าใช้จ่าย"])
            # %เทียบปีก่อนแยกราย Electric/Mechanical — ใส่ไว้ใน tooltip
            by_em = by_em.sort_values(["ประเภทงาน", "ปี"]).reset_index(drop=True)
            for c in ("งาน", "ค่าใช้จ่าย"):
                by_em[f"YoY_{c}"] = by_em.groupby("ประเภทงาน")[c].pct_change()

            def em_chart(value_col, title, axis_format, tip_title):
                head = float(em_yoy[value_col].max()) * 1.16
                bars = alt.Chart(by_em).mark_bar().encode(
                    x=alt.X("ปี:O", title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y(f"{value_col}:Q", title=title,
                            axis=alt.Axis(format=axis_format),
                            scale=alt.Scale(domainMax=head, nice=False)),
                    color=alt.Color("ประเภทงาน:N", scale=EM_SCALE,
                                    legend=alt.Legend(orient="bottom", title=None)),
                    tooltip=[alt.Tooltip("ปี:O"), alt.Tooltip("ประเภทงาน:N"),
                             alt.Tooltip(f"{value_col}:Q", format=",.0f", title=tip_title),
                             alt.Tooltip(f"YoY_{value_col}:Q", format="+.1%",
                                         title="เทียบปีก่อน (เฉพาะประเภทนี้)")])
                total_lbl = alt.Chart(em_yoy).mark_text(dy=-19, fontSize=11).encode(
                    x=alt.X("ปี:O"), y=alt.Y(f"{value_col}:Q"),
                    text=alt.Text(f"{value_col}:Q", format=",.3~s"))
                yoy_lbl = alt.Chart(em_yoy).mark_text(dy=-6, fontSize=11, fontWeight="bold").encode(
                    x=alt.X("ปี:O"), y=alt.Y(f"{value_col}:Q"),
                    text=alt.Text(f"ป้าย_{value_col}:N"),
                    tooltip=[alt.Tooltip("ปี:O"),
                             alt.Tooltip(f"{value_col}:Q", format=",.0f", title=f"{tip_title} รวมทั้งปี"),
                             alt.Tooltip(f"YoY_{value_col}:Q", format="+.1%", title="เทียบปีก่อน")])
                return (bars + total_lbl + yoy_lbl).properties(height=300)

            e1, e2 = st.columns(2)
            with e1:
                st.markdown("**จำนวนงาน**")
                st.altair_chart(em_chart("งาน", "จำนวนงาน", ",.0f", "จำนวนงาน"))
            with e2:
                st.markdown("**ค่าใช้จ่าย (บาท)**")
                st.altair_chart(em_chart("ค่าใช้จ่าย", "บาท", "~s", "ค่าใช้จ่าย (บาท)"))
            st.caption(
                "ตัวเลขบนแท่ง = ยอดรวมทั้งปี · บรรทัดล่าง ▲/▼ = % เทียบปีก่อน (รวมทั้ง Electric และ Mechanical) · "
                "ชี้ที่แท่งเพื่อดู % เทียบปีก่อนแยกแต่ละประเภท · "
                "นับเฉพาะรายการที่ระบุประเภทงาน (ส่วนใหญ่อยู่ในหมวดเครื่องจักรและซ่อมสร้าง) · "
                "ปี 2026 มีข้อมูลถึง ก.ค. ตัวเลข YoY จึงยังเทียบไม่เต็มปี")

    # ---------- วิเคราะห์ Module (หมวดเครื่องจักร) ----------
    with st.container(border=True):
        st.subheader("วิเคราะห์ Module — หมวดเครื่องจักร")
        d_mod = df[(df["หมวด"] == "เครื่องจักร")
                   & (~df["โมดูล"].isin(["", "nan", "None"]))].copy()
        if "เครื่องจักร" not in cats:
            st.info("เลือกหมวด \"เครื่องจักร\" ในตัวกรองก่อน จึงจะแสดงการวิเคราะห์ Module ได้")
        elif d_mod.empty:
            st.info("ไม่มีรายการที่ระบุ Module ตามตัวกรองปัจจุบัน")
        else:
            d_mod["โมดูลเต็ม"] = d_mod["โมดูล"] + " · " + d_mod["ชื่อโมดูล"]
            n_total_mach = len(df[df["หมวด"] == "เครื่องจักร"])
            st.caption(
                f"{year_label} · ระบุโมดูล {len(d_mod):,} จาก {n_total_mach:,} รายการของหมวดเครื่องจักร "
                f"({len(d_mod)/n_total_mach:.0%})")

            module_view = st.segmented_control(
                "มุมมอง", ["สรุปรวม", "รายเดือน"], default="สรุปรวม", key="module_view")

            if module_view == "รายเดือน":
                mv1, mv2 = st.columns(2)
                with mv1:
                    month_metric = st.segmented_control(
                        "ค่าที่แสดง", ["จำนวนงาน", "ค่าใช้จ่าย"], default="จำนวนงาน", key="module_month_metric")
                with mv2:
                    mod_list = sorted(d_mod["โมดูล"].unique().tolist())
                    name_map = (d_mod.drop_duplicates("โมดูล").set_index("โมดูล")["ชื่อโมดูล"].to_dict())
                    focus = st.selectbox(
                        "เจาะโมดูล", ["ทุกโมดูล"] + mod_list,
                        format_func=lambda m: m if m == "ทุกโมดูล" else f"{m} · {name_map.get(m, '')}",
                        key="module_focus")
                mval = "งาน" if month_metric == "จำนวนงาน" else "ค่าใช้จ่าย"
                mfmt = "," if month_metric == "จำนวนงาน" else ",.0f"

                if focus == "ทุกโมดูล":
                    st.markdown(f"**{month_metric}ราย Module รายเดือน**")
                    mm = (d_mod.groupby(["เดือนปี", "โมดูล", "ชื่อโมดูล"], as_index=False)
                          .agg(งาน=("โมดูล", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum")))
                    month_order = sorted(mm["เดือนปี"].unique().tolist())
                    mm["เดือนป้าย"] = mm["เดือนปี"].dt.strftime("%m/%y")
                    label_order = [pd.Timestamp(t).strftime("%m/%y") for t in month_order]
                    mm_tips = [alt.Tooltip("เดือนป้าย:N", title="เดือน"), alt.Tooltip("โมดูล:N"),
                               alt.Tooltip("ชื่อโมดูล:N"), alt.Tooltip("งาน:Q", format=","),
                               alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")]
                    mm_base = alt.Chart(mm).encode(
                        x=alt.X("เดือนป้าย:N", sort=label_order, title="เดือน (ดด/ปป)",
                                axis=alt.Axis(labelAngle=-60, labelOverlap="parity", labelFontSize=10)),
                        y=alt.Y("โมดูล:N", sort=mod_list, title=None))
                    ch = mm_base.mark_rect(cornerRadius=2).encode(
                        color=alt.Color(f"{mval}:Q", scale=alt.Scale(scheme="blues", type="sqrt"),
                                        legend=alt.Legend(title=month_metric, format="~s")),
                        tooltip=mm_tips)
                    # เดือนไม่เยอะ (เลือกปีเดียว) จึงใส่ตัวเลขในช่องได้โดยไม่รก
                    if len(label_order) <= 14:
                        ch = ch + mm_base.mark_text(fontSize=10, baseline="middle").encode(
                            text=alt.Text(f"{mval}:Q", format=",.3~s"),
                            color=alt.condition(alt.datum[mval] > mm[mval].quantile(0.6),
                                                alt.value("#ffffff"), alt.value("#52514e")),
                            tooltip=mm_tips)
                    st.altair_chart(ch.properties(height=max(300, 26 * len(mod_list))))
                    if year_sel == "ทั้งหมด":
                        st.caption(f"กำลังแสดง {len(label_order)} เดือน (2020–2026) จึงย่อป้ายเดือนเหลือเว้นช่อง — "
                                   "เลือกปีในตัวกรองด้านซ้ายเพื่อดูตัวเลขในทุกช่อง")
                else:
                    d_f = d_mod[d_mod["โมดูล"] == focus]
                    st.markdown(f"**{focus} · {name_map.get(focus, '')} — {month_metric}รายเดือน**")
                    fm = (d_f.groupby("เดือนปี", as_index=False)
                          .agg(งาน=("โมดูล", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum")))
                    ch = alt.Chart(fm).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3,
                                                color="#2a78d6").encode(
                        x=alt.X("yearmonth(เดือนปี):T", title=None, axis=alt.Axis(format="%m/%Y")),
                        y=alt.Y(f"{mval}:Q", title=month_metric, axis=alt.Axis(format="~s")),
                        tooltip=[alt.Tooltip("yearmonth(เดือนปี):T", title="เดือน", format="%m/%Y"),
                                 alt.Tooltip("งาน:Q", format=","),
                                 alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")],
                    ).properties(height=240)
                    st.altair_chart(ch)

                    st.markdown(f"**เครื่อง × เดือน ของโมดูล {focus}**")
                    top_mach_f = d_f["รหัสเครื่อง"].value_counts().nlargest(20).index.tolist()
                    fmm = (d_f[d_f["รหัสเครื่อง"].isin(top_mach_f)]
                           .groupby(["รหัสเครื่อง", "เดือนปี"], as_index=False)
                           .agg(งาน=("โมดูล", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum")))
                    month_order_f = sorted(fmm["เดือนปี"].unique().tolist())
                    fmm["เดือนป้าย"] = fmm["เดือนปี"].dt.strftime("%m/%y")
                    label_order_f = [pd.Timestamp(t).strftime("%m/%y") for t in month_order_f]
                    fmm_tips = [alt.Tooltip("รหัสเครื่อง:N"), alt.Tooltip("เดือนป้าย:N", title="เดือน"),
                                alt.Tooltip("งาน:Q", format=","),
                                alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")]
                    fmm_base = alt.Chart(fmm).encode(
                        x=alt.X("เดือนป้าย:N", sort=label_order_f, title="เดือน (ดด/ปป)",
                                axis=alt.Axis(labelAngle=-60, labelOverlap="parity", labelFontSize=10)),
                        y=alt.Y("รหัสเครื่อง:N", sort=top_mach_f, title=None))
                    ch = fmm_base.mark_rect(cornerRadius=2).encode(
                        color=alt.Color(f"{mval}:Q", scale=alt.Scale(scheme="blues", type="sqrt"),
                                        legend=alt.Legend(title=month_metric, format="~s")),
                        tooltip=fmm_tips)
                    if len(label_order_f) <= 14:
                        ch = ch + fmm_base.mark_text(fontSize=10, baseline="middle").encode(
                            text=alt.Text(f"{mval}:Q", format=",.3~s"),
                            color=alt.condition(alt.datum[mval] > fmm[mval].quantile(0.6),
                                                alt.value("#ffffff"), alt.value("#52514e")),
                            tooltip=fmm_tips)
                    st.altair_chart(ch.properties(height=max(260, 24 * len(top_mach_f))))
                    st.caption(f"แสดง {len(top_mach_f)} เครื่องที่มีงานโมดูลนี้บ่อยสุด · สีเข้ม = ค่ามาก")

            if module_view == "สรุปรวม":
                by_mod = (d_mod.groupby("โมดูลเต็ม", as_index=False)
                          .agg(งาน=("โมดูลเต็ม", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"), นาที=("นาที", "sum")))
                by_mod["ชั่วโมง"] = by_mod["นาที"] / 60
                mod_axis = alt.Axis(labelLimit=320, labelFontSize=11)
                mod_h = max(340, 26 * len(by_mod))
                m1, m2 = st.columns(2)
                with m1:
                    st.markdown("**จำนวนงานตาม Module**")
                    base = alt.Chart(by_mod).encode(
                        y=alt.Y("โมดูลเต็ม:N", sort="-x", title=None, axis=mod_axis),
                        x=alt.X("งาน:Q", title="จำนวนงาน",
                                scale=alt.Scale(nice=True, padding=0)),
                        tooltip=[alt.Tooltip("โมดูลเต็ม:N", title="Module"),
                                 alt.Tooltip("งาน:Q", format=","),
                                 alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)"),
                                 alt.Tooltip("ชั่วโมง:Q", format=",.0f", title="เวลาซ่อม (ชม.)")])
                    ch = (base.mark_bar(cornerRadiusEnd=4, color="#2a78d6")
                          + base.mark_text(align="left", dx=4, fontSize=11).encode(
                              text=alt.Text("งาน:Q", format=",")))
                    st.altair_chart(ch.properties(height=mod_h))
                with m2:
                    st.markdown("**ค่าใช้จ่ายตาม Module (บาท)**")
                    base = alt.Chart(by_mod).encode(
                        y=alt.Y("โมดูลเต็ม:N", sort="-x", title=None, axis=mod_axis),
                        x=alt.X("ค่าใช้จ่าย:Q", title="บาท", axis=alt.Axis(format="~s")),
                        tooltip=[alt.Tooltip("โมดูลเต็ม:N", title="Module"),
                                 alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)"),
                                 alt.Tooltip("งาน:Q", format=",")])
                    ch = (base.mark_bar(cornerRadiusEnd=4, color="#2a78d6")
                          + base.mark_text(align="left", dx=4, fontSize=11).encode(
                              text=alt.Text("ค่าใช้จ่าย:Q", format=",.3~s")))
                    st.altair_chart(ch.properties(height=mod_h))

                st.markdown("**Matrix เครื่อง × Module**")
                mx1, mx2 = st.columns([1, 1])
                with mx1:
                    matrix_metric = st.segmented_control(
                        "ค่าในตาราง", ["จำนวนงาน", "ค่าใช้จ่าย"], default="จำนวนงาน", key="matrix_metric")
                with mx2:
                    n_mach = st.slider("จำนวนเครื่องที่แสดง (เรียงตามจำนวนงาน)", 10, 40, 20, key="matrix_n")
                top_mach = (d_mod["รหัสเครื่อง"].value_counts().nlargest(n_mach).index.tolist())
                mat = (d_mod[d_mod["รหัสเครื่อง"].isin(top_mach)]
                       .groupby(["รหัสเครื่อง", "โมดูล", "ชื่อโมดูล"], as_index=False)
                       .agg(งาน=("โมดูล", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum")))
                val_field = "งาน" if matrix_metric == "จำนวนงาน" else "ค่าใช้จ่าย"
                mod_order = sorted(mat["โมดูล"].unique().tolist())
                cell_tips = [alt.Tooltip("รหัสเครื่อง:N"), alt.Tooltip("โมดูล:N"),
                             alt.Tooltip("ชื่อโมดูล:N"), alt.Tooltip("งาน:Q", format=","),
                             alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")]
                mx_base = alt.Chart(mat).encode(
                    x=alt.X("โมดูล:N", sort=mod_order, title="Module", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("รหัสเครื่อง:N", sort=top_mach, title=None))
                cells = mx_base.mark_rect(cornerRadius=2).encode(
                    color=alt.Color(f"{val_field}:Q",
                                    scale=alt.Scale(scheme="blues", type="sqrt"),
                                    legend=alt.Legend(title=matrix_metric, format="~s")),
                    tooltip=cell_tips)
                # ตัวเลขในช่อง — สีขาวบนช่องเข้ม เพื่ออ่านค่าได้โดยไม่ต้องชี้
                cell_text = mx_base.mark_text(fontSize=10, baseline="middle").encode(
                    text=alt.Text(f"{val_field}:Q", format=",.3~s"),
                    color=alt.condition(
                        alt.datum[val_field] > mat[val_field].quantile(0.6),
                        alt.value("#ffffff"), alt.value("#52514e")),
                    tooltip=cell_tips)
                st.altair_chart((cells + cell_text).properties(
                    height=max(300, 22 * len(top_mach))))
                st.caption(f"ตัวเลขในช่อง = {matrix_metric} · สีเข้ม = ค่ามาก · "
                           "ช่องว่าง = ไม่มีงานซ่อมโมดูลนั้นของเครื่องนั้น · ชี้ที่ช่องเพื่อดูชื่อโมดูลเต็ม")

    # ---------- Pareto เครื่องจักร ----------
    with st.container(border=True):
        st.subheader("Pareto เครื่องจักร")
        metric_sel = st.segmented_control(
            "จัดอันดับตาม", ["ค่าใช้จ่าย", "เวลาซ่อม"], default="ค่าใช้จ่าย", key="pareto_metric")
        dfm = df[~df["รหัสเครื่อง"].isin(BAD_CODES)]
        agg_m = (dfm.groupby("รหัสเครื่อง", as_index=False)
                 .agg(ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"), นาที=("นาที", "sum"), งาน=("รหัสเครื่อง", "size")))
        agg_m["ชั่วโมง"] = agg_m["นาที"] / 60
        val_col = "ค่าใช้จ่าย" if metric_sel == "ค่าใช้จ่าย" else "ชั่วโมง"
        unit = "บาท" if metric_sel == "ค่าใช้จ่าย" else "ชม."
        total_val = agg_m[val_col].sum()
        top = agg_m.nlargest(15, val_col).reset_index(drop=True)
        if total_val > 0 and not top.empty:
            top["สัดส่วน"] = top[val_col] / total_val
            top["สะสม"] = top["สัดส่วน"].cumsum()
            order = top["รหัสเครื่อง"].tolist()
            tips = [alt.Tooltip("รหัสเครื่อง:N"),
                    alt.Tooltip(f"{val_col}:Q", format=",.0f", title=f"{metric_sel} ({unit})"),
                    alt.Tooltip("งาน:Q", format=","),
                    alt.Tooltip("สัดส่วน:Q", format=".1%", title="สัดส่วนของทั้งหมด"),
                    alt.Tooltip("สะสม:Q", format=".1%", title="สะสม")]
            # แกนเดียวต่อกราฟ — แท่ง = ค่าจริง, เส้น = สัดส่วนสะสม (แยกกราฟไม่ให้สเกลกลบกัน)
            bars = alt.Chart(top).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3,
                                           color="#2a78d6").encode(
                x=alt.X("รหัสเครื่อง:N", sort=order, title=None, axis=alt.Axis(labels=False, ticks=False)),
                y=alt.Y(f"{val_col}:Q", title=f"{metric_sel} ({unit})", axis=alt.Axis(format="~s")),
                tooltip=tips)
            bar_text = alt.Chart(top).mark_text(dy=-7, fontSize=11).encode(
                x=alt.X("รหัสเครื่อง:N", sort=order, title=None, axis=None),
                y=alt.Y(f"{val_col}:Q"),
                text=alt.Text(f"{val_col}:Q", format=",.3~s"))
            st.altair_chart((bars + bar_text).properties(height=250))

            rule80 = alt.Chart(pd.DataFrame({"y": [0.8]})).mark_rule(
                strokeDash=[5, 4], color="#898781").encode(y="y:Q")
            line = alt.Chart(top).mark_line(point=alt.OverlayMarkDef(size=45), strokeWidth=2,
                                            color="#e34948").encode(
                x=alt.X("รหัสเครื่อง:N", sort=order, title=None, axis=alt.Axis(labelAngle=-45)),
                y=alt.Y("สะสม:Q", title="สัดส่วนสะสม",
                        axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                tooltip=tips)
            st.altair_chart((line + rule80).properties(height=200))

            # กี่เครื่องแรกถึงจะกิน 80% ของทั้งหมด (นับจากเครื่องทั้งชุด ไม่ใช่แค่ Top 15)
            cum_all = agg_m.sort_values(val_col, ascending=False)[val_col].cumsum() / total_val
            n80 = int((cum_all < 0.8).sum()) + 1
            st.caption(
                f"บน = {metric_sel}จริงของ Top 15 · ล่าง = สัดส่วนสะสม (เส้นประ = 80%) · "
                f"Top 15 จาก {len(agg_m):,} เครื่อง คิดเป็น {top['สัดส่วน'].sum():.0%} ของ{metric_sel}ทั้งหมด · "
                f"ต้องรวม {n80:,} เครื่องแรกจึงจะครบ 80% ของทั้งหมด · {year_label}")
        else:
            st.info("ไม่มีข้อมูลเครื่องตามตัวกรองปัจจุบัน")

    # ---------- เจาะรายเครื่อง: ปัญหา-สาเหตุ ----------
    with st.container(border=True):
        st.subheader("เจาะรายเครื่อง — ประเภทปัญหาและกลุ่มสาเหตุ")
        if ps_all.empty:
            st.info(f"ไม่พบไฟล์ {PS_FILE} ในโฟลเดอร์ข้อมูล")
        else:
            dfm_all = df[~df["รหัสเครื่อง"].isin(BAD_CODES)]
            mc_rank = (dfm_all.groupby("รหัสเครื่อง")
                       .agg(งาน=("รหัสเครื่อง", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"))
                       .sort_values("ค่าใช้จ่าย", ascending=False))
            options = mc_rank.index.tolist()
            if not options:
                st.info("ไม่มีเครื่องตามตัวกรองปัจจุบัน")
            else:
                mc = st.selectbox(
                    "เลือกเครื่อง (เรียงตามค่าใช้จ่ายสะสม)", options,
                    format_func=lambda m: f"{m} — {mc_rank.loc[m, 'งาน']:,.0f} งาน · {mc_rank.loc[m, 'ค่าใช้จ่าย']:,.0f} บาท")
                ps_m = ps[ps["รหัสเครื่อง"] == mc]
                d_m = dfm_all[dfm_all["รหัสเครื่อง"] == mc]
                with st.container(horizontal=True):
                    st.metric("งานซ่อม", f"{len(d_m):,.0f} งาน", border=True)
                    st.metric("ค่าใช้จ่ายสะสม", f"{d_m['ค่าใช้จ่าย'].sum():,.0f} บาท", border=True)
                    st.metric("เวลาซ่อมสะสม", f"{d_m['นาที'].sum()/60:,.0f} ชม.", border=True)
                    st.metric("BM", f"{int((d_m['สถานะ']=='BM').sum()):,} ครั้ง", border=True)
                if ps_m.empty:
                    st.info("เครื่องนี้ไม่มีข้อมูลในไฟล์วิเคราะห์ปัญหา-สาเหตุ (ตามตัวกรองปี)")
                else:
                    p1, p2 = st.columns(2)
                    for col_st, field in ((p1, "ประเภทปัญหา"), (p2, "กลุ่มสาเหตุ")):
                        with col_st:
                            st.markdown(f"**{field}**")
                            cnt = (ps_m[~ps_m[field].isin(["", "nan", "None"])]
                                   .groupby(field, as_index=False).agg(ครั้ง=(field, "size"))
                                   .nlargest(8, "ครั้ง"))
                            base = alt.Chart(cnt).encode(
                                y=alt.Y(f"{field}:N", sort="-x", title=None,
                                        axis=alt.Axis(labelLimit=260, labelFontSize=11)),
                                x=alt.X("ครั้ง:Q", title="จำนวนครั้ง",
                                        scale=alt.Scale(domainMax=float(cnt["ครั้ง"].max()) * 1.15, nice=False)),
                                tooltip=[alt.Tooltip(f"{field}:N"), alt.Tooltip("ครั้ง:Q", format=",")])
                            ch = (base.mark_bar(cornerRadiusEnd=4, color="#2a78d6")
                                  + base.mark_text(align="left", dx=4, fontSize=11).encode(
                                      text=alt.Text("ครั้ง:Q", format=",")))
                            st.altair_chart(ch.properties(height=max(240, 30 * len(cnt))))
                    with st.expander(f"ประวัติการซ่อมของ {mc} ({len(ps_m):,} รายการ)"):
                        hist = ps_m.sort_values("วันที่แจ้ง", ascending=False)[
                            ["วันที่แจ้ง", "ประเภทปัญหา", "กลุ่มสาเหตุ", "ปัญหา", "วิเคราะห์สาเหตุ", "การแก้ไข", "นาที", "ค่าใช้จ่าย"]]
                        st.dataframe(
                            hist, hide_index=True, height=350,
                            column_config={"วันที่แจ้ง": st.column_config.DateColumn("วันที่แจ้ง", format="DD/MM/YYYY")})

    # ---------- ข้อสังเกตสำคัญ ----------
    with st.container(border=True):
        st.subheader("ข้อสังเกตสำคัญ")
        insights = []
        yr_cost = df_cats_all_years.groupby("ปี")["ค่าใช้จ่าย"].sum()
        if not yr_cost.empty and yr_cost.sum() > 0:
            y_max = int(yr_cost.idxmax())
            insights.append(
                f"ปีที่ค่าใช้จ่ายสูงสุดคือ **{y_max}** ({yr_cost.max()/1e6:,.1f} ลบ. "
                f"คิดเป็น {yr_cost.max()/yr_cost.sum():.0%} ของค่าใช้จ่ายทั้งหมดในช่วงข้อมูล)")
        d_mach = df_all[df_all["หมวด"] == "เครื่องจักร"]
        if not d_mach.empty:
            bm_pct = (d_mach["สถานะ"] == "BM").mean()
            pm_pct = (d_mach["สถานะ"] == "PM").mean()
            insights.append(
                f"หมวดเครื่องจักร: PM {pm_pct:.0%} เทียบ BM {bm_pct:.0%} — "
                + ("สัดส่วน BM ยังสูง ควรทบทวนแผน PM ของเครื่องที่เสียซ้ำ" if bm_pct > 0.25
                   else "สัดส่วน PM สูงกว่า BM ชัดเจน"))
        dfm_i = df[~df["รหัสเครื่อง"].isin(BAD_CODES)]
        if not dfm_i.empty:
            top1 = dfm_i.groupby("รหัสเครื่อง")["ค่าใช้จ่าย"].sum().nlargest(1)
            insights.append(
                f"เครื่องที่ค่าใช้จ่ายสะสมสูงสุด ({year_label}) คือ **{top1.index[0]}** ({top1.iloc[0]:,.0f} บาท)")
        dfd_i = df[~df["หน่วยงาน"].isin(["", "nan", "None"])]
        if not dfd_i.empty:
            top_d = dfd_i["หน่วยงาน"].value_counts()
            insights.append(
                f"หน่วยงานที่แจ้งซ่อมมากที่สุดคือ **{top_d.index[0]}** ({top_d.iloc[0]:,} งาน "
                f"คิดเป็น {top_d.iloc[0]/len(dfd_i):.0%} ของงานที่ระบุหน่วยงาน)")
        if not ps.empty:
            pv = ps[~ps["ประเภทปัญหา"].isin(["", "nan", "None"])]["ประเภทปัญหา"].value_counts()
            cv = ps[~ps["กลุ่มสาเหตุ"].isin(["", "nan", "None"])]["กลุ่มสาเหตุ"].value_counts()
            if not pv.empty and not cv.empty:
                insights.append(
                    f"จากไฟล์วิเคราะห์ปัญหา-สาเหตุ: ประเภทปัญหาอันดับ 1 คือ **{pv.index[0]}** ({pv.iloc[0]:,} ครั้ง) "
                    f"และกลุ่มสาเหตุอันดับ 1 คือ **{cv.index[0]}** ({cv.iloc[0]:,} ครั้ง)")
        if len(df):
            avg_min, med = df["นาที"].mean(), df["นาที"].median()
            n_long = int((df["นาที"] >= 1440).sum())
            if avg_min > med * 3:
                insights.append(
                    f"เวลาซ่อม: มัธยฐาน **{med:,.0f} นาที/ใบ** แต่ค่าเฉลี่ยสูงถึง **{avg_min:,.0f} นาที** เพราะมี "
                    f"**{n_long:,} ใบ** ที่บันทึกเวลาแบบเหมาเป็นวัน (เช่น '30วัน' = 43,200 นาที) — "
                    "ยอด \"ชั่วโมงซ่อมรวม\" จึงเป็นเวลาตั้งแต่แจ้งจนปิดงาน ไม่ใช่ชั่วโมงช่างทำงานจริง")
        for i in insights:
            st.markdown("- " + i)
        if not insights:
            st.info("ไม่มีข้อมูลพอสำหรับสรุปข้อสังเกตตามตัวกรองปัจจุบัน")

# ==================== แท็บโปรไฟล์เครื่องจักร ====================
with tab_mc:
    mt_rng = ("—" if mtbf_all.empty else
              f"{mtbf_all['เริ่ม'].min():%d/%m/%Y}–{mtbf_all['เริ่ม'].max():%d/%m/%Y}")
    oe_rng = ("—" if oee_all.empty else
              f"{oee_all['วันที่'].min():%d/%m/%Y}–{oee_all['วันที่'].max():%d/%m/%Y}")
    st.caption(
        "เชื่อม 4 แหล่ง: ทะเบียนเครื่องจักร × ฐาน MTBF-MTTR × ฐาน OEE × ใบงานซ่อม")
    st.warning(
        f"**คนละช่วงเวลากัน — อย่าเทียบตรงๆ**  \n"
        f"• MTBF / MTTR / Breakdown มาจากฐาน MTBF-MTTR ปี 2569: **{mt_rng}**  \n"
        f"• ชั่วโมงเดินเครื่อง / OEE มาจากฐาน OEE ปี 2569: **{oe_rng}**  \n"
        f"• ใบงานซ่อม / ค่าซ่อม เป็นยอด**สะสม 2020–2026** ทั้งหมด  \n"
        f"• แท็บนี้**ไม่ใช้ตัวกรองปี**ในแถบซ้าย (เพราะฐาน MTBF/OEE มีเฉพาะปี 2569)",
        icon=":material/schedule:")
    src_note = []
    if reg_all.empty:
        src_note.append("ทะเบียนเครื่องจักร")
    if mtbf_all.empty:
        src_note.append("ฐาน MTBF-MTTR")
    if oee_all.empty:
        src_note.append("ฐาน OEE")
    if src_note:
        st.warning("อ่านไม่ได้ (ไฟล์ไม่พบหรือถูกเปิดล็อกอยู่): " + " · ".join(src_note)
                   + " — ส่วนที่เกี่ยวข้องจะว่าง กด \"โหลดข้อมูลใหม่\" หลังปิด Excel")

    rep_mc = df_all[(df_all["หมวด"] == "เครื่องจักร")
                    & (~df_all["รหัสเครื่อง"].isin(BAD_CODES))]

    # ---------- ตารางเทียบทุกเครื่อง ----------
    with st.container(border=True):
        st.subheader("ตารางเทียบรายเครื่อง — MTBF · MTTR · OEE · ค่าซ่อม")
        rep_sum = (rep_mc.groupby("รหัสเครื่อง")
                   .agg(**{"ใบงานซ่อม 20-26": ("รหัสเครื่อง", "size"),
                           "ค่าซ่อมสะสม 20-26": ("ค่าใช้จ่าย", "sum"),
                           "ชม.ซ่อม 20-26": ("นาที", lambda s: s.sum() / 60),
                           "BM 20-26": ("สถานะ", lambda s: int((s == "BM").sum())),
                           "PM 20-26": ("สถานะ", lambda s: int((s == "PM").sum()))}))
        prof = rep_sum.copy()
        if not mtbf_all.empty:
            bd = mtbf_all[mtbf_all["ประเภท"] == "Breakdown"].groupby("รหัสเครื่อง")
            bp = mtbf_all[mtbf_all["ประเภท"] == "Maintenance"].groupby("รหัสเครื่อง")
            prof = prof.join(bd.size().rename("Breakdown 69 (ครั้ง)"), how="outer")
            prof = prof.join(bp["นาที"].mean().rename("MTTR 69 (นาที)"), how="outer")
        if not oee_all.empty:
            og = oee_all.groupby("รหัสเครื่อง")
            prof = prof.join((og["เวลาทำงานจริง"].sum() / 60).rename("ชม.เดินเครื่อง 69"), how="outer")
            # เฉลี่ยเฉพาะวันที่เครื่องเดินจริง — รวมวันที่จอดสนิทจะทำให้ค่าต่ำเกินจริง
            run_days = oee_all[oee_all["เวลาทำงานจริง"] > 0].groupby("รหัสเครื่อง")
            prof = prof.join(run_days["OEE"].mean().rename("OEE 69 (%)"), how="outer")
            prof = prof.join(run_days["Availability"].mean().rename("Availability 69 (%)"), how="outer")
        if "ชม.เดินเครื่อง 69" in prof.columns and "Breakdown 69 (ครั้ง)" in prof.columns:
            prof["MTBF 69 (ชม.)"] = (prof["ชม.เดินเครื่อง 69"]
                                     / prof["Breakdown 69 (ครั้ง)"].replace(0, pd.NA))
        if not reg_all.empty:
            for c in ("ชื่อเครื่องจักร", "สถานที่ติดตั้ง", "อายุ (ปี)", "สถานะ"):
                if c in reg_all.columns:
                    prof[c] = prof.index.map(reg_all[c])
        prof.index.name = "รหัสเครื่อง"
        order = [c for c in ["ชื่อเครื่องจักร", "สถานที่ติดตั้ง", "อายุ (ปี)", "สถานะ",
                             "MTBF 69 (ชม.)", "MTTR 69 (นาที)", "Breakdown 69 (ครั้ง)",
                             "ชม.เดินเครื่อง 69", "OEE 69 (%)", "Availability 69 (%)",
                             "ใบงานซ่อม 20-26", "PM 20-26", "BM 20-26",
                             "ค่าซ่อมสะสม 20-26", "ชม.ซ่อม 20-26"] if c in prof.columns]
        st.dataframe(
            prof[order].sort_values("ค่าซ่อมสะสม 20-26", ascending=False),
            height=380,
            column_config={c: st.column_config.NumberColumn(c, format="localized")
                           for c in order if prof[c].dtype.kind in "fi"})
        st.caption("ท้ายชื่อคอลัมน์ = ช่วงข้อมูล (69 = ปี 2569 เท่านั้น · 20-26 = สะสม 2020–2026) · "
                   "คลิกหัวคอลัมน์เพื่อเรียงลำดับ · MTBF = ชั่วโมงเดินเครื่องจริง (ฐาน OEE) ÷ จำนวนครั้ง Breakdown · "
                   "MTTR = เวลาช่างเข้าซ่อมเฉลี่ย (ฐาน MTBF-MTTR) · "
                   "OEE/Availability เฉลี่ยเฉพาะวันที่เครื่องเดินจริง และตัดค่าผิดปกติ (<0% หรือ >100%) ออกแล้ว · "
                   "ชม.ซ่อม อ้างอิงคอลัมน์เวลาซ่อมในใบงานซึ่งบางใบกรอกแบบเหมาเป็นวัน")

    if "MTBF 69 (ชม.)" in prof.columns and prof["MTBF 69 (ชม.)"].notna().any():
        with st.container(border=True):
            st.subheader("15 เครื่องที่ MTBF ต่ำสุด (เสียบ่อยเทียบเวลาเดินเครื่อง)")
            low = (prof.dropna(subset=["MTBF 69 (ชม.)"]).nsmallest(15, "MTBF 69 (ชม.)")
                   .reset_index()
                   .rename(columns={"MTBF 69 (ชม.)": "MTBF", "Breakdown 69 (ครั้ง)": "Breakdown",
                                    "ชม.เดินเครื่อง 69": "เดินเครื่อง"}))
            base = alt.Chart(low).encode(
                y=alt.Y("รหัสเครื่อง:N", sort=low["รหัสเครื่อง"].tolist(), title=None),
                x=alt.X("MTBF:Q", title="MTBF (ชม.เดินเครื่องต่อการเสีย 1 ครั้ง)",
                        scale=alt.Scale(domainMax=float(low["MTBF"].max()) * 1.18, nice=False)),
                tooltip=[alt.Tooltip("รหัสเครื่อง:N"),
                         alt.Tooltip("MTBF:Q", format=",.1f", title="MTBF (ชม.)"),
                         alt.Tooltip("Breakdown:Q", format=",", title="Breakdown (ครั้ง)"),
                         alt.Tooltip("เดินเครื่อง:Q", format=",.0f", title="เดินเครื่อง (ชม.)")])
            ch = (base.mark_bar(cornerRadiusEnd=4, color="#e34948")
                  + base.mark_text(align="left", dx=4, fontSize=11).encode(
                      text=alt.Text("MTBF:Q", format=",.1f")))
            st.altair_chart(ch.properties(height=420))
            st.caption("ข้อมูลปี 2569 เท่านั้น · ยิ่งค่าน้อย = เดินเครื่องได้ไม่นานก็เสีย ควรพิจารณาปรับรอบ PM ก่อนเครื่องอื่น · "
                       "เครื่องที่เดินน้อยชั่วโมงแต่เสีย 2–3 ครั้งจะได้ค่าต่ำมาก ให้ดูคอลัมน์ชั่วโมงเดินเครื่องประกอบ")

    # ---------- เจาะรายเครื่อง ----------
    with st.container(border=True):
        st.subheader("เจาะรายเครื่อง")
        codes = sorted(set(prof.index.astype(str)) | set(reg_all.index.astype(str)))
        codes = [c for c in codes if c and c not in BAD_CODES]
        if not codes:
            st.info("ไม่มีรหัสเครื่องให้เลือก")
        else:
            default_ix = 0
            if not rep_sum.empty:
                top_code = rep_sum["ค่าซ่อมสะสม 20-26"].idxmax()
                if top_code in codes:
                    default_ix = codes.index(top_code)
            mc = st.selectbox("เลือกเครื่อง", codes, index=default_ix, key="profile_mc")

            info = reg_all.loc[mc] if (not reg_all.empty and mc in reg_all.index) else None
            title = f"{mc}"
            if info is not None and pd.notna(info.get("ชื่อเครื่องจักร")):
                title += f" — {info['ชื่อเครื่องจักร']}"
            st.markdown(f"### {title}")

            if info is None:
                st.info("เครื่องนี้ยังไม่มีในทะเบียนเครื่องจักร (แสดงเฉพาะข้อมูลงานซ่อม/MTBF/OEE)")
            else:
                def fld(name, fmt=None):
                    v = info.get(name)
                    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
                        return "—"
                    if isinstance(v, pd.Timestamp):
                        return v.strftime("%d/%m/%Y")
                    if fmt and isinstance(v, (int, float)):
                        return format(v, fmt)
                    return str(v)

                r1 = st.columns(4)
                for col, (lab, key) in zip(r1, [("ยี่ห้อ / รุ่น", None), ("ตระกูล / ประเภท", None),
                                                ("สถานที่ติดตั้ง", "สถานที่ติดตั้ง"),
                                                ("ผู้รับผิดชอบ", "ผู้รับผิดชอบ")]):
                    with col:
                        if lab == "ยี่ห้อ / รุ่น":
                            val = " / ".join(x for x in [fld("ยี่ห้อ"), fld("รุ่น")] if x != "—") or "—"
                        elif lab == "ตระกูล / ประเภท":
                            val = " / ".join(x for x in [fld("ตระกูล"), fld("ประเภท")] if x != "—") or "—"
                        else:
                            val = fld(key)
                        st.caption(lab)
                        st.markdown(f"**{val}**")
                r2 = st.columns(4)
                for col, (lab, key, f) in zip(r2, [("วันที่ติดตั้ง", "วันที่ติดตั้ง", None),
                                                   ("อายุ (ปี)", "อายุ (ปี)", ",.1f"),
                                                   ("ความถี่ PM", "ความถี่ PM", None),
                                                   ("สถานะ", "สถานะ", None)]):
                    with col:
                        st.caption(lab)
                        st.markdown(f"**{fld(key, f)}**")

            d_one = rep_mc[rep_mc["รหัสเครื่อง"] == mc]
            ev_one = mtbf_all[mtbf_all["รหัสเครื่อง"] == mc] if not mtbf_all.empty else pd.DataFrame()
            oee_one = oee_all[oee_all["รหัสเครื่อง"] == mc] if not oee_all.empty else pd.DataFrame()
            n_bd = int((ev_one["ประเภท"] == "Breakdown").sum()) if not ev_one.empty else 0
            run_h = oee_one["เวลาทำงานจริง"].sum() / 60 if not oee_one.empty else 0
            mtbf_h = run_h / n_bd if n_bd else None
            mttr_m = (ev_one[ev_one["ประเภท"] == "Maintenance"]["นาที"].mean()
                      if not ev_one.empty and (ev_one["ประเภท"] == "Maintenance").any() else None)

            st.markdown("")
            st.caption("จากใบงานซ่อมสะสม 2020–2026")
            with st.container(horizontal=True):
                st.metric("ใบงานซ่อมสะสม", f"{len(d_one):,} ใบ", border=True)
                st.metric("ค่าซ่อมสะสม", f"{d_one['ค่าใช้จ่าย'].sum():,.0f} บาท", border=True)
                st.metric("เวลาซ่อมมัธยฐาน", f"{d_one['นาที'].median():,.0f} นาที/ใบ" if len(d_one) else "—",
                          border=True, help="ค่ากลางต่อใบงาน — ทนต่อใบที่กรอกเวลาแบบเหมาเป็นวัน")
                st.metric("PM / BM", f"{int((d_one['สถานะ']=='PM').sum()):,} / {int((d_one['สถานะ']=='BM').sum()):,}",
                          border=True)
            st.caption("จากฐาน MTBF-MTTR และฐาน OEE — ปี 2569 เท่านั้น")
            with st.container(horizontal=True):
                st.metric("Breakdown", f"{n_bd:,} ครั้ง", border=True)
                st.metric("MTBF", f"{mtbf_h:,.1f} ชม." if mtbf_h else "—", border=True,
                          help="ชั่วโมงเดินเครื่องจริงต่อการเสีย 1 ครั้ง (ยิ่งมากยิ่งดี)")
                st.metric("MTTR", f"{mttr_m:,.0f} นาที" if mttr_m else "—", border=True,
                          help="เวลาช่างเข้าซ่อมเฉลี่ยต่อครั้ง (ยิ่งน้อยยิ่งดี)")
                oee_run = oee_one[oee_one["เวลาทำงานจริง"] > 0] if not oee_one.empty else pd.DataFrame()
                st.metric("OEE เฉลี่ย", f"{oee_run['OEE'].mean():,.1f}%"
                          if not oee_run.empty and oee_run["OEE"].notna().any() else "—", border=True,
                          help="เฉลี่ยเฉพาะวันที่เครื่องเดินจริง ตัดค่าผิดปกติ (<0% หรือ >100%) ออกแล้ว")

            g1, g2 = st.columns(2)
            with g1:
                st.markdown("**งานซ่อมและค่าใช้จ่ายรายปี**")
                if d_one.empty:
                    st.info("ไม่มีใบงานซ่อมของเครื่องนี้")
                else:
                    yr = (d_one.groupby("ปี", as_index=False)
                          .agg(ใบงาน=("ปี", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum")))
                    b = alt.Chart(yr).encode(x=alt.X("ปี:O", title=None, axis=alt.Axis(labelAngle=0)))
                    ch = (b.mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2, color="#2a78d6").encode(
                              y=alt.Y("ค่าใช้จ่าย:Q", title="ค่าใช้จ่าย (บาท)", axis=alt.Axis(format="~s"),
                                      scale=alt.Scale(domainMax=float(yr["ค่าใช้จ่าย"].max()) * 1.18, nice=False)),
                              tooltip=[alt.Tooltip("ปี:O"), alt.Tooltip("ใบงาน:Q", format=","),
                                       alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")])
                          + b.mark_text(dy=-7, fontSize=11).encode(
                              y=alt.Y("ค่าใช้จ่าย:Q"), text=alt.Text("ค่าใช้จ่าย:Q", format=",.3~s")))
                    st.altair_chart(ch.properties(height=260))
                    st.caption("แท่ง = ค่าใช้จ่าย · ชี้เพื่อดูจำนวนใบงานของปีนั้น")
            with g2:
                st.markdown("**โมดูลที่ซ่อมบ่อย**")
                dm_one = d_one[~d_one["โมดูล"].isin(BAD_CODES)]
                if dm_one.empty:
                    st.info("ใบงานของเครื่องนี้ยังไม่ระบุ Module")
                else:
                    dm_one = dm_one.assign(โมดูลเต็ม=dm_one["โมดูล"] + " · " + dm_one["ชื่อโมดูล"])
                    cnt = (dm_one.groupby("โมดูลเต็ม", as_index=False)
                           .agg(ใบงาน=("โมดูลเต็ม", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"))
                           .nlargest(8, "ใบงาน"))
                    b = alt.Chart(cnt).encode(
                        y=alt.Y("โมดูลเต็ม:N", sort="-x", title=None,
                                axis=alt.Axis(labelLimit=260, labelFontSize=11)),
                        x=alt.X("ใบงาน:Q", title="จำนวนใบงาน",
                                scale=alt.Scale(domainMax=float(cnt["ใบงาน"].max()) * 1.2, nice=False)),
                        tooltip=[alt.Tooltip("โมดูลเต็ม:N", title="Module"),
                                 alt.Tooltip("ใบงาน:Q", format=","),
                                 alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")])
                    ch = (b.mark_bar(cornerRadiusEnd=4, color="#2a78d6")
                          + b.mark_text(align="left", dx=4, fontSize=11).encode(
                              text=alt.Text("ใบงาน:Q", format=",")))
                    st.altair_chart(ch.properties(height=260))

            g3, g4 = st.columns(2)
            with g3:
                st.markdown("**แนวโน้ม OEE รายเดือน (ปี 2569)**")
                if oee_run.empty or oee_run["OEE"].isna().all():
                    st.info("ไม่มีข้อมูล OEE ของเครื่องนี้")
                else:
                    mo = (oee_run.groupby("เดือนปี", as_index=False)[
                        ["OEE", "Availability", "Performance", "Quality"]].mean())
                    long = mo.melt("เดือนปี", var_name="ตัวชี้วัด", value_name="ค่า").dropna()
                    ch = alt.Chart(long).mark_line(point=alt.OverlayMarkDef(size=35), strokeWidth=2).encode(
                        x=alt.X("yearmonth(เดือนปี):T", title=None, axis=alt.Axis(format="%m/%Y")),
                        y=alt.Y("ค่า:Q", title="%"),
                        color=alt.Color("ตัวชี้วัด:N",
                                        scale=alt.Scale(domain=["OEE", "Availability", "Performance", "Quality"],
                                                        range=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]),
                                        legend=alt.Legend(orient="bottom", title=None)),
                        tooltip=[alt.Tooltip("yearmonth(เดือนปี):T", title="เดือน", format="%m/%Y"),
                                 alt.Tooltip("ตัวชี้วัด:N"), alt.Tooltip("ค่า:Q", format=",.1f", title="%")],
                    ).properties(height=260)
                    st.altair_chart(ch)
                    st.caption("เฉลี่ยเฉพาะวันที่เครื่องเดินจริง · ตัดค่าผิดปกติ (<0% หรือ >100%) ออกแล้ว")
            with g4:
                st.markdown("**เหตุการณ์หยุดเครื่องรายเดือน (ปี 2569)**")
                if ev_one.empty:
                    st.info("ไม่มีเหตุการณ์ในฐาน MTBF-MTTR ของเครื่องนี้")
                else:
                    em = (ev_one.groupby(["เดือนปี", "ประเภท"], as_index=False)
                          .agg(ครั้ง=("ประเภท", "size"), นาที=("นาที", "sum")))
                    em["ประเภท"] = em["ประเภท"].map({"Breakdown": "B - แจ้งเสีย",
                                                     "Maintenance": "BP - ช่างเข้าซ่อม"})
                    ch = alt.Chart(em).mark_bar().encode(
                        x=alt.X("yearmonth(เดือนปี):T", title=None, axis=alt.Axis(format="%m/%Y")),
                        y=alt.Y("ครั้ง:Q", title="จำนวนครั้ง"),
                        color=alt.Color("ประเภท:N",
                                        scale=alt.Scale(domain=["B - แจ้งเสีย", "BP - ช่างเข้าซ่อม"],
                                                        range=["#e34948", "#4a3aa7"]),
                                        legend=alt.Legend(orient="bottom", title=None)),
                        tooltip=[alt.Tooltip("yearmonth(เดือนปี):T", title="เดือน", format="%m/%Y"),
                                 alt.Tooltip("ประเภท:N"), alt.Tooltip("ครั้ง:Q", format=","),
                                 alt.Tooltip("นาที:Q", format=",.0f", title="รวม (นาที)")],
                    ).properties(height=260)
                    st.altair_chart(ch)

            ps_one = ps_all[ps_all["รหัสเครื่อง"] == mc] if not ps_all.empty else pd.DataFrame()
            with st.expander(f"ประวัติการซ่อมของ {mc}"):
                if ps_one.empty:
                    st.dataframe(d_one[["ปี", "เดือน", "หน่วยงาน", "สถานะ", "ประเภทงาน",
                                        "โมดูล", "นาที", "ค่าใช้จ่าย", "ปัญหา"]],
                                 hide_index=True, height=320)
                else:
                    st.dataframe(
                        ps_one.sort_values("วันที่แจ้ง", ascending=False)[
                            ["วันที่แจ้ง", "ประเภทปัญหา", "กลุ่มสาเหตุ", "ปัญหา",
                             "วิเคราะห์สาเหตุ", "การแก้ไข", "นาที", "ค่าใช้จ่าย"]],
                        hide_index=True, height=320,
                        column_config={"วันที่แจ้ง": st.column_config.DateColumn("วันที่แจ้ง", format="DD/MM/YYYY")})

st.caption("แหล่งข้อมูล: ใบงานซ่อม 6 ไฟล์ + วิเคราะห์ปัญหา-สาเหตุ_รายเครื่อง + ทะเบียนเครื่องจักร + ฐาน MTBF-MTTR + ฐาน OEE · "
           "แก้ไฟล์ Excel แล้วกด \"โหลดข้อมูลใหม่\" หรือรอ cache หมดอายุ (1 ชม.)")
