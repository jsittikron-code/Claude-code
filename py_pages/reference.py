"""คู่มืออ้างอิง — ค้นหาไวยากรณ์และสำนวนที่ใช้บ่อย พร้อมตัวอย่างที่กดไปรันต่อได้"""

import streamlit as st

ENTRIES: list[dict] = [
    # ---------------- ชนิดข้อมูลและตัวแปร ----------------
    {"sec": "ชนิดข้อมูล", "name": "แปลงชนิด",
     "code": 'int("45")   → 45\nfloat("3.5") → 3.5\nstr(45)      → "45"\nint(7.9)     → 7   (ตัดเศษ)\nround(7.9)   → 8',
     "note": "int() ตัดเศษทิ้งเสมอ ถ้าต้องการปัดใช้ round()"},
    {"sec": "ชนิดข้อมูล", "name": "ตรวจชนิด",
     "code": 'type(x)\nisinstance(x, int)\nisinstance(x, (int, float))',
     "note": "ใช้ isinstance เวลาต้องรองรับหลายชนิด"},
    {"sec": "ชนิดข้อมูล", "name": "ค่าที่ถือเป็นเท็จ",
     "code": '0, 0.0, "", [], {}, set(), None',
     "note": "นอกจากนี้ถือเป็นจริงหมด รวมถึงข้อความ \"0\" และลิสต์ [0]"},

    # ---------------- ข้อความ ----------------
    {"sec": "ข้อความ", "name": "เมท็อดที่ใช้บ่อย",
     "code": '"  M01 ".strip()        → "M01"\n"m01".upper()          → "M01"\n"M-01".replace("-","") → "M01"\n"a,b".split(",")       → ["a","b"]\n", ".join(["a","b"])   → "a, b"\n"M01".startswith("M")  → True\n"1".zfill(3)           → "001"\n"45".isdigit()         → True',
     "note": "สตริงแก้ในตัวเองไม่ได้ ต้องรับค่ากลับมาเก็บ"},
    {"sec": "ข้อความ", "name": "f-string จัดรูปแบบ",
     "code": 'f"{0.9062:.1%}"   → 90.6%\nf"{1234567:,}"    → 1,234,567\nf"{3.14159:.2f}"  → 3.14\nf"{5:03d}"        → 005\nf"{name:<10}"     → ชิดซ้ายกว้าง 10\nf"{name:>10}"     → ชิดขวา\nf"{value!r}"      → แสดงแบบ repr (ดีบัก)',
     "note": "!r ทำให้เห็นช่องว่างที่ซ่อนอยู่ ใช้ตอนไล่บั๊ก"},
    {"sec": "ข้อความ", "name": "ตัดจำนวนครั้ง",
     "code": 'line.split(" ", 3)   # ตัดแค่ 3 ครั้ง ที่เหลือติดกันเป็นก้อนเดียว',
     "note": "ใช้แยกล็อกที่ส่วนท้ายมีเว้นวรรค"},

    # ---------------- ลิสต์ ----------------
    {"sec": "list", "name": "การเข้าถึงและตัดช่วง",
     "code": 'x[0]      ตัวแรก\nx[-1]     ตัวสุดท้าย\nx[1:3]    ตำแหน่ง 1,2 (ไม่รวม 3)\nx[:3]     สามตัวแรก\nx[-2:]    สองตัวท้าย\nx[::-1]   กลับลำดับ',
     "note": "ปลายทางไม่รวมเสมอ"},
    {"sec": "list", "name": "เมท็อดสำคัญ",
     "code": 'x.append(v)      เพิ่มท้าย 1 ตัว\nx.extend([a,b])  เพิ่มหลายตัว\nx.pop()          ดึงตัวท้ายออก\nx.remove(v)      ลบตามค่า\nx.sort()         เรียงในตัวเอง (คืน None)\nsorted(x)        คืนลิสต์ใหม่ที่เรียงแล้ว\nx.copy()         สำเนาจริง',
     "note": "b = a ไม่ใช่สำเนา แต่เป็นชื่อที่ชี้ก้อนเดียวกัน"},
    {"sec": "list", "name": "ฟังก์ชันรวบยอด",
     "code": 'sum(x)   max(x)   min(x)   len(x)\nsorted(x, key=lambda r: r[1], reverse=True)\nany(v > 100 for v in x)\nall(v < 200 for v in x)\nsum(1 for v in x if v > 0)   # นับแบบมีเงื่อนไข',
     "note": "key= คือหัวใจของการเรียงข้อมูลจริง"},
    {"sec": "list", "name": "comprehension",
     "code": '[v * 2 for v in values]\n[v for v in values if v > 60]\n{k: v for k, v in pairs}\n{code[:3] for code in codes}',
     "note": "ใช้เมื่อเป็นการแปลง/กรองตรง ๆ ถ้าซับซ้อนให้กลับไปเขียนลูป"},

    # ---------------- dict / set ----------------
    {"sec": "dict / set", "name": "การใช้งานพื้นฐาน",
     "code": 'd["key"]              ไม่มีคีย์ → KeyError\nd.get("key", 0)       ไม่มีคีย์ → คืนค่าเริ่มต้น\nd.keys() d.values() d.items()\nd.setdefault(k, {})\n"key" in d',
     "note": ".get() คือเกราะกันโปรแกรมล้มเมื่อข้อมูลไม่ครบ"},
    {"sec": "dict / set", "name": "สรุปยอดแยกกลุ่ม",
     "code": 'totals = {}\nfor code, minutes in records:\n    totals[code] = totals.get(code, 0) + minutes',
     "note": "สำนวนที่ใช้บ่อยที่สุดในงานสรุปข้อมูล — วนข้อมูลรอบเดียว"},
    {"sec": "dict / set", "name": "เรียง dict ตามค่า",
     "code": 'for k, v in sorted(d.items(), key=lambda kv: kv[1], reverse=True):\n    print(k, v)',
     "note": "ใช้ทำตารางจัดอันดับ"},
    {"sec": "dict / set", "name": "เปรียบเทียบกลุ่มด้วย set",
     "code": 'planned - done   ยังไม่ได้ทำ\nplanned & done   ทำตามแผน\nplanned | done   รวมทั้งหมด\ndone - planned   ทำนอกแผน',
     "note": "หัวใจของรายงาน PM Compliance"},

    # ---------------- เงื่อนไขและลูป ----------------
    {"sec": "เงื่อนไขและลูป", "name": "if / elif / else",
     "code": 'if oee >= 0.85:\n    ...\nelif oee >= 0.60:\n    ...\nelse:\n    ...',
     "note": "เรียงจากเข้มงวดที่สุดไปหลวมที่สุดเสมอ"},
    {"sec": "เงื่อนไขและลูป", "name": "for และตัวช่วย",
     "code": 'for v in values: ...\nfor i in range(1, 6): ...          # 1..5\nfor i, v in enumerate(values, 1): ...\nfor a, b in zip(list1, list2): ...',
     "note": "range ไม่รวมค่าปลาย · zip หยุดที่ลิสต์สั้นสุด"},
    {"sec": "เงื่อนไขและลูป", "name": "while / break / continue",
     "code": 'while stock > 100:\n    stock -= 45\n\nfor v in values:\n    if v == 0:\n        continue   # ข้ามรอบนี้\n    if v > 300:\n        break      # ออกจากลูป',
     "note": "while ต้องมีบรรทัดที่ทำให้เงื่อนไขเข้าใกล้เท็จ"},

    # ---------------- ฟังก์ชัน ----------------
    {"sec": "ฟังก์ชัน", "name": "โครงมาตรฐาน",
     "code": 'def availability(planned: int, downtime: int) -> float:\n    """อัตราการเดินเครื่อง 0-1"""\n    if planned <= 0:\n        return 0.0\n    return (planned - downtime) / planned',
     "note": "ตรวจกรณีผิดปกติแล้ว return ออกก่อน (early return)"},
    {"sec": "ฟังก์ชัน", "name": "ค่าเริ่มต้นและคืนหลายค่า",
     "code": 'def f(a, b=1.2): ...\nf(10, b=1.5)\n\ndef summary(x):\n    return min(x), max(x), sum(x)/len(x)\nlo, hi, avg = summary(values)',
     "note": "อย่าใช้ list/dict เป็นค่าเริ่มต้น ให้ใช้ None แล้วสร้างใหม่ข้างใน"},

    # ---------------- ไฟล์ ----------------
    {"sec": "ไฟล์", "name": "อ่าน/เขียนไฟล์ข้อความ",
     "code": 'with open("f.txt", encoding="utf-8") as fh:\n    for line in fh:\n        print(line.strip())\n\nwith open("out.txt", "w", encoding="utf-8") as fh:\n    fh.write("ข้อความ\\n")',
     "note": 'ภาษาไทยบน Windows ต้องใส่ encoding="utf-8" เสมอ · โหมด "w" ล้างไฟล์เดิม'},
    {"sec": "ไฟล์", "name": "CSV",
     "code": 'import csv\nwith open("d.csv", encoding="utf-8", newline="") as fh:\n    for row in csv.DictReader(fh):\n        total += int(row["downtime_min"])\n\nwith open("o.csv", "w", encoding="utf-8-sig", newline="") as fh:\n    w = csv.DictWriter(fh, fieldnames=["a", "b"])\n    w.writeheader(); w.writerows(rows)',
     "note": "ค่าที่อ่านมาเป็นข้อความทั้งหมด · utf-8-sig ทำให้ Excel อ่านภาษาไทยได้"},
    {"sec": "ไฟล์", "name": "JSON",
     "code": 'import json\njson.dump(obj, fh, ensure_ascii=False, indent=2)\nobj = json.load(fh)\ns = json.dumps(obj, ensure_ascii=False)',
     "note": "ensure_ascii=False ทำให้ภาษาไทยในไฟล์อ่านออก"},
    {"sec": "ไฟล์", "name": "พาธด้วย pathlib",
     "code": 'from pathlib import Path\nbase = Path(r"C:\\งาน\\ข้อมูล")\nfor f in base.glob("*.csv"):\n    print(f.name, f.stat().st_size)\nout = base / "รายงาน.xlsx"',
     "note": 'ใส่ r นำหน้าสตริงพาธบน Windows เพื่อไม่ให้ \\n ถูกตีความ'},

    # ---------------- วันเวลา ----------------
    {"sec": "วันเวลา", "name": "แปลงและคำนวณ",
     "code": 'from datetime import date, datetime, timedelta\nd = datetime.strptime("2026-06-01", "%Y-%m-%d").date()\ns = d.strftime("%d/%m/%Y")\nnext_pm = d + timedelta(days=90)\ndays_left = (next_pm - date.today()).days\nminutes = (t2 - t1).total_seconds() / 60',
     "note": "p = parse (อ่านเข้า), f = format (พิมพ์ออก)"},

    # ---------------- ข้อผิดพลาด ----------------
    {"sec": "ข้อผิดพลาด", "name": "try / except",
     "code": 'try:\n    total += int(v)\nexcept ValueError:\n    skipped.append(v)\nelse:\n    ...      # ไม่มีข้อผิดพลาด\nfinally:\n    ...      # ทำเสมอ',
     "note": "ระบุชนิดให้เจาะจง · ห้าม except: pass"},
    {"sec": "ข้อผิดพลาด", "name": "ยกข้อผิดพลาดเอง",
     "code": 'if not 0 <= value <= 1:\n    raise ValueError(f"ค่าต้องอยู่ระหว่าง 0-1 แต่ได้ {value}")\n\nassert total >= 0, "ยอดติดลบ"',
     "note": "พังให้ไว พังให้ชัด ดีกว่าปล่อยค่าผิดไหลเข้าระบบ"},
    {"sec": "ข้อผิดพลาด", "name": "ความหมายของแต่ละชนิด",
     "code": 'SyntaxError       เขียนผิดไวยากรณ์ (มักลืม : หรือวงเล็บ)\nIndentationError  ย่อหน้าไม่ตรง\nNameError         ไม่รู้จักชื่อนี้\nTypeError         ชนิดเข้ากันไม่ได้\nValueError        ชนิดถูก ค่าใช้ไม่ได้\nIndexError        ตำแหน่งเกินขอบ\nKeyError          ไม่มีคีย์นี้\nAttributeError    ชนิดนี้ไม่มีเมท็อดนั้น (มักเพราะเป็น None)',
     "note": "อ่าน traceback จากล่างขึ้นบนเสมอ"},

    # ---------------- pandas ----------------
    {"sec": "pandas", "name": "อ่านและสำรวจ",
     "code": 'import pandas as pd\ndf = pd.read_csv("production.csv")\ndf = pd.read_excel("f.xlsx", sheet_name="ข้อมูล")\ndf.shape  df.head()  df.dtypes  df.info()  df.describe()\ndf.isna().sum()',
     "note": "ตรวจ dtypes ทุกครั้ง — คอลัมน์ตัวเลขที่เป็น object คือสัญญาณอันตราย"},
    {"sec": "pandas", "name": "กรองและสร้างคอลัมน์",
     "code": 'df[df["downtime_min"] > 60]\ndf[(df["line"] == "Line A") & (df["downtime_min"] > 60)]\ndf[df["machine_id"].isin(["M01", "M03"])]\ndf[df["cause"].str.contains("มอเตอร์", na=False)]\ndf["run_min"] = df["planned_min"] - df["downtime_min"]\ndf.loc[df["downtime_min"] > 120, "flag"] = "วิกฤต"',
     "note": "ใช้ & | ~ และครอบวงเล็บทุกเงื่อนไข · ใช้ .loc เวลาจะเขียนค่า"},
    {"sec": "pandas", "name": "สรุปด้วย groupby",
     "code": 'df.groupby("machine_id")["downtime_min"].sum()\ndf.groupby(["line", "shift"])["downtime_min"].mean().round(1)\ndf.groupby("machine_id").agg(\n    รวม=("downtime_min", "sum"),\n    ครั้ง=("downtime_min", "count"),\n).reset_index()\ndf.pivot_table(index="machine_id", columns="shift",\n               values="downtime_min", aggfunc="sum", fill_value=0)',
     "note": "idxmax() คืนชื่อกลุ่มที่มากที่สุด ส่วน max() คืนตัวเลข"},
    {"sec": "pandas", "name": "รวมตารางและส่งออก",
     "code": 'df = prod.merge(machines, on="machine_id", how="left")\ndf["date"] = pd.to_datetime(df["date"])\ndf["เดือน"] = df["date"].dt.to_period("M").astype(str)\ndf.to_excel("รายงาน.xlsx", index=False)\ndf.to_csv("out.csv", index=False, encoding="utf-8-sig")',
     "note": "ตรวจจำนวนแถวก่อน/หลัง merge เสมอ ถ้าเพิ่ม = คีย์ซ้ำ"},

    # ---------------- Streamlit ----------------
    {"sec": "Streamlit", "name": "โครงหน้าเว็บ",
     "code": 'import streamlit as st\nst.title("รายงาน")\nline = st.selectbox("สาย", options)\nst.metric("Downtime", f"{total:,} นาที")\nst.dataframe(df, width="stretch")\nst.bar_chart(series)\n\n@st.cache_data\ndef load(path):\n    return pd.read_csv(path)',
     "note": "ทุกครั้งที่กดวิดเจ็ต สคริปต์ทั้งไฟล์จะรันใหม่ตั้งแต่ต้น"},
    {"sec": "Streamlit", "name": "รันและเปิดให้คนอื่นเข้า",
     "code": 'python -m streamlit run app.py\npython -m streamlit run app.py --server.port 8510 --server.address 0.0.0.0',
     "note": "เปิดพอร์ตในไฟร์วอลล์ก่อน แล้วให้เพื่อนเข้าที่ http://<ไอพี>:8510"},

    # ---------------- คำสั่งที่หน้าต่างคำสั่ง ----------------
    {"sec": "คำสั่งระบบ", "name": "pip และ venv",
     "code": 'python --version\npython -m pip install pandas openpyxl streamlit\npython -m pip list\npython -m pip freeze > requirements.txt\npython -m venv .venv\n.venv\\Scripts\\activate',
     "note": "ใช้ python -m pip เสมอ เพื่อให้ติดตั้งลง Python ตัวที่รันอยู่จริง"},
]

SECTIONS = list(dict.fromkeys(e["sec"] for e in ENTRIES))

st.title("คู่มืออ้างอิง")
st.caption("เปิดค้างไว้ระหว่างเขียนโค้ดได้ — พิมพ์คำค้นเพื่อกรอง เช่น groupby, encoding, split")

query = st.text_input("ค้นหา", placeholder="พิมพ์คำที่ต้องการหา เช่น dict, merge, encoding",
                      key="ref_q").strip().lower()

picked = st.segmented_control("หมวด", ["ทั้งหมด"] + SECTIONS, key="ref_sec",
                              default="ทั้งหมด") or "ทั้งหมด"

items = ENTRIES
if picked != "ทั้งหมด":
    items = [e for e in items if e["sec"] == picked]
if query:
    items = [e for e in items
             if query in e["name"].lower() or query in e["code"].lower()
             or query in e["note"].lower() or query in e["sec"].lower()]

st.caption(f"พบ {len(items)} หัวข้อ")

current = None
for e in items:
    if e["sec"] != current:
        current = e["sec"]
        st.subheader(current)
    with st.container(border=True):
        st.markdown(f"**{e['name']}**")
        st.code(e["code"], language="python")
        st.caption(e["note"])

if not items:
    st.info("ไม่พบหัวข้อที่ตรงกับคำค้น ลองคำสั้นลง", icon=":material/search_off:")
