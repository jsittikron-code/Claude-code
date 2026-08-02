# -*- coding: utf-8 -*-
"""Dashboard งานซ่อมบำรุง 6 หมวด (2020-2026) — อ่านข้อมูลสดจากไฟล์ Excel ในโฟลเดอร์ฝ่ายซ่อมบำรุง"""
import os
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


def file_signature():
    """mtime ของทุกไฟล์ — เปลี่ยนเมื่อไฟล์ถูกแก้ ทำให้ cache โหลดใหม่เอง"""
    sig = []
    for fname in FILES.values():
        p = os.path.join(DATA_DIR, fname)
        sig.append(os.path.getmtime(p) if os.path.exists(p) else 0)
    return tuple(sig)


@st.cache_data(ttl="1h", max_entries=3, show_spinner="กำลังอ่านข้อมูลจากไฟล์ Excel ทั้ง 6 ไฟล์...")
def load_data(sig):
    frames, missing = [], []
    for cat, fname in FILES.items():
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            missing.append(fname)
            continue
        try:
            raw = pd.read_excel(path, sheet_name="ข้อมูล", engine="calamine")
        except Exception:
            raw = pd.read_excel(path, sheet_name="ข้อมูล")
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
        df["นาที"] = pd.to_numeric(col("เวลาซ่อม (นาที)"), errors="coerce").fillna(0)
        df["ค่าใช้จ่าย"] = (
            pd.to_numeric(col("ค่าใช้จ่าย (บาท)"), errors="coerce").fillna(0)
            + pd.to_numeric(col("Petty Cash (บาท)"), errors="coerce").fillna(0)
        )
        df["ปัญหา"] = col("ปัญหา").astype(str)
        df = df[df["ปี"].between(2019, 2030) & df["เดือน"].between(1, 12)]
        df["ปี"] = df["ปี"].astype(int)
        df["เดือน"] = df["เดือน"].astype(int)
        df["เดือนปี"] = pd.to_datetime(dict(year=df["ปี"], month=df["เดือน"], day=1))
        frames.append(df)
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return data, missing


# ---------- โหลดข้อมูล ----------
if not os.path.isdir(DATA_DIR):
    st.error(f"ไม่พบโฟลเดอร์ข้อมูล: {DATA_DIR}")
    st.stop()

df_all, missing = load_data(file_signature())
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
        load_data.clear()
        st.rerun()
    newest = max(
        (os.path.getmtime(os.path.join(DATA_DIR, f)) for f in FILES.values()
         if os.path.exists(os.path.join(DATA_DIR, f))), default=0)
    if newest:
        st.caption("ไฟล์อัปเดตล่าสุด: " + datetime.datetime.fromtimestamp(newest).strftime("%d/%m/%Y %H:%M"))

cats = cat_sel or CATS
df = df_all[df_all["หมวด"].isin(cats)]
if year_sel != "ทั้งหมด":
    df = df[df["ปี"] == year_sel]
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
    st.metric("ชั่วโมงซ่อมรวม", f"{hours_total:,.0f} ชม.", border=True)
    st.metric("ค่าใช้จ่ายเฉลี่ย/งาน", f"{(cost_total/n_jobs if n_jobs else 0):,.0f} บาท", border=True)
    st.metric("BM ที่บันทึก", f"{n_bm:,.0f} ครั้ง", border=True)

# ---------- แถวที่ 1: ตามหมวด ----------
by_cat = (df.groupby("หมวด", as_index=False)
          .agg(งาน=("หมวด", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"), นาที=("นาที", "sum")))
c1, c2 = st.columns(2)
with c1, st.container(border=True):
    st.subheader("จำนวนงานซ่อมตามหมวด")
    base = alt.Chart(by_cat).encode(
        y=alt.Y("หมวด:N", sort="-x", title=None),
        x=alt.X("งาน:Q", title="จำนวนงาน"),
        tooltip=[alt.Tooltip("หมวด:N"), alt.Tooltip("งาน:Q", format=","),
                 alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")],
    )
    bars = base.mark_bar(cornerRadiusEnd=4).encode(
        color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=None))
    text = base.mark_text(align="left", dx=4).encode(text=alt.Text("งาน:Q", format=","))
    st.altair_chart((bars + text).properties(height=260))
with c2, st.container(border=True):
    st.subheader("ค่าใช้จ่ายตามหมวด")
    base = alt.Chart(by_cat).encode(
        y=alt.Y("หมวด:N", sort="-x", title=None),
        x=alt.X("ค่าใช้จ่าย:Q", title="บาท", axis=alt.Axis(format="~s")),
        tooltip=[alt.Tooltip("หมวด:N"), alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)"),
                 alt.Tooltip("งาน:Q", format=",")],
    )
    bars = base.mark_bar(cornerRadiusEnd=4).encode(
        color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=None))
    text = base.mark_text(align="left", dx=4).encode(
        text=alt.Text("ค่าใช้จ่าย:Q", format=",.3~s"))
    st.altair_chart((bars + text).properties(height=260))

# ---------- แถวที่ 2: รายปี + PM/BM ----------
c3, c4 = st.columns(2)
with c3, st.container(border=True):
    st.subheader("จำนวนงานรายปี แยกตามหมวด")
    by_year = (df_all[df_all["หมวด"].isin(cats)]
               .groupby(["ปี", "หมวด"], as_index=False).agg(งาน=("หมวด", "size")))
    ch = alt.Chart(by_year).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("ปี:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("งาน:Q", title="จำนวนงาน"),
        color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=[alt.Tooltip("ปี:O"), alt.Tooltip("หมวด:N"), alt.Tooltip("งาน:Q", format=",")],
    ).properties(height=280)
    st.altair_chart(ch)
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

# ---------- แนวโน้มรายเดือน ----------
with st.container(border=True):
    st.subheader("แนวโน้มจำนวนงานรายเดือน")
    by_month = df.groupby(["เดือนปี", "หมวด"], as_index=False).agg(
        งาน=("หมวด", "size"), ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"))
    ch = alt.Chart(by_month).mark_line(point=alt.OverlayMarkDef(size=28), strokeWidth=2).encode(
        x=alt.X("yearmonth(เดือนปี):T", title=None, axis=alt.Axis(format="%m/%Y")),
        y=alt.Y("งาน:Q", title="จำนวนงาน"),
        color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=[alt.Tooltip("yearmonth(เดือนปี):T", title="เดือน", format="%m/%Y"),
                 alt.Tooltip("หมวด:N"), alt.Tooltip("งาน:Q", format=","),
                 alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)")],
    ).properties(height=300).interactive(bind_y=False)
    st.altair_chart(ch)

# ---------- Top 10 ----------
c5, c6 = st.columns(2)
with c5, st.container(border=True):
    st.subheader("Top 10 เครื่อง — ค่าใช้จ่ายสะสมสูงสุด")
    dfm = df[~df["รหัสเครื่อง"].isin(["", "#", "-", "nan", "None"])]
    top_m = (dfm.groupby(["รหัสเครื่อง", "หมวด"], as_index=False)
             .agg(ค่าใช้จ่าย=("ค่าใช้จ่าย", "sum"), งาน=("หมวด", "size"))
             .nlargest(10, "ค่าใช้จ่าย"))
    ch = alt.Chart(top_m).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("รหัสเครื่อง:N", sort="-x", title=None),
        x=alt.X("ค่าใช้จ่าย:Q", title="บาท", axis=alt.Axis(format="~s")),
        color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=[alt.Tooltip("รหัสเครื่อง:N"), alt.Tooltip("หมวด:N"),
                 alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f", title="ค่าใช้จ่าย (บาท)"),
                 alt.Tooltip("งาน:Q", format=",")],
    ).properties(height=300)
    st.altair_chart(ch)
with c6, st.container(border=True):
    st.subheader("Top 10 หน่วยงานที่แจ้งซ่อม")
    dfd = df[~df["หน่วยงาน"].isin(["", "nan", "None"])]
    top_depts = dfd["หน่วยงาน"].value_counts().nlargest(10).index.tolist()
    by_dept = (dfd[dfd["หน่วยงาน"].isin(top_depts)]
               .groupby(["หน่วยงาน", "หมวด"], as_index=False).agg(งาน=("หมวด", "size")))
    ch = alt.Chart(by_dept).mark_bar().encode(
        y=alt.Y("หน่วยงาน:N", sort=top_depts, title=None),
        x=alt.X("งาน:Q", title="จำนวนงาน"),
        color=alt.Color("หมวด:N", scale=CAT_SCALE, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=[alt.Tooltip("หน่วยงาน:N"), alt.Tooltip("หมวด:N"), alt.Tooltip("งาน:Q", format=",")],
    ).properties(height=300)
    st.altair_chart(ch)

# ---------- ตารางสรุป ----------
with st.container(border=True):
    st.subheader("ตารางสรุปตามหมวด")
    summary = (df.groupby("หมวด")
               .agg(งาน=("หมวด", "size"),
                    PM=("สถานะ", lambda s: int((s == "PM").sum())),
                    BM=("สถานะ", lambda s: int((s == "BM").sum())),
                    ค่าใช้จ่าย_บาท=("ค่าใช้จ่าย", "sum"),
                    เวลาซ่อม_ชม=("นาที", lambda s: s.sum() / 60))
               .reindex([c for c in CATS if c in df["หมวด"].unique()]))
    summary["เฉลี่ย_บาทต่องาน"] = (summary["ค่าใช้จ่าย_บาท"] / summary["งาน"].replace(0, pd.NA)).fillna(0)
    total = summary.sum(numeric_only=True)
    total["เฉลี่ย_บาทต่องาน"] = total["ค่าใช้จ่าย_บาท"] / total["งาน"] if total["งาน"] else 0
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

st.caption("แหล่งข้อมูล: ชีต \"ข้อมูล\" ในไฟล์รายงานซ่อมบำรุง 6 ไฟล์ · แก้ไฟล์ Excel แล้วกด \"โหลดข้อมูลใหม่\" หรือรอ cache หมดอายุ (1 ชม.)")
