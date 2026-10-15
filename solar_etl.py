# -*- coding: utf-8 -*-
"""ETL ตัวเดียวของข้อมูล Solar Inverter — EVE export → parquet ให้แดชบอร์ดพอร์ต 8504
=================================================================================

งานประจำวันของผู้ใช้มีแค่ 2 ขั้น
  1. ดึงรายงาน "รายการละเอียดแต่ละรายการ" ของอินเวอร์เตอร์ทั้ง 11 ตัวจากเว็บ EVE
     (ไฟล์ลงใน Downloads ชื่อ อินเวอร์เตอร์<SN>-รายการละเอียดแต่ละรายการ-<YYYYMMDD>.xlsx)
  2. ดับเบิลคลิก  อัปเดต Solar.bat

สคริปต์นี้ทำที่เหลือทั้งหมด
  ขั้น 1  ย้ายไฟล์จาก Downloads เข้า 01_ข้อมูลดิบ_Solar Cell\\<ปี พ.ศ.-เดือน-วัน>_EVE_Export\\
          (วันที่อ่านจากชื่อไฟล์ แปลง ค.ศ. → พ.ศ. ด้วย +543 แบบเดียวกับ etl_prepare.py)
  ขั้น 2  อ่านเฉพาะไฟล์ที่ยังไม่เคยอ่าน (จำด้วย parquet\\_ingested.json) ทำความสะอาด
          ตัดแถวซ้ำด้วย SN + เวลา แล้วเขียน parquet\\solar_readings.parquet
  ขั้น 3  สรุปรายวัน (ราย inverter และราย MPPT) + โปรไฟล์ราย 15 นาที
          → solar_daily.parquet, solar_profile15.parquet
  ขั้น 4  รายงานผล: แถวที่เพิ่ม ข้อมูลล่าสุดถึงเมื่อไร ผลผลิตวันล่าสุด และสิ่งที่ต้องตรวจ

กฎการทำความสะอาดและสูตรทั้งหมดอยู่ในบล็อก CONFIG + ฟังก์ชัน derive()/summarize()
ของไฟล์นี้ที่เดียว ย้ายมาจาก Solar_Inverter_ฐานข้อมูลหลัก_2569.xlsx (ชีต README /
คุณภาพข้อมูล) และ Report&EE_DATA.xlsx (ชีต PQ_Instructions / Summary / AC_Output)
แดชบอร์ด import ฟังก์ชันจากที่นี่ ห้ามเขียนสูตรซ้ำในแดชบอร์ด

รันเดี่ยว:   python solar_etl.py            (ทำครบ 4 ขั้น)
             python solar_etl.py --check    (ดูว่าจะย้าย/อ่านไฟล์ไหน ไม่เขียนอะไร)
             python solar_etl.py --rebuild  (อ่านไฟล์ดิบใหม่ทั้งหมด ไม่สนใจที่เคยอ่านแล้ว)
"""

from __future__ import annotations

import contextlib
import datetime as dt
import glob
import json
import os
import re
import shutil
import stat
import sys
import time

import numpy as np
import pandas as pd

import data_paths

HERE = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")

# ===========================================================================
# CONFIG — กฎทั้งหมดของข้อมูล Solar อยู่ตรงนี้ที่เดียว
# ===========================================================================
# ชื่อไฟล์ที่ EVE ส่งออก — รับเฉพาะรายงาน "รายการละเอียดแต่ละรายการ" รายอินเวอร์เตอร์
# (ใน Downloads มีรายงานแบบอื่นปนอยู่ เช่น ...รายงาน.xlsx และ Modernform-P1-... ไม่เอา)
# ท้ายชื่ออาจมี " (2)" จาก Windows เมื่อดาวน์โหลดซ้ำ หรือจากขั้น 1 ที่เก็บสำเนาไว้ — รับทั้งคู่
FILE_RE = re.compile(r"^อินเวอร์เตอร์(\d{10})-รายการละเอียดแต่ละรายการ-(\d{8})(?: \(\d+\))*\.xlsx$")
_COPY_SUFFIX_RE = re.compile(r"(?: \(\d+\))+$")
FOLDER_SUFFIX = "_EVE_Export"

# หมายเลขอินเวอร์เตอร์ #1–#11 = เรียงตาม SN (ลำดับเดียวกับรายการในเว็บ EVE)
# ตรงกับที่ใช้ในสไลด์ผู้บริหาร Rev2 และใบแจ้งซ่อมผู้รับเหมา 25 ก.ย. 69 (#6 = 2205059057,
# #10 = 2208109322) — ไม่ใช่คอลัมน์ "ตัวที่" ในฐานข้อมูลหลัก Excel ซึ่งเรียงคนละแบบ
# และยังไม่ใช่ INVERTER 1–11 ตามแบบ SLD (ยังไม่มีใครยืนยันหน้างานว่า SN ไหนคือตู้ไหน)
INVERTER_NO = {
    "2106114215": 1, "2203014488": 2, "2203014490": 3, "2205059038": 4,
    "2205059053": 5, "2205059057": 6, "2208109254": 7, "2208109291": 8,
    "2208109310": 9, "2208109322": 10, "2301130556": 11,
}
RATED_KW = 100.0            # พิกัด AC ต่อเครื่อง
N_INVERTERS = 11
AC_TOTAL_KW = RATED_KW * N_INVERTERS
KWP_TOTAL = 1243.0          # กำลังติดตั้ง DC (2,260 แผง × 550 W)
# เป้าผลผลิตต่อวัน = kWp × PSH × (1 − System loss 20%) ตามสไลด์ผู้บริหาร Rev2
# พิกัดอุปกรณ์ (จากแบบ SLD CUE-IE-006 / datasheet) — ใช้เป็นเส้นอ้างอิงในกราฟกระแส
AC_IMAX_A = 158.8           # กระแส AC สูงสุดต่อเฟสของอินเวอร์เตอร์ SUN-100K-G03
MPPT_IMAX_A = 40.0          # กระแส DC เข้าสูงสุดต่อ MPPT
STRING_IMP_A = 13.42        # กระแสที่จุดกำลังสูงสุดของสตริง (แผง EVE GREP 550 ที่ STC)
MPPT_V_MIN, MPPT_V_MAX = 200.0, 850.0   # ช่วงแรงดันที่ MPPT ทำงาน (แบบ SLD แผ่น INVERTER)
PHASES = {"R": "iac_r", "S": "iac_s", "T": "iac_t"}
AC_V_COLS = ["vac_r", "vac_s", "vac_t"]
PHASE_IMBAL_MIN_A = 5.0     # คิดความไม่สมดุลเฉพาะตอนกระแสเฉลี่ย ≥ 5 A (ตอนเช้า/เย็นกระแสน้อย % จะแกว่ง)

# MAX = แดดปกติ (PSH 4.5) · MIN = แดดไม่เอื้อ/ฤดูฝน (PSH 4.0) — ต่ำกว่า MIN คือผลผลิตต่ำกว่าที่ควร
TARGET_KWH_DAY = {"MAX (PSH 4.5)": 4475.0, "MIN (PSH 4.0)": 3978.0}

# ค่าผิดปกติที่ต้องตัดทิ้ง (พบจริงในข้อมูล ก.ย. 69 — ดูชีต "คุณภาพข้อมูล" ของฐานข้อมูลหลัก)
PAC_MAX_KW = 150.0          # Total AC Output Power ตอนกลางคืนเด้งเป็นค่า uint32 มหาศาล
PDC_MPPT_MAX_W = 40_000.0   # เฟรมเสีย: Pdc ต่อ MPPT เกิน 40 kW (จริงไม่เกิน ~15 kW)
ECUM_MAX_KWH = 1e7          # เฟรมเสีย: มิเตอร์สะสม 52 ล้าน kWh
OK_STATUS = {"Grid connected", "Checking", "Standby"}   # นอกนี้ = fault ("4", "10000")

# พลังงาน DC = Pdc(W)/1000 × dt_hr  — dt คือช่วงห่างจากแถวก่อนของเครื่องเดียวกัน
DT_FIRST_HR = 0.0175        # แถวแรกของแต่ละเครื่อง (≈ 63 วินาที = คาบบันทึกปกติ)
DT_CAP_HR = 0.05            # เพดาน 3 นาที — ช่วงที่ข้อมูลขาดจะนับต่ำกว่าจริง (ตั้งใจกันค่าพุ่ง)

MIDDAY_HOURS = (10, 14)     # ช่วงวัดสุขภาพสตริง (median ของ Vdc/Pdc ขณะแดดเต็ม)
MIDDAY_MIN_PDC_KW = 20.0    # นับเฉพาะเฟรมที่เครื่องผลิตจริง
DAYLIGHT_HOURS = (8, 16)    # ช่วงตรวจ "หยุดจ่ายไฟกลางวัน"
CURTAIL_HOURS = (10, 15)    # ช่วงตรวจ "ถูกจำกัดกำลัง" (Zero-export วันโหลดต่ำ)
SHIFT_HOURS = (7, 16)       # กะผลิต P1 07:00–16:00

# เกณฑ์แจ้งเตือน
# MPPT: ชีต Summary เทียบพลังงานแต่ละ MPPT กับค่าเฉลี่ย 6 MPPT ของเครื่อง แต่ตามแบบติดตั้ง
# MPPT 5/6 (และบางเครื่อง MPPT 1/3/5) ต่อสตริงเดียว ส่วนที่เหลือต่อ 2 สตริงขนาน — เทียบตรง ๆ
# จะฟ้องเกือบทุกเครื่องทั้งที่ปกติ จึงอนุมานจำนวนสตริงจากกระแสกลางวัน (Idc ของ MPPT นั้น
# เทียบ MPPT ที่สูงสุดในเครื่อง ≥ 75% = 2 สตริง) แล้วเทียบพลังงาน "ต่อสตริง" แทน
STRINGS_2_RATIO = 0.75
MPPT_ALERT = 0.15           # พลังงานต่อสตริงต่ำกว่าเฉลี่ยต่อสตริงของเครื่องเกิน 15%
# เทียบ MPPT ได้เฉพาะวันที่มีข้อมูลช่วงแดดเต็ม (10–14 น. ผลิต > 20 kW) อย่างน้อยเท่านี้ — วันปกติมี 75–216 จุด
# ต่ำกว่านี้คือ logger ส่งแต่ตอนเย็น/กลางคืน (#6 05/10 ได้ 17%–404% ไร้ความหมาย) วันถูกจำกัดกำลัง
# หรือวันที่เครื่องหยุด → ไม่คำนวณ แสดงเป็นช่องเทา
MPPT_MIN_MID_FRAMES = 10
VDC_ALERT = 0.90            # Vdc กลางวันของ MPPT ต่ำกว่า 90% ของ MPPT อื่นในเครื่อง = สตริงอาจขาด
OUTAGE_PAC_KW = 0.2         # เครื่องนี้ไม่จ่ายไฟ ...
OUTAGE_SYSTEM_KW = 10.0     # ... ขณะที่ค่ากลางของเครื่องอื่นยังผลิตอยู่
CURTAIL_PAC_KW = 20.0       # ผลิตต่ำ ...
CURTAIL_VDC = 800.0         # ... ทั้งที่ Vdc ลอยสูง = อินเวอร์เตอร์ถอยออกจาก MPP เอง
# "ออนไลน์แต่ไม่จ่ายไฟทั้งวัน" — logger ส่งเฟรมช่วงแดดเต็มครบตามปกติ สถานะ Grid connected ไฟกริดมี
# แต่ Eday = 0 ทั้งวัน ขณะที่เครื่องอื่นผลิตได้ (9 ต.ค. 69 12:43 #1–#5, #7–#10 หยุดพร้อมกันภายใน 2 นาที
# แล้วไม่กลับมาอีก 4 วัน — Vdc ลอย ~850 V = อินเวอร์เตอร์ไม่ดึงกำลังจากแผง ถูกจำกัดกำลังเป็น 0 หรือถูกสั่งหยุด)
# ต้องแยกจาก "ไม่มีข้อมูล" (ช่องเทา) และจาก Zero-export ชั่วคราววันโหลดต่ำ (เครื่องยังผลิตได้บ้าง)
# ไม่งั้นแดชบอร์ดดูเหมือน "ข้อมูลขาดช่วง" ทั้งที่ผลผลิตหายไปวันละ ~3,000 kWh และไม่มีใครรู้
ZERO_DAY_MIN_MID_ROWS = 60  # เฟรม 10–14 น. ทุกเฟรม (ไม่ดูว่าผลิตไหม) อย่างน้อยเท่านี้ = เครื่อง/logger ออนไลน์ (ปกติ ~200)
ZERO_DAY_AC_KWH = 1.0       # ผลผลิตทั้งวันต่ำกว่านี้ = ไม่จ่ายไฟทั้งวัน
ZERO_DAY_REF_KWH = 50.0     # เครื่องที่ผลิตได้มากสุดในวันนั้นต้องได้อย่างน้อยเท่านี้ (มีแดดจริง ไม่ใช่ฝนตก/ไฟดับทั้งระบบ)
PAC_ON_KW = 1.0             # เฟรมที่ถือว่า "จ่ายไฟอยู่" — ใช้หาเวลาสุดท้ายที่เครื่องจ่ายไฟก่อนหยุด
# ลิงก์มิเตอร์ Zero-export: คอลัมน์ Grid Status ของ EVE = "Purchasing energy" เมื่ออินเวอร์เตอร์ได้ค่าจากมิเตอร์
# และ "Static" เมื่อไม่ได้ (RS485 มิเตอร์→ตัวควบคุม→อินเวอร์เตอร์หลุด) — เครื่องกลุ่ม #1–#5, #7–#10 ตั้ง fail-safe
# จ่าย 0 W ระหว่างนั้น (ตรวจทั้งประวัติ 9 ก.ย.–13 ต.ค. 69: P(Pac=0 | Static) = 0.85 เทียบ 0.03 ตอนปกติ) ส่วน #11 ไม่หยุด
# วันปกติทุกเครื่องหลุดสั้น ๆ รวม 40–90 นาที/วัน · #10 หลุดนาน 160–450 นาทีในวันที่ "หยุดกลางวัน" · 9 ต.ค. 12:43 หลุดทั้งระบบ
METER_LOST_STATUS = "Static"
STATIC_NODE_MIN = 120       # เครื่องเดียวไม่ได้รับค่ามิเตอร์ ≥ 2 ชม./วัน ขณะเครื่องอื่นปกติ = โหนด RS485 ของเครื่องนั้น
STATIC_SYSTEM_MIN = 240     # กลุ่มที่ไม่จ่ายไฟมี Static ≥ 4 ชม./วัน = ลิงก์มิเตอร์หลุดทั้งระบบ (สาเหตุของการหยุด)
COVERAGE_ALERT = 40.0       # เครื่องส่งข้อมูลน้อยกว่า 40% ของเครื่องที่ครบที่สุดในวันนั้น
EFF_MIN_COVERAGE = 80.0     # คิดประสิทธิภาพ DC→AC เฉพาะวันที่ข้อมูลครบ ≥ 80%
EFF_MIN_MID_FRAMES = 40     # และมีเฟรมช่วงแดดเต็ม (10–14 น.) อย่างน้อยเท่านี้ (วันปกติ 75–216)
DAYLIGHT_ROWS_HOURS = (6.0, 18.5)   # ช่วงที่นับว่าเป็น "แถวช่วงผลิต" (06:00–18:29)
DAY_MIN_ROWS = 5            # น้อยกว่านี้ = วันนั้นไม่มีข้อมูลช่วงผลิต (logger ส่งแต่กลางคืน)
DAY_COMPLETE_HOUR = 17.5    # ข้อมูลวันล่าสุดสิ้นสุดก่อน 17:30 = ดึง export ระหว่างวัน ยังไม่ครบวัน
# ยอด AC รายวันปกติใช้ Eday (มิเตอร์รายวัน) แต่ถ้า Eday ต่ำกว่าผลต่างมิเตอร์สะสม Ecum ในวันเดียวกันชัดเจน
# ให้ใช้ Ecum แทน — #6 ตั้งแต่ 1 ต.ค. 69 ส่ง Eday = 0 ทั้งที่ Ecum เพิ่ม 380 kWh (03/10)
# วันที่ข้อมูลครบ ทั้งสองค่าต่างกันไม่เกิน 1 kWh (ตรวจแล้ว 236 วัน) จึงใช้เกณฑ์ห่างกันเกิน 2 kWh และ 5%
ECUM_OVER_EDAY_KWH = 2.0
ECUM_OVER_EDAY_PCT = 0.05
ECUM_DAY_MAX_KWH = RATED_KW * 14   # ผลต่าง Ecum วันเดียวเกินนี้ = ค่าเพี้ยน ไม่ใช้
GAP_ENERGY_MIN_KWH = 1.0    # ผลิตระหว่างที่ logger เงียบข้ามวัน ≥ เท่านี้ → แจ้งว่ามีพลังงานที่ระบุวันไม่ได้

# คอลัมน์ในไฟล์ EVE → ชื่อสั้นในฐาน (คอลัมน์ที่ไม่อยู่ในนี้ไม่เก็บ: PV7/PV8 เป็น 0 ทุกแถว,
# เซนเซอร์อุณหภูมิแวดล้อม/ขดลวดอ่านได้ −100 °C, Grid/Consumption มีค่าผิดปกติ)
RAW_COLS = {
    "หมายเลขอนุกรม": "sn",
    "หมายเลขซีเรียลของอุปกรณ์ที่สังกัด": "collector",
    "เวลาอัปเดต": "ts",
    "Rated Power(W)": "rated_w",
    "MPPT No": "mppt_n",
    "Control Software Version 1": "fw",
    "AC Voltage R/U/A(V)": "vac_r", "AC Voltage S/V/B(V)": "vac_s", "AC Voltage T/W/C(V)": "vac_t",
    "AC Current R/U/A(A)": "iac_r", "AC Current S/V/B(A)": "iac_s", "AC Current T/W/C(A)": "iac_t",
    "AC Output Frequency R(Hz)": "hz",
    "Total AC Output Power (Active)(W)": "pac_w",
    "Cumulative Production (Active)(kWh)": "ecum_kwh",
    "Daily Production (Active)(kWh)": "eday_kwh",
    "Inverter Output Power L1(W)": "p_l1", "Inverter Output Power L2(W)": "p_l2",
    "Inverter Output Power L3(W)": "p_l3",
    "Grid Status": "grid_status",
    "Inverter status": "status",
    "Heat-sink Temperature(℃)": "t_heatsink",
    "DC-AC Temperature(℃)": "t_dcac",
}
for _i in range(1, 7):
    RAW_COLS[f"DC Voltage PV{_i}(V)"] = f"vdc{_i}"
    RAW_COLS[f"DC Current PV{_i}(A)"] = f"idc{_i}"
    RAW_COLS[f"DC Power PV{_i}(W)"] = f"pdc{_i}"
TEXT_COLS = ("sn", "collector", "ts", "fw", "grid_status", "status")
MPPT = range(1, 7)
PDC_COLS = [f"pdc{i}" for i in MPPT]
VDC_COLS = [f"vdc{i}" for i in MPPT]
IDC_COLS = [f"idc{i}" for i in MPPT]
E_COLS = [f"e{i}" for i in MPPT]

DERIVED_COLS = ["dt_hr", *E_COLS, "e_dc", "pdc_kw", "vdc_mean", "date", "hour", "slot", "inv_no"]

READINGS = "solar_readings.parquet"
DAILY = "solar_daily.parquet"
PROFILE = "solar_profile15.parquet"
MANIFEST = "_ingested.json"


# ===========================================================================
# ขั้น 1 — ย้ายไฟล์จาก Downloads เข้าโฟลเดอร์ลงวันที่
# ===========================================================================
def folder_for(ymd: str) -> str | None:
    """'20261002' → '2569-10-02_EVE_Export' (None ถ้าไม่ใช่วันที่จริง)"""
    try:
        d = dt.date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
    except ValueError:
        return None
    return f"{d.year + 543}-{d.month:02d}-{d.day:02d}{FOLDER_SUFFIX}"


def _move(src: str, dest: str) -> None:
    """ย้ายไฟล์ไปที่ว่าง — ลอง rename ก่อน (ไดรฟ์เดียวกัน) ไม่ได้ค่อย copy แล้วลบ"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        os.rename(src, dest)
    except OSError:
        tmp = dest + ".tmp"
        try:
            shutil.copy2(src, tmp)
            os.rename(tmp, dest)
        except OSError:
            try:                                   # อย่าทิ้ง .tmp ค้างไว้ในโฟลเดอร์ดิบ (เคยค้าง 1 ไฟล์ 2 ต.ค. 69)
                os.remove(tmp)
            except OSError:
                pass
            raise
        os.remove(src)


def _same_content(a: str, b: str) -> bool:
    """สองไฟล์มีข้อมูลชุดเดียวกันไหม — เทียบจำนวนแถวและเวลาแรก/สุดท้ายของข้อมูลจริง
    (ขนาดไฟล์ใช้ไม่ได้: ไฟล์เดิมที่ถูกเปิดใน Excel แล้วเซฟ ขนาดเปลี่ยนได้หลายร้อย KB)"""
    try:
        da, db = parse_file(a), parse_file(b)
    except Exception:
        return False
    return (len(da) == len(db) and da["ts"].min() == db["ts"].min()
            and da["ts"].max() == db["ts"].max())


def _free_name(dest: str) -> str:
    """ชื่อที่ยังว่างในโฟลเดอร์ปลายทาง: name.xlsx → name (2).xlsx → name (3).xlsx ...
    ตัด " (1)" ที่ Windows เติมตอนดาวน์โหลดซ้ำออกก่อน จะได้ไม่กลายเป็น "name (1) (2).xlsx" """
    stem, ext = os.path.splitext(dest)
    stem = _COPY_SUFFIX_RE.sub("", stem)
    k = 2
    while os.path.exists(f"{stem} ({k}){ext}"):
        k += 1
    return f"{stem} ({k}){ext}"


def prepare(dry_run: bool = False) -> dict:
    """ย้ายไฟล์ EVE จาก Downloads เข้าโฟลเดอร์ลงวันที่

    กฎเหล็ก: ไม่ทับไฟล์ที่มีอยู่แล้วเด็ดขาด
      - ชื่อซ้ำและข้อมูลข้างในเท่ากัน (จำนวนแถว + ช่วงเวลาเดียวกัน) → ปล่อยไว้ใน Downloads
      - ชื่อซ้ำแต่ข้อมูลต่างกัน → เก็บเป็นสำเนา "ชื่อ (2).xlsx" ข้าง ๆ แล้วให้ขั้น 2 อ่านทั้งคู่
        (ตัดแถวซ้ำด้วย SN + เวลาอยู่แล้ว ไฟล์ไหนมีแถวเพิ่มก็ได้มาครบ ไฟล์ไหนเสียก็ไม่ทำลายของเดิม)
    ทำไมต้องเข้มขนาดนี้: 2 ต.ค. 69 เคยใช้กฎ "ใหม่กว่าและใหญ่กว่า = ทับได้" แล้วไฟล์ที่ทับไป
    กลายเป็นอ่านไม่ได้ ทำให้ข้อมูล 6 วันของเครื่อง #6 หายจากฐานจนต้องกู้คืน
    """
    raw = data_paths.solar_raw_dir()
    moved, copies, failed, dup = [], [], [], 0
    for f in sorted(glob.glob(os.path.join(DOWNLOADS, "อินเวอร์เตอร์*.xlsx"))):
        m = FILE_RE.match(os.path.basename(f))
        if not m:
            continue
        folder = folder_for(m.group(2))
        if not folder:
            continue
        dest = os.path.join(raw, folder, os.path.basename(f))
        target = moved
        if os.path.exists(dest):
            try:
                same = (os.path.samefile(f, dest) or os.path.getsize(f) == os.path.getsize(dest)
                        or _same_content(f, dest))
            except FileNotFoundError:              # อีกรอบ (ไอคอน/ปุ่ม) ย้ายไฟล์นี้ไปแล้วระหว่างทาง
                continue
            if same:
                dup += 1
                continue
            dest = _free_name(dest)
            if not FILE_RE.match(os.path.basename(dest)):     # กันพลาด: ชื่อที่ขั้น 2 อ่านไม่ได้ = ข้อมูลหายเงียบ
                failed.append(f"{os.path.basename(f)}: ชื่อปลายทาง {os.path.basename(dest)} ขั้น 2 อ่านไม่ได้")
                continue
            target = copies
        if dry_run:
            target.append(dest)
            continue
        try:
            _move(f, dest)
            target.append(dest)
        except OSError as e:
            # ไฟล์ถูกล็อก (OneDrive กำลังซิงก์ / เปิดค้างใน Excel) — ข้ามไฟล์นี้
            # ปล่อยไว้ใน Downloads ให้รอบหน้าลองใหม่ ไม่ล้มทั้งรอบเพราะไฟล์เดียว
            failed.append(f"{os.path.basename(f)}: {e.strerror or e}")
    return {"moved": moved, "copies": copies, "failed": failed, "duplicate": dup}


# ===========================================================================
# ขั้น 2 — อ่านไฟล์ EVE + ทำความสะอาด
# ===========================================================================
def _file_order(path: str) -> tuple:
    """ลำดับอ่านไฟล์ = วันที่ export ในชื่อไฟล์ → เลขสำเนา (2), (3) → mtime
    ไฟล์ที่อ่านทีหลังชนะเมื่อเวลาซ้ำ จึงต้องเรียงแบบนี้ทุกรอบ ไม่ว่ารอบปกติหรือ --rebuild
    (เรียงตามชื่อตรง ๆ ไม่ได้: "name (2).xlsx" มาก่อน "name.xlsx" เพราะช่องว่าง < จุด)"""
    base = os.path.basename(path)
    m = FILE_RE.match(base)
    k = re.findall(r" \((\d+)\)", base)
    return (m.group(2) if m else "", int(k[-1]) if k else 1, os.path.getmtime(path), base)


def list_raw_files() -> list[str]:
    raw = data_paths.solar_raw_dir()
    out = []
    for f in glob.glob(os.path.join(raw, f"*{FOLDER_SUFFIX}", "*.xlsx")):
        if FILE_RE.match(os.path.basename(f)):
            out.append(f)
    return sorted(out, key=_file_order)


def _header_row(rows: list, scan: int = 20) -> int | None:
    """ดัชนีแถวหัวตาราง = แถวแรก (ใน scan แถวแรก) ที่มี "หมายเลขอนุกรม" — ปกติคือแถว 0
    แต่ไฟล์ที่ผ่าน Excel/Power Query มีแถว Column1..Column76 แทรกไว้ข้างบน (เจอจริง 14 ต.ค. 69)"""
    for i, r in enumerate(rows[:scan]):
        if "หมายเลขอนุกรม" in [str(h).strip() for h in r]:
            return i
    return None


def parse_file(path: str) -> pd.DataFrame:
    """อ่านไฟล์ EVE หนึ่งไฟล์ → DataFrame คอลัมน์ชื่อสั้น (ยังไม่คำนวณอะไร)"""
    from python_calamine import CalamineWorkbook   # เร็วกว่า openpyxl ~20 เท่า

    # EVE ตั้งชื่อชีตข้อมูลว่า "0" — แต่ถ้าใครเปิดไฟล์ใน Excel แล้วเพิ่มชีตไว้ข้างหน้า
    # (เจอจริง: ['Sheet2', '0', 'Sheet1']) ชีตแรกจะว่าง จึงไล่หาชีตที่มีหัวตารางจริง
    wb = CalamineWorkbook.from_path(path)
    rows = []
    for name in wb.sheet_names:
        sheet = wb.get_sheet_by_name(name).to_python()
        hdr = _header_row(sheet)
        if hdr is not None:
            rows = sheet[hdr:]
            break
    if not rows:
        raise ValueError("ไม่พบชีตที่มีหัวตาราง EVE (ไฟล์ว่าง?)")
    header = [str(h).strip() for h in rows[0]]
    missing = [c for c in ("หมายเลขอนุกรม", "เวลาอัปเดต", "Total AC Output Power (Active)(W)")
               if c not in header]
    if missing:
        raise ValueError("ไม่ใช่รายงานรายการละเอียดของ EVE — ขาดคอลัมน์ " + ", ".join(missing))

    df = pd.DataFrame(rows[1:], columns=header)
    keep = [c for c in RAW_COLS if c in df.columns]
    df = df.loc[:, keep].rename(columns=RAW_COLS)
    for c in df.columns:
        if c in TEXT_COLS:
            df[c] = df[c].astype(str).str.strip()
        else:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    n_raw = len(df)
    df["ts"] = pd.to_datetime(df["ts"], format="%Y/%m/%d %H:%M:%S", errors="coerce")
    df = df.dropna(subset=["ts"])
    df = df[df["sn"].str.fullmatch(r"\d{10}")]
    # ถ้ากรองแล้วหายเกินครึ่ง แปลว่า EVE เปลี่ยนรูปแบบเวลา/SN — ให้ล้มดัง ๆ (ไฟล์จะไม่ถูกจำ
    # ในรายการที่อ่านแล้ว รอบหน้าลองใหม่ได้) ดีกว่าเงียบแล้วข้อมูลวันนั้นหายถาวร
    if n_raw and len(df) < n_raw * 0.5:
        raise ValueError(f"อ่านเวลา/SN ได้แค่ {len(df):,} จาก {n_raw:,} แถว — รูปแบบไฟล์ EVE อาจเปลี่ยน")
    df["src_file"] = os.path.basename(path)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """ติดธงเฟรมเสียแล้วล้างค่าวัดทั้งแถว (คงแถวไว้ให้นับได้ว่าเกิดเมื่อไร)"""
    df = df.copy()
    df["pac_kw"] = df["pac_w"] / 1000.0
    bad = (df["pac_kw"] > PAC_MAX_KW) | (df["ecum_kwh"] > ECUM_MAX_KWH) | (df["status"] == "10000")
    for c in PDC_COLS:
        bad |= df[c] > PDC_MPPT_MAX_W
    df["flag"] = bad.astype("int8")
    meas = [c for c in df.columns if c not in (*TEXT_COLS, "src_file", "flag", "rated_w", "mppt_n")]
    df.loc[bad, meas] = np.nan
    return df


def derive(df: pd.DataFrame) -> pd.DataFrame:
    """คอลัมน์คำนวณ — ต้องทำบนข้อมูลรวมทุกไฟล์ เพราะ dt ข้ามรอยต่อไฟล์"""
    df = df.sort_values(["sn", "ts"]).reset_index(drop=True)
    same = df["sn"].eq(df["sn"].shift())
    dt_hr = df["ts"].diff().dt.total_seconds().div(3600).where(same, DT_FIRST_HR)
    df["dt_hr"] = dt_hr.clip(lower=0, upper=DT_CAP_HR)
    for i in MPPT:
        df[f"e{i}"] = df[f"pdc{i}"].fillna(0) / 1000.0 * df["dt_hr"]
    df["e_dc"] = df[E_COLS].sum(axis=1)
    df["pdc_kw"] = df[PDC_COLS].sum(axis=1, min_count=1) / 1000.0
    vdc = df[VDC_COLS].where(df[VDC_COLS] > 50)        # 0 V = สตริงไม่ทำงาน ไม่เอามาเฉลี่ย
    df["vdc_mean"] = vdc.mean(axis=1)
    df["date"] = df["ts"].dt.normalize()
    df["hour"] = df["ts"].dt.hour.astype("int8")
    df["slot"] = df["ts"].dt.floor("15min")
    df["inv_no"] = df["sn"].map(inv_numbers(df["sn"].unique())).astype("int16")
    return df


def inv_numbers(sns) -> dict:
    """SN → หมายเลขเครื่อง · เครื่องที่ไม่อยู่ใน INVERTER_NO (เปลี่ยนเครื่องใหม่) ได้เลข 12, 13, ...
    เรียงตาม SN — ไม่ให้เป็นค่าว่าง เพราะทุกตาราง/กราฟใช้เลขนี้เป็นป้ายชื่อ"""
    out = {s: INVERTER_NO[s] for s in sns if s in INVERTER_NO}
    for k, s in enumerate(sorted(s for s in sns if s not in INVERTER_NO), start=N_INVERTERS + 1):
        out[s] = k
    return out


def _replace(tmp: str, dst: str, tries: int = 10) -> None:
    """os.replace ที่ทนไฟล์ถูกล็อกชั่วคราว (แดชบอร์ดกำลังอ่าน / OneDrive กำลังซิงก์)"""
    for i in range(tries):
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.5)


def _manifest_key(path: str) -> tuple:
    st_ = os.stat(path)
    return [st_.st_size, round(st_.st_mtime, 3)]


def ingest(rebuild: bool = False, dry_run: bool = False, log=print) -> dict:
    pq_dir = data_paths.solar_parquet_dir()
    os.makedirs(pq_dir, exist_ok=True)
    man_path = os.path.join(pq_dir, MANIFEST)
    rd_path = os.path.join(pq_dir, READINGS)
    # ไม่มีไฟล์ฐานแล้ว (ถูกลบ/OneDrive เปลี่ยนชื่อเป็นสำเนา conflict) → รายการที่เคยอ่านไม่มีความหมาย
    # ต้องอ่านใหม่หมด ไม่งั้นจะติดอยู่ที่ "ไม่มีไฟล์ใหม่" ตลอดไปทั้งที่ไฟล์ดิบอยู่ครบ
    if not os.path.exists(rd_path):
        rebuild = True
    manifest = {}
    if os.path.exists(man_path) and not rebuild:
        try:
            with open(man_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, ValueError) as e:
            log(f"    รายการไฟล์ที่อ่านแล้ว ({MANIFEST}) เสีย — อ่านไฟล์ดิบใหม่ทั้งหมด ({e})")
            rebuild = True

    files = list_raw_files()
    rel = lambda p: os.path.relpath(p, data_paths.solar_raw_dir())
    todo = [p for p in files if rel(p) not in manifest]
    # ไฟล์ที่เคยอ่านเข้าฐานแล้วแต่ขนาด/เวลาเปลี่ยน = มีคนเปิดใน Excel/Power Query แล้วบันทึกทับ (EVE ไม่เขียนทับ
    # ไฟล์เดิม ตัวย้ายไฟล์ก็ไม่ทับ) — ไม่อ่านซ้ำ ใช้แถวที่อ่านไว้ตอนไฟล์ยังเป็นต้นฉบับ แล้วจำฉบับใหม่ไว้
    # ไม่งั้นฉบับที่แก้แล้วอ่านไม่ได้จะขึ้น *** ทุกรอบตลอดไป หรือถ้าอ่านได้ ค่าที่ถูกแก้จะทับค่าจริง
    # (14 ต.ค. 69 ไฟล์ #1 ถูกแก้ตอน 15:54 หลังอ่านเข้าฐานตอน 08:01 — หัวตารางเลื่อนไปแถว 2 มีคอลัมน์สูตรแทรก)
    changed = [p for p in files if rel(p) in manifest and manifest[rel(p)] != _manifest_key(p)]
    stats = {"files_total": len(files), "files_new": len(todo), "rows_before": 0,
             "rows_after": 0, "errors": []}

    old = None
    if os.path.exists(rd_path) and not rebuild:
        old = pd.read_parquet(rd_path)
        stats["rows_before"] = len(old)
    for p in changed:
        n_old = int((old["src_file"] == os.path.basename(p)).sum()) if old is not None else 0
        stats["errors"].append(
            f"{rel(p)} ถูกแก้ไขหลังอ่านเข้าฐานแล้ว (ขนาด/เวลาไฟล์เปลี่ยน) — ไม่อ่านซ้ำ ใช้ {n_old:,} แถวเดิมที่อ่านไว้ "
            "· อย่าเปิดแล้วบันทึกไฟล์ในโฟลเดอร์ข้อมูลดิบ ให้ดูจากแดชบอร์ด/ดาวน์โหลด CSV แทน "
            "(ถ้าต้องการอ่านฉบับนี้จริง ให้รัน --rebuild)")

    def _save_manifest() -> None:
        # จำเฉพาะไฟล์ที่อ่านสำเร็จ — ไฟล์ใหม่ที่พังจะถูกลองใหม่ทุกรอบจนกว่าจะอ่านได้/ถูกลบ
        # (rebuild = เริ่มรายการใหม่ ไม่เก็บชื่อไฟล์เก่าที่ไม่มีแล้วค้างไว้)
        m = {} if rebuild else dict(manifest)
        for p in files:
            if p not in todo or p in parsed_ok:
                m[rel(p)] = _manifest_key(p)
        tmp = man_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=0)
        _replace(tmp, man_path)

    parsed_ok: set = set()
    if not todo:
        stats["rows_after"] = stats["rows_before"]
        if changed and not dry_run:
            _save_manifest()
        return stats
    if dry_run:
        stats["todo"] = [rel(p) for p in todo]
        return stats

    parts = []
    t0 = time.time()
    for p in todo:
        try:
            parts.append(parse_file(p))
            parsed_ok.add(p)
            log(f"    อ่าน {rel(p)}  ({len(parts[-1]):,} แถว)")
        except Exception as e:                      # ไฟล์เดียวพัง ไม่ให้ล้มทั้งรอบ
            stats["errors"].append(f"{rel(p)}: {e}")
            log(f"    ข้าม {rel(p)} — {e}")
    log(f"    (อ่าน {len(parts)} ไฟล์ ใช้เวลา {time.time() - t0:.0f} วินาที)")
    if not parts:
        stats["rows_after"] = stats["rows_before"]
        if changed:
            _save_manifest()
        return stats

    new = clean(pd.concat(parts, ignore_index=True))
    if old is not None:
        # ทิ้งเฉพาะคอลัมน์คำนวณ (derive() สร้างใหม่ทั้งหมด) — ห้ามตัดคอลัมน์ดิบตามไฟล์ใหม่
        # ไม่งั้น export รอบไหนขาดหัวคอลัมน์ไปหนึ่งตัว ประวัติทั้งหมดของคอลัมน์นั้นจะหาย
        old = old.drop(columns=[c for c in DERIVED_COLS if c in old.columns])
        new = pd.concat([old, new], ignore_index=True)
    missing = [c for c in RAW_COLS.values() if c not in new.columns]
    for c in missing:                               # คอลัมน์ที่ไม่มีเลยสักไฟล์ — เติมว่างไว้ให้ขั้น 3 ไม่ล้ม
        new[c] = "" if c in TEXT_COLS else np.nan
    if missing:
        log(f"    *** ไฟล์ EVE ไม่มีคอลัมน์: {', '.join(missing)} — เติมค่าว่างไว้ (EVE อาจเปลี่ยนรูปแบบรายงาน)")
    # เวลาซ้ำ (ดึงซ้ำ/สำเนา) — เลือกแถวที่ไม่ใช่เฟรมเสียก่อน แล้วค่อยเป็นไฟล์ที่อ่านหลังสุด
    # (sort แบบ stable: flag=1 ไปก่อน flag=0 ไปหลัง ลำดับไฟล์ในกลุ่มเดียวกันคงเดิม แล้ว keep="last")
    new = new.sort_values("flag", ascending=False, kind="stable")
    new = new.drop_duplicates(subset=["sn", "ts"], keep="last")
    new = derive(new)

    tmp = rd_path + ".tmp"
    new.to_parquet(tmp, engine="pyarrow", index=False)
    _replace(tmp, rd_path)
    _save_manifest()
    stats["rows_after"] = len(new)
    return stats


# ===========================================================================
# ขั้น 3 — สรุปรายวัน + โปรไฟล์ 15 นาที
# ===========================================================================
def phase_imbalance(df: pd.DataFrame) -> pd.Series:
    """% ความไม่สมดุลกระแส AC 3 เฟสรายแถว = (สูงสุด − ต่ำสุด) ÷ เฉลี่ย × 100
    ว่างเมื่อกระแสเฉลี่ยต่ำกว่า PHASE_IMBAL_MIN_A (ตอนเช้า/เย็น % แกว่งจนไม่มีความหมาย)"""
    i = df[list(PHASES.values())]
    avg = i.mean(axis=1)
    return ((i.max(axis=1) - i.min(axis=1)) / avg * 100).where(avg >= PHASE_IMBAL_MIN_A)


def summarize(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid = df[df["flag"] == 0]

    # ---- โปรไฟล์ราย 15 นาที ต่อเครื่อง (ตรงรอบวัด Demand ของการไฟฟ้า) ----
    prof = (valid.groupby(["sn", "date", "slot"], as_index=False)
            .agg(pac_mean=("pac_kw", "mean"), pac_max=("pac_kw", "max"),
                 pdc_mean=("pdc_kw", "mean"), vdc_mean=("vdc_mean", "mean"),
                 e_kwh=("e_dc", "sum"), n=("ts", "size")))
    sys_med = prof.groupby(["date", "slot"])["pac_mean"].median().rename("sys_pac_median")
    prof = prof.merge(sys_med, on=["date", "slot"], how="left")
    prof["hour"] = prof["slot"].dt.hour.astype("int8")
    day = prof["hour"].between(DAYLIGHT_HOURS[0], DAYLIGHT_HOURS[1] - 1)
    prof["outage"] = day & (prof["pac_mean"] <= OUTAGE_PAC_KW) & (prof["sys_pac_median"] >= OUTAGE_SYSTEM_KW)
    mid = prof["hour"].between(CURTAIL_HOURS[0], CURTAIL_HOURS[1] - 1)
    prof["curtail"] = mid & (prof["pac_mean"] < CURTAIL_PAC_KW) & (prof["vdc_mean"] > CURTAIL_VDC)
    nums = inv_numbers(df["sn"].unique())
    prof["inv_no"] = prof["sn"].map(nums).astype("int16")

    # ---- รายวัน ต่อเครื่อง ----
    agg = {
        "ac_kwh": ("eday_kwh", "max"),          # Eday เป็นมิเตอร์สะสมในวัน รีเซ็ตทุกเช้า
        "ecum_min": ("ecum_kwh", "min"), "ecum_max": ("ecum_kwh", "max"),
        "dc_kwh": ("e_dc", "sum"),
        "pac_max": ("pac_kw", "max"), "pdc_max": ("pdc_kw", "max"),
        "t_heatsink_max": ("t_heatsink", "max"),
        "n_rows": ("ts", "size"), "first_ts": ("ts", "min"), "last_ts": ("ts", "max"),
        "fw": ("fw", "last"),
    }
    for i in MPPT:
        agg[f"e{i}"] = (f"e{i}", "sum")
        agg[f"pdc{i}_max"] = (f"pdc{i}", "max")
        agg[f"idc{i}_max"] = (f"idc{i}", "max")
    for c in PHASES.values():
        agg[f"{c}_max"] = (c, "max")
    daily = valid.groupby(["sn", "date"], as_index=False).agg(**agg)
    daily["ecum_delta"] = daily["ecum_max"] - daily["ecum_min"]
    daily["ac_eday"] = daily["ac_kwh"]
    use_ecum = (daily["ecum_delta"].between(0, ECUM_DAY_MAX_KWH)
                & (daily["ecum_delta"] - daily["ac_eday"].fillna(0)
                   > np.maximum(ECUM_OVER_EDAY_KWH, ECUM_OVER_EDAY_PCT * daily["ecum_delta"])))
    daily["ac_kwh"] = daily["ac_eday"].where(~use_ecum, daily["ecum_delta"])
    daily["ac_src"] = np.where(use_ecum, "Ecum", "Eday")

    # พลังงานที่ผลิตระหว่างที่ logger เงียบข้ามวัน (แถวก่อน-หลังอยู่คนละวัน) — Ecum เพิ่มแต่ไม่มีแถวในวันไหน
    # ให้นับได้ จึงไม่อยู่ในยอดรายวันใด ๆ เก็บไว้ที่วันที่เริ่มเงียบ เพื่อแจ้งให้รู้ว่ายอดรวมต่ำกว่าจริงเท่าไร
    v = valid.dropna(subset=["ecum_kwh"]).sort_values(["sn", "ts"])
    nxt = v.groupby("sn")[["ts", "ecum_kwh", "date"]].shift(-1)
    jump = (nxt["ecum_kwh"] - v["ecum_kwh"])
    cross = (nxt["date"] != v["date"]) & nxt["date"].notna() & (jump >= GAP_ENERGY_MIN_KWH) & (jump < ECUM_DAY_MAX_KWH * 7)
    gaps = pd.DataFrame({"sn": v.loc[cross, "sn"], "date": v.loc[cross, "date"], "gap_kwh": jump[cross],
                         "gap_from": v.loc[cross, "ts"], "gap_to": nxt.loc[cross, "ts"]})
    gaps = gaps.groupby(["sn", "date"], as_index=False).agg(
        gap_kwh=("gap_kwh", "sum"), gap_from=("gap_from", "min"), gap_to=("gap_to", "max"))
    daily = daily.merge(gaps, on=["sn", "date"], how="left")
    daily["gap_kwh"] = daily["gap_kwh"].fillna(0.0)

    # สุขภาพสตริง: median ของ Vdc / Pdc / Idc ช่วงแดดเต็ม (10–14 น.) ขณะเครื่องผลิตจริง
    m = valid[valid["hour"].between(MIDDAY_HOURS[0], MIDDAY_HOURS[1] - 1)
              & (valid["pdc_kw"] > MIDDAY_MIN_PDC_KW)]
    midc = PDC_COLS + VDC_COLS + IDC_COLS + list(PHASES.values()) + AC_V_COLS
    mid_med = m.groupby(["sn", "date"])[midc].median()
    mid_med.columns = [f"{c}_mid" for c in midc]
    mid_med["n_mid"] = m.groupby(["sn", "date"]).size()
    daily = daily.merge(mid_med.reset_index(), on=["sn", "date"], how="left")
    daily["n_mid"] = daily["n_mid"].fillna(0).astype("int32")
    # เฟรมช่วงแดดเต็ม "ทุกเฟรม" (ไม่ดูว่าผลิตไหม) + Vdc/สถานะช่วงนั้น — ใช้แยก "ออนไลน์แต่ไม่จ่ายไฟ"
    # ออกจาก "ไม่มีข้อมูล": เครื่องที่ถูกจำกัดกำลังเป็น 0 ส่งเฟรมครบ ~200 เฟรมแต่ n_mid (ผลิต > 20 kW) = 0
    am = valid[valid["hour"].between(MIDDAY_HOURS[0], MIDDAY_HOURS[1] - 1)]
    am_g = am.groupby(["sn", "date"])
    am_s = pd.DataFrame({"n_mid_all": am_g.size(), "vdc_mid_all": am_g["vdc_mean"].median(),
                         "status_mid": am_g["status"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "")})
    daily = daily.merge(am_s.reset_index(), on=["sn", "date"], how="left")
    daily["n_mid_all"] = daily["n_mid_all"].fillna(0).astype("int32")
    daily["status_mid"] = daily["status_mid"].fillna("")
    # เวลาสุดท้ายที่เครื่องจ่ายไฟ (Pac ≥ PAC_ON_KW) ในวันนั้น — บอกได้ว่าหยุดกี่โมง
    on = valid[valid["pac_kw"] >= PAC_ON_KW].groupby(["sn", "date"])["ts"].max().rename("last_on_ts")
    daily = daily.merge(on.reset_index(), on=["sn", "date"], how="left")
    # นาทีช่วงกลางวันที่ไม่ได้รับค่าจากมิเตอร์ Zero-export (Grid Status = Static) — ดู METER_LOST_STATUS
    dl = valid[valid["hour"].between(DAYLIGHT_HOURS[0], DAYLIGHT_HOURS[1] - 1)]
    sm = (dl[dl["grid_status"] == METER_LOST_STATUS].groupby(["sn", "date"])["dt_hr"].sum() * 60).rename("static_min")
    daily = daily.merge(sm.reset_index(), on=["sn", "date"], how="left")
    daily["static_min"] = daily["static_min"].fillna(0).round().astype("int32")
    # ความไม่สมดุลกระแส AC 3 เฟส ช่วงแดดเต็ม (ค่ากลางของทั้งวัน) — สูงผิดปกติ = เฟสใดเฟสหนึ่งมีปัญหา
    mi = m.assign(_imb=phase_imbalance(m)).groupby(["sn", "date"])["_imb"].median().rename("phase_imbal_pct")
    daily = daily.merge(mi.reset_index(), on=["sn", "date"], how="left")

    # จำนวนสตริงต่อ MPPT (1 หรือ 2) — อนุมานจาก "ประวัติทั้งหมด" ไม่ใช่ช่วงที่ผู้ใช้เลือก
    # ถ้าอนุมานจากช่วงที่เลือก MPPT 2 สตริงที่สตริงขาดไปหนึ่ง (กระแสหายครึ่ง) จะถูกนับใหม่เป็น
    # 1 สตริง แล้วพลังงานต่อสตริงกลับดูปกติ — ความผิดปกติที่ต้องจับจะหายไปจากหน้าจอ
    # ใช้เปอร์เซ็นไทล์ 90 ของสัดส่วน Idc(MPPT นั้น) ÷ Idc(MPPT สูงสุดในเครื่อง) รายวัน = สภาพตอนดีที่สุด
    idc_mid = daily[[f"idc{i}_mid" for i in MPPT]]
    share = idc_mid.div(idc_mid.max(axis=1), axis=0)
    share.columns = [f"s{i}" for i in MPPT]
    base = pd.concat([daily[["sn"]], share], axis=1).groupby("sn").quantile(0.9)
    for i in MPPT:
        nstr = (base[f"s{i}"] >= STRINGS_2_RATIO).map({True: 2, False: 1})
        daily[f"nstr{i}"] = daily["sn"].map(nstr).fillna(1).astype("int8")

    # เฟรม fault นับจากทุกแถว (รวมเฟรมเสียที่ถูกล้างค่า)
    # นับเฉพาะเฟรมที่ไม่ใช่เฟรมเสีย — เฟรมเสีย (status 10000) เป็นข้อมูลขยะจาก logger ไม่ใช่เครื่อง fault
    # (#4 เคยถูกแจ้งว่า "Fault 1 ครั้ง" จากเฟรมเสียเฟรมเดียว แล้วถูกนับเป็นเครื่องที่ต้องตรวจ)
    nf = (df[~df["status"].isin(OK_STATUS) & (df["flag"] == 0)].groupby(["sn", "date"]).size()
          .rename("n_fault").reset_index())
    daily = daily.merge(nf, on=["sn", "date"], how="left")
    daily["n_fault"] = daily["n_fault"].fillna(0).astype("int32")

    # ความครบของข้อมูล เทียบกับเครื่องที่ส่งข้อมูลมากที่สุดในวันนั้น
    daily["coverage_pct"] = daily["n_rows"] / daily.groupby("date")["n_rows"].transform("max") * 100
    # DC มาจากการอินทิเกรตทุกเฟรม — เครื่องที่ logger ส่งข้อมูลขาดช่วง DC จะต่ำกว่าจริงมาก
    # (#6 ส่งมาแค่ ~12% ทำให้ AC/DC ออกมา 112% ซึ่งเป็นไปไม่ได้) จึงคิดเฉพาะวันที่ข้อมูลครบพอ
    # ต้องมีเฟรมช่วงผลิตจริงมากพอด้วย — #6 วันที่ 25–27 ก.ย. ส่งแถวกลางคืนเป็นร้อยแต่กลางวันแค่ 0–29 แถว
    # coverage จึงดูเหมือน 100% ทั้งที่ DC อินทิเกรตได้แค่เศษเดียว ออกมาเป็น 265% ซึ่งเป็นไปไม่ได้
    daily["eff_pct"] = (daily["ac_kwh"] / daily["dc_kwh"] * 100).where(
        (daily["dc_kwh"] > 1) & (daily["coverage_pct"] >= EFF_MIN_COVERAGE)
        & (daily["n_mid"] >= EFF_MIN_MID_FRAMES))
    daily.loc[daily["eff_pct"] > 100, "eff_pct"] = np.nan      # เกิน 100% = ข้อมูลไม่ครบ ไม่ใช่ค่าจริง

    # วันที่ไม่มีแถวช่วงผลิต (06:00–18:30) เลย — Eday ที่ส่งมาตอนกลางคืนอาจเป็น 0 ทั้งที่ผลิตจริง (#6)
    # ให้เป็น "ไม่มีข้อมูล" (NaN) ไม่ใช่ 0 kWh ผลผลิตวันนั้นถ้ามีจะอยู่ใน gap_kwh จากมิเตอร์สะสม
    hf = valid["ts"].dt.hour + valid["ts"].dt.minute / 60          # ชั่วโมงทศนิยม — 18:28 ต้องไม่นับเป็นช่วงผลิต
    nd = valid[(hf >= DAYLIGHT_ROWS_HOURS[0]) & (hf < DAYLIGHT_ROWS_HOURS[1])].groupby(["sn", "date"]).size()
    daily = daily.merge(nd.rename("n_day").reset_index(), on=["sn", "date"], how="left")
    daily["n_day"] = daily["n_day"].fillna(0).astype("int32")
    no_day = (daily["n_day"] < DAY_MIN_ROWS) & (daily["ac_kwh"].fillna(0) <= 0)
    daily.loc[no_day, "ac_kwh"] = np.nan
    daily.loc[no_day, "ac_src"] = "ไม่มีข้อมูล"

    # ออนไลน์แต่ไม่จ่ายไฟทั้งวัน (ดู ZERO_DAY_*) — ผลผลิตเป็น 0 จริง ไม่ใช่ข้อมูลขาด จึงคง 0 kWh ไว้แต่ติดธง
    # เทียบกับเครื่องที่ผลิตได้มากสุดในวันเดียวกัน: ถ้าทุกเครื่องเป็น 0 (ฝนทั้งวัน/ไฟดับทั้งระบบ) ไม่ติดธง
    ref = daily.groupby("date")["ac_kwh"].transform("max")
    daily["zero_day"] = ((daily["n_mid_all"] >= ZERO_DAY_MIN_MID_ROWS)
                         & (daily["ac_kwh"].fillna(0) < ZERO_DAY_AC_KWH) & (ref >= ZERO_DAY_REF_KWH))
    # วันที่ไม่จ่ายไฟ DC ที่อินทิเกรตได้ (16–75 kWh/วัน) คือ Idc ~1 A ระดับพื้นของเซนเซอร์ × Voc ~850 V
    # ไม่ใช่พลังงานจริง (เครื่องไม่ได้ดึงกำลังจากแผง) — ให้เป็น 0 ไม่งั้นกราฟ DC ต่อ MPPT ดูเหมือนแผงผลิตแต่ AC หาย
    daily.loc[daily["zero_day"], ["dc_kwh", *E_COLS]] = 0.0

    ev = (prof.groupby(["sn", "date"])[["outage", "curtail"]].sum() * 15).astype("int32")
    ev.columns = ["outage_min", "curtail_min"]
    daily = daily.merge(ev.reset_index(), on=["sn", "date"], how="left")
    daily[["outage_min", "curtail_min"]] = daily[["outage_min", "curtail_min"]].fillna(0).astype("int32")

    daily["inv_no"] = daily["sn"].map(nums).astype("int16")
    daily = daily.sort_values(["date", "inv_no"]).reset_index(drop=True)
    return daily, prof


def write_summaries(daily: pd.DataFrame, prof: pd.DataFrame) -> None:
    pq_dir = data_paths.solar_parquet_dir()
    for name, d in ((DAILY, daily), (PROFILE, prof)):
        tmp = os.path.join(pq_dir, name + ".tmp")
        d.to_parquet(tmp, engine="pyarrow", index=False)
        _replace(tmp, os.path.join(pq_dir, name))


def partial_days(daily: pd.DataFrame) -> dict:
    """วันที่ข้อมูลไม่ครบวัน → {date: เวลาข้อมูลล่าสุดของวันนั้น}

    ไม่ใช่แค่วันล่าสุด: export แต่ละรอบครอบคลุมช่วงวันที่ที่เลือกไว้ใน EVE ถ้ารอบก่อนดึงตอนบ่าย
    แล้วรอบถัดไปเริ่มวันรุ่งขึ้น ช่วงบ่ายของวันนั้นจะหายถาวร (เจอจริง 15 ก.ย. 69 ข้อมูลหยุด 15:41
    ทั้งที่ทุกเครื่องยังผลิต ~10 kW) — วันแบบนี้ต้องไม่นับเป็นวันผลผลิตต่ำ"""
    if daily.empty:
        return {}
    t = daily.groupby("date")["last_ts"].max()
    frac = t.dt.hour + t.dt.minute / 60
    return {d: ts for d, ts in t[frac < DAY_COMPLETE_HOUR].items()}


def partial_last_day(daily: pd.DataFrame):
    """วันล่าสุดยังไม่ครบวันไหม (ดึง EVE ก่อนแดดหมด) → คืนเวลาข้อมูลล่าสุดของวันนั้น หรือ None"""
    if daily.empty:
        return None
    return partial_days(daily).get(daily["date"].max())


# ===========================================================================
# ฟังก์ชันให้แดชบอร์ดเรียก (อ่าน parquet + สรุปตามช่วงที่เลือก)
# ===========================================================================
def load_daily() -> pd.DataFrame:
    return pd.read_parquet(os.path.join(data_paths.solar_parquet_dir(), DAILY))


def load_profile() -> pd.DataFrame:
    return pd.read_parquet(os.path.join(data_paths.solar_parquet_dir(), PROFILE))


def load_readings(date_from=None, date_to=None, sn: str | None = None) -> pd.DataFrame:
    """อ่านแถวดิบเฉพาะช่วง/เครื่องที่ขอ (pyarrow กรองก่อนโหลด ไม่ต้องอ่านทั้งไฟล์)"""
    filters = []
    if date_from is not None:
        filters.append(("date", ">=", pd.Timestamp(date_from)))
    if date_to is not None:
        filters.append(("date", "<=", pd.Timestamp(date_to)))
    if sn:
        filters.append(("sn", "==", sn))
    return pd.read_parquet(os.path.join(data_paths.solar_parquet_dir(), READINGS),
                           filters=filters or None)


def mppt_table(daily: pd.DataFrame) -> pd.DataFrame:
    """ตารางราย MPPT ของช่วงที่ส่งเข้ามา — 1 แถวต่อ (เครื่อง, MPPT)

    คอลัมน์: e_kwh พลังงาน DC รวม · idc_mid กระแสกลางวัน (median) · n_str จำนวนสตริงที่อนุมาน
    · per_str พลังงานต่อสตริง · ratio = per_str ÷ เฉลี่ยต่อสตริงของเครื่อง (1.0 = ปกติ)
    · vdc_mid แรงดันกลางวัน · vdc_ratio เทียบ MPPT อื่นในเครื่อง
    """
    if daily.empty:
        return pd.DataFrame()
    recs = []
    for sn, g_all in daily.groupby("sn"):
        no = int(g_all["inv_no"].iloc[0])
        # ใช้เฉพาะวันที่ข้อมูลช่วงแดดเต็มพอ (ดู MPPT_MIN_MID_FRAMES) — ไม่มีเลยในช่วงนี้ = ค่าว่างทุก MPPT (ช่องเทา)
        ok = (g_all["n_mid"] >= MPPT_MIN_MID_FRAMES) if "n_mid" in g_all.columns \
            else g_all[[f"vdc{i}_mid" for i in MPPT]].notna().any(axis=1)
        g = g_all[ok]
        if g.empty:
            recs.extend({"inv_no": no, "sn": sn, "mppt": i, "e_kwh": np.nan, "idc_mid": np.nan, "n_str": np.nan,
                         "per_str": np.nan, "ratio": np.nan, "vdc_mid": np.nan, "vdc_others": np.nan,
                         "vdc_ratio": np.nan, "days": 0} for i in MPPT)
            continue
        e = g[E_COLS].sum()
        idc = g[[f"idc{i}_mid" for i in MPPT]].median()
        vdc = g[[f"vdc{i}_mid" for i in MPPT]].median()
        if all(f"nstr{i}" in g.columns for i in MPPT):    # จำนวนสตริงจากประวัติทั้งหมด (summarize)
            n_str = pd.Series({i: int(g[f"nstr{i}"].iloc[0]) for i in MPPT})
        else:                                               # parquet รุ่นเก่า — อนุมานจากช่วงนี้
            idc_max = idc.max()
            n_str = pd.Series({i: (2 if idc[f"idc{i}_mid"] >= STRINGS_2_RATIO * idc_max else 1)
                               for i in MPPT}) if idc_max > 0 else pd.Series({i: 1 for i in MPPT})
        per_str = pd.Series({i: e[f"e{i}"] / n_str[i] for i in MPPT})
        mean_per_str = e.sum() / n_str.sum() if n_str.sum() else np.nan
        for i in MPPT:
            v = vdc[f"vdc{i}_mid"]
            others = vdc.drop(f"vdc{i}_mid")
            others = others[others > 50]
            recs.append({
                "inv_no": no, "sn": sn, "mppt": i,
                "e_kwh": e[f"e{i}"], "idc_mid": idc[f"idc{i}_mid"], "n_str": int(n_str[i]),
                "per_str": per_str[i],
                "ratio": per_str[i] / mean_per_str if mean_per_str else np.nan,
                "vdc_mid": v, "vdc_others": others.median() if not others.empty else np.nan,
                "vdc_ratio": v / others.median() if (not others.empty and pd.notna(v)) else np.nan,
                "days": int(g[f"vdc{i}_mid"].notna().sum()),
            })
    return pd.DataFrame(recs).sort_values(["inv_no", "mppt"]).reset_index(drop=True)


def mppt_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """ตารางราย MPPT แยกรายวัน (date, sn, mppt, ratio, vdc_ratio ...) — คิดแบบ mppt_table() ทีละวัน
    จำนวนสตริงยังมาจากประวัติทั้งหมด (คอลัมน์ nstr*) วันเดียวจึงเทียบกันได้ตรง"""
    if daily.empty:
        return pd.DataFrame()
    parts = [mppt_table(g).assign(date=d) for d, g in daily.groupby("date")]
    return pd.concat(parts, ignore_index=True)


def inverter_summary(daily: pd.DataFrame) -> pd.DataFrame:
    """ตารางสรุปรายเครื่องของช่วงที่ส่งเข้ามา — เทียบเท่าชีต Summary ของ Report&EE_DATA
    (ต่างตรงที่เทียบ MPPT แบบ "ต่อสตริง" ดูคำอธิบายที่ STRINGS_2_RATIO)"""
    if daily.empty:
        return pd.DataFrame()
    mt = mppt_table(daily)
    rows = []
    for sn, g in daily.groupby("sn"):
        days = int(g["ac_kwh"].notna().sum())        # นับเฉพาะวันที่มีข้อมูลจริง (วัน NaN = logger ไม่ส่ง)
        zd = g["zero_day"] if "zero_day" in g.columns else pd.Series(False, index=g.index)
        ac, dc = g["ac_kwh"].sum(), g["dc_kwh"].sum()
        m = mt[mt["sn"] == sn].set_index("mppt")
        # เครื่องที่ DC เป็น 0 ทั้งช่วง (ปลดวงจรซ่อม / เพิ่งกลับมา) ratio เป็นค่าว่างทั้งหมด
        # idxmax() บนค่าว่างล้วนจะ error แล้วพาทั้งแท็บพัง จึงต้องกันไว้
        if m["ratio"].notna().any():
            best_m, worst_m = int(m["ratio"].idxmax()), int(m["ratio"].idxmin())
        else:
            best_m = worst_m = 0
        ratio = m["ratio"].min()
        ac_ok = g["ac_kwh"].notna().any()
        best = g.loc[g["ac_kwh"].idxmax()] if ac_ok else g.iloc[0]
        worst = g.loc[g["ac_kwh"].idxmin()] if ac_ok else g.iloc[0]
        # ประสิทธิภาพคิดเฉพาะวันที่ข้อมูลครบพอ (ดู EFF_MIN_COVERAGE) ทั้งตัวตั้งและตัวหาร
        ok = g["eff_pct"].notna()
        ac_e, dc_e = g.loc[ok, "ac_kwh"].sum(), g.loc[ok, "dc_kwh"].sum()
        rows.append({
            "inv_no": int(g["inv_no"].iloc[0]), "sn": sn, "days": days,
            "ac_kwh": ac, "avg_kwh": ac / days if days else np.nan,
            "best_kwh": best["ac_kwh"], "best_date": best["date"],
            "worst_kwh": worst["ac_kwh"], "worst_date": worst["date"],
            "pac_max": g["pac_max"].max(), "pdc_max": g["pdc_max"].max(),
            "cf_pct": ac / (RATED_KW * 24 * days) * 100 if days else np.nan,
            "eff_pct": ac_e / dc_e * 100 if dc_e > 1 else np.nan,
            "dc_kwh": dc,
            "mppt_best": best_m, "mppt_worst": worst_m,
            "mppt_min_ratio": ratio,
            "n_strings": int(m["n_str"].sum()),
            "coverage_pct": g["coverage_pct"].mean(),
            "outage_min": int(g["outage_min"].sum()),
            "outage_days": int((g["outage_min"] > 0).sum()),
            # วันที่ไม่จ่ายไฟทั้งวันไม่นับเป็น "ถูกจำกัดกำลัง" (Zero-export ชั่วคราว) — เป็นคนละเรื่อง
            "curtail_days": int(((g["curtail_min"] >= 60) & ~zd).sum()),
            "zero_days": int(zd.sum()),
            # วันที่ลิงก์มิเตอร์หลุดนานจนเครื่องหยุดจ่ายไฟ (หยุดกลางวัน ≥ 15 นาที หรือไม่จ่ายไฟทั้งวัน)
            "static_days": int(((g["static_min"] >= STATIC_NODE_MIN) & ((g["outage_min"] >= 15) | zd)).sum())
            if "static_min" in g.columns else 0,
            "n_fault": int(g["n_fault"].sum()),
            "fw": g["fw"].iloc[-1],
        })
    out = pd.DataFrame(rows).sort_values("inv_no").reset_index(drop=True)
    out["status"] = np.select(
        [out["zero_days"] > 0, out["mppt_min_ratio"].isna(), out["mppt_min_ratio"] < 1 - MPPT_ALERT],
        ["ไม่จ่ายไฟ " + out["zero_days"].astype(str) + " วัน", "ไม่มีข้อมูล DC",
         "ตรวจสอบ MPPT " + out["mppt_worst"].astype(str)], "ปกติ")
    return out


def string_health(daily: pd.DataFrame) -> pd.DataFrame:
    """Vdc กลางวันราย MPPT เทียบ MPPT อื่นในเครื่องเดียวกัน → หาสตริงที่น่าจะขาด
    (แรงดันไม่ขึ้นกับจำนวนสตริงขนาน จึงใช้ชี้สตริงขาด/วงจรเปิดได้ตรงกว่าพลังงาน)"""
    mt = mppt_table(daily)
    if mt.empty:
        return mt
    out = mt.dropna(subset=["vdc_ratio"])[["inv_no", "sn", "mppt", "vdc_mid", "vdc_others", "days"]].copy()
    out["ratio"] = mt.loc[out.index, "vdc_ratio"]
    return out.reset_index(drop=True)


def alerts(daily: pd.DataFrame) -> list[dict]:
    """รายการสิ่งที่ต้องตรวจในช่วงที่ส่งเข้ามา — level: error / warning / info"""
    out = []
    if daily.empty:
        return out
    summ = inverter_summary(daily)
    mt = mppt_table(daily)
    fmt_d = lambda s: pd.Timestamp(s).strftime("%d/%m")

    # ออนไลน์แต่ไม่จ่ายไฟทั้งวัน — เครื่องที่หยุดวันเดียวกันรวมเป็นรายการเดียว (9 เครื่องพร้อมกัน = ระบบควบคุม/
    # การตั้งค่า ไม่ใช่เครื่องเสียทีละตัว) ขึ้นก่อนทุกรายการ เพราะผลผลิตหายวันละ ~300 kWh ต่อเครื่อง
    zd = daily[daily["zero_day"]] if "zero_day" in daily.columns else daily.iloc[0:0]
    if not zd.empty:
        groups: dict[tuple, list] = {}
        for sn, g in zd.groupby("sn"):
            groups.setdefault(tuple(sorted(g["date"])), []).append((int(g["inv_no"].iloc[0]), sn))
        for ds, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            members.sort()
            nos, sns = [n for n, _ in members], [s for _, s in members]
            tags = ", ".join(f"#{n}" for n in nos)
            # เริ่มหยุดเมื่อไร = เวลาสุดท้ายที่จ่ายไฟในวันก่อนหน้าวันแรกที่เป็น 0 (ถ้าวันนั้นอยู่ในช่วงที่ดู)
            since = ""
            prev = daily[daily["sn"].isin(sns) & (daily["date"] < ds[0])]
            if not prev.empty and "last_on_ts" in prev.columns:
                t = prev[prev["date"] == prev["date"].max()]["last_on_ts"].dropna()
                if not t.empty:
                    lo, hi = t.min(), t.max()
                    together = (hi - lo) <= pd.Timedelta(minutes=5)
                    since = (f" · หยุดตั้งแต่ {lo:%d/%m %H:%M}" + ("" if together else f"–{hi:%H:%M}")
                             + (" พร้อมกัน" if together and len(sns) > 1 else ""))
            # ที่หายไป ≈ ถ้าผลิตได้เท่าค่ากลางของเครื่องที่ยังผลิตอยู่ในวันเดียวกัน (ประมาณการ ไม่ใช่มิเตอร์)
            prod = daily[daily["date"].isin(ds) & (daily["ac_kwh"] >= ZERO_DAY_REF_KWH)]
            lost = float(prod.groupby("date")["ac_kwh"].median().reindex(list(ds)).fillna(0).sum()) * len(sns)
            ok_tags = ", ".join(f"#{int(n)}" for n in sorted(prod["inv_no"].unique()))
            z = zd[zd["sn"].isin(sns)]
            vdc = z["vdc_mid_all"].median() if "vdc_mid_all" in z.columns else np.nan
            st_txt = z["status_mid"].mode().iloc[0] if "status_mid" in z.columns and not z["status_mid"].mode().empty else ""
            days_txt = (f"{fmt_d(ds[0])}–{fmt_d(ds[-1])}" if len(ds) > 1 and (pd.Timestamp(ds[-1]) - pd.Timestamp(ds[0])).days == len(ds) - 1
                        else ", ".join(fmt_d(d) for d in ds))
            # สาเหตุที่ชี้ได้จากข้อมูล: ไม่ได้รับค่าจากมิเตอร์ Zero-export ตลอดวัน → fail-safe จ่าย 0 W
            static_med = z["static_min"].median() if "static_min" in z.columns else 0
            if static_med >= STATIC_SYSTEM_MIN:
                cause = (f"สาเหตุ: อินเวอร์เตอร์ไม่ได้รับค่าจากมิเตอร์ Zero-export ตลอดวัน (Grid Status = Static "
                         f"~{static_med:,.0f} นาที/วัน ปกติ 40–90) เครื่องกลุ่มนี้ตั้ง fail-safe จ่าย 0 W เมื่อขาดมิเตอร์ — "
                         "ให้ตรวจสาย RS485/ขั้วต่อ/ตัวควบคุม Zero-export และตัวมิเตอร์ก่อน แล้วค่อยดูค่า Active Power Limit "
                         "ในเว็บ EVE และหน้าจออินเวอร์เตอร์ (ลิงก์กลับมาเมื่อไร เครื่องจะกลับมาจ่ายไฟเองใน ~1–2 นาที)")
            else:
                cause = ("ตรวจระบบจำกัดกำลัง Zero-export (ตัวควบคุม/มิเตอร์/CT) ค่า Active Power Limit "
                         "หรือคำสั่งหยุดเครื่องในเว็บ EVE และหน้าจออินเวอร์เตอร์")
            out.append({"level": "error", "inv_no": 0 if len(sns) > 1 else nos[0], "inv_nos": nos,
                        "text": f"{tags} ออนไลน์แต่ไม่จ่ายไฟทั้งวัน {len(ds)} วัน ({days_txt}){since} — "
                                f"logger ส่งข้อมูลครบ สถานะ {st_txt or 'ปกติ'} ไฟกริดมี"
                                + (f" แต่ Vdc ลอยที่ ~{vdc:,.0f} V (เปิดวงจร)" if pd.notna(vdc) else "")
                                + " = อินเวอร์เตอร์ไม่ดึงกำลังจากแผง **ไม่ใช่ข้อมูลขาด** · "
                                + (f"เครื่องที่ยังผลิตอยู่: {ok_tags} · " if ok_tags else "")
                                + f"ผลผลิตที่หายไปราว {lost:,.0f} kWh (ถ้าได้เท่าเครื่องที่ผลิตอยู่) · " + cause})

    # โหนดมิเตอร์ของเครื่องเดียวหลุดนาน ขณะเครื่องอื่นปกติ และเครื่องหยุดจ่ายไฟจริงในวันนั้น — อธิบาย "หยุดจ่ายไฟ
    # กลางวัน" ของ #10 (8 วันใน ก.ย.–ต.ค. 69) · ต้องมีหลักฐานว่าหยุดด้วย: #11 มี Static มากกว่าเครื่องอื่นเป็นปกติ
    # (50–130 นาที/วัน) แต่ไม่เคยหยุด ถ้าดูแค่นาที Static จะฟ้อง #11 ผิด
    if "static_min" in daily.columns:
        med = daily.groupby("date")["static_min"].transform("median")
        node = daily[(daily["static_min"] >= STATIC_NODE_MIN) & (med < STATIC_NODE_MIN) & (daily["outage_min"] >= 15)]
        for sn, g in node.groupby("sn"):
            no = int(g["inv_no"].iloc[0])
            lst = ", ".join(f"{fmt_d(x.date)} {int(x.static_min)} นาที" for x in g.sort_values("date").itertuples())
            out.append({"level": "warning", "inv_no": no,
                        "text": f"#{no} (SN {sn}) ไม่ได้รับค่าจากมิเตอร์ Zero-export (Grid Status = Static) นานผิดปกติ "
                                f"{len(g)} วัน ขณะเครื่องอื่นปกติ — {lst} · ระหว่างนั้นเครื่องจ่าย 0 W (fail-safe) "
                                "= สาเหตุของ 'หยุดจ่ายไฟกลางวัน' ของเครื่องนี้ ไม่ใช่ตัวเครื่องเสีย — "
                                "ตรวจสาย/ขั้วต่อ RS485 ที่โหนดของเครื่องนี้"})

    # เครื่องที่ "ไม่มีแถวเลย" ไม่อยู่ใน summ — ต้องเทียบกับรายการ 11 ตัวเอง ไม่งั้นหายเงียบ
    # (logger หลุด / ปิดเครื่อง / ลืม export ไฟล์ของเครื่องนั้น) ทั้งที่ผลผลิตหายไปทั้งเครื่อง
    dates = sorted(daily["date"].unique())
    for sn, no in sorted(INVERTER_NO.items(), key=lambda kv: kv[1]):
        g_sn = daily[daily["sn"] == sn]
        # "มีข้อมูล" = วันที่สรุปยอด AC ได้ (ac_kwh ไม่ว่าง) — วันที่ logger ส่งแต่กลางคืนและ Eday = 0
        # (#6 02/10, 05/10) ถูกตั้งเป็นว่างใน summarize() จึงนับว่าไม่มีข้อมูล · วันที่ใช้ Ecum แทนได้ (03/10) ยังนับว่ามี
        have = set(g_sn.loc[g_sn["ac_kwh"].notna(), "date"])
        gone = [d for d in dates if d not in have]
        if not have:
            out.append({"level": "error", "inv_no": no,
                        "text": f"#{no} (SN {sn}) ไม่มีข้อมูลเลยในช่วงนี้ — ตรวจว่าเครื่องทำงาน/logger ส่งข้อมูล "
                                "และ export จาก EVE ครบ 11 ไฟล์"})
        elif gone:
            out.append({"level": "error", "inv_no": no,
                        "text": f"#{no} (SN {sn}) ไม่มีข้อมูลช่วงผลิต {len(gone)} วันที่เครื่องอื่นมี — "
                                + ", ".join(fmt_d(d) for d in gone[:10]) + (" ..." if len(gone) > 10 else "")
                                + " (ผลผลิตวันนั้นไม่ถูกนับในยอดรวม — ถ้ามิเตอร์สะสมเห็นว่าผลิต จะแจ้งแยกเป็น kWh ที่ระบุวันไม่ได้)"})

    for _, r in summ.iterrows():
        tag = f"#{r['inv_no']} (SN {r['sn']})"
        if r["outage_days"] > 0:
            days = daily[(daily["sn"] == r["sn"]) & (daily["outage_min"] > 0)]
            lst = ", ".join(f"{fmt_d(x.date)} {int(x.outage_min)} นาที" for x in days.itertuples())
            out.append({"level": "error", "inv_no": r["inv_no"],
                        "text": f"{tag} หยุดจ่ายไฟกลางวันขณะเครื่องอื่นผลิตอยู่ {r['outage_days']} วัน "
                                f"รวม {r['outage_min']:,} นาที — {lst}"})
        if r["inv_no"] > N_INVERTERS:
            out.append({"level": "warning", "inv_no": r["inv_no"],
                        "text": f"{tag} เป็นเครื่องที่ระบบยังไม่รู้จัก (ไม่อยู่ในรายการ 11 ตัวเดิม) — ถ้าเปลี่ยน "
                                "อินเวอร์เตอร์ใหม่ ให้แจ้งคนดูแลระบบเพิ่ม SN นี้ใน INVERTER_NO ของ solar_etl.py"})
        # ดูจาก ratio ตรง ๆ ไม่ใช่จากคอลัมน์ status (สถานะ "ไม่จ่ายไฟ" มาก่อน แต่ MPPT ที่ตกในวันอื่นยังต้องแจ้ง)
        if pd.notna(r["mppt_min_ratio"]) and r["mppt_min_ratio"] < 1 - MPPT_ALERT:
            # แจ้งทุก MPPT ที่ต่ำกว่าเกณฑ์ ไม่ใช่แค่ตัวแย่สุด (#6 MPPT 5 ที่ 56% เคยถูกข้ามเพราะ MPPT 6 แย่กว่า)
            low = mt[(mt["sn"] == r["sn"]) & (mt["ratio"] < 1 - MPPT_ALERT)].sort_values("ratio")
            lst = ", ".join(f"MPPT {int(x.mppt)} {x.ratio*100:.0f}%" for x in low.itertuples())
            out.append({"level": "warning", "inv_no": r["inv_no"],
                        "text": f"{tag} พลังงานต่อสตริงต่ำกว่าค่าเฉลี่ยในเครื่อง (เกณฑ์ {100*(1-MPPT_ALERT):.0f}%): {lst} — "
                                "ตรวจฝุ่น เงาบัง สตริงขาด หรือฟิวส์ DC (ถ้ามีแจ้งเตือนแรงดัน DC ของ MPPT เดียวกัน "
                                "แปลว่าสตริงขาด/วงจรเปิด)"})
        if r["n_fault"] > 0:
            out.append({"level": "warning", "inv_no": r["inv_no"],
                        "text": f"{tag} มีเฟรมสถานะ Fault {r['n_fault']} ครั้ง — ดู event log ที่หน้าจออินเวอร์เตอร์"})
        if r["coverage_pct"] < COVERAGE_ALERT:
            out.append({"level": "info", "inv_no": r["inv_no"],
                        "text": f"{tag} ส่งข้อมูลเพียง {r['coverage_pct']:.0f}% ของเครื่องที่ครบที่สุด — "
                                "ปัญหา data logger/สายสัญญาณ ไม่ใช่ตัวเครื่อง (ตัวเลข DC จะต่ำกว่าจริง)"})

    sh = string_health(daily)
    if not sh.empty:
        for _, r in sh[sh["ratio"] < VDC_ALERT].sort_values("ratio").iterrows():
            out.append({"level": "error", "inv_no": r["inv_no"],
                        "text": f"#{r['inv_no']} MPPT {r['mppt']} แรงดัน DC กลางวัน {r['vdc_mid']:.0f} V "
                                f"ต่ำกว่า MPPT อื่นในเครื่อง ({r['vdc_others']:.0f} V) {100*(1-r['ratio']):.0f}% — "
                                "สตริงอาจขาด (connector/ฟิวส์/สายหลุด) ให้ช่างวัดแรงดันหน้างาน"})

    # ถูกจำกัดกำลังระดับระบบ (Zero-export วันโหลดต่ำ) — ข้อมูลประกอบ ไม่ใช่ความผิดปกติของเครื่อง
    # ไม่นับเครื่องที่ไม่จ่ายไฟทั้งวัน (แจ้งเป็น error ด้านบนแล้ว) — ไม่งั้นข้อความนี้จะบอกว่า "ไม่ใช่เครื่องเสีย"
    # ทั้งที่ 9 เครื่องหยุดไป 4 วัน (10–13 ต.ค. 69)
    not_zero = ~daily["zero_day"] if "zero_day" in daily.columns else pd.Series(True, index=daily.index)
    cur = daily[(daily["curtail_min"] >= 60) & not_zero].groupby("date")["sn"].nunique()
    cur = cur[cur >= N_INVERTERS // 2]
    if not cur.empty:
        lst = ", ".join(f"{fmt_d(d)} ({n} เครื่อง)" for d, n in cur.items())
        out.append({"level": "info", "inv_no": 0,
                    "text": f"ถูกจำกัดกำลังบางช่วง (Pac < {CURTAIL_PAC_KW:.0f} kW ขณะ Vdc > {CURTAIL_VDC:.0f} V) "
                            f"อย่างน้อย 1 ชม. ใน {len(cur)} วัน — {lst} · วันหยุดโรงงานคือ Zero-export ตอนโหลดต่ำ "
                            "(ไม่ใช่แดดหรือเครื่องเสีย) · ถ้าเป็นวันทำงานหรือเป็นวันเดียวกับที่มีเครื่องไม่จ่ายไฟ "
                            "ให้ดูว่าระบบควบคุมสั่งลดกำลังจากอะไร"})

    # พลังงานที่ผลิตช่วง logger เงียบข้ามวัน — มิเตอร์สะสมยืนยันว่าผลิตจริง แต่ระบุวันไม่ได้ จึงไม่อยู่ในยอดรายวัน
    sys_gap_days: set = set()
    if "gap_kwh" in daily.columns:
        gp = daily[daily["gap_kwh"] > 0]
        # วันที่เกือบทุกเครื่องเงียบพร้อมกัน = export รอบนั้นจบก่อนแดดหมด ไม่ใช่เครื่องหรือ logger เสีย
        # รวมเป็นรายการเดียว (เดิมขึ้นแยก 11 บรรทัด และทำให้นับว่า "ต้องตรวจ 11 เครื่อง" ผิด ๆ)
        cnt = gp.groupby("date")["sn"].nunique()
        sys_gap_days = set(cnt[cnt >= N_INVERTERS // 2].index)
        for d in sorted(sys_gap_days):
            g = gp[gp["date"] == d]
            med = g["gap_from"].median()
            # เครื่องที่เงียบไปก่อนเครื่องอื่นเกิน 1 ชม. = logger ของเครื่องนั้นหลุดเอง ไม่ใช่เพราะ export จบ
            # (#3 15/09 หยุดส่ง 12:31 ขณะเครื่องอื่นส่งถึง 15:40 — ขาดไป 107 kWh มากกว่าเครื่องอื่น 10 เท่า)
            early = g[g["gap_from"] < med - pd.Timedelta(hours=1)]
            note = ("" if early.empty else " · ยกเว้น " + ", ".join(
                f"#{int(x.inv_no)} ที่หยุดส่งตั้งแต่ {x.gap_from:%H:%M} ({x.gap_kwh:,.0f} kWh) — logger ของเครื่องนั้นหลุดเอง"
                for x in early.itertuples()))
            out.append({"level": "info", "inv_no": 0,
                        "text": f"{fmt_d(d)} ข้อมูลหยุดราว {med:%H:%M} พร้อมกันทุกเครื่อง "
                                f"(ดึง export ก่อนแดดหมด) — หลังจากนั้นผลิตต่ออีกรวม {g['gap_kwh'].sum():,.0f} kWh "
                                "(มิเตอร์สะสมยืนยัน) ซึ่งยังไม่อยู่ในยอดรายวัน และไม่นับวันนั้นในค่าเฉลี่ย · "
                                "ดึงรายงานวันนั้นซ้ำจาก EVE แล้วกดอัปเดตจะได้ยอดครบ" + note})
        for sn, g in gp[~gp["date"].isin(sys_gap_days)].groupby("sn"):
            no = int(g["inv_no"].iloc[0])
            spans = ", ".join(f"{r.gap_from:%d/%m %H:%M} → {r.gap_to:%d/%m %H:%M} ({r.gap_kwh:,.0f} kWh)"
                              for r in g.itertuples())
            out.append({"level": "warning", "inv_no": no,
                        "text": f"#{no} (SN {sn}) ผลิตได้ {g['gap_kwh'].sum():,.0f} kWh ในช่วงที่ logger ไม่ส่งข้อมูล "
                                f"(มิเตอร์สะสม Ecum ยืนยัน) แต่ระบุวันไม่ได้ จึงไม่อยู่ในยอดรายวัน — {spans}"})
    src = daily[daily.get("ac_src", pd.Series(dtype=str)) == "Ecum"] if "ac_src" in daily.columns else daily.iloc[0:0]
    for r in src.itertuples():
        out.append({"level": "info", "inv_no": int(r.inv_no),
                    "text": f"#{int(r.inv_no)} วันที่ {fmt_d(r.date)} มิเตอร์รายวัน (Eday) ส่งค่าผิด "
                            f"({r.ac_eday:,.0f} kWh) — ใช้ผลต่างมิเตอร์สะสม Ecum {r.ac_kwh:,.0f} kWh แทน"})

    # วันที่ข้อมูลขาดช่วงบ่าย (ไม่ใช่วันล่าสุด ซึ่งปกติยังไม่ครบเพราะเพิ่งดึง) — เติมได้ด้วยการดึงซ้ำ
    gaps = {d: t for d, t in partial_days(daily).items()
            if d != daily["date"].max() and d not in sys_gap_days}     # วันที่รวมไว้ในรายการด้านบนแล้ว
    if gaps:
        lst = ", ".join(f"{fmt_d(d)} (ถึง {t:%H:%M})" for d, t in gaps.items())
        out.append({"level": "info", "inv_no": 0,
                    "text": f"ข้อมูลไม่ครบวัน {len(gaps)} วัน — {lst} · ยอดวันนั้นต่ำกว่าจริงและไม่ถูกนับในค่าเฉลี่ย "
                            "เติมได้โดยดึงรายงานวันนั้นซ้ำจาก EVE แล้วกดอัปเดต (ระบบตัดข้อมูลซ้ำให้เอง)"})
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda a: (order[a["level"]], a["inv_no"]))


# ===========================================================================
# CLI — 4 ขั้นสำหรับปุ่ม อัปเดต Solar.bat
# ===========================================================================
LINE = "=" * 62
LOG_DIR = os.path.join(HERE, "logs")
LOG_KEEP = 30


def head(text: str) -> None:
    print("\n" + LINE + "\n  " + text + "\n" + LINE)


class _Tee:
    """เขียนทั้งลงจอและไฟล์ log — หน้าต่าง .bat ปิดแล้วข้อความหาย ต้องมีที่ให้ย้อนดู"""
    encoding = "utf-8"

    def __init__(self, path):
        self.console, self.f = sys.stdout, open(path, "a", encoding="utf-8")

    def write(self, s):
        self.console.write(s)
        self.f.write(s)
        self.f.flush()
        return len(s)

    def flush(self):
        self.console.flush()
        self.f.flush()


def _start_log() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, time.strftime("solar_%Y%m%d_%H%M%S.log"))
    sys.stdout = _Tee(path)
    sys.stderr = sys.stdout
    _prune_logs("solar")
    return path


def _prune_logs(prefix: str) -> None:
    """เก็บ log ของแต่ละช่องทางแยกกัน (solar_ = ไอคอน .bat · solar_web_ = ปุ่มในแดชบอร์ด)
    ไม่งั้นกดปุ่มในแดชบอร์ดบ่อย ๆ จะไล่ลบ log ของรอบที่รันจากไอคอนทิ้งหมด"""
    pat = re.compile(rf"{prefix}_\d{{8}}_\d{{6}}\.log")
    old = sorted(f for f in os.listdir(LOG_DIR) if pat.fullmatch(f))
    for f in old[:-LOG_KEEP]:
        try:
            os.remove(os.path.join(LOG_DIR, f))
        except OSError:
            pass


# ===========================================================================
# ขั้นตอนอัปเดตทั้งชุด — ปุ่ม อัปเดต Solar.bat และปุ่มในแดชบอร์ดเรียกฟังก์ชันเดียวกันนี้
# ===========================================================================
LOCK_PATH = os.path.join(HERE, "logs", "_solar_update.lock")


class UpdateBusy(RuntimeError):
    """มีการอัปเดตอีกรอบกำลังทำงานอยู่ (กดซ้ำ / กดทั้งไอคอนและปุ่มในแดชบอร์ดพร้อมกัน)"""


@contextlib.contextmanager
def update_lock():
    """กันสองรอบเขียน parquet ชนกัน — ไอคอนบนเดสก์ท็อปกับปุ่มในแดชบอร์ดอยู่คนละโปรเซส

    ใช้ล็อกของ Windows (msvcrt.locking) ไม่ใช่ "มีไฟล์ = ล็อก" เพราะถ้าผู้ใช้ปิดหน้าต่าง .bat
    กลางคัน ไฟล์ล็อกจะค้าง แล้วทั้งไอคอนและปุ่มในแดชบอร์ดจะปฏิเสธทุกคนไป 15 นาที
    (ทดสอบแล้ว 2 ต.ค. 69) — ล็อกของ OS ปลดเองทันทีที่โปรเซสตาย ไฟล์ไม่ต้องลบ
    ล็อกผูกกับ handle จึงกันสองเธรดในโปรเซสแดชบอร์ดเดียวกันได้ด้วย"""
    import msvcrt
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    fd = os.open(LOCK_PATH, os.O_RDWR | os.O_CREAT)
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    except OSError:
        os.close(fd)
        try:
            with open(LOCK_PATH + ".info", encoding="utf-8") as f:
                who = f.read().strip()
        except OSError:
            who = ""
        raise UpdateBusy("มีการอัปเดต Solar กำลังทำงานอยู่" + (f" ({who})" if who else "")
                         + " — รอให้เสร็จก่อนแล้วกดใหม่")
    try:
        try:
            with open(LOCK_PATH + ".info", "w", encoding="utf-8") as f:
                f.write(f"เริ่ม {time.strftime('%H:%M:%S')}")
        except OSError:
            pass
        yield
    finally:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        os.close(fd)


def run_update(rebuild: bool = False, check: bool = False, out=print) -> int:
    """ทำครบ 4 ขั้น แล้วคืนรหัสผล 0 = สำเร็จ · 1 = ผิดพลาด · 2 = ยังไม่มีข้อมูลในฐานเลย

    out คือฟังก์ชันรับข้อความทีละบรรทัด — .bat ส่ง print, แดชบอร์ดส่งตัวที่เขียนลงหน้าจอ
    """
    def head_(text):
        out("\n" + LINE + "\n  " + text + "\n" + LINE)

    try:
        raw = data_paths.solar_raw_dir()
    except data_paths.DataFolderNotFound as e:
        out(f"\n{e}")
        return 1
    out(f"  โฟลเดอร์ข้อมูลดิบ: {raw}")

    head_("ขั้น 1/4  ย้ายไฟล์ EVE จาก Downloads เข้าโฟลเดอร์ลงวันที่")
    p = prepare(dry_run=check)
    for d in p["moved"]:
        out(f"  ย้าย  {os.path.relpath(d, raw)}")
    for d in p["copies"]:
        out(f"  เก็บเป็นสำเนา {os.path.relpath(d, raw)}  (ชื่อซ้ำแต่เนื้อหาต่าง — ไม่ทับของเดิม)")
    for d in p["failed"]:
        out(f"  *** ย้ายไม่ได้ {d} — ปล่อยไว้ใน Downloads รอบหน้าจะลองใหม่")
    if p["duplicate"]:
        out(f"  ซ้ำกับที่มีอยู่แล้ว {p['duplicate']} ไฟล์ — ปล่อยไว้ใน Downloads")
    if not p["moved"] and not p["copies"]:
        out("  ไม่มีไฟล์ใหม่ใน Downloads — เดินต่อเผื่อมีไฟล์ในโฟลเดอร์ที่ยังไม่ได้อ่าน")

    head_("ขั้น 2/4  อ่านไฟล์ที่ยังไม่เคยอ่าน → solar_readings.parquet")
    try:
        s = ingest(rebuild=rebuild, dry_run=check, log=out)
    except Exception as e:
        out(f"\n  อ่านข้อมูลไม่สำเร็จ: {e}")
        return 1
    out(f"  ไฟล์ดิบทั้งหมด {s['files_total']} ไฟล์ · ต้องอ่านรอบนี้ {s['files_new']} ไฟล์")
    if check:
        for r in s.get("todo", []):
            out(f"    - {r}")
        out("\n  (โหมดตรวจ จบแค่นี้)")
        return 0
    for e in s["errors"]:
        out(f"  *** {e}")
    added = s["rows_after"] - s["rows_before"]
    out(f"  แถวในฐาน {s['rows_before']:,} → {s['rows_after']:,}  (เพิ่ม {added:,} แถว)")
    if s["files_new"] == 0:
        out("\n  *** ไม่มีไฟล์ใหม่เลย — ถ้าเพิ่งดึงจาก EVE ให้ตรวจว่าไฟล์ลง Downloads จริง"
            " และชื่อไฟล์ขึ้นต้นด้วย อินเวอร์เตอร์<SN>-รายการละเอียดแต่ละรายการ- ***")

    head_("ขั้น 3/4  สรุปรายวัน (ราย inverter / ราย MPPT) + โปรไฟล์ 15 นาที")
    rd_path = os.path.join(data_paths.solar_parquet_dir(), READINGS)
    if not os.path.exists(rd_path):
        out("  ยังไม่มีข้อมูลในฐานเลย — วางไฟล์ EVE แล้วรันใหม่")
        return 2
    t0 = time.time()
    df = pd.read_parquet(rd_path)
    daily, prof = summarize(df)
    write_summaries(daily, prof)
    out(f"  รายวัน {len(daily):,} แถว (เครื่อง×วัน) · โปรไฟล์ {len(prof):,} แถว"
        f" · ใช้เวลา {time.time() - t0:.0f} วินาที")

    head_("ขั้น 4/4  ผลล่าสุด")
    last = daily["date"].max()
    span = (daily["date"].max() - daily["date"].min()).days + 1
    newest = df["ts"].max()
    out(f"  ข้อมูลตั้งแต่ {daily['date'].min():%d/%m/%Y} ถึง {last:%d/%m/%Y}  ({span} วัน)"
        f"  ล่าสุด {newest:%d/%m/%Y %H:%M}")
    # วันล่าสุดที่ "ควรมีข้อมูลครบแล้ว": ก่อน 19:00 คือเมื่อวาน (วันนี้ยังผลิตไม่จบ) หลังจากนั้นคือวันนี้
    # ผู้ใช้กดตอนเช้าทุกวัน ถ้าเทียบกับวันนี้ตรง ๆ จะขึ้นเตือน "ขาด 1 วัน" ทุกเช้าทั้งที่ข้อมูลครบแล้ว
    now = dt.datetime.now()
    expect = now.date() if now.hour >= 19 else now.date() - dt.timedelta(days=1)
    gap_days = (expect - newest.date()).days
    if gap_days >= 1:
        out(f"\n  *** ข้อมูลล่าสุดถึง {newest:%d/%m/%Y} — ยังขาดถึง {expect:%d/%m/%Y} อีก {gap_days} วัน ***\n"
            "      ตอนดึงรายงานในเว็บ EVE ให้เลือกช่วงวันที่ให้ถึงวันล่าสุด"
            " (ไฟล์ที่ได้มีข้อมูลเฉพาะช่วงวันที่ที่เลือกไว้)")
    else:
        out(f"  ข้อมูลครบถึง {newest:%d/%m/%Y} แล้ว (ล่าสุดที่เป็นไปได้ ณ ตอนนี้)")
    ld = daily[daily["date"] == last].sort_values("inv_no")
    out(f"\n  ผลผลิตวัน {last:%d/%m/%Y}  รวม {ld['ac_kwh'].sum():,.0f} kWh"
        f"  (เป้า MIN {TARGET_KWH_DAY['MIN (PSH 4.0)']:,.0f} · MAX {TARGET_KWH_DAY['MAX (PSH 4.5)']:,.0f})")
    pl = partial_last_day(daily)
    if pl is not None:
        out(f"  (วันนี้ยังไม่ครบวัน — ข้อมูลถึง {pl:%H:%M} น. แดชบอร์ดจะไม่นับวันนี้ในค่าเฉลี่ย/เป้า"
            " ดึง export ใหม่หลัง 18:30 แล้วกดอัปเดตอีกครั้งจะได้ยอดเต็มวัน)")
    if len(ld) < N_INVERTERS:
        lack = sorted(set(INVERTER_NO) - set(ld["sn"]), key=INVERTER_NO.get)
        out(f"  *** วันนี้มีข้อมูลแค่ {len(ld)} จาก {N_INVERTERS} เครื่อง — ขาด "
            + ", ".join(f"#{INVERTER_NO[s]} ({s})" for s in lack) + " ***")
    for r in ld.itertuples():
        flag = ""
        if getattr(r, "zero_day", False):
            flag += "  <<< ออนไลน์แต่ไม่จ่ายไฟทั้งวัน"
        if getattr(r, "static_min", 0) >= STATIC_NODE_MIN:
            flag += f"  ไม่ได้รับค่ามิเตอร์ {int(r.static_min)} นาที"
        if r.outage_min > 0:
            flag += f"  หยุดกลางวัน {r.outage_min} นาที"
        if r.n_fault > 0:
            flag += f"  fault {r.n_fault} เฟรม"
        out(f"    #{int(r.inv_no):>2}  SN {r.sn}  {r.ac_kwh:>7,.0f} kWh  สูงสุด {r.pac_max:>5.0f} kW"
            f"  ข้อมูล {r.coverage_pct:>3.0f}%{flag}")
    nz = ld[ld["zero_day"]] if "zero_day" in ld.columns else ld.iloc[0:0]
    if not nz.empty:
        out(f"  *** {len(nz)} เครื่องออนไลน์แต่ไม่จ่ายไฟทั้งวัน ({', '.join('#' + str(int(x)) for x in nz['inv_no'])}) "
            "— ไม่ใช่ข้อมูลขาด ตรวจระบบจำกัดกำลัง/การตั้งค่าในเว็บ EVE และหน้าจอเครื่อง (รายละเอียดด้านล่าง) ***")
    al = alerts(daily[daily["date"] >= last - pd.Timedelta(days=6)])
    if al:
        out(f"\n  สิ่งที่ต้องตรวจ (7 วันล่าสุด) {len(al)} รายการ:")
        for x in al:
            out(f"    [{x['level']}] {x['text']}")
    else:
        out("\n  7 วันล่าสุดไม่พบความผิดปกติ")
    out("\n  แดชบอร์ดพอร์ต 8504 แท็บ Solar Monitor จะเห็นข้อมูลใหม่ภายใน ~30 วินาที")
    return 0


class FileLog:
    """เขียนบรรทัดลงไฟล์ log ใน logs\\ — ใช้กับปุ่มในแดชบอร์ด (หน้าเว็บปิดแล้วยังย้อนดูได้)"""

    def __init__(self, prefix: str = "solar_web"):
        os.makedirs(LOG_DIR, exist_ok=True)
        self.path = os.path.join(LOG_DIR, time.strftime(f"{prefix}_%Y%m%d_%H%M%S.log"))
        self._f = open(self.path, "a", encoding="utf-8")
        _prune_logs(prefix)

    def __call__(self, s: str = "") -> None:
        self._f.write(s + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="อัปเดตข้อมูล Solar Inverter จาก EVE export")
    ap.add_argument("--check", action="store_true", help="ดูว่าจะทำอะไร ไม่เขียนไฟล์")
    ap.add_argument("--rebuild", action="store_true", help="อ่านไฟล์ดิบใหม่ทั้งหมด")
    a = ap.parse_args(argv)

    log_path = None if a.check else _start_log()
    head("อัปเดตข้อมูล Solar Inverter (EVE → แดชบอร์ด 8504)")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}"
          + (f"  บันทึกผลรอบนี้ไว้ที่ {log_path}" if log_path else "  (โหมดตรวจ ไม่เขียนไฟล์)"))
    if a.check:
        return run_update(rebuild=a.rebuild, check=True)
    try:
        with update_lock():
            code = run_update(rebuild=a.rebuild)
    except UpdateBusy as e:
        print(f"\n  *** {e}")
        return 1
    if log_path:
        print(f"  ผลทั้งหมดของรอบนี้อยู่ใน  {log_path}")
    return code


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        print("\n\n  ยกเลิกโดยผู้ใช้")
        code = 1
    except Exception:                       # ห้ามให้หน้าต่าง .bat ปิดหายไปโดยไม่เหลือข้อความ
        import traceback
        print("\n  *** อัปเดตไม่สำเร็จ — ข้อความด้านล่างนี้ส่งให้คนดูแลระบบได้เลย ***\n")
        traceback.print_exc()
        code = 1
    if sys.stdin.isatty() and "--check" not in sys.argv:
        print()
        try:
            input("  กด Enter เพื่อปิดหน้าต่าง ")
        except EOFError:
            pass
    sys.exit(code)
