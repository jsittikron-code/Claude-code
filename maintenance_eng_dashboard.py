"""MAINTENANCE ENGINEERING DASHBOARD — วิศวกรรมซ่อมบำรุง (สไตล์ infographic หน้าเดียว)
=============================================================================
มองเห็นประสิทธิภาพงานซ่อมบำรุง ลด Downtime เพิ่มความพร้อมของเครื่องจักร:
Availability · MTBF · MTTR · PM/BM · ต้นทุนซ่อม · วิเคราะห์สาเหตุเสีย
— เทียบเดือนก่อน (MoM) ทุกตัว · ข้อมูลจริงจากฐาน MTBF-MTTR + OEE + ใบงานซ่อม

รัน: python -m streamlit run maintenance_eng_dashboard.py --server.port 8511
"""

import os
import time

import altair as alt
import pandas as pd
import streamlit as st

import auth

# ---------------------------------------------------------------------------
# แหล่งข้อมูล + ค่าคงที่
# ---------------------------------------------------------------------------
DEPT_DIR = r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD\ฝ่ายซ่อมบำรุงรักษา"
MTBF_PATH = os.path.join(DEPT_DIR, r"2.เรื่องMTBF-MTTR\รายละเอียด\MTBF-MTTR_ฐานข้อมูลหลัก_2569.xlsx")
OEE_PATH = os.path.join(DEPT_DIR, r"3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx")
MT_DIR = os.path.join(DEPT_DIR, "ทดสอบแยกข้อมูลย้อนหลัง")
MT_FILES = {
    "เครื่องจักร": "รายงานซ่อมบำรุง_เครื่อง_2020-2026.xlsx",
    "ซ่อมสร้าง": "รายงานซ่อมบำรุง_ซ่อมสร้าง_2020-2026.xlsx",
    "ลับคม": "รายงานซ่อมบำรุง_ลับคม_2020-2026.xlsx",
    "ซ่อมรถยนต์": "รายงานซ่อมบำรุง_ซ่อมรถยนต์_2020-2026.xlsx",
    "เครื่องมือเล็ก": "รายงานซ่อมบำรุง_เครื่องมือเล็ก_2020-2026.xlsx",
    "ดัดแปลง": "รายงานซ่อมบำรุง_ดัดแปลง_2020-2026.xlsx",
}
PS_PATH = os.path.join(MT_DIR, "วิเคราะห์ปัญหา-สาเหตุ_รายเครื่อง.xlsx")
MTBF_SHEETS = {"Breakdown_B000000001": "Breakdown", "Maintenance_BP00000001": "Maintenance"}
TARGET_AVAIL = 90.0

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
CAT_COLORS = {"เครื่องจักร": "#2563eb", "ซ่อมสร้าง": "#ea580c", "ลับคม": "#16a34a",
              "ซ่อมรถยนต์": "#f59e0b", "เครื่องมือเล็ก": "#db2777", "ดัดแปลง": "#0d9488"}


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
    files = ([MTBF_PATH, OEE_PATH, PS_PATH]
             + [os.path.join(MT_DIR, f) for f in MT_FILES.values()])
    return tuple(_mtime(p) for p in files)


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านฐาน MTBF-MTTR...")
def load_events(_sig):
    """เหตุการณ์ B (เครื่องเสีย) และ BP (ช่างซ่อม) — สูตรเดียวกับแอปใบงานซ่อม"""
    frames = []
    for sheet, typ in MTBF_SHEETS.items():
        try:
            d = _read_sheet(MTBF_PATH, sheet)
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


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านเวลาเดินเครื่อง (ฐาน OEE)...")
def load_runtime(_sig):
    """เวลาทำงานจริง/วัน จากฐาน OEE — ตัวหารของ MTBF ตามสูตรมาตรฐานฝ่าย"""
    d = _read_sheet(OEE_PATH, "Report1")
    d.columns = [str(c).strip() for c in d.columns]
    out = pd.DataFrame(index=d.index)
    out["รหัสเครื่อง"] = d["MC"].astype(str).str.strip()
    out["วันที่"] = pd.to_datetime(d.get("Trans_date"), errors="coerce")
    out["นาทีเดิน"] = pd.to_numeric(d.get("เวลาทำงานจริง/วัน"), errors="coerce").fillna(0)
    out = out.dropna(subset=["วันที่"])
    out["เดือนปี"] = out["วันที่"].dt.to_period("M").dt.to_timestamp()
    return out


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านการวิเคราะห์ปัญหา-สาเหตุ...")
def load_causes(_sig):
    """ไฟล์วิเคราะห์ปัญหา-สาเหตุ_รายเครื่อง → กลุ่มสาเหตุ + ประเภทปัญหา รายใบงาน"""
    try:
        raw = _read_sheet(PS_PATH, "ข้อมูล")
    except Exception:
        return pd.DataFrame()
    raw.columns = [str(c).strip() for c in raw.columns]
    if "กลุ่มสาเหตุ" not in raw.columns:
        return pd.DataFrame()
    out = pd.DataFrame(index=raw.index)
    out["วันที่"] = pd.to_datetime(raw.get("วันที่แจ้ง"), errors="coerce")
    out["รหัสเครื่อง"] = raw.get("รหัสเครื่อง", "").astype(str).str.strip()
    out["สาเหตุ"] = raw["กลุ่มสาเหตุ"].astype(str).str.strip()
    out["ประเภทปัญหา"] = raw.get("ประเภทปัญหา", "").astype(str).str.strip()
    out["สาเหตุ"] = out["สาเหตุ"].replace({"nan": "(ไม่ระบุ)", "": "(ไม่ระบุ)"})
    return out.dropna(subset=["วันที่"])


@st.cache_data(ttl="30m", max_entries=2, show_spinner="กำลังอ่านใบงานซ่อม 6 หมวด...")
def load_repair(_sig):
    """ใบงานซ่อม 6 หมวด — ต้นทุน (รวม Petty Cash) + PM/BM + รหัสเครื่อง"""
    frames = []
    for cat, fname in MT_FILES.items():
        path = os.path.join(MT_DIR, fname)
        if not os.path.exists(path):
            continue
        try:
            raw = _read_sheet(path, "ข้อมูล")
        except Exception:
            continue
        raw.columns = [str(c).strip() for c in raw.columns]

        def col(name):
            return raw[name] if name in raw.columns else pd.Series([None] * len(raw), index=raw.index)

        df = pd.DataFrame(index=raw.index)
        df["หมวด"] = cat
        df["ปี"] = pd.to_numeric(col("ปี"), errors="coerce")
        df["เดือน"] = pd.to_numeric(col("เดือน"), errors="coerce")
        df["รหัสเครื่อง"] = col("รหัสเครื่อง").astype(str).str.strip()
        df["สถานะ"] = col("สถานะการซ่อม (PM/BM)").astype(str).str.strip().str.upper()
        df["สถานะ"] = df["สถานะ"].where(df["สถานะ"].isin(["PM", "BM"]), "ไม่ระบุ")
        df["ค่าใช้จ่าย"] = (
            pd.to_numeric(col("ค่าใช้จ่าย (บาท)"), errors="coerce").fillna(0)
            + pd.to_numeric(col("Petty Cash (บาท)"), errors="coerce").fillna(0)
        )
        df = df[df["ปี"].between(2019, 2030) & df["เดือน"].between(1, 12)]
        df["เดือนปี"] = pd.to_datetime(dict(year=df["ปี"].astype(int),
                                            month=df["เดือน"].astype(int), day=1))
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def kpis_for(ev, run, rep, month) -> dict:
    """ชุด KPI ซ่อมบำรุงของเดือนที่กำหนด (สูตรมาตรฐานฝ่าย)"""
    e = ev[ev["เดือนปี"] == month]
    r = run[run["เดือนปี"] == month]
    p = rep[rep["เดือนปี"] == month] if len(rep) else rep
    bd = e[e["ประเภท"] == "Breakdown"]
    bp = e[e["ประเภท"] == "Maintenance"]
    n_bd = len(bd)
    run_min = float(r["นาทีเดิน"].sum())
    down_min = float(bd["นาที"].sum()) + float(bp["นาที"].sum())
    avail = run_min / (run_min + down_min) * 100 if (run_min + down_min) > 0 else float("nan")
    mtbf = run_min / 60 / n_bd if n_bd > 0 else float("nan")
    mttr = float(bp["นาที"].mean()) if len(bp) else float("nan")
    n_pm = int((p["สถานะ"] == "PM").sum()) if len(p) else 0
    n_bm = int((p["สถานะ"] == "BM").sum()) if len(p) else 0
    pm_ratio = n_pm / (n_pm + n_bm) * 100 if (n_pm + n_bm) > 0 else float("nan")
    cost = float(p["ค่าใช้จ่าย"].sum()) if len(p) else 0.0
    return {"avail": avail, "down_h": down_min / 60, "mtbf": mtbf, "mttr": mttr,
            "pm_ratio": pm_ratio, "cost": cost, "n_bd": n_bd, "n_pm": n_pm,
            "n_bm": n_bm, "run_h": run_min / 60, "bd": bd, "bp": bp}


# ---------------------------------------------------------------------------
# สไตล์ infographic (ชุดเดียวกับ Production Dashboard — โทนส้มวิศวกรรม)
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
.pd-title {{ font-size: 2.0rem; font-weight: 900; line-height: 1.12; }}
.pd-title .a {{ color: {NAVY}; }} .pd-title .b {{ color: {ORANGE}; }}
.pd-sub {{ display: inline-block; background: {NAVY}; color: #fff; font-weight: 700;
  border-radius: 999px; padding: 2px 16px; font-size: .95rem; margin-top: 4px; }}
.pd-tag {{ font-size: .85rem; color: {INKC}; margin-top: 6px; }}
.flow {{ display: flex; justify-content: center; align-items: center; gap: 10px;
  flex-wrap: wrap; margin-top: 10px; }}
.fs {{ text-align: center; width: 118px; }}
.fs .ic {{ width: 46px; height: 46px; border-radius: 50%; display: inline-flex;
  align-items: center; justify-content: center; font-size: 22px;
  background: #fff3e8; border: 2px solid {ORANGE}33; }}
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
.alert {{ background: #fff; border: 1px solid #fecaca; border-left: 6px solid {RED};
  border-radius: 10px; padding: 8px 12px; margin-bottom: 8px; }}
.alert .t {{ font-size: .8rem; font-weight: 800; color: {INKC}; }}
.alert .s {{ font-size: .74rem; color: #64748b; }}
.alert.warn {{ border-color: #fde68a; border-left-color: {GOLD}; }}
</style>
"""


def sec(no, title, color):
    st.markdown(
        f'<div class="sec-hd"><span class="sec-no" style="background:{color}">{no}</span>'
        f'{title}</div>', unsafe_allow_html=True)


def insight(text):
    st.markdown(f'<div class="insight">💡 {text}</div>', unsafe_allow_html=True)


def delta_html(cur, prev, good_when_up=True):
    if prev in (0, None) or pd.isna(prev) or pd.isna(cur):
        return '<span style="color:#94a3b8">— vs Last Month</span>'
    ch = (cur - prev) / abs(prev) * 100
    up = ch >= 0
    color = GREEN if (up == good_when_up) else RED
    arrow = "▲" if up else "▼"
    return f'<span style="color:{color}">{arrow} {ch:+.1f}% vs Last Month</span>'


def kpi(label, lcolor, value, sub, dhtml):
    return (f'<div class="kpi"><div class="l" style="color:{lcolor}">{label}</div>'
            f'<div class="v">{value}</div><div class="s">{sub}</div>'
            f'<div class="d">{dhtml}</div></div>')


def cfg(ch):
    return (ch.configure_axis(labelColor=INKC, titleColor=INKC, gridColor="#eef2f7")
              .configure_legend(labelColor=INKC, titleColor=INKC)
              .configure_view(strokeWidth=0))


# ---------------------------------------------------------------------------
# หน้าแดชบอร์ด
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Maintenance Engineering Dashboard — วิศวกรรมซ่อมบำรุง",
                       page_icon="🔧", layout="wide")
    auth.check_login("Maintenance Engineering Dashboard — วิศวกรรมซ่อมบำรุง")
    st.markdown(APP_CSS, unsafe_allow_html=True)

    with st.sidebar:
        auth.sidebar_user_box()
        if st.button("🔄 โหลดข้อมูลใหม่", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        st.caption("ข้อมูลจากฐาน MTBF-MTTR + OEE + ใบงานซ่อม 6 หมวด")

    try:
        ev = load_events(sig())
        run = load_runtime(sig())
        rep = load_repair(sig())
        causes = load_causes(sig())
    except Exception as e:
        st.error(f"อ่านฐานข้อมูลไม่ได้ — {e}")
        st.stop()
    if ev.empty or run.empty:
        st.warning("ไม่พบข้อมูล MTBF/Runtime")
        st.stop()

    months = sorted(set(ev["เดือนปี"]) & set(run["เดือนปี"]))
    with st.sidebar:
        sel = st.selectbox("เดือน", list(reversed(months)), format_func=month_label)
    idx = months.index(sel)
    m = kpis_for(ev, run, rep, sel)
    mp = (kpis_for(ev, run, rep, months[idx - 1]) if idx > 0
          else {k: float("nan") for k in ("avail", "down_h", "mtbf", "mttr", "pm_ratio", "cost")})

    # ---------- แบนเนอร์ + flow ----------
    st.markdown(
        '<div class="pd-banner">'
        '<div class="pd-title"><span class="b">วิศวกรรมซ่อมบำรุง</span><br>'
        '<span class="a">MAINTENANCE ENGINEERING DASHBOARD</span></div>'
        f'<div class="pd-sub">มองเห็นประสิทธิภาพงานซ่อมบำรุง ลด Downtime เพิ่มความพร้อมของเครื่องจักร</div>'
        f'<div class="pd-tag">เดือน {month_label(sel)}</div>'
        '<div class="flow">'
        '<div class="fs"><span class="ic">⚙️</span><div class="t1">เครื่องจักร</div><div class="t2">(MACHINE)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">📋</span><div class="t1">วางแผนซ่อม</div><div class="t2">(PM PLAN)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">🛠️</span><div class="t1">ปฏิบัติงาน</div><div class="t2">(WORK ORDER)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">🔩</span><div class="t1">อะไหล่/ทรัพยากร</div><div class="t2">(SPARE PARTS)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">⏰</span><div class="t1">หยุดซ่อม</div><div class="t2">(DOWNTIME)</div></div><span class="fa">→</span>'
        '<div class="fs"><span class="ic">📊</span><div class="t1">วิเคราะห์ &amp; พัฒนา</div><div class="t2">(ANALYSIS)</div></div>'
        '</div></div>', unsafe_allow_html=True)

    # ---------- 1 KPI SUMMARY ----------
    sec(1, "KPI SUMMARY", GREEN)
    st.markdown('<div class="kpi-grid">' + "".join([
        kpi("🟢 Availability", GREEN, f"{m['avail']:,.1f}%", "ความพร้อมเครื่องจักร",
            delta_html(m["avail"], mp["avail"])),
        kpi("⏰ Downtime", RED, f"{m['down_h']:,.1f} ชม.", "B + BP เดือนนี้",
            delta_html(m["down_h"], mp["down_h"], good_when_up=False)),
        kpi("📅 MTBF", BLUE, "-" if pd.isna(m["mtbf"]) else f"{m['mtbf']:,.0f} ชม.",
            "เดินเครื่องต่อการเสีย 1 ครั้ง", delta_html(m["mtbf"], mp["mtbf"])),
        kpi("🔧 MTTR", ORANGE, "-" if pd.isna(m["mttr"]) else f"{m['mttr']:,.0f} นาที",
            "เวลาซ่อมเฉลี่ยต่อครั้ง", delta_html(m["mttr"], mp["mttr"], good_when_up=False)),
        kpi("📋 สัดส่วนงาน PM", PURPLE, "-" if pd.isna(m["pm_ratio"]) else f"{m['pm_ratio']:,.1f}%",
            f"PM {m['n_pm']:,} · BM {m['n_bm']:,}", delta_html(m["pm_ratio"], mp["pm_ratio"])),
        kpi("💰 Maintenance Cost", GOLD,
            (f"{m['cost']:,.0f} ฿" if m["cost"] < 1e5 else f"{m['cost'] / 1e6:,.2f}M ฿"),
            "ค่าซ่อมเดือนนี้", delta_html(m["cost"], mp["cost"], good_when_up=False)),
    ]) + "</div>", unsafe_allow_html=True)

    # ---------- 2 AVAILABILITY + 3 BREAKDOWN + 4 TREND ----------
    ROW1_H, ROW2_H = 500, 520
    c2, c3, c4 = st.columns([1, 1, 1.15])
    with c2, st.container(border=True, height=ROW1_H):
        sec(2, "MACHINE AVAILABILITY", GREEN)
        src = pd.DataFrame({
            "ชื่อ": ["Run Time", "Downtime"],
            "ชม.": [m["run_h"], m["down_h"]],
        })
        base = alt.Chart(src).mark_arc(innerRadius=58, outerRadius=86).encode(
            theta="ชม.:Q",
            color=alt.Color("ชื่อ:N", scale=alt.Scale(domain=["Run Time", "Downtime"],
                                                      range=[GREEN, RED]),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["ชื่อ", alt.Tooltip("ชม.:Q", format=",.0f")],
        ).properties(height=205)
        txt = alt.Chart(pd.DataFrame({"t": [f"{m['avail']:,.1f}%"]})).mark_text(
            fontSize=21, fontWeight="bold", color=NAVY).encode(text="t:N")
        st.altair_chart(cfg(base + txt), width="stretch")
        st.markdown(
            f'<table class="mini"><tr><th>Run Time</th><th>Downtime</th></tr>'
            f'<tr><td style="color:{GREEN};font-weight:800">{m["run_h"]:,.0f} ชม.</td>'
            f'<td style="color:{RED};font-weight:800">{m["down_h"]:,.1f} ชม.</td></tr></table>',
            unsafe_allow_html=True)
        insight(f"เป้าหมาย Availability ≥ {TARGET_AVAIL:g}% → "
                f"{'✅ ผ่าน' if m['avail'] >= TARGET_AVAIL else '⚠️ ยังไม่ถึงเป้า'}")

    with c3, st.container(border=True, height=ROW1_H):
        sec(3, "BREAKDOWN & DOWNTIME", RED)
        st.markdown(
            f'<table class="mini"><tr><th>Breakdown</th><th>Downtime</th></tr>'
            f'<tr><td style="color:{RED};font-weight:900;font-size:1.3rem">{m["n_bd"]} ครั้ง</td>'
            f'<td style="color:{RED};font-weight:900;font-size:1.3rem">{m["down_h"]:,.1f} ชม.</td></tr></table>',
            unsafe_allow_html=True)
        top5 = (m["bd"].groupby("รหัสเครื่อง")["นาที"].sum().sort_values(ascending=False)
                .head(5).reset_index())
        top5["ชม."] = top5["นาที"] / 60
        bars = alt.Chart(top5).mark_bar(color=RED).encode(
            x=alt.X("ชม.:Q", title="ชม."),
            y=alt.Y("รหัสเครื่อง:N", sort="-x", title=None),
            tooltip=["รหัสเครื่อง", alt.Tooltip("ชม.:Q", format=",.1f")],
        ).properties(height=180)
        st.altair_chart(cfg(bars), width="stretch")
        if len(top5):
            insight(f"Downtime สูงสุดมาจาก {top5.iloc[0]['รหัสเครื่อง']} "
                    f"({top5.iloc[0]['ชม.']:,.1f} ชม.)")

    with c4, st.container(border=True, height=ROW1_H):
        sec(4, "MTBF & MTTR TREND (รายเดือน)", BLUE)
        rows = []
        for ts in months[max(0, idx - 5): idx + 1]:
            k = kpis_for(ev, run, rep, ts)
            rows.append({"เดือน": month_label(ts), "ts": ts,
                         "MTBF": k["mtbf"], "MTTR": k["mttr"]})
        tr = pd.DataFrame(rows)
        order = tr.sort_values("ts")["เดือน"].tolist()
        l1 = alt.Chart(tr).mark_line(point=True, color=BLUE, strokeWidth=2.5).encode(
            x=alt.X("เดือน:N", sort=order, title=None),
            y=alt.Y("MTBF:Q", title="MTBF (ชม.)"),
            tooltip=["เดือน", alt.Tooltip("MTBF:Q", format=",.0f")])
        l2 = alt.Chart(tr).mark_line(point=True, color=RED, strokeWidth=2.5).encode(
            x=alt.X("เดือน:N", sort=order),
            y=alt.Y("MTTR:Q", title="MTTR (นาที)"),
            tooltip=["เดือน", alt.Tooltip("MTTR:Q", format=",.0f")])
        ch = alt.layer(l1, l2).resolve_scale(y="independent").properties(height=225)
        st.altair_chart(cfg(ch), width="stretch")
        d_mtbf = delta_html(m["mtbf"], mp["mtbf"])
        d_mttr = delta_html(m["mttr"], mp["mttr"], good_when_up=False)
        st.markdown(f'<div style="font-size:.82rem">🔵 MTBF {d_mtbf} · 🔴 MTTR {d_mttr}</div>',
                    unsafe_allow_html=True)

    # ---------- 5 PM/BM + 6 COST + 7 FAILURE ----------
    c5, c6, c7 = st.columns([1, 1.15, 1])
    yr = pd.Timestamp(sel).year
    rep_yr = rep[rep["เดือนปี"].dt.year == yr] if len(rep) else rep

    with c5, st.container(border=True, height=ROW2_H):
        sec(5, "PREVENTIVE MAINTENANCE (PM/BM)", PURPLE)
        pmbm = (rep_yr.groupby([rep_yr["เดือนปี"].dt.month, "สถานะ"]).size()
                .rename("งาน").reset_index().rename(columns={"เดือนปี": "เดือน"}))
        pmbm = pmbm[pmbm["สถานะ"].isin(["PM", "BM"])]
        pmbm["ด"] = pmbm["เดือน"].map(lambda x: TH_M[int(x) - 1])
        order = [TH_M[i] for i in range(12)]
        bars = alt.Chart(pmbm).mark_bar().encode(
            x=alt.X("ด:N", sort=order, title=None),
            y=alt.Y("งาน:Q", title="จำนวนงาน"),
            color=alt.Color("สถานะ:N", scale=alt.Scale(domain=["PM", "BM"],
                                                       range=[PURPLE, RED]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["ด", "สถานะ", "งาน"],
        ).properties(height=225)
        st.altair_chart(cfg(bars), width="stretch")
        n_pm_y = int((rep_yr["สถานะ"] == "PM").sum())
        n_bm_y = int((rep_yr["สถานะ"] == "BM").sum())
        share = n_pm_y / (n_pm_y + n_bm_y) * 100 if (n_pm_y + n_bm_y) else 0
        insight(f"ปี {yr}: PM {n_pm_y:,} งาน · BM {n_bm_y:,} งาน → สัดส่วน PM {share:,.1f}% "
                f"({'ดี ซ่อมเชิงป้องกันนำ' if share >= 50 else 'ควรเพิ่มงาน PM'})")

    with c6, st.container(border=True, height=ROW2_H):
        sec(6, "MAINTENANCE COST", GOLD)
        cost_cat = (rep_yr.groupby("หมวด")["ค่าใช้จ่าย"].sum()
                    .sort_values(ascending=False).reset_index())
        base = alt.Chart(cost_cat).mark_arc(innerRadius=52, outerRadius=80).encode(
            theta="ค่าใช้จ่าย:Q",
            color=alt.Color("หมวด:N",
                            scale=alt.Scale(domain=list(CAT_COLORS),
                                            range=list(CAT_COLORS.values())),
                            legend=alt.Legend(orient="right", title=None)),
            tooltip=["หมวด", alt.Tooltip("ค่าใช้จ่าย:Q", format=",.0f")],
        ).properties(height=180)
        total_y = cost_cat["ค่าใช้จ่าย"].sum()
        txt = alt.Chart(pd.DataFrame({"t": [f"{total_y / 1e6:,.2f}M"]})).mark_text(
            fontSize=17, fontWeight="bold", color=NAVY).encode(text="t:N")
        st.altair_chart(cfg(base + txt), width="stretch")
        mc = rep_yr[rep_yr["หมวด"] == "เครื่องจักร"]
        top_mc = (mc[~mc["รหัสเครื่อง"].isin(["", "nan", "-", "#"])]
                  .groupby("รหัสเครื่อง")["ค่าใช้จ่าย"].sum()
                  .sort_values(ascending=False).head(5).reset_index())
        body = "".join(f'<tr><td>{r["รหัสเครื่อง"]}</td>'
                       f'<td style="font-weight:700">{r["ค่าใช้จ่าย"]:,.0f}</td></tr>'
                       for _, r in top_mc.iterrows())
        st.markdown('<table class="mini"><tr><th>เครื่องค่าซ่อมสูงสุด (ปีนี้)</th>'
                    '<th>บาท</th></tr>' + body + "</table>", unsafe_allow_html=True)
        if len(top_mc):
            insight(f"เครื่อง {top_mc.iloc[0]['รหัสเครื่อง']} ค่าซ่อมสูงสุด "
                    f"{top_mc.iloc[0]['ค่าใช้จ่าย']:,.0f} บาท")

    with c7, st.container(border=True, height=ROW2_H):
        sec(7, "FAILURE ANALYSIS", ORANGE)
        cz = causes[causes["วันที่"].dt.year == yr] if len(causes) else causes
        if len(cz):
            top = (cz["สาเหตุ"].value_counts().head(5).rename_axis("สาเหตุ")
                   .reset_index(name="ครั้ง"))
            top["%"] = top["ครั้ง"] / len(cz) * 100
            bars = alt.Chart(top).mark_bar(color=ORANGE).encode(
                x=alt.X("ครั้ง:Q", title="ครั้ง"),
                y=alt.Y("สาเหตุ:N", sort="-x", title=None,
                        axis=alt.Axis(labelLimit=160)),
                tooltip=["สาเหตุ", "ครั้ง", alt.Tooltip("%:Q", format=".1f")],
            ).properties(height=225)
            st.altair_chart(cfg(bars), width="stretch")
            insight(f"🎯 \"{top.iloc[0]['สาเหตุ']}\" เป็นสาเหตุหลัก "
                    f"({top.iloc[0]['%']:,.1f}%) ควรตรวจสอบและแก้ไขเชิงป้องกัน")
        else:
            st.info("ไม่พบข้อมูลไฟล์วิเคราะห์ปัญหา-สาเหตุ")

    # ---------- 8 ALERT ----------
    with st.container(border=True):
        sec(8, "MAINTENANCE ALERT", RED)
        a1, a2, a3 = st.columns(3)
        alerts = []
        if len(m["bd"]):
            worst = m["bd"].groupby("รหัสเครื่อง")["นาที"].sum().idxmax()
            worst_h = m["bd"].groupby("รหัสเครื่อง")["นาที"].sum().max() / 60
            alerts.append(("⏰ Downtime สูงผิดปกติ",
                           f"เครื่อง {worst} หยุดรวม {worst_h:,.1f} ชม. เดือนนี้"))
        if not pd.isna(m["pm_ratio"]) and m["pm_ratio"] < 50:
            alerts.append(("📋 สัดส่วน PM ต่ำ",
                           f"PM เพียง {m['pm_ratio']:,.0f}% — งานซ่อมส่วนใหญ่เป็น BM (เสียแล้วค่อยซ่อม)"))
        if not pd.isna(m["avail"]) and m["avail"] < TARGET_AVAIL:
            alerts.append(("🟠 Availability ต่ำกว่าเป้า",
                           f"{m['avail']:,.1f}% (เป้า ≥ {TARGET_AVAIL:g}%)"))
        if not pd.isna(mp.get("cost", float("nan"))) and mp["cost"] > 0 and m["cost"] > mp["cost"] * 1.2:
            alerts.append(("💰 ค่าซ่อมพุ่ง",
                           f"เดือนนี้ {m['cost']:,.0f} บาท สูงกว่าเดือนก่อน "
                           f"{(m['cost'] / mp['cost'] - 1) * 100:,.0f}%"))
        if not alerts:
            alerts.append(("✅ ไม่มีประเด็นเร่งด่วน", "ทุกตัวชี้วัดอยู่ในเกณฑ์ปกติ"))
        cols = [a1, a2, a3]
        for i, (t, s) in enumerate(alerts):
            with cols[i % 3]:
                st.markdown(f'<div class="alert"><div class="t">{t}</div>'
                            f'<div class="s">{s}</div></div>', unsafe_allow_html=True)
        insight("📢 ตรวจสอบและดำเนินการเพื่อลดความเสี่ยง")

    st.caption(f"ฐานข้อมูลอัปเดตล่าสุด "
               f"{pd.Timestamp.fromtimestamp(max(sig())):%d/%m/%Y %H:%M} · "
               "Maintenance Engineering Dashboard · ฝ่ายวิศวกรรมกระบวนการผลิต (IE)")


if __name__ == "__main__":
    main()
