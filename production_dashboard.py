"""PRODUCTION DASHBOARD — แดชบอร์ดฝ่ายผลิต (สไตล์ infographic หน้าเดียว)
=============================================================================
ติดตามการผลิตแบบเห็นครบจบในหน้าจอเดียว: แผน vs ผลิตจริง · Good/Defect ·
OEE (A/P/Q) · การหยุดเครื่อง · แจ้งเตือนอัตโนมัติ — เทียบเดือนก่อน (MoM) ทุกตัว

ข้อมูลจริงจากฐาน OEE (ชีต Report1) — สูตร cap ชุดเดียวกับระบบบริหาร OEE
รัน: python -m streamlit run production_dashboard.py --server.port 8510
"""

import os
import re
import time

import altair as alt
import pandas as pd
import streamlit as st

import auth

# ---------------------------------------------------------------------------
# แหล่งข้อมูล + ค่าคงที่
# ---------------------------------------------------------------------------
DEPT_DIR = r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD\ฝ่ายซ่อมบำรุงรักษา"
OEE_PATH = os.path.join(DEPT_DIR, r"3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx")

TARGET_OEE = 85.0
TARGET_DEFECT = 3.0     # % ของเสียที่ยอมรับได้

LOSS_DEFS = [
    ("Break_time_b", "Breakdown"), ("Break_time_bp", "Maintenance"),
    ("Break_time_p", "Planned stop"), ("Setup", "Setup / Changeover"),
    ("Break_time_noemp", "No operator"), ("Break_time_S", "Special stop"),
    ("Others", "Others"),
]
LOSS_COLS = [c for c, _ in LOSS_DEFS]

PREFIX_CAT = {
    "CT": "ตัด", "DL": "เจาะ", "EG": "ปิดขอบ", "CO": "พ่นสี", "PO": "ขัด/ปัดเงา",
    "MB": "ขัด/ปัดเงา", "MS": "ขัด/ปัดเงา", "MO": "เพลาตั้ง", "LA": "ปิดผิว",
    "PR": "ปิดผิว", "SF": "ปิดผิว", "AL": "ประกอบ", "AD": "หน่วยงาน",
    "SKL": "หน่วยงาน", "RP": "หน่วยงาน",
}
TH_M = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
        "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

NAVY = "#1e3a8a"
ORANGE = "#ea580c"
BLUE = "#2563eb"
GREEN = "#16a34a"
RED = "#dc2626"
PURPLE = "#7c3aed"
GOLD = "#f59e0b"
INKC = "#334155"


def month_label(ts) -> str:
    return f"{TH_M[ts.month - 1]} {(ts.year + 543) % 100:02d}"


def _read_sheet(path, sheet, header=0):
    last_err = None
    for _ in range(2):
        for engine in ("calamine", None):
            try:
                return pd.read_excel(path, sheet_name=sheet, header=header, engine=engine)
            except PermissionError as e:
                last_err = e
                break
            except Exception as e:
                last_err = e
        time.sleep(1.5)
    raise last_err


def _mtime(path) -> float:
    return os.path.getmtime(path) if os.path.exists(path) else 0.0


def sig() -> tuple:
    return (_mtime(OEE_PATH),)


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านฐานข้อมูลการผลิต...")
def load_prod(_sig):
    """ชีต Report1 → ตารางรายวันรายเครื่อง + กลุ่มเครื่อง (สูตร cap ชุดเดียวกับระบบ OEE)"""
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
    df["Cap"] = col("Cap")
    df["Pieces"] = col("จำนวน(ชิ้น)/วัน")
    df["Good"] = col("ชิ้นงานดี(ชิ้น)/วัน")
    for c in LOSS_COLS:
        df[c] = col(c)
    df = df[df["วันที่"].notna() & (df["Machine"] != "") & (df["Machine"] != "nan")].copy()

    bad = (
        (df["PlanMin"] <= 0) | (df["RunMin"] < 0)
        | ((df["PlanMin"] > 0) & (df["RunMin"] > df["PlanMin"]))
        | (df[LOSS_COLS] < 0).any(axis=1)
        | (df["Pieces"] < 0) | (df["Good"] < 0)
        | ((df["Good"] > df["Pieces"]) & (df["Good"] >= 0))
    )
    df = df[~bad].copy()

    df["RunCap"] = df["RunMin"].clip(lower=0).where(
        df["PlanMin"] <= 0, df[["RunMin", "PlanMin"]].min(axis=1).clip(lower=0))
    df["PieceCap"] = df[["Pieces", "Cap"]].min(axis=1).clip(lower=0).where(df["Cap"] > 0, 0.0)
    df["GoodCap"] = df[["Good", "Pieces"]].min(axis=1).clip(lower=0)
    df["Defect"] = (df["Pieces"] - df["GoodCap"]).clip(lower=0)

    # กลุ่มเครื่อง: ชีต "หมวดหมู่เครื่อง" ก่อน เดารหัสนำหน้าเป็นตัวสำรอง
    grp = pd.Series(pd.NA, index=df.index, dtype="object")
    try:
        cat = _read_sheet(OEE_PATH, "หมวดหมู่เครื่อง", header=3)
        cat.columns = [str(c).strip() for c in cat.columns]
        if "รหัสเครื่อง" in cat.columns and "กลุ่มหลัก" in cat.columns:
            mapping = dict(zip(cat["รหัสเครื่อง"].astype(str).str.strip(),
                               cat["กลุ่มหลัก"].astype(str).str.strip()))
            grp = df["Machine"].map(mapping)
    except Exception:
        pass
    prefix = df["Machine"].str.extract(r"^([A-Za-z]+)")[0].str.upper()
    df["กลุ่ม"] = grp.fillna(prefix.map(PREFIX_CAT)).fillna("อื่นๆ")

    df["เดือนปี"] = df["วันที่"].dt.to_period("M").dt.to_timestamp()
    return df


def month_stats(d: pd.DataFrame) -> dict:
    """สรุปตัวเลขผลิตของชุดแถว (สูตรผลรวมหารผลรวม ชุดเดียวกับระบบ OEE)"""
    base = d[d["Cap"] > 0]
    plan = float(base["Cap"].sum())
    actual = float(d["Pieces"].sum())
    good = float(d["GoodCap"].sum())
    defect = float(d["Defect"].sum())
    p_run = float(base["PlanMin"].sum())
    a = float(base["RunCap"].sum()) / p_run * 100 if p_run > 0 else float("nan")
    p = float(base["PieceCap"].sum()) / plan * 100 if plan > 0 else float("nan")
    prod = base[base["Pieces"] > 0]
    q = (float(prod["GoodCap"].sum()) / float(prod["Pieces"].sum()) * 100
         if float(prod["Pieces"].sum()) > 0 else float("nan"))
    oee = a * p * q / 10000 if not (pd.isna(a) or pd.isna(p) or pd.isna(q)) else float("nan")
    return {
        "plan": plan, "actual": actual, "good": good, "defect": defect,
        "ach": actual / plan * 100 if plan > 0 else float("nan"),
        "defect_rate": defect / actual * 100 if actual > 0 else float("nan"),
        "A": a, "P": p, "Q": q, "OEE": oee,
    }


# ---------------------------------------------------------------------------
# สไตล์ infographic
# ---------------------------------------------------------------------------
APP_CSS = f"""
<style>
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 2.6rem; padding-bottom: 1.4rem; max-width: 1400px; }}
.stApp {{ background: #eef2f7; }}
[data-testid="stMain"] {{ color: {INKC}; }}
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: #ffffff; border-radius: 14px;
  box-shadow: 0 3px 10px rgba(30,41,90,.08); border: 1px solid #e2e8f0; }}

.pd-banner {{ background: #ffffff; border-radius: 16px; padding: 14px 22px 12px;
  text-align: center; border: 1px solid #e2e8f0; box-shadow: 0 3px 10px rgba(30,41,90,.08);
  margin-bottom: 12px; }}
.pd-title {{ font-size: 2.2rem; font-weight: 900; line-height: 1.1; letter-spacing: .01em; }}
.pd-title .a {{ color: {NAVY}; }} .pd-title .b {{ color: {ORANGE}; }}
.pd-sub {{ display: inline-block; background: {NAVY}; color: #fff; font-weight: 700;
  border-radius: 999px; padding: 2px 16px; font-size: .95rem; margin-top: 4px; }}
.pd-tag {{ font-size: .85rem; color: {INKC}; margin-top: 6px; }}

.flow {{ display: flex; justify-content: center; align-items: center; gap: 10px;
  flex-wrap: wrap; margin-top: 10px; }}
.fs {{ text-align: center; width: 120px; }}
.fs .ic {{ width: 46px; height: 46px; border-radius: 50%; display: inline-flex;
  align-items: center; justify-content: center; font-size: 22px;
  background: #eef2ff; border: 2px solid {NAVY}22; }}
.fs .t1 {{ font-size: .78rem; font-weight: 700; color: {INKC}; margin-top: 3px; }}
.fs .t2 {{ font-size: .66rem; color: #64748b; }}
.fa {{ font-size: 1.2rem; font-weight: 800; color: {ORANGE}; }}

.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px; margin: 4px 0 12px; }}
.kpi {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 10px 14px; box-shadow: 0 3px 10px rgba(30,41,90,.07); }}
.kpi .l {{ font-size: .82rem; font-weight: 800; }}
.kpi .v {{ font-size: 1.7rem; font-weight: 900; color: {NAVY}; line-height: 1.15; }}
.kpi .s {{ font-size: .75rem; color: #64748b; }}
.kpi .d {{ font-size: .78rem; font-weight: 800; margin-top: 2px; }}

.sec-hd {{ display: flex; width: 100%; align-items: center; gap: 9px; background: {NAVY};
  color: #fff; border-radius: 10px; padding: 4px 16px 4px 6px; font-weight: 800;
  font-size: 1.0rem; margin-bottom: 10px; }}
.sec-no {{ width: 26px; height: 26px; border-radius: 50%; display: inline-flex;
  align-items: center; justify-content: center; font-weight: 900; color: #fff; }}
.insight {{ background: #fef9e7; border: 1px solid #f5e6b8; border-radius: 9px;
  padding: 5px 12px; font-size: .82rem; color: #7a5c00; margin-top: 6px; }}
.mini {{ width: 100%; border-collapse: collapse; font-size: .84rem; }}
.mini th {{ background: {NAVY}; color: #fff; padding: 5px 8px; text-align: left; }}
.mini td {{ padding: 5px 8px; border-bottom: 1px solid #eef2f7; }}
.alert-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.alert {{ background: #fff; border: 1px solid #fecaca; border-left: 6px solid {RED};
  border-radius: 10px; padding: 8px 12px; }}
.alert .t {{ font-size: .78rem; font-weight: 700; color: {INKC}; }}
.alert .v {{ font-size: 1.25rem; font-weight: 900; color: {RED}; }}
.alert .s {{ font-size: .72rem; color: #64748b; }}
.alert.ok {{ border-color: #bbf7d0; border-left-color: {GREEN}; }}
.alert.ok .v {{ color: {GREEN}; }}
</style>
"""


def sec(no, title, color):
    st.markdown(
        f'<div class="sec-hd"><span class="sec-no" style="background:{color}">{no}</span>'
        f'{title}</div>', unsafe_allow_html=True)


def insight(text):
    st.markdown(f'<div class="insight">💡 {text}</div>', unsafe_allow_html=True)


def delta_html(cur, prev, good_when_up=True, unit="%"):
    if prev in (0, None) or pd.isna(prev) or pd.isna(cur):
        return '<span style="color:#94a3b8">— MoM</span>'
    ch = (cur - prev) / abs(prev) * 100
    up = ch >= 0
    good = up == good_when_up
    color = GREEN if good else RED
    arrow = "▲" if up else "▼"
    return f'<span style="color:{color}">{arrow} {ch:+.1f}% (MoM)</span>'


def kpi(label, lcolor, value, sub, dhtml):
    return (f'<div class="kpi"><div class="l" style="color:{lcolor}">{label}</div>'
            f'<div class="v">{value}</div><div class="s">{sub}</div>'
            f'<div class="d">{dhtml}</div></div>')


def cfg(ch):
    return (ch.configure_axis(labelColor=INKC, titleColor=INKC, gridColor="#eef2f7")
              .configure_legend(labelColor=INKC, titleColor=INKC)
              .configure_view(strokeWidth=0))


def donut(vals, names, colors, center_txt, center_sub, height=210):
    src = pd.DataFrame({"ชื่อ": names, "ค่า": vals})
    base = alt.Chart(src).mark_arc(innerRadius=62, outerRadius=90).encode(
        theta="ค่า:Q",
        color=alt.Color("ชื่อ:N", scale=alt.Scale(domain=names, range=colors),
                        legend=alt.Legend(orient="right", labelColor=INKC, title=None)),
        tooltip=["ชื่อ", alt.Tooltip("ค่า:Q", format=",.0f")],
    ).properties(height=height)
    txt = alt.Chart(pd.DataFrame({"t": [center_txt], "s": [center_sub]}))
    t1 = txt.mark_text(fontSize=22, fontWeight="bold", color=NAVY, dy=-4).encode(text="t:N")
    t2 = txt.mark_text(fontSize=11, color="#64748b", dy=16).encode(text="s:N")
    return cfg(base + t1 + t2)


# ---------------------------------------------------------------------------
# หน้าแดชบอร์ด
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Production Dashboard — แดชบอร์ดฝ่ายผลิต",
                       page_icon="🏭", layout="wide")
    auth.check_login("Production Dashboard — แดชบอร์ดฝ่ายผลิต")
    st.markdown(APP_CSS, unsafe_allow_html=True)

    with st.sidebar:
        auth.sidebar_user_box()
        if st.button("🔄 โหลดข้อมูลใหม่", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        st.caption("ข้อมูลจากฐาน OEE (Report1) · สูตรชุดเดียวกับระบบบริหาร OEE")

    try:
        df = load_prod(sig())
    except Exception as e:
        st.error(f"อ่านฐานข้อมูลไม่ได้ — {e}")
        st.stop()
    if df.empty:
        st.warning("ไม่พบข้อมูล")
        st.stop()

    months = sorted(df["เดือนปี"].unique())
    with st.sidebar:
        sel = st.selectbox("เดือน", list(reversed(months)), format_func=month_label)
    cur = df[df["เดือนปี"] == sel]
    prev_ts = months[months.index(sel) - 1] if months.index(sel) > 0 else None
    prv = df[df["เดือนปี"] == prev_ts] if prev_ts is not None else df.iloc[0:0]
    m = month_stats(cur)
    mp = month_stats(prv) if len(prv) else {k: float("nan") for k in m}

    # ---------- แบนเนอร์ + flow ----------
    st.markdown(
        '<div class="pd-banner">'
        '<div class="pd-title"><span class="a">PRODUCTION </span><span class="b">DASHBOARD</span></div>'
        '<div class="pd-sub">แดชบอร์ดฝ่ายผลิต</div>'
        f'<div class="pd-tag">ติดตามการผลิตแบบ Real-Data เห็นครบ จบในหน้าจอเดียว · เดือน {month_label(sel)}</div>'
        '<div class="flow">'
        '<div class="fs"><span class="ic">📋</span><div class="t1">วางแผนการผลิต</div><div class="t2">(PLAN)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">🏭</span><div class="t1">ดำเนินการผลิต</div><div class="t2">(PRODUCE)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">⚙️</span><div class="t1">เครื่องจักร &amp; ไลน์</div><div class="t2">(MACHINE)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">✅</span><div class="t1">คุณภาพสินค้า</div><div class="t2">(QUALITY)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">⏰</span><div class="t1">หยุดเครื่อง &amp; เหตุผล</div><div class="t2">(DOWNTIME)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">📈</span><div class="t1">วิเคราะห์ &amp; ปรับปรุง</div><div class="t2">(IMPROVE)</div></div>'
        '</div></div>', unsafe_allow_html=True)

    # ---------- 1 KPI SUMMARY ----------
    sec(1, "KPI SUMMARY", GREEN)
    st.markdown('<div class="kpi-grid">' + "".join([
        kpi("🎯 Plan Qty (ชิ้น)", BLUE, f"{m['plan']:,.0f}", "เป้าหมาย (Cap)",
            delta_html(m["plan"], mp["plan"])),
        kpi("📦 Actual Qty (ชิ้น)", GREEN, f"{m['actual']:,.0f}", "ผลิตได้จริง",
            delta_html(m["actual"], mp["actual"])),
        kpi("⏱ Achievement (%)", GOLD, f"{m['ach']:,.1f}%", "เทียบแผน",
            delta_html(m["ach"], mp["ach"])),
        kpi("✅ Good Qty (ชิ้น)", GREEN, f"{m['good']:,.0f}", "ของดี",
            delta_html(m["good"], mp["good"])),
        kpi("❌ Defect Rate (%)", RED, f"{m['defect_rate']:,.2f}%", "ของเสีย",
            delta_html(m["defect_rate"], mp["defect_rate"], good_when_up=False)),
        kpi("⚙️ OEE (%)", PURPLE, f"{m['OEE']:,.1f}%", "ประสิทธิผลรวม",
            delta_html(m["OEE"], mp["OEE"])),
    ]) + "</div>", unsafe_allow_html=True)

    # ---------- 2 PLAN vs ACTUAL + 3 TREND ----------
    ROW1_H, ROW2_H, ROW3_H = 520, 480, 420
    c2, c3 = st.columns([1.05, 1])
    with c2, st.container(border=True, height=ROW1_H):
        sec(2, "PLAN vs ACTUAL", BLUE)
        var = m["actual"] - m["plan"]
        st.markdown(
            f'<table class="mini"><tr><th>Plan</th><th>Actual</th><th>Variance</th><th>Achievement</th></tr>'
            f'<tr><td style="color:{BLUE};font-weight:800">{m["plan"]:,.0f}</td>'
            f'<td style="color:{GREEN};font-weight:800">{m["actual"]:,.0f}</td>'
            f'<td style="color:{RED if var < 0 else GREEN};font-weight:800">{var:+,.0f}</td>'
            f'<td style="font-weight:800">{m["ach"]:,.1f}%</td></tr></table>',
            unsafe_allow_html=True)
        daily = (cur.groupby("วันที่").agg(Plan=("Cap", "sum"), Actual=("Pieces", "sum"))
                 .reset_index())
        daily["วัน"] = daily["วันที่"].dt.day
        longd = daily.melt(id_vars="วัน", value_vars=["Plan", "Actual"],
                           var_name="ชุด", value_name="ชิ้น")
        bars = alt.Chart(longd).mark_bar().encode(
            x=alt.X("วัน:O", title="วัน"), xOffset="ชุด:N",
            y=alt.Y("ชิ้น:Q", title="Qty (ชิ้น)"),
            color=alt.Color("ชุด:N", scale=alt.Scale(domain=["Plan", "Actual"],
                                                     range=[BLUE, GREEN]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["วัน", "ชุด", alt.Tooltip("ชิ้น:Q", format=",.0f")],
        ).properties(height=235)
        st.altair_chart(cfg(bars), width="stretch")
        tone = ("ผลิตต่ำกว่าแผน" if var < 0 else "ผลิตได้ตามแผน")
        insight(f"เดือนนี้{tone} {m['ach'] - 100:+,.1f}% ({var:+,.0f} ชิ้น)")

    with c3, st.container(border=True, height=ROW1_H):
        sec(3, "PRODUCTION TREND (รายวัน)", GREEN)
        n_days = max(1, cur["วันที่"].nunique())
        best = daily.loc[daily["Actual"].idxmax()] if len(daily) else None
        line = alt.Chart(daily).mark_line(point=True, color=GREEN, strokeWidth=2.5).encode(
            x=alt.X("วัน:O", title="Day"), y=alt.Y("Actual:Q", title="Qty (ชิ้น)"),
            tooltip=["วัน", alt.Tooltip("Actual:Q", format=",.0f")])
        tgt = alt.Chart(daily).mark_line(color=BLUE, strokeDash=[5, 4]).encode(
            x="วัน:O", y="Plan:Q")
        st.altair_chart(cfg(line + tgt).properties(height=235), width="stretch")
        st.markdown(
            f'<table class="mini"><tr><th>Total Actual</th><th>Daily Avg</th><th>Best Day</th><th>% vs Target</th></tr>'
            f'<tr><td style="font-weight:800">{m["actual"]:,.0f} ชิ้น</td>'
            f'<td style="font-weight:800">{m["actual"] / n_days:,.0f} ชิ้น/วัน</td>'
            f'<td style="font-weight:800">{(best["Actual"] if best is not None else 0):,.0f} '
            f'({best["วัน"] if best is not None else "-"} {month_label(sel).split()[0]})</td>'
            f'<td style="font-weight:800">{m["ach"]:,.1f}%</td></tr></table>',
            unsafe_allow_html=True)

    # ---------- 4 BY LINE + 5 GOOD/DEFECT + 6 OEE ----------
    c4, c5, c6 = st.columns([1.15, 1, 1.15])
    with c4, st.container(border=True, height=ROW2_H):
        sec(4, "PRODUCTION BY GROUP", NAVY)
        rows = []
        for g, gd in cur.groupby("กลุ่ม"):
            gm = month_stats(gd)
            if gm["actual"] <= 0:
                continue
            rows.append((g, gm["actual"], gm["ach"], gm["OEE"], gm["defect_rate"]))
        rows.sort(key=lambda r: -r[1])
        def ach_cell(v):
            if pd.isna(v):
                return '<td style="color:#94a3b8">-</td>'
            c = GREEN if v >= 90 else (GOLD if v >= 80 else RED)
            return f'<td style="color:{c};font-weight:700">{v:,.1f}%</td>'

        body = "".join(
            f'<tr><td style="font-weight:700">{g}</td><td>{a:,.0f}</td>'
            + ach_cell(ach)
            + f'<td style="font-weight:700">{"-" if pd.isna(o) else f"{o:,.1f}%"}</td>'
            f'<td style="color:{RED if dr > TARGET_DEFECT else GREEN}">{dr:,.2f}%</td></tr>'
            for g, a, ach, o, dr in rows[:8])
        st.markdown('<table class="mini"><tr><th>กลุ่ม</th><th>Actual</th><th>Achv.</th>'
                    '<th>OEE</th><th>Defect</th></tr>' + body + "</table>",
                    unsafe_allow_html=True)
        if rows:
            top = max(rows, key=lambda r: (r[3] if not pd.isna(r[3]) else -1))
            insight(f"🏆 กลุ่ม {top[0]} มี OEE สูงสุด "
                    f"({'-' if pd.isna(top[3]) else f'{top[3]:,.1f}%'})")

    with c5, st.container(border=True, height=ROW2_H):
        sec(5, "GOOD vs DEFECT", GREEN)
        st.altair_chart(
            donut([m["good"], m["defect"]], ["Good Qty", "Defect Qty"], [GREEN, RED],
                  f"{m['actual']:,.0f}", "Total Production"),
            width="stretch")
        yld = m["good"] / m["actual"] * 100 if m["actual"] > 0 else float("nan")
        st.markdown(
            f'<table class="mini"><tr><th>Yield (%)</th><th>Defect Rate (%)</th></tr>'
            f'<tr><td style="color:{GREEN};font-weight:800;font-size:1.1rem">{yld:,.1f}%</td>'
            f'<td style="color:{RED};font-weight:800;font-size:1.1rem">{m["defect_rate"]:,.2f}%</td></tr></table>',
            unsafe_allow_html=True)
        insight(f"ของดี {yld:,.1f}% · ของเสีย {m['defect_rate']:,.2f}%")

    with c6, st.container(border=True, height=ROW2_H):
        sec(6, "OEE — A × P × Q", PURPLE)
        g1, g2, g3 = st.columns(3)
        for cc, (k, name, color) in zip(
                (g1, g2, g3),
                (("A", "Availability", GOLD), ("P", "Performance", BLUE),
                 ("Q", "Quality", GREEN))):
            with cc:
                v = m[k]
                st.altair_chart(
                    donut([max(v, 0), max(100 - v, 0)], [name, "gap"],
                          [color, "#e5e9f2"], f"{v:,.1f}%", name, height=125),
                    width="stretch")
        st.markdown(
            f'<div style="background:{PURPLE};color:#fff;border-radius:10px;'
            f'text-align:center;padding:6px;font-weight:900;font-size:1.5rem">'
            f'OEE {m["OEE"]:,.1f}%</div>', unsafe_allow_html=True)
        gap = m["OEE"] - TARGET_OEE
        insight(f"OEE เทียบเป้า {TARGET_OEE:g}% → {gap:+,.1f} จุด")

    # ---------- 7 DOWNTIME + 8 ALERT ----------
    c7, c8 = st.columns([1, 1.4])
    with c7, st.container(border=True, height=ROW3_H):
        sec(7, "DOWNTIME ANALYSIS (ชั่วโมง)", RED)
        loss = pd.DataFrame({
            "สาเหตุ": [n for _, n in LOSS_DEFS],
            "ชม.": [cur[c].clip(lower=0).sum() / 60 for c, _ in LOSS_DEFS],
        })
        loss = loss[loss["ชม."] > 0].sort_values("ชม.", ascending=False)
        total_dt = loss["ชม."].sum()
        bars = alt.Chart(loss).mark_bar(color=RED).encode(
            x=alt.X("ชม.:Q", title="ชั่วโมง"),
            y=alt.Y("สาเหตุ:N", sort="-x", title=None),
            tooltip=["สาเหตุ", alt.Tooltip("ชม.:Q", format=",.1f")],
        ).properties(height=230)
        st.altair_chart(cfg(bars), width="stretch")
        if len(loss):
            top = loss.iloc[0]
            insight(f"⚠️ หยุดเครื่องรวม {total_dt:,.0f} ชม. · มากที่สุดคือ "
                    f"{top['สาเหตุ']} {top['ชม.'] / total_dt * 100:,.1f}% ({top['ชม.']:,.1f} ชม.)")

    with c8, st.container(border=True, height=ROW3_H):
        sec(8, "PRODUCTION ALERT & ACTION", RED)
        alerts = []
        if m["ach"] < 100:
            alerts.append(("📉 Production ต่ำกว่าแผน", f"{m['ach'] - 100:,.1f}%",
                           f"ต่ำกว่าแผน {m['plan'] - m['actual']:,.0f} ชิ้น", False))
        else:
            alerts.append(("📈 Production ตามแผน", f"{m['ach'] - 100:+,.1f}%", "ทำได้ตามเป้า", True))
        ok_oee = m["OEE"] >= TARGET_OEE
        alerts.append(("⚙️ OEE เทียบเป้า", f"{m['OEE']:,.1f}%",
                       f"เป้า {TARGET_OEE:g}%", ok_oee))
        ok_def = m["defect_rate"] <= TARGET_DEFECT
        alerts.append(("❌ Defect Rate", f"{m['defect_rate']:,.2f}%",
                       f"เกณฑ์ {TARGET_DEFECT:g}%", ok_def))
        alerts.append(("⏰ Downtime รวม", f"{total_dt:,.0f} ชม.",
                       "รวมทุกสาเหตุเดือนนี้", total_dt == 0))
        n_mc = cur["Machine"].nunique()
        alerts.append(("🏭 เครื่องที่เดินงาน", f"{n_mc}", "เครื่องที่มีบันทึกเดือนนี้", True))
        st.markdown('<div class="alert-grid">' + "".join(
            f'<div class="alert{" ok" if ok else ""}"><div class="t">{t}</div>'
            f'<div class="v">{v}</div><div class="s">{s}</div></div>'
            for t, v, s, ok in alerts) + "</div>", unsafe_allow_html=True)
        st.markdown("")
        insight("📢 ตรวจสอบและดำเนินการแก้ไข เพื่อเพิ่มประสิทธิภาพการผลิต")

    st.caption(f"ข้อมูลจากฐาน OEE อัปเดตล่าสุด "
               f"{pd.Timestamp.fromtimestamp(_mtime(OEE_PATH)):%d/%m/%Y %H:%M} · "
               "Production Dashboard · ฝ่ายวิศวกรรมกระบวนการผลิต (IE)")


if __name__ == "__main__":
    main()
