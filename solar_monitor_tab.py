# -*- coding: utf-8 -*-
"""แท็บ Solar Monitor ของ energy_monitor.py — ประสิทธิภาพราย inverter / ราย MPPT / รายวัน
------------------------------------------------------------------------------------
อ่าน parquet ที่ solar_etl.py สร้าง (ปุ่ม อัปเดต Solar.bat) — สูตรและเกณฑ์ทั้งหมดอยู่ใน
solar_etl.py ไฟล์นี้มีแต่การแสดงผล ห้ามคำนวณกฎธุรกิจซ้ำที่นี่

เรียกจาก energy_monitor.py:   solar_monitor_tab.render(kpi_card)
"""

from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import data_paths
import solar_etl as se

PERIODS = {"7 วัน": 7, "14 วัน": 14, "30 วัน": 30, "ทั้งหมด": None}
# สีประจำเครื่อง #1–#11 (คงที่ทุกกราฟ จะได้จำได้ว่าสีไหนเครื่องไหน)
INV_COLORS = ["#f59e0b", "#3b82f6", "#ef4444", "#10b981", "#8b5cf6", "#ec4899",
              "#14b8a6", "#f97316", "#6366f1", "#84cc16", "#06b6d4"]
COLOR_SOLAR, COLOR_COST, COLOR_ALERT, COLOR_GRID2 = "#f59e0b", "#16a34a", "#dc2626", "#0ea5e9"


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
# หน้าแท็บ
# ---------------------------------------------------------------------------
def render(kpi_card) -> None:
    sig = data_paths.solar_signature()
    if not sig or not all(m for _, m in sig):
        st.info(
            "ยังไม่มีข้อมูล Solar inverter ในระบบ\n\n"
            "1. ดึงรายงาน **รายการละเอียดแต่ละรายการ** ของอินเวอร์เตอร์ทั้ง 11 ตัวจากเว็บ EVE "
            "(ไฟล์จะลงใน Downloads)\n"
            "2. ดับเบิลคลิก **อัปเดต Solar.bat** ในโฟลเดอร์แดชบอร์ด — หน้านี้จะแสดงผลเองภายใน ~30 วินาที"
        )
        return
    daily_all, prof_all = _load(sig)
    last = daily_all["date"].max()
    last_ts = daily_all["last_ts"].max()

    # ---- ตัวเลือกช่วงเวลา + เป้า ----
    with st.container(horizontal=True, vertical_alignment="center"):
        period = st.segmented_control("ช่วงเวลา", list(PERIODS), default="30 วัน",
                                      key="solar_period") or "30 วัน"
        target_name = st.selectbox("เป้าผลผลิตต่อวัน", list(se.TARGET_KWH_DAY), index=1,
                                   key="solar_target")
        st.caption(f"ข้อมูล EVE ล่าสุด {last_ts:%d/%m/%Y %H:%M} · "
                   f"อินเวอร์เตอร์ {se.N_INVERTERS} ชุด × {se.RATED_KW:.0f} kW · {se.KWP_TOTAL:,.0f} kWp")
    days_back = PERIODS[period]
    start = (last - pd.Timedelta(days=days_back - 1)) if days_back else daily_all["date"].min()
    start = max(start, daily_all["date"].min())      # ข้อมูลเริ่มหลังช่วงที่ขอ ให้โชว์วันแรกที่มีจริง
    daily = daily_all[daily_all["date"] >= start].copy()
    prof = prof_all[prof_all["date"] >= start].copy()
    target = se.TARGET_KWH_DAY[target_name]
    labels = _inv_labels(daily_all)
    inv_scale = _inv_scale(labels)

    # ---- KPI ----
    sys_day = daily.groupby("date", as_index=False).agg(ac_kwh=("ac_kwh", "sum"), dc_kwh=("dc_kwh", "sum"))
    sys_slot = prof.groupby(["date", "slot", "tod"], as_index=False)["pac_mean"].sum()
    n_days = len(sys_day)
    ac_total, dc_total = sys_day["ac_kwh"].sum(), sys_day["dc_kwh"].sum()
    # วันล่าสุดที่ดึง export ระหว่างวัน (ยังไม่ครบวัน) ไม่เอามานับค่าเฉลี่ย/ถึงเป้า/ดีสุด-แย่สุด
    # ไม่งั้นทุกครั้งที่กดอัปเดตตอนสาย ค่าเฉลี่ยจะดิ่งและ "แย่สุด" จะชี้วันนี้เสมอ
    partial = se.partial_last_day(daily_all)
    full_day = sys_day[sys_day["date"] != last] if partial is not None else sys_day
    n_full = len(full_day)
    avg_day = full_day["ac_kwh"].sum() / n_full if n_full else 0
    partial_note = (f" · ไม่นับ {_fmt_date(last)} (ข้อมูลถึง {partial:%H:%M} ยังไม่ครบวัน)"
                    if partial is not None else "")
    peak = sys_slot.loc[sys_slot["pac_mean"].idxmax()] if not sys_slot.empty else None
    summ = se.inverter_summary(daily)
    al = se.alerts(daily)
    n_bad = len({a["inv_no"] for a in al if a["level"] in ("error", "warning")})

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        kpi_card("ผลิตได้ (AC)", f"{ac_total:,.0f} kWh", COLOR_SOLAR,
                 f"{n_days} วัน · {_fmt_date(start)} – {_fmt_date(last)}")
    with k2:
        pct = avg_day / target * 100 if target else 0
        kpi_card("เฉลี่ยต่อวัน", f"{avg_day:,.0f} kWh", COLOR_COST if pct >= 100 else COLOR_ALERT,
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
            st.subheader("ผลผลิตรายวัน แยกตามอินเวอร์เตอร์ (AC kWh)")
            d = daily.merge(sys_day.rename(columns={"ac_kwh": "รวมทั้งระบบ"})[["date", "รวมทั้งระบบ"]], on="date")
            d["สัดส่วน"] = d["ac_kwh"] / d["รวมทั้งระบบ"] * 100
            bars = (
                alt.Chart(d)
                .mark_bar()
                .encode(
                    x=alt.X("date:T", title="วันที่", axis=alt.Axis(format="%d/%m", labelAngle=0)),
                    y=alt.Y("ac_kwh:Q", title="kWh"),
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
            rules = alt.Chart(pd.DataFrame({"y": list(se.TARGET_KWH_DAY.values()),
                                            "เป้า": list(se.TARGET_KWH_DAY)})).mark_rule(
                strokeDash=[6, 4], strokeWidth=1.5, color="#e2e8f0").encode(
                y="y:Q", tooltip=["เป้า", alt.Tooltip("y:Q", title="kWh/วัน", format=",.0f")])
            st.altair_chart((bars + rules).properties(height=360), width="stretch")
            ref = full_day if n_full else sys_day
            best = ref.loc[ref["ac_kwh"].idxmax()]
            worst = ref.loc[ref["ac_kwh"].idxmin()]
            n_hit = int((full_day["ac_kwh"] >= target).sum())
            st.caption(
                f"เส้นประ = เป้า {' / '.join(f'{v:,.0f}' for v in se.TARGET_KWH_DAY.values())} kWh/วัน · "
                f"ถึงเป้า{target_name.split(' ')[0]} {n_hit}/{n_full} วัน · "
                f"ดีสุด {best['ac_kwh']:,.0f} ({_fmt_date(best['date'])}) · "
                f"แย่สุด {worst['ac_kwh']:,.0f} ({_fmt_date(worst['date'])}){partial_note}"
            )
    with col_r:
        with st.container(border=True, key="solar_profile_card"):
            st.subheader("โปรไฟล์กำลังผลิต ราย 15 นาที")
            dates = sorted(daily["date"].unique(), reverse=True)
            sel_day = st.selectbox("วัน", dates, format_func=lambda x: pd.Timestamp(x).strftime("%d/%m/%Y (%a)"),
                                   key="solar_profile_day", label_visibility="collapsed")
            mean_prof = (sys_slot.groupby("tod", as_index=False)["pac_mean"].mean()
                         .rename(columns={"pac_mean": "kW"}).assign(ชนิด=f"เฉลี่ย {n_days} วัน"))
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
        st.subheader(f"สรุปรายอินเวอร์เตอร์ — {_fmt_date(start)} ถึง {_fmt_date(last)}")
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

    # ---- ราย MPPT: heatmap + สุขภาพสตริง ----
    col_l2, col_r2 = st.columns([3, 2])
    with col_l2:
        with st.container(border=True, key="solar_mppt_heat"):
            st.subheader("ราย MPPT — พลังงานต่อสตริง เทียบค่าเฉลี่ยของเครื่อง (%)")
            hm = se.mppt_table(daily).rename(columns={"mppt": "MPPT"})
            hm["เทียบเฉลี่ย"] = hm["ratio"] * 100
            hm["เครื่อง"] = "#" + hm["inv_no"].astype(str)
            base = alt.Chart(hm).encode(
                x=alt.X("MPPT:O", title="MPPT"),
                y=alt.Y("เครื่อง:N", sort=labels, title=None),
                tooltip=["เครื่อง", "sn", "MPPT",
                         alt.Tooltip("e_kwh:Q", title="พลังงาน DC (kWh)", format=",.0f"),
                         alt.Tooltip("n_str:Q", title="สตริงที่อนุมานจากกระแส"),
                         alt.Tooltip("idc_mid:Q", title="Idc กลางวัน (A)", format=".1f"),
                         alt.Tooltip("per_str:Q", title="kWh ต่อสตริง", format=",.0f"),
                         alt.Tooltip("เทียบเฉลี่ย:Q", title="เทียบเฉลี่ยต่อสตริง (%)", format=".0f"),
                         alt.Tooltip("vdc_mid:Q", title="Vdc กลางวัน (V)", format=".0f")])
            rect = base.mark_rect().encode(color=alt.Color(
                "เทียบเฉลี่ย:Q", title="% ของเฉลี่ย",
                scale=alt.Scale(scheme="redyellowgreen", domain=[50, 120], clamp=True)))
            txt = base.mark_text(fontWeight="bold").encode(
                text=alt.Text("เทียบเฉลี่ย:Q", format=".0f"),
                color=alt.condition(alt.datum["เทียบเฉลี่ย"] < 70, alt.value("white"), alt.value("#0f172a")))
            st.altair_chart((rect + txt).properties(height=380), width="stretch")
            st.caption(f"100 = เท่าค่าเฉลี่ยต่อสตริงของเครื่องนั้น · ต่ำกว่า {100 * (1 - se.MPPT_ALERT):.0f} = ต้องตรวจ "
                       "(ฝุ่น เงาบัง สตริงขาด ฟิวส์ DC) · จำนวนสตริงต่อ MPPT (1 หรือ 2) อนุมานจากกระแสกลางวัน "
                       "เพราะแบบติดตั้งต่อ MPPT 5/6 สตริงเดียว ถ้าเทียบ kWh ตรง ๆ จะฟ้องผิดทุกเครื่อง")
    with col_r2:
        with st.container(border=True, key="solar_string_health"):
            st.subheader("สุขภาพสตริง — Vdc กลางวัน (V)")
            sh = se.string_health(daily)
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
        opts = summ.sort_values("inv_no")
        sel = st.selectbox("อินเวอร์เตอร์", opts["sn"].tolist(),
                           format_func=lambda s: f"#{int(opts.loc[opts['sn'] == s, 'inv_no'].iloc[0])}  SN {s}",
                           key="solar_detail_sn")
        g = daily[daily["sn"] == sel].sort_values("date")
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
        exp = st.expander("ข้อมูลดิบของเครื่องนี้ในวันที่เลือกด้านบน (ทุก ~65 วินาที)", on_change="rerun")
        if exp.open:
            with exp:
                raw = _readings(sig, sel_day, sel)
                cols = ["ts", "status", "grid_status", "pac_kw", "pdc_kw", "eday_kwh", "ecum_kwh"] + \
                       [f"vdc{i}" for i in se.MPPT] + [f"idc{i}" for i in se.MPPT] + [f"pdc{i}" for i in se.MPPT] + \
                       ["vac_r", "vac_s", "vac_t", "hz", "t_heatsink", "flag"]
                st.dataframe(raw[[c for c in cols if c in raw.columns]], hide_index=True, width="stretch", height=360)
                st.download_button("⬇️ ดาวน์โหลด CSV — ข้อมูลดิบวันนี้", raw.to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"solar_raw_{sel}_{pd.Timestamp(sel_day):%Y%m%d}.csv", mime="text/csv",
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
            file_name=f"solar_daily_{_fmt_date(start).replace('/', '')}_{_fmt_date(last).replace('/', '')}.csv",
            mime="text/csv", key="solar_dl_daily")
        mp = daily.melt(id_vars=["date", "inv_no", "sn"], value_vars=se.E_COLS, var_name="mppt", value_name="kwh_dc")
        mp["mppt"] = mp["mppt"].str[1].astype(int)
        st.download_button(
            "⬇️ CSV รายวัน × ราย MPPT", mp.sort_values(["date", "inv_no", "mppt"]).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"solar_mppt_daily_{_fmt_date(start).replace('/', '')}_{_fmt_date(last).replace('/', '')}.csv",
            mime="text/csv", key="solar_dl_mppt")
        st.caption("อัปเดตข้อมูล: ดึง EVE export ลง Downloads แล้วดับเบิลคลิก อัปเดต Solar.bat")
