# -*- coding: utf-8 -*-
"""ตรวจสุขภาพระบบแดชบอร์ด — ตอบคำถามเดียวว่า "ตอนนี้เชื่อตัวเลขบนจอได้ไหม"

ทำไมต้องมีไฟล์นี้ ทั้งที่มี data_paths.py อยู่แล้ว
    data_paths.health() ดูแค่ว่า "ไฟล์ยังอยู่ไหม" กับเวลาแก้ไขไฟล์ (mtime)
    ซึ่งมองไม่เห็นความพังที่เกิดขึ้นจริงสองแบบ
      - ไฟล์อยู่ครบ เปิดได้ แต่ข้อมูลข้างในหยุดอยู่เมื่อ 15 วันก่อน
      - มีสคริปต์ไปเปิดแล้วเซฟใหม่โดยไม่เพิ่มแถว mtime เด้งเป็นวันนี้
        ทั้งที่ไม่มีข้อมูลใหม่เลย ทำให้ตัวตรวจแบบ mtime บอกว่า "สด"
    (เกิดจริง 17 ก.ย. 2569 data_paths.py รายงาน "ครบทุกชุด" ตอนที่ฐาน
     ใบแจ้งซ่อมเก่า 5-15 วัน และระบบที่เขียนมันพังอยู่)

    ไฟล์นี้จึงอ่าน "วันที่ของข้อมูลข้างใน" ไม่ใช่วันที่ของไฟล์

เหตุการณ์ที่ไฟล์นี้มีไว้กันไม่ให้เกิดซ้ำ (18 ก.ย. 2569)
    กดไอคอนอัปเดต หน้าจอขึ้น "เสร็จเรียบร้อย" แต่เข้าฐาน 0 แถว
    และแดชบอร์ดล่มไป 7 จาก 9 ตัว โดยไม่มีอะไรบอกเลยทั้งสองเรื่อง
    รู้ตัวก็ต่อเมื่อบังเอิญเห็นว่าวันที่บนจอมันเก่า

รัน
    python ตรวจสุขภาพระบบ.py          ตรวจเต็ม
    python ตรวจสุขภาพระบบ.py --สั้น    เอาเฉพาะสรุป (etl_run.py เรียกแบบนี้)

รหัสผลลัพธ์
    0 = ปกติ   1 = ต้องดู   2 = ต้องแก้ทันที
"""

import datetime as dt
import glob
import os
import socket
import sys

DEPT = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา"
)
HERE = os.path.dirname(os.path.abspath(__file__))
PORTS = range(8503, 8512)

# โรงงานเดินเครื่องทั้ง 7 วัน รวมอาทิตย์ (ดูจากข้อมูล 90 วันหลังสุด
# วันอาทิตย์มีราว 837 แถว วันอื่น 1,500-2,000 แถว) จึงไม่มีวันหยุดให้ยกเว้น
# ข้อมูลต้องสดทุกวัน ถ้าเก่ากว่านี้แปลว่ามีอะไรผิด
#
# ปกติข้อมูลจะช้ากว่าวันนี้ 1 วัน เพราะดึง export ตอนเช้า
# ซึ่งได้ข้อมูลถึงสิ้นวันก่อนหน้า
สด_ปกติ = 1        # ช้าได้ถึง 1 วัน = ปกติ
สด_ต้องดู = 2      # 2 วัน = เริ่มผิดปกติ
                   # เกินนั้น = ต้องแก้ทันที

ผล = []            # (ระดับ, หัวข้อ, รายละเอียด)  ระดับ 0=ปกติ 1=ต้องดู 2=ต้องแก้


def บันทึก(ระดับ, หัวข้อ, รายละเอียด):
    ผล.append((ระดับ, หัวข้อ, รายละเอียด))


def อายุวัน(วันที่):
    if วันที่ is None:
        return None
    return (dt.date.today() - วันที่).days


def ระดับจากอายุ(อายุ):
    if อายุ is None:
        return 2
    if อายุ <= สด_ปกติ:
        return 0
    if อายุ <= สด_ต้องดู:
        return 1
    return 2


# ---------------------------------------------------------------------------
# 1. ความสดของข้อมูล — อ่านวันที่ในข้อมูล ไม่ใช่ mtime ของไฟล์
# ---------------------------------------------------------------------------
def ตรวจความสด():
    import pandas as pd

    def วันล่าสุด(ซีรีส์):
        d = pd.to_datetime(ซีรีส์, errors="coerce").dropna()
        return d.max().date() if len(d) else None

    รายการ = []

    # Workcenter — อ่านจาก parquet เพราะเร็วกว่า Excel 80 MB มาก
    pq = os.path.join(DEPT, "00_ETL_Pipeline", "parquet", "workcenter_data.parquet")
    if os.path.exists(pq):
        df = pd.read_parquet(pq)
        รายการ.append(("Workcenter (ใบงาน)", วันล่าสุด(df["วันที่"]), len(df)))
    else:
        รายการ.append(("Workcenter (ใบงาน)", None, 0))

    # MTBF — ข้อมูลจริงอยู่ 3 ชีต ใช้ชีตที่ใหม่ที่สุดเป็นตัวแทน
    mt = os.path.join(DEPT, r"2.เรื่องMTBF-MTTR\รายละเอียด"
                            r"\MTBF-MTTR_ฐานข้อมูลหลัก_2569.xlsx")
    if os.path.exists(mt):
        x = pd.ExcelFile(mt, engine="calamine")
        ใหม่สุด, แถว = None, 0
        for sh in ("Breakdown_B000000001", "Maintenance_BP00000001",
                   "P000000001_รายละเอียด"):
            if sh in x.sheet_names:
                t = x.parse(sh)
                แถว += len(t)
                v = วันล่าสุด(t["Start"]) if "Start" in t.columns else None
                if v and (ใหม่สุด is None or v > ใหม่สุด):
                    ใหม่สุด = v
        รายการ.append(("MTBF-MTTR (การหยุดเครื่อง)", ใหม่สุด, แถว))
    else:
        รายการ.append(("MTBF-MTTR (การหยุดเครื่อง)", None, 0))

    # OEE
    oee = os.path.join(DEPT, r"3.เรื่องOverall Equipment Effectiveness"
                             r"\OEE_ฐานข้อมูลหลัก_2569.xlsx")
    if os.path.exists(oee):
        t = pd.read_excel(oee, sheet_name="Report1", engine="calamine")
        รายการ.append(("OEE", วันล่าสุด(t["Trans_date"]), len(t)))
    else:
        รายการ.append(("OEE", None, 0))

    # ใบแจ้งซ่อม 6 หมวด — ระบบที่เขียนไฟล์พวกนี้เคยพังเงียบมาแล้ว
    try:
        sys.path.insert(0, HERE)
        import data_paths
        rd = data_paths.repair_dir()
    except Exception:
        rd = None
    if rd:
        for f in sorted(glob.glob(os.path.join(rd, "รายงานซ่อมบำรุง_*.xlsx"))):
            ชื่อ = os.path.basename(f)[15:-14].strip("_")
            try:
                t = pd.read_excel(f, sheet_name="ข้อมูล", engine="calamine")
                รายการ.append(("ใบแจ้งซ่อม: " + ชื่อ, วันล่าสุด(t["วันที่แจ้งซ่อม"]), len(t)))
            except Exception as e:
                รายการ.append(("ใบแจ้งซ่อม: " + ชื่อ, None, 0))

    # แยกรายงานสองกลุ่ม เพราะคนละระบบเขียน คนละสาเหตุเวลาพัง
    # ถ้ารวมกัน ใบแจ้งซ่อมที่พังค้างอยู่จะกลบไม่ให้เห็นว่าฐานหลักปกติดี
    def สรุปกลุ่ม(หัวข้อ, ชุด, แก้ไขยังไง=None):
        if not ชุด:
            return 0
        บรรทัด, แย่สุด = [], 0
        for ชื่อ, วัน, แถว in ชุด:
            อายุ = อายุวัน(วัน)
            ลv = ระดับจากอายุ(อายุ)
            แย่สุด = max(แย่สุด, ลv)
            หมาย = {0: "สด", 1: "เริ่มเก่า", 2: "เก่าเกินไป"}[ลv]
            บรรทัด.append("  %-28s %s  %-18s %s แถว" % (
                ชื่อ[:28],
                วัน.strftime("%Y-%m-%d") if วัน else "  ไม่มีข้อมูล ",
                "(%d วัน %s)" % (อายุ, หมาย) if อายุ is not None else "(อ่านไม่ได้)",
                "{:,}".format(แถว)))
        if แย่สุด and แก้ไขยังไง:
            บรรทัด.append("      " + แก้ไขยังไง)
        บันทึก(แย่สุด, หัวข้อ, "\n".join(บรรทัด))
        return แย่สุด

    หลัก = [r for r in รายการ if not r[0].startswith("ใบแจ้งซ่อม")]
    ซ่อม = [r for r in รายการ if r[0].startswith("ใบแจ้งซ่อม")]
    สรุปกลุ่ม("ความสดของฐานหลัก", หลัก,
             "แก้: ดึง export ที่ขาดจาก MOS แล้วกดไอคอน  อัปเดตข้อมูล MOS")
    สรุปกลุ่ม("ความสดของใบแจ้งซ่อม", ซ่อม,
             "แก้: ดึง export ใบแจ้งซ่อมรอบใหม่จาก MOS ให้ครบ 6 หมวด วางในโฟลเดอร์วันที่\n"
             "      แล้วกด 1-ตรวจก่อน-ใบแจ้งซ่อม.bat ตามด้วย 2-เขียนเข้าฐาน-ใบแจ้งซ่อม.bat")
    return รายการ


# ---------------------------------------------------------------------------
# 2. แดชบอร์ด — เปิดอยู่ครบไหม มีพอร์ตซ้ำไหม
# ---------------------------------------------------------------------------
def ตรวจแดชบอร์ด():
    ล่ม = []
    for p in PORTS:
        s = socket.socket()
        s.settimeout(2)
        if s.connect_ex(("127.0.0.1", p)) != 0:
            ล่ม.append(p)
        s.close()

    ซ้ำ = []
    try:
        import subprocess
        r = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                           capture_output=True, text=True, timeout=30)
        # นับ "จำนวนโปรเซสที่ต่างกัน" ต่อพอร์ต ไม่ใช่จำนวนบรรทัด
        #
        # ของเดิมนับบรรทัดแล้วถือว่าเกิน 2 = ซ้ำ โดยคิดว่าโปรเซสเดียวจะขึ้น 2 บรรทัด
        # (IPv4 + IPv6) เสมอ ซึ่งไม่จริง streamlit บางครั้งจับแค่ IPv4 บรรทัดเดียว
        # 23 ก.ย. 2569 พอร์ต 8507 มี 2 โปรเซสจริงแต่ขึ้นแค่ 2 บรรทัด ตัวตรวจจึงบอก
        # "ไม่มีพอร์ตซ้ำ" ทั้งที่ซ้ำอยู่ — นับ PID แทนจะถูกไม่ว่าจับกี่ stack
        pid_ของพอร์ต = {}
        for ln in r.stdout.splitlines():
            if "LISTENING" not in ln:
                continue
            ส่วน = ln.split()
            if len(ส่วน) < 5:
                continue
            pid = ส่วน[-1]
            for p in PORTS:
                if ส่วน[1].endswith(":%d" % p):
                    pid_ของพอร์ต.setdefault(p, set()).add(pid)
        ซ้ำ = [p for p, s in pid_ของพอร์ต.items() if len(s) > 1]
    except Exception:
        pass

    if ล่ม:
        บันทึก(2, "แดชบอร์ด",
               "  ล่ม %d จาก 9 ตัว : พอร์ต %s\n"
               "  แก้: ดับเบิลคลิก  เปิดระบบทั้งหมด_เบื้องหลัง.vbs\n"
               "       (กดซ้ำได้ ตัวที่เปิดอยู่แล้วจะไม่ถูกแตะ)"
               % (len(ล่ม), ", ".join(str(p) for p in ล่ม)))
    elif ซ้ำ:
        บันทึก(1, "แดชบอร์ด",
               "  ขึ้นครบ 9 ตัว แต่พอร์ต %s มีตัวซ้ำ\n"
               "  ตัวที่เปิดทีหลังจะยึดพอร์ตไว้เฉย ๆ ไม่รับงาน"
               % ", ".join(str(p) for p in ซ้ำ))
    else:
        บันทึก(0, "แดชบอร์ด", "  ขึ้นครบ 9 ตัว (8503-8511) ไม่มีพอร์ตซ้ำ")
    return ล่ม


# ---------------------------------------------------------------------------
# 3. ข้อมูลซ้ำ — แถวซ้ำทำให้ยอดรวมของวันนั้นพองเป็นสองเท่า
# ---------------------------------------------------------------------------
def ตรวจซ้ำ():
    import pandas as pd
    บรรทัด, แย่ = [], 0

    pq = os.path.join(DEPT, "00_ETL_Pipeline", "parquet", "oee_report1.parquet")
    if os.path.exists(pq):
        t = pd.read_parquet(pq)
        d = pd.to_datetime(t["Trans_date"], errors="coerce").dt.date
        n = t.assign(_d=d).duplicated(subset=["MC", "_d"]).sum()
        แย่ = max(แย่, 1 if n else 0)
        บรรทัด.append("  OEE (เครื่อง+วัน)          ซ้ำ %d แถว" % n)

    pq = os.path.join(DEPT, "00_ETL_Pipeline", "parquet", "workcenter_data.parquet")
    if os.path.exists(pq):
        t = pd.read_parquet(pq)
        # ต้องใช้คีย์ชุดเดียวกับที่ ETL ใช้ตัดซ้ำ (update_mos.py:662)
        # เครื่องหนึ่งทำงานหลายรอบในวันเดียวได้ปกติ คีย์ที่มีแค่ เครื่อง+วัน
        # จะนับงานปกติเป็นของซ้ำ (ลองแล้วได้ 28,454 แถว ทั้งที่ของจริงมี 15)
        คีย์ = ["Machine", "Job", "Start", "End"]
        if all(c in t.columns for c in คีย์):
            n = t.duplicated(subset=คีย์).sum()
            # 15 แถวที่ 2026-09-02 เป็นของเดิมติดมาจากฐานตั้งต้น ไม่ใช่ของใหม่
            แย่ = max(แย่, 1 if n > 20 else 0)
            บรรทัด.append("  Workcenter (เครื่อง+Job+เวลา)  ซ้ำ %d แถว%s"
                          % (n, "  (15 แถวเดิมที่ 2 ก.ย. ทราบแล้ว)" if n <= 20 else ""))
    บันทึก(แย่, "ข้อมูลซ้ำ", "\n".join(บรรทัด) or "  ตรวจไม่ได้")


# ---------------------------------------------------------------------------
# 4. ไฟล์ดิบค้าง — ย้ายเข้าโฟลเดอร์แล้วแต่ไม่เคยถูกโหลดเข้าฐาน
# ---------------------------------------------------------------------------
def ตรวจไฟล์ค้าง(วันฐาน):
    บรรทัด, แย่ = [], 0

    raw = os.path.join(DEPT, "00_ข้อมูลดิบ_MOS")
    วันดิบ = None
    if os.path.isdir(raw):
        ชื่อ = sorted(d for d in os.listdir(raw) if os.path.isdir(os.path.join(raw, d)))
        if ชื่อ:
            ล่าสุด = ชื่อ[-1]
            try:
                ปี, ด, ว = (int(x) for x in ล่าสุด.split("-"))
                วันดิบ = dt.date(ปี - 543, ด, ว)
            except Exception:
                pass
            n = len(glob.glob(os.path.join(raw, ล่าสุด, "*.xls*")))
            บรรทัด.append("  โฟลเดอร์ดิบล่าสุด : %s (%d ไฟล์)" % (ล่าสุด, n))

    # export ที่ดึงวันนี้ จะมีข้อมูลถึงสิ้นวันก่อนหน้า ฐานจึงควรตามมาไม่เกิน 1 วัน
    if วันดิบ and วันฐาน and (วันดิบ - วันฐาน).days > สด_ปกติ + 1:
        แย่ = 2
        บรรทัด.append("  [!] ไฟล์ดิบถึง %s แต่ฐานมีข้อมูลถึงแค่ %s"
                      % (วันดิบ, วันฐาน))
        บรรทัด.append("      แปลว่าไฟล์ถูกย้ายเข้าโฟลเดอร์แล้วแต่ไม่ได้โหลดเข้าฐาน")
        บรรทัด.append("      แก้: กดไอคอน  อัปเดตข้อมูล MOS  อีกครั้ง แล้วรอจนจบ")

    # ไฟล์ที่ดึงมาวันนี้ — ตรวจว่าดึง "ถูกชนิด" ด้วย ไม่ใช่แค่ว่ามีไฟล์
    #
    # MOS มีรายงานหลายตัวที่ชื่อขึ้นต้นเหมือนกัน ระบบใช้แค่สองตัวนี้
    #   r-jobtran-mc   ใบงานรายเครื่อง -> Workcenter + MTBF  (ขาดไม่ได้)
    #   r-jobtran-oee  -> ชีต Report1 ของไฟล์ OEE
    # ตัวอื่นเช่น r-jobtran-wc (สรุปรายเครื่อง 54 แถว) ไม่มีสคริปต์ไหนใช้
    # ดึงมาก็ไม่เกิดอะไรขึ้น แต่คนดึงจะนึกว่าครบแล้ว
    # (เกิดจริง 18 ก.ย. 2569 ดึง mc + wc มา ขาด oee ตัวเลข OEE เลยค้างอยู่วันก่อน)
    ต้องมี = {"r-jobtran-mc": "ใบงานรายเครื่อง", "r-jobtran-oee": "OEE"}
    dl = os.path.join(os.path.expanduser("~"), "Downloads")
    วันนี้ = dt.date.today().strftime("%y%m%d")
    ของวันนี้ = [os.path.basename(f)
                for f in glob.glob(os.path.join(dl, "r-jobtran-*.xls*"))
                if ("_" + วันนี้) in os.path.basename(f)]

    # ไฟล์ที่ย้ายเข้าโฟลเดอร์ของวันนี้ไปแล้ว ถือว่า "ดึงมาแล้ว" เหมือนกัน
    # ไม่งั้นจะฟ้องว่าขาด ทั้งที่ย้ายเข้าไปเรียบร้อยตั้งแต่รอบเช้า
    พศวันนี้ = "%d-%02d-%02d" % (dt.date.today().year + 543,
                                 dt.date.today().month, dt.date.today().day)
    ย้ายแล้ว = [os.path.basename(f)
               for f in glob.glob(os.path.join(raw, พศวันนี้, "*.xls*"))]

    ดึงมาแล้ว = ของวันนี้ + ย้ายแล้ว
    if ดึงมาแล้ว:
        มี = {k for k in ต้องมี if any(n.startswith(k) for n in ดึงมาแล้ว)}
        ขาด = [v for k, v in ต้องมี.items() if k not in มี]

        if ของวันนี้:
            แย่ = max(แย่, 1)
            บรรทัด.append("  [!] มีไฟล์ของวันนี้ค้างใน Downloads %d ไฟล์ ยังไม่ได้ย้าย"
                          % len(ของวันนี้))
            for n in ของวันนี้:
                ใช้ = any(n.startswith(k) for k in ต้องมี)
                บรรทัด.append("      %s %s" % ("ใช้ได้ :" if ใช้ else "ไม่ใช้:", n))
            if any(not any(n.startswith(k) for k in ต้องมี) for n in ของวันนี้):
                บรรทัด.append("      (ไฟล์ 'ไม่ใช้' ไม่มีสคริปต์ไหนอ่าน ดึงมาก็ไม่มีผล)")
        if ย้ายแล้ว:
            บรรทัด.append("  ย้ายเข้าโฟลเดอร์ %s แล้ว %d ไฟล์" % (พศวันนี้, len(ย้ายแล้ว)))
        if ขาด:
            แย่ = max(แย่, 1)
            บรรทัด.append("  [!] วันนี้ยังไม่ได้ดึง: %s" % ", ".join(ขาด))
            บรรทัด.append("      ตัวเลขส่วนนั้นจะยังเป็นของรอบก่อนจนกว่าจะดึงมา")
        if ของวันนี้:
            บรรทัด.append("      แก้: กดไอคอน  อัปเดตข้อมูล MOS")

    บันทึก(แย่, "ไฟล์ดิบ", "\n".join(บรรทัด) or "  ไม่มีไฟล์ค้าง")


# ---------------------------------------------------------------------------
# 5. parquet ตรงกับ Excel ไหม — แดชบอร์ดอ่าน parquet ถ้าเพี้ยนจะไม่มีใครรู้
# ---------------------------------------------------------------------------
def ตรวจparquet():
    import pandas as pd
    บรรทัด, แย่ = [], 0

    คู่ = [
        ("OEE", os.path.join(DEPT, "00_ETL_Pipeline", "parquet", "oee_report1.parquet"),
         os.path.join(DEPT, r"3.เรื่องOverall Equipment Effectiveness"
                            r"\OEE_ฐานข้อมูลหลัก_2569.xlsx"), "Report1"),
    ]
    for ชื่อ, pq, xl, sheet in คู่:
        if not (os.path.exists(pq) and os.path.exists(xl)):
            continue
        if os.path.getmtime(pq) < os.path.getmtime(xl) - 60:
            แย่ = max(แย่, 1)
            บรรทัด.append("  [!] %s : parquet เก่ากว่า Excel — แดชบอร์ดเห็นตัวเลขรอบก่อน" % ชื่อ)
            บรรทัด.append("      แก้: python etl_recalc_excel.py")
        else:
            a = len(pd.read_parquet(pq))
            b = len(pd.read_excel(xl, sheet_name=sheet, engine="calamine"))
            if a != b:
                แย่ = max(แย่, 1)
                บรรทัด.append("  [!] %s : parquet %d แถว แต่ Excel %d แถว" % (ชื่อ, a, b))
            else:
                บรรทัด.append("  %-6s parquet ตรงกับ Excel (%s แถว)" % (ชื่อ, "{:,}".format(a)))

    # ช่องสูตรที่ต้องมีค่า ถ้าว่างแปลว่า Excel ยังไม่ได้คำนวณก่อนเซฟ
    xl = os.path.join(DEPT, r"3.เรื่องOverall Equipment Effectiveness"
                            r"\OEE_ฐานข้อมูลหลัก_2569.xlsx")
    if os.path.exists(xl):
        t = pd.read_excel(xl, sheet_name="Report1", engine="calamine")
        if "หมวดหมู่เครื่อง" in t.columns:
            d = pd.to_datetime(t["Trans_date"], errors="coerce")
            ล่าสุด = t[d.dt.date == d.max().date()]
            ว่าง = ล่าสุด["หมวดหมู่เครื่อง"].isna().sum()
            if ว่าง:
                แย่ = max(แย่, 2)
                บรรทัด.append("  [!] ช่องสูตร 'หมวดหมู่เครื่อง' ว่าง %d จาก %d แถวของวันล่าสุด"
                              % (ว่าง, len(ล่าสุด)))
                บรรทัด.append("      แก้: python etl_recalc_excel.py")
            else:
                บรรทัด.append("  ช่องสูตรของวันล่าสุดมีค่าครบ %d แถว" % len(ล่าสุด))

    บันทึก(แย่, "parquet กับสูตร Excel", "\n".join(บรรทัด) or "  ตรวจไม่ได้")


# ---------------------------------------------------------------------------
def main() -> int:
    สั้น = "--สั้น" in sys.argv or "--short" in sys.argv
    เริ่ม = dt.datetime.now()

    if not สั้น:
        print("=" * 70)
        print("  ตรวจสุขภาพระบบแดชบอร์ด   %s" % เริ่ม.strftime("%Y-%m-%d %H:%M"))
        print("=" * 70)

    if not os.path.isdir(DEPT):
        print("\n  [!!] เข้าโฟลเดอร์ฝ่ายไม่ได้ — OneDrive อาจยังไม่ซิงก์")
        print("       %s" % DEPT)
        return 2

    รายการ = ตรวจความสด()
    วันฐาน = รายการ[0][1] if รายการ else None
    ตรวจแดชบอร์ด()
    ตรวจซ้ำ()
    ตรวจไฟล์ค้าง(วันฐาน)
    ตรวจparquet()

    if not สั้น:
        for ระดับ, หัวข้อ, ราย in ผล:
            ธง = {0: "[ ปกติ ]", 1: "[ ต้องดู ]", 2: "[ ต้องแก้ ]"}[ระดับ]
            print("\n%s %s" % (ธง, หัวข้อ))
            print(ราย)

    แย่สุด = max((r for r, _, _ in ผล), default=0)
    เสีย = [h for r, h, _ in ผล if r == 2]
    ดู = [h for r, h, _ in ผล if r == 1]

    print("\n" + "=" * 70)
    if แย่สุด == 0:
        print("  ระบบปกติ — เชื่อตัวเลขบนแดชบอร์ดได้")
    elif แย่สุด == 1:
        print("  ใช้งานได้ แต่มีเรื่องต้องดู : %s" % ", ".join(ดู))
    else:
        print("  ต้องแก้ก่อนใช้ตัวเลข : %s" % ", ".join(เสีย))
        if ดู:
            print("  และมีเรื่องต้องดูอีก : %s" % ", ".join(ดู))
    print("  (ใช้เวลาตรวจ %.0f วินาที)" % (dt.datetime.now() - เริ่ม).total_seconds())
    print("=" * 70)
    return แย่สุด


if __name__ == "__main__":
    sys.exit(main())
