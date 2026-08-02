# คู่มืออ่านโค้ด `monitor.py` — ระบบ Monitoring กระบวนการผลิต

เอกสารนี้อธิบายโค้ดของแดชบอร์ดทีละส่วน ตั้งแต่หลักคิด สถาปัตยกรรม
ไปจนถึงรายละเอียดว่าทำไมแต่ละบรรทัดต้องเขียนแบบนั้น
ใช้คู่กับไฟล์จริงที่ `monitor.py` (794 บรรทัด)

---

## สารบัญ

1. [ภาพรวมสถาปัตยกรรม](#1-ภาพรวมสถาปัตยกรรม)
2. [Streamlit ทำงานยังไง (สำคัญที่สุด)](#2-streamlit-ทำงานยังไง-สำคัญที่สุด)
3. [ส่วนที่ 1: ค่าคงที่และการตั้งค่า](#3-ส่วนที่-1-ค่าคงที่และการตั้งค่า)
4. [ส่วนที่ 2: `load_data()` — อ่านและทำความสะอาดข้อมูล](#4-ส่วนที่-2-load_data--อ่านและทำความสะอาดข้อมูล)
5. [ส่วนที่ 3: ฟังก์ชันคำนวณ](#5-ส่วนที่-3-ฟังก์ชันคำนวณ)
6. [ส่วนที่ 4: ฟังก์ชันวาดหน้าจอ](#6-ส่วนที่-4-ฟังก์ชันวาดหน้าจอ)
7. [ส่วนที่ 5: การโหลดข้อมูล + auto-refresh](#7-ส่วนที่-5-การโหลดข้อมูล--auto-refresh)
8. [ส่วนที่ 6: Sidebar และการกรอง](#8-ส่วนที่-6-sidebar-และการกรอง)
9. [ส่วนที่ 7: แท็บทั้ง 6](#9-ส่วนที่-7-แท็บทั้ง-6)
10. [Altair 101 — อ่านโค้ดกราฟให้ออก](#10-altair-101--อ่านโค้ดกราฟให้ออก)
11. [ความรู้เรื่อง OEE ที่ฝังอยู่ในโค้ด](#11-ความรู้เรื่อง-oee-ที่ฝังอยู่ในโค้ด)
12. [กับดักที่เคยเจอจริงในโปรเจกต์นี้](#12-กับดักที่เคยเจอจริงในโปรเจกต์นี้)
13. [แนวทางต่อยอด](#13-แนวทางต่อยอด)

---

## 1. ภาพรวมสถาปัตยกรรม

```
ไฟล์ Excel (OneDrive)          <- แหล่งข้อมูลจริง (ชีต Report1)
        |
        v
   load_data()                 <- อ่าน + ทำความสะอาด + cache
        |
        v
   DataFrame `data`            <- ข้อมูลทั้งหมดในหน่วยความจำ
        |
        +--> ตัวกรอง sidebar --> DataFrame `filtered`
        |                              |
        v                              v
   แท็บ "ดูตามวัน"              แท็บอื่น ๆ อีก 5 แท็บ
   (ใช้ data ตรง ๆ)             (ใช้ filtered)
        |                              |
        +---------- ฟังก์ชันคำนวณ ------+
                    weighted_pct / machine_summary / daily_weighted
                              |
                              v
                    ฟังก์ชันวาด kpi_card / trend_chart / Altair
```

**หลักคิดที่ใช้ตลอดไฟล์:**

| หลักการ | ทำไม |
|---|---|
| อ่านไฟล์ครั้งเดียว แล้ว cache | ไฟล์ 8,500 แถว อ่านทุกครั้งที่คลิกจะช้ามาก |
| แยกฟังก์ชัน "คำนวณ" ออกจาก "วาด" | เอาฟังก์ชันคำนวณไปใช้ซ้ำได้ทุกแท็บ |
| ค่าคงที่รวมไว้ข้างบนสุด | เปลี่ยนสี/เพิ่มหมวด แก้ที่เดียว ไม่ต้องไล่ทั้งไฟล์ |
| ไม่คำนวณ OEE เอง | ไฟล์ต้นทางคำนวณมาแล้ว ถ้าคำนวณซ้ำจะขัดกับตัวเลขที่ฝ่ายผลิตใช้ |

---

## 2. Streamlit ทำงานยังไง (สำคัญที่สุด)

ถ้าเข้าใจข้อนี้ข้อเดียว จะอ่านโค้ดที่เหลือออกทั้งหมด

> **ทุกครั้งที่ผู้ใช้แตะอะไรสักอย่าง (คลิกปุ่ม เลื่อน slider เลือกวันที่)
> Streamlit จะรัน `monitor.py` ใหม่ตั้งแต่บรรทัดที่ 1 ถึงบรรทัดสุดท้าย**

ไม่มี event handler แบบ JavaScript ไม่มี state ค้างในตัวแปรปกติ — รันใหม่หมดทุกรอบ
เรียกว่า **rerun model**

ผลที่ตามมา 3 ข้อ:

### 2.1 ต้อง cache ไม่งั้นช้า

```python
@st.cache_data(show_spinner="กำลังอ่านไฟล์ข้อมูล...")
def load_data(source, file_mtime=None):
    ...
```

`@st.cache_data` แปลว่า "ถ้าเรียกด้วย argument ชุดเดิม ให้คืนผลลัพธ์เก่าเลย ไม่ต้องรันซ้ำ"
ถ้าไม่มีบรรทัดนี้ ทุกครั้งที่เลื่อน slider จะอ่าน Excel 8,500 แถวใหม่ (ช้า 3–5 วินาที)

### 2.2 ตัวแปรปกติหายทุกรอบ ต้องใช้ `session_state`

```python
st.session_state["_sel_day"] = stored
```

`st.session_state` คือ dict ที่อยู่รอดข้ามการ rerun — แยกกันคนละคนต่อ 1 เบราว์เซอร์
ใช้เก็บ "วันที่ที่ผู้ใช้เลือกไว้"

### 2.3 ลำดับบรรทัดคือลำดับการวาดหน้าจอ

โค้ดบรรทัดบน = แสดงข้างบนหน้าจอ ตรงไปตรงมา
`st.stop()` = หยุดวาดตรงนั้นเลย (ใช้ตอนเจอ error)

---

## 3. ส่วนที่ 1: ค่าคงที่และการตั้งค่า

### 3.1 ตั้งค่าหน้าเพจ (บรรทัด 25–29)

```python
st.set_page_config(
    page_title="Production Monitoring — โรงงาน MDF",
    page_icon="📡",
    layout="wide",
)
```

**ต้องเป็นคำสั่ง Streamlit คำสั่งแรกของไฟล์เสมอ** ไม่งั้น error
`layout="wide"` = ใช้ความกว้างจอเต็ม (ค่า default คือคอลัมน์แคบตรงกลาง ไม่เหมาะกับแดชบอร์ด)

### 3.2 แหล่งข้อมูลแบบมีลำดับสำรอง (บรรทัด 33–37)

```python
DATA_SOURCES = [
    r"C:\Users\p\OneDrive - ...\OEE_ฐานข้อมูลหลัก_2569.xlsx",
    "เดือน1-6.xlsx",
]
```

เป็น list เพราะโค้ดจะ **ไล่ลองทีละไฟล์** ถ้าไฟล์แรกอ่านไม่ได้ (เช่น มีคนเปิด Excel ค้างอยู่
หรือ OneDrive ยังไม่ sync) จะตกไปใช้ไฟล์ที่สองแทน ระบบไม่ล่ม

`r"..."` ข้างหน้าคือ **raw string** — ทำให้ `\` ใน path ของ Windows ไม่ถูกตีความเป็น escape character
(ถ้าไม่ใส่ `r` แล้วเจอ `\n` ใน path จะกลายเป็นขึ้นบรรทัดใหม่ทันที)

### 3.3 Dictionary แปลงชื่อ (บรรทัด 55–82)

```python
LOSS_CATEGORIES = {
    "Setup": "ตั้งเครื่อง / เปลี่ยนรุ่น",
    "Break_time_p": "PM เชิงป้องกัน",
    "Break_time_bp": "ซ่อมแซม (Maintenance)",
    "Break_time_b": "เครื่องเสีย (Breakdown)",
    ...
}
```

**pattern ที่ใช้บ่อยมาก:** dict ที่ map `ชื่อคอลัมน์ในไฟล์` → `ชื่อที่คนอ่านรู้เรื่อง`
เอาไปใช้ 2 อย่างพร้อมกัน:

```python
loss_cols = [c for c in LOSS_CATEGORIES if c in filtered.columns]   # ได้ list ของ key
day_df[loss_cols].sum().rename(index=LOSS_CATEGORIES)               # แปลงเป็นชื่อไทย
```

วน dict เฉย ๆ จะได้ key; `.rename(index=dict)` จะแปลง index ของ Series ตาม dict

> ความหมายของรหัส `b` / `bp` / `p` ได้มาจากชีต `B001` / `BP001` / `P0001`
> ในไฟล์ฐานข้อมูลหลัก ซึ่งบันทึกรายการ Breakdown / Maintenance / Preventive Maintenance ไว้

### 3.4 สี (บรรทัด 85–95)

```python
COLOR_OEE = "#2a78d6"           # น้ำเงิน
COLOR_AVAILABILITY = "#eb6834"  # ส้ม
STATUS_CRITICAL = "#d03b3b"
```

ชุดสีนี้ผ่านการตรวจ **colorblind-safe** มาแล้ว (คนตาบอดสีแยกออก)
สีสถานะ (`STATUS_*`) แยกออกจากสีตัวชี้วัด (`COLOR_*`) โดยตั้งใจ
เพื่อไม่ให้ "สีแดง = วิกฤต" ไปชนกับ "สีแดง = ตัวชี้วัดอันที่ 4"

---

## 4. ส่วนที่ 2: `load_data()` — อ่านและทำความสะอาดข้อมูล

หัวใจของไฟล์ อยู่บรรทัด 114–159

### 4.1 เทคนิค cache key ที่ต้องเข้าใจ

```python
@st.cache_data(show_spinner="กำลังอ่านไฟล์ข้อมูล...")
def load_data(source, file_mtime: float | None = None) -> pd.DataFrame:
    # file_mtime ไม่ได้ใช้ในฟังก์ชัน แต่เป็นส่วนหนึ่งของ cache key
```

พารามิเตอร์ `file_mtime` **ไม่ได้ถูกใช้ในตัวฟังก์ชันเลย** — แล้วใส่ทำไม?

เพราะ `@st.cache_data` ตัดสินใจว่า "ต้องรันใหม่ไหม" จาก **argument ที่ส่งเข้ามา**
ถ้าส่งแค่ `load_data(path)` เมื่อไฟล์ถูกแก้ Streamlit จะยังคืนข้อมูลเก่า
เพราะ path เหมือนเดิม

พอส่ง `load_data(path, os.path.getmtime(path))` ตอนไฟล์ถูกแก้
เวลาแก้ไขไฟล์เปลี่ยน → argument เปลี่ยน → cache ไม่ตรง → อ่านไฟล์ใหม่อัตโนมัติ

นี่คือกลไกที่ทำให้ **อัปเดตไฟล์ Excel แล้วแดชบอร์ดเห็นข้อมูลใหม่**

### 4.2 เลือกชีตแบบยืดหยุ่น

```python
xl = pd.ExcelFile(source, engine="openpyxl")
sheet = "Report1" if "Report1" in xl.sheet_names else 0
df = pd.read_excel(xl, sheet_name=sheet)
```

ไฟล์ฐานข้อมูลหลักมี 6 ชีต (`Report1`, `หมวดหมู่เครื่อง`, `วิธีคิด OEE`, `B001`, `BP001`, `P0001`)
ต้องระบุให้ชัดว่าเอา `Report1` ไม่งั้น pandas จะหยิบชีตแรกมาให้
`else 0` = ถ้าไม่มีชีตชื่อนี้ ให้ใช้ชีตแรก (เผื่อไฟล์ที่อัปโหลดมาโครงสร้างต่าง)

การเปิดด้วย `pd.ExcelFile()` ก่อนแล้วค่อย `read_excel(xl, ...)` **เปิดไฟล์ครั้งเดียว**
ถ้าเขียน `pd.read_excel(path, sheet_name=...)` ตรง ๆ สองครั้ง จะเปิดไฟล์สองรอบ ช้ากว่า

### 4.3 ตรวจคอลัมน์ก่อนใช้งาน

```python
missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
if missing:
    raise ValueError("ไฟล์ขาดคอลัมน์: " + ", ".join(missing) + ...)
```

**fail fast** — ถ้าไฟล์ผิดรูปแบบ บอกทันทีว่าขาดคอลัมน์ไหน
ดีกว่าปล่อยให้ไป error ลึก ๆ ตอนวาดกราฟแล้วอ่านไม่ออกว่าเกิดอะไรขึ้น

### 4.4 ทำความสะอาดข้อมูล 4 ขั้น

```python
# ขั้น 1 — แปลงวันที่ ตัวไหนแปลงไม่ได้ให้เป็น NaT แล้วทิ้งแถวนั้น
df["Trans_date"] = pd.to_datetime(df["Trans_date"], errors="coerce")
df = df.dropna(subset=["Trans_date"])

# ขั้น 2 — แปลงตัวเลข ตัวไหนแปลงไม่ได้ให้เป็น 0
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# ขั้น 3 — ตัดเพดาน % ไม่ให้เกิน 100
for col in METRIC_COLS.values():
    df[col] = df[col].clip(lower=0, upper=100)

# ขั้น 4 — สร้างคอลัมน์ช่วย
df["Month"] = df["Trans_date"].dt.to_period("M").dt.to_timestamp()
df["Machine"] = df["MC"] + " — " + df["Description"].str.strip()
```

**`errors="coerce"` คือพระเอก** — แปลว่า "ถ้าแปลงไม่ได้อย่า error ให้ใส่ค่าว่างแทน"
ข้อมูลจากหน้างานจริงมักมีเซลล์ว่าง มีข้อความปนในคอลัมน์ตัวเลข ถ้าไม่ใส่ตัวนี้แอปจะพังทันที

**ทำไมต้อง clip ที่ 100?** ข้อมูลจริงมี 585 แถวที่ OEE เกิน 100%
(ผลิตได้เกิน Cap ที่ตั้งไว้) ถ้าปล่อยไว้ ค่าเฉลี่ยจะถูกดันสูงเกินจริง

**`to_period("M").to_timestamp()`** = ปัดวันที่ทุกวันให้เป็นวันที่ 1 ของเดือนนั้น
เช่น 15/03/2026 → 01/03/2026 ใช้สำหรับ group รายเดือน

### 4.5 หมวดหมู่เครื่อง — ใช้ของจริงก่อน ค่อย fallback

```python
prefix_group = (
    df["MC"].astype(str).str.extract(r"^([A-Za-z]+)")[0].str.upper()
    .map(lambda g: GROUP_NAMES.get(g, g))
)
if "หมวดหมู่เครื่อง" in df.columns:
    df["Group"] = df["หมวดหมู่เครื่อง"].astype(str).str.strip().replace(
        {"": None, "nan": None}
    ).fillna(prefix_group)
else:
    df["Group"] = prefix_group
```

อ่านจากล่างขึ้นบน:
1. ถ้าไฟล์**มี**คอลัมน์ `หมวดหมู่เครื่อง` (ที่โรงงานจัดกลุ่มไว้เอง) → ใช้อันนั้น
2. ถ้าช่องไหนว่าง → `.fillna(prefix_group)` เติมด้วยการเดาจากรหัส
3. ถ้าไฟล์**ไม่มี**คอลัมน์นั้นเลย → เดาจากรหัสทั้งหมด

`str.extract(r"^([A-Za-z]+)")` = regex ดึงตัวอักษรที่อยู่หน้าสุดของรหัส
เช่น `CT-40` → `CT`, `SKL-1` → `SKL` แล้วเอาไปเปิด dict `GROUP_NAMES`

`.get(g, g)` = ถ้าหาไม่เจอใน dict ให้คืนตัวมันเอง (ไม่ error, ไม่ได้ค่าว่าง)

---

## 5. ส่วนที่ 3: ฟังก์ชันคำนวณ

### 5.1 `weighted_pct()` — ค่าเฉลี่ยถ่วงน้ำหนัก (บรรทัด 162–166)

```python
def weighted_pct(df, col, wcol="เวลาทำงาน/วัน") -> float:
    w = df[wcol]
    total = w.sum()
    return float((df[col] * w).sum() / total) if total > 0 else 0.0
```

**ฟังก์ชันที่สำคัญที่สุดในไฟล์** และเป็นจุดที่คนทำแดชบอร์ดมือใหม่มักพลาด

สมมติมี 2 เครื่อง:

| เครื่อง | เวลาทำงาน | OEE |
|---|---|---|
| A | 480 นาที | 30% |
| B | 60 นาที | 90% |

- **ค่าเฉลี่ยธรรมดา** (`.mean()`) = (30 + 90) / 2 = **60%** ← หลอกตา
- **ถ่วงน้ำหนัก** = (30×480 + 90×60) / (480+60) = **36.7%** ← ตรงความจริง

เครื่อง B เดินแค่ 1 ชั่วโมงแต่ได้คะแนนเท่ากับเครื่องที่เดินทั้งวัน — ไม่ยุติธรรม
สูตรถ่วงน้ำหนักให้น้ำหนักตามเวลาที่เดินจริง

`if total > 0 else 0.0` = กันหารด้วยศูนย์ (วันที่ไม่มีเครื่องไหนเดินเลย)

### 5.2 `daily_weighted()` — สรุปรายวัน (บรรทัด 169–177)

```python
def daily_weighted(df) -> pd.DataFrame:
    rows = []
    for d, g in df.groupby("Trans_date"):
        row = {"Trans_date": d}
        for name, col in METRIC_COLS.items():
            row[name] = weighted_pct(g, col)
        rows.append(row)
    return pd.DataFrame(rows)
```

`df.groupby("Trans_date")` คืน generator ที่วนได้เป็นคู่ `(ค่าที่ group, DataFrame ย่อย)`
โค้ดนี้จึงแปลว่า "แต่ละวัน เอา DataFrame ของวันนั้นมาคิด weighted_pct ทั้ง 4 ตัวชี้วัด"

ผลลัพธ์: DataFrame ที่ 1 แถว = 1 วัน มีคอลัมน์ `OEE`, `Availability`, `Performance`, `Quality`

> เขียนแบบ loop เพราะอ่านง่ายและช้าไม่พอให้รู้สึก (แค่ ~140 วัน)
> ถ้าข้อมูลเป็นหลักแสนแถวค่อยเปลี่ยนไปใช้ `groupby().apply()` แบบ vectorized

### 5.3 `machine_summary()` — สรุปรายเครื่อง + จัดสถานะ (บรรทัด 180–203)

```python
for (mc, machine), g in df.groupby(["MC", "Machine"]):
    row = {
        "MC": mc,
        "Machine": machine,
        "จำนวนวัน": g["Trans_date"].nunique(),
        "เวลาสูญเสียรวม (นาที)": g["เวลาสูญเสีย/วัน"].sum(),
    }
```

`groupby(["MC", "Machine"])` group ด้วย 2 คอลัมน์ → key ที่ได้เป็น tuple จึงเขียน `(mc, machine)`
group ด้วย `Machine` ไปด้วยเพื่อให้ชื่อเต็มติดมาในผลลัพธ์ ไม่ต้อง join ทีหลัง

```python
def status(oee: float) -> str:
    if oee >= threshold:
        return "🟢 ปกติ"
    if oee >= threshold * 0.75:
        return "🟡 เฝ้าระวัง"
    return "🔴 วิกฤต"

out["สถานะ"] = out["OEE"].map(status)
```

**nested function** — ประกาศฟังก์ชันข้างในฟังก์ชัน ทำได้เพราะต้องใช้ค่า `threshold`
ที่รับเข้ามา (closure) `.map(func)` = เอาทุกค่าในคอลัมน์ไปผ่านฟังก์ชันทีละตัว

เกณฑ์ `threshold * 0.75` = โซนเฝ้าระวังคือ 75% ของเกณฑ์ขึ้นไป
ถ้าเกณฑ์ 50% → 37.5–50% = เฝ้าระวัง, ต่ำกว่า 37.5% = วิกฤต

---

## 6. ส่วนที่ 4: ฟังก์ชันวาดหน้าจอ

### 6.1 `kpi_card()` — การ์ด KPI ด้วย HTML (บรรทัด 206–228)

```python
card_html = (
    f'<div style="background: linear-gradient(135deg, {color}15 0%, {color}05 100%);'
    f'border-left: 6px solid {color}; border-radius: 12px; padding: 16px 20px;'
    ...
)
st.markdown(card_html, unsafe_allow_html=True)
```

**จุดที่ต้องระวังที่สุดในไฟล์นี้** (เคยพังมาแล้วจริง — ดูหัวข้อ 12):

> ต้องเขียน HTML แบบ **ไม่มีการเยื้องหน้าบรรทัด** เด็ดขาด

เพราะ Streamlit ส่งข้อความผ่าน Markdown parser ก่อน และ Markdown ตีความว่า
"บรรทัดที่เยื้อง 4 ช่องขึ้นไป = code block" → HTML จะโผล่เป็นตัวหนังสือดิบ ๆ บนหน้าจอ

การต่อ string ด้วยวงเล็บหลาย ๆ บรรทัดแบบนี้ ทำให้ string จริง **ไม่มี newline และไม่มีช่องว่างนำหน้า**
แต่โค้ดยังอ่านง่ายอยู่

`{color}15` = ต่อ hex สี 6 หลักด้วย `15` กลายเป็น 8 หลัก = สีเดิมแต่โปร่งใส ~8%
(`AARRGGBB` แบบ CSS: 2 หลักท้ายคือ alpha)

```python
value_text = f"{value:.1f}%" if unit == "%" else f"{value:,.0f} {unit}"
```

format string ของ Python:
- `:.1f` = ทศนิยม 1 ตำแหน่ง
- `:,.0f` = ไม่มีทศนิยม + ใส่ comma คั่นหลักพัน
- `:+.1f` = บังคับแสดงเครื่องหมาย + หรือ − (ใช้ในตัวเลขเทียบวันก่อน)

### 6.2 `trend_chart()` — กราฟเส้นหลายเส้น (บรรทัด 231–259)

```python
plot_df = daily.melt(id_vars="Trans_date", value_vars=metrics,
                     var_name="ตัวชี้วัด", value_name="ค่า")
```

**`melt()` คือหัวใจของการทำกราฟหลายเส้น** — แปลงจาก wide เป็น long:

จาก (wide):
| Trans_date | OEE | Availability |
|---|---|---|
| 01/07 | 28 | 48 |

เป็น (long):
| Trans_date | ตัวชี้วัด | ค่า |
|---|---|---|
| 01/07 | OEE | 28 |
| 01/07 | Availability | 48 |

Altair ต้องการรูปแบบ long เพราะมันวาดเส้นโดย "แยกสีตามค่าในคอลัมน์เดียว"
(`color="ตัวชี้วัด:N"`) ไม่ใช่ "วาดทีละคอลัมน์"

```python
color_scale = alt.Scale(
    domain=list(METRIC_COLS.keys()),
    range=[METRIC_COLOR[m] for m in METRIC_COLS],
)
```

**ล็อกสีให้ผูกกับชื่อตัวชี้วัด ไม่ใช่ลำดับ**
ถ้าไม่ล็อก พอผู้ใช้ติ๊กเอา 3 เส้นออก เส้น OEE ที่เหลืออาจเปลี่ยนสีเอง — สับสนมาก

```python
return line + rule
```

เครื่องหมาย `+` ใน Altair = **layer** (ซ้อนกราฟ) — เอาเส้นเป้าหมายมาซ้อนบนกราฟเส้น

---

## 7. ส่วนที่ 5: การโหลดข้อมูล + auto-refresh

### 7.1 ไล่ลองหลายไฟล์ (บรรทัด 300–317)

```python
for path in DATA_SOURCES:
    if not os.path.exists(path):
        continue
    try:
        data = load_data(path, os.path.getmtime(path))
        source_name = os.path.basename(path)
        source_mtime = pd.Timestamp.fromtimestamp(os.path.getmtime(path))
        break
    except Exception as e:
        load_errors.append(f"{os.path.basename(path)}: {e}")
```

pattern **try each source until one works**:
- `continue` = ไฟล์ไม่มี ข้ามไปตัวถัดไป
- `break` = สำเร็จแล้ว หยุดวน
- `except` = อ่านไม่ได้ (ไฟล์ถูกล็อก/เสีย) เก็บ error ไว้ แล้วลองตัวถัดไป

เก็บ `source_mtime` ไว้เพื่อโชว์ให้ผู้ใช้เห็นว่า "ฐานข้อมูลอัปเดตล่าสุดเมื่อไหร่"

### 7.2 auto-refresh ด้วย fragment (บรรทัด 277–286)

```python
@st.fragment(run_every="30s")
def watch_data_file():
    sig = tuple(
        os.path.getmtime(p) if os.path.exists(p) else None for p in DATA_SOURCES
    )
    prev = st.session_state.get("_data_sig")
    st.session_state["_data_sig"] = sig
    if prev is not None and sig != prev:
        st.rerun(scope="app")
```

`@st.fragment(run_every="30s")` = ฟังก์ชันนี้จะถูกเรียกซ้ำเองทุก 30 วินาที
**โดยไม่รันทั้งไฟล์ใหม่** (ถ้ารันทั้งไฟล์ทุก 30 วิ จะกินทรัพยากรและหน้าจอกระพริบ)

ตรรกะ:
1. อ่านเวลาแก้ไขไฟล์ทุกไฟล์ เก็บเป็น tuple เรียก "ลายเซ็น" (signature)
2. เทียบกับลายเซ็นรอบก่อนที่เก็บใน `session_state`
3. ถ้าต่างกัน = ไฟล์ถูกแก้ → `st.rerun(scope="app")` สั่งรันใหม่ทั้งแอป

`scope="app"` สำคัญ — ถ้าไม่ใส่ จะ rerun แค่ fragment ตัวเอง หน้าจอไม่อัปเดต

`prev is not None` = รอบแรกไม่ต้อง rerun (ยังไม่มีอะไรให้เทียบ)

---

## 8. ส่วนที่ 6: Sidebar และการกรอง

### 8.1 ปุ่มล้าง cache (บรรทัด 323–325)

```python
if st.button("🔄 โหลดข้อมูลใหม่", help="..."):
    st.cache_data.clear()
    st.rerun()
```

`st.button()` คืน `True` **เฉพาะรอบที่เพิ่งถูกกด** รอบถัดไปกลับเป็น `False`
จึงเขียนเป็น `if st.button(...):` ได้เลย

### 8.2 การกรองข้อมูล (บรรทัด 345–358)

```python
filtered = data
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["Trans_date"] >= pd.Timestamp(start))
        & (filtered["Trans_date"] <= pd.Timestamp(end))
    ]
if sel_groups:
    filtered = filtered[filtered["Group"].isin(sel_groups)]
```

**boolean masking** — วิธีกรอง DataFrame มาตรฐานของ pandas
- ต้องใช้ `&` ไม่ใช่ `and` (pandas ทำงานทีละแถวพร้อมกัน ไม่ใช่ค่าเดี่ยว)
- ต้องครอบวงเล็บทุกเงื่อนไข เพราะ `&` มีลำดับความสำคัญสูงกว่า `>=`

`isinstance(date_range, tuple)` ต้องเช็คเพราะ **ระหว่างที่ผู้ใช้กำลังเลือกวันแรก
`st.date_input` แบบช่วงจะคืนค่ามาแค่ตัวเดียว** ถ้าไม่เช็คแล้วไป unpack จะ error ทันที

---

## 9. ส่วนที่ 7: แท็บทั้ง 6

```python
tab_daily, tab_overview, tab_alert, tab_machine, tab_loss, tab_table = st.tabs([...])

with tab_daily:
    ...
```

`st.tabs()` คืน list ของ tab object เอามา unpack เป็นตัวแปร แล้วใช้ `with` เพื่อกำหนดว่า
"โค้ดในบล็อกนี้ให้วาดในแท็บนั้น"

> **ข้อควรรู้:** Streamlit วาด**ทุกแท็บ**ทุกรอบ ไม่ได้วาดเฉพาะแท็บที่เปิดอยู่
> ถ้าแท็บไหนคำนวณหนัก จะช้าทุกรอบแม้ผู้ใช้ไม่เคยเปิดแท็บนั้น

### 9.1 แท็บ "ดูตามวัน" — จุดที่ยากที่สุด (บรรทัด 371–524)

**ก) แยก data pool ออกจาก filtered**

```python
day_pool = data[data["Group"].isin(sel_groups)] if sel_groups else data
```

ใช้ `data` (ทั้งหมด) ไม่ใช่ `filtered` — จงใจ เพื่อให้เลือกดูวันไหนก็ได้
โดยไม่ต้องไปขยายช่วงวันที่ใน sidebar ก่อน แต่ยังเคารพตัวกรองกลุ่มเครื่อง

**ข) จัดการ session_state ของ date picker**

```python
stored = st.session_state.get("_sel_day", latest_day)
if not (available_days[0] <= stored <= latest_day):
    stored = latest_day
st.session_state["_sel_day"] = stored

sel_day = st.date_input("เลือกวันที่ต้องการดู",
                        min_value=available_days[0],
                        max_value=latest_day,
                        key="_sel_day")
```

3 บรรทัดแรกคือ **การป้องกันค่าหลุดช่วง** — ถ้าผู้ใช้เลือกวันที่ 27/07 ไว้
แล้วไปเปลี่ยนตัวกรองกลุ่มเป็นกลุ่มที่มีข้อมูลถึงแค่ 20/07 ค่าเก่าจะหลุดช่วง → error
โค้ดนี้ดึงกลับมาเป็นวันล่าสุดที่มีจริง

สังเกตว่า **ไม่มี `value=`** ในการเรียก `st.date_input` — เพราะเมื่อใช้ `key=`
Streamlit จะอ่านค่าเริ่มต้นจาก `session_state[key]` ให้เอง
ถ้าใส่ทั้ง `value=` และ `key=` จะได้ warning

**ค) ปุ่มที่แก้ค่า widget อื่น — ต้องใช้ `on_click`**

```python
st.button(
    "⏭ ไปวันล่าสุดในฐานข้อมูล",
    width="stretch",
    on_click=lambda: st.session_state.update(_sel_day=latest_day),
)
```

เขียนแบบนี้ **ไม่ได้**:

```python
if st.button("⏭ ไปวันล่าสุด"):
    st.session_state["_sel_day"] = latest_day   # ← StreamlitAPIException!
    st.rerun()
```

เพราะ Streamlit ห้ามแก้ `session_state` ของ widget **หลังจาก widget ถูกสร้างไปแล้วในรอบนั้น**
(`st.date_input` ถูกสร้างไปก่อนหน้าปุ่มไม่กี่บรรทัด)

`on_click` แก้ปัญหานี้เพราะ callback จะทำงาน **ตอนต้นของรอบถัดไป ก่อนที่ widget จะถูกสร้าง**

**ง) หาวันก่อนหน้าที่มีข้อมูลจริง**

```python
prev_days = [d for d in available_days if d < sel_day]
prev_df = day_pool[day_pool["Trans_date"].dt.date == prev_days[-1]] if prev_days else pd.DataFrame()
```

ไม่ใช้ `sel_day - timedelta(days=1)` เพราะโรงงานไม่ได้เดินทุกวัน
(เสาร์-อาทิตย์/วันหยุด ไม่มีข้อมูล) ต้องหา "วันที่มีข้อมูลก่อนหน้านี้" จริง ๆ

**จ) หาเครื่องที่ไม่มีข้อมูล**

```python
idle = sorted(set(day_pool["MC"].unique()) - set(day_df["MC"].unique()))
```

**set difference** — เอาเซ็ตเครื่องทั้งหมด ลบด้วยเซ็ตเครื่องที่มีข้อมูลวันนั้น
ได้เครื่องที่หายไป ใช้จับได้ว่า "เครื่องไหนยังไม่ได้คีย์ข้อมูล"

### 9.2 แท็บ "เวลาสูญเสีย" — Pareto (บรรทัด 693–722)

```python
loss_total = filtered[loss_cols].sum().rename(index=LOSS_CATEGORIES).reset_index()
loss_total.columns = ["สาเหตุ", "นาที"]
loss_total = loss_total[loss_total["นาที"] > 0].sort_values("นาที", ascending=False)
loss_total["สัดส่วน (%)"] = loss_total["นาที"] / loss_total["นาที"].sum() * 100
```

ไล่ทีละขั้น:
1. `filtered[loss_cols].sum()` → Series: index = ชื่อคอลัมน์, value = ผลรวม
2. `.rename(index=LOSS_CATEGORIES)` → เปลี่ยน index เป็นชื่อไทย
3. `.reset_index()` → แปลง Series เป็น DataFrame 2 คอลัมน์
4. กรองเอาเฉพาะที่ > 0 (ไม่โชว์หมวดที่ไม่มีข้อมูล เช่น `Break_time_S`)
5. เรียงมากไปน้อย = **หลักการ Pareto** (แก้ตัวใหญ่ก่อน)

```python
pct_label = pareto.mark_text(align="left", dx=6, color="#0b0b0b").encode(
    text=alt.Text("สัดส่วน (%):Q", format=".1f")
)
st.altair_chart((pareto + pct_label).properties(...))
```

`pareto.mark_text(...)` = **เอากราฟเดิมมาเปลี่ยนชนิด mark เป็นข้อความ**
ใช้ encoding ชุดเดิม (ตำแหน่ง y เท่ากัน) แค่เปลี่ยนสิ่งที่วาด — ได้ label ท้ายแท่งพอดี

### 9.3 แท็บ "ข้อมูลรายวัน" — ดาวน์โหลด CSV (บรรทัด 786–793)

```python
csv_buf = io.BytesIO()
display.to_csv(csv_buf, index=False, encoding="utf-8-sig")
st.download_button("⬇️ ดาวน์โหลดเป็น CSV", data=csv_buf.getvalue(), ...)
```

**`encoding="utf-8-sig"` สำคัญมากสำหรับภาษาไทย**
`-sig` = ใส่ BOM (Byte Order Mark) ไว้หน้าไฟล์ ซึ่ง Excel ใช้ตรวจว่าไฟล์เป็น UTF-8
ถ้าใช้ `utf-8` เฉย ๆ เปิดใน Excel แล้วภาษาไทยจะเป็นตัวยึกยือทันที

`io.BytesIO()` = ไฟล์จำลองในหน่วยความจำ ไม่ต้องเขียนลงดิสก์จริง

---

## 10. Altair 101 — อ่านโค้ดกราฟให้ออก

Altair ใช้แนวคิด **grammar of graphics**: กราฟ = ข้อมูล + ชนิดของ mark + การ encode

```python
alt.Chart(dataframe)          # 1. ข้อมูล
   .mark_bar()                # 2. วาดเป็นอะไร (bar/line/point/text/rule)
   .encode(                   # 3. คอลัมน์ไหนไปอยู่ช่องไหน
       x=alt.X("OEE:Q"),      #    แกน X
       y=alt.Y("MC:N"),       #    แกน Y
       color=alt.Color(...),  #    สี
       tooltip=[...],         #    ข้อมูลตอนเอาเมาส์ชี้
   )
   .properties(height=420)    # 4. ขนาด
```

### ตัวอักษรท้ายชื่อคอลัมน์ = ชนิดข้อมูล

| สัญลักษณ์ | ชนิด | ใช้กับ |
|---|---|---|
| `:Q` | Quantitative | ตัวเลขต่อเนื่อง (OEE, นาที) |
| `:N` | Nominal | หมวดหมู่ไม่มีลำดับ (ชื่อเครื่อง, สาเหตุ) |
| `:T` | Temporal | วันเวลา |
| `:O` | Ordinal | หมวดหมู่มีลำดับ (เล็ก/กลาง/ใหญ่) |

**ใส่ผิดแล้วกราฟจะเพี้ยนทันที** เช่น ใส่ `:N` ให้วันที่ → แกนจะเรียงตามตัวอักษรแทนตามเวลา

### เทคนิคที่ใช้ในไฟล์นี้

```python
# เรียงแท่งตามค่า
y=alt.Y("MC:N", sort=alt.EncodingSortField("OEE", order="ascending"))
y=alt.Y("สาเหตุ:N", sort="-x")     # ย่อ: เรียงตามค่าแกน x จากมากไปน้อย

# ล็อกแกนไม่ให้ยืดตามข้อมูล
x=alt.X("OEE:Q", scale=alt.Scale(domain=[0, 100]))

# เส้นอ้างอิงแนวนอน/ตั้ง
alt.Chart(pd.DataFrame({"y": [threshold]})).mark_rule(strokeDash=[6, 4]).encode(y="y:Q")

# ความสูงยืดตามจำนวนแท่ง
.properties(height=max(300, 22 * len(day_summary)))

# ซ้อนกราฟ
chart_a + chart_b
```

---

## 11. ความรู้เรื่อง OEE ที่ฝังอยู่ในโค้ด

### สูตร

```
OEE = Availability × Performance × Quality

Availability = เวลาเดินจริง / เวลาที่วางแผน      (เครื่องหยุดบ่อยไหม)
Performance  = ผลผลิตจริง / ผลผลิตที่ควรได้      (เดินช้ากว่ามาตรฐานไหม)
Quality      = ของดี / ผลผลิตทั้งหมด             (ของเสียเยอะไหม)
```

เพราะเป็นการ**คูณ** ตัวเลขจึงต่ำกว่าที่คิดเสมอ:
90% × 90% × 90% = 72.9% ไม่ใช่ 90%

### แดชบอร์ดนี้ไม่ได้คำนวณ OEE เอง

ข้อมูลต้นทางมีคอลัมน์ `Avaliable (%)`, `Performance (%)`, `Quality (%)`, `OEE (%)`
คำนวณมาแล้วจากระบบ MOS โค้ดแค่**อ่านมาแสดง**

> **ตั้งใจให้เป็นแบบนี้** — ถ้าแดชบอร์ดคำนวณเอง ตัวเลขอาจไม่ตรงกับที่ฝ่ายผลิตรายงาน
> ทำให้เถียงกันว่าเลขไหนถูก แดชบอร์ดควรเป็น "กระจกสะท้อนฐานข้อมูล" ไม่ใช่ "แหล่งความจริงที่สอง"
>
> (สังเกตว่าคำว่า `Avaliable` สะกดผิดในไฟล์ต้นทาง — โค้ดก็ต้องสะกดผิดตาม
> เพราะต้องตรงกับชื่อคอลัมน์จริง เป็นเรื่องปกติของงาน data จริง)

ไฟล์ฐานข้อมูลหลักมีชีต **"วิธีคิด OEE"** อธิบายพารามิเตอร์ที่โรงงานใช้ไว้ด้วย — ควรอ่านประกอบ

### เกณฑ์อ้างอิง

| ระดับ | OEE |
|---|---|
| World-class | ≥ 85% |
| ยอมรับได้ทั่วไป | 60–85% |
| ต้องปรับปรุง | < 60% |

โรงงานนี้อยู่ที่ ~28% — ค่า default ของ slider จึงตั้งไว้ที่ 50% (เกณฑ์ที่ท้าทายแต่ไปถึงได้)
ไม่ใช่ 85% ที่จะทำให้ทุกเครื่องเป็นสีแดงหมดจนแดชบอร์ดไม่มีประโยชน์

---

## 12. กับดักที่เคยเจอจริงในโปรเจกต์นี้

รวมบั๊กที่เกิดขึ้นจริงระหว่างพัฒนา พร้อมวิธีแก้ — ส่วนที่มีค่าที่สุดสำหรับการศึกษา

### 12.1 HTML โผล่เป็นตัวหนังสือ

**อาการ:** การ์ด KPI แสดงเป็น `<div style="background:...` แทนที่จะเป็นการ์ดสวย ๆ
**สาเหตุ:** เขียน HTML แบบเยื้องหน้าบรรทัด → Markdown ตีความเป็น code block
**แก้:** ต่อ string แบบไม่มี indent (ดูหัวข้อ 6.1)

### 12.2 อัปโหลดไฟล์แล้วเพื่อนไม่เห็น

**อาการ:** อัปโหลดไฟล์ใหม่ผ่าน sidebar แต่เครื่องอื่นยังเห็นข้อมูลเก่า
**สาเหตุ:** `st.file_uploader` ผูกกับ session ของเบราว์เซอร์คนอัปโหลดเท่านั้น
ไม่ได้ save ลง server
**แก้:** เปลี่ยนไปอ่านไฟล์จาก path บนดิสก์ (`DATA_SOURCES`) แทน
ช่องอัปโหลดเก็บไว้เป็น "ดูชั่วคราว"

### 12.3 แก้ไฟล์แล้วแดชบอร์ดไม่อัปเดต

**อาการ:** อัปเดต Excel แล้ว refresh หน้า ตัวเลขยังเป็นของเก่า
**สาเหตุ:** `@st.cache_data` เห็นว่า argument (path) เหมือนเดิม เลยคืน cache
**แก้:** ส่ง `os.path.getmtime(path)` เป็น argument เพิ่ม (ดูหัวข้อ 4.1)

### 12.4 `StreamlitAPIException` ตอนกดปุ่ม

**อาการ:** `st.session_state._sel_day cannot be modified after the widget with key _sel_day is instantiated`
**สาเหตุ:** พยายามแก้ค่า widget หลังจาก widget ถูกสร้างไปแล้วในรอบเดียวกัน
**แก้:** ใช้ `on_click=lambda: ...` แทน (ดูหัวข้อ 9.1 ค)

### 12.5 `use_container_width` deprecated

**อาการ:** log เต็มไปด้วย warning
**แก้:** เปลี่ยนเป็น `width="stretch"` (Streamlit ≥ 1.57)

---

## 13. แนวทางต่อยอด

### ง่าย — ลองทำเป็นแบบฝึกหัด

1. **เพิ่มเกณฑ์ world-class 85%** เป็นเส้นประเส้นที่สองในกราฟแนวโน้ม
   (hint: สร้าง `rule` อีกอันแล้ว `+` เข้าไป)
2. **เพิ่มตัวกรองรายเครื่อง** ใน sidebar (hint: `st.multiselect` กับ `data["MC"]`)
3. **เปลี่ยนช่วงเฝ้าระวัง** จาก 75% ของเกณฑ์เป็นค่าที่ปรับได้เอง
4. **เพิ่มปุ่มดาวน์โหลด Excel** แทน CSV (hint: `pd.ExcelWriter` + `io.BytesIO`)

### กลาง

5. **กราฟ Pareto สะสม** — เพิ่มเส้น % สะสมทับบนแท่ง (คลาสสิกของ Pareto จริง)
6. **เทียบเดือนต่อเดือนรายเครื่อง** — heatmap เครื่อง × เดือน ด้วย `mark_rect()`
7. **คำนวณ MTBF / MTTR** จากชีต `B001` / `BP001` ที่มี timestamp เริ่ม-จบของทุกเหตุการณ์

### ยาก

8. **แจ้งเตือนอัตโนมัติ** — ส่ง LINE Notify เมื่อมีเครื่อง OEE ต่ำติดต่อกัน 3 วัน
9. **ย้ายไปฐานข้อมูลจริง** (SQLite/PostgreSQL) แทน Excel เมื่อข้อมูลโตเกิน ~100,000 แถว
10. **พยากรณ์แนวโน้ม** ด้วย moving average หรือ Prophet

---

## ภาคผนวก: คำสั่งที่ใช้บ่อย

```bash
# รันแดชบอร์ด
python -m streamlit run monitor.py --server.port 8502

# ติดตั้ง dependency
pip install -r requirements.txt

# ดูโครงสร้างไฟล์ Excel ก่อนเขียนโค้ด (ทำทุกครั้งก่อนเริ่ม!)
python -c "import pandas as pd; xl = pd.ExcelFile('ไฟล์.xlsx'); print(xl.sheet_names)"
```

**ไลบรารีที่ใช้:**

| ไลบรารี | หน้าที่ | เอกสาร |
|---|---|---|
| `streamlit` | สร้าง UI เว็บจาก Python | docs.streamlit.io |
| `pandas` | จัดการตารางข้อมูล | pandas.pydata.org |
| `altair` | วาดกราฟ | altair-viz.github.io |
| `openpyxl` | อ่าน/เขียน .xlsx (pandas เรียกใช้เบื้องหลัง) | openpyxl.readthedocs.io |
