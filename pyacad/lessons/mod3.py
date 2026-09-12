"""โมดูล 3 — โครงสร้างข้อมูล"""

MODULE = {
    "id": "m3",
    "title": "เก็บข้อมูลให้ถูกโครงสร้าง",
    "icon": ":material/data_object:",
    "goal": "เลือกใช้ list / tuple / dict / set ให้เหมาะกับงาน และเขียนสรุปข้อมูลได้กระชับ",
    "lessons": [
        # ------------------------------------------------------------------
        {
            "id": "m3l1",
            "title": "list — เก็บของหลายชิ้นเรียงกัน",
            "minutes": 10,
            "goal": "สร้าง เข้าถึง แก้ไข และเรียงลำดับ list ได้คล่อง",
            "body": """
```python
machines = ["M01", "M03", "M06"]
print(machines[0])      # M01   — ตัวแรกคือตำแหน่ง 0
print(machines[-1])     # M06   — ติดลบคือนับจากท้าย
print(len(machines))    # 3
```

**ตำแหน่งเริ่มที่ 0** ดังนั้นตัวสุดท้ายคือ `len(x) - 1` การเผลออ้าง `machines[3]` จะได้ IndexError

### เมท็อดที่ใช้บ่อยที่สุด

| เมท็อด | ทำอะไร | หมายเหตุ |
|---|---|---|
| `.append(x)` | เพิ่มต่อท้าย 1 ตัว | ใช้บ่อยที่สุด |
| `.extend([a,b])` | ต่อท้ายหลายตัว | `append([a,b])` จะได้ลิสต์ซ้อนลิสต์ |
| `.insert(i, x)` | แทรกตำแหน่ง i | |
| `.remove(x)` | ลบตัวที่มีค่าเท่ากับ x ตัวแรก | ไม่เจอ = ValueError |
| `.pop()` / `.pop(i)` | ดึงตัวท้าย/ตำแหน่ง i ออกมา | คืนค่าที่ดึงด้วย |
| `.sort()` | เรียงในตัวเอง | เปลี่ยนลิสต์เดิม คืน None |
| `sorted(x)` | คืนลิสต์ใหม่ที่เรียงแล้ว | ลิสต์เดิมไม่เปลี่ยน |
| `.count(x)` / `.index(x)` | นับ / หาตำแหน่ง | |

```python
downtimes = [45, 120, 0, 30]
print(sum(downtimes), max(downtimes), min(downtimes))    # 195 120 0
print(sum(downtimes) / len(downtimes))                   # 48.75
print(sorted(downtimes, reverse=True))                   # [120, 45, 30, 0]
```

`sum`, `max`, `min`, `len`, `sorted` เป็นฟังก์ชันในตัวที่ใช้ได้ทันที ไม่ต้อง import

### เรียงตามเงื่อนไขที่กำหนดเอง

```python
records = [("M01", 45), ("M03", 120), ("M06", 0)]
records.sort(key=lambda r: r[1], reverse=True)     # เรียงตามนาที มากไปน้อย
print(records[0])       # ('M03', 120)  — เครื่องที่แย่ที่สุด
```

`key=` บอกว่า "ให้ใช้อะไรเป็นตัวเทียบ" — เป็นเครื่องมือที่ใช้บ่อยมากในการทำรายงานจัดอันดับ

### กับดักสำคัญ: list ถูกส่งแบบอ้างอิง

```python
a = [1, 2, 3]
b = a                  # b กับ a คือลิสต์ก้อนเดียวกัน (ป้ายชื่อสองป้าย)
b.append(4)
print(a)               # [1, 2, 3, 4]   ← a เปลี่ยนด้วย!

c = a.copy()           # แบบนี้ถึงจะได้ก้อนใหม่จริง
```

นี่คือเหตุผลที่บอกไว้ในบทที่ 1 ว่าตัวแปรคือ "ป้ายชื่อ" ไม่ใช่ "กล่อง"
เข้าใจข้อนี้แล้วจะเลี่ยงบั๊กประหลาดที่หายากที่สุดชนิดหนึ่งไปได้เลย
""",
            "pitfalls": [
                "`x = y.sort()` ได้ None เพราะ .sort() เรียงในตัวเองและไม่คืนค่า — ต้องใช้ `sorted()` ถ้าอยากได้ลิสต์ใหม่",
                "ใช้ `b = a` แล้วคิดว่าได้สำเนา ทั้งที่แก้ b แล้ว a เปลี่ยนตาม",
                "`.append()` กับลิสต์ทำให้เกิดลิสต์ซ้อน — ต้องการต่อท้ายหลายตัวให้ใช้ `.extend()`",
                "ลบสมาชิกขณะวนลูปบนลิสต์เดิม ทำให้ข้ามสมาชิก — ให้วนบนสำเนา `for x in items.copy():`",
            ],
            "demo": '''records = [("M01", 45), ("M03", 120), ("M06", 0), ("M08", 75)]

minutes = [r[1] for r in records]
print("รวม", sum(minutes), "นาที")
print("เฉลี่ย", round(sum(minutes) / len(minutes), 1), "นาที")

records.sort(key=lambda r: r[1], reverse=True)
print("อันดับเครื่องที่หยุดนานสุด:")
for i, (machine, mins) in enumerate(records, start=1):
    print(f"  {i}. {machine} = {mins} นาที")
''',
            "task": "สร้างลิสต์ downtime 6 ค่า แล้วหาค่าเฉลี่ย ค่าสูงสุด และเรียงจากมากไปน้อย",
            "quiz": ["q_m3l1_1", "q_m3l1_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m3l2",
            "title": "การตัดช่วง (slicing) และ tuple",
            "minutes": 8,
            "goal": "ตัดข้อมูลบางส่วนออกมาใช้ และรู้ว่าเมื่อไรควรใช้ tuple แทน list",
            "body": """
### ตัดช่วงด้วย [เริ่ม:จบ:ก้าว]

```python
days = [1, 2, 3, 4, 5, 6, 7]
print(days[0:3])     # [1, 2, 3]     เริ่มที่ 0 ไม่รวมตัวที่ 3
print(days[:3])      # [1, 2, 3]     ละไว้ = ตั้งแต่ต้น
print(days[4:])      # [5, 6, 7]     ละไว้ = จนจบ
print(days[-2:])     # [6, 7]        สองตัวสุดท้าย
print(days[::2])     # [1, 3, 5, 7]  เว้นทีละตัว
print(days[::-1])    # [7, ..., 1]   กลับลำดับ
```

หลักจำ: **ปลายทางไม่รวม** เสมอ — `days[0:3]` ได้ 3 ตัว (0, 1, 2)

ใช้กับข้อความได้เหมือนกัน ซึ่งมีประโยชน์มากตอนแยกรหัส

```python
code = "M01-A-2026"
print(code[:3])       # M01
print(code.split("-"))  # ['M01', 'A', '2026']   ← มักสะดวกกว่า slicing
```

### tuple — ลิสต์ที่แก้ไม่ได้

```python
point = ("M01", "กะเช้า", 45)     # ใช้วงเล็บกลม
machine, shift, minutes = point   # แตกค่าออกมาทีเดียว
```

เมื่อไรควรใช้ tuple
* ข้อมูลหนึ่ง**ระเบียน**ที่ตำแหน่งมีความหมายตายตัว เช่น (เครื่อง, กะ, นาที)
* ค่าที่ไม่ควรถูกแก้โดยบังเอิญ เช่น ค่าคงที่ตั้งค่าไว้
* ใช้เป็นคีย์ของ dict ได้ (list ใช้ไม่ได้เพราะแก้ได้)

```python
totals = {}
totals[("M01", "กะเช้า")] = 45     # คีย์เป็นทูเพิลได้
```

### ฟังก์ชันคืนค่าหลายค่าก็คือ tuple

```python
def summary(values):
    return min(values), max(values), sum(values) / len(values)

lo, hi, avg = summary([45, 120, 0, 30])
print(lo, hi, avg)     # 0 120 48.75
```

การแตกค่า (unpacking) นี้ทำให้โค้ดอ่านเหมือนภาษาคน และเป็นสำนวนที่คนเขียน Python ใช้ตลอด
""",
            "pitfalls": [
                "คิดว่า `days[1:3]` ได้ 3 ตัว ทั้งที่ได้ 2 ตัว",
                "พยายามแก้ค่าใน tuple → TypeError (ถ้าต้องแก้ ตั้งแต่แรกควรใช้ list)",
                "`x = (5)` ไม่ใช่ทูเพิล แต่คือเลข 5 — ทูเพิลตัวเดียวต้องเขียน `(5,)`",
                "แตกค่าไม่ครบจำนวน เช่น `a, b = (1, 2, 3)` → ValueError",
            ],
            "demo": '''code = "M01-A-2026"
print("รหัสเครื่อง:", code[:3])
print("แยกด้วย split:", code.split("-"))

days = [1, 2, 3, 4, 5, 6, 7]
print("สามวันแรก", days[:3])
print("สองวันท้าย", days[-2:])
print("กลับลำดับ", days[::-1])

def summary(values):
    return min(values), max(values), sum(values) / len(values)

lo, hi, avg = summary([45, 120, 0, 30])
print(f"ต่ำสุด {lo} สูงสุด {hi} เฉลี่ย {avg:.2f}")
''',
            "task": "จากลิสต์ downtime 7 วัน ให้ตัดเอาเฉพาะ 5 วันทำการแรก แล้วหาค่าเฉลี่ย",
            "quiz": ["q_m3l2_1", "q_m3l2_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m3l3",
            "title": "dict — จับคู่คีย์กับค่า",
            "minutes": 11,
            "goal": "ใช้ dict สรุปยอดแยกกลุ่มแทนการวนลูปซ้อน และเข้าถึงข้อมูลได้เร็ว",
            "body": """
`dict` คือโครงสร้าง "ชื่อ → ค่า" เหมือนตารางค้นหา

```python
machine = {"id": "M01", "line": "Line A", "power_kw": 15.0}
print(machine["line"])            # Line A
machine["last_pm"] = "2026-05-20" # เพิ่มคีย์ใหม่ได้เลย
```

### .get() กันพัง

```python
print(machine["cost"])            # KeyError! โปรแกรมหยุดทันที
print(machine.get("cost"))        # None — ไม่พัง
print(machine.get("cost", 0))     # 0    — กำหนดค่าเริ่มต้นเองได้
```

ในงานจริงที่ข้อมูลมาจากไฟล์ซึ่งอาจไม่ครบทุกคอลัมน์ `.get()` ช่วยให้โปรแกรมไม่ล้มกลางทาง

### วนลูปบน dict

```python
for key, value in machine.items():
    print(f"{key} = {value}")

print(list(machine.keys()))       # ['id', 'line', 'power_kw', 'last_pm']
print(list(machine.values()))
```

### สรุปยอดแยกกลุ่ม — สิ่งที่ dict เกิดมาเพื่อทำ

จำลูปซ้อนในบทที่แล้วได้ไหม? dict ทำงานเดียวกันได้ในรอบเดียว

```python
data = [("M01", 45), ("M03", 120), ("M01", 30), ("M06", 0)]

totals = {}
for machine, minutes in data:
    totals[machine] = totals.get(machine, 0) + minutes
print(totals)      # {'M01': 75, 'M03': 120, 'M06': 0}
```

บรรทัด `totals.get(machine, 0) + minutes` คือสำนวนสรุปยอดที่คุณจะใช้ตลอดชีวิตการเขียนโปรแกรม
อ่านว่า "เอายอดเดิมของเครื่องนี้ (ถ้ายังไม่มีถือเป็น 0) มาบวกเพิ่ม"

ต่างจากลูปซ้อนตรงที่ **วนข้อมูลรอบเดียว** ไม่ว่าจะมีกี่เครื่อง — ข้อมูลหมื่นแถวก็ยังเร็ว

### เรียงผลลัพธ์ออกมาเป็นอันดับ

```python
for machine, total in sorted(totals.items(), key=lambda kv: kv[1], reverse=True):
    print(f"{machine}: {total} นาที")
```

### dict ซ้อน dict = ข้อมูลหลายมิติ

```python
by_machine_shift = {}
for m, s, mins in [("M01", "เช้า", 45), ("M01", "บ่าย", 30)]:
    by_machine_shift.setdefault(m, {})
    by_machine_shift[m][s] = mins
print(by_machine_shift)     # {'M01': {'เช้า': 45, 'บ่าย': 30}}
```
""",
            "pitfalls": [
                "อ้างคีย์ที่ไม่มีด้วย `d[key]` แล้วโปรแกรมล้ม — ใช้ `.get(key, ค่าเริ่มต้น)` เมื่อไม่มั่นใจ",
                "ลืมว่าคีย์ต้องไม่ซ้ำ — ใส่คีย์เดิมซ้ำคือการทับค่าเก่า ไม่ใช่การเพิ่ม",
                "ใช้ list เป็นคีย์ → TypeError (คีย์ต้องเป็นชนิดที่แก้ไม่ได้ เช่น str, int, tuple)",
                "เทียบ dict สองอันด้วยลำดับคีย์ — dict เทียบด้วยเนื้อหา ลำดับไม่มีผลกับ `==`",
            ],
            "demo": '''data = [("M01", 45), ("M03", 120), ("M01", 30), ("M06", 0), ("M03", 60)]

totals = {}
count = {}
for machine, minutes in data:
    totals[machine] = totals.get(machine, 0) + minutes
    count[machine] = count.get(machine, 0) + 1

print("ยอดรวมต่อเครื่อง:", totals)

print("\\nอันดับเครื่องที่หยุดนานสุด")
for machine, total in sorted(totals.items(), key=lambda kv: kv[1], reverse=True):
    avg = total / count[machine]
    print(f"  {machine}: รวม {total} นาที จาก {count[machine]} ครั้ง (เฉลี่ย {avg:.1f})")
''',
            "task": "นับว่าสาเหตุการเสียแต่ละแบบเกิดกี่ครั้ง จากลิสต์สาเหตุที่มีค่าซ้ำกัน แล้วแสดง 3 อันดับแรก",
            "quiz": ["q_m3l3_1", "q_m3l3_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m3l4",
            "title": "set และ comprehension",
            "minutes": 9,
            "goal": "หาค่าไม่ซ้ำและเปรียบเทียบกลุ่มข้อมูล พร้อมเขียนลูปสรุปแบบบรรทัดเดียว",
            "body": """
### set — กลุ่มของค่าที่ไม่ซ้ำ

```python
machines = ["M01", "M03", "M01", "M06", "M03"]
unique = set(machines)
print(unique)          # {'M01', 'M03', 'M06'}  — ลำดับไม่แน่นอน
print(len(unique))     # 3
```

set ทำสิ่งที่ list ทำได้ยากมาก คือ **เปรียบเทียบกลุ่ม**

```python
planned = {"M01", "M03", "M06", "M08"}     # เครื่องที่วางแผน PM เดือนนี้
done = {"M01", "M06"}                       # ที่ทำจริง

print(planned - done)          # {'M03', 'M08'}  ยังไม่ได้ทำ
print(planned & done)          # {'M01', 'M06'}  ทำแล้วตามแผน
print(done - planned)          # ทำนอกแผน
print(planned | done)          # รวมทั้งหมด
```

สามบรรทัดนี้แทนที่โค้ดลูปซ้อนหลายสิบบรรทัดในการทำรายงาน PM Compliance ได้ทั้งหมด

### comprehension — ลูปสร้างลิสต์ในบรรทัดเดียว

```python
downtimes = [45, 120, 0, 30]

# แบบปกติ
doubled = []
for d in downtimes:
    doubled.append(d * 2)

# แบบ comprehension — ความหมายเดียวกัน
doubled = [d * 2 for d in downtimes]
```

ใส่เงื่อนไขกรองได้ด้วย

```python
critical = [d for d in downtimes if d > 60]        # [120]
hours = [round(d / 60, 2) for d in downtimes]      # แปลงหน่วย
```

ใช้กับ dict และ set ได้เช่นกัน

```python
as_hours = {m: mins / 60 for m, mins in [("M01", 45), ("M03", 120)]}
lines = {code[:3] for code in ["M01-A", "M03-B", "M01-C"]}
```

**ใช้เมื่อไร:** เมื่อเป็นการ "แปลงค่า" หรือ "กรอง" ตรงไปตรงมาและเขียนได้ในบรรทัดเดียวที่ยังอ่านออก
ถ้าเริ่มมี if ซ้อน หรือยาวเกินหน้าจอ — กลับไปเขียนลูปธรรมดาจะดีกว่า
โค้ดที่อ่านง่ายมีค่ามากกว่าโค้ดที่สั้น

### ฟังก์ชันช่วยตรวจเงื่อนไขทั้งชุด

```python
print(any(d > 100 for d in downtimes))    # True  — มีอย่างน้อยหนึ่งตัวที่เกิน
print(all(d < 200 for d in downtimes))    # True  — ทุกตัวต่ำกว่า 200
print(sum(1 for d in downtimes if d > 0)) # 3     — นับแบบมีเงื่อนไข
```
""",
            "pitfalls": [
                "คาดหวังว่า set จะเรียงลำดับให้ — set ไม่มีลำดับ ถ้าต้องการเรียงใช้ `sorted(set(x))`",
                "`{}` ว่าง ๆ คือ dict ไม่ใช่ set — set ว่างต้องเขียน `set()`",
                "เขียน comprehension ซ้อนหลายชั้นจนอ่านไม่ออก ทั้งที่ลูปธรรมดาชัดเจนกว่า",
                "ใส่ค่าที่แก้ไขได้ (เช่น list) ลงใน set ไม่ได้ → TypeError",
            ],
            "demo": '''planned = {"M01", "M03", "M06", "M08"}
done = {"M01", "M06"}

print("ยังไม่ได้ทำ PM:", sorted(planned - done))
print("ทำตามแผนแล้ว:", sorted(planned & done))
print(f"PM Compliance = {len(planned & done) / len(planned):.0%}")

downtimes = [45, 120, 0, 30, 210]
print("เกิน 60 นาที:", [d for d in downtimes if d > 60])
print("มีเคสวิกฤตไหม:", any(d > 180 for d in downtimes))
print("จำนวนกะที่มีการหยุด:", sum(1 for d in downtimes if d > 0))
''',
            "task": "สร้าง set ของเครื่องที่วางแผน PM และที่ทำจริง แล้วคำนวณ % ความสำเร็จพร้อมรายชื่อที่ตกค้าง",
            "quiz": ["q_m3l4_1", "q_m3l4_2"],
        },
    ],
}
