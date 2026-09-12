"""แบบฝึกหัดเขียนโค้ด พร้อมชุดทดสอบสำหรับตรวจอัตโนมัติ
========================================================

วิธีตรวจ
--------
ระบบ **รันโค้ดของผู้เรียนจริง** ในโปรเซสแยก แล้วเทียบผลลัพธ์กับชุดทดสอบหลายเคส
เขียนวิธีไหนก็ได้ถ้าผลถูกทุกเคส — ไม่ได้เทียบข้อความโค้ดกับเฉลย

โครงของแต่ละข้อ
    id, group, level (1-4), title, prompt
    kind      "func"   = ให้เขียนฟังก์ชัน ระบบจะเรียกด้วยอาร์กิวเมนต์ตามเคส
              "stdout" = ให้เขียนสคริปต์ ระบบจะเทียบสิ่งที่พิมพ์ออกจอ
    func      ชื่อฟังก์ชันที่ต้องสร้าง (เฉพาะ kind="func")
    cases     [{args/kwargs/expect}] หรือ [{stdin, expect}]
    must_use  โครงสร้างที่โจทย์บังคับให้ใช้ (ตรวจจาก AST ไม่ใช่ค้นข้อความ)
    banned    โครงสร้างที่ห้ามใช้ (เช่น ห้ามใช้ sum() เพราะต้องการให้ฝึกลูป)
    files     ไฟล์ประกอบที่จะถูกวางในโฟลเดอร์ทำงานตอนตรวจ
    starter   โค้ดตั้งต้นในช่องเขียน
    solution  เฉลย · teach ข้อคิดหลังทำเสร็จ · lesson บทเรียนที่เกี่ยวข้อง
    project   True = โจทย์งานจริง (ได้ XP มากกว่า)

ค่าคาดหวังของโจทย์ที่ใช้ไฟล์ข้อมูล คำนวณจาก pyacad/sampledata.py ซึ่งล็อกเมล็ดสุ่มไว้
ตัวเลขจึงคงที่ทุกครั้ง
"""

from __future__ import annotations

from pyacad.sampledata import FILES as _F

CSV = {"production.csv": _F["production.csv"]}
CSV_ALL = {k: _F[k] for k in ("production.csv", "machines.csv", "breakdown.csv")}
LOG = {"machine_log.txt": _F["machine_log.txt"]}


EXERCISES: list[dict] = [
    # =======================================================================
    # 1. พื้นฐาน
    # =======================================================================
    {
        "id": "e01", "group": "1. พื้นฐาน", "level": 1, "lesson": "m1l4",
        "title": "เวลาเดินเครื่องจริง",
        "prompt": "เขียนฟังก์ชัน `run_minutes(planned, downtime)` คืนเวลาที่เครื่องเดินจริง "
                  "(เวลาที่วางแผน ลบ เวลาหยุด) ถ้าผลออกมาติดลบให้คืน 0",
        "kind": "func", "func": "run_minutes",
        "cases": [
            {"args": [480, 45], "expect": 435},
            {"args": [480, 0], "expect": 480},
            {"args": [300, 300], "expect": 0},
            {"args": [480, 600], "expect": 0, "label": "หยุดนานกว่าที่วางแผน"},
        ],
        "starter": "def run_minutes(planned, downtime):\n    ...\n",
        "hint": "คำนวณผลต่างก่อน แล้วใช้ if ตรวจว่าติดลบไหม (หรือใช้ max(0, ผลต่าง))",
        "solution": "def run_minutes(planned, downtime):\n"
                    "    return max(0, planned - downtime)\n",
        "teach": "การกันค่าผิดปกติไว้ในฟังก์ชันตั้งแต่ต้น ทำให้รายงานปลายทางไม่มีค่าประหลาดหลุดไป",
    },
    {
        "id": "e02", "group": "1. พื้นฐาน", "level": 1, "lesson": "m1l4",
        "title": "แปลงนาทีเป็นชั่วโมง",
        "prompt": "เขียนฟังก์ชัน `to_hours(minutes)` คืนข้อความรูปแบบ `\"7 ชั่วโมง 15 นาที\"`",
        "kind": "func", "func": "to_hours",
        "cases": [
            {"args": [435], "expect": "7 ชั่วโมง 15 นาที"},
            {"args": [60], "expect": "1 ชั่วโมง 0 นาที"},
            {"args": [45], "expect": "0 ชั่วโมง 45 นาที"},
            {"args": [0], "expect": "0 ชั่วโมง 0 นาที"},
        ],
        "starter": "def to_hours(minutes):\n    ...\n",
        "hint": "ชั่วโมงคือ minutes // 60 ส่วนนาทีที่เหลือคือ minutes % 60",
        "solution": "def to_hours(minutes):\n"
                    "    return f\"{minutes // 60} ชั่วโมง {minutes % 60} นาที\"\n",
        "teach": "คู่หูของ // และ % คือเครื่องมือมาตรฐานสำหรับแปลงหน่วยทุกชนิด",
    },
    {
        "id": "e03", "group": "1. พื้นฐาน", "level": 2, "lesson": "m4l1",
        "title": "Availability ที่ไม่พังเมื่อหารศูนย์",
        "prompt": "เขียนฟังก์ชัน `availability(planned, downtime)` คืนอัตราการเดินเครื่องเป็นทศนิยม 0-1\n\n"
                  "ถ้า `planned` น้อยกว่าหรือเท่ากับ 0 ให้คืน `0.0` และถ้าเดินจริงติดลบให้คืน `0.0`",
        "kind": "func", "func": "availability",
        "cases": [
            {"args": [480, 45], "expect": 0.90625},
            {"args": [480, 0], "expect": 1.0},
            {"args": [480, 480], "expect": 0.0},
            {"args": [0, 0], "expect": 0.0, "label": "ไม่มีแผนเดินเครื่อง"},
            {"args": [480, 600], "expect": 0.0},
        ],
        "starter": "def availability(planned, downtime):\n    ...\n",
        "hint": "ตรวจกรณีผิดปกติก่อนแล้ว return 0.0 ออกไปเลย จากนั้นค่อยคำนวณตามปกติ",
        "solution": "def availability(planned, downtime):\n"
                    "    if planned <= 0:\n"
                    "        return 0.0\n"
                    "    run = planned - downtime\n"
                    "    if run <= 0:\n"
                    "        return 0.0\n"
                    "    return run / planned\n",
        "teach": "รูปแบบ 'ตรวจกรณีผิดปกติแล้วออกก่อน' (early return) ทำให้โค้ดหลักไม่ต้องซ้อน if ลึก ๆ",
    },
    {
        "id": "e04", "group": "1. พื้นฐาน", "level": 2, "lesson": "m1l3",
        "title": "รับค่าจากผู้ใช้แล้วสรุปผล",
        "prompt": "เขียนสคริปต์ที่อ่านค่า 2 บรรทัดจากผู้ใช้ (บรรทัดแรก = เวลาที่วางแผน, "
                  "บรรทัดที่สอง = เวลาหยุด) แล้วพิมพ์ออกมาบรรทัดเดียวในรูปแบบ\n\n"
                  "`เดินจริง 435 นาที (90.6%)`\n\n"
                  "เปอร์เซ็นต์ให้แสดงทศนิยม 1 ตำแหน่ง",
        "kind": "stdout",
        "cases": [
            {"stdin": "480\n45\n", "expect": "เดินจริง 435 นาที (90.6%)"},
            {"stdin": "480\n0\n", "expect": "เดินจริง 480 นาที (100.0%)"},
            {"stdin": "600\n150\n", "expect": "เดินจริง 450 นาที (75.0%)"},
        ],
        "starter": "planned = int(input())\ndowntime = int(input())\n",
        "hint": "ใช้ f-string กับรูปแบบ {ค่า:.1%} ซึ่งคูณ 100 และใส่ % ให้อยู่แล้ว",
        "solution": "planned = int(input())\n"
                    "downtime = int(input())\n"
                    "run = planned - downtime\n"
                    "print(f\"เดินจริง {run} นาที ({run / planned:.1%})\")\n",
        "teach": "input() คืนข้อความเสมอ ต้อง int() ก่อนคำนวณ — เป็นข้อผิดพลาดอันดับต้น ๆ ของมือใหม่",
    },
    {
        "id": "e05", "group": "1. พื้นฐาน", "level": 2, "lesson": "m2l1",
        "title": "บอกกะจากเวลา",
        "prompt": "เขียนฟังก์ชัน `shift_of(hour)` รับชั่วโมง 0-23 คืนชื่อกะ\n\n"
                  "* 6 ถึงก่อน 14 = `\"กะเช้า\"`\n* 14 ถึงก่อน 22 = `\"กะบ่าย\"`\n* นอกนั้น = `\"กะดึก\"`",
        "kind": "func", "func": "shift_of",
        "cases": [
            {"args": [7], "expect": "กะเช้า"},
            {"args": [6], "expect": "กะเช้า"},
            {"args": [13], "expect": "กะเช้า"},
            {"args": [14], "expect": "กะบ่าย"},
            {"args": [21], "expect": "กะบ่าย"},
            {"args": [22], "expect": "กะดึก"},
            {"args": [3], "expect": "กะดึก"},
        ],
        "must_use": ["if"],
        "starter": "def shift_of(hour):\n    ...\n",
        "hint": "เขียนช่วงแบบคณิตศาสตร์ได้เลย เช่น 6 <= hour < 14",
        "solution": "def shift_of(hour):\n"
                    "    if 6 <= hour < 14:\n"
                    "        return \"กะเช้า\"\n"
                    "    if 14 <= hour < 22:\n"
                    "        return \"กะบ่าย\"\n"
                    "    return \"กะดึก\"\n",
        "teach": "เขียนช่วงต่อเนื่องแบบ a <= x < b อ่านง่ายและกันค่าคาบเกี่ยวได้ดีกว่าการใช้ and",
    },

    # =======================================================================
    # 2. เงื่อนไขและลูป
    # =======================================================================
    {
        "id": "e06", "group": "2. เงื่อนไขและลูป", "level": 1, "lesson": "m2l1",
        "title": "จัดระดับความรุนแรงของ downtime",
        "prompt": "เขียนฟังก์ชัน `downtime_level(minutes)` คืนระดับ\n\n"
                  "* มากกว่า 120 = `\"วิกฤต\"`\n* มากกว่า 60 (ถึง 120) = `\"เฝ้าระวัง\"`\n* นอกนั้น = `\"ปกติ\"`",
        "kind": "func", "func": "downtime_level",
        "cases": [
            {"args": [200], "expect": "วิกฤต"},
            {"args": [121], "expect": "วิกฤต"},
            {"args": [120], "expect": "เฝ้าระวัง", "label": "ค่าขอบพอดี 120"},
            {"args": [61], "expect": "เฝ้าระวัง"},
            {"args": [60], "expect": "ปกติ", "label": "ค่าขอบพอดี 60"},
            {"args": [0], "expect": "ปกติ"},
        ],
        "must_use": ["if"],
        "starter": "def downtime_level(minutes):\n    ...\n",
        "hint": "ไล่เงื่อนไขจากเข้มงวดที่สุดลงมา และระวังค่าขอบ 60 กับ 120 ว่าต้องอยู่ระดับไหน",
        "solution": "def downtime_level(minutes):\n"
                    "    if minutes > 120:\n"
                    "        return \"วิกฤต\"\n"
                    "    if minutes > 60:\n"
                    "        return \"เฝ้าระวัง\"\n"
                    "    return \"ปกติ\"\n",
        "teach": "ชุดทดสอบนี้จงใจใส่ค่าขอบ (60, 120) เพราะบั๊กส่วนใหญ่ของเงื่อนไขซ่อนอยู่ตรงขอบพอดี",
    },
    {
        "id": "e07", "group": "2. เงื่อนไขและลูป", "level": 1, "lesson": "m2l2",
        "title": "รวมยอดด้วยลูป (ห้ามใช้ sum)",
        "prompt": "เขียนฟังก์ชัน `total_downtime(values)` คืนผลรวมของตัวเลขในลิสต์\n\n"
                  "ข้อนี้บังคับให้เขียนลูปเอง **ห้ามใช้ `sum()`** เพื่อฝึกรูปแบบตัวสะสม",
        "kind": "func", "func": "total_downtime",
        "cases": [
            {"args": [[45, 120, 0, 30]], "expect": 195},
            {"args": [[]], "expect": 0, "label": "ลิสต์ว่าง"},
            {"args": [[10]], "expect": 10},
        ],
        "must_use": ["for"], "banned": ["call:sum"],
        "starter": "def total_downtime(values):\n    total = 0\n    ...\n",
        "hint": "เตรียม total = 0 ไว้ก่อนลูป แล้วบวกเพิ่มในลูปด้วย total += v",
        "solution": "def total_downtime(values):\n"
                    "    total = 0\n"
                    "    for v in values:\n"
                    "        total += v\n"
                    "    return total\n",
        "teach": "ตำแหน่งของ total = 0 ต้องอยู่ก่อนลูปเสมอ ถ้าเผลอวางในลูปจะได้แค่ค่าตัวสุดท้าย",
    },
    {
        "id": "e08", "group": "2. เงื่อนไขและลูป", "level": 2, "lesson": "m2l2",
        "title": "นับกะที่หยุดเกินเกณฑ์",
        "prompt": "เขียนฟังก์ชัน `count_over(values, limit)` นับว่ามีกี่ค่าที่ **มากกว่า** limit",
        "kind": "func", "func": "count_over",
        "cases": [
            {"args": [[45, 120, 0, 30, 210], 60], "expect": 2},
            {"args": [[45, 120, 0, 30, 210], 0], "expect": 4},
            {"args": [[], 60], "expect": 0},
            {"args": [[60, 60], 60], "expect": 0, "label": "เท่ากับเกณฑ์พอดี ไม่นับ"},
        ],
        "must_use": ["for"],
        "starter": "def count_over(values, limit):\n    ...\n",
        "hint": "ใช้ตัวนับ n = 0 แล้ว n += 1 เมื่อเข้าเงื่อนไข",
        "solution": "def count_over(values, limit):\n"
                    "    n = 0\n"
                    "    for v in values:\n"
                    "        if v > limit:\n"
                    "            n += 1\n"
                    "    return n\n",
        "teach": "การนับแบบมีเงื่อนไขคือรูปแบบเดียวกับการรวมยอด เปลี่ยนจากบวกค่าเป็นบวกหนึ่ง",
    },
    {
        "id": "e09", "group": "2. เงื่อนไขและลูป", "level": 2, "lesson": "m2l2",
        "title": "หาเครื่องที่หยุดนานที่สุด",
        "prompt": "เขียนฟังก์ชัน `worst_machine(records)` รับลิสต์ของ `[รหัสเครื่อง, นาที]` "
                  "คืนรหัสเครื่องที่หยุดนานที่สุด ถ้าลิสต์ว่างให้คืน `\"\"`\n\n"
                  "ถ้ามีค่าสูงสุดเท่ากันหลายตัว ให้คืนตัวที่พบก่อน",
        "kind": "func", "func": "worst_machine",
        "cases": [
            {"args": [[["M01", 45], ["M03", 120], ["M06", 0]]], "expect": "M03"},
            {"args": [[["M01", 45]]], "expect": "M01"},
            {"args": [[]], "expect": ""},
            {"args": [[["M01", 90], ["M03", 90]]], "expect": "M01", "label": "เสมอกัน เอาตัวแรก"},
        ],
        "must_use": ["for"],
        "starter": "def worst_machine(records):\n    ...\n",
        "hint": "เก็บค่าสูงสุดที่เจอไว้ในตัวแปร แล้วเทียบทีละรายการ ใช้ > (ไม่ใช่ >=) เพื่อให้ตัวแรกชนะเมื่อเสมอ",
        "solution": "def worst_machine(records):\n"
                    "    best_code, best = \"\", -1\n"
                    "    for code, minutes in records:\n"
                    "        if minutes > best:\n"
                    "            best_code, best = code, minutes\n"
                    "    return best_code\n",
        "teach": "เลือก > หรือ >= ตัดสินว่าใครชนะเมื่อค่าเท่ากัน — รายละเอียดเล็กที่เปลี่ยนผลรายงานได้",
    },
    {
        "id": "e10", "group": "2. เงื่อนไขและลูป", "level": 2, "lesson": "m2l3",
        "title": "อีกกี่วันต้องสั่งอะไหล่",
        "prompt": "เขียนฟังก์ชัน `days_to_reorder(stock, usage, reorder_point)` "
                  "คืนจำนวนวันที่ผ่านไปจนสต๊อกเหลือ **น้อยกว่าหรือเท่ากับ** จุดสั่งซื้อ\n\n"
                  "ถ้าสต๊อกตอนนี้ถึงจุดสั่งซื้อแล้วให้คืน 0",
        "kind": "func", "func": "days_to_reorder",
        "cases": [
            {"args": [500, 45, 100], "expect": 9},
            {"args": [100, 45, 100], "expect": 0, "label": "ถึงจุดสั่งซื้อแล้ว"},
            {"args": [200, 100, 50], "expect": 2},
        ],
        "must_use": ["while"], "timeout": 5,
        "starter": "def days_to_reorder(stock, usage, reorder_point):\n    days = 0\n    ...\n",
        "hint": "วน while ตราบใดที่ stock ยังมากกว่า reorder_point แล้วลดสต๊อกพร้อมนับวันในลูป",
        "solution": "def days_to_reorder(stock, usage, reorder_point):\n"
                    "    days = 0\n"
                    "    while stock > reorder_point:\n"
                    "        stock -= usage\n"
                    "        days += 1\n"
                    "    return days\n",
        "teach": "ทุก while ต้องมีบรรทัดที่ทำให้เงื่อนไขเข้าใกล้เท็จ ไม่งั้นคือลูปไม่รู้จบ",
    },
    {
        "id": "e11", "group": "2. เงื่อนไขและลูป", "level": 3, "lesson": "m2l2",
        "title": "ยอดสะสมรายวัน",
        "prompt": "เขียนฟังก์ชัน `running_total(values)` คืนลิสต์ยอดสะสม\n\n"
                  "เช่น `[45, 30, 20]` → `[45, 75, 95]`",
        "kind": "func", "func": "running_total",
        "cases": [
            {"args": [[45, 30, 20]], "expect": [45, 75, 95]},
            {"args": [[]], "expect": []},
            {"args": [[10, 0, 5]], "expect": [10, 10, 15]},
        ],
        "must_use": ["for"],
        "starter": "def running_total(values):\n    ...\n",
        "hint": "ใช้ตัวสะสมหนึ่งตัว และลิสต์ผลลัพธ์อีกหนึ่ง เพิ่มค่าสะสมลงลิสต์ทุกรอบด้วย .append()",
        "solution": "def running_total(values):\n"
                    "    out = []\n"
                    "    total = 0\n"
                    "    for v in values:\n"
                    "        total += v\n"
                    "        out.append(total)\n"
                    "    return out\n",
        "teach": "ยอดสะสมคือฐานของกราฟแนวโน้มสะสมที่ใช้ดูว่า downtime เดือนนี้จะทะลุเป้าหรือไม่",
    },

    # =======================================================================
    # 3. โครงสร้างข้อมูล
    # =======================================================================
    {
        "id": "e12", "group": "3. โครงสร้างข้อมูล", "level": 1, "lesson": "m3l4",
        "title": "รายชื่อเครื่องที่ไม่ซ้ำ",
        "prompt": "เขียนฟังก์ชัน `unique_machines(items)` คืน **ลิสต์** ของรหัสเครื่องที่ไม่ซ้ำ เรียงจากน้อยไปมาก",
        "kind": "func", "func": "unique_machines",
        "cases": [
            {"args": [["M03", "M01", "M03", "M06"]], "expect": ["M01", "M03", "M06"]},
            {"args": [[]], "expect": []},
            {"args": [["M01", "M01"]], "expect": ["M01"]},
        ],
        "starter": "def unique_machines(items):\n    ...\n",
        "hint": "set() ตัดค่าซ้ำให้ แล้ว sorted() คืนลิสต์ที่เรียงแล้ว",
        "solution": "def unique_machines(items):\n"
                    "    return sorted(set(items))\n",
        "teach": "sorted(set(x)) คือสำนวนมาตรฐานสำหรับ 'ค่าที่ไม่ซ้ำและเรียงแล้ว'",
    },
    {
        "id": "e13", "group": "3. โครงสร้างข้อมูล", "level": 2, "lesson": "m3l3",
        "title": "รวม downtime แยกตามเครื่อง",
        "prompt": "เขียนฟังก์ชัน `sum_by_machine(records)` รับลิสต์ของ `[รหัสเครื่อง, นาที]` "
                  "คืน **dict** ที่จับคู่รหัสเครื่องกับผลรวมนาที",
        "kind": "func", "func": "sum_by_machine",
        "cases": [
            {"args": [[["M01", 45], ["M03", 120], ["M01", 30]]],
             "expect": {"M01": 75, "M03": 120}},
            {"args": [[]], "expect": {}},
            {"args": [[["M06", 0]]], "expect": {"M06": 0}},
        ],
        "must_use": ["for"],
        "starter": "def sum_by_machine(records):\n    totals = {}\n    ...\n",
        "hint": "ใช้ totals[code] = totals.get(code, 0) + minutes",
        "solution": "def sum_by_machine(records):\n"
                    "    totals = {}\n"
                    "    for code, minutes in records:\n"
                    "        totals[code] = totals.get(code, 0) + minutes\n"
                    "    return totals\n",
        "teach": "สำนวน .get(key, 0) + value คือการสรุปยอดแบบวนข้อมูลรอบเดียว เร็วกว่าลูปซ้อนมาก",
    },
    {
        "id": "e14", "group": "3. โครงสร้างข้อมูล", "level": 2, "lesson": "m3l3",
        "title": "นับสาเหตุการเสีย",
        "prompt": "เขียนฟังก์ชัน `count_causes(causes)` รับลิสต์ข้อความสาเหตุ "
                  "คืน dict ของสาเหตุกับจำนวนครั้ง",
        "kind": "func", "func": "count_causes",
        "cases": [
            {"args": [["สายพานขาด", "มอเตอร์ร้อน", "สายพานขาด"]],
             "expect": {"สายพานขาด": 2, "มอเตอร์ร้อน": 1}},
            {"args": [[]], "expect": {}},
        ],
        "starter": "def count_causes(causes):\n    ...\n",
        "hint": "ทำแบบเดียวกับข้อที่แล้ว แต่บวกทีละ 1 (หรือใช้ collections.Counter แล้วแปลงเป็น dict)",
        "solution": "def count_causes(causes):\n"
                    "    result = {}\n"
                    "    for c in causes:\n"
                    "        result[c] = result.get(c, 0) + 1\n"
                    "    return result\n",
        "teach": "การนับความถี่คือขั้นแรกของการวิเคราะห์พาเรโต — หาสาเหตุ 20% ที่ทำให้เสียเวลา 80%",
    },
    {
        "id": "e15", "group": "3. โครงสร้างข้อมูล", "level": 3, "lesson": "m3l1",
        "title": "จัดอันดับเครื่องที่หยุดนานสุด",
        "prompt": "เขียนฟังก์ชัน `top_machines(records, n)` รับลิสต์ `[รหัส, นาที]` "
                  "คืนลิสต์ของ **รหัสเครื่อง** n อันดับแรกเรียงจากนาทีมากไปน้อย",
        "kind": "func", "func": "top_machines",
        "cases": [
            {"args": [[["M01", 45], ["M03", 120], ["M06", 0], ["M08", 75]], 3],
             "expect": ["M03", "M08", "M01"]},
            {"args": [[["M01", 45]], 3], "expect": ["M01"], "label": "ขอมากกว่าที่มี"},
            {"args": [[], 3], "expect": []},
        ],
        "starter": "def top_machines(records, n):\n    ...\n",
        "hint": "sorted(records, key=lambda r: r[1], reverse=True) แล้วตัดด้วย [:n] และดึงเฉพาะช่องแรก",
        "solution": "def top_machines(records, n):\n"
                    "    ranked = sorted(records, key=lambda r: r[1], reverse=True)\n"
                    "    return [code for code, _minutes in ranked[:n]]\n",
        "teach": "key= คือหัวใจของการเรียงข้อมูลจริง และ [:n] ปลอดภัยเสมอแม้ข้อมูลน้อยกว่า n",
    },
    {
        "id": "e16", "group": "3. โครงสร้างข้อมูล", "level": 2, "lesson": "m3l4",
        "title": "PM ที่ยังไม่ได้ทำ",
        "prompt": "เขียนฟังก์ชัน `pm_pending(planned, done)` รับลิสต์เครื่องที่วางแผน PM "
                  "และลิสต์ที่ทำแล้ว คืนลิสต์เครื่องที่ยังไม่ได้ทำ เรียงจากน้อยไปมาก",
        "kind": "func", "func": "pm_pending",
        "cases": [
            {"args": [["M01", "M03", "M06", "M08"], ["M01", "M06"]], "expect": ["M03", "M08"]},
            {"args": [["M01"], ["M01"]], "expect": []},
            {"args": [["M01", "M03"], []], "expect": ["M01", "M03"]},
            {"args": [["M01"], ["M01", "M99"]], "expect": [], "label": "มีของที่ทำนอกแผน"},
        ],
        "starter": "def pm_pending(planned, done):\n    ...\n",
        "hint": "แปลงทั้งสองเป็น set แล้วลบกัน จากนั้น sorted()",
        "solution": "def pm_pending(planned, done):\n"
                    "    return sorted(set(planned) - set(done))\n",
        "teach": "การลบ set คือวิธีคำนวณ PM Compliance ที่สั้นและถูกที่สุด แทนลูปซ้อนหลายสิบบรรทัด",
    },
    {
        "id": "e17", "group": "3. โครงสร้างข้อมูล", "level": 3, "lesson": "m3l4",
        "title": "กรองด้วย comprehension",
        "prompt": "เขียนฟังก์ชัน `over_limit(values, limit)` คืนลิสต์เฉพาะค่าที่มากกว่า limit\n\n"
                  "ข้อนี้บังคับให้เขียนด้วย **comprehension** (ห้ามใช้ลูป for ธรรมดา)",
        "kind": "func", "func": "over_limit",
        "cases": [
            {"args": [[45, 120, 0, 210], 60], "expect": [120, 210]},
            {"args": [[], 60], "expect": []},
            {"args": [[10, 20], 60], "expect": []},
        ],
        "must_use": ["comprehension"], "banned": ["for"],
        "starter": "def over_limit(values, limit):\n    return [...]\n",
        "hint": "รูปแบบคือ [x for x in values if เงื่อนไข] — ระบบมองว่านี่ไม่ใช่ลูป for ธรรมดา",
        "solution": "def over_limit(values, limit):\n"
                    "    return [v for v in values if v > limit]\n",
        "teach": "comprehension เหมาะกับการกรอง/แปลงตรง ๆ ถ้าเริ่มซับซ้อนให้กลับไปเขียนลูปที่อ่านง่ายกว่า",
    },

    # =======================================================================
    # 4. ฟังก์ชัน
    # =======================================================================
    {
        "id": "e18", "group": "4. ฟังก์ชัน", "level": 3, "lesson": "m4l4",
        "title": "คำนวณ OEE เต็มสูตร",
        "prompt": "เขียนฟังก์ชัน `oee(planned, downtime, good, reject, ideal_rate=1.2)` คืนค่า OEE (0-1)\n\n"
                  "สูตร\n"
                  "* `run = planned - downtime`\n"
                  "* `A = run / planned`\n"
                  "* `P = (good + reject) / (run * ideal_rate)` แต่ไม่ให้เกิน 1.0\n"
                  "* `Q = good / (good + reject)`\n"
                  "* `OEE = A * P * Q`\n\n"
                  "ถ้า `run <= 0` หรือ `planned <= 0` หรือผลิตได้ 0 ชิ้น ให้คืน `0.0`",
        "kind": "func", "func": "oee", "tol": 1e-6,
        "cases": [
            {"args": [480, 45, 380, 20], "expect": 0.6597222222222222},
            {"args": [480, 0, 576, 0], "expect": 1.0, "label": "สมบูรณ์แบบ"},
            {"args": [480, 480, 100, 0], "expect": 0.0, "label": "ไม่ได้เดินเลย"},
            {"args": [480, 45, 0, 0], "expect": 0.0, "label": "ไม่ได้ผลิตเลย"},
            {"args": [0, 0, 10, 0], "expect": 0.0},
            {"args": [480, 45, 380, 20, 1.5], "expect": 0.5277777777777777, "label": "เปลี่ยนความเร็วมาตรฐาน"},
        ],
        "starter": "def oee(planned, downtime, good, reject, ideal_rate=1.2):\n    ...\n",
        "hint": "ใช้ min(ค่า, 1.0) เพื่อจำกัด P ไม่ให้เกิน 100% และตรวจกรณีผิดปกติก่อนคำนวณ",
        "solution": "def oee(planned, downtime, good, reject, ideal_rate=1.2):\n"
                    "    run = planned - downtime\n"
                    "    total = good + reject\n"
                    "    if planned <= 0 or run <= 0 or total == 0:\n"
                    "        return 0.0\n"
                    "    a = run / planned\n"
                    "    p = min(total / (run * ideal_rate), 1.0)\n"
                    "    q = good / total\n"
                    "    return a * p * q\n",
        "teach": "การจำกัด P ไม่ให้เกิน 100% ป้องกันค่า OEE เกินจริงเมื่อความเร็วมาตรฐานตั้งไว้ต่ำเกินไป",
    },
    {
        "id": "e19", "group": "4. ฟังก์ชัน", "level": 2, "lesson": "m3l2",
        "title": "คืนค่าหลายค่าพร้อมกัน",
        "prompt": "เขียนฟังก์ชัน `summary(values)` คืน tuple `(ต่ำสุด, สูงสุด, เฉลี่ยปัดทศนิยม 2 ตำแหน่ง)`\n\n"
                  "ถ้าลิสต์ว่างให้คืน `(0, 0, 0.0)`",
        "kind": "func", "func": "summary",
        "cases": [
            {"args": [[45, 120, 0, 30]], "expect": [0, 120, 48.75]},
            {"args": [[10]], "expect": [10, 10, 10.0]},
            {"args": [[]], "expect": [0, 0, 0.0]},
            {"args": [[1, 2]], "expect": [1, 2, 1.5]},
        ],
        "starter": "def summary(values):\n    ...\n",
        "hint": "return a, b, c ได้เลยโดยไม่ต้องใส่วงเล็บ และใช้ round(x, 2) กับค่าเฉลี่ย",
        "solution": "def summary(values):\n"
                    "    if not values:\n"
                    "        return 0, 0, 0.0\n"
                    "    return min(values), max(values), round(sum(values) / len(values), 2)\n",
        "teach": "การคืนหลายค่าคือ tuple โดยปริยาย ฝั่งเรียกใช้จึงแตกค่าได้ทันที: lo, hi, avg = summary(...)",
    },
    {
        "id": "e20", "group": "4. ฟังก์ชัน", "level": 2, "lesson": "m6l2",
        "title": "หารอย่างปลอดภัย",
        "prompt": "เขียนฟังก์ชัน `safe_div(a, b, default=0.0)` คืน `a / b` "
                  "แต่ถ้า `b` เป็น 0 ให้คืนค่า `default` แทนที่จะพัง",
        "kind": "func", "func": "safe_div",
        "cases": [
            {"args": [10, 4], "expect": 2.5},
            {"args": [10, 0], "expect": 0.0},
            {"args": [10, 0], "kwargs": {"default": -1}, "expect": -1},
            {"args": [0, 5], "expect": 0.0},
        ],
        "starter": "def safe_div(a, b, default=0.0):\n    ...\n",
        "hint": "จะเช็ก if b == 0 ก่อน หรือใช้ try/except ZeroDivisionError ก็ได้ทั้งคู่",
        "solution": "def safe_div(a, b, default=0.0):\n"
                    "    if b == 0:\n"
                    "        return default\n"
                    "    return a / b\n",
        "teach": "ฟังก์ชันเล็ก ๆ แบบนี้ใช้ครอบทุกจุดที่หารในรายงาน ทำให้ข้อมูลกะที่ไม่มีการผลิตไม่ทำให้ทั้งไฟล์ล้ม",
    },
    {
        "id": "e21", "group": "4. ฟังก์ชัน", "level": 3, "lesson": "m4l2",
        "title": "ฟังก์ชันที่ไม่แก้ของที่รับมา",
        "prompt": "เขียนฟังก์ชัน `add_machine(items, code)` คืน **ลิสต์ใหม่** ที่มี code ต่อท้าย "
                  "โดยลิสต์เดิมต้องไม่ถูกแก้\n\nข้อนี้ห้ามใช้ `.append()`",
        "kind": "func", "func": "add_machine",
        "cases": [
            {"args": [["M01"], "M03"], "expect": ["M01", "M03"]},
            {"args": [[], "M01"], "expect": ["M01"]},
        ],
        "banned": ["method:append", "method:extend", "method:insert"],
        "starter": "def add_machine(items, code):\n    ...\n",
        "hint": "การบวกลิสต์สองก้อนสร้างลิสต์ใหม่เสมอ: items + [code]",
        "solution": "def add_machine(items, code):\n"
                    "    return items + [code]\n",
        "teach": "ฟังก์ชันที่ไม่แก้ข้อมูลที่รับเข้ามา (pure) ทำให้ตามหาต้นตอบั๊กง่ายกว่ามาก",
    },
    {
        "id": "e22", "group": "4. ฟังก์ชัน", "level": 3, "lesson": "m4l1",
        "title": "ประกอบฟังก์ชันเข้าด้วยกัน",
        "prompt": "เขียนฟังก์ชัน `classify(records)` รับลิสต์ `[รหัส, นาที]` "
                  "คืน dict ที่จับคู่รหัสเครื่องกับระดับความรุนแรง\n\n"
                  "เกณฑ์เดียวกับข้อ e06: มากกว่า 120 = วิกฤต, มากกว่า 60 = เฝ้าระวัง, นอกนั้น = ปกติ\n\n"
                  "**บังคับให้แยกเกณฑ์ออกเป็นฟังก์ชันย่อยชื่อ `level_of(minutes)` แล้วเรียกใช้**",
        "kind": "func", "func": "classify",
        "cases": [
            {"args": [[["M01", 45], ["M03", 200], ["M06", 90]]],
             "expect": {"M01": "ปกติ", "M03": "วิกฤต", "M06": "เฝ้าระวัง"}},
            {"args": [[]], "expect": {}},
        ],
        "must_use": ["def", "call:level_of"],
        "starter": "def level_of(minutes):\n    ...\n\n\ndef classify(records):\n    ...\n",
        "hint": "เขียน level_of ให้เสร็จก่อน แล้ว classify แค่วนลูปเรียกใช้",
        "solution": "def level_of(minutes):\n"
                    "    if minutes > 120:\n"
                    "        return \"วิกฤต\"\n"
                    "    if minutes > 60:\n"
                    "        return \"เฝ้าระวัง\"\n"
                    "    return \"ปกติ\"\n\n\n"
                    "def classify(records):\n"
                    "    return {code: level_of(minutes) for code, minutes in records}\n",
        "teach": "แยกกฎเกณฑ์ออกเป็นฟังก์ชันเดี่ยว ทำให้เปลี่ยนเกณฑ์ทีเดียวแล้วมีผลทุกที่ที่ใช้",
    },

    # =======================================================================
    # 5. ข้อความและไฟล์
    # =======================================================================
    {
        "id": "e23", "group": "5. ข้อความและไฟล์", "level": 2, "lesson": "m5l1",
        "title": "ล้างข้อมูลที่คนกรอกมา",
        "prompt": "เขียนฟังก์ชัน `clean_row(raw)` รับข้อความรูปแบบ `\" m01 , Line A , 45 \"` "
                  "คืน tuple `(\"M01\", \"Line A\", 45)`\n\n"
                  "รหัสเครื่องต้องเป็นตัวพิมพ์ใหญ่ ตัดช่องว่างหัวท้ายทุกช่อง และนาทีต้องเป็นจำนวนเต็ม",
        "kind": "func", "func": "clean_row",
        "cases": [
            {"args": ["  m01 , Line A , 45 "], "expect": ["M01", "Line A", 45]},
            {"args": ["M03,Line A,120"], "expect": ["M03", "Line A", 120]},
            {"args": [" m06 , Line B , 0 "], "expect": ["M06", "Line B", 0]},
        ],
        "starter": "def clean_row(raw):\n    ...\n",
        "hint": "split(\",\") ก่อน แล้ว strip() ทีละช่อง จากนั้น upper() และ int()",
        "solution": "def clean_row(raw):\n"
                    "    parts = [p.strip() for p in raw.split(\",\")]\n"
                    "    return parts[0].upper(), parts[1], int(parts[2])\n",
        "teach": "การทำความสะอาดตั้งแต่ตอนอ่านข้อมูลเข้า ทำให้โค้ดส่วนคำนวณไม่ต้องเผื่อข้อมูลสกปรก",
    },
    {
        "id": "e24", "group": "5. ข้อความและไฟล์", "level": 2, "lesson": "m5l1",
        "title": "แยกส่วนบรรทัดล็อก",
        "prompt": "เขียนฟังก์ชัน `parse_log(line)` รับบรรทัดล็อกรูปแบบ\n\n"
                  "`\"2026-06-01 09:40 M01 ALARM มอเตอร์ร้อนเกิน\"`\n\n"
                  "คืน tuple `(\"2026-06-01\", \"09:40\", \"M01\", \"ALARM มอเตอร์ร้อนเกิน\")` "
                  "— ส่วนสุดท้ายต้องเก็บข้อความที่เหลือทั้งหมดไว้เป็นก้อนเดียว",
        "kind": "func", "func": "parse_log",
        "cases": [
            {"args": ["2026-06-01 09:40 M01 ALARM มอเตอร์ร้อนเกิน"],
             "expect": ["2026-06-01", "09:40", "M01", "ALARM มอเตอร์ร้อนเกิน"]},
            {"args": ["2026-06-01 07:12 M01 START"],
             "expect": ["2026-06-01", "07:12", "M01", "START"]},
        ],
        "starter": "def parse_log(line):\n    ...\n",
        "hint": "split(\" \", 3) จำกัดการตัดไว้ 3 ครั้ง ทำให้ส่วนที่เหลือติดกันเป็นก้อนเดียว",
        "solution": "def parse_log(line):\n"
                    "    date, time, machine, event = line.split(\" \", 3)\n"
                    "    return date, time, machine, event\n",
        "teach": "การจำกัดจำนวนครั้งของ split คือเครื่องมือหลักในการแยกล็อกที่ส่วนท้ายมีเว้นวรรค",
    },
    {
        "id": "e25", "group": "5. ข้อความและไฟล์", "level": 3, "lesson": "m5l2",
        "title": "นับ ALARM จากไฟล์ล็อก",
        "prompt": "ไฟล์ `machine_log.txt` อยู่ในโฟลเดอร์เดียวกับโค้ดของคุณแล้ว\n\n"
                  "เขียนฟังก์ชัน `count_alarms()` อ่านไฟล์นั้นแล้วคืน dict "
                  "ที่จับคู่รหัสเครื่องกับจำนวนบรรทัดที่มีคำว่า `ALARM`",
        "kind": "func", "func": "count_alarms", "files": LOG,
        "cases": [
            {"args": [], "expect": {"M01": 1, "M03": 2, "M06": 1}, "label": "ทั้งไฟล์"},
        ],
        "starter": "def count_alarms():\n"
                   "    counts = {}\n"
                   "    with open(\"machine_log.txt\", encoding=\"utf-8\") as fh:\n"
                   "        ...\n"
                   "    return counts\n",
        "hint": "วนทีละบรรทัด ถ้ามีคำว่า ALARM ให้แยกรหัสเครื่องออกมาด้วย split แล้วนับด้วย .get()",
        "solution": "def count_alarms():\n"
                    "    counts = {}\n"
                    "    with open(\"machine_log.txt\", encoding=\"utf-8\") as fh:\n"
                    "        for line in fh:\n"
                    "            if \"ALARM\" not in line:\n"
                    "                continue\n"
                    "            machine = line.split()[2]\n"
                    "            counts[machine] = counts.get(machine, 0) + 1\n"
                    "    return counts\n",
        "teach": "อ่านไฟล์ทีละบรรทัดใน with ใช้หน่วยความจำน้อยและปิดไฟล์ให้เองแม้เกิดข้อผิดพลาด",
    },
    {
        "id": "e26", "group": "5. ข้อความและไฟล์", "level": 3, "lesson": "m5l3",
        "title": "รวม downtime จาก CSV (ไม่ใช้ pandas)",
        "prompt": "ไฟล์ `production.csv` อยู่ในโฟลเดอร์เดียวกับโค้ดแล้ว "
                  "(คอลัมน์: date, machine_id, line, shift, planned_min, downtime_min, good_qty, reject_qty)\n\n"
                  "เขียนฟังก์ชัน `total_downtime()` คืนผลรวมของคอลัมน์ `downtime_min` เป็นจำนวนเต็ม\n\n"
                  "ข้อนี้ห้ามใช้ pandas — ให้ใช้โมดูล `csv`",
        "kind": "func", "func": "total_downtime", "files": CSV,
        "cases": [{"args": [], "expect": 9642}],
        "banned": ["import:pandas"],
        "starter": "import csv\n\n\ndef total_downtime():\n    ...\n",
        "hint": "csv.DictReader คืนค่าทุกช่องเป็นข้อความ ต้อง int() ก่อนบวก",
        "solution": "import csv\n\n\n"
                    "def total_downtime():\n"
                    "    total = 0\n"
                    "    with open(\"production.csv\", encoding=\"utf-8\", newline=\"\") as fh:\n"
                    "        for row in csv.DictReader(fh):\n"
                    "            total += int(row[\"downtime_min\"])\n"
                    "    return total\n",
        "teach": "รู้วิธีอ่าน CSV ด้วยมือก่อน ทำให้เข้าใจว่าตอน pandas อ่านให้ มันทำอะไรแทนเราบ้าง",
    },
    {
        "id": "e27", "group": "5. ข้อความและไฟล์", "level": 4, "lesson": "m5l3",
        "title": "สรุป downtime รายสายการผลิต (ไม่ใช้ pandas)",
        "prompt": "จาก `production.csv` เขียนฟังก์ชัน `line_totals()` "
                  "คืน dict ที่จับคู่ชื่อสายการผลิต (คอลัมน์ `line`) กับผลรวม `downtime_min`",
        "kind": "func", "func": "line_totals", "files": CSV,
        "cases": [{"args": [], "expect": {"Line A": 3543, "Line B": 3870, "Line C": 2229}}],
        "banned": ["import:pandas"],
        "starter": "import csv\n\n\ndef line_totals():\n    ...\n",
        "hint": "รวมสองสำนวนที่ฝึกมาแล้ว: อ่าน CSV ทีละแถว + สรุปยอดด้วย dict.get()",
        "solution": "import csv\n\n\n"
                    "def line_totals():\n"
                    "    totals = {}\n"
                    "    with open(\"production.csv\", encoding=\"utf-8\", newline=\"\") as fh:\n"
                    "        for row in csv.DictReader(fh):\n"
                    "            line = row[\"line\"]\n"
                    "            totals[line] = totals.get(line, 0) + int(row[\"downtime_min\"])\n"
                    "    return totals\n",
        "teach": "นี่คือ groupby ที่เขียนด้วยมือ — บทต่อไปจะเห็นว่า pandas ทำสิ่งเดียวกันในบรรทัดเดียว",
    },

    # =======================================================================
    # 6. pandas
    # =======================================================================
    {
        "id": "e28", "group": "6. pandas", "level": 2, "lesson": "m7l2",
        "title": "รวม downtime ด้วย pandas",
        "prompt": "อ่าน `production.csv` ด้วย pandas แล้วเขียนฟังก์ชัน `total_downtime()` "
                  "คืนผลรวมคอลัมน์ `downtime_min` เป็น **จำนวนเต็ม**",
        "kind": "func", "func": "total_downtime", "files": CSV,
        "cases": [{"args": [], "expect": 9642}],
        "must_use": ["import:pandas"],
        "starter": "import pandas as pd\n\n\ndef total_downtime():\n    ...\n",
        "hint": "df[\"downtime_min\"].sum() คืนชนิดของ numpy ต้องครอบด้วย int() ก่อนคืนค่า",
        "solution": "import pandas as pd\n\n\n"
                    "def total_downtime():\n"
                    "    df = pd.read_csv(\"production.csv\")\n"
                    "    return int(df[\"downtime_min\"].sum())\n",
        "teach": "ค่าที่ได้จาก pandas เป็นชนิดของ numpy การครอบ int()/float() ทำให้ส่งต่อไปยังส่วนอื่นได้ปลอดภัย",
    },
    {
        "id": "e29", "group": "6. pandas", "level": 2, "lesson": "m7l4",
        "title": "เครื่องที่หยุดนานที่สุด",
        "prompt": "จาก `production.csv` เขียนฟังก์ชัน `worst_machine()` "
                  "คืนรหัสเครื่อง (ข้อความ) ที่มี downtime รวมมากที่สุด",
        "kind": "func", "func": "worst_machine", "files": CSV,
        "cases": [{"args": [], "expect": "M04"}],
        "must_use": ["import:pandas"],
        "starter": "import pandas as pd\n\n\ndef worst_machine():\n    ...\n",
        "hint": "groupby(...).sum() แล้วใช้ .idxmax() ซึ่งคืน 'ดัชนีของค่าสูงสุด' = รหัสเครื่อง",
        "solution": "import pandas as pd\n\n\n"
                    "def worst_machine():\n"
                    "    df = pd.read_csv(\"production.csv\")\n"
                    "    return df.groupby(\"machine_id\")[\"downtime_min\"].sum().idxmax()\n",
        "teach": "idxmax() คืนดัชนี ส่วน max() คืนตัวเลข — เลือกผิดตัวคือบั๊กที่เจอบ่อยตอนทำรายงานจัดอันดับ",
    },
    {
        "id": "e30", "group": "6. pandas", "level": 3, "lesson": "m7l4",
        "title": "สรุปรายสายการผลิต",
        "prompt": "จาก `production.csv` เขียนฟังก์ชัน `line_totals()` "
                  "คืน **dict** จับคู่ชื่อสายการผลิตกับผลรวม downtime (เป็นจำนวนเต็ม)",
        "kind": "func", "func": "line_totals", "files": CSV,
        "cases": [{"args": [], "expect": {"Line A": 3543, "Line B": 3870, "Line C": 2229}}],
        "must_use": ["import:pandas"],
        "starter": "import pandas as pd\n\n\ndef line_totals():\n    ...\n",
        "hint": "Series มีเมท็อด .to_dict() และแปลงชนิดทั้งคอลัมน์ได้ด้วย .astype(int)",
        "solution": "import pandas as pd\n\n\n"
                    "def line_totals():\n"
                    "    df = pd.read_csv(\"production.csv\")\n"
                    "    return df.groupby(\"line\")[\"downtime_min\"].sum().astype(int).to_dict()\n",
        "teach": "เทียบกับข้อ e27 ที่เขียนเองด้วย csv — ผลเหมือนกันทุกประการ แต่สั้นกว่าและเร็วกว่ามาก",
    },
    {
        "id": "e31", "group": "6. pandas", "level": 3, "lesson": "m7l4",
        "title": "downtime เฉลี่ยต่อกะ",
        "prompt": "จาก `production.csv` เขียนฟังก์ชัน `avg_by_shift()` "
                  "คืน dict จับคู่ชื่อกะกับ downtime **เฉลี่ยต่อกะ ปัดทศนิยม 1 ตำแหน่ง**",
        "kind": "func", "func": "avg_by_shift", "files": CSV, "tol": 1e-9,
        "cases": [{"args": [], "expect": {"กะเช้า": 21.8, "กะบ่าย": 24.5}}],
        "must_use": ["import:pandas"],
        "starter": "import pandas as pd\n\n\ndef avg_by_shift():\n    ...\n",
        "hint": ".mean() แล้ว .round(1) จากนั้น .to_dict()",
        "solution": "import pandas as pd\n\n\n"
                    "def avg_by_shift():\n"
                    "    df = pd.read_csv(\"production.csv\")\n"
                    "    return df.groupby(\"shift\")[\"downtime_min\"].mean().round(1).to_dict()\n",
        "teach": "ค่าเฉลี่ยต่อกะเทียบกันได้ตรงกว่ายอดรวม เพราะแต่ละกะมีจำนวนครั้งไม่เท่ากัน",
    },
    {
        "id": "e32", "group": "6. pandas", "level": 3, "lesson": "m7l4",
        "title": "สาเหตุการเสียที่พบบ่อยที่สุด",
        "prompt": "ไฟล์ `breakdown.csv` (คอลัมน์: bd_id, date, machine_id, cause, minutes, technician) "
                  "อยู่ในโฟลเดอร์แล้ว\n\nเขียนฟังก์ชัน `top3_causes()` "
                  "คืน **ลิสต์** ของสาเหตุ 3 อันดับแรกที่เกิดบ่อยที่สุด เรียงจากมากไปน้อย",
        "kind": "func", "func": "top3_causes", "files": CSV_ALL,
        "cases": [{"args": [], "expect": ["หัวฉีดอุดตัน", "โปรแกรมค้าง", "ใบมีดสึก"]}],
        "must_use": ["import:pandas"],
        "starter": "import pandas as pd\n\n\ndef top3_causes():\n    ...\n",
        "hint": "value_counts() เรียงจากมากไปน้อยให้อยู่แล้ว ใช้ .head(3).index แล้วแปลงเป็น list",
        "solution": "import pandas as pd\n\n\n"
                    "def top3_causes():\n"
                    "    df = pd.read_csv(\"breakdown.csv\")\n"
                    "    return list(df[\"cause\"].value_counts().head(3).index)\n",
        "teach": "value_counts() คือทางลัดของ groupby().size() ที่เรียงผลให้เรียบร้อยแล้ว",
    },
    {
        "id": "e33", "group": "6. pandas", "level": 4, "lesson": "m7l5",
        "title": "เครื่องเก่ากับเครื่องใหม่ต่างกันแค่ไหน",
        "prompt": "รวม `production.csv` กับ `machines.csv` (คีย์ `machine_id`) แล้วเขียนฟังก์ชัน "
                  "`old_vs_new()` คืน tuple `(เฉลี่ยเครื่องเก่า, เฉลี่ยเครื่องใหม่)` "
                  "ของ downtime ต่อกะ ปัดทศนิยม 1 ตำแหน่ง\n\n"
                  "นิยาม: เครื่องเก่า = `install_year < 2018`, เครื่องใหม่ = `install_year >= 2018`",
        "kind": "func", "func": "old_vs_new", "files": CSV_ALL, "tol": 1e-9,
        "cases": [{"args": [], "expect": [30.1, 19.0]}],
        "must_use": ["import:pandas"],
        "starter": "import pandas as pd\n\n\ndef old_vs_new():\n    ...\n",
        "hint": "merge ก่อน แล้วกรองสองชุดด้วยเงื่อนไข install_year จากนั้น .mean() แล้ว round(x, 1)",
        "solution": "import pandas as pd\n\n\n"
                    "def old_vs_new():\n"
                    "    prod = pd.read_csv(\"production.csv\")\n"
                    "    machines = pd.read_csv(\"machines.csv\")\n"
                    "    df = prod.merge(machines, on=\"machine_id\", how=\"left\")\n"
                    "    old = df[df[\"install_year\"] < 2018][\"downtime_min\"].mean()\n"
                    "    new = df[df[\"install_year\"] >= 2018][\"downtime_min\"].mean()\n"
                    "    return round(float(old), 1), round(float(new), 1)\n",
        "teach": "ตัวเลขนี้คือหลักฐานเชิงปริมาณที่ใช้เสนอของบเปลี่ยนเครื่อง — แรงกว่าความรู้สึกว่า 'เครื่องเก่ามันเสียบ่อย'",
    },

    # =======================================================================
    # 7. โจทย์งานจริง
    # =======================================================================
    {
        "id": "p01", "group": "7. โจทย์งานจริง", "level": 4, "lesson": "m7l4",
        "title": "ตาราง OEE รายเครื่องทั้งเดือน", "project": True,
        "prompt": "จาก `production.csv` เขียนฟังก์ชัน `oee_by_machine()` "
                  "คืน dict จับคู่รหัสเครื่องกับค่า OEE ของทั้งเดือน **ปัดทศนิยม 4 ตำแหน่ง**\n\n"
                  "คำนวณจากยอดรวมทั้งเดือนของแต่ละเครื่อง (ไม่ใช่ค่าเฉลี่ยของ OEE รายกะ)\n"
                  "* `A = (planned_min รวม - downtime_min รวม) / planned_min รวม`\n"
                  "* `P = (good+reject รวม) / (เวลาเดินจริง * 1.2)` จำกัดไม่เกิน 1.0\n"
                  "* `Q = good รวม / (good+reject รวม)`",
        "kind": "func", "func": "oee_by_machine", "files": CSV, "tol": 1e-9,
        "cases": [{"args": [], "expect": {
            "M01": 0.7942, "M02": 0.7995, "M03": 0.8169, "M04": 0.7928,
            "M05": 0.8194, "M06": 0.8134, "M07": 0.8103, "M08": 0.8122}}],
        "starter": "import pandas as pd\n\n\ndef oee_by_machine():\n    ...\n",
        "hint": "groupby(\"machine_id\").sum() ก่อนเพื่อได้ยอดรวมรายเครื่อง แล้วค่อยคำนวณ A, P, Q "
                "จากคอลัมน์ที่รวมแล้ว ใช้ .clip(upper=1.0) จำกัดค่า P",
        "solution": "import pandas as pd\n\n\n"
                    "def oee_by_machine():\n"
                    "    df = pd.read_csv(\"production.csv\")\n"
                    "    df[\"total_qty\"] = df[\"good_qty\"] + df[\"reject_qty\"]\n"
                    "    g = df.groupby(\"machine_id\").agg(\n"
                    "        planned=(\"planned_min\", \"sum\"),\n"
                    "        down=(\"downtime_min\", \"sum\"),\n"
                    "        good=(\"good_qty\", \"sum\"),\n"
                    "        total=(\"total_qty\", \"sum\"),\n"
                    "    )\n"
                    "    run = g[\"planned\"] - g[\"down\"]\n"
                    "    a = run / g[\"planned\"]\n"
                    "    p = (g[\"total\"] / (run * 1.2)).clip(upper=1.0)\n"
                    "    q = g[\"good\"] / g[\"total\"]\n"
                    "    return (a * p * q).round(4).to_dict()\n",
        "teach": "คำนวณ OEE จากยอดรวมก่อนเสมอ การเฉลี่ย OEE รายกะให้ผลผิด เพราะแต่ละกะมีเวลาเดินไม่เท่ากัน",
    },
    {
        "id": "p02", "group": "7. โจทย์งานจริง", "level": 4, "lesson": "m7l4",
        "title": "อันดับเครื่องที่คุณภาพต่ำสุด", "project": True,
        "prompt": "จาก `production.csv` เขียนฟังก์ชัน `quality_ranking()` "
                  "คืน **ลิสต์รหัสเครื่อง** เรียงจากค่า Quality ต่ำสุดไปสูงสุด\n\n"
                  "`Quality = good_qty รวม / (good_qty + reject_qty) รวม` ของแต่ละเครื่อง",
        "kind": "func", "func": "quality_ranking", "files": CSV,
        "cases": [{"args": [], "expect": ["M03", "M08", "M01", "M07", "M04", "M02", "M05", "M06"]}],
        "starter": "import pandas as pd\n\n\ndef quality_ranking():\n    ...\n",
        "hint": "groupby แล้ว sum ทั้งสองคอลัมน์ คำนวณสัดส่วน จากนั้น sort_values() แล้วเอา .index มาทำเป็นลิสต์",
        "solution": "import pandas as pd\n\n\n"
                    "def quality_ranking():\n"
                    "    df = pd.read_csv(\"production.csv\")\n"
                    "    g = df.groupby(\"machine_id\")[[\"good_qty\", \"reject_qty\"]].sum()\n"
                    "    quality = g[\"good_qty\"] / (g[\"good_qty\"] + g[\"reject_qty\"])\n"
                    "    return list(quality.sort_values().index)\n",
        "teach": "รายการนี้ตอบคำถามว่าควรเข้าไปแก้เครื่องไหนก่อนเมื่อของเสียเป็นปัญหาหลัก",
    },
    {
        "id": "p03", "group": "7. โจทย์งานจริง", "level": 3, "lesson": "m7l4",
        "title": "ภาระงานของช่างแต่ละคน", "project": True,
        "prompt": "จาก `breakdown.csv` เขียนฟังก์ชัน `tech_workload()` "
                  "คืน dict จับคู่ชื่อช่าง (`technician`) กับเวลาซ่อมรวม (`minutes`) เป็นจำนวนเต็ม",
        "kind": "func", "func": "tech_workload", "files": CSV_ALL,
        "cases": [{"args": [], "expect": {"ธนา": 1114, "ปกรณ์": 643, "วิรัช": 940, "สมชาย": 1319}}],
        "starter": "import pandas as pd\n\n\ndef tech_workload():\n    ...\n",
        "hint": "groupby(\"technician\")[\"minutes\"].sum() แล้วแปลงเป็น dict ด้วย .astype(int).to_dict()",
        "solution": "import pandas as pd\n\n\n"
                    "def tech_workload():\n"
                    "    df = pd.read_csv(\"breakdown.csv\")\n"
                    "    return df.groupby(\"technician\")[\"minutes\"].sum().astype(int).to_dict()\n",
        "teach": "ตัวเลขภาระงานจริงคือฐานของการจัดเวรและการขออัตรากำลังเพิ่ม",
    },
    {
        "id": "p04", "group": "7. โจทย์งานจริง", "level": 4, "lesson": "m5l4",
        "title": "เครื่องที่เลยกำหนด PM", "project": True,
        "prompt": "เขียนฟังก์ชัน `pm_overdue(records, today)` โดย\n\n"
                  "* `records` = ลิสต์ของ `[รหัสเครื่อง, วันที่ PM ล่าสุด (YYYY-MM-DD), รอบ PM เป็นวัน]`\n"
                  "* `today` = ข้อความวันที่ปัจจุบัน `YYYY-MM-DD`\n\n"
                  "คืน **ลิสต์รหัสเครื่องที่เลยกำหนดแล้ว** (วันครบกำหนด < วันนี้) เรียงจากที่เลยกำหนดนานที่สุดก่อน",
        "kind": "func", "func": "pm_overdue",
        "cases": [
            {"args": [[["M01", "2026-05-20", 90], ["M03", "2026-03-01", 60],
                       ["M06", "2026-06-01", 30]], "2026-06-15"],
             "expect": ["M03"]},
            {"args": [[["M01", "2026-01-01", 30], ["M03", "2026-03-01", 60]], "2026-06-15"],
             "expect": ["M01", "M03"], "label": "เลยกำหนดสองเครื่อง เรียงตามความนาน"},
            {"args": [[["M01", "2026-06-10", 30]], "2026-06-15"], "expect": []},
        ],
        "must_use": ["import:datetime"],
        "starter": "from datetime import datetime, timedelta\n\n\n"
                   "def pm_overdue(records, today):\n    ...\n",
        "hint": "แปลงข้อความเป็นวันที่ด้วย datetime.strptime(s, \"%Y-%m-%d\").date() "
                "แล้วบวกรอบด้วย timedelta(days=cycle) เก็บคู่ (รหัส, วันครบกำหนด) ไว้เรียงทีหลัง",
        "solution": "from datetime import datetime, timedelta\n\n\n"
                    "def pm_overdue(records, today):\n"
                    "    now = datetime.strptime(today, \"%Y-%m-%d\").date()\n"
                    "    overdue = []\n"
                    "    for code, last_str, cycle in records:\n"
                    "        last = datetime.strptime(last_str, \"%Y-%m-%d\").date()\n"
                    "        due = last + timedelta(days=cycle)\n"
                    "        if due < now:\n"
                    "            overdue.append((due, code))\n"
                    "    return [code for _due, code in sorted(overdue)]\n",
        "teach": "รายการนี้คือหัวใจของรายงาน PM Compliance — เรียงตามวันครบกำหนดทำให้รู้ว่าต้องจัดการอะไรก่อน",
    },
]

EX_BY_ID = {e["id"]: e for e in EXERCISES}
GROUPS = sorted({e["group"] for e in EXERCISES})
TOTAL = len(EXERCISES)
PROJECT_IDS = {e["id"] for e in EXERCISES if e.get("project")}


def in_group(group: str) -> list[dict]:
    return [e for e in EXERCISES if e["group"] == group]


def for_lesson(lesson_id: str) -> list[dict]:
    """แบบฝึกหัดที่ผูกกับบทเรียนนี้ (ใช้แสดงลิงก์ 'ฝึกต่อ' ท้ายบท)"""
    return [e for e in EXERCISES if e.get("lesson") == lesson_id]
