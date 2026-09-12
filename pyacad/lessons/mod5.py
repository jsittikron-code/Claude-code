"""โมดูล 5 — ข้อความ ไฟล์ และวันเวลา"""

MODULE = {
    "id": "m5",
    "title": "ข้อความ ไฟล์ และวันเวลา",
    "icon": ":material/description:",
    "goal": "อ่านและเขียนไฟล์จริงในเครื่อง จัดการข้อความภาษาไทย และคำนวณกับวันที่ได้",
    "lessons": [
        # ------------------------------------------------------------------
        {
            "id": "m5l1",
            "title": "จัดการข้อความให้อยู่หมัด",
            "minutes": 9,
            "goal": "ทำความสะอาดข้อมูลข้อความที่คนกรอกมาไม่เป็นระเบียบ",
            "body": """
ข้อมูลจากไฟล์ที่คนกรอกเองมักสกปรกเสมอ — เว้นวรรคเกิน ตัวพิมพ์ไม่ตรงกัน มีอักขระแปลกปน
เมท็อดของสตริงคือเครื่องมือทำความสะอาดชุดแรก

| เมท็อด | ทำอะไร | ตัวอย่าง |
|---|---|---|
| `.strip()` | ตัดช่องว่างหัวท้าย | `" M01 ".strip()` → `"M01"` |
| `.upper()` `.lower()` | เปลี่ยนตัวพิมพ์ | `"m01".upper()` → `"M01"` |
| `.replace(a, b)` | แทนที่ข้อความ | `"M-01".replace("-", "")` → `"M01"` |
| `.split(sep)` | ตัดเป็นลิสต์ | `"a,b".split(",")` → `["a","b"]` |
| `sep.join(list)` | รวมลิสต์เป็นข้อความ | `", ".join(["a","b"])` → `"a, b"` |
| `.startswith()` `.endswith()` | ขึ้นต้น/ลงท้ายด้วย | `"M01".startswith("M")` → True |
| `.zfill(n)` | เติมศูนย์หน้า | `"1".zfill(3)` → `"001"` |
| `.isdigit()` | เป็นตัวเลขล้วนไหม | ใช้ตรวจก่อน int() |

```python
raw = "  m01 ,  Line A , 45  "
parts = [p.strip() for p in raw.split(",")]
machine = parts[0].upper()
print(machine, parts[1], int(parts[2]))     # M01 Line A 45
```

สำนวน `[p.strip() for p in text.split(",")]` คือสิ่งที่คุณจะเขียนบ่อยที่สุดเวลาจัดการไฟล์ดิบ

### ตรวจก่อนแปลง

```python
value = "45x"
if value.strip().isdigit():
    minutes = int(value)
else:
    minutes = 0
    print(f"ข้อมูลผิดรูป: {value!r} — ใช้ 0 แทน")
```

`{value!r}` แสดงแบบ repr (มีเครื่องหมายคำพูดครอบ) ทำให้เห็นช่องว่างที่ซ่อนอยู่ — มีประโยชน์มากตอนดีบัก

### ค้นหาในข้อความ

```python
line = "2026-06-01 09:40 M01 ALARM มอเตอร์ร้อนเกิน"
print("ALARM" in line)          # True
print(line.find("M01"))         # 17  (คืน -1 ถ้าไม่เจอ)
date, time, machine, event = line.split(" ", 3)
print(machine, "->", event)
```

`split(" ", 3)` จำกัดจำนวนครั้งที่ตัด ทำให้ส่วนท้ายที่มีเว้นวรรคยังอยู่ครบเป็นก้อนเดียว

### สตริงแก้ไขไม่ได้

```python
s = "M01"
s.replace("M", "X")     # คืนค่าใหม่ — ตัว s เดิมไม่เปลี่ยน
s = s.replace("M", "X") # ต้องรับค่ากลับมาเก็บเอง
```
""",
            "pitfalls": [
                "ลืมรับค่ากลับจากเมท็อดสตริง เพราะสตริงแก้ในตัวเองไม่ได้",
                "เทียบข้อความโดยไม่ `.strip()` ก่อน แล้วงงว่าทำไมไม่เท่ากัน",
                "`.isdigit()` เป็นเท็จกับ `\"45.5\"` และ `\"-3\"` — ถ้าต้องรับทศนิยม ให้ใช้ try/except แทน",
                "ใช้ `.split()` ไม่ใส่อาร์กิวเมนต์กับข้อมูลที่คั่นด้วยจุลภาค — แบบไม่ใส่จะตัดตามช่องว่าง",
            ],
            "demo": '''rows = ["  m01 , Line A , 45 ", "M03,Line A,120", " m06 , Line B , 0 "]

for raw in rows:
    parts = [p.strip() for p in raw.split(",")]
    machine, line, minutes = parts[0].upper(), parts[1], parts[2]
    if minutes.isdigit():
        print(f"{machine:<5}{line:<10}{int(minutes):>5} นาที")
    else:
        print(f"{machine}: ข้อมูลผิดรูป {minutes!r}")

log = "2026-06-01 09:40 M01 ALARM มอเตอร์ร้อนเกิน"
date, time, machine, event = log.split(" ", 3)
print(f"\\nวันที่ {date} เวลา {time} เครื่อง {machine}: {event}")
''',
            "task": "รับข้อความ '  m03 , 120 ' แล้วแปลงเป็นรหัสเครื่องตัวพิมพ์ใหญ่กับตัวเลขจำนวนเต็ม",
            "quiz": ["q_m5l1_1", "q_m5l1_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m5l2",
            "title": "อ่านและเขียนไฟล์ข้อความ",
            "minutes": 9,
            "goal": "อ่านไฟล์บันทึกของเครื่องจักรและเขียนผลสรุปออกเป็นไฟล์",
            "body": """
```python
with open("machine_log.txt", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if "ALARM" in line:
            print(line)
```

**สองสิ่งที่ห้ามลืม**

1. `with` — ปิดไฟล์ให้อัตโนมัติแม้โปรแกรมพัง ถ้าไม่ใช้ ไฟล์อาจถูกล็อกค้างไว้
2. `encoding="utf-8"` — **จำเป็นเสมอสำหรับภาษาไทยบน Windows**
   ถ้าไม่ใส่ Python จะใช้ค่ามาตรฐานของระบบ (เช่น cp874) แล้วเจอ UnicodeDecodeError
   หรือได้ตัวอักษรเพี้ยน นี่คือปัญหาอันดับหนึ่งของคนไทยที่เพิ่งเริ่มเขียนโปรแกรม

### โหมดการเปิดไฟล์

| โหมด | ความหมาย | ระวัง |
|---|---|---|
| `"r"` | อ่าน (ค่าเริ่มต้น) | ไม่มีไฟล์ → FileNotFoundError |
| `"w"` | เขียนใหม่ | **ล้างของเดิมทิ้งทันที** |
| `"a"` | เขียนต่อท้าย | ปลอดภัยกว่าสำหรับล็อก |
| `"x"` | สร้างใหม่เท่านั้น | ถ้ามีไฟล์อยู่แล้วจะฟ้อง |

```python
with open("summary.txt", "w", encoding="utf-8") as fh:
    fh.write("รายงานสรุป\\n")             # ต้องใส่ \\n เอง write ไม่ขึ้นบรรทัดให้
    for machine, total in [("M01", 75), ("M03", 120)]:
        fh.write(f"{machine}\\t{total}\\n")
```

### อ่านทั้งไฟล์ทีเดียว vs อ่านทีละบรรทัด

```python
text = fh.read()             # ทั้งไฟล์เป็นข้อความก้อนเดียว
lines = fh.readlines()       # ลิสต์ของบรรทัด (มี \\n ติดมาด้วย)
for line in fh: ...          # ทีละบรรทัด — ประหยัดหน่วยความจำที่สุด
```

ไฟล์ล็อกหลายร้อยเมกะไบต์ให้วนทีละบรรทัดเสมอ อย่า `.read()` ทั้งก้อน

### พาธไฟล์บน Windows

```python
from pathlib import Path

folder = Path(r"C:\\Users\\p\\Desktop\\งาน")     # ใส่ r นำหน้าเพื่อไม่ให้ \\ ถูกตีความ
for f in folder.glob("*.csv"):                  # ทุกไฟล์ csv ในโฟลเดอร์
    print(f.name, f.stat().st_size, "ไบต์")
```

`pathlib` จัดการเรื่องเครื่องหมายทับให้เอง จึงย้ายโค้ดไปเครื่องอื่นได้โดยไม่ต้องแก้
""",
            "pitfalls": [
                "ลืม `encoding=\"utf-8\"` แล้วภาษาไทยเพี้ยนหรือโปรแกรมพัง",
                "เปิดไฟล์ด้วยโหมด \"w\" ทับไฟล์ข้อมูลจริงจนหายทั้งไฟล์ — ตรวจให้ดีก่อนเสมอ",
                "ลืมว่า `fh.write()` ไม่ขึ้นบรรทัดใหม่ให้ ต้องเติม `\\n` เอง",
                "ใช้พาธแบบ `\"C:\\new\\test\"` โดยไม่ใส่ r นำหน้า — `\\n` และ `\\t` จะกลายเป็นอักขระพิเศษ",
            ],
            "demo": '''# ไฟล์ machine_log.txt มีให้แล้วในสนามซ้อมของแอปนี้
with open("machine_log.txt", encoding="utf-8") as fh:
    lines = [ln.strip() for ln in fh if ln.strip()]

alarms = [ln for ln in lines if "ALARM" in ln]
print(f"มีทั้งหมด {len(lines)} บรรทัด เป็น ALARM {len(alarms)} ครั้ง\\n")

for ln in alarms:
    date, time, machine, event = ln.split(" ", 3)
    print(f"{date} {time} | {machine} | {event.replace('ALARM ', '')}")

with open("summary.txt", "w", encoding="utf-8") as fh:
    fh.write(f"จำนวน ALARM = {len(alarms)}\\n")

print("\\nเขียนไฟล์ summary.txt แล้ว อ่านกลับมาดู:")
print(open("summary.txt", encoding="utf-8").read())
''',
            "task": "อ่าน machine_log.txt แล้วนับว่าเครื่องไหนมี ALARM กี่ครั้ง (ใช้ dict สรุปยอด)",
            "quiz": ["q_m5l2_1", "q_m5l2_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m5l3",
            "title": "CSV และ JSON",
            "minutes": 10,
            "goal": "อ่านไฟล์ CSV ที่ export จากระบบ และเก็บ/โหลดค่าตั้งค่าเป็น JSON",
            "body": """
### CSV — ตารางในรูปข้อความ

อ่านเองด้วย `.split(",")` ได้ แต่จะพังทันทีที่ข้อมูลมีจุลภาคอยู่ในเครื่องหมายคำพูด
ใช้โมดูล `csv` ที่จัดการให้ครบดีกว่า

```python
import csv

with open("production.csv", encoding="utf-8", newline="") as fh:
    reader = csv.DictReader(fh)          # ใช้บรรทัดแรกเป็นชื่อคอลัมน์
    for row in reader:
        print(row["machine_id"], row["downtime_min"])   # ค่าเป็น str ทุกตัว!
```

**ทุกค่าที่อ่านจาก CSV เป็นข้อความ** ต้องแปลงเองก่อนคำนวณ

```python
total = 0
with open("production.csv", encoding="utf-8", newline="") as fh:
    for row in csv.DictReader(fh):
        total += int(row["downtime_min"])
print("downtime รวม", total, "นาที")
```

เขียนออก

```python
rows = [{"machine_id": "M01", "total": 75}, {"machine_id": "M03", "total": 120}]
with open("out.csv", "w", encoding="utf-8-sig", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=["machine_id", "total"])
    writer.writeheader()
    writer.writerows(rows)
```

สองจุดที่ต้องจำตอนเขียน CSV บน Windows
* `newline=""` — ไม่ใส่แล้วจะได้บรรทัดว่างคั่นทุกแถว
* `encoding="utf-8-sig"` — ใส่แล้ว Excel เปิดภาษาไทยไม่เพี้ยน (sig คือ BOM ที่ Excel ต้องการ)

### JSON — เก็บโครงสร้างข้อมูลทั้งก้อน

```python
import json

config = {"ideal_rate": 1.2, "lines": ["Line A", "Line B"], "target_oee": 0.85}

with open("config.json", "w", encoding="utf-8") as fh:
    json.dump(config, fh, ensure_ascii=False, indent=2)   # ensure_ascii=False = ภาษาไทยอ่านออก

with open("config.json", encoding="utf-8") as fh:
    loaded = json.load(fh)
print(loaded["target_oee"])
```

JSON เหมาะกับ **ค่าตั้งค่าและข้อมูลที่มีโครงสร้างซ้อน** ส่วน CSV เหมาะกับ **ตารางแถว-คอลัมน์**
ระบบเก็บความก้าวหน้าของแอปที่คุณกำลังใช้อยู่นี้ก็เก็บเป็น JSON หนึ่งไฟล์ต่อผู้เรียนหนึ่งคน
""",
            "pitfalls": [
                "ลืมแปลงชนิด แล้วเอาข้อความมาบวกกันได้ '4545' แทนที่จะเป็น 90",
                "เขียน CSV บน Windows โดยไม่ใส่ `newline=\"\"` ทำให้มีบรรทัดว่างคั่น",
                "เปิด CSV ภาษาไทยใน Excel แล้วเพี้ยน เพราะไม่ได้เขียนด้วย utf-8-sig",
                "`json.dump` โดยไม่ใส่ `ensure_ascii=False` ทำให้ภาษาไทยกลายเป็น \\uXXXX (ยังอ่านกลับได้ แต่คนอ่านไม่ออก)",
            ],
            "demo": '''import csv, json

total = 0
by_machine = {}
with open("production.csv", encoding="utf-8", newline="") as fh:
    for row in csv.DictReader(fh):
        d = int(row["downtime_min"])
        total += d
        by_machine[row["machine_id"]] = by_machine.get(row["machine_id"], 0) + d

print("downtime รวมทั้งเดือน", f"{total:,}", "นาที")
print("สามเครื่องที่หยุดนานสุด:")
for m, v in sorted(by_machine.items(), key=lambda kv: kv[1], reverse=True)[:3]:
    print(f"  {m}: {v:,} นาที")

with open("summary.json", "w", encoding="utf-8") as fh:
    json.dump(by_machine, fh, ensure_ascii=False, indent=2)
print("\\nไฟล์ JSON ที่เขียนออกมา:")
print(open("summary.json", encoding="utf-8").read()[:200])
''',
            "task": "อ่าน production.csv แล้วหาว่าสายการผลิตไหน (คอลัมน์ line) มี downtime รวมมากที่สุด",
            "quiz": ["q_m5l3_1", "q_m5l3_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m5l4",
            "title": "วันที่และเวลา",
            "minutes": 9,
            "goal": "คำนวณช่วงเวลา หาว่าครบกำหนด PM หรือยัง และจัดรูปแบบวันที่",
            "body": """
```python
from datetime import date, datetime, timedelta

today = date.today()
d = date(2026, 6, 1)
print(d.isoformat())          # 2026-06-01
print(d.strftime("%d/%m/%Y")) # 01/06/2026
```

### แปลงข้อความเป็นวันที่ และกลับกัน

```python
d = datetime.strptime("2026-06-01", "%Y-%m-%d").date()   # ข้อความ -> วันที่
s = d.strftime("%d/%m/%Y")                               # วันที่ -> ข้อความ
```

จำง่าย ๆ: **p = parse (อ่านเข้า), f = format (พิมพ์ออก)**

| รหัส | ความหมาย |
|---|---|
| `%Y` `%m` `%d` | ปี 4 หลัก, เดือน, วัน |
| `%H` `%M` `%S` | ชั่วโมง นาที วินาที |
| `%A` `%B` | ชื่อวัน ชื่อเดือน |

### คำนวณกับวันที่

```python
last_pm = date(2026, 5, 20)
next_pm = last_pm + timedelta(days=90)          # ครบกำหนดอีก 90 วัน
days_left = (next_pm - date.today()).days       # ผลต่างของวันที่ = timedelta

if days_left < 0:
    print(f"เลยกำหนด PM มาแล้ว {abs(days_left)} วัน")
elif days_left <= 7:
    print(f"ใกล้ครบกำหนด อีก {days_left} วัน")
```

การลบวันที่สองค่าได้ `timedelta` แล้วใช้ `.days` ดึงจำนวนวันออกมา
สำหรับเวลาให้ใช้ `.total_seconds()` แล้วหารเอง

```python
start = datetime(2026, 6, 1, 9, 40)
end = datetime(2026, 6, 1, 10, 5)
minutes = (end - start).total_seconds() / 60     # 25.0
```

นี่คือวิธีคำนวณ downtime จากบันทึกเวลาเริ่ม-จบของจริง

### แยกกลุ่มตามเดือน

```python
d = date(2026, 6, 15)
print(d.year, d.month)              # 2026 6
print(d.strftime("%Y-%m"))          # 2026-06   ← ใช้เป็นคีย์สรุปรายเดือนได้เลย
print(d.weekday())                  # 0=จันทร์ ... 6=อาทิตย์
```
""",
            "pitfalls": [
                "เทียบวันที่ที่ยังเป็นข้อความ — `\"2026-6-1\" < \"2026-05-20\"` ให้ผลผิด ต้องแปลงเป็น date ก่อน",
                "สลับ `date` กับ `datetime` แล้วลบกันไม่ได้ (TypeError)",
                "ใช้ `%m` (เดือน) สลับกับ `%M` (นาที) — ตัวพิมพ์เล็กใหญ่คนละความหมาย",
                "ลืมว่า `.days` ของ timedelta ตัดเศษเวลาทิ้ง ถ้าต้องการละเอียดให้ใช้ `.total_seconds()`",
            ],
            "demo": '''from datetime import date, datetime, timedelta

pm_records = [("M01", "2026-05-20", 90), ("M03", "2026-03-01", 60), ("M06", "2026-06-01", 30)]
today = date(2026, 6, 15)          # สมมติวันนี้ เพื่อให้ผลคงที่

for machine, last_str, cycle in pm_records:
    last_pm = datetime.strptime(last_str, "%Y-%m-%d").date()
    next_pm = last_pm + timedelta(days=cycle)
    left = (next_pm - today).days
    if left < 0:
        status = f"เลยกำหนด {abs(left)} วัน"
    elif left <= 7:
        status = f"ใกล้ครบ อีก {left} วัน"
    else:
        status = f"ปกติ อีก {left} วัน"
    print(f"{machine} | PM ล่าสุด {last_pm.strftime('%d/%m/%Y')} | ครบกำหนด {next_pm} | {status}")

start = datetime(2026, 6, 1, 9, 40)
end = datetime(2026, 6, 1, 10, 5)
print(f"\\nหยุดไป {(end - start).total_seconds() / 60:.0f} นาที")
''',
            "task": "เขียนโค้ดหาว่าเครื่องไหนเลยกำหนด PM แล้วบ้าง จากวันที่ PM ล่าสุดและรอบ PM เป็นวัน",
            "quiz": ["q_m5l4_1", "q_m5l4_2"],
        },
    ],
}
