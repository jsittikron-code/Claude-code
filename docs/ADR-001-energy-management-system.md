# ADR-001: ระบบบริหารพลังงานโรงงาน (Factory Energy Management System)

**Status:** Proposed
**Date:** 2026-07-29
**Deciders:** ฝ่ายซ่อมบำรุงรักษา / IE_PD

## Context

โรงงานมีข้อมูลพลังงานกระจายอยู่ 3 แหล่งบน OneDrive
(`4.เรื่องการใช้ปริมาณไฟฟ้าภายในโรงงาน\งานระบบไฟฟ้าโรงงาน`):

| แหล่งข้อมูล | รูปแบบ | ความถี่ | เนื้อหา |
|---|---|---|---|
| `Bill_33-2/2569/สรุปค่าไฟฟ้า 2569.xlsx` | ชีต `Bill_of_Electric` (หัวตาราง 2 แถว) | รายเดือน | TOU 3.2.2 — kWh On/Off-peak, Demand, kVAR, Ft, PF, ค่าปรับ, Vat, Total Cost |
| `Bill_33-5/2569/สรุปค่าไฟฟ้า 2569.xlsx` | ชีตเดียวกัน (คอลัมน์มากกว่า) | รายเดือน | โครงเดียวกับ 33-2 |
| `ระบบไฟฟ้าภายใน/ETL/สรุปมิเตอร์ภายใน_มค-มิย_2569.xlsx` | ชีต `สรุปรายเดือน` + `สรุปรายการยกเลิก-ผ่านจด` | รายเดือน | kWh มิเตอร์ย่อยรายสถานี (PL, ตึกอำนวยการ, MOCK UP LINE, อาคาร 4 ฯลฯ) |
| PDF บิล PEA รายเดือน | PDF | รายเดือน | หลักฐานอ้างอิง / ตรวจกลับ |

ปัญหาปัจจุบัน:
- ดูภาพรวมไม่ได้ในที่เดียว — ต้องเปิด 3 ไฟล์ + dashboard.html แบบ static ที่ต้องแก้มือ
- ไม่มีการเชื่อมค่าไฟกับผลผลิต (kWh/หน่วยผลิต) ทั้งที่มีข้อมูล OEE รายเครื่องอยู่แล้วใน `OEE_ฐานข้อมูลหลัก_2569.xlsx`
- ไม่มีระบบเตือน: PF ต่ำจนโดนค่าปรับ, Demand On-peak พุ่ง, Ft เปลี่ยน, มิเตอร์ย่อยผิดปกติ (ค่ากระโดด/ค้าง)
- kWh มิเตอร์ย่อยรวมกัน ควร reconcile กับ kWh บิลหลัก เพื่อจับ loss / มิเตอร์เสีย

ข้อจำกัด (constraints):
- ทีมถนัดสแต็กเดิม: **Python + Streamlit + pandas + Excel บน OneDrive** (ใช้กับ OEE monitor อยู่แล้ว ใช้งานได้จริง)
- ยังไม่มีมิเตอร์อัตโนมัติ (AMR/IoT) — ข้อมูลเข้าระบบด้วยการจดมือรายเดือน
- ไม่มีงบ server/database แยก — ทุกอย่างรันบนเครื่อง Windows ในโรงงาน แชร์ผ่าน OneDrive

## Decision

สร้าง **`energy_monitor.py`** — Streamlit app ตัวที่ 3 ใน repo เดียวกับ
[monitor.py](../monitor.py) / [workcenter_monitor.py](../workcenter_monitor.py)
อ่าน Excel ทั้ง 3 ไฟล์จาก OneDrive โดยตรง (แพตเทิร์น `DATA_SOURCES` + fallback ไฟล์ local เหมือน monitor.py)
ไม่ตั้ง database — Excel บน OneDrive คือฐานข้อมูลหลัก (single source of truth) ตามที่ทีมทำอยู่แล้ว

## Options Considered

### Option A: Streamlit app อ่าน Excel บน OneDrive (แพตเทิร์นเดิม) — แนะนำ

| Dimension | Assessment |
|-----------|------------|
| Complexity | ต่ำ — โค้ดแนวเดียวกับ monitor.py, ทีม maintain เองได้ |
| Cost | ~0 บาท — ใช้เครื่อง/ไลเซนส์ที่มีอยู่ |
| Scalability | พอสำหรับข้อมูลรายเดือน × ไม่กี่สิบมิเตอร์ ไปได้อีกหลายปี |
| Team familiarity | สูงสุด — สแต็กเดียวกับระบบ OEE ที่ใช้อยู่ |

**Pros:** เร็ว (ทำได้ใน 1–2 วัน), ทุกคนอัปเดต Excel แบบเดิมได้ต่อ, รวม KPI ไฟฟ้า+OEE ในโค้ดเดียว
**Cons:** ยังพึ่งการจดมือ, ประวัติแก้ไขอยู่ที่ OneDrive version history เท่านั้น, ต้องเขียน parser รองรับหัวตาราง 2 แถว/ชื่อคอลัมน์ไม่นิ่ง

### Option B: Static HTML dashboard (generate ซ้ำแบบ Dashboard_พลังงานโรงงาน_Modernform.html)

| Dimension | Assessment |
|-----------|------------|
| Complexity | ต่ำ แต่ข้อมูลตายตัว ต้อง regenerate ทุกเดือน |
| Cost | 0 |
| Scalability | แย่ — interaction/filter ทำยาก, ไม่มี upload/refresh |
| Team familiarity | ปานกลาง |

**Pros:** เปิดได้ทุกเครื่องไม่ต้องรัน server
**Cons:** ซ้ำรอยปัญหาเดิม (dashboard ค้าง ไม่ตรงข้อมูลล่าสุด), ไม่มี drill-down, งาน manual เพิ่ม

### Option C: Database (SQLite/Postgres) + AMR/IoT มิเตอร์อัตโนมัติ

| Dimension | Assessment |
|-----------|------------|
| Complexity | สูง — ต้องเดินสาย/ติด power meter + gateway, ดูแลระบบเพิ่ม |
| Cost | สูง — ฮาร์ดแวร์มิเตอร์ CT + software หลักแสนบาท |
| Scalability | ดีที่สุด — ได้ข้อมูลราย 15 นาที ทำ load profile ได้จริง |
| Team familiarity | ต่ำ |

**Pros:** ตัดงานจดมือ, จับ demand spike ได้ real-time, รากฐาน ISO 50001 เต็มรูป
**Cons:** ลงทุนสูงก่อนรู้ว่า KPI ไหนคุ้ม — ควรพิสูจน์ด้วยข้อมูลรายเดือนก่อน (Option A) แล้วใช้ผลไปของบ

## Trade-off Analysis

- **A vs B:** ต้นทุนเท่ากัน แต่ A ได้ refresh อัตโนมัติจากไฟล์ + filter/drill-down ฟรีจาก Streamlit — B ไม่มีข้อได้เปรียบนอกจาก "ไม่ต้องรัน server" ซึ่งแก้ได้ด้วย `run_energy.bat` แบบเดียวกับ [run_monitor.bat](../run_monitor.bat)
- **A vs C:** C ให้ข้อมูลละเอียดกว่ามาก แต่ตอนนี้ยังตอบคำถามพื้นฐานไม่ได้เลย (เดือนไหนแพงเพราะอะไร, ตึกไหนกิน, kWh/ผลผลิตเป็นเท่าไร) — ควรใช้ A สร้าง baseline 6–12 เดือนก่อน แล้วชี้จุดที่คุ้มติดมิเตอร์อัตโนมัติ
- ความเสี่ยงหลักของ A คือ **โครงไฟล์ Excel ไม่นิ่ง** (หัวตาราง 2 แถว, ชื่อคอลัมน์ไทย/อังกฤษปน, 33-5 มีคอลัมน์มากกว่า 33-2) → ต้องเขียน parser แบบ tolerant + validate แล้วฟ้องชัด ๆ ว่าขาดคอลัมน์อะไร (แบบ `REQUIRED_COLUMNS` ใน monitor.py)

## System Design (Option A)

### Data flow

```
PDF บิล PEA ──(จดมือ)──▶ สรุปค่าไฟฟ้า 2569.xlsx (33-2, 33-5) ─┐
จดมิเตอร์ย่อย ─────────▶ สรุปมิเตอร์ภายใน_XX_2569.xlsx ───────┼─▶ energy_monitor.py (Streamlit)
OEE_ฐานข้อมูลหลัก_2569.xlsx (มีอยู่แล้ว) ─────────────────────┘      │ cache_data + ปุ่มรีเฟรช
                                                                    ▼
                                                       5 แท็บ: ภาพรวม / บิล&ต้นทุน /
                                                       มิเตอร์ย่อย / พลังงานต่อผลผลิต / แจ้งเตือน
```

### โมดูลหลัก

1. **Loader/Parser** — ฟังก์ชันละไฟล์: `load_bill(path, meter_id)` (ข้ามแถวหัว, map ชื่อคอลัมน์ → schema กลาง), `load_submeters(path)` (unpivot เดือน ม.ค.–ธ.ค. → long format), `load_oee(path)` (reuse logic จาก monitor.py)
2. **Schema กลาง** (DataFrame):
   - `bills`: meter, month, kwh_total, kwh_on, kwh_off, demand_on, demand_off, kvar, pf, ft_rate, pf_penalty, total_cost
   - `submeters`: station, meter_no, month, kwh (+สถานะ ยกเลิก/ผ่านจด)
   - `production`: month, output รวมจาก OEE (เชื่อม kWh/หน่วยผลิต)
3. **KPI Engine**: ค่าไฟรวม/เดือน, บาท/kWh เฉลี่ย, สัดส่วน On:Off-peak, Load Factor, kWh จำเพาะ (kWh ต่อหน่วยผลิต), % reconcile (Σ มิเตอร์ย่อย ÷ kWh บิล)
4. **Alert Engine** (เกณฑ์ปรับได้ใน sidebar):
   - PF < 0.85 หรือมีค่าปรับ PF > 0 → เตือนปรับ capacitor bank
   - Demand On-peak เดือนนี้ > ค่าเฉลี่ย 3 เดือน + X% → เตือนย้ายโหลดไป Off-peak
   - มิเตอร์ย่อยค่ากระโดด >±Y% MoM หรือค่าเท่าเดิมเป๊ะ (มิเตอร์ค้าง/ลืมจด)
   - Σ มิเตอร์ย่อยต่างจากบิลเกิน Z% → สงสัย loss หรือจดผิด
5. **Export**: ดาวน์โหลด CSV/รายงานสรุปเดือน สำหรับส่งผู้บริหาร

### สิ่งที่ต้องทำเพิ่มฝั่งข้อมูล (ไม่ใช่โค้ด)

- ตกลง **ชื่อคอลัมน์มาตรฐาน** ในไฟล์บิลทั้งสองหม้อแปลงให้ตรงกัน (ตอนนี้ 33-5 มี 40 คอลัมน์ / 33-2 มี 25)
- ไฟล์มิเตอร์ภายในตอนนี้ชื่อผูกช่วงเดือน (`มค-มิย`) → เปลี่ยนเป็นไฟล์เดียวทั้งปี เช่น `สรุปมิเตอร์ภายใน_2569.xlsx` เติมคอลัมน์เดือนไปเรื่อย ๆ

## Consequences

- **ง่ายขึ้น:** เห็นต้นทุนไฟ + สาเหตุ (Ft/PF/Demand/On-peak) + ตึกที่กินไฟ ในหน้าเดียว; ได้ baseline สำหรับตั้งเป้าลดพลังงานและของบ Option C
- **ยากขึ้น:** มี Streamlit app ที่ 3 ต้องดูแล; วินัยการจดมิเตอร์/กรอก Excel รายเดือนกลายเป็นจุดตายของระบบ (ข้อมูลช้า = dashboard ช้า)
- **ต้อง revisit:** เมื่อ baseline ครบ ~12 เดือน ให้ประเมินติด power meter อัตโนมัติเฉพาะจุดที่กินไฟสูงสุด (จากข้อมูลมิเตอร์ย่อย) แล้วค่อยยกระดับเป็น Option C เฉพาะจุด

## Action Items

1. [ ] ปรับชื่อคอลัมน์ไฟล์บิล 33-2 / 33-5 ให้เป็นมาตรฐานเดียวกัน + รวมไฟล์มิเตอร์ภายในเป็นไฟล์เดียวทั้งปี
2. [ ] เขียน `energy_monitor.py` (loader + 5 แท็บ + alert) และ `run_energy.bat`
3. [ ] เชื่อมข้อมูลผลผลิตจาก `OEE_ฐานข้อมูลหลัก_2569.xlsx` เพื่อคำนวณ kWh จำเพาะ
4. [ ] ทดลองใช้ 1 รอบเดือน (จดมิเตอร์ → กรอก Excel → เปิด dashboard) แล้วเก็บ feedback ปรับเกณฑ์ alert
5. [ ] หลังมีข้อมูล ≥ 6–12 เดือน: ทำสรุปเสนอผู้บริหารเรื่องจุดคุ้มค่าติดมิเตอร์อัตโนมัติ (Option C บางส่วน)
