# -*- coding: utf-8 -*-
"""แท็บ Solar Monitor ของ energy_monitor.py — ประสิทธิภาพราย inverter / ราย MPPT / รายวัน
------------------------------------------------------------------------------------
อ่าน parquet ที่ solar_etl.py สร้าง (ปุ่ม อัปเดต Solar.bat) — สูตรและเกณฑ์ทั้งหมดอยู่ใน
solar_etl.py ไฟล์นี้มีแต่การแสดงผล ห้ามคำนวณกฎธุรกิจซ้ำที่นี่

เรียกจาก energy_monitor.py:   solar_monitor_tab.render(kpi_card)
"""

from __future__ import annotations

import threading
import traceback
from datetime import time as dtime, timedelta

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import data_paths
import solar_etl as se

PERIODS = {"รายวัน": 0, "7 วัน": 7, "14 วัน": 14, "30 วัน": 30, "ทั้งหมด": None}
# สีประจำเครื่อง #1–#11 (คงที่ทุกกราฟ จะได้จำได้ว่าสีไหนเครื่องไหน)
INV_COLORS = ["#f59e0b", "#3b82f6", "#ef4444", "#10b981", "#8b5cf6", "#ec4899",
              "#14b8a6", "#f97316", "#6366f1", "#84cc16", "#06b6d4"]
# เส้นเป้าผลผลิตต่อวัน: MAX (PSH 4.5) เขียว · MIN (PSH 4.0) แดง · ตัวเลขที่อยู่ระหว่างกลางสีส้ม
TARGET_MAX_COLOR, TARGET_MIN_COLOR, TARGET_MID_COLOR = "#22c55e", "#ef4444", "#f59e0b"
COLOR_SOLAR, COLOR_COST, COLOR_ALERT, COLOR_GRID2 ="#f59e0b", "#16a34a", "#dc2626", "#0ea5e9"


# ---------------------------------------------------------------------------
# โหลดข้อมูล — แคชด้วยลายเซ็นไฟล์ parquet (ETL รันใหม่เมื่อไร โหลดใหม่เมื่อนั้น)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="กำลังอ่านข้อมูล Solar inverter...")
def _load(sig: tuple):
    daily = se.load_daily()
    prof = se.load_profile()
    daily["เครื่อง"] = "#" + daily["inv_no"].astype(str)
    prof["เครื่อง"] = "#" + prof["inv_no"].astype(str)
    prof["tod"] = prof["slot"].dt.hour + prof["slot"].dt.minute / 60
    return daily, prof


@st.cache_data(show_spinner=False)
def _readings(sig: tuple, day, sn: str) -> pd.DataFrame:
    return se.load_readings(day, day, sn)


def last_date(sig: tuple):
    """วันล่าสุดในฐาน Solar (ให้แถบด้านข้างแสดง) — None ถ้ายังไม่มีข้อมูล"""
    if not sig or not all(m for _, m in sig):
        return None
    try:
        return _load(sig)[0]["date"].max()
    except Exception:
        return None


def _fmt_date(d) -> str:
    return pd.Timestamp(d).strftime("%d/%m/%y")


def _inv_labels(daily: pd.DataFrame) -> list[str]:
    """ป้าย #1–#11 เสมอ + เครื่องใหม่ที่ระบบยังไม่รู้จัก (#12, #13, ...) ถ้ามีในข้อมูล"""
    nos = sorted(set(range(1, se.N_INVERTERS + 1)) | set(int(x) for x in daily["inv_no"].unique()))
    return [f"#{i}" for i in nos]


def _inv_scale(labels: list[str]) -> alt.Scale:
    return alt.Scale(domain=labels, range=[INV_COLORS[i % len(INV_COLORS)] for i in range(len(labels))])


# ---------------------------------------------------------------------------
# ปุ่มอัปเดตในแดชบอร์ด — เรียก solar_etl.run_update() ตัวเดียวกับไอคอน อัปเดต Solar บนเดสก์ท็อป
# ---------------------------------------------------------------------------
UPDATE_HELP = ("ย้ายไฟล์ EVE ที่ดึงลง Downloads เข้าฐานข้อมูล แล้วคำนวณใหม่ทั้งหมด — "
               "ทำงานเหมือนดับเบิลคลิกไอคอน อัปเดต Solar บนเดสก์ท็อป กดซ้ำได้ ข้อมูลไม่ซ้ำ")


# การอัปเดตทำในเธรดเบื้องหลังของโปรเซสแดชบอร์ด ไม่ใช่ในรอบรันสคริปต์ของผู้กด
# ทำไม: ถ้าทำในรอบรันสคริปต์ ผู้ใช้กดอะไรก็ตาม (เปลี่ยนช่วงเวลา / F5 / ปิดแท็บ) ระหว่างรอ ~20 วินาที
# Streamlit จะหยุดสคริปต์กลางคัน อาจค้างอยู่หลังเขียนฐานแถวดิบแต่ก่อนสรุปรายวัน (ทดสอบแล้วเกิดจริง)
# เธรดนี้อยู่ต่อแม้หน้าเว็บปิด และทุกคนใน LAN ที่เปิดแท็บนี้อยู่จะเห็นว่ากำลังอัปเดต
_JOB: dict = {"thread": None, "lines": [], "code": None, "start": None, "end": None, "path": None, "by": ""}
_JOB_GUARD = threading.Lock()


def _job_running() -> bool:
    t = _JOB["thread"]
    return t is not None and t.is_alive()


def _start_update(user: str) -> bool:
    """เริ่มอัปเดตในเธรดเบื้องหลัง — False ถ้ามีรอบกำลังทำอยู่แล้ว"""
    with _JOB_GUARD:
        if _job_running():
            return False
        flog = se.FileLog()
        lines: list[str] = []
        _JOB.update(lines=lines, code=None, start=pd.Timestamp.now(), end=None, path=flog.path, by=user)

        def out(s: str = "") -> None:
            flog(str(s))
            lines.extend(str(s).split("\n"))

        def work() -> None:
            code = 1
            try:
                with se.update_lock():
                    code = se.run_update(out=out)
            except se.UpdateBusy as e:
                out(f"*** {e}")
            except Exception:
                out(traceback.format_exc())
            finally:
                flog.close()
                _JOB["code"], _JOB["end"] = code, pd.Timestamp.now()

        t = threading.Thread(target=work, name="solar-update", daemon=True)
        _JOB["thread"] = t
        t.start()
    return True


@st.fragment(run_every="1s")
def _progress() -> None:
    """แสดงความคืบหน้าทุก 1 วินาทีระหว่างอัปเดต เสร็จแล้วรีเฟรชทั้งหน้าครั้งเดียวเพื่อโหลดข้อมูลใหม่"""
    if _job_running():
        with st.status(f"กำลังอัปเดตข้อมูล Solar จาก Downloads ... (เริ่ม {_JOB['start']:%H:%M:%S}"
                       + (f" โดย {_JOB['by']}" if _JOB["by"] else "") + ")", expanded=True):
            st.code("\n".join(_JOB["lines"][-25:]) or "เริ่มต้น ...", language=None)
        return
    # เพิ่งเสร็จและผู้ใช้คนนี้ยังไม่ได้เห็นผล → รีเฟรชทั้งหน้า (ลายเซ็น parquet เปลี่ยน แคชเดิมไม่ถูกใช้)
    if _JOB["end"] is not None and st.session_state.get("solar_seen_job") != _JOB["end"]:
        st.session_state["solar_seen_job"] = _JOB["end"]
        st.rerun(scope="app")


def _update_controls(key: str) -> None:
    """ปุ่มอัปเดต (หรือป้ายกำลังอัปเดต) — วางในแถวตัวเลือกด้านบน"""
    if _job_running():
        st.button(":material/hourglass_top: กำลังอัปเดต ...", key=key, disabled=True)
        return
    if st.button(":material/sync: อัปเดต Solar", type="primary", key=key, help=UPDATE_HELP):
        import auth                                    # โมดูลเดียวกับที่ energy_monitor ใช้ล็อกอิน
        if not _start_update(auth.current_user()):
            st.toast("มีการอัปเดตกำลังทำงานอยู่ รอสักครู่", icon=":material/hourglass_top:")
        st.rerun()


def _last_update_panel() -> None:
    """ความคืบหน้า (ระหว่างอัปเดต) หรือผลการอัปเดตครั้งล่าสุด — สรุปสั้น ๆ + log เต็มให้กางดู"""
    if _job_running() or (_JOB["end"] is not None and st.session_state.get("solar_seen_job") != _JOB["end"]):
        _progress()
        return
    if _JOB["end"] is None:
        return
    log = "\n".join(_JOB["lines"])
    key_lines = [ln.strip() for ln in log.splitlines()
                 if ln.strip().startswith(("แถวในฐาน", "ข้อมูลตั้งแต่", "ผลผลิตวัน", "***", "ย้าย"))]
    secs = (_JOB["end"] - _JOB["start"]).total_seconds()
    msg = (f"อัปเดตล่าสุด {_JOB['end']:%d/%m %H:%M:%S} ({secs:.0f} วินาที"
           + (f" · โดย {_JOB['by']}" if _JOB["by"] else "") + ") — "
           + " · ".join(k for k in key_lines if not k.startswith("ย้าย")))
    n_moved = sum(1 for k in key_lines if k.startswith("ย้าย"))
    if n_moved:
        msg += f" · ย้ายไฟล์ใหม่ {n_moved} ไฟล์"
    # แดง = ล้ม · เหลือง = สำเร็จแต่มีเรื่องต้องดู (ไม่มีไฟล์ใหม่ / ข้อมูลยังไม่ถึงวันนี้) · เขียว = เรียบร้อย
    show = (st.error if _JOB["code"] != 0 else
            st.warning if any(k.startswith("***") for k in key_lines) else st.success)
    show(msg, icon=":material/sync:")
    with st.expander("ดูรายละเอียดการอัปเดตครั้งล่าสุด"):
        st.code(log, language=None)
        st.caption(f"บันทึกไว้ที่ {_JOB['path']}")


# ---------------------------------------------------------------------------
# กราฟกระแสไฟฟ้า DC ขาเข้า / AC ขาออก (ใช้ในส่วนเจาะรายเครื่อง)
# ---------------------------------------------------------------------------
PHASE_COLORS = {"R": "#ef4444", "S": "#facc15", "T": "#3b82f6"}      # แดง/เหลือง/น้ำเงิน อ่านง่ายบนพื้นมืด
# ตำนาน 6 MPPT แถวเดียวยาวเกินกราฟครึ่งจอจนโดนตัด ("MPPT 5 ■ M") — แบ่งเป็น 2 แถว แถวละ 3
MPPT_COLOR = alt.Color("MPPT:N", scale=alt.Scale(scheme="category10"),
                       legend=alt.Legend(orient="bottom", title=None, columns=3, symbolType="stroke",
                                         symbolStrokeWidth=3, labelLimit=0))
PHASE_COLOR = alt.Color("เฟส:N", scale=alt.Scale(domain=list(PHASE_COLORS), range=list(PHASE_COLORS.values())),
                        legend=alt.Legend(orient="bottom", title="เฟส", columns=3, symbolType="stroke",
                                          symbolStrokeWidth=3))
REF_MUTED = "#94a3b8"


def _ref_rules(refs: list[tuple[float, str, str]]) -> alt.Chart:
    """เส้นอ้างอิงแนวนอน + ป้ายบนแกนขวา (นอกพื้นที่กราฟ ไม่ทับข้อมูล) — refs = [(ค่า, ป้าย, สี)]
    ใช้กับ alt.layer(...).resolve_axis(y="independent") เพื่อให้แกนซ้ายยังเป็นหน่วยของกราฟหลัก"""
    df = pd.DataFrame(refs, columns=["y", "ป้าย", "สี"])
    expr = " : ".join(f"datum.value == {v} ? '{lbl}'" for v, lbl, _ in refs) + " : ''"
    color_cond = {"condition": [{"test": f"datum.value == {v}", "value": c} for v, _, c in refs],
                  "value": REF_MUTED}
    return alt.Chart(df).mark_rule(strokeDash=[6, 4], strokeWidth=1.5).encode(
        y=alt.Y("y:Q", axis=alt.Axis(orient="right", values=[v for v, _, _ in refs], labelExpr=expr,
                                     title=None, grid=False, ticks=False, domain=False, labelFontSize=11,
                                     labelFontWeight="bold", labelPadding=6, labelColor=color_cond)),
        color=alt.Color("สี:N", scale=None, legend=None),
        tooltip=[alt.Tooltip("ป้าย:N", title="เส้นอ้างอิง")])


NO_DATA_COLOR = "#334155"


def _ratio_heatmap(df: pd.DataFrame, x, y, tip: list, font: int = 12) -> alt.LayerChart:
    """ตาราง % เทียบค่าเฉลี่ยต่อสตริง — ช่องที่คำนวณไม่ได้ (ข้อมูลกลางวันไม่พอ) เป็นสีเทาพร้อม "—"
    ไม่ปล่อยให้หายไปเฉย ๆ หรือโชว์ตัวเลขจากข้อมูลตอนเย็นที่ไม่มีความหมาย"""
    df = df.copy()
    df["เทียบเฉลี่ย"] = df["ratio"] * 100
    df["ว่าง"] = df["เทียบเฉลี่ย"].isna()
    df["ป้าย"] = df["เทียบเฉลี่ย"].map(lambda v: "—" if pd.isna(v) else f"{v:.0f}")
    df["สถานะ"] = np.where(df["ว่าง"], "ข้อมูลกลางวันไม่พอ — ไม่คำนวณ", "คำนวณแล้ว")
    tip = tip + [alt.Tooltip("เทียบเฉลี่ย:Q", title="เทียบเฉลี่ยต่อสตริง (%)", format=".0f"),
                 alt.Tooltip("สถานะ:N", title="สถานะ")]
    base = alt.Chart(df).encode(x=x, y=y, tooltip=tip)
    gray = base.transform_filter(alt.datum["ว่าง"]).mark_rect(color=NO_DATA_COLOR)
    heat = base.transform_filter(~alt.datum["ว่าง"]).mark_rect().encode(color=alt.Color(
        "เทียบเฉลี่ย:Q", title="% ของเฉลี่ย", scale=alt.Scale(scheme="redyellowgreen", domain=[50, 120], clamp=True)))
    txt = base.mark_text(fontWeight="bold", fontSize=font).encode(
        text="ป้าย:N",
        color=alt.condition("datum['ว่าง'] || datum['เทียบเฉลี่ย'] < 70", alt.value("#e2e8f0"), alt.value("#0f172a")))
    return alt.layer(gray, heat, txt)


def _with_refs(chart: alt.Chart, refs) -> alt.LayerChart:
    return alt.layer(chart, _ref_rules(refs)).resolve_axis(y="independent")


def _current_trend(g: pd.DataFrame) -> None:
    """แนวโน้มรายวันของกระแส DC ขาเข้าต่อ MPPT และกระแส AC ขาออกต่อเฟส (ค่ากลางช่วงแดดเต็ม 10–14 น.)"""
    if "iac_r_mid" not in g.columns:       # parquet รุ่นก่อนมีคอลัมน์กระแส AC — ยังไม่ได้กดอัปเดตหลังเพิ่มฟีเจอร์
        st.info("ยังไม่มีข้อมูลกระแสรายวัน — กดปุ่ม อัปเดต Solar 1 ครั้งเพื่อคำนวณใหม่")
        return
    x = alt.X("date:T", title="วันที่", axis=alt.Axis(format="%d/%m", labelAngle=0))
    c1, c2 = st.columns(2)
    with c1:
        dc = pd.concat([
            g[["date"]].assign(MPPT=f"MPPT {i}", ค่ากลาง=g[f"idc{i}_mid"], สูงสุด=g[f"idc{i}_max"])
            for i in se.MPPT], ignore_index=True)
        line = alt.Chart(dc.dropna(subset=["ค่ากลาง"])).mark_line(point=True, strokeWidth=2).encode(
            x=x, y=alt.Y("ค่ากลาง:Q", title=None, scale=alt.Scale(domain=[0, se.STRING_IMP_A * 2.3])),
            color=MPPT_COLOR,
            tooltip=[alt.Tooltip("date:T", title="วันที่", format="%d/%m/%Y"), "MPPT",
                     alt.Tooltip("ค่ากลาง:Q", title="ค่ากลาง 10–14 น. (A)", format=".1f"),
                     alt.Tooltip("สูงสุด:Q", title="สูงสุดของวัน (A)", format=".1f")])
        refs = [(round(se.STRING_IMP_A * 2, 2), f"2 สตริง {se.STRING_IMP_A * 2:.1f} A", REF_MUTED),
                (se.STRING_IMP_A, f"1 สตริง {se.STRING_IMP_A:.1f} A", REF_MUTED)]
        st.altair_chart(_with_refs(line, refs).properties(
            height=300, title="กระแส DC ขาเข้า ต่อ MPPT (A) · รายวัน ค่ากลาง 10–14 น."), width="stretch")
        st.caption("เส้นประ = กระแสที่แดดเต็ม (STC) ของ MPPT ที่ต่อ 1 / 2 สตริง · "
                   "MPPT ที่ต่อ 2 สตริงแต่กระแสตกมาใกล้เส้น 1 สตริง = สตริงขนานหลุดไป 1 ชุด")
    with c2:
        ac = pd.concat([
            g[["date"]].assign(เฟส=p, ชนิด=n, A=g[f"{col}_{suf}"])
            for p, col in se.PHASES.items() for n, suf in (("ค่ากลาง 10–14 น.", "mid"), ("สูงสุดของวัน", "max"))],
            ignore_index=True)
        ac = ac.merge(g[["date", "phase_imbal_pct"]], on="date", how="left")
        line = alt.Chart(ac.dropna(subset=["A"])).mark_line(point=True, strokeWidth=2).encode(
            x=x, y=alt.Y("A:Q", title=None, scale=alt.Scale(domain=[0, se.AC_IMAX_A * 1.08])),
            color=PHASE_COLOR,
            strokeDash=alt.StrokeDash("ชนิด:N", scale=alt.Scale(
                domain=["ค่ากลาง 10–14 น.", "สูงสุดของวัน"], range=[[1, 0], [4, 3]]),
                legend=None),           # สัญลักษณ์เส้นประในตำนานมองไม่เห็นบนพื้นมืด — อธิบายใน caption แทน
            tooltip=[alt.Tooltip("date:T", title="วันที่", format="%d/%m/%Y"), "เฟส", "ชนิด",
                     alt.Tooltip("A:Q", title="กระแส (A)", format=".1f"),
                     alt.Tooltip("phase_imbal_pct:Q", title="เฟสไม่สมดุล (%)", format=".1f")])
        refs = [(se.AC_IMAX_A, f"พิกัด {se.AC_IMAX_A:.1f} A", COLOR_ALERT)]
        st.altair_chart(_with_refs(line, refs).properties(
            height=300, title="กระแส AC ขาออก ต่อเฟส R / S / T (A) · รายวัน"), width="stretch")
        imb = g["phase_imbal_pct"].dropna()
        st.caption("เส้นทึบ = ค่ากลางช่วงแดดเต็ม · เส้นประ = สูงสุดของวัน · เส้นแดง = พิกัดกระแสอินเวอร์เตอร์"
                   + (f" · เฟสไม่สมดุล ค่ากลาง {imb.median():.1f}% (สูงสุด {imb.max():.1f}% วันที่ "
                      f"{_fmt_date(g.loc[imb.idxmax(), 'date'])}) — ปกติไม่เกิน ~5%" if len(imb) else ""))


OUTAGE_LABEL = "หยุดจ่ายไฟ (เครื่องอื่นยังผลิต)"
STATUS_COLORS = {"Grid connected": "#22c55e", "Checking": "#f59e0b", "Standby": "#64748b", "Fault": "#ef4444",
                 OUTAGE_LABEL: "#d946ef"}
STRIP_ROWS = ["เครื่องรายงาน", "ระบบตรวจพบ"]


# ---------------------------------------------------------------------------
# ผังพลังงานเคลื่อนไหล: แผง (MPPT 1–6) → อินเวอร์เตอร์ → AC 3 เฟส → โรงงาน · เล่นย้อนทั้งวันได้
# ---------------------------------------------------------------------------
FLOW_STEP_MIN = 10           # เล่นทีละ 10 นาที
FLOW_TICK = "1.2s"           # ขยับทุก 1.2 วินาที (14 ชม. ≈ 100 วินาที)
FLOW_W, FLOW_H = 1200, 400
MPPT_HEX = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]   # = scheme category10 ของกราฟ
FLOW_IDLE = "#475569"
FLOW_MPPT_KW = 20.0          # กำลัง DC ต่อ MPPT ที่ถือว่า "เต็ม" สำหรับความหนาเส้น (จริงสูงสุด ~17 kW)


def _flow_dur(frac: float) -> str:
    """ความเร็วอนุภาคตามกำลัง: แรงมาก = วิ่งเร็ว (0.45 วิ/รอบ) · เบา = ช้า (2.6 วิ/รอบ)"""
    return f"{max(0.45, 2.6 - 2.15 * min(max(frac, 0.0), 1.0)):.2f}s"


def _flow_svg(row, t: pd.Timestamp, day_pac: pd.DataFrame, inv_label: str, n_out_now: bool) -> str:
    """ภาพ SVG ณ เวลา t — row = แถวข้อมูลล่าสุดก่อน t (ภายใน 3 นาที) หรือ None ถ้า logger ไม่ส่ง"""
    W, H = FLOW_W, FLOW_H
    txt = "#e2e8f0"
    mute = "#94a3b8"
    have = row is not None
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" '
         f'style="display:block;max-width:{W}px;font-family:inherit">',
         "<style>"
         "@keyframes sflow{to{stroke-dashoffset:-36}}"
         ".sf{stroke-dasharray:3 15;stroke-linecap:round;animation:sflow linear infinite}"
         "@keyframes sglow{0%,100%{opacity:.55}50%{opacity:1}}"
         ".sg{animation:sglow 1.6s ease-in-out infinite}"
         "</style>"]
    # ---- หัว: เวลา + สถานะ + ตัวเลขหลัก ----
    pac = float(row["pac_kw"]) if have and pd.notna(row["pac_kw"]) else 0.0
    pdc = float(row["pdc_kw"]) if have and pd.notna(row["pdc_kw"]) else 0.0
    status = str(row["status"]) if have else "ไม่มีข้อมูล"
    if have and n_out_now:
        st_txt, st_col = "หยุดจ่ายไฟ (เครื่องอื่นยังผลิต)", STATUS_COLORS[OUTAGE_LABEL]
    elif have:
        st_txt, st_col = status, STATUS_COLORS.get(status, STATUS_COLORS["Fault"])
    else:
        st_txt, st_col = "logger ไม่ส่งข้อมูล ณ เวลานี้", FLOW_IDLE
    o.append(f'<text x="20" y="40" font-size="34" font-weight="800" fill="{txt}">{t:%H:%M}</text>'
             f'<text x="128" y="40" font-size="15" fill="{mute}">{t:%d/%m/%Y} · {inv_label}</text>'
             f'<circle cx="136" cy="58" r="6" fill="{st_col}" class="sg"/>'
             f'<text x="148" y="63" font-size="14" font-weight="700" fill="{st_col}">{st_txt}</text>')
    eff = pac / pdc * 100 if pdc > 1 else None
    eday = float(row["eday_kwh"]) if have and pd.notna(row.get("eday_kwh")) else None
    kpis = [("DC ขาเข้า", f"{pdc:.1f} kW", COLOR_SOLAR), ("AC ขาออก", f"{pac:.1f} kW", COLOR_GRID2),
            ("ประสิทธิภาพ", f"{eff:.1f} %" if eff else "—", "#22c55e"),
            ("ผลิตสะสมวันนี้", f"{eday:,.1f} kWh" if eday is not None else "—", "#a78bfa")]
    for k, (lbl, val, col) in enumerate(kpis):
        x = 560 + k * 160
        o.append(f'<text x="{x}" y="26" font-size="12" fill="{mute}">{lbl}</text>'
                 f'<text x="{x}" y="52" font-size="22" font-weight="800" fill="{col}">{val}</text>')

    # ---- MPPT 1–6 (ซ้าย) → อินเวอร์เตอร์ (กลาง) ----
    ix0, ix1, iy0, iy1 = 520, 700, 120, 260
    for k, i in enumerate(se.MPPT):
        y = 84 + k * 35
        v = row.get(f"vdc{i}") if have else None
        a = row.get(f"idc{i}") if have else None
        p = (row.get(f"pdc{i}") or 0) / 1000.0 if have else 0.0
        on = have and p > 0.05
        col = MPPT_HEX[k] if on else FLOW_IDLE
        o.append(f'<rect x="20" y="{y}" width="230" height="30" rx="6" fill="{col}" fill-opacity=".14" '
                 f'stroke="{col}" stroke-opacity=".7"/>'
                 f'<text x="32" y="{y + 20}" font-size="13" font-weight="700" fill="{col}">MPPT {i}</text>'
                 f'<text x="100" y="{y + 20}" font-size="12" fill="{txt}">'
                 + (f"{v:.0f} V · {a:.1f} A · {p:.1f} kW" if have and pd.notna(v) and pd.notna(a) else "—")
                 + "</text>")
        ty = iy0 + 24 + k * 18
        path = f"M250,{y + 15} C390,{y + 15} 390,{ty} {ix0},{ty}"
        frac = p / FLOW_MPPT_KW
        o.append(f'<path d="{path}" fill="none" stroke="{col}" stroke-opacity=".22" stroke-width="{2 + 9 * frac:.1f}"/>')
        if on:
            o.append(f'<path d="{path}" fill="none" stroke="{col}" stroke-width="{2.5 + 5 * frac:.1f}" class="sf" '
                     f'style="animation-duration:{_flow_dur(frac)}"/>')
    o.append(f'<rect x="{ix0}" y="{iy0}" width="{ix1 - ix0}" height="{iy1 - iy0}" rx="10" fill="#0f172a" '
             f'stroke="{st_col}" stroke-width="2"/>'
             f'<text x="{(ix0 + ix1) / 2}" y="{iy0 + 32}" font-size="15" font-weight="800" fill="{txt}" '
             f'text-anchor="middle">อินเวอร์เตอร์</text>'
             f'<text x="{(ix0 + ix1) / 2}" y="{iy0 + 54}" font-size="12" fill="{mute}" text-anchor="middle">'
             f'{inv_label}</text>'
             f'<text x="{(ix0 + ix1) / 2}" y="{iy0 + 86}" font-size="24" font-weight="800" fill="{COLOR_GRID2}" '
             f'text-anchor="middle">{pac:.1f} kW</text>'
             f'<text x="{(ix0 + ix1) / 2}" y="{iy0 + 110}" font-size="12" fill="{mute}" text-anchor="middle">'
             + (f"Heatsink {row['t_heatsink']:.0f} °C · {row['hz']:.2f} Hz"
                if have and pd.notna(row.get("t_heatsink")) and pd.notna(row.get("hz")) else "")
             + "</text>")

    # ---- AC 3 เฟส (ขวา) → โรงงาน ----
    fx0, fx1 = 980, 1180
    for k, (ph, col_name) in enumerate(se.PHASES.items()):
        a = row.get(col_name) if have else None
        vv = row.get(se.AC_V_COLS[k]) if have else None
        frac = (a or 0) / se.AC_IMAX_A if have and pd.notna(a) else 0.0
        on = have and pac > 0.2
        col = PHASE_COLORS[ph] if on else FLOW_IDLE
        y = iy0 + 38 + k * 32
        path = f"M{ix1},{y} L{fx0},{y}"
        o.append(f'<path d="{path}" fill="none" stroke="{col}" stroke-opacity=".22" stroke-width="{2 + 9 * frac:.1f}"/>')
        if on:
            o.append(f'<path d="{path}" fill="none" stroke="{col}" stroke-width="{2.5 + 5 * frac:.1f}" class="sf" '
                     f'style="animation-duration:{_flow_dur(frac)}"/>')
        o.append(f'<text x="{ix1 + 20}" y="{y - 8}" font-size="12" font-weight="700" fill="{col}">เฟส {ph} · '
                 + (f"{a:.1f} A · {vv:.0f} V" if have and pd.notna(a) and pd.notna(vv) else "—") + "</text>")
    o.append(f'<rect x="{fx0}" y="{iy0}" width="{fx1 - fx0}" height="{iy1 - iy0}" rx="10" fill="#0f172a" '
             f'stroke="{COLOR_GRID2}" stroke-width="2"/>'
             f'<text x="{(fx0 + fx1) / 2}" y="{iy0 + 36}" font-size="15" font-weight="800" fill="{txt}" '
             f'text-anchor="middle">โรงงาน 33/5</text>'
             f'<text x="{(fx0 + fx1) / 2}" y="{iy0 + 58}" font-size="12" fill="{mute}" text-anchor="middle">'
             f'Solar MDB → MDB 22 kV</text>'
             f'<text x="{(fx0 + fx1) / 2}" y="{iy0 + 96}" font-size="24" font-weight="800" fill="{COLOR_GRID2}" '
             f'text-anchor="middle">{pac:.1f} kW</text>')

    # ---- แถบเวลาทั้งวัน: กำลัง AC ราย 15 นาที + ตำแหน่งเวลาที่กำลังดู ----
    bx0, bx1, by0, by1 = 20, W - 20, 326, 382
    d0 = t.normalize() + pd.Timedelta(hours=5, minutes=30)
    span = 14 * 3600.0

    def px(ts):
        return bx0 + (bx1 - bx0) * min(max((ts - d0).total_seconds() / span, 0), 1)
    o.append(f'<rect x="{bx0}" y="{by0}" width="{bx1 - bx0}" height="{by1 - by0}" fill="#0f172a" rx="6"/>')
    if not day_pac.empty:
        pts = " ".join(f"{px(r.slot):.1f},{by1 - (by1 - by0 - 6) * min(r.kw / se.RATED_KW, 1):.1f}"
                       for r in day_pac.itertuples())
        o.append(f'<polyline points="{bx0},{by1} {pts} {bx1},{by1}" fill="{COLOR_SOLAR}" fill-opacity=".25" '
                 f'stroke="{COLOR_SOLAR}" stroke-width="1.5"/>')
    for hh in range(6, 20, 2):
        xx = px(t.normalize() + pd.Timedelta(hours=hh))
        o.append(f'<text x="{xx:.1f}" y="{by1 + 14}" font-size="10" fill="{mute}" text-anchor="middle">{hh:02d}:00</text>')
    cx = px(t)
    o.append(f'<line x1="{cx:.1f}" y1="{by0 - 6}" x2="{cx:.1f}" y2="{by1}" stroke="#f8fafc" stroke-width="2"/>'
             f'<circle cx="{cx:.1f}" cy="{by0 - 6}" r="4" fill="#f8fafc"/>')
    o.append("</svg>")
    return "".join(o)


def _flow_board(raw: pd.DataFrame, day: pd.Timestamp, inv_label: str, outage_slots) -> None:
    """ผังพลังงานเคลื่อนไหลของเครื่องที่เลือก — ลากเวลา หรือกด ▶ เล่นทั้งวัน (ทีละ 10 นาที)"""
    lo, hi = 5 * 60 + 30, 19 * 60 + 30
    ctx = f"{inv_label}|{day:%Y%m%d}"
    if st.session_state.get("solar_flow_ctx") != ctx:      # เปลี่ยนเครื่อง/วัน → เริ่มที่เวลาที่ผลิตสูงสุด
        st.session_state["solar_flow_ctx"] = ctx
        st.session_state["solar_flow_play"] = False
        pk = raw.loc[raw["pac_kw"].idxmax(), "ts"] if raw["pac_kw"].notna().any() else day + pd.Timedelta(hours=12)
        st.session_state["solar_flow_cursor"] = int(pk.hour * 60 + pk.minute) // FLOW_STEP_MIN * FLOW_STEP_MIN
    playing = bool(st.session_state.get("solar_flow_play"))
    out_set = set(pd.to_datetime(pd.Series(list(outage_slots))) if outage_slots is not None else [])
    day_pac = (raw.assign(slot=raw["ts"].dt.floor("15min")).groupby("slot", as_index=False)["pac_kw"].mean()
               .rename(columns={"pac_kw": "kw"}))

    def _play(on: bool):
        st.session_state["solar_flow_play"] = on

    def _jump(minute: int):
        st.session_state["solar_flow_play"] = False
        st.session_state["solar_flow_cursor"] = minute
        st.session_state["solar_flow_nonce"] = st.session_state.get("solar_flow_nonce", 0) + 1

    def _slid(key: str):
        # กรองค่าเก่าจากสไลเดอร์ที่ถูกสร้างใหม่ระหว่างเล่น (ปัญหาเดียวกับผังไลน์ผลิต 8503)
        if key != st.session_state.get("solar_flow_sl_key"):
            return
        v = st.session_state.get(key)
        if v is None:
            return
        m = v.hour * 60 + v.minute
        if m == int(key.rsplit("_", 1)[1]):
            return
        st.session_state.update(solar_flow_cursor=m, solar_flow_play=False,
                                solar_flow_nonce=st.session_state.get("solar_flow_nonce", 0) + 1)

    @st.fragment(run_every=FLOW_TICK if playing else None)
    def board(playing_at_def=playing):
        # run_every ถูกตรึงตอนประกาศ — สถานะเล่น/หยุดเปลี่ยนต้อง rerun ทั้งหน้าให้ประกาศใหม่
        if bool(st.session_state.get("solar_flow_play")) != playing_at_def:
            st.rerun()
        cur = max(lo, min(hi, int(st.session_state.get("solar_flow_cursor", 12 * 60))))
        if playing_at_def:
            nxt = cur + FLOW_STEP_MIN
            if nxt > hi:                                  # ถึงปลายวัน → หยุดเอง
                st.session_state["solar_flow_play"] = False
                st.session_state["solar_flow_cursor"] = hi
                st.rerun()
            cur = nxt
        st.session_state["solar_flow_cursor"] = cur
        sl_key = f"solar_flow_sl_{st.session_state.get('solar_flow_nonce', 0)}_{cur}"
        st.session_state["solar_flow_sl_key"] = sl_key
        c_sl, c_b1, c_b2 = st.columns([6, 1, 1], vertical_alignment="bottom")
        with c_sl:
            st.slider("เวลา", min_value=dtime(lo // 60, lo % 60), max_value=dtime(hi // 60, hi % 60),
                      value=dtime(cur // 60, cur % 60), step=timedelta(minutes=FLOW_STEP_MIN), format="HH:mm",
                      key=sl_key, on_change=_slid, args=(sl_key,), label_visibility="collapsed")
        with c_b1:
            if playing_at_def:
                st.button(":material/pause: หยุด", key="solar_flow_pause", width="stretch", on_click=_play,
                          args=(False,))
            else:
                st.button(":material/play_arrow: เล่นทั้งวัน", key="solar_flow_go", width="stretch",
                          on_click=_play, args=(True,), type="primary")
        with c_b2:
            st.button(":material/skip_previous: 06:00", key="solar_flow_home", width="stretch", on_click=_jump,
                      args=(6 * 60,))
        t = day + pd.Timedelta(minutes=cur)
        prev = raw[(raw["ts"] <= t) & (raw["ts"] > t - pd.Timedelta(minutes=3))]
        row = prev.iloc[-1] if not prev.empty else None
        n_out_now = t.floor("15min") in out_set
        svg = _flow_svg(row, t, day_pac, inv_label, n_out_now)
        # ต้องใช้ st.markdown ห่อ <div> และทำเป็นบรรทัดเดียว (st.html ไม่วาด SVG — บทเรียนจากผังไลน์ผลิต 8503)
        st.markdown("<div>\n" + svg.replace("\r", " ").replace("\n", " ") + "\n</div>", unsafe_allow_html=True)
        st.caption("เส้นวิ่ง = ทิศทางพลังงาน · ยิ่งหนาและวิ่งเร็ว = กำลังมาก · เส้นเทานิ่ง = ไม่มีกำลังไหล · "
                   "แถบล่าง = กำลัง AC ทั้งวัน เส้นขาวคือเวลาที่กำลังดู · ข้อมูลจริงจาก EVE ทุก ~65 วินาที")

    board()


def _intraday(raw: pd.DataFrame, day: pd.Timestamp, outage_slots: pd.Series | None = None,
              inv_label: str = "") -> None:
    """รายละเอียดทั้งวันของเครื่องเดียว: แถบสถานะ · KPI · กระแส DC ต่อ MPPT · กระแส AC ต่อเฟส · กำลัง · แรงดัน DC

    outage_slots = ช่วง 15 นาทีที่ solar_etl ตรวจพบว่าเครื่องนี้หยุดจ่ายไฟขณะเครื่องอื่นยังผลิต
    (อินเวอร์เตอร์บางตัวยังรายงาน "Grid connected" ตอนหยุด — แถบสถานะของเครื่องอย่างเดียวจึงไม่พอ)"""
    raw = raw[raw["flag"] == 0].sort_values("ts").copy() if not raw.empty else raw
    if raw.empty:
        st.info("ไม่มีข้อมูลของเครื่องนี้ในวันที่เลือก")
        return
    # แสดงเฉพาะช่วง 05:30–19:30 — บาง logger (#6) ส่งแถวตอนกลางคืนมาด้วย (Pac = 0) ถ้าไม่ตัด
    # เส้นจะลากออกนอกแกนซ้าย และกราฟบีบจนช่วงกลางวันเหลือนิดเดียว
    t0, t1 = day + pd.Timedelta(hours=5, minutes=30), day + pd.Timedelta(hours=19, minutes=30)
    n_night = int((~raw["ts"].between(t0, t1)).sum())
    raw = raw[raw["ts"].between(t0, t1)].copy()
    if raw.empty:
        st.warning(f"วันนี้เครื่องนี้ส่งข้อมูลมาเฉพาะช่วงกลางคืน ({n_night} จุด) ไม่มีข้อมูลช่วงผลิตเลย — "
                   "data logger ของเครื่องนี้มีปัญหา ให้ตรวจสายสัญญาณ/ตัว Collector")
        return
    # logger ส่งข้อมูลน้อย (ปกติ ~650 จุด/วัน) — แต่ละจุดห่างกันจนเป็นเส้นไม่ได้ ต้องแสดงเป็นจุด
    sparse = len(raw) < 300
    if sparse:
        st.warning(f"วันนี้เครื่องนี้ส่งข้อมูลแค่ {len(raw)} จุดในช่วงกลางวัน (ปกติ ~650) — กราฟด้านล่างเป็นจุด "
                   "เท่าที่มี ไม่ใช่ภาพเต็มวัน · ยอดผลิตรายวันยังถูกต้องเพราะใช้มิเตอร์สะสมของเครื่อง")
    # ช่วงที่ logger ไม่ส่งข้อมูล (ห่าง > 3 นาที) — ตัดเส้นให้ขาด ไม่ลากเส้นตรงข้ามช่องว่างจนดูเหมือนมีข้อมูล
    raw["seg"] = (raw["ts"].diff() > pd.Timedelta(minutes=3)).cumsum()
    raw["สถานะ"] = raw["status"].where(raw["status"].isin(["Grid connected", "Checking", "Standby"]), "Fault")
    raw["ts_end"] = raw["ts"].shift(-1).fillna(raw["ts"] + pd.Timedelta(minutes=1))
    raw["ts_end"] = raw[["ts_end"]].assign(cap=raw["ts"] + pd.Timedelta(minutes=3)).min(axis=1)
    raw["imb"] = se.phase_imbalance(raw)
    x = alt.X("ts:T", title=None, axis=alt.Axis(format="%H:%M", labelAngle=0, tickCount=8),
              scale=alt.Scale(domain=[t0.isoformat(), t1.isoformat()]))

    def line(d: pd.DataFrame, width: float = 1.6) -> alt.Chart:
        """เส้นตามเวลา ตัดส่วนเกินกรอบ · ข้อมูลน้อยให้มีจุดด้วย ไม่งั้นช่วงที่มีจุดเดียวจะมองไม่เห็นเลย"""
        return alt.Chart(d).mark_line(strokeWidth=width, clip=True,
                                      point=alt.OverlayMarkDef(size=18, filled=True) if sparse else False)

    # ---- KPI ของวัน ----
    prod = raw[raw["pdc_kw"].fillna(0) > 5]
    idc_max = raw[[f"idc{i}" for i in se.MPPT]].max()
    iac_max = raw[list(se.PHASES.values())].max()
    n_gap = int(raw["seg"].max())
    with st.container(horizontal=True):
        st.metric("Idc สูงสุด", f"{idc_max.max():.1f} A", f"MPPT {int(idc_max.idxmax()[3:])}", delta_color="off",
                  border=True)
        st.metric("Iac สูงสุด", f"{iac_max.max():.1f} A",
                  f"เฟส {[p for p, c in se.PHASES.items() if c == iac_max.idxmax()][0]} · "
                  f"{iac_max.max() / se.AC_IMAX_A * 100:.0f}% ของพิกัด", delta_color="off", border=True)
        st.metric("เฟสไม่สมดุล (ค่ากลาง)", f"{raw['imb'].median():.1f} %" if raw["imb"].notna().any() else "—",
                  f"สูงสุด {raw['imb'].max():.1f}%" if raw["imb"].notna().any() else None, delta_color="off",
                  border=True)
        st.metric("Pac สูงสุด", f"{raw['pac_kw'].max():.1f} kW",
                  f"{raw['pac_kw'].max() / se.RATED_KW * 100:.0f}% ของ {se.RATED_KW:.0f} kW", delta_color="off",
                  border=True)
        st.metric("แรงดัน AC เฉลี่ย", f"{prod[se.AC_V_COLS].mean().mean():.0f} V" if len(prod) else "—",
                  f"{prod['hz'].mean():.2f} Hz" if len(prod) else None, delta_color="off", border=True)
        st.metric("จุดข้อมูล", f"{len(raw):,}", f"ขาดช่วง {n_gap} ครั้ง" if n_gap else "ต่อเนื่อง",
                  delta_color="inverse" if n_gap else "off", border=True)
        n_out = 0 if outage_slots is None else len(outage_slots)
        st.metric("หยุดจ่ายไฟกลางวัน", f"{n_out * 15} นาที",
                  "ขณะเครื่องอื่นยังผลิต" if n_out else "ไม่พบ", delta_color="inverse" if n_out else "off",
                  border=True)

    # ---- ผังพลังงานเคลื่อนไหล ----
    st.markdown("**พลังงานเคลื่อนไหล** — แผง → อินเวอร์เตอร์ → โรงงาน ณ เวลาที่เลือก")
    _flow_board(raw, day, inv_label, outage_slots)

    # ---- แถบสถานะตลอดวัน: แถวบน = ที่เครื่องรายงานเอง · แถวล่าง = ที่ระบบตรวจพบจากการเทียบเครื่องอื่น ----
    rep = raw[["ts", "ts_end", "สถานะ", "status", "grid_status", "pac_kw"]].assign(แถว=STRIP_ROWS[0])
    parts = [rep]
    if n_out:
        s = pd.to_datetime(pd.Series(list(outage_slots)))
        parts.append(pd.DataFrame({"ts": s, "ts_end": s + pd.Timedelta(minutes=15), "สถานะ": OUTAGE_LABEL,
                                   "status": "ไม่จ่ายไฟ", "แถว": STRIP_ROWS[1]}))
    strip_df = pd.concat(parts, ignore_index=True)
    # ชื่อและคำอธิบายสีเขียนนอกกราฟ — ใส่ title หรือ legend ไว้ในกราฟ Streamlit จะหักความสูงไปให้
    # จนแถบเหลือเส้นบาง ๆ และป้ายแถวซ้อนกัน (เจอทั้งสองแบบบนหน้าจริง 6 ต.ค. 69)
    chips = " ".join(f'<span style="display:inline-block;width:11px;height:11px;border-radius:2px;'
                     f'background:{c};margin:0 4px 0 10px;vertical-align:-1px"></span>{k}'
                     for k, c in STATUS_COLORS.items())
    st.markdown(f"**สถานะตลอดวัน** — แถวบน = ที่เครื่องรายงานเอง · แถวล่าง = ที่ระบบตรวจพบจากการเทียบเครื่องอื่น "
                f"· ช่องว่าง = logger ไม่ส่งข้อมูล<br><small>{chips}</small>", unsafe_allow_html=True)
    strip = alt.Chart(strip_df).mark_rect(clip=True).encode(
        x=x, x2="ts_end:T",
        y=alt.Y("แถว:N", sort=STRIP_ROWS, title=None, scale=alt.Scale(domain=STRIP_ROWS, paddingInner=0.2),
                axis=alt.Axis(labelLimit=0, labelFontSize=12)),
        color=alt.Color("สถานะ:N", scale=alt.Scale(domain=list(STATUS_COLORS), range=list(STATUS_COLORS.values())),
                        legend=None),
        tooltip=[alt.Tooltip("ts:T", title="เวลา", format="%H:%M:%S"), alt.Tooltip("แถว:N", title="แหล่ง"),
                 alt.Tooltip("status:N", title="สถานะ"), alt.Tooltip("grid_status:N", title="Grid"),
                 alt.Tooltip("pac_kw:Q", title="Pac (kW)", format=".1f")])
    st.altair_chart(strip.properties(height=96), width="stretch")

    def melt(cols: dict, name: str, value: str) -> pd.DataFrame:
        return pd.concat([raw[["ts", "seg"]].assign(**{name: k, value: raw[c]}) for k, c in cols.items()],
                         ignore_index=True).dropna(subset=[value])

    tip_t = alt.Tooltip("ts:T", title="เวลา", format="%H:%M:%S")
    H = 300                                   # ทุกกราฟสูงเท่ากัน · หน่วยอยู่ในชื่อกราฟ (แกน y ไม่ใส่ชื่อ ไม่ให้ทับตัวเลข)

    def panel(chart, refs, title):
        # ชื่อกราฟเขียนนอกกราฟ — ใน title ของ Vega ชื่อถูกตัดซ้ายเมื่อแกนขวามีป้ายยาว (① ④ บนหน้าจริง)
        st.markdown(f"**{title}**")
        st.altair_chart(_with_refs(chart, refs).properties(height=H), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        d = melt({f"MPPT {i}": f"idc{i}" for i in se.MPPT}, "MPPT", "A")
        ch = line(d).encode(
            x=x, y=alt.Y("A:Q", title=None, scale=alt.Scale(domain=[0, se.MPPT_IMAX_A * 1.08])),
            color=MPPT_COLOR, detail="seg:N", tooltip=[tip_t, "MPPT", alt.Tooltip("A:Q", title="A", format=".2f")])
        panel(ch, [(se.MPPT_IMAX_A, f"สูงสุด {se.MPPT_IMAX_A:.0f} A", COLOR_ALERT),
                   (round(se.STRING_IMP_A * 2, 2), f"2 สตริง {se.STRING_IMP_A * 2:.1f} A", REF_MUTED),
                   (se.STRING_IMP_A, f"1 สตริง {se.STRING_IMP_A:.1f} A", REF_MUTED)],
              "① กระแส DC ขาเข้า ต่อ MPPT (A)")
    with c2:
        d = melt(se.PHASES, "เฟส", "A")
        ch = line(d).encode(
            x=x, y=alt.Y("A:Q", title=None, scale=alt.Scale(domain=[0, se.AC_IMAX_A * 1.08])),
            color=PHASE_COLOR, detail="seg:N", tooltip=[tip_t, "เฟส", alt.Tooltip("A:Q", title="A", format=".1f")])
        panel(ch, [(se.AC_IMAX_A, f"พิกัด {se.AC_IMAX_A:.0f} A", COLOR_ALERT)],
              "② กระแส AC ขาออก ต่อเฟส R / S / T (A)")
    c3, c4 = st.columns(2)
    with c3:
        d = melt({"DC ขาเข้า": "pdc_kw", "AC ขาออก": "pac_kw"}, "ฝั่ง", "kW")
        ch = line(d, 1.8).encode(
            x=x, y=alt.Y("kW:Q", title=None, scale=alt.Scale(domain=[0, se.RATED_KW * 1.12])),
            color=alt.Color("ฝั่ง:N", scale=alt.Scale(domain=["DC ขาเข้า", "AC ขาออก"], range=[COLOR_SOLAR, COLOR_GRID2]),
                            legend=alt.Legend(orient="bottom", title=None, columns=3, symbolType="stroke",
                                              symbolStrokeWidth=3)),
            detail="seg:N", tooltip=[tip_t, "ฝั่ง", alt.Tooltip("kW:Q", title="kW", format=".2f")])
        panel(ch, [(se.RATED_KW, f"พิกัด {se.RATED_KW:.0f} kW", COLOR_ALERT)],
              "③ กำลังไฟฟ้า DC ขาเข้า เทียบ AC ขาออก (kW)")
    with c4:
        d = melt({f"MPPT {i}": f"vdc{i}" for i in se.MPPT}, "MPPT", "V")
        ch = line(d).encode(
            x=x, y=alt.Y("V:Q", title=None, scale=alt.Scale(domain=[0, 1000])),
            color=MPPT_COLOR, detail="seg:N", tooltip=[tip_t, "MPPT", alt.Tooltip("V:Q", title="V", format=".0f")])
        panel(ch, [(se.MPPT_V_MAX, f"MPPT สูงสุด {se.MPPT_V_MAX:.0f} V", REF_MUTED),
                   (se.MPPT_V_MIN, f"MPPT ต่ำสุด {se.MPPT_V_MIN:.0f} V", REF_MUTED)],
              "④ แรงดัน DC ขาเข้า ต่อ MPPT (V)")
    st.caption(
        "① MPPT ที่ต่อ 2 สตริงควรมีกระแสราว 2 เท่าของ MPPT ที่ต่อ 1 สตริง · "
        "② กระแส 3 เฟสควรใกล้กัน (ไม่สมดุลเกิน ~5% ให้ตรวจขั้วสาย/เบรกเกอร์ฝั่ง AC) · "
        "③ เส้น DC กับ AC ห่างกัน = การสูญเสียในอินเวอร์เตอร์ (ปกติ 2–4%) · AC ตกเป็น 0 ขณะ DC ยังมี = เครื่องหยุดจ่ายไฟ · "
        "④ แรงดันพุ่งขึ้น ~850 V ค้าง = อินเวอร์เตอร์หยุดดึงไฟจากแผง · เส้นขาด = ช่วงที่ logger ไม่ส่งข้อมูล"
        + (f" · ซ่อนข้อมูลกลางคืน {n_night} จุด" if n_night else ""))


# ---------------------------------------------------------------------------
# หน้าแท็บ
# ---------------------------------------------------------------------------
def render(kpi_card) -> None:
    sig = data_paths.solar_signature()
    if not sig or not all(m for _, m in sig):
        st.info(
            "ยังไม่มีข้อมูล Solar inverter ในระบบ\n\n"
            "1. ดึงรายงาน **รายการละเอียดแต่ละรายการ** ของอินเวอร์เตอร์ทั้ง 11 ตัวจากเว็บ EVE "
            "(ไฟล์จะลงใน Downloads)\n"
            "2. กดปุ่ม **อัปเดต Solar** ด้านล่าง หรือดับเบิลคลิกไอคอน **อัปเดต Solar** บนเดสก์ท็อป"
        )
        _update_controls("solar_update_empty")
        _last_update_panel()
        return
    daily_all, prof_all = _load(sig)
    last = daily_all["date"].max()
    last_ts = daily_all["last_ts"].max()
    all_dates = sorted(daily_all["date"].unique(), reverse=True)

    # ---- ปุ่มอัปเดต + ตัวเลือกช่วงเวลา + เป้า ----
    with st.container(horizontal=True, vertical_alignment="center"):
        _update_controls("solar_update_btn")
        period = st.segmented_control("ช่วงเวลา", list(PERIODS), default="30 วัน",
                                      key="solar_period") or "30 วัน"
        if PERIODS[period] == 0:
            pick = st.selectbox("วันที่", all_dates, key="solar_pick_day",
                                format_func=lambda x: pd.Timestamp(x).strftime("%d/%m/%Y (%a)"))
        target_name = st.selectbox("เป้าผลผลิตต่อวัน", list(se.TARGET_KWH_DAY), index=1,
                                   key="solar_target")
        st.caption(f"ข้อมูล EVE ล่าสุด {last_ts:%d/%m/%Y %H:%M} · "
                   f"อินเวอร์เตอร์ {se.N_INVERTERS} ชุด × {se.RATED_KW:.0f} kW · {se.KWP_TOTAL:,.0f} kWp")
    _last_update_panel()
    days_back = PERIODS[period]
    single = days_back == 0                            # โหมดรายวัน — ทุกส่วนของแท็บแสดงวันเดียว
    if single:
        start = end = pd.Timestamp(pick)
    else:
        end = last
        start = (last - pd.Timedelta(days=days_back - 1)) if days_back else daily_all["date"].min()
        start = max(start, daily_all["date"].min())  # ข้อมูลเริ่มหลังช่วงที่ขอ ให้โชว์วันแรกที่มีจริง
    daily = daily_all[daily_all["date"].between(start, end)].copy()
    prof = prof_all[prof_all["date"].between(start, end)].copy()
    # กราฟรายวัน/เจาะรายเครื่องในโหมดรายวัน: แสดง 14 วันย้อนหลังถึงวันที่เลือก เห็นแนวโน้มรอบ ๆ วันนั้น
    trend = (daily_all[daily_all["date"].between(end - pd.Timedelta(days=13), end)].copy()
             if single else daily)
    target = se.TARGET_KWH_DAY[target_name]
    labels = _inv_labels(daily_all)
    inv_scale = _inv_scale(labels)

    # ---- KPI ----
    sys_day = daily.groupby("date", as_index=False).agg(ac_kwh=("ac_kwh", "sum"), dc_kwh=("dc_kwh", "sum"))
    sys_slot = prof.groupby(["date", "slot", "tod"], as_index=False)["pac_mean"].sum()
    n_days = len(sys_day)
    ac_total, dc_total = sys_day["ac_kwh"].sum(), sys_day["dc_kwh"].sum()
    # วันที่ข้อมูลไม่ครบวัน (ดึง export ระหว่างวัน / export รอบก่อนจบตอนบ่าย) ไม่เอามานับค่าเฉลี่ย
    # ถึงเป้า ดีสุด-แย่สุด — ไม่งั้นวันพวกนี้ดูเหมือนโรงงาน Solar ผลิตตก ทั้งที่แค่ข้อมูลขาด
    # โหมดรายวันไม่ตัดทิ้ง (ผู้ใช้เลือกดูวันนั้นเอง) แต่บอกว่าไม่ครบวัน
    gaps = se.partial_days(daily)
    full_day = sys_day if single else sys_day[~sys_day["date"].isin(list(gaps))]
    n_full = len(full_day)
    avg_day = full_day["ac_kwh"].sum() / n_full if n_full else 0
    if not gaps:
        partial_note = ""
    elif single:
        partial_note = f" · ข้อมูลถึง {next(iter(gaps.values())):%H:%M} ยังไม่ครบวัน"
    else:
        partial_note = (" · ไม่นับวันที่ข้อมูลไม่ครบ "
                        + ", ".join(f"{pd.Timestamp(d):%d/%m} (ถึง {t:%H:%M})" for d, t in gaps.items()))
    peak = sys_slot.loc[sys_slot["pac_mean"].idxmax()] if not sys_slot.empty else None
    summ = se.inverter_summary(daily)
    al = se.alerts(daily)
    n_bad = len({a["inv_no"] for a in al if a["level"] in ("error", "warning")})

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        gap_kwh = float(daily["gap_kwh"].sum()) if "gap_kwh" in daily.columns else 0.0
        kpi_card("ผลิตได้ (AC)", f"{ac_total:,.0f} kWh", COLOR_SOLAR,
                 (f"วันที่ {_fmt_date(start)}" if single else f"{n_days} วัน · {_fmt_date(start)} – {_fmt_date(end)}")
                 + (f" · + {gap_kwh:,.0f} kWh ระบุวันไม่ได้ (logger ขาด)" if gap_kwh >= 1 else ""))
    with k2:
        pct = avg_day / target * 100 if target else 0
        kpi_card("ผลิตวันนั้น" if single else "เฉลี่ยต่อวัน", f"{avg_day:,.0f} kWh",
                 COLOR_COST if pct >= 100 else COLOR_ALERT,
                 f"{pct:.0f}% ของเป้า {target:,.0f} kWh ({target_name}){partial_note}")
    with k3:
        kpi_card("Specific yield", f"{avg_day / se.KWP_TOTAL:.2f} kWh/kWp/วัน", COLOR_GRID2,
                 "เกณฑ์ประเทศไทยที่ควรได้ 3.5–4.5")
    with k4:
        if peak is not None:
            kpi_card("กำลังสูงสุด (15 นาที)", f"{peak['pac_mean']:,.0f} kW", "#9333ea",
                     f"{peak['pac_mean'] / se.AC_TOTAL_KW * 100:.0f}% ของ {se.AC_TOTAL_KW:,.0f} kW · "
                     f"{_fmt_date(peak['date'])} {int(peak['tod']):02d}:{int(round(peak['tod'] % 1 * 60)):02d}")
    with k5:
        ok = daily["eff_pct"].notna()
        ac_e, dc_e = daily.loc[ok, "ac_kwh"].sum(), daily.loc[ok, "dc_kwh"].sum()
        eff = ac_e / dc_e * 100 if dc_e > 1 else 0
        kpi_card("ประสิทธิภาพ DC→AC", f"{eff:.1f} %", COLOR_COST if eff >= 95 else COLOR_SOLAR,
                 f"ควรได้ 96–98% · คิดเฉพาะวันที่ข้อมูลครบ ≥ {se.EFF_MIN_COVERAGE:.0f}%")
    with k6:
        kpi_card("เครื่องที่ต้องตรวจ", f"{n_bad} เครื่อง", COLOR_ALERT if n_bad else COLOR_COST,
                 f"จาก {len(al)} รายการแจ้งเตือนในช่วงนี้" if al else "ไม่พบความผิดปกติในช่วงนี้")

    st.markdown("")

    # ---- ผลิตรายวัน แยกเครื่อง + โปรไฟล์ 15 นาที ----
    col_l, col_r = st.columns([3, 2])
    with col_l:
        with st.container(border=True, key="solar_daily_card"):
            st.subheader("ผลผลิตรายวัน แยกตามอินเวอร์เตอร์ (AC kWh)"
                         + (f" · 14 วันถึง {_fmt_date(end)}" if single else ""))
            tr_day = trend.groupby("date", as_index=False)["ac_kwh"].sum().rename(columns={"ac_kwh": "รวมทั้งระบบ"})
            d = trend.merge(tr_day, on="date")
            d["สัดส่วน"] = d["ac_kwh"] / d["รวมทั้งระบบ"] * 100
            d["เลือก"] = (d["date"] == end) if single else True
            t_max, t_min = se.TARGET_KWH_DAY["MAX (PSH 4.5)"], se.TARGET_KWH_DAY["MIN (PSH 4.0)"]
            # แกนวันแบบช่อง (ordinal) — 1 ช่องต่อ 1 วัน แท่งกว้างเต็มช่อง ไม่มีป้ายวันซ้ำ
            x_day = alt.X("yearmonthdate(date):O", title="วันที่",
                          axis=alt.Axis(format="%d/%m", formatType="time", labelAngle=0, labelOverlap=True))
            bars = (
                alt.Chart(d)
                .mark_bar()
                .encode(
                    opacity=alt.condition(alt.datum["เลือก"], alt.value(1.0), alt.value(0.35)),
                    x=x_day,
                    # เผื่อที่ด้านบนให้ป้าย MAX และตัวเลขบนหัวแท่งไม่ชนขอบ
                    y=alt.Y("ac_kwh:Q", title="kWh", scale=alt.Scale(
                        domain=[0, max(t_max * 1.08, float(tr_day["รวมทั้งระบบ"].max()) * 1.1)], nice=False)),
                    color=alt.Color("เครื่อง:N", scale=inv_scale, title="อินเวอร์เตอร์",
                                    legend=alt.Legend(orient="bottom", columns=len(labels))),
                    order=alt.Order("inv_no:Q"),
                    tooltip=[alt.Tooltip("date:T", title="วันที่", format="%d/%m/%Y"), "เครื่อง", "sn",
                             alt.Tooltip("ac_kwh:Q", title="ผลิตได้ (kWh)", format=",.1f"),
                             alt.Tooltip("สัดส่วน:Q", title="สัดส่วนของวัน (%)", format=".1f"),
                             alt.Tooltip("รวมทั้งระบบ:Q", title="รวมทั้งระบบ (kWh)", format=",.0f"),
                             alt.Tooltip("pac_max:Q", title="สูงสุด (kW)", format=",.0f"),
                             alt.Tooltip("outage_min:Q", title="หยุดกลางวัน (นาที)"),
                             alt.Tooltip("coverage_pct:Q", title="ข้อมูลครบ (%)", format=".0f")],
                )
            )
            # โซนเป้า MIN–MAX + เส้น MAX (เขียว) / MIN (แดง) พร้อมป้ายบนเส้น
            tgt = pd.DataFrame({
                "y": [t_max, t_min], "ระดับ": ["MAX", "MIN"],
                "ป้าย": [f"MAX {t_max:,.0f} kWh · PSH 4.5", f"MIN {t_min:,.0f} kWh · PSH 4.0"],
                "สี": [TARGET_MAX_COLOR, TARGET_MIN_COLOR],
                "ความหมาย": ["แดดปกติ — ผลิตได้เต็มศักยภาพ", "แดดไม่เอื้อ/ฤดูฝน — ต่ำกว่านี้ถือว่าผลิตต่ำ"],
            })
            band = alt.Chart(pd.DataFrame({"lo": [t_min], "hi": [t_max]})).mark_rect(
                color=TARGET_MAX_COLOR, opacity=0.08).encode(y=alt.Y("lo:Q", axis=None), y2="hi:Q")
            tgt_tip = [alt.Tooltip("ระดับ:N", title="เป้า"), alt.Tooltip("y:Q", title="kWh/วัน", format=",.0f"),
                       alt.Tooltip("ความหมาย:N", title="ความหมาย")]
            # ป้าย MAX/MIN อยู่บนแกนขวา (นอกพื้นที่กราฟ) ตรงความสูงของเส้นพอดี — วางป้ายในกราฟ
            # ฝั่งไหนก็ชนตัวเลขบนหัวแท่งของวันที่ผลิตใกล้เป้าได้เสมอ (ลองแล้วทั้งซ้ายและขวา)
            lbl = (f"datum.value == {t_max} ? 'MAX {t_max:,.0f} · PSH 4.5' : "
                   f"datum.value == {t_min} ? 'MIN {t_min:,.0f} · PSH 4.0' : ''")
            rules = alt.Chart(tgt).mark_rule(strokeDash=[8, 4], strokeWidth=2).encode(
                y=alt.Y("y:Q", axis=alt.Axis(
                    orient="right", values=[t_min, t_max], labelExpr=lbl, title=None, grid=False,
                    ticks=False, domain=False, labelFontSize=12, labelFontWeight="bold", labelPadding=6,
                    labelColor=alt.condition(f"datum.value == {t_max}",
                                             alt.value(TARGET_MAX_COLOR), alt.value(TARGET_MIN_COLOR)))),
                color=alt.Color("สี:N", scale=None, legend=None), tooltip=tgt_tip)
            # ยอดรวมบนหัวแท่ง สีตามระดับ: เขียว ≥ MAX · ส้ม อยู่ในโซน · แดง < MIN (โชว์เมื่อไม่เกิน 31 วัน)
            layers = [band, bars, rules]
            if tr_day["date"].nunique() <= 31:
                tops = tr_day.assign(สี=np.select(
                    [tr_day["รวมทั้งระบบ"] >= t_max, tr_day["รวมทั้งระบบ"] >= t_min],
                    [TARGET_MAX_COLOR, TARGET_MID_COLOR], TARGET_MIN_COLOR))
                top_enc = dict(x=x_day, y=alt.Y("รวมทั้งระบบ:Q", axis=None),
                               text=alt.Text("รวมทั้งระบบ:Q", format=",.0f"))
                # ขอบเข้มรอบตัวเลข (halo) — วันที่ผลิตใกล้เป้า ตัวเลขจะทับเส้นประ ยังอ่านออก
                layers.append(alt.Chart(tops).mark_text(dy=-6, fontSize=10, fontWeight="bold",
                                                        stroke="#0b1220", strokeWidth=4, strokeJoin="round")
                              .encode(**top_enc))
                layers.append(alt.Chart(tops).mark_text(dy=-6, fontSize=10, fontWeight="bold")
                              .encode(**top_enc, color=alt.Color("สี:N", scale=None, legend=None)))
            # สเกล y ใช้ร่วมกัน (ความสูงตรงกันทุกชั้น) แต่แกนแยก: ซ้าย = kWh · ขวา = ป้าย MAX/MIN
            st.altair_chart(alt.layer(*layers).resolve_scale(color="independent").resolve_axis(y="independent")
                            .properties(height=380), width="stretch")
            ref = full_day if n_full else sys_day
            best = ref.loc[ref["ac_kwh"].idxmax()]
            worst = ref.loc[ref["ac_kwh"].idxmin()]
            n_max = int((full_day["ac_kwh"] >= t_max).sum())
            n_min = int((full_day["ac_kwh"] >= t_min).sum())
            st.caption(
                f"เส้น MAX {t_max:,.0f} / MIN {t_min:,.0f} kWh/วัน = {se.KWP_TOTAL:,.0f} kWp × PSH 4.5 / 4.0 × (1 − loss 20%) · "
                f"ถึง MAX {n_max}/{n_full} วัน · ถึง MIN {n_min}/{n_full} วัน · "
                f"ตัวเลขบนแท่ง เขียว ≥ MAX · ส้ม อยู่ระหว่าง MIN–MAX · แดง < MIN · "
                f"ดีสุด {best['ac_kwh']:,.0f} ({_fmt_date(best['date'])}) · "
                f"แย่สุด {worst['ac_kwh']:,.0f} ({_fmt_date(worst['date'])}){partial_note}"
            )
    with col_r:
        with st.container(border=True, key="solar_profile_card"):
            st.subheader("โปรไฟล์กำลังผลิต ราย 15 นาที")
            if single:                     # วันที่เลือกด้านบนแล้ว เทียบกับเฉลี่ย 14 วันก่อนหน้า
                sel_day = end
                cmp_prof = prof_all[prof_all["date"].between(end - pd.Timedelta(days=13), end)]
                cmp_slot = cmp_prof.groupby(["date", "slot", "tod"], as_index=False)["pac_mean"].sum()
                cmp_label = f"เฉลี่ย {cmp_slot['date'].nunique()} วันถึง {_fmt_date(end)}"
                st.caption(f"วันที่ {_fmt_date(end)} (เปลี่ยนวันที่ที่ตัวเลือกด้านบน)")
            else:
                dates = sorted(daily["date"].unique(), reverse=True)
                sel_day = st.selectbox("วัน", dates, format_func=lambda x: pd.Timestamp(x).strftime("%d/%m/%Y (%a)"),
                                       key="solar_profile_day", label_visibility="collapsed")
                cmp_slot, cmp_label = sys_slot, f"เฉลี่ย {n_days} วัน"
            mean_prof = (cmp_slot.groupby("tod", as_index=False)["pac_mean"].mean()
                         .rename(columns={"pac_mean": "kW"}).assign(ชนิด=cmp_label))
            day_prof = (sys_slot[sys_slot["date"] == sel_day][["tod", "pac_mean"]]
                        .rename(columns={"pac_mean": "kW"}).assign(ชนิด=_fmt_date(sel_day)))
            x = alt.X("tod:Q", title="เวลา", scale=alt.Scale(domain=[5, 19.5]),
                      axis=alt.Axis(values=list(range(5, 20)), labelExpr="format(datum.value, '02d') + ':00'"))
            shift = alt.Chart(pd.DataFrame({"a": [se.SHIFT_HOURS[0]], "b": [se.SHIFT_HOURS[1]]})).mark_rect(
                opacity=0.08, color="#e2e8f0").encode(x="a:Q", x2="b:Q")
            area = alt.Chart(day_prof).mark_area(color=COLOR_SOLAR, opacity=0.45, line={"color": COLOR_SOLAR}).encode(
                x=x, y=alt.Y("kW:Q", title="kW"),
                tooltip=[alt.Tooltip("tod:Q", title="เวลา (ชม.)", format=".2f"), alt.Tooltip("kW:Q", format=",.0f"), "ชนิด"])
            line = alt.Chart(mean_prof).mark_line(color="#e2e8f0", strokeWidth=2, strokeDash=[4, 3]).encode(
                x=x, y="kW:Q", tooltip=[alt.Tooltip("tod:Q", title="เวลา (ชม.)", format=".2f"),
                                        alt.Tooltip("kW:Q", format=",.0f"), "ชนิด"])
            onpeak = alt.Chart(pd.DataFrame({"x": [9]})).mark_rule(color=COLOR_ALERT, strokeDash=[2, 2]).encode(x="x:Q")
            st.altair_chart((shift + area + line + onpeak).properties(height=330), width="stretch")
            dp = day_prof["kW"]
            st.caption(
                f"พื้นที่ส้ม = วันที่เลือก (สูงสุด {dp.max() if len(dp) else 0:,.0f} kW) · เส้นประขาว = ค่าเฉลี่ยช่วงที่เลือก · "
                f"แถบจาง = กะผลิต {se.SHIFT_HOURS[0]:02d}:00–{se.SHIFT_HOURS[1]:02d}:00 · "
                "เส้นแดง 09:00 = เริ่ม On-peak (Solar ก่อนเวลานี้ช่วยตัด Demand ที่ MEA คิดเงินไม่ได้)"
            )

    # ---- ตารางสรุปรายเครื่อง ----
    with st.container(border=True, key="solar_inv_table"):
        st.subheader(f"สรุปรายอินเวอร์เตอร์ — วันที่ {_fmt_date(start)}" if single else
                     f"สรุปรายอินเวอร์เตอร์ — {_fmt_date(start)} ถึง {_fmt_date(end)}")
        show = summ[["inv_no", "sn", "ac_kwh", "avg_kwh", "best_kwh", "best_date", "worst_kwh", "worst_date",
                     "pac_max", "cf_pct", "eff_pct", "mppt_best", "mppt_worst", "mppt_min_ratio",
                     "coverage_pct", "outage_days", "outage_min", "n_fault", "curtail_days", "status", "fw"]].copy()
        show["mppt_min_ratio"] = show["mppt_min_ratio"] * 100
        show["ac_share"] = show["ac_kwh"] / show["ac_kwh"].sum() * 100
        show.insert(3, "ac_share", show.pop("ac_share"))

        def _row_style(r):
            if r["status"] != "ปกติ" or r["outage_days"] > 0:
                return ["background-color: rgba(220,38,38,0.12)"] * len(r)
            return [""] * len(r)

        st.dataframe(
            show.style.apply(_row_style, axis=1), hide_index=True, width="stretch",
            column_config={
                "inv_no": st.column_config.NumberColumn("#", format="%d", width="small"),
                "sn": st.column_config.TextColumn("SN"),
                "ac_kwh": st.column_config.NumberColumn("AC รวม (kWh)", format="localized"),
                "ac_share": st.column_config.ProgressColumn("สัดส่วน", format="%.1f%%", min_value=0, max_value=15),
                "avg_kwh": st.column_config.NumberColumn("เฉลี่ย/วัน", format="%.0f"),
                "best_kwh": st.column_config.NumberColumn("วันดีสุด", format="%.0f"),
                "best_date": st.column_config.DateColumn("เมื่อ", format="DD/MM"),
                "worst_kwh": st.column_config.NumberColumn("วันแย่สุด", format="%.0f"),
                "worst_date": st.column_config.DateColumn("เมื่อ ", format="DD/MM"),
                "pac_max": st.column_config.NumberColumn("Pac สูงสุด (kW)", format="%.0f"),
                "cf_pct": st.column_config.NumberColumn("CF %", format="%.1f", help="Capacity factor = kWh ÷ (100 kW × 24 ชม. × วัน)"),
                "eff_pct": st.column_config.NumberColumn("DC→AC %", format="%.1f"),
                "mppt_best": st.column_config.NumberColumn("MPPT ดีสุด", format="%d"),
                "mppt_worst": st.column_config.NumberColumn("MPPT แย่สุด", format="%d"),
                "mppt_min_ratio": st.column_config.ProgressColumn(
                    "MPPT แย่สุด เทียบเฉลี่ย", format="%.0f%%", min_value=0, max_value=120,
                    help=f"ต่ำกว่า {100 * (1 - se.MPPT_ALERT):.0f}% = ต้องตรวจ (เกณฑ์เดียวกับชีต Summary)"),
                "coverage_pct": st.column_config.NumberColumn("ข้อมูลครบ %", format="%.0f",
                                                              help="เทียบเครื่องที่ส่งข้อมูลครบที่สุดในวันเดียวกัน"),
                "outage_days": st.column_config.NumberColumn("วันหยุดกลางวัน", format="%d"),
                "outage_min": st.column_config.NumberColumn("นาทีหยุด", format="%d"),
                "n_fault": st.column_config.NumberColumn("เฟรม Fault", format="%d"),
                "curtail_days": st.column_config.NumberColumn("วันถูกจำกัดกำลัง", format="%d"),
                "status": st.column_config.TextColumn("สถานะ"),
                "fw": st.column_config.TextColumn("Firmware"),
            },
        )
        st.caption(
            "AC รวม = ผลต่างมิเตอร์รายวันของเครื่อง (Eday) · DC จากการอินทิเกรต Pdc ทุก ~65 วินาที · "
            "แถวสีแดง = มีเรื่องให้ตรวจ (ดูรายละเอียดด้านล่าง)"
        )

    # ---- ราย MPPT: heatmap + สุขภาพสตริง (ดูทั้งช่วง หรือเลือกดูทีละวัน) ----
    if single:                                         # โหมดรายวัน — ใช้วันที่เลือกด้านบนอยู่แล้ว
        md, md_label = daily, _fmt_date(end)
    else:
        whole = f"ทั้งช่วง ({period})"
        day_opts = [whole] + sorted(daily["date"].unique(), reverse=True)
        mppt_day = st.selectbox(
            "ดูราย MPPT ของ", day_opts, key="solar_mppt_day",
            format_func=lambda x: x if isinstance(x, str) else pd.Timestamp(x).strftime("วันที่ %d/%m/%Y (%a)"),
            help="ทั้งช่วง = รวมทุกวันในช่วงที่เลือกด้านบน · เลือกวันเดียวเพื่อดูว่า MPPT ไหนเริ่มตกวันไหน")
        md = daily if isinstance(mppt_day, str) else daily[daily["date"] == mppt_day]
        md_label = period if isinstance(mppt_day, str) else _fmt_date(mppt_day)
    col_l2, col_r2 = st.columns([3, 2])
    with col_l2:
        with st.container(border=True, key="solar_mppt_heat"):
            st.subheader(f"ราย MPPT — พลังงานต่อสตริง เทียบค่าเฉลี่ยของเครื่อง (%) · {md_label}")
            hm = se.mppt_table(md).rename(columns={"mppt": "MPPT"})
            hm["เครื่อง"] = "#" + hm["inv_no"].astype(str)
            st.altair_chart(_ratio_heatmap(
                hm, x=alt.X("MPPT:O", title="MPPT"), y=alt.Y("เครื่อง:N", sort=labels, title=None),
                tip=["เครื่อง", "sn", "MPPT",
                     alt.Tooltip("e_kwh:Q", title="พลังงาน DC (kWh)", format=",.0f"),
                     alt.Tooltip("n_str:Q", title="สตริงที่อนุมานจากกระแส"),
                     alt.Tooltip("idc_mid:Q", title="Idc กลางวัน (A)", format=".1f"),
                     alt.Tooltip("per_str:Q", title="kWh ต่อสตริง", format=",.0f"),
                     alt.Tooltip("vdc_mid:Q", title="Vdc กลางวัน (V)", format=".0f"),
                     alt.Tooltip("days:Q", title="จำนวนวันที่ใช้คำนวณ")]).properties(height=380),
                width="stretch")
            st.caption(f"100 = เท่าค่าเฉลี่ยต่อสตริงของเครื่องนั้น · ต่ำกว่า {100 * (1 - se.MPPT_ALERT):.0f} = ต้องตรวจ "
                       "(ฝุ่น เงาบัง สตริงขาด ฟิวส์ DC) · จำนวนสตริงต่อ MPPT (1 หรือ 2) อนุมานจากกระแสกลางวัน "
                       "เพราะแบบติดตั้งต่อ MPPT 5/6 สตริงเดียว ถ้าเทียบ kWh ตรง ๆ จะฟ้องผิดทุกเครื่อง · "
                       f"ช่องเทา — = ข้อมูลช่วง 10–14 น. ไม่ถึง {se.MPPT_MIN_MID_FRAMES} จุด (logger ส่งแต่ตอนเย็น/"
                       "เครื่องหยุด/วันถูกจำกัดกำลัง) จึงไม่คำนวณ")
    with col_r2:
        with st.container(border=True, key="solar_string_health"):
            st.subheader(f"สุขภาพสตริง — Vdc กลางวัน (V) · {md_label}")
            sh = se.string_health(md)
            if sh.empty:
                st.info("ยังไม่มีค่ากลางวันพอสำหรับคำนวณ")
            else:
                pv = sh.pivot(index="inv_no", columns="mppt", values="vdc_mid").round(0)
                pv.columns = [f"MPPT {c}" for c in pv.columns]
                pv.index = ["#" + str(i) for i in pv.index]
                ratio = sh.pivot(index="inv_no", columns="mppt", values="ratio")
                ratio.columns = pv.columns
                ratio.index = pv.index

                def _paint(df_):
                    out = pd.DataFrame("", index=df_.index, columns=df_.columns)
                    out[ratio < se.VDC_ALERT] = "background-color: rgba(220,38,38,0.35); font-weight: 700"
                    return out

                st.dataframe(pv.style.apply(_paint, axis=None).format("{:.0f}", na_rep="—"),
                             width="stretch", height=420)
                st.caption(f"ค่ากลาง {se.MIDDAY_HOURS[0]}–{se.MIDDAY_HOURS[1]} น. · สตริง 20 แผง ควรได้ ~700–740 V · "
                           f"สีแดง = ต่ำกว่า MPPT อื่นในเครื่องเกิน {100 * (1 - se.VDC_ALERT):.0f}% → สตริงอาจขาด")

    # ---- เจาะรายเครื่อง ----
    with st.container(border=True, key="solar_inv_detail"):
        st.subheader("เจาะรายเครื่อง — ราย MPPT รายวัน")
        # รายชื่อจากช่วง 14 วัน (โหมดรายวัน) — เครื่องที่ไม่มีข้อมูลวันที่เลือกต้องยังเลือกดูแนวโน้มได้
        # เพราะนั่นคือมุมที่ต้องใช้หาว่ามันหายไปตั้งแต่เมื่อไร
        opts = (trend.groupby("sn", as_index=False)["inv_no"].first()
                .sort_values("inv_no").reset_index(drop=True))
        sel = st.selectbox("อินเวอร์เตอร์", opts["sn"].tolist(),
                           format_func=lambda s: f"#{int(opts.loc[opts['sn'] == s, 'inv_no'].iloc[0])}  SN {s}",
                           key="solar_detail_sn")
        g = trend[trend["sn"] == sel].sort_values("date")
        if single:
            st.caption(f"แสดง 14 วันถึง {_fmt_date(end)} เพื่อให้เห็นแนวโน้มรอบวันที่เลือก")

        # วัน × MPPT — พลังงานต่อสตริงเทียบค่าเฉลี่ยของเครื่องในวันนั้น (เห็นว่า MPPT ไหนเริ่มตกวันไหน)
        dm = se.mppt_daily(g)
        if not dm.empty:
            dm = dm[dm["date"] > dm["date"].max() - pd.Timedelta(days=60)]   # 60 วันล่าสุดพอ ไม่งั้นสูงเป็นเมตร
            dm["วันที่"] = dm["date"].dt.strftime("%d/%m/%y")                # ต้องมีปี ข้ามปีแล้ววันซ้ำกัน
            day_sort = list(dict.fromkeys(dm.sort_values("date", ascending=False)["วันที่"]))
            st.altair_chart(_ratio_heatmap(
                dm, x=alt.X("mppt:O", title="MPPT"), y=alt.Y("วันที่:N", sort=day_sort, title=None),
                tip=[alt.Tooltip("date:T", title="วันที่", format="%d/%m/%Y"), alt.Tooltip("mppt:O", title="MPPT"),
                     alt.Tooltip("e_kwh:Q", title="พลังงาน DC (kWh)", format=",.1f"),
                     alt.Tooltip("n_str:Q", title="จำนวนสตริง"),
                     alt.Tooltip("vdc_mid:Q", title="Vdc กลางวัน (V)", format=".0f")], font=11).properties(
                height=max(160, 22 * len(day_sort)),
                title="รายวัน × MPPT — พลังงานต่อสตริง เทียบค่าเฉลี่ยของเครื่องในวันนั้น (%) · ช่องเทา = ข้อมูลกลางวันไม่พอ"),
                width="stretch")

        ml = g.melt(id_vars=["date"], value_vars=se.E_COLS, var_name="mppt", value_name="kWh")
        ml["MPPT"] = "MPPT " + ml["mppt"].str[1]
        vl = g.melt(id_vars=["date"], value_vars=[f"vdc{i}_mid" for i in se.MPPT], var_name="mppt", value_name="Vdc")
        vl["MPPT"] = "MPPT " + vl["mppt"].str[3]
        c1, c2 = st.columns(2)
        mppt_color = alt.Color("MPPT:N", scale=alt.Scale(scheme="category10"), legend=alt.Legend(orient="bottom"))
        with c1:
            ch = alt.Chart(ml).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X("date:T", title="วันที่", axis=alt.Axis(format="%d/%m", labelAngle=0)),
                y=alt.Y("kWh:Q", title="พลังงาน DC (kWh/วัน)"), color=mppt_color,
                tooltip=[alt.Tooltip("date:T", format="%d/%m/%Y"), "MPPT", alt.Tooltip("kWh:Q", format=",.1f")],
            ).properties(height=280, title="พลังงาน DC ต่อ MPPT")
            st.altair_chart(ch, width="stretch")
        with c2:
            ch = alt.Chart(vl.dropna(subset=["Vdc"])).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X("date:T", title="วันที่", axis=alt.Axis(format="%d/%m", labelAngle=0)),
                y=alt.Y("Vdc:Q", title="Vdc กลางวัน (V)", scale=alt.Scale(zero=False)), color=mppt_color,
                tooltip=[alt.Tooltip("date:T", format="%d/%m/%Y"), "MPPT", alt.Tooltip("Vdc:Q", format=",.0f")],
            ).properties(height=280, title="แรงดัน DC กลางวัน ต่อ MPPT")
            st.altair_chart(ch, width="stretch")

        # ---- กระแสไฟฟ้า: DC ขาเข้า (ราย MPPT) และ AC ขาออก (ราย เฟส) — แนวโน้มรายวัน ----
        _current_trend(g)

        # ---- ละเอียดทั้งวัน (ทุก ~65 วินาที): สถานะ · กระแส DC/AC · กำลัง · แรงดัน ----
        days_g = sorted(g["date"].unique(), reverse=True)
        iday = None
        if days_g:
            st.markdown("")
            st.subheader("ละเอียดทั้งวัน — กระแสขาเข้า DC / ขาออก AC ทุก ~65 วินาที")
            iday = st.selectbox(
                "วันที่ (ดูละเอียดทั้งวัน)", days_g, key="solar_intraday_day",
                index=days_g.index(np.datetime64(end)) if single and np.datetime64(end) in days_g else 0,
                format_func=lambda x: pd.Timestamp(x).strftime("%d/%m/%Y (%a)"))
            po = prof_all[(prof_all["sn"] == sel) & (prof_all["date"] == iday) & prof_all["outage"]]["slot"]
            no = int(opts.loc[opts["sn"] == sel, "inv_no"].iloc[0])
            _intraday(_readings(sig, iday, sel), pd.Timestamp(iday), po, inv_label=f"#{no} · SN {sel}")

        det = g[["date", "ac_kwh", "dc_kwh", "eff_pct"] + se.E_COLS + ["pac_max", "pdc_max",
                 "coverage_pct", "outage_min", "curtail_min", "n_fault", "t_heatsink_max"]].copy()
        det = det.sort_values("date", ascending=False)
        st.dataframe(
            det, hide_index=True, width="stretch",
            column_config={
                "date": st.column_config.DateColumn("วันที่", format="DD/MM/YYYY"),
                "ac_kwh": st.column_config.NumberColumn("AC (kWh)", format="%.1f"),
                "dc_kwh": st.column_config.NumberColumn("DC (kWh)", format="%.1f"),
                "eff_pct": st.column_config.NumberColumn("DC→AC %", format="%.1f"),
                **{f"e{i}": st.column_config.NumberColumn(f"MPPT{i} (kWh)", format="%.1f") for i in se.MPPT},
                "pac_max": st.column_config.NumberColumn("Pac max (kW)", format="%.0f"),
                "pdc_max": st.column_config.NumberColumn("Pdc max (kW)", format="%.0f"),
                "coverage_pct": st.column_config.NumberColumn("ข้อมูลครบ %", format="%.0f"),
                "outage_min": st.column_config.NumberColumn("หยุดกลางวัน (นาที)", format="%d"),
                "curtail_min": st.column_config.NumberColumn("ถูกจำกัด (นาที)", format="%d"),
                "n_fault": st.column_config.NumberColumn("Fault", format="%d"),
                "t_heatsink_max": st.column_config.NumberColumn("Heatsink max °C", format="%.0f"),
            },
        )
        raw_day = iday if iday is not None else sel_day
        exp = st.expander(f"ข้อมูลดิบของเครื่องนี้ วันที่ {_fmt_date(raw_day)} (ทุก ~65 วินาที)", on_change="rerun")
        if exp.open:
            with exp:
                raw = _readings(sig, raw_day, sel)
                cols = ["ts", "status", "grid_status", "pac_kw", "pdc_kw", "eday_kwh", "ecum_kwh"] + \
                       [f"vdc{i}" for i in se.MPPT] + [f"idc{i}" for i in se.MPPT] + [f"pdc{i}" for i in se.MPPT] + \
                       ["vac_r", "vac_s", "vac_t", "iac_r", "iac_s", "iac_t", "hz", "t_heatsink", "flag"]
                st.dataframe(raw[[c for c in cols if c in raw.columns]], hide_index=True, width="stretch", height=360)
                st.download_button("⬇️ ดาวน์โหลด CSV — ข้อมูลดิบวันนี้", raw.to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"solar_raw_{sel}_{pd.Timestamp(raw_day):%Y%m%d}.csv", mime="text/csv",
                                   key="solar_dl_raw")

    # ---- แจ้งเตือน ----
    with st.container(border=True, key="solar_alerts"):
        st.subheader(f"สิ่งที่ต้องตรวจ — {period}")
        if not al:
            st.success("ไม่พบความผิดปกติในช่วงที่เลือก")
        for a in al:
            {"error": st.error, "warning": st.warning, "info": st.info}[a["level"]](a["text"])
        st.caption(
            "หยุดกลางวัน = เครื่องนี้ไม่จ่ายไฟ 08–16 น. ขณะค่ากลางของเครื่องอื่น ≥ 10 kW (ระบบ EVE ไม่ส่ง alarm กรณีนี้) · "
            "ถูกจำกัดกำลัง = ผลิต < 20 kW ทั้งที่ Vdc > 800 V (Zero-export วันโหลดต่ำ ไม่ใช่เครื่องเสีย)"
        )

    # ---- ดาวน์โหลด ----
    with st.container(horizontal=True):
        st.download_button(
            "⬇️ CSV รายวัน × รายเครื่อง", daily.drop(columns=["เครื่อง"]).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"solar_daily_{_fmt_date(start).replace('/', '')}_{_fmt_date(end).replace('/', '')}.csv",
            mime="text/csv", key="solar_dl_daily")
        mp = daily.melt(id_vars=["date", "inv_no", "sn"], value_vars=se.E_COLS, var_name="mppt", value_name="kwh_dc")
        mp["mppt"] = mp["mppt"].str[1].astype(int)
        st.download_button(
            "⬇️ CSV รายวัน × ราย MPPT", mp.sort_values(["date", "inv_no", "mppt"]).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"solar_mppt_daily_{_fmt_date(start).replace('/', '')}_{_fmt_date(end).replace('/', '')}.csv",
            mime="text/csv", key="solar_dl_mppt")
        st.caption("อัปเดตข้อมูล: ดึง EVE export ลง Downloads แล้วดับเบิลคลิก อัปเดต Solar.bat")
