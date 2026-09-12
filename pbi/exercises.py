"""แบบฝึกหัด DAX และ Power Query พร้อมระบบตรวจอัตโนมัติ
==========================================================

วิธีตรวจคำตอบ DAX
-----------------
ไม่ได้เทียบ "ข้อความของสูตร" (ซึ่งจะบังคับให้เขียนเหมือนเฉลยเป๊ะ ๆ)
แต่รันทั้งสูตรของผู้เรียนและสูตรเฉลยบนโมเดลเดียวกัน **ภายใต้ filter context หลายชุด**
แล้วเทียบผลลัพธ์ทีละชุด

การทดสอบหลายบริบทสำคัญมาก เพราะสูตรที่เขียน CALCULATE หรือ ALL ผิด
มักให้ค่าถูกตอนไม่มีตัวกรอง แต่ผิดทันทีเมื่อมีตัวกรอง — วิธีนี้จับได้
"""

from __future__ import annotations

import math

from pbi.dax_engine import DaxError, evaluate

# บริบทมาตรฐานที่ใช้ตรวจ — เลือกให้ครอบคลุมทั้งกรองมิติ กรองเวลา และกรองซ้อน
DEFAULT_CONTEXTS: list[tuple[str, dict]] = [
    ("ไม่กรองอะไรเลย", {}),
    ("กรองสาย Line A", {"Machine[Line]": ["Line A"]}),
    ("กรองเครื่อง M03 กะเช้า", {"Machine[MachineID]": ["M03"], "Shift[ShiftID]": ["S1"]}),
    ("กรองหมวดสินค้า ตู้", {"Product[Category]": ["ตู้"]}),
    ("กรอง มี.ค. 2026", {"Date[Year]": [2026], "Date[MonthNo]": [3]}),
]

# บริบทสำหรับข้อที่เกี่ยวกับเวลา — ต้องมีตัวกรองวันที่เสมอจึงจะมีความหมาย
TIME_CONTEXTS: list[tuple[str, dict]] = [
    ("มี.ค. 2026", {"Date[Year]": [2026], "Date[MonthNo]": [3]}),
    ("มิ.ย. 2026", {"Date[Year]": [2026], "Date[MonthNo]": [6]}),
    ("ก.ย. 2025", {"Date[Year]": [2025], "Date[MonthNo]": [9]}),
    ("มี.ค. 2026 เฉพาะ Line B", {"Date[Year]": [2026], "Date[MonthNo]": [3],
                                  "Machine[Line]": ["Line B"]}),
]


# ===========================================================================
# แบบฝึกหัด DAX
# ===========================================================================
DAX_EXERCISES: list[dict] = [
    # ---------- พื้นฐาน ----------
    {
        "id": "d01", "group": "1. พื้นฐาน", "level": 1,
        "title": "รวมจำนวนชิ้นดี",
        "prompt": "สร้าง measure ที่รวมจำนวนชิ้นดีทั้งหมดจากคอลัมน์ `Production[GoodQty]`",
        "hint": "ใช้ฟังก์ชัน SUM รับคอลัมน์เดียว เขียนแบบ SUM(ตาราง[คอลัมน์])",
        "solution": "SUM( Production[GoodQty] )",
        "teach": "ฟังก์ชันรวมยอดพื้นฐานทำงานกับ 'คอลัมน์ที่มองเห็นในบริบทปัจจุบัน' เสมอ",
    },
    {
        "id": "d02", "group": "1. พื้นฐาน", "level": 1,
        "title": "นับจำนวนเครื่องจักร",
        "prompt": "นับจำนวนเครื่องจักรที่มีอยู่ในบริบทปัจจุบัน (ตาราง `Machine`)",
        "hint": "COUNTROWS รับ 'ตาราง' ไม่ใช่คอลัมน์",
        "solution": "COUNTROWS( Machine )",
        "teach": "COUNTROWS(ตารางมิติ) นับจำนวนแถวของมิตินั้นที่ยังมองเห็นอยู่หลังถูกกรอง",
    },
    {
        "id": "d03", "group": "1. พื้นฐาน", "level": 1,
        "title": "นับสายการผลิตที่ไม่ซ้ำ",
        "prompt": "นับว่ามีสายการผลิตที่แตกต่างกันกี่สาย จากคอลัมน์ `Machine[Line]`",
        "hint": "COUNT นับทุกแถว ส่วนที่นับเฉพาะค่าไม่ซ้ำคือ DISTINCTCOUNT",
        "solution": "DISTINCTCOUNT( Machine[Line] )",
        "teach": "แยกให้ออกระหว่าง COUNT (ทุกแถวที่ไม่ว่าง) กับ DISTINCTCOUNT (ค่าที่ไม่ซ้ำ)",
    },
    {
        "id": "d04", "group": "1. พื้นฐาน", "level": 1,
        "title": "อัตราการเดินเครื่อง (Availability)",
        "prompt": "คำนวณ Availability = เวลาเดินเครื่องจริง `RunMin` หารด้วยเวลาที่วางแผน `PlannedMin` "
                  "โดยต้องไม่พังเมื่อตัวหารเป็นศูนย์",
        "hint": "ใช้ DIVIDE( ตัวตั้ง, ตัวหาร ) แทนเครื่องหมาย /",
        "solution": "DIVIDE( SUM( Production[RunMin] ), SUM( Production[PlannedMin] ) )",
        "teach": "DIVIDE คืนค่าว่างแทนที่จะเกิด error เมื่อตัวหารเป็นศูนย์ — ใช้เป็นนิสัย",
    },
    {
        "id": "d05", "group": "1. พื้นฐาน", "level": 1,
        "title": "อัตราของเสีย",
        "prompt": "คำนวณสัดส่วนชิ้นเสีย = `RejectQty` ÷ (`GoodQty` + `RejectQty`)",
        "hint": "ตัวหารคือผลรวมของทั้งสองคอลัมน์ — บวก SUM สองตัวเข้าด้วยกัน",
        "solution": "DIVIDE( SUM( Production[RejectQty] ), "
                    "SUM( Production[GoodQty] ) + SUM( Production[RejectQty] ) )",
        "teach": "การบวก SUM สองตัวทำที่ระดับยอดรวม ไม่ใช่ระดับแถว จึงไม่ต้องใช้ตระกูล X",
    },
    {
        "id": "d06", "group": "1. พื้นฐาน", "level": 2,
        "title": "เวลาหยุดเฉลี่ยต่อกะ",
        "prompt": "หาค่าเฉลี่ยของ `Production[DownMin]` ต่อหนึ่งแถว (หนึ่งกะการผลิต)",
        "hint": "AVERAGE รับคอลัมน์เดียว",
        "solution": "AVERAGE( Production[DownMin] )",
        "teach": "AVERAGE ข้ามแถวที่เป็นค่าว่างให้อัตโนมัติ ต่างจากการเอา SUM หารด้วย COUNTROWS",
    },

    # ---------- ตระกูล X ----------
    {
        "id": "d07", "group": "2. ตระกูล X", "level": 2,
        "title": "มูลค่าการผลิต",
        "prompt": "คำนวณมูลค่ารวม = จำนวนชิ้นดีของแต่ละแถว × ราคาต่อหน่วยของสินค้าในแถวนั้น "
                  "(`Product[UnitPrice]`)",
        "hint": "ต้องคูณทีละแถวก่อนแล้วค่อยรวม จึงต้องใช้ SUMX( ตาราง, สูตรระดับแถว )",
        "solution": "SUMX( Production, Production[GoodQty] * RELATED( Product[UnitPrice] ) )",
        "teach": "SUM(a) * SUM(b) ให้ผลผิดสิ้นเชิง เพราะเป็นผลคูณของยอดรวม ไม่ใช่ผลรวมของยอดคูณ",
    },
    {
        "id": "d08", "group": "2. ตระกูล X", "level": 2,
        "title": "จำนวนที่ควรผลิตได้ตามทฤษฎี",
        "prompt": "คำนวณจำนวนที่ควรผลิตได้ = เวลาเดินเครื่องของแต่ละแถว × กำลังผลิตมาตรฐานของเครื่องนั้น "
                  "(`Machine[StdRate]` หน่วยชิ้น/นาที)",
        "hint": "แต่ละเครื่องมี StdRate ต่างกัน จึงคูณที่ระดับแถวเท่านั้นถึงจะถูก",
        "solution": "SUMX( Production, Production[RunMin] * RELATED( Machine[StdRate] ) )",
        "teach": "นี่คือฐานของ Performance ใน OEE — ใช้ค่าเฉลี่ย StdRate มาคูณยอดรวมจะได้เลขผิด",
    },
    {
        "id": "d09", "group": "2. ตระกูล X", "level": 2,
        "title": "ค่าเฉลี่ยของ Availability รายกะ",
        "prompt": "หาค่าเฉลี่ยของอัตราเดินเครื่องรายกะ (คำนวณสัดส่วนของแต่ละแถวก่อน แล้วค่อยเฉลี่ย)",
        "hint": "ใช้ AVERAGEX แล้วใส่ DIVIDE ระดับแถวไว้ข้างใน",
        "solution": "AVERAGEX( Production, DIVIDE( Production[RunMin], Production[PlannedMin] ) )",
        "teach": "ค่านี้ต่างจาก DIVIDE(SUM,SUM) — อันนี้คือค่าเฉลี่ยของสัดส่วน อีกอันคือสัดส่วนของยอดรวม",
    },
    {
        "id": "d10", "group": "2. ตระกูล X", "level": 3,
        "title": "เวลาหยุดสูงสุดของกะเดียว",
        "prompt": "หาค่าเวลาหยุดที่มากที่สุดที่เคยเกิดในกะเดียว จาก `Production[DownMin]`",
        "hint": "ข้อนี้ใช้ MAX ธรรมดาก็ได้ ลองดูว่า MAXX ให้ผลเดียวกันไหม",
        "solution": "MAX( Production[DownMin] )",
        "teach": "เมื่อไม่มีการคำนวณระดับแถว ให้ใช้ฟังก์ชันธรรมดาซึ่งเร็วกว่าตระกูล X",
    },

    # ---------- ตรรกะ ----------
    {
        "id": "d11", "group": "3. ตรรกะ", "level": 2,
        "title": "จัดสถานะตามอัตราเดินเครื่อง",
        "prompt": 'คืนค่า "ผ่านเป้า" เมื่อ Availability ≥ 0.85 มิฉะนั้นคืน "ต่ำกว่าเป้า"',
        "hint": "IF( เงื่อนไข, ค่าถ้าจริง, ค่าถ้าเท็จ ) — เขียน DIVIDE ไว้ในเงื่อนไขได้เลย",
        "solution": 'IF( DIVIDE( SUM( Production[RunMin] ), SUM( Production[PlannedMin] ) ) >= 0.85, '
                    '"ผ่านเป้า", "ต่ำกว่าเป้า" )',
        "teach": "measure คืนค่าเป็นข้อความได้ ใช้ทำป้ายสถานะในตารางหรือการ์ด KPI",
    },
    {
        "id": "d12", "group": "3. ตรรกะ", "level": 3,
        "title": "จัดเกรดด้วย SWITCH",
        "prompt": "จัดเกรดจาก Availability เป็น 3 ระดับ: ≥ 0.90 คืน \"A\", ≥ 0.80 คืน \"B\", "
                  "นอกนั้นคืน \"C\"",
        "hint": "SWITCH( TRUE(), เงื่อนไข1, ผล1, เงื่อนไข2, ผล2, ผลที่เหลือ ) — เรียงจากเข้มไปหลวม",
        "solution": 'VAR A = DIVIDE( SUM( Production[RunMin] ), SUM( Production[PlannedMin] ) ) '
                    'RETURN SWITCH( TRUE(), A >= 0.90, "A", A >= 0.80, "B", "C" )',
        "teach": "SWITCH ตรวจจากบนลงล่างแล้วหยุดที่เงื่อนไขแรกที่จริง ลำดับจึงสำคัญมาก",
        # เลือกบริบทที่ให้ค่าตกคนละเกรด เพื่อให้จับได้ถ้าเรียงลำดับเงื่อนไขผิด
        "contexts": [
            ("M02 ม.ค. 2025 (ควรได้ A)", {"Machine[MachineID]": ["M02"],
                                           "Date[Year]": [2025], "Date[MonthNo]": [1]}),
            ("M03 พ.ค. 2026 (ควรได้ B)", {"Machine[MachineID]": ["M03"],
                                            "Date[Year]": [2026], "Date[MonthNo]": [5]}),
            ("M01 มิ.ย. 2026 (ควรได้ C)", {"Machine[MachineID]": ["M01"],
                                             "Date[Year]": [2026], "Date[MonthNo]": [6]}),
            ("ไม่กรองอะไรเลย", {}),
        ],
    },
    {
        "id": "d13", "group": "3. ตรรกะ", "level": 2,
        "title": "ใช้ VAR ให้สูตรอ่านง่าย",
        "prompt": "คำนวณ Quality = ชิ้นดี ÷ (ชิ้นดี + ชิ้นเสีย) โดยใช้ `VAR ... RETURN` "
                  "และต้องเรียก SUM ของแต่ละคอลัมน์เพียงครั้งเดียว",
        "hint": "VAR ชื่อ = สูตร (ขึ้นบรรทัดใหม่ได้) แล้วปิดท้ายด้วย RETURN นิพจน์",
        "solution": "VAR G = SUM( Production[GoodQty] ) "
                    "VAR R = SUM( Production[RejectQty] ) "
                    "RETURN DIVIDE( G, G + R )",
        "teach": "VAR คำนวณครั้งเดียวแม้เรียกใช้หลายที่ ทั้งเร็วกว่าและอ่านง่ายกว่า",
    },

    # ---------- CALCULATE ----------
    {
        "id": "d14", "group": "4. CALCULATE", "level": 2,
        "title": "ยอดเฉพาะสาย Line A",
        "prompt": 'คำนวณยอดชิ้นดีเฉพาะสาย "Line A" โดยไม่สนใจว่าผู้ใช้กำลังกรองสายอื่นอยู่หรือไม่',
        "hint": 'CALCULATE( นิพจน์, Machine[Line] = "Line A" )',
        "solution": 'CALCULATE( SUM( Production[GoodQty] ), Machine[Line] = "Line A" )',
        "teach": "ตัวกรองใน CALCULATE แทนที่ตัวกรองเดิมของคอลัมน์นั้น — จึงได้ Line A เสมอ "
                 "ถ้าครอบด้วย KEEPFILTERS ผลจะกลายเป็นค่าว่างเมื่อผู้ใช้เลือกสายอื่นอยู่",
        # ต้องมีบริบทที่กรองสายอื่นอยู่ ไม่งั้นคำตอบที่ใส่ KEEPFILTERS ผิด ๆ จะผ่านไปได้
        "contexts": [
            ("ไม่กรองอะไรเลย", {}),
            ("ผู้ใช้เลือก Line B อยู่", {"Machine[Line]": ["Line B"]}),
            ("ผู้ใช้เลือก Line C + กะเช้า", {"Machine[Line]": ["Line C"],
                                              "Shift[ShiftID]": ["S1"]}),
            ("ผู้ใช้เลือก Line A อยู่", {"Machine[Line]": ["Line A"]}),
        ],
    },
    {
        "id": "d15", "group": "4. CALCULATE", "level": 3,
        "title": "เวลาหยุดจากเครื่องเสีย",
        "prompt": 'รวมเวลาหยุด `DownMin` เฉพาะแถวที่ `Production[DownReason]` เท่ากับ "เครื่องเสีย"',
        "hint": "เงื่อนไขคอลัมน์เดียวแบบนี้เขียนตรง ๆ ใน CALCULATE ได้ ไม่ต้องใช้ FILTER",
        "solution": 'CALCULATE( SUM( Production[DownMin] ), Production[DownReason] = "เครื่องเสีย" )',
        "teach": "เงื่อนไขคอลัมน์เดียวควรเขียนตรง ๆ เพราะเร็วกว่าการใช้ FILTER เดินทีละแถว",
    },
    {
        "id": "d16", "group": "4. CALCULATE", "level": 3,
        "title": "ยอดจากกะที่หยุดนาน",
        "prompt": "รวมจำนวนชิ้นดีเฉพาะกะที่มีเวลาหยุดเกิน 120 นาที **และ** ผลิตได้มากกว่า 0 ชิ้น",
        "hint": "เงื่อนไขอ้างสองคอลัมน์ ต้องใช้ FILTER( Production, เงื่อนไข1 && เงื่อนไข2 )",
        "solution": "CALCULATE( SUM( Production[GoodQty] ), "
                    "FILTER( Production, Production[DownMin] > 120 && Production[GoodQty] > 0 ) )",
        "teach": "เมื่อเงื่อนไขอ้างมากกว่าหนึ่งคอลัมน์ ต้องใช้ FILTER เพราะเขียนแบบเงื่อนไขตรง ๆ ไม่ได้",
    },
    {
        "id": "d17", "group": "4. CALCULATE", "level": 3,
        "title": "ยอดของเครื่องวิกฤตเท่านั้น",
        "prompt": "รวมจำนวนชิ้นดีเฉพาะเครื่องที่ `Machine[IsCritical]` เป็นจริง",
        "hint": "เขียนเงื่อนไขเป็น Machine[IsCritical] = TRUE()",
        "solution": "CALCULATE( SUM( Production[GoodQty] ), Machine[IsCritical] = TRUE() )",
        "teach": "คอลัมน์ตรรกะเทียบกับ TRUE() / FALSE() ได้ตรง ๆ ไม่ต้องแปลงเป็นข้อความ",
    },

    # ---------- ALL และสัดส่วน ----------
    {
        "id": "d18", "group": "5. ALL และสัดส่วน", "level": 3,
        "title": "สัดส่วนต่อยอดรวมทั้งโรงงาน",
        "prompt": "คำนวณสัดส่วนของยอดชิ้นดีในบริบทปัจจุบัน เทียบกับยอดรวมของทุกเครื่องทุกสาย "
                  "(ตัวส่วนต้องไม่เปลี่ยนตามการกรองที่ตาราง `Machine`)",
        "hint": "ตัวส่วนใช้ CALCULATE( ..., ALL( Machine ) ) เพื่อถอดตัวกรองของตาราง Machine ทั้งหมด",
        "solution": "DIVIDE( SUM( Production[GoodQty] ), "
                    "CALCULATE( SUM( Production[GoodQty] ), ALL( Machine ) ) )",
        "teach": "สำนวนนี้คือรากของทุกสูตร '% ของยอดรวม' ที่ใช้ในงานจริง",
        "contexts": [
            ("กรองสาย Line A", {"Machine[Line]": ["Line A"]}),
            ("กรองเครื่อง M05", {"Machine[MachineID]": ["M05"]}),
            ("กรองประเภทเครื่อง พ่นสี", {"Machine[MachineType]": ["พ่นสี"]}),
            ("กรอง Line C + กะบ่าย", {"Machine[Line]": ["Line C"], "Shift[ShiftID]": ["S2"]}),
        ],
    },
    {
        "id": "d19", "group": "5. ALL และสัดส่วน", "level": 4,
        "title": "สัดส่วนต่อยอดของสายตัวเอง",
        "prompt": "คำนวณสัดส่วนของยอดชิ้นดี เทียบกับยอดรวมของ **สายการผลิตที่แถวนั้นอยู่** "
                  "(ตัวส่วนต้องยังคงถูกกรองด้วย `Machine[Line]` แต่ไม่ถูกกรองด้วยคอลัมน์อื่นของ Machine)",
        "hint": "ALLEXCEPT( Machine, Machine[Line] ) ถอดทุกคอลัมน์ของ Machine ยกเว้น Line",
        "solution": "DIVIDE( SUM( Production[GoodQty] ), "
                    "CALCULATE( SUM( Production[GoodQty] ), ALLEXCEPT( Machine, Machine[Line] ) ) )",
        "teach": "ALLEXCEPT ใช้ทำสัดส่วนเทียบกลุ่มแม่ ซึ่งตัวส่วนเปลี่ยนไปตามกลุ่มของแต่ละแถว",
        # จำลองสถานการณ์จริงคือ matrix ที่มีทั้งสายและเครื่องอยู่บนแถว จึงมีตัวกรองทั้งสองระดับ
        # ถ้าไม่มีตัวกรองสายอยู่ด้วย คำตอบที่ใช้ ALL(Machine) ผิด ๆ จะให้ผลเท่ากันจนแยกไม่ออก
        "contexts": [
            ("Line A → เครื่อง M01", {"Machine[Line]": ["Line A"],
                                       "Machine[MachineID]": ["M01"]}),
            ("Line C → เครื่อง M07", {"Machine[Line]": ["Line C"],
                                       "Machine[MachineID]": ["M07"]}),
            ("Line B → ประเภท ปิดขอบ", {"Machine[Line]": ["Line B"],
                                          "Machine[MachineType]": ["ปิดขอบ"]}),
            ("Line D → M10 กะเช้า", {"Machine[Line]": ["Line D"],
                                      "Machine[MachineID]": ["M10"],
                                      "Shift[ShiftID]": ["S1"]}),
        ],
    },
    {
        "id": "d20", "group": "5. ALL และสัดส่วน", "level": 4,
        "title": "ถอดตัวกรองเฉพาะคอลัมน์เดียว",
        "prompt": "คำนวณยอดชิ้นดีของ **ทุกสายการผลิต** แต่ยังคงตัวกรองอื่น ๆ ของตาราง `Machine` ไว้ "
                  "(เช่นถ้าผู้ใช้กรองประเภทเครื่องไว้ ต้องยังถูกกรองอยู่)",
        "hint": "ALL( Machine[Line] ) ถอดเฉพาะคอลัมน์ Line ไม่ใช่ทั้งตาราง",
        "solution": "CALCULATE( SUM( Production[GoodQty] ), ALL( Machine[Line] ) )",
        "teach": "ต้องเลือกระดับของ ALL ให้ถูก — ถอดทั้งตารางทั้งที่ต้องการถอดคอลัมน์เดียวจะได้ตัวเลขกว้างเกินไป",
        "contexts": [
            ("กรอง Line A + ประเภทตัด", {"Machine[Line]": ["Line A"], "Machine[MachineType]": ["ตัด"]}),
            ("กรอง Line B + ประเภทเจาะ", {"Machine[Line]": ["Line B"], "Machine[MachineType]": ["เจาะ"]}),
            ("กรอง Line C + เครื่องวิกฤต", {"Machine[Line]": ["Line C"], "Machine[IsCritical]": [True]}),
        ],
    },

    # ---------- Time intelligence ----------
    {
        "id": "d21", "group": "6. Time intelligence", "level": 3,
        "title": "ยอดสะสมตั้งแต่ต้นปี (YTD)",
        "prompt": "คำนวณยอดชิ้นดีสะสมตั้งแต่ 1 มกราคมของปีนั้น ถึงวันสุดท้ายในบริบทปัจจุบัน",
        "hint": "CALCULATE( นิพจน์, DATESYTD( Date[Date] ) ) หรือใช้ TOTALYTD ก็ได้",
        "solution": "CALCULATE( SUM( Production[GoodQty] ), DATESYTD( Date[Date] ) )",
        "teach": "DATESYTD คืนตารางวันที่ตั้งแต่ต้นปีถึงวันสุดท้ายในบริบท แล้ว CALCULATE เอาไปแทนตัวกรองวันที่เดิม",
        "contexts": TIME_CONTEXTS,
    },
    {
        "id": "d22", "group": "6. Time intelligence", "level": 3,
        "title": "ยอดของช่วงเดียวกันปีก่อน",
        "prompt": "คำนวณยอดชิ้นดีของช่วงเวลาเดียวกันในปีก่อนหน้า",
        "hint": "SAMEPERIODLASTYEAR( Date[Date] ) หรือ DATEADD( Date[Date], -1, YEAR )",
        "solution": "CALCULATE( SUM( Production[GoodQty] ), SAMEPERIODLASTYEAR( Date[Date] ) )",
        "teach": "ทั้งสองฟังก์ชันให้ผลเหมือนกัน ต่างที่ DATEADD เปลี่ยนหน่วยเวลาได้",
        "contexts": TIME_CONTEXTS,
    },
    {
        "id": "d23", "group": "6. Time intelligence", "level": 4,
        "title": "อัตราการเติบโตเทียบปีก่อน (YoY %)",
        "prompt": "คำนวณอัตราการเติบโต = (ยอดปีนี้ − ยอดปีก่อน) ÷ ยอดปีก่อน "
                  "โดยถ้าปีก่อนไม่มีข้อมูล ให้คืนค่าว่าง",
        "hint": "เก็บยอดทั้งสองไว้ใน VAR แล้วใช้ IF ตรวจว่าปีก่อนว่างหรือเป็นศูนย์ก่อนหาร",
        "solution": "VAR cur = SUM( Production[GoodQty] ) "
                    "VAR prev = CALCULATE( SUM( Production[GoodQty] ), SAMEPERIODLASTYEAR( Date[Date] ) ) "
                    "RETURN IF( NOT ISBLANK( prev ) && prev <> 0, DIVIDE( cur - prev, prev ) )",
        "teach": "การดักกรณีฐานว่างสำคัญมาก ไม่งั้นกราฟจะพุ่งเป็น 100% ในเดือนที่ยังไม่มีข้อมูลปีก่อน",
        "contexts": TIME_CONTEXTS,
    },

    # ---------- OEE ----------
    {
        "id": "d24", "group": "7. โปรเจกต์ OEE", "level": 3,
        "title": "Performance",
        "prompt": "คำนวณ Performance = จำนวนที่ผลิตได้ทั้งหมด (ดี + เสีย) ÷ จำนวนที่ควรผลิตได้ตามทฤษฎี "
                  "(เวลาเดินเครื่อง × `Machine[StdRate]` ระดับแถว)",
        "hint": "ตัวตั้งใช้ SUM สองตัวบวกกัน ตัวหารต้องใช้ SUMX",
        "solution": "DIVIDE( SUM( Production[GoodQty] ) + SUM( Production[RejectQty] ), "
                    "SUMX( Production, Production[RunMin] * RELATED( Machine[StdRate] ) ) )",
        "teach": "องค์ประกอบที่คนคำนวณผิดบ่อยที่สุดใน OEE เพราะลืมว่า StdRate ต่างกันในแต่ละเครื่อง",
    },
    {
        "id": "d25", "group": "7. โปรเจกต์ OEE", "level": 4,
        "title": "OEE เต็มสูตร",
        "prompt": "คำนวณ OEE = Availability × Performance × Quality โดยใช้ `VAR` แยกแต่ละองค์ประกอบ",
        "hint": "A = RunMin ÷ PlannedMin · P = (ดี+เสีย) ÷ ทฤษฎี · Q = ดี ÷ (ดี+เสีย)",
        "solution": "VAR PlannedM = SUM( Production[PlannedMin] ) "
                    "VAR RunM = SUM( Production[RunMin] ) "
                    "VAR G = SUM( Production[GoodQty] ) "
                    "VAR T = G + SUM( Production[RejectQty] ) "
                    "VAR Theo = SUMX( Production, Production[RunMin] * RELATED( Machine[StdRate] ) ) "
                    "RETURN DIVIDE( RunM, PlannedM ) * DIVIDE( T, Theo ) * DIVIDE( G, T )",
        "teach": "ในงานจริงควรแยกเป็น measure ทีละชั้นแล้วเรียกต่อกัน จะแก้และทดสอบง่ายกว่ามาก",
    },
    {
        "id": "d26", "group": "7. โปรเจกต์ OEE", "level": 4,
        "title": "สัดส่วนเวลาหยุดของแต่ละสาเหตุ",
        "prompt": "คำนวณสัดส่วนเวลาหยุดในบริบทปัจจุบัน เทียบกับเวลาหยุดรวมของ **ทุกสาเหตุ** "
                  "(ใช้ทำกราฟพาเรโต)",
        "hint": "ตัวส่วนถอดตัวกรองเฉพาะคอลัมน์ Production[DownReason]",
        "solution": "DIVIDE( SUM( Production[DownMin] ), "
                    "CALCULATE( SUM( Production[DownMin] ), ALL( Production[DownReason] ) ) )",
        "teach": "ถอดตัวกรองเฉพาะคอลัมน์สาเหตุ จึงยังเทียบภายในสาย/เดือนที่ผู้ใช้เลือกอยู่ได้",
        "contexts": [
            ("สาเหตุ เครื่องเสีย", {"Production[DownReason]": ["เครื่องเสีย"]}),
            ("สาเหตุ รอวัสดุ", {"Production[DownReason]": ["รอวัสดุ"]}),
            ("เครื่องเสีย + Line A", {"Production[DownReason]": ["เครื่องเสีย"],
                                       "Machine[Line]": ["Line A"]}),
            # มีตัวกรองคอลัมน์อื่นของ Production ด้วย เพื่อจับคำตอบที่ใช้ ALL(Production)
            # ซึ่งถอดตัวกรองมากเกินไปจนตัวส่วนกว้างผิด
            ("เครื่องเสีย + กะเต็ม 480 นาที", {"Production[DownReason]": ["เครื่องเสีย"],
                                                "Production[PlannedMin]": [480.0]}),
            ("ปรับตั้งเครื่อง + มี.ค. 2026", {"Production[DownReason]": ["ปรับตั้งเครื่อง"],
                                              "Date[Year]": [2026], "Date[MonthNo]": [3]}),
        ],
    },
]

DAX_BY_ID: dict[str, dict] = {e["id"]: e for e in DAX_EXERCISES}
DAX_GROUPS: list[str] = list(dict.fromkeys(e["group"] for e in DAX_EXERCISES))
TOTAL_DAX = len(DAX_EXERCISES)


# ---------------------------------------------------------------------------
# ตัวตรวจคำตอบ DAX
# ---------------------------------------------------------------------------
def _same(a, b, tol: float = 1e-6) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, str) or isinstance(b, str):
        return str(a).strip() == str(b).strip()
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    if math.isnan(fa) and math.isnan(fb):
        return True
    scale = max(1.0, abs(fa), abs(fb))
    return abs(fa - fb) <= tol * scale


def grade_dax(ex: dict, user_formula: str, model) -> dict:
    """ตรวจสูตรของผู้เรียนเทียบกับเฉลย ภายใต้ filter context หลายชุด

    คืน {"ok": bool, "error": str|None, "rows": [{"ctx", "user", "expect", "pass"}]}
    """
    contexts = ex.get("contexts") or DEFAULT_CONTEXTS
    rows: list[dict] = []

    for label, sel in contexts:
        try:
            expect = evaluate(ex["solution"], model, sel)
        except DaxError as e:                      # ไม่ควรเกิด — เฉลยผิดเอง
            return {"ok": False, "error": f"เฉลยของข้อนี้มีปัญหา: {e}", "rows": []}
        try:
            got = evaluate(user_formula, model, sel)
        except DaxError as e:
            return {"ok": False, "error": str(e), "rows": rows}
        except Exception as e:                     # ป้องกันแอปล้มจากสูตรแปลก ๆ
            return {"ok": False, "error": f"คำนวณไม่สำเร็จ: {type(e).__name__}: {e}", "rows": rows}

        rows.append({"ctx": label, "user": got, "expect": expect,
                     "pass": _same(got, expect)})

    return {"ok": all(r["pass"] for r in rows), "error": None, "rows": rows}


# ===========================================================================
# แบบฝึกหัด Power Query
# ===========================================================================
# kind = "order"  → เรียงลำดับขั้นตอนให้ถูก (ผู้เรียนเลือกตามลำดับ)
# kind = "choice" → เลือกคำตอบที่ถูกที่สุด
PQ_EXERCISES: list[dict] = [
    {
        "id": "p01", "group": "1. ทำความสะอาด", "kind": "order",
        "title": "ลำดับขั้นตอนที่มีประสิทธิภาพ",
        "scenario": "ไฟล์ยอดผลิตมี 40 คอลัมน์ แต่ใช้จริง 8 คอลัมน์ และมีแถวรวมยอดปะปนอยู่ "
                    "จงเรียงลำดับขั้นตอนให้ประมวลผลเร็วที่สุด",
        "steps": [
            "เลือกเก็บเฉพาะ 8 คอลัมน์ที่ใช้ (Choose Columns)",
            "กรองแถวรวมยอดออก (Filter Rows)",
            "ตัดช่องว่างของคอลัมน์รหัส (Trim)",
            "กำหนดชนิดข้อมูลให้ทุกคอลัมน์ (Change Type)",
        ],
        "answer": [0, 1, 2, 3],
        "explain": "ลดปริมาณข้อมูลก่อนเสมอ — ตัดคอลัมน์ที่ไม่ใช้ แล้วตัดแถวที่ไม่ใช้ "
                   "จากนั้นจึงทำงานที่ใช้ทรัพยากรอย่างการตัดช่องว่างและแปลงชนิดข้อมูล "
                   "บนข้อมูลที่เล็กที่สุดเท่าที่จะเป็นได้",
    },
    {
        "id": "p02", "group": "1. ทำความสะอาด", "kind": "choice",
        "title": "รหัสเชื่อมกันไม่ติด",
        "scenario": "สร้างความสัมพันธ์ระหว่าง Production[MachineID] กับ Machine[MachineID] แล้ว "
                    "ยอดหายไปบางส่วน ตรวจดูพบว่าค่าในไฟล์ต้นทางเป็น \"M01 \" (มีช่องว่างท้าย) "
                    "ควรแก้อย่างไรให้ถูกต้องที่สุด",
        "options": [
            "ใช้ Replace Values แทนที่ \"M01 \" ด้วย \"M01\"",
            "ใช้ Trim กับคอลัมน์รหัสทั้งสองตาราง",
            "เปลี่ยนความสัมพันธ์เป็นสองทิศทาง",
            "สร้าง calculated column ด้วย TRIM ใน DAX",
        ],
        "answer": 1,
        "explain": "Trim แก้ทั้งคอลัมน์ในครั้งเดียวและครอบคลุมค่าอื่นที่มีปัญหาเดียวกัน "
                   "ส่วน Replace Values แก้ได้ทีละค่าซึ่งไม่ยั่งยืน และการแก้ด้วย DAX "
                   "ก็สายเกินไปเพราะความสัมพันธ์ถูกสร้างจากคอลัมน์เดิมไปแล้ว",
    },
    {
        "id": "p03", "group": "2. Unpivot", "kind": "choice",
        "title": "ตารางที่เดือนเป็นคอลัมน์",
        "scenario": "ไฟล์รายงานมีคอลัมน์ เครื่อง, ม.ค., ก.พ., มี.ค. และทุกเดือนจะมีคอลัมน์ใหม่เพิ่มมา "
                    "ต้องการให้ query รองรับเดือนใหม่โดยไม่ต้องแก้ขั้นตอน",
        "options": [
            "เลือกคอลัมน์เดือนทั้งหมด แล้วกด Unpivot Columns",
            "เลือกคอลัมน์ เครื่อง แล้วกด Unpivot Other Columns",
            "ใช้ Transpose แล้วเลื่อนหัวตาราง",
            "ใช้ Pivot Column กับคอลัมน์เครื่อง",
        ],
        "answer": 1,
        "explain": "Unpivot Other Columns บอกว่า 'ทุกอย่างที่ไม่ใช่คอลัมน์เครื่องคือค่า' "
                   "เดือนใหม่ที่เพิ่มเข้ามาจึงถูก unpivot ให้อัตโนมัติ "
                   "ส่วน Unpivot Columns จะจำเฉพาะคอลัมน์ที่เลือกไว้ตอนนั้น",
    },
    {
        "id": "p04", "group": "2. Unpivot", "kind": "order",
        "title": "แปลงตารางไขว้ให้พร้อมเข้าโมเดล",
        "scenario": "ไฟล์มีโลโก้ 3 บรรทัดบนสุด ต่อด้วยหัวตาราง แล้วเป็นข้อมูลที่เดือนเป็นคอลัมน์ "
                    "จงเรียงขั้นตอนให้ถูกต้อง",
        "steps": [
            "Remove Top Rows จำนวน 3 แถว",
            "Use First Row as Headers",
            "เลือกคอลัมน์ที่ไม่ใช่เดือน แล้ว Unpivot Other Columns",
            "เปลี่ยนชื่อ Attribute เป็น เดือน และ Value เป็น จำนวน",
        ],
        "answer": [0, 1, 2, 3],
        "explain": "ต้องตัดบรรทัดขยะออกก่อน ไม่งั้นการเลื่อนหัวตารางจะได้หัวผิด "
                   "แล้วจึง unpivot และตั้งชื่อคอลัมน์ผลลัพธ์ให้สื่อความหมาย",
    },
    {
        "id": "p05", "group": "3. Merge และ Append", "kind": "choice",
        "title": "ตรวจหาคีย์กำพร้า",
        "scenario": "ต้องการตรวจว่ามีรหัสเครื่องใน Production ที่ไม่มีอยู่ในทะเบียน Machine หรือไม่ "
                    "ก่อนสร้างความสัมพันธ์",
        "options": [
            "Merge แบบ Inner แล้วดูจำนวนแถวที่ได้",
            "Merge แบบ Left Anti โดยให้ Production เป็นตารางซ้าย",
            "Append สองตารางแล้ว Remove Duplicates",
            "Merge แบบ Full Outer แล้วกรองค่าว่าง",
        ],
        "answer": 1,
        "explain": "Left Anti คืนเฉพาะแถวของตารางซ้ายที่จับคู่ไม่ได้ ถ้าผลลัพธ์มีแถวเหลือ "
                   "แปลว่ามีรหัสกำพร้าที่จะกลายเป็นแถว (Blank) ในรายงาน "
                   "เป็นการตรวจที่ตรงประเด็นและอ่านผลได้ทันที",
    },
    {
        "id": "p06", "group": "3. Merge และ Append", "kind": "choice",
        "title": "จำนวนแถวเพิ่มขึ้นหลัง Merge",
        "scenario": "หลังจาก Merge ตาราง Production (10,000 แถว) กับ Machine แบบ Left Outer "
                    "กลับได้ผลลัพธ์ 12,400 แถว สาเหตุคืออะไร",
        "options": [
            "Power Query คำนวณผิดพลาด",
            "ตาราง Machine มีรหัสเครื่องซ้ำกัน ทำให้หนึ่งแถวซ้ายจับคู่ได้หลายแถวขวา",
            "เลือกชนิด Merge ผิด ควรใช้ Inner",
            "ต้องกด Remove Duplicates ที่ตาราง Production ก่อน",
        ],
        "answer": 1,
        "explain": "Merge แบบ Left Outer คงจำนวนแถวซ้ายไว้ก็ต่อเมื่อคีย์ฝั่งขวาไม่ซ้ำ "
                   "ถ้าฝั่งขวาซ้ำ แถวซ้ายจะถูกทำซ้ำตามจำนวนคู่ที่จับได้ "
                   "จึงต้องตรวจว่าคีย์ของตารางมิติไม่ซ้ำเสมอ",
    },
    {
        "id": "p07", "group": "4. From Folder", "kind": "order",
        "title": "รวมไฟล์รายเดือนจากโฟลเดอร์",
        "scenario": "มีไฟล์ Excel ยอดผลิตรายเดือนอยู่ในโฟลเดอร์เดียวกัน และบางครั้งมีคนเปิดไฟล์ค้างไว้ "
                    "จงเรียงขั้นตอนตั้งแต่ต้น",
        "steps": [
            "Get Data → Folder แล้วชี้ไปที่โฟลเดอร์",
            "กรองเอาเฉพาะไฟล์ .xlsx และตัดไฟล์ที่ขึ้นต้นด้วย ~$ ออก",
            "กด Combine & Transform Data",
            "แก้ขั้นตอนการแปลงข้อมูลที่ Transform Sample File",
        ],
        "answer": [0, 1, 2, 3],
        "explain": "ต้องกรองไฟล์ขยะออกก่อน Combine เสมอ ไม่งั้น query จะพังเมื่อมีคนเปิดไฟล์ค้าง "
                   "และการแก้การแปลงข้อมูลต้องทำที่ Transform Sample File จึงจะมีผลกับทุกไฟล์",
    },
    {
        "id": "p08", "group": "4. From Folder", "kind": "choice",
        "title": "ดึงเดือนจากชื่อไฟล์",
        "scenario": "ชื่อไฟล์เป็นรูปแบบ ยอดผลิต_2569_03.xlsx และต้องการใช้ปีกับเดือนจากชื่อไฟล์ "
                    "เป็นคอลัมน์ในตาราง ควรทำอย่างไร",
        "options": [
            "พิมพ์คอลัมน์ปีและเดือนเพิ่มเองทีละไฟล์",
            "เก็บคอลัมน์ Source.Name ไว้ แล้วใช้ Split Column by Delimiter แยกปีและเดือนออกมา",
            "เรียงไฟล์ตามวันที่แก้ไขล่าสุดแทน",
            "ใช้ Index Column แทนเดือน",
        ],
        "answer": 1,
        "explain": "ชื่อไฟล์มักเป็นข้อมูลที่มีค่า ควรเก็บ Source.Name ไว้ก่อน Combine "
                   "แล้วแยกส่วนที่ต้องการออกมาเป็นคอลัมน์ ทำให้ระบบทำงานอัตโนมัติได้ตลอดไป",
    },
    {
        "id": "p09", "group": "5. ความยั่งยืนของ query", "kind": "choice",
        "title": "ต้นทางเพิ่มคอลัมน์ใหม่",
        "scenario": "ทุกเดือนระบบต้นทางอาจเพิ่มคอลัมน์ใหม่เข้ามา และคุณไม่ต้องการให้คอลัมน์นั้น "
                    "หลุดเข้าโมเดล ควรใช้คำสั่งใด",
        "options": [
            "Remove Columns เลือกคอลัมน์ที่ไม่ต้องการ",
            "Choose Columns เลือกเฉพาะคอลัมน์ที่ต้องการเก็บ",
            "Remove Other Columns หลังจากเรียงคอลัมน์แล้ว",
            "ตั้ง Data Load ไม่ให้ตรวจจับชนิดข้อมูลอัตโนมัติ",
        ],
        "answer": 1,
        "explain": "Choose Columns ระบุรายการที่จะเก็บอย่างชัดเจน คอลัมน์ใหม่ที่ไม่อยู่ในรายการ "
                   "จะถูกตัดทิ้งโดยอัตโนมัติ ในขณะที่ Remove Columns ระบุสิ่งที่จะทิ้ง "
                   "จึงปล่อยให้คอลัมน์ใหม่หลุดเข้ามา",
    },
    {
        "id": "p10", "group": "5. ความยั่งยืนของ query", "kind": "choice",
        "title": "ย้ายไฟล์แล้ว refresh พัง",
        "scenario": "ทีมย้ายโฟลเดอร์ข้อมูลไปเซิร์ฟเวอร์ใหม่ ทำให้ query 12 ตัวพังทั้งหมด "
                    "ควรออกแบบอย่างไรตั้งแต่แรกเพื่อไม่ให้เกิดปัญหานี้",
        "options": [
            "คัดลอกไฟล์ทั้งหมดมาไว้ในเครื่องตัวเอง",
            "สร้าง parameter เก็บ path แล้วให้ทุก query อ้างจาก parameter นั้น",
            "ใช้ path แบบสัมพัทธ์กับตำแหน่งของไฟล์ pbix",
            "เขียน path ซ้ำในทุก query เพื่อความชัดเจน",
        ],
        "answer": 1,
        "explain": "parameter ทำให้เปลี่ยน path ได้ที่เดียวแล้วมีผลทุก query "
                   "และยังแก้ค่าได้จาก Power BI Service โดยไม่ต้องเปิด Desktop "
                   "ซึ่งสำคัญมากเมื่อรายงานถูกเผยแพร่ไปแล้ว",
    },
    {
        "id": "p11", "group": "6. ตารางวันที่", "kind": "order",
        "title": "สร้างตารางวันที่ให้ใช้งานได้จริง",
        "scenario": "จงเรียงขั้นตอนการเตรียมตารางวันที่ให้พร้อมใช้กับ time intelligence",
        "steps": [
            "สร้างรายการวันที่ต่อเนื่องครอบคลุมทั้งปีแรกถึงปีสุดท้ายของข้อมูล",
            "เพิ่มคอลัมน์ ปี เลขเดือน ชื่อเดือน และไตรมาส",
            "ตั้ง Sort by column ให้ชื่อเดือนเรียงตามเลขเดือน",
            "ทำเครื่องหมาย Mark as date table",
            "สร้างความสัมพันธ์จากตารางวันที่ไปยังตาราง fact",
        ],
        "answer": [0, 1, 2, 3, 4],
        "explain": "ลำดับนี้สำคัญเพราะ Mark as date table ต้องทำหลังจากตารางมีวันครบและไม่ซ้ำแล้ว "
                   "และการเรียงเดือนต้องตั้งก่อนนำไปใช้ในรายงาน ไม่งั้นเดือนจะเรียงตามตัวอักษร",
    },
    {
        "id": "p12", "group": "6. ตารางวันที่", "kind": "choice",
        "title": "รอบรายงานไม่ตรงเดือนปฏิทิน",
        "scenario": "รอบรายงานของฝ่ายคือวันที่ 26 ของเดือนก่อน ถึงวันที่ 25 ของเดือนปัจจุบัน "
                    "ควรจัดการอย่างไรให้ยั่งยืนที่สุด",
        "options": [
            "เขียน measure ด้วย CALCULATE ดักช่วงวันที่ทุกครั้งที่ใช้",
            "สร้างคอลัมน์ รอบบัญชี ในตารางวันที่ตั้งแต่ใน Power Query แล้วใช้เป็นแกนแทนเดือนปฏิทิน",
            "เปลี่ยนไปใช้ DirectQuery",
            "ให้ผู้ใช้เลือกช่วงวันที่เองด้วย slicer ทุกครั้ง",
        ],
        "answer": 1,
        "explain": "การแก้ที่ตารางวันที่ทำครั้งเดียวแล้วใช้ได้กับทุก measure และทุก visual "
                   "ส่วนการเขียนเงื่อนไขใน measure ทีละตัวจะต้องทำซ้ำและพลาดง่ายเมื่อมี measure หลายสิบตัว",
    },
]

PQ_BY_ID: dict[str, dict] = {e["id"]: e for e in PQ_EXERCISES}
PQ_GROUPS: list[str] = list(dict.fromkeys(e["group"] for e in PQ_EXERCISES))
TOTAL_PQ = len(PQ_EXERCISES)


def grade_pq(ex: dict, answer) -> bool:
    if ex["kind"] == "order":
        return list(answer) == list(ex["answer"])
    return answer == ex["answer"]
