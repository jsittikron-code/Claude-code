"""โมดูล 8 — จากสคริปต์สู่เครื่องมือที่ทีมใช้"""

MODULE = {
    "id": "m8",
    "title": "จากสคริปต์สู่เครื่องมือที่ทีมใช้",
    "icon": ":material/deployed_code:",
    "goal": "จัดโครงโปรเจกต์ ทำหน้าเว็บให้คนอื่นใช้ และเขียนโค้ดที่ดูแลต่อได้",
    "lessons": [
        # ------------------------------------------------------------------
        {
            "id": "m8l1",
            "title": "จัดโครงโปรเจกต์ venv และ pip",
            "minutes": 9,
            "goal": "ติดตั้งไลบรารีอย่างเป็นระบบและย้ายโปรเจกต์ไปเครื่องอื่นได้",
            "body": """
### ติดตั้งไลบรารี

```bat
python -m pip install pandas openpyxl streamlit
python -m pip list                       ดูว่าติดตั้งอะไรไว้บ้าง
python -m pip install --upgrade pandas
```

ใช้ `python -m pip` แทน `pip` เฉย ๆ เพื่อให้แน่ใจว่าติดตั้งลง Python ตัวที่คุณกำลังรันจริง
(เครื่องที่มี Python หลายเวอร์ชันเจอปัญหานี้บ่อยมาก: ติดตั้งแล้วแต่ import ไม่เจอ)

### virtual environment — แยกของแต่ละโปรเจกต์

```bat
python -m venv .venv
.venv\\Scripts\\activate            :: Windows
python -m pip install -r requirements.txt
deactivate
```

ทำไมต้องแยก: โปรเจกต์ A ต้องการ pandas 1.5 แต่โปรเจกต์ B ต้องการ 2.2
ถ้าติดตั้งรวมกันในเครื่อง จะมีอันหนึ่งพังเสมอ

### requirements.txt

```
pandas>=2.0
openpyxl>=3.1
streamlit>=1.57
```

```bat
python -m pip freeze > requirements.txt      :: บันทึกของที่ใช้อยู่
python -m pip install -r requirements.txt    :: ติดตั้งตามรายการ
```

ไฟล์นี้คือสิ่งที่ทำให้เพื่อนร่วมงานรันโปรแกรมของคุณได้โดยไม่ต้องถามว่าต้องลงอะไรบ้าง

### โครงโฟลเดอร์ที่โตต่อได้

```
oee_report/
├─ .venv/                  สภาพแวดล้อมเฉพาะโปรเจกต์ (ไม่ต้องส่งต่อ)
├─ data/                   ไฟล์ข้อมูลดิบ
├─ output/                 ไฟล์รายงานที่สร้างออกมา
├─ src/
│  ├─ loader.py            อ่านและทำความสะอาดข้อมูล
│  ├─ metrics.py           สูตรคำนวณ (ฟังก์ชันบริสุทธิ์ ทดสอบง่าย)
│  └─ report.py            ประกอบรายงานและส่งออก
├─ app.py                  หน้าเว็บ Streamlit
├─ run.bat                 ดับเบิลคลิกแล้วทำงาน (สำคัญมากสำหรับผู้ใช้ทั่วไป)
└─ requirements.txt
```

หลักการแบ่ง: **อ่านข้อมูล / คำนวณ / แสดงผล แยกไฟล์กัน**
เพราะสามอย่างนี้เปลี่ยนด้วยเหตุผลคนละแบบ — แหล่งข้อมูลเปลี่ยน, สูตรเปลี่ยน, รูปแบบรายงานเปลี่ยน

### ไฟล์ .bat ให้คนอื่นกดใช้

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
python app.py
pause
```
`cd /d "%~dp0"` = ย้ายไปโฟลเดอร์ที่ไฟล์ .bat วางอยู่ ทำให้พาธไฟล์ข้อมูลถูกเสมอ
และ `pause` ทำให้หน้าต่างไม่ปิดหนีตอนเกิดข้อผิดพลาด — จะได้อ่านข้อความทัน
""",
            "pitfalls": [
                "ติดตั้งไลบรารีด้วย pip ของ Python คนละเวอร์ชันกับที่รันอยู่ แล้ว import ไม่เจอ",
                "ส่งโฟลเดอร์ .venv ให้เพื่อน (ใหญ่และใช้ไม่ได้ข้ามเครื่อง) — ส่ง requirements.txt แทน",
                "ใช้พาธเต็มแบบตายตัวในโค้ด ทำให้ย้ายเครื่องแล้วพัง",
                "ไม่มี pause ในไฟล์ .bat หน้าต่างเลยปิดก่อนที่ผู้ใช้จะอ่านข้อความผิดพลาดทัน",
            ],
            "demo": '''from pathlib import Path
import sys

print("Python ที่กำลังรัน:", sys.version.split()[0])
print("ไฟล์นี้อยู่ที่:", Path.cwd())

# วิธีอ้างพาธที่ย้ายเครื่องแล้วไม่พัง — อิงจากตำแหน่งไฟล์ ไม่ใช่พาธตายตัว
base = Path.cwd()
for folder in ["data", "output"]:
    print(f"เตรียมโฟลเดอร์: {base / folder}")
''',
            "task": "สร้างโฟลเดอร์โปรเจกต์ตามโครงข้างบนสำหรับงานรายงาน downtime ของคุณ พร้อมไฟล์ requirements.txt",
            "quiz": ["q_m8l1_1", "q_m8l1_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m8l2",
            "title": "Streamlit — เปลี่ยนสคริปต์เป็นหน้าเว็บ",
            "minutes": 10,
            "goal": "ทำหน้าเว็บให้คนอื่นใช้งานสคริปต์ของคุณได้โดยไม่ต้องเขียนโค้ด",
            "body": """
สคริปต์ที่รันในหน้าต่างคำสั่งมีคุณอยู่คนเดียวที่ใช้เป็น
Streamlit เปลี่ยนสคริปต์เดิมให้เป็นหน้าเว็บได้ **โดยแทบไม่ต้องรู้ HTML เลย**

```python
import pandas as pd
import streamlit as st

st.title("รายงาน Downtime")

df = pd.read_csv("production.csv")

line = st.selectbox("เลือกสายการผลิต", ["ทั้งหมด"] + sorted(df["line"].unique()))
if line != "ทั้งหมด":
    df = df[df["line"] == line]

st.metric("Downtime รวม", f"{df['downtime_min'].sum():,} นาที")

summary = df.groupby("machine_id")["downtime_min"].sum().sort_values(ascending=False)
st.bar_chart(summary)
st.dataframe(df.head(50))
```

รันด้วย `python -m streamlit run app.py` แล้วเปิดเบราว์เซอร์ที่ localhost:8501

### วิธีคิดของ Streamlit

**ทุกครั้งที่ผู้ใช้กดอะไร สคริปต์ทั้งไฟล์จะถูกรันใหม่ตั้งแต่บรรทัดแรก**
เข้าใจข้อนี้แล้วจะเข้าใจทุกอย่างที่เหลือ

ผลที่ตามมา
* โค้ดที่ช้า (อ่านไฟล์ใหญ่) จะทำงานซ้ำทุกครั้ง → ใช้ `@st.cache_data` ครอบไว้
* ตัวแปรธรรมดาถูกล้างทุกรอบ → ถ้าต้องจำค่าข้ามการกด ใช้ `st.session_state`

```python
@st.cache_data
def load(path):
    return pd.read_csv(path)      # อ่านครั้งเดียว รอบต่อไปดึงจากแคช
```

### วิดเจ็ตที่ใช้บ่อย

| คำสั่ง | ได้อะไร |
|---|---|
| `st.selectbox` / `st.multiselect` | เลือกจากรายการ |
| `st.slider` / `st.date_input` | ช่วงตัวเลข / วันที่ |
| `st.file_uploader` | ให้ผู้ใช้อัปโหลด Excel เข้ามาเอง |
| `st.metric` | การ์ดตัวเลข KPI |
| `st.dataframe` / `st.line_chart` / `st.bar_chart` | ตารางและกราฟ |
| `st.download_button` | ปุ่มดาวน์โหลดผลลัพธ์ |
| `st.columns` / `st.tabs` / `st.expander` | จัดหน้า |

### ให้คนอื่นในโรงงานเข้าถึง

```bat
python -m streamlit run app.py --server.port 8510 --server.address 0.0.0.0
```
แล้วเปิดพอร์ตในไฟร์วอลล์ เพื่อนร่วมงานเข้าที่ `http://<ไอพีเครื่องคุณ>:8510` ได้เลย
(แดชบอร์ดที่คุณใช้อยู่ในโฟลเดอร์นี้ก็ทำแบบเดียวกัน)
""",
            "pitfalls": [
                "ลืมว่าสคริปต์รันใหม่ทั้งไฟล์ทุกครั้งที่กดปุ่ม แล้วงงว่าทำไมตัวแปรถูกล้าง",
                "อ่านไฟล์ใหญ่โดยไม่ใส่ @st.cache_data ทำให้หน้าเว็บช้ามาก",
                "ใส่ปุ่มซ้อนปุ่ม (`if st.button(): if st.button():`) ซึ่งไม่ทำงานอย่างที่คิด — ใช้ session_state แทน",
                "เปิดพอร์ตให้เข้าถึงทั้งเครือข่ายโดยไม่มีระบบล็อกอิน ทั้งที่ข้อมูลเป็นความลับของบริษัท",
            ],
            "demo": '''# ตัวอย่างนี้แสดงโครงของแอป Streamlit (รันในสนามซ้อมจะไม่เห็นหน้าเว็บ
# ให้คัดลอกไปไว้ในไฟล์ app.py แล้วสั่ง  python -m streamlit run app.py)
code = """
import pandas as pd
import streamlit as st

st.set_page_config(page_title="รายงาน Downtime", layout="wide")
st.title("รายงาน Downtime รายเครื่อง")

@st.cache_data
def load(path):
    return pd.read_csv(path)

df = load("production.csv")
line = st.selectbox("สายการผลิต", ["ทั้งหมด"] + sorted(df["line"].unique()))
if line != "ทั้งหมด":
    df = df[df["line"] == line]

c1, c2, c3 = st.columns(3)
c1.metric("Downtime รวม", f"{df['downtime_min'].sum():,} นาที")
c2.metric("จำนวนกะ", f"{len(df):,}")
c3.metric("ของเสียรวม", f"{df['reject_qty'].sum():,} ชิ้น")

st.bar_chart(df.groupby("machine_id")["downtime_min"].sum())
st.dataframe(df.head(50), width="stretch")
"""
print(code)
print("จำนวนบรรทัดทั้งหมด:", len([l for l in code.strip().splitlines() if l.strip()]))
''',
            "task": "คัดลอกโค้ดตัวอย่างไปเป็นไฟล์ app.py ในโฟลเดอร์ที่มี production.csv แล้วสั่งรันด้วย streamlit",
            "quiz": ["q_m8l2_1", "q_m8l2_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m8l3",
            "title": "คลาส — เมื่อไรควรใช้ และเมื่อไรไม่ต้อง",
            "minutes": 9,
            "goal": "อ่านโค้ดที่ใช้คลาสออก และรู้ว่างานแบบไหนคุ้มที่จะสร้างคลาส",
            "body": """
คลาสคือแม่พิมพ์ที่มัด **ข้อมูล** กับ **สิ่งที่ทำกับข้อมูลนั้น** ไว้ด้วยกัน

```python
class Machine:
    def __init__(self, code, name, ideal_rate=1.2):
        self.code = code                # แอตทริบิวต์ประจำตัวแต่ละเครื่อง
        self.name = name
        self.ideal_rate = ideal_rate
        self.records = []

    def add_shift(self, planned, downtime, good, reject):
        self.records.append((planned, downtime, good, reject))

    def total_downtime(self):
        return sum(r[1] for r in self.records)

    def oee(self):
        if not self.records:
            return 0.0
        planned = sum(r[0] for r in self.records)
        downtime = sum(r[1] for r in self.records)
        good = sum(r[2] for r in self.records)
        total = good + sum(r[3] for r in self.records)
        run = planned - downtime
        if run <= 0 or total == 0:
            return 0.0
        return (run / planned) * min(total / (run * self.ideal_rate), 1.0) * (good / total)


m01 = Machine("M01", "เลื่อยตัดแผ่น")
m01.add_shift(480, 45, 380, 20)
m01.add_shift(480, 30, 400, 10)
print(m01.code, m01.total_downtime(), f"{m01.oee():.1%}")
```

* `__init__` ทำงานตอนสร้างวัตถุ ใช้ตั้งค่าเริ่มต้น
* `self` คือตัววัตถุนั้นเอง ต้องเป็นพารามิเตอร์แรกของทุกเมท็อดเสมอ

### เมื่อไร**ควร**ใช้คลาส

* มีของหลายชิ้นที่มีข้อมูลประจำตัวและพฤติกรรมเหมือนกัน (เครื่องจักร, ใบสั่งซ่อม, ผู้ใช้)
* ต้องเก็บสถานะที่เปลี่ยนไปตามเวลา
* มีฟังก์ชันหลายตัวที่รับพารามิเตอร์ชุดเดียวกันซ้ำ ๆ — นั่นคือคลาสที่รอเกิด

### เมื่อไร**ไม่ต้อง**ใช้

* สคริปต์อ่านไฟล์ → คำนวณ → เขียนออก — ฟังก์ชันเพียงพอและเรียบง่ายกว่า
* สร้างคลาสที่มีแค่ `__init__` กับเมท็อดเดียว — ใช้ฟังก์ชันเถอะ
* เก็บข้อมูลตารางล้วน ๆ — ใช้ DataFrame ดีกว่าคลาสที่ทำเอง

> โปรแกรมเมอร์มือใหม่มักสร้างคลาสเยอะเกิน ส่วนมืออาชีพจะสร้างเมื่อมันลดความซับซ้อนจริง
> เกณฑ์ที่ใช้ได้: **ถ้าเขียนด้วยฟังก์ชันแล้วยังอ่านง่าย ก็ไม่ต้องมีคลาส**

### dataclass — เขียนคลาสเก็บข้อมูลแบบสั้น

```python
from dataclasses import dataclass, field

@dataclass
class Breakdown:
    machine: str
    cause: str
    minutes: int
    technician: str = "ไม่ระบุ"

b = Breakdown("M01", "สายพานขาด", 45)
print(b)        # Breakdown(machine='M01', cause='สายพานขาด', minutes=45, ...)
```
`@dataclass` สร้าง `__init__`, `__repr__` และการเปรียบเทียบให้อัตโนมัติ
""",
            "pitfalls": [
                "ลืมใส่ `self` เป็นพารามิเตอร์แรกของเมท็อด → TypeError ตอนเรียก",
                "สร้างคลาสเพราะรู้สึกว่าดูเป็นมืออาชีพ ทั้งที่ฟังก์ชันเรียบง่ายกว่า",
                "เก็บข้อมูลตารางในคลาสที่เขียนเอง แทนที่จะใช้ DataFrame ที่มีเครื่องมือครบแล้ว",
                "ใช้ค่าที่แก้ไขได้เป็นค่าเริ่มต้นของ dataclass ต้องใช้ `field(default_factory=list)`",
            ],
            "demo": '''from dataclasses import dataclass, field

@dataclass
class Machine:
    code: str
    name: str
    ideal_rate: float = 1.2
    records: list = field(default_factory=list)

    def add_shift(self, planned, downtime, good, reject):
        self.records.append((planned, downtime, good, reject))

    def total_downtime(self):
        return sum(r[1] for r in self.records)

    def oee(self):
        if not self.records:
            return 0.0
        planned = sum(r[0] for r in self.records)
        downtime = sum(r[1] for r in self.records)
        good = sum(r[2] for r in self.records)
        total = good + sum(r[3] for r in self.records)
        run = planned - downtime
        if run <= 0 or total == 0:
            return 0.0
        return (run / planned) * min(total / (run * self.ideal_rate), 1.0) * (good / total)


fleet = [Machine("M01", "เลื่อยตัดแผ่น"), Machine("M03", "เครื่องเจาะ CNC")]
fleet[0].add_shift(480, 45, 380, 20)
fleet[0].add_shift(480, 30, 400, 10)
fleet[1].add_shift(480, 180, 250, 40)

for m in sorted(fleet, key=lambda x: x.oee()):
    print(f"{m.code} {m.name:<16} downtime {m.total_downtime():>4} นาที  OEE {m.oee():.1%}")
''',
            "task": "เพิ่มเมท็อด quality() ให้คลาส Machine แล้วเรียงเครื่องตามค่า quality จากน้อยไปมาก",
            "quiz": ["q_m8l3_1", "q_m8l3_2"],
        },
        # ------------------------------------------------------------------
        {
            "id": "m8l4",
            "title": "เขียนโค้ดที่กลับมาอ่านแล้วยังเข้าใจ",
            "minutes": 9,
            "goal": "ใช้แนวปฏิบัติที่ทำให้โค้ดอยู่ได้นานและส่งต่อให้คนอื่นได้",
            "body": """
โค้ดถูกเขียนครั้งเดียวแต่ถูกอ่านนับสิบครั้ง — ส่วนใหญ่โดยตัวคุณเองในอีกหกเดือน

### 1. ตั้งชื่อให้ตรงกับความหมาย

```python
# ❌                          # ✅
d = 45                        downtime_min = 45
def calc(a, b): ...           def availability(planned_min, downtime_min): ...
df2 = df[df.x > 1]            long_stops = shifts[shifts.downtime_min > 60]
```
ใส่หน่วยไว้ในชื่อ (`_min`, `_kw`, `_pct`) ป้องกันบั๊กหน่วยผิด ซึ่งเป็นบั๊กที่แพงที่สุดชนิดหนึ่ง

### 2. ดึงค่าคงที่ขึ้นไปไว้ข้างบน

```python
IDEAL_RATE = 1.2
TARGET_OEE = 0.85
DATA_DIR = Path("data")
```
เลขลอย ๆ กลางโค้ด (`if x > 0.85:`) ทำให้ไม่มีใครรู้ว่ามันคืออะไร และหาแก้ไม่เจอเวลาต้องเปลี่ยน

### 3. ฟังก์ชันละหนึ่งหน้าที่ ยาวไม่เกินหนึ่งหน้าจอ

ถ้าต้องเลื่อนจอเพื่ออ่านฟังก์ชันเดียวจบ แสดงว่ามันทำหลายอย่างเกินไป

### 4. ตรวจข้อมูลเข้าตั้งแต่ต้นทาง

```python
def load_production(path):
    df = pd.read_csv(path)
    required = {"date", "machine_id", "planned_min", "downtime_min"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"ไฟล์ {path} ขาดคอลัมน์: {sorted(missing)}")
    if (df["downtime_min"] < 0).any():
        raise ValueError("พบ downtime ติดลบ ตรวจข้อมูลต้นทาง")
    return df
```
รายงานที่คำนวณจากข้อมูลผิดแล้วส่งให้ผู้บริหาร เสียหายกว่าโปรแกรมที่หยุดทำงานพร้อมบอกเหตุผลมาก

### 5. บันทึกการทำงานด้วย logging แทน print

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("run.log", encoding="utf-8"),
              logging.StreamHandler()],
)

logging.info("เริ่มประมวลผล %s แถว", len(df))
logging.warning("พบ %s แถวที่ downtime เป็นค่าว่าง", n_missing)
```
สคริปต์ที่ตั้งเวลารันอัตโนมัติต้องมีล็อก ไม่งั้นเวลาผิดพลาดตอนตีสองจะไม่มีใครรู้ว่าเกิดอะไร

### 6. อย่าเก็บรหัสผ่านไว้ในโค้ด

ใช้ไฟล์ `.env` หรือตัวแปรสภาพแวดล้อม และอย่าอัปโหลดขึ้น git
(ในโฟลเดอร์นี้มีไฟล์ `.env.example` เป็นตัวอย่างอยู่แล้ว)

### เช็กลิสต์ก่อนส่งงาน

- [ ] รันบนเครื่องที่ไม่ใช่ของตัวเองได้ไหม
- [ ] ถ้าไฟล์ข้อมูลหาย/ผิดรูป โปรแกรมบอกสาเหตุชัดไหม
- [ ] มี requirements.txt และวิธีรันในไฟล์ README ไหม
- [ ] ตัวเลขที่ได้ตรงกับที่เคยทำมือไหม (ตรวจอย่างน้อยหนึ่งงวด)
- [ ] ลบ print ที่ใช้ดีบักออกหมดหรือยัง
""",
            "pitfalls": [
                "ปรับปรุงโค้ดให้สวยแต่ไม่เคยตรวจว่าตัวเลขตรงกับของเดิม",
                "ใส่เลขคงที่กระจายทั่วโค้ด แล้วตอนเปลี่ยนเป้าหมาย OEE ต้องไล่แก้ 12 ที่",
                "ใช้ print แทน logging ในสคริปต์ที่รันอัตโนมัติ ทำให้ตามปัญหาย้อนหลังไม่ได้",
                "commit ไฟล์ที่มีรหัสผ่านหรือข้อมูลลูกค้าขึ้น git",
            ],
            "demo": '''import logging
from pathlib import Path

IDEAL_RATE = 1.2
TARGET_OEE = 0.85
REQUIRED_COLUMNS = {"date", "machine_id", "planned_min", "downtime_min"}

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


def load_production(path):
    """อ่านไฟล์ผลิตพร้อมตรวจความครบถ้วนของคอลัมน์"""
    import pandas as pd
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"ไฟล์ {path} ขาดคอลัมน์: {sorted(missing)}")
    if (df["downtime_min"] < 0).any():
        raise ValueError("พบ downtime ติดลบ ตรวจข้อมูลต้นทางก่อนใช้งาน")
    logging.info("อ่าน %s สำเร็จ %s แถว", path, len(df))
    return df


df = load_production("production.csv")
under = df[df["downtime_min"] > 120]
logging.warning("พบ %s กะที่หยุดเกิน 120 นาที", len(under))
print(f"เป้าหมาย OEE ที่ใช้ = {TARGET_OEE:.0%}, ความเร็วมาตรฐาน {IDEAL_RATE} ชิ้น/นาที")
''',
            "task": "เอาสคริปต์ที่คุณเขียนไว้แล้วมาปรับ: ดึงค่าคงที่ขึ้นบน ตั้งชื่อตัวแปรใหม่ให้มีหน่วย และเพิ่มการตรวจคอลัมน์ที่จำเป็น",
            "quiz": ["q_m8l4_1", "q_m8l4_2"],
        },
    ],
}
