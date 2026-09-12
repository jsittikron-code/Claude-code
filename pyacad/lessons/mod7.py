"""โมดูล 7 — pandas สำหรับงานโรงงาน"""

MODULE = {
    "id": "m7",
    "title": "pandas สำหรับงานโรงงาน",
    "icon": ":material/table_chart:",
    "goal": "ทำงานกับตารางข้อมูลจริงหลักหมื่นแถวได้ในไม่กี่บรรทัด แทน Excel ที่ทำมือ",
    "lessons": [
        # ------------------------------------------------------------------
        {
            "id": "m7l1",
            "title": "ทำไมต้อง pandas และ DataFrame คืออะไร",
            "minutes": 8,
            "goal": "เห็นว่าโค้ดลูป 20 บรรทัดกลายเป็น 2 บรรทัดได้อย่างไร",
            "body": """
สิ่งที่คุณเขียนมาทั้งหมด — อ่าน CSV, วนลูป, สรุปยอดด้วย dict — pandas ทำให้เหลือไม่กี่บรรทัด

```python
# แบบเขียนเอง (บทที่ 5)
totals = {}
with open("production.csv", encoding="utf-8", newline="") as fh:
    for row in csv.DictReader(fh):
        m = row["machine_id"]
        totals[m] = totals.get(m, 0) + int(row["downtime_min"])

# แบบ pandas
df = pd.read_csv("production.csv")
totals = df.groupby("machine_id")["downtime_min"].sum()
```

ไม่ใช่แค่สั้นกว่า แต่ **เร็วกว่ามาก** กับข้อมูลหลักแสนแถว เพราะทำงานเป็นชุดในระดับล่าง
ไม่ได้วนทีละแถวใน Python

> แต่การที่คุณเขียนเองเป็นมาก่อนมีค่ามาก — เวลา pandas ให้ผลแปลก คุณจะรู้ว่ามันควรได้อะไร

### สองโครงสร้างหลัก

**Series** = คอลัมน์เดียว (มีดัชนีกำกับแต่ละค่า)
**DataFrame** = ตารางทั้งใบ (หลาย Series ที่ใช้ดัชนีร่วมกัน)

```python
import pandas as pd

df = pd.DataFrame({
    "machine_id": ["M01", "M03", "M01"],
    "shift": ["เช้า", "เช้า", "บ่าย"],
    "downtime_min": [45, 120, 30],
})
print(df)
print(df["downtime_min"])          # Series หนึ่งคอลัมน์
print(df["downtime_min"].sum())    # 195
```

### คิดเป็น "ทั้งคอลัมน์" ไม่ใช่ "ทีละแถว"

นี่คือการเปลี่ยนวิธีคิดที่สำคัญที่สุดของบทนี้

```python
# ❌ วิธีคิดแบบเดิม
for i in range(len(df)):
    df.loc[i, "run_min"] = df.loc[i, "planned_min"] - df.loc[i, "downtime_min"]

# ✅ วิธีคิดแบบ pandas — ทำทั้งคอลัมน์พร้อมกัน
df["run_min"] = df["planned_min"] - df["downtime_min"]
```

แบบล่างสั้นกว่า อ่านง่ายกว่า และเร็วกว่าหลายสิบเท่า
เมื่อไรที่คุณเริ่มเขียน `for` กับ DataFrame ให้หยุดคิดก่อนว่ามีวิธีทำทั้งคอลัมน์ไหม
""",
            "pitfalls": [
                "วนลูป `for i in range(len(df))` แทนการทำทั้งคอลัมน์ — ช้าและยาวโดยไม่จำเป็น",
                "สับสนระหว่าง Series กับ DataFrame — `df[\"a\"]` ได้ Series ส่วน `df[[\"a\"]]` ได้ DataFrame",
                "ลืมว่าดัชนี (index) ติดมากับข้อมูลเสมอ และไม่ได้เรียง 0,1,2 หลังการกรอง",
            ],
            "demo": '''import pandas as pd

df = pd.DataFrame({
    "machine_id": ["M01", "M03", "M01", "M06"],
    "shift": ["เช้า", "เช้า", "บ่าย", "เช้า"],
    "planned_min": [480, 480, 480, 480],
    "downtime_min": [45, 120, 30, 0],
})

df["run_min"] = df["planned_min"] - df["downtime_min"]
df["availability"] = df["run_min"] / df["planned_min"]

print(df)
print("\\ndowntime รวม =", df["downtime_min"].sum(), "นาที")
print("availability เฉลี่ย =", f"{df['availability'].mean():.1%}")
''',
            "task": "สร้าง DataFrame จาก dict ของข้อมูล 4 กะ แล้วเพิ่มคอลัมน์ availability",
            "quiz": ["q_m7l1_1", "q_m7l1_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m7l2",
            "title": "อ่านไฟล์และสำรวจข้อมูล",
            "minutes": 9,
            "goal": "เปิดไฟล์จริงแล้วตรวจสภาพข้อมูลก่อนใช้งาน",
            "body": """
```python
import pandas as pd

df = pd.read_csv("production.csv")                    # CSV
# df = pd.read_excel("รายงาน.xlsx", sheet_name="ข้อมูลดิบ")   # Excel
```

ไฟล์ CSV ภาษาไทยจากระบบเก่าบางระบบไม่ใช่ utf-8 ถ้าเจอตัวอักษรเพี้ยนให้ลอง
`pd.read_csv(path, encoding="utf-8-sig")` หรือ `encoding="cp874"`

### 5 คำสั่งที่ต้องรันทุกครั้งที่เจอข้อมูลใหม่

```python
df.shape          # (จำนวนแถว, จำนวนคอลัมน์) — เช็กก่อนว่าอ่านครบไหม
df.head()         # 5 แถวแรก ดูหน้าตาข้อมูล
df.dtypes         # ชนิดของแต่ละคอลัมน์ ← สำคัญที่สุด
df.info()         # ชนิด + จำนวนค่าที่ไม่ว่าง
df.describe()     # ค่าสถิติของคอลัมน์ตัวเลข
```

**`df.dtypes` คือคำสั่งที่ช่วยคุณได้มากที่สุด** ถ้าคอลัมน์ตัวเลขขึ้นเป็น `object`
แปลว่ามีค่าที่ไม่ใช่ตัวเลขปนอยู่ (เช่น "-", "N/A", ช่องว่าง) และการคำนวณทั้งหมดหลังจากนั้นจะผิด

### จัดการค่าว่าง

```python
df.isna().sum()                     # นับค่าว่างต่อคอลัมน์
df["downtime_min"].fillna(0)        # แทนค่าว่างด้วย 0
df.dropna(subset=["machine_id"])    # ทิ้งแถวที่ไม่มีรหัสเครื่อง
```

ตัดสินใจให้ชัดว่าค่าว่างแปลว่าอะไรในงานของคุณ — "ไม่ได้บันทึก" กับ "หยุด 0 นาที" ไม่เหมือนกัน
การเติม 0 ทั้งหมดโดยไม่คิด ทำให้ค่าเฉลี่ยเพี้ยนได้ง่าย ๆ

### บังคับชนิดข้อมูล

```python
df["downtime_min"] = pd.to_numeric(df["downtime_min"], errors="coerce")   # แปลงไม่ได้ → NaN
df["date"] = pd.to_datetime(df["date"])                                   # เป็นวันที่จริง
```

`errors="coerce"` ทำให้ค่าที่แปลงไม่ได้กลายเป็น NaN แทนที่จะพังทั้งโปรแกรม
แล้วค่อยใช้ `df[df["downtime_min"].isna()]` ดูว่าแถวไหนมีปัญหา
""",
            "pitfalls": [
                "ไม่ตรวจ dtypes แล้วคำนวณกับคอลัมน์ที่จริง ๆ เป็นข้อความ ได้ผลลัพธ์แปลกโดยไม่มีข้อผิดพลาด",
                "เติม 0 ให้ค่าว่างทั้งหมดโดยไม่คิดว่ามันหมายถึงอะไร ทำให้ค่าเฉลี่ยผิด",
                "ลืมว่า `df.head()` ไม่ได้บอกความจริงทั้งหมด — ปัญหามักอยู่แถวท้าย ๆ",
                "อ่าน Excel ที่มีหัวตารางตกแต่ง 3 บรรทัดโดยไม่ใส่ `skiprows`",
            ],
            "demo": '''import pandas as pd

df = pd.read_csv("production.csv")

print("ขนาดข้อมูล:", df.shape)
print("\\nชนิดข้อมูลแต่ละคอลัมน์:")
print(df.dtypes)
print("\\n5 แถวแรก:")
print(df.head())
print("\\nค่าว่างต่อคอลัมน์:")
print(df.isna().sum())
print("\\nสถิติของคอลัมน์ตัวเลข:")
print(df[["downtime_min", "good_qty", "reject_qty"]].describe().round(1))
''',
            "task": "อ่าน production.csv แล้วรายงานจำนวนแถว จำนวนเครื่องที่ไม่ซ้ำ และช่วงวันที่ของข้อมูล",
            "quiz": ["q_m7l2_1", "q_m7l2_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m7l3",
            "title": "เลือก กรอง และสร้างคอลัมน์ใหม่",
            "minutes": 10,
            "goal": "ดึงเฉพาะข้อมูลที่ต้องการและคำนวณคอลัมน์ใหม่ได้",
            "body": """
### เลือกคอลัมน์

```python
df["machine_id"]                       # Series
df[["machine_id", "downtime_min"]]     # DataFrame (วงเล็บเหลี่ยมสองชั้น)
```

### กรองแถวด้วยเงื่อนไข

```python
long_stops = df[df["downtime_min"] > 60]
line_a = df[df["line"] == "Line A"]
both = df[(df["line"] == "Line A") & (df["downtime_min"] > 60)]
```

**สองข้อที่พลาดกันมากที่สุด**
* ใช้ `&` `|` `~` (ไม่ใช่ `and` `or` `not`) เพราะเป็นการเทียบทั้งคอลัมน์พร้อมกัน
* **ต้องใส่วงเล็บครอบแต่ละเงื่อนไข** — ไม่ใส่แล้วลำดับการคำนวณจะเพี้ยนและฟ้อง error

```python
df[df["machine_id"].isin(["M01", "M03"])]        # อยู่ในกลุ่มนี้
df[df["cause"].str.contains("มอเตอร์", na=False)] # ข้อความมีคำนี้
df[df["downtime_min"].between(30, 120)]           # อยู่ในช่วง
```

### .loc — เลือกแถวและคอลัมน์พร้อมกัน

```python
df.loc[df["line"] == "Line A", ["machine_id", "downtime_min"]]
df.loc[df["downtime_min"] > 200, "flag"] = "วิกฤต"     # กำหนดค่าเฉพาะแถวที่เข้าเงื่อนไข
```

ใช้ `.loc` เวลาจะ **เขียนค่า** เสมอ ถ้าเขียนแบบ `df[df["x"] > 1]["y"] = 0`
pandas จะเตือน `SettingWithCopyWarning` และค่ามักไม่ถูกเขียนจริง

### สร้างคอลัมน์ใหม่

```python
df["run_min"] = df["planned_min"] - df["downtime_min"]
df["total_qty"] = df["good_qty"] + df["reject_qty"]
df["availability"] = df["run_min"] / df["planned_min"]
df["quality"] = df["good_qty"] / df["total_qty"].replace(0, pd.NA)   # กันหารศูนย์
```

### จัดกลุ่มเป็นระดับด้วย np.where หรือ cut

```python
import numpy as np
df["ระดับ"] = np.where(df["downtime_min"] > 120, "วิกฤต",
                np.where(df["downtime_min"] > 60, "เฝ้าระวัง", "ปกติ"))

df["ช่วง"] = pd.cut(df["downtime_min"], bins=[-1, 60, 120, 9999],
                    labels=["ปกติ", "เฝ้าระวัง", "วิกฤต"])
```
""",
            "pitfalls": [
                "ใช้ `and` / `or` กับเงื่อนไข pandas → ValueError ต้องใช้ `&` `|`",
                "ลืมวงเล็บครอบเงื่อนไขแต่ละอัน",
                "เขียนค่าลง DataFrame ที่เป็นสำเนา (SettingWithCopyWarning) แล้วค่าไม่เปลี่ยนจริง",
                "หารด้วยคอลัมน์ที่มี 0 แล้วได้ inf ปนในผลลัพธ์โดยไม่รู้ตัว",
            ],
            "demo": '''import pandas as pd

df = pd.read_csv("production.csv")
df["run_min"] = df["planned_min"] - df["downtime_min"]
df["total_qty"] = df["good_qty"] + df["reject_qty"]
df["availability"] = df["run_min"] / df["planned_min"]

critical = df[(df["downtime_min"] > 120) & (df["line"] == "Line A")]
print(f"กะที่หยุดเกิน 120 นาทีใน Line A: {len(critical)} กะ")
print(critical[["date", "machine_id", "shift", "downtime_min"]].head())

df.loc[df["downtime_min"] > 120, "ระดับ"] = "วิกฤต"
df["ระดับ"] = df["ระดับ"].fillna("ปกติ")
print("\\nจำนวนกะแยกตามระดับ:")
print(df["ระดับ"].value_counts())
''',
            "task": "กรองเฉพาะกะของ Line B ที่ downtime เกิน 60 นาที แล้วนับว่ามีกี่กะและเป็นของเครื่องไหนบ้าง",
            "quiz": ["q_m7l3_1", "q_m7l3_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m7l4",
            "title": "groupby, agg และ pivot_table",
            "minutes": 11,
            "goal": "สรุปข้อมูลแยกกลุ่มแบบเดียวกับ PivotTable ใน Excel",
            "body": """
`groupby` คือหัวใจของการทำรายงาน — แนวคิดคือ **แยก → คำนวณ → รวมกลับ**

```python
df.groupby("machine_id")["downtime_min"].sum()
df.groupby("machine_id")["downtime_min"].mean().round(1)
df.groupby(["line", "shift"])["downtime_min"].sum()      # จัดกลุ่มหลายชั้น
```

### agg — หลายค่าสถิติพร้อมกัน

```python
summary = df.groupby("machine_id").agg(
    downtime_รวม=("downtime_min", "sum"),
    downtime_เฉลี่ย=("downtime_min", "mean"),
    จำนวนกะ=("downtime_min", "count"),
    ของดี=("good_qty", "sum"),
    ของเสีย=("reject_qty", "sum"),
).round(1)

summary["quality"] = summary["ของดี"] / (summary["ของดี"] + summary["ของเสีย"])
print(summary.sort_values("downtime_รวม", ascending=False))
```

รูปแบบ `ชื่อคอลัมน์ใหม่=("คอลัมน์เดิม", "ฟังก์ชัน")` อ่านง่ายที่สุดและตั้งชื่อผลลัพธ์ได้เลย
ฟังก์ชันที่ใช้ได้: `sum`, `mean`, `median`, `count`, `nunique`, `min`, `max`, `std`

### reset_index — ทำให้กลับมาเป็นตารางปกติ

หลัง groupby ผลลัพธ์จะเอากลุ่มไปเป็นดัชนี ถ้าจะเอาไปใช้ต่อหรือเขียนลง Excel ให้ทำ

```python
summary = summary.reset_index()      # เอา machine_id กลับมาเป็นคอลัมน์ปกติ
```

### pivot_table — ตารางไขว้แบบ Excel

```python
pivot = df.pivot_table(
    index="machine_id", columns="shift", values="downtime_min",
    aggfunc="sum", fill_value=0, margins=True, margins_name="รวม",
)
```
ได้ตารางที่แถวเป็นเครื่อง คอลัมน์เป็นกะ — เหมือน PivotTable ทุกประการ แต่ทำซ้ำได้ด้วยการกดรัน

### เรียงและเอาอันดับต้น

```python
top = summary.sort_values("downtime_รวม", ascending=False).head(5)
```

ตารางจัดอันดับ 5 เครื่องที่หยุดนานที่สุด — คือรายงานที่หัวหน้าอยากเห็นที่สุด และตอนนี้ใช้บรรทัดเดียว
""",
            "pitfalls": [
                "ลืม `reset_index()` แล้วงงว่าทำไมอ้างคอลัมน์กลุ่มไม่ได้",
                "ใช้ `mean` กับข้อมูลที่มีค่าว่าง โดยไม่รู้ว่า pandas ข้าม NaN ให้อัตโนมัติ (จำนวนหารจึงไม่เท่าที่คิด)",
                "จัดกลุ่มด้วยคอลัมน์ข้อความที่ยังไม่ได้ `.str.strip()` ทำให้ 'M01' กับ 'M01 ' แยกเป็นคนละกลุ่ม",
                "เอา sum ของ availability มาหาค่าเฉลี่ย ทั้งที่ต้องคำนวณจากผลรวมของเวลาก่อน",
            ],
            "demo": '''import pandas as pd

df = pd.read_csv("production.csv")

summary = df.groupby("machine_id").agg(
    downtime_รวม=("downtime_min", "sum"),
    downtime_เฉลี่ย=("downtime_min", "mean"),
    จำนวนกะ=("downtime_min", "count"),
    ของดี=("good_qty", "sum"),
    ของเสีย=("reject_qty", "sum"),
).round(1)
summary["quality"] = (summary["ของดี"] / (summary["ของดี"] + summary["ของเสีย"])).round(4)

print("5 เครื่องที่หยุดนานที่สุด")
print(summary.sort_values("downtime_รวม", ascending=False).head(5))

print("\\nตารางไขว้ เครื่อง x กะ (นาทีหยุดรวม)")
print(df.pivot_table(index="machine_id", columns="shift",
                     values="downtime_min", aggfunc="sum", fill_value=0))
''',
            "task": "หาว่าสายการผลิตไหนมี downtime เฉลี่ยต่อกะสูงสุด และแยกดูรายกะด้วย pivot_table",
            "quiz": ["q_m7l4_1", "q_m7l4_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m7l5",
            "title": "รวมตาราง วันที่ และส่งออก Excel",
            "minutes": 10,
            "goal": "เชื่อมข้อมูลหลายไฟล์เข้าด้วยกันและส่งผลลัพธ์เป็นรายงานที่ส่งต่อได้",
            "body": """
### merge — เชื่อมตาราง (เหมือน VLOOKUP แต่ทำทั้งตารางทีเดียว)

```python
prod = pd.read_csv("production.csv")
machines = pd.read_csv("machines.csv")

df = prod.merge(machines, on="machine_id", how="left")
```

| how | ได้อะไร |
|---|---|
| `"left"` | เก็บทุกแถวของตารางซ้าย (ใช้บ่อยที่สุด — ไม่ทำข้อมูลหลัก) |
| `"inner"` | เฉพาะที่จับคู่ได้ทั้งสองฝั่ง |
| `"outer"` | ทุกแถวของทั้งสองฝั่ง |

**ตรวจทุกครั้งหลัง merge** ว่าจำนวนแถวเปลี่ยนไหม
```python
print(len(prod), "->", len(df))       # ถ้าเพิ่มขึ้น = ตารางขวามีคีย์ซ้ำ!
print(df["name"].isna().sum())        # จับคู่ไม่ได้กี่แถว
```
แถวเพิ่มขึ้นหลัง merge คือบั๊กที่ทำให้ยอดรวมเกินความจริง และตรวจไม่เจอถ้าไม่ดูตรงนี้

### วันที่ใน pandas

```python
df["date"] = pd.to_datetime(df["date"])
df["เดือน"] = df["date"].dt.to_period("M").astype(str)   # 2026-06
df["วันในสัปดาห์"] = df["date"].dt.day_name()
monthly = df.groupby("เดือน")["downtime_min"].sum()
```

`.dt` คือประตูสู่ทุกอย่างที่เกี่ยวกับวันที่ (`.dt.year`, `.dt.month`, `.dt.hour`, `.dt.days`)

### ส่งออก

```python
summary.to_excel("รายงาน_downtime.xlsx", index=False)
summary.to_csv("สรุป.csv", index=False, encoding="utf-8-sig")

# หลายชีตในไฟล์เดียว
with pd.ExcelWriter("รายงานเดือน.xlsx") as writer:
    summary.to_excel(writer, sheet_name="สรุปรายเครื่อง", index=False)
    monthly.to_frame().to_excel(writer, sheet_name="รายเดือน")
```

`index=False` เกือบทุกครั้ง ไม่งั้นจะมีคอลัมน์เลขลำดับติดไปด้วยจนคนรับไฟล์งง
และ `encoding="utf-8-sig"` สำหรับ CSV ที่จะเปิดใน Excel

### รูปแบบสคริปต์รายงานที่ใช้จริง

```python
def build_report(prod_path, machine_path, out_path):
    prod = pd.read_csv(prod_path)
    machines = pd.read_csv(machine_path)
    df = prod.merge(machines, on="machine_id", how="left")
    df["run_min"] = df["planned_min"] - df["downtime_min"]

    summary = (df.groupby(["line", "machine_id", "name"])
                 .agg(downtime=("downtime_min", "sum"),
                      ชิ้นดี=("good_qty", "sum"))
                 .reset_index()
                 .sort_values("downtime", ascending=False))
    summary.to_excel(out_path, index=False)
    return summary
```
เขียนครั้งเดียว แล้วเดือนหน้าแค่กดรัน — นี่คือจุดที่การเรียนทั้งหมดคืนทุน
""",
            "pitfalls": [
                "merge แล้วแถวเพิ่มขึ้นเพราะตารางขวามีคีย์ซ้ำ — ตรวจด้วย `machines[\"machine_id\"].duplicated().any()`",
                "merge ด้วยคีย์ที่ชนิดต่างกัน (int กับ str) แล้วจับคู่ไม่ได้เลยสักแถว",
                "ลืม `index=False` ตอน to_excel ทำให้มีคอลัมน์ดัชนีเกินมา",
                "เขียนทับไฟล์รายงานเดิมโดยไม่ได้ตั้งใจ — ใส่วันที่ในชื่อไฟล์ผลลัพธ์",
            ],
            "demo": '''import pandas as pd

prod = pd.read_csv("production.csv")
machines = pd.read_csv("machines.csv")

df = prod.merge(machines, on="machine_id", how="left")
print(f"ก่อน merge {len(prod)} แถว -> หลัง merge {len(df)} แถว")
print("จับคู่ไม่ได้:", df["name"].isna().sum(), "แถว")

df["date"] = pd.to_datetime(df["date"])
df["สัปดาห์"] = df["date"].dt.isocalendar().week

report = (df.groupby(["line", "machine_id", "name"])
            .agg(downtime=("downtime_min", "sum"), ชิ้นดี=("good_qty", "sum"))
            .reset_index()
            .sort_values("downtime", ascending=False))
print("\\n", report.head(5).to_string(index=False))

report.to_csv("รายงาน.csv", index=False, encoding="utf-8-sig")
print("\\nบันทึกไฟล์รายงาน.csv แล้ว")
''',
            "task": "รวม production.csv กับ machines.csv แล้วหาว่าเครื่องที่ติดตั้งก่อนปี 2018 มี downtime เฉลี่ยต่างจากเครื่องใหม่เท่าไร",
            "quiz": ["q_m7l5_1", "q_m7l5_2"],
        },
    ],
}
