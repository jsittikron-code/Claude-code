"""โมดูล 4 — ฟังก์ชันและการจัดระเบียบโค้ด"""

MODULE = {
    "id": "m4",
    "title": "ฟังก์ชันและการจัดระเบียบโค้ด",
    "icon": ":material/function:",
    "goal": "แยกโค้ดเป็นชิ้นที่ทดสอบได้ นำกลับมาใช้ซ้ำได้ และไม่พังเวลาแก้",
    "lessons": [
        # ------------------------------------------------------------------
        {
            "id": "m4l1",
            "title": "สร้างฟังก์ชันด้วย def",
            "minutes": 10,
            "goal": "เขียนฟังก์ชันที่รับค่า คืนค่า และเรียกใช้ซ้ำได้",
            "body": '''
เมื่อไรควรทำเป็นฟังก์ชัน — เมื่อคุณเริ่ม **คัดลอกโค้ดไปวางแล้วแก้ตัวเลข**
นั่นคือสัญญาณว่าควรทำเป็นฟังก์ชัน เพราะถ้าสูตรผิด คุณจะต้องไล่แก้ทุกที่ที่วางไว้

```python
def availability(planned_min, downtime_min):
    """คำนวณอัตราการเดินเครื่อง (0-1)"""
    if planned_min <= 0:
        return 0.0
    return (planned_min - downtime_min) / planned_min

print(availability(480, 45))     # 0.90625
print(availability(480, 0))      # 1.0
```

องค์ประกอบ
* `def ชื่อ(พารามิเตอร์):` — ชื่อควรเป็น **คำกริยาหรือสิ่งที่คืนค่า** เช่น `availability`, `load_data`
* บรรทัดข้อความใต้ def คือ **docstring** — บอกว่าฟังก์ชันทำอะไร
* `return` ส่งค่ากลับและ **จบฟังก์ชันทันที**

### return กับ print ไม่เหมือนกัน

```python
def calc_a(p, d):
    print((p - d) / p)         # แสดงให้คนดู แต่เอาไปคำนวณต่อไม่ได้

def calc_b(p, d):
    return (p - d) / p         # ส่งค่ากลับ เอาไปใช้ต่อได้

x = calc_a(480, 45)            # x = None !
y = calc_b(480, 45) * 100      # ใช้งานต่อได้
```

**กฎ:** ฟังก์ชันคำนวณควร `return` เสมอ ส่วนการ `print` ให้ทำที่ตัวโปรแกรมหลัก
แยกแบบนี้แล้วจะเอาฟังก์ชันเดิมไปใช้กับแดชบอร์ด กับไฟล์ Excel หรือกับการทดสอบก็ได้

### ค่าเริ่มต้นและการเรียกด้วยชื่อ

```python
def oee(planned, downtime, good, reject, ideal_rate=1.2):
    run = planned - downtime
    if run <= 0:
        return 0.0
    total = good + reject
    a = run / planned
    p = total / (run * ideal_rate)
    q = good / total if total else 0
    return a * p * q

print(oee(480, 45, 380, 20))                    # ใช้ ideal_rate เริ่มต้น
print(oee(480, 45, 380, 20, ideal_rate=1.5))    # ระบุชื่อพารามิเตอร์ = อ่านง่ายกว่า
```

พารามิเตอร์ที่มีค่าเริ่มต้นต้องอยู่ **หลัง** ตัวที่ไม่มีเสมอ

### รับจำนวนไม่จำกัดด้วย *args

```python
def total_downtime(*minutes):
    return sum(minutes)

print(total_downtime(45, 120, 30))    # 195
```
''',
            "pitfalls": [
                "ลืม `return` แล้วฟังก์ชันคืน None ทำให้บรรทัดถัดไปพังด้วย TypeError",
                "ใช้ค่าเริ่มต้นเป็นลิสต์ `def f(items=[])` — ลิสต์ก้อนนั้นถูกใช้ร่วมกันทุกครั้งที่เรียก ให้ใช้ `None` แล้วสร้างใหม่ข้างใน",
                "ฟังก์ชันเดียวทำหลายอย่างจนยาวเป็นร้อยบรรทัด — แตกเป็นฟังก์ชันย่อยที่ทำอย่างเดียว",
                "ตั้งชื่อฟังก์ชันซ้ำกับตัวแปร ทำให้ตัวใดตัวหนึ่งหายไปเงียบ ๆ",
            ],
            "demo": '''def availability(planned_min, downtime_min):
    """อัตราการเดินเครื่อง คืนค่า 0-1 (กันหารศูนย์ไว้แล้ว)"""
    if planned_min <= 0:
        return 0.0
    return (planned_min - downtime_min) / planned_min


def grade(value):
    if value >= 0.90:
        return "ดีเยี่ยม"
    if value >= 0.75:
        return "พอใช้"
    return "ต้องปรับปรุง"


for machine, planned, down in [("M01", 480, 45), ("M03", 480, 180), ("M06", 480, 0)]:
    a = availability(planned, down)
    print(f"{machine}: A = {a:.1%} -> {grade(a)}")
''',
            "task": "เขียนฟังก์ชัน quality(good, reject) ที่คืนสัดส่วนของดี และคืน 0 เมื่อไม่มีการผลิตเลย",
            "quiz": ["q_m4l1_1", "q_m4l1_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m4l2",
            "title": "ขอบเขตตัวแปรและการส่งค่าเข้าฟังก์ชัน",
            "minutes": 9,
            "goal": "เข้าใจว่าทำไมตัวแปรบางตัวเปลี่ยนตามและบางตัวไม่เปลี่ยน",
            "body": """
ตัวแปรที่สร้างในฟังก์ชัน **อยู่แค่ในฟังก์ชันนั้น** พอฟังก์ชันจบก็หายไป

```python
def calc():
    result = 10        # ตัวแปรเฉพาะในฟังก์ชัน
    return result

calc()
print(result)          # NameError — ข้างนอกไม่รู้จัก
```

ฟังก์ชัน **อ่าน** ตัวแปรข้างนอกได้ แต่ **เขียนทับ** ไม่ได้ (ถ้าไม่บอกชัดเจน)

```python
IDEAL_RATE = 1.2       # ค่าคงที่ระดับโปรแกรม เขียนตัวใหญ่ตามธรรมเนียม

def calc(qty, minutes):
    return qty / (minutes * IDEAL_RATE)     # อ่านได้ ไม่มีปัญหา
```

### กับดักคลาสสิก: ส่ง list เข้าฟังก์ชัน

```python
def add_machine(items, code):
    items.append(code)          # แก้ลิสต์ก้อนเดิมที่ส่งเข้ามา!
    return items

machines = ["M01"]
add_machine(machines, "M03")
print(machines)                 # ['M01', 'M03']  ← ตัวแปรข้างนอกเปลี่ยนไปแล้ว
```

ตัวเลขและข้อความส่งเข้าไปแล้วแก้ไม่กระทบข้างนอก แต่ **list และ dict กระทบ**
เพราะสิ่งที่ส่งเข้าไปคือ "ป้ายชื่ออีกใบที่ชี้ก้อนเดียวกัน"

วิธีที่ปลอดภัยกว่าคือ **ไม่แก้ของที่รับเข้ามา แต่คืนของใหม่**

```python
def add_machine(items, code):
    return items + [code]       # สร้างลิสต์ใหม่ ของเดิมไม่ถูกแตะ
```

ฟังก์ชันที่ "ผลลัพธ์ขึ้นกับอาร์กิวเมนต์อย่างเดียว และไม่ไปแก้อะไรข้างนอก"
เรียกว่า **ฟังก์ชันบริสุทธิ์** (pure function) — ทดสอบง่ายที่สุด และเป็นต้นเหตุของบั๊กน้อยที่สุด
พยายามให้ฟังก์ชันคำนวณของคุณเป็นแบบนี้

### ค่าเริ่มต้นที่แก้ไขได้ = กับดักที่ต้องจำ

```python
def bad(items=[]):        # ❌ ลิสต์นี้ถูกสร้างครั้งเดียวตอนนิยามฟังก์ชัน
    items.append(1)
    return items

print(bad())   # [1]
print(bad())   # [1, 1]  ← ค้างจากครั้งก่อน!

def good(items=None):     # ✅ วิธีที่ถูก
    if items is None:
        items = []
    items.append(1)
    return items
```
""",
            "pitfalls": [
                "ใช้ตัวแปรข้างนอกในฟังก์ชันแทนการรับเป็นพารามิเตอร์ ทำให้ย้ายไปใช้ที่อื่นไม่ได้",
                "ใช้ `global` เพื่อแก้ปัญหาชั่วคราว แล้วโค้ดกลายเป็นตามรอยไม่ได้",
                "ลืมว่า list/dict ที่ส่งเข้าฟังก์ชันถูกแก้จริง",
                "ใช้ list/dict เป็นค่าเริ่มต้นของพารามิเตอร์",
            ],
            "demo": '''def add_bad(items, code):
    items.append(code)
    return items

def add_good(items, code):
    return items + [code]

a = ["M01"]
add_bad(a, "M03")
print("หลังเรียก add_bad:", a)      # ถูกแก้

b = ["M01"]
add_good(b, "M03")
print("หลังเรียก add_good:", b)     # ไม่ถูกแก้

def bad(items=[]):
    items.append(1)
    return items

print(bad(), bad(), bad())          # ดูค่าที่ค้างสะสม
''',
            "task": "เปิดหน้า 'ไล่โค้ดทีละบรรทัด' แล้ววางตัวอย่างข้างบน สังเกตค่าของ items ในแต่ละครั้งที่เรียก bad()",
            "quiz": ["q_m4l2_1", "q_m4l2_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m4l3",
            "title": "โมดูล การ import และ __main__",
            "minutes": 9,
            "goal": "แยกโค้ดเป็นหลายไฟล์และใช้ไลบรารีมาตรฐานเป็น",
            "body": """
ทุกไฟล์ `.py` คือ **โมดูล** ที่ไฟล์อื่นเรียกใช้ได้

```python
# ไฟล์ oee_tools.py
def availability(planned, downtime):
    return (planned - downtime) / planned if planned else 0.0
```

```python
# ไฟล์ report.py — อยู่โฟลเดอร์เดียวกัน
import oee_tools
print(oee_tools.availability(480, 45))

from oee_tools import availability      # เอาเฉพาะที่ใช้
print(availability(480, 45))
```

### ไลบรารีมาตรฐานที่ติดมากับ Python (ไม่ต้องติดตั้ง)

| โมดูล | ใช้ทำอะไร |
|---|---|
| `math` | `sqrt`, `ceil`, `floor`, `pi` |
| `statistics` | `mean`, `median`, `stdev` |
| `datetime` | วันที่ เวลา ผลต่างของเวลา |
| `csv` / `json` | อ่านเขียนไฟล์ข้อมูล |
| `pathlib` | จัดการพาธไฟล์แบบข้ามระบบปฏิบัติการ |
| `collections` | `Counter` นับของ, `defaultdict` |
| `os` / `glob` | เดินโฟลเดอร์ ค้นไฟล์ |
| `random` | สุ่ม |

```python
from statistics import mean, median
from collections import Counter

downtimes = [45, 120, 0, 30, 210]
print(mean(downtimes), median(downtimes))     # 81 45

causes = ["สายพานขาด", "มอเตอร์ร้อน", "สายพานขาด"]
print(Counter(causes).most_common(1))         # [('สายพานขาด', 2)]
```

`Counter` ทำงานเดียวกับที่เราเขียนเองด้วย dict ในบทที่แล้ว — รู้วิธีเขียนเองแล้วค่อยใช้ของสำเร็จรูป
จะได้เข้าใจว่ามันทำอะไรอยู่

### if __name__ == "__main__"

```python
def availability(planned, downtime):
    return (planned - downtime) / planned


if __name__ == "__main__":       # ทำงานเฉพาะตอนสั่งรันไฟล์นี้ตรง ๆ
    print(availability(480, 45)) # ไม่ทำงานตอนถูก import จากไฟล์อื่น
```

ประโยชน์จริง: ใส่โค้ดทดลอง/ทดสอบไว้ใต้บรรทัดนี้ได้ โดยไม่รบกวนไฟล์ที่ import ไปใช้
""",
            "pitfalls": [
                "ตั้งชื่อไฟล์ทับไลบรารี เช่น `random.py` หรือ `csv.py` แล้ว import ของจริงไม่ได้อีก",
                "ใช้ `from module import *` ทำให้ไม่รู้ว่าชื่อไหนมาจากไหนและชนกันได้",
                "โค้ดทดสอบระดับบนสุดของไฟล์ทำงานทุกครั้งที่ถูก import — ต้องมี `if __name__ == \"__main__\"`",
                "import วนกลับไปกลับมาระหว่างสองไฟล์ (circular import) → ต้องออกแบบให้ไหลทางเดียว",
            ],
            "demo": '''from statistics import mean, median, pstdev
from collections import Counter
import math

downtimes = [45, 120, 0, 30, 210]
print("เฉลี่ย", round(mean(downtimes), 1))
print("มัธยฐาน", median(downtimes))
print("ส่วนเบี่ยงเบน", round(pstdev(downtimes), 1))
print("ปัดขึ้นเป็นชั่วโมง", math.ceil(sum(downtimes) / 60))

causes = ["สายพานขาด", "มอเตอร์ร้อน", "สายพานขาด", "ลมตก", "สายพานขาด"]
for cause, n in Counter(causes).most_common(2):
    print(f"{cause}: {n} ครั้ง")
''',
            "task": "ใช้ Counter หาสาเหตุการเสียที่พบบ่อยที่สุด 3 อันดับจากลิสต์สาเหตุ",
            "quiz": ["q_m4l3_1", "q_m4l3_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m4l4",
            "title": "เขียนฟังก์ชันให้คนอื่น (และตัวเราในอนาคต) ใช้ได้",
            "minutes": 8,
            "goal": "ใส่ docstring, type hint และออกแบบฟังก์ชันให้ทดสอบได้",
            "body": '''
```python
def oee(planned_min: int, downtime_min: int, good_qty: int,
        reject_qty: int, ideal_rate: float = 1.2) -> float:
    """คำนวณ OEE จากข้อมูลหนึ่งกะ

    Args:
        planned_min: เวลาที่วางแผนเดินเครื่อง (นาที)
        downtime_min: เวลาหยุดรวม (นาที)
        good_qty: จำนวนชิ้นดี
        reject_qty: จำนวนชิ้นเสีย
        ideal_rate: ความเร็วมาตรฐาน (ชิ้นต่อนาที)

    Returns:
        ค่า OEE ระหว่าง 0 ถึง 1 — คืน 0.0 ถ้าไม่มีเวลาเดินเครื่อง
    """
    run_min = planned_min - downtime_min
    if run_min <= 0 or planned_min <= 0:
        return 0.0
    total = good_qty + reject_qty
    if total == 0:
        return 0.0
    a = run_min / planned_min
    p = min(total / (run_min * ideal_rate), 1.0)   # กันค่าเกิน 100%
    q = good_qty / total
    return a * p * q
```

### type hint — บอกชนิดที่คาดหวัง

`planned_min: int` และ `-> float` ไม่ได้บังคับให้ Python ตรวจ แต่ช่วยสองอย่าง
1. โปรแกรมแก้โค้ด (VS Code) เตือนเมื่อส่งชนิดผิด และเติมคำให้ถูก
2. คนอ่านเข้าใจทันทีว่าต้องส่งอะไรและได้อะไรกลับ

### สามข้อที่ทำให้ฟังก์ชันน่าเชื่อถือ

**1. จัดการกรณีสุดขอบให้ชัด** — เวลาเดินเครื่อง 0, ผลิตได้ 0 ชิ้น, ข้อมูลหาย
ฟังก์ชันที่ดีต้องตอบได้ว่าจะทำอย่างไร ไม่ใช่ปล่อยให้ล้ม

**2. ทำอย่างเดียว** — ถ้าชื่อฟังก์ชันต้องใช้คำว่า "และ" แสดงว่าควรแยกเป็นสองฟังก์ชัน

**3. อย่าให้ฟังก์ชันคำนวณไปอ่านไฟล์เอง** — รับข้อมูลที่อ่านมาแล้วเป็นพารามิเตอร์
แบบนี้จึงจะทดสอบด้วยตัวเลขสมมติได้โดยไม่ต้องมีไฟล์จริง

### ทดสอบฟังก์ชันด้วย assert

```python
assert oee(480, 480, 100, 0) == 0.0            # เครื่องไม่ได้เดินเลย
assert abs(oee(480, 0, 576, 0) - 1.0) < 1e-9   # เดินเต็ม ผลิตเต็ม ของดีล้วน
print("ผ่านการทดสอบทั้งหมด")
```

`assert` คือคำสั่ง "ถ้าไม่จริงให้หยุดพร้อมฟ้อง" — เอาไว้ท้ายไฟล์ตอนพัฒนา
พอโปรแกรมโตขึ้น จะขยับไปใช้ `pytest` แต่หลักการเดียวกัน
''',
            "pitfalls": [
                "เขียน docstring เป็นการอธิบายโค้ดทีละบรรทัด แทนที่จะบอกว่าใช้ทำอะไรและคืนอะไร",
                "ฟังก์ชันรับ 8 พารามิเตอร์ — สัญญาณว่าควรรวมเป็น dict หรือแยกฟังก์ชัน",
                "ให้ฟังก์ชันคำนวณอ่านไฟล์เอง ทำให้ทดสอบไม่ได้ถ้าไม่มีไฟล์นั้น",
                "ไม่จัดการหารศูนย์ในฟังก์ชันสูตร แล้วโปรแกรมทั้งระบบล้มเพราะข้อมูลกะเดียว",
            ],
            "demo": '''def oee(planned_min: int, downtime_min: int, good_qty: int,
        reject_qty: int, ideal_rate: float = 1.2) -> float:
    """คำนวณ OEE ของหนึ่งกะ คืนค่า 0-1"""
    run_min = planned_min - downtime_min
    if run_min <= 0 or planned_min <= 0:
        return 0.0
    total = good_qty + reject_qty
    if total == 0:
        return 0.0
    a = run_min / planned_min
    p = min(total / (run_min * ideal_rate), 1.0)
    q = good_qty / total
    return a * p * q


assert oee(480, 480, 100, 0) == 0.0
assert oee(480, 45, 0, 0) == 0.0
assert 0 < oee(480, 45, 380, 20) < 1
print("ผ่านการทดสอบทั้งหมด")
print(f"OEE ตัวอย่าง = {oee(480, 45, 380, 20):.1%}")
print(oee.__doc__)
''',
            "task": "เพิ่ม assert อีก 2 บรรทัดที่ตรวจกรณีสุดขอบของฟังก์ชัน oee แล้วดูว่าเมื่อ assert ไม่ผ่าน ข้อความที่ได้หน้าตาเป็นอย่างไร",
            "quiz": ["q_m4l4_1", "q_m4l4_2"],
        },
    ],
}
