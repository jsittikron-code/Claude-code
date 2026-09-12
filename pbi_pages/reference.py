"""คู่มืออ้างอิง — ฟังก์ชัน DAX ที่ใช้บ่อย สำนวนที่ใช้ซ้ำ และตารางแก้ปัญหา"""

import pandas as pd
import streamlit as st

FUNCTIONS: list[tuple[str, str, str, str, bool]] = [
    # (ชื่อ, หมวด, ไวยากรณ์, คำอธิบาย, ลองในสนามซ้อมได้ไหม)
    ("SUM", "รวมยอด", "SUM( <คอลัมน์> )", "รวมค่าตัวเลขในคอลัมน์ตาม filter context ปัจจุบัน", True),
    ("AVERAGE", "รวมยอด", "AVERAGE( <คอลัมน์> )", "ค่าเฉลี่ย ข้ามค่าว่างให้อัตโนมัติ", True),
    ("MIN / MAX", "รวมยอด", "MIN( <คอลัมน์> )", "ค่าน้อยสุด/มากสุด ใช้กับวันที่ได้ด้วย", True),
    ("COUNT", "รวมยอด", "COUNT( <คอลัมน์> )", "นับแถวที่ค่าไม่ว่าง", True),
    ("COUNTROWS", "รวมยอด", "COUNTROWS( <ตาราง> )", "นับจำนวนแถวของตาราง (รับตาราง ไม่ใช่คอลัมน์)", True),
    ("DISTINCTCOUNT", "รวมยอด", "DISTINCTCOUNT( <คอลัมน์> )", "นับจำนวนค่าที่ไม่ซ้ำ", True),
    ("SUMX", "ตระกูล X", "SUMX( <ตาราง>, <สูตรระดับแถว> )",
     "คำนวณทีละแถวแล้วรวมผล — ใช้เมื่อต้องคูณ/หารก่อนบวก", True),
    ("AVERAGEX", "ตระกูล X", "AVERAGEX( <ตาราง>, <สูตร> )", "ค่าเฉลี่ยของผลลัพธ์ระดับแถว", True),
    ("MAXX / MINX", "ตระกูล X", "MAXX( <ตาราง>, <สูตร> )", "ค่ามากสุด/น้อยสุดของผลลัพธ์ระดับแถว", True),
    ("CONCATENATEX", "ตระกูล X", "CONCATENATEX( <ตาราง>, <สูตร>, <ตัวคั่น> )",
     "ต่อข้อความจากทุกแถว — ใช้ทำ measure ตรวจสอบบริบทได้ดีมาก", True),
    ("CALCULATE", "บริบท", "CALCULATE( <นิพจน์>, <ตัวกรอง>... )",
     "ฟังก์ชันเดียวที่เปลี่ยน filter context ได้ · ตัวกรองจะ 'แทนที่' ของเดิมในคอลัมน์นั้น", True),
    ("FILTER", "บริบท", "FILTER( <ตาราง>, <เงื่อนไข> )",
     "คืนตารางที่กรองแล้ว ใช้เมื่อเงื่อนไขอ้างหลายคอลัมน์หรืออ้าง measure", True),
    ("ALL", "บริบท", "ALL( <ตาราง> ) หรือ ALL( <คอลัมน์> )",
     "ถอดตัวกรอง — ระบุระดับให้ตรงกับตัวส่วนที่ต้องการ", True),
    ("ALLEXCEPT", "บริบท", "ALLEXCEPT( <ตาราง>, <คอลัมน์ที่คงไว้>... )",
     "ถอดตัวกรองทั้งตารางยกเว้นคอลัมน์ที่ระบุ · ใช้ทำสัดส่วนเทียบกลุ่มแม่", True),
    ("ALLSELECTED", "บริบท", "ALLSELECTED( <ตาราง/คอลัมน์> )",
     "ถอดเฉพาะตัวกรองจาก visual แต่คงตัวกรองจาก slicer", False),
    ("REMOVEFILTERS", "บริบท", "REMOVEFILTERS( <ตาราง/คอลัมน์> )", "เหมือน ALL แต่ชื่อสื่อความหมายกว่า", True),
    ("KEEPFILTERS", "บริบท", "KEEPFILTERS( <ตัวกรอง> )",
     "ให้ตัวกรองใหม่ซ้อนทับกับของเดิม แทนที่จะแทนที่", True),
    ("VALUES", "บริบท", "VALUES( <คอลัมน์> )", "คืนค่าที่ไม่ซ้ำของคอลัมน์ในบริบทปัจจุบัน", True),
    ("SELECTEDVALUE", "บริบท", "SELECTEDVALUE( <คอลัมน์>, <ค่าสำรอง> )",
     "คืนค่าเดียวเมื่อผู้ใช้เลือกค่าเดียว · ใช้ทำหัวข้อไดนามิก", True),
    ("HASONEVALUE", "บริบท", "HASONEVALUE( <คอลัมน์> )", "ตรวจว่าบริบทเหลือค่าเดียวหรือไม่ · ใช้ซ่อนแถวรวม", True),
    ("USERELATIONSHIP", "บริบท", "USERELATIONSHIP( <คอลัมน์1>, <คอลัมน์2> )",
     "เรียกใช้ความสัมพันธ์ที่เป็น inactive เฉพาะใน measure นั้น", False),
    ("IF", "ตรรกะ", "IF( <เงื่อนไข>, <ถ้าจริง>, <ถ้าเท็จ> )", "เงื่อนไขเดียว", True),
    ("SWITCH", "ตรรกะ", "SWITCH( TRUE(), <เงื่อนไข>, <ผล>, ..., <ค่าที่เหลือ> )",
     "หลายเงื่อนไข อ่านง่ายกว่า IF ซ้อน · ลำดับเงื่อนไขสำคัญมาก", True),
    ("DIVIDE", "คณิต", "DIVIDE( <ตัวตั้ง>, <ตัวหาร>, <ค่าสำรอง> )",
     "หารที่ไม่พังเมื่อตัวหารเป็นศูนย์ — ใช้แทน / เสมอ", True),
    ("ROUND", "คณิต", "ROUND( <ตัวเลข>, <ตำแหน่ง> )", "ปัดเศษ", True),
    ("BLANK / ISBLANK", "ตรรกะ", "ISBLANK( <ค่า> )", "ค่าว่างของ DAX · คืน BLANK() เพื่อให้กราฟข้ามจุดนั้น", True),
    ("COALESCE", "ตรรกะ", "COALESCE( <ค่า1>, <ค่า2> )", "คืนค่าแรกที่ไม่ว่าง", False),
    ("RELATED", "ความสัมพันธ์", "RELATED( <คอลัมน์ฝั่ง 1> )",
     "ดึงค่าจากตารางฝั่ง 'หนึ่ง' มาใช้ใน row context", True),
    ("RELATEDTABLE", "ความสัมพันธ์", "RELATEDTABLE( <ตารางฝั่ง *> )", "ดึงตารางฝั่ง 'หลาย' ที่เกี่ยวข้อง", False),
    ("TOTALYTD", "เวลา", "TOTALYTD( <นิพจน์>, <คอลัมน์วันที่>, <สิ้นปีงบ> )", "ยอดสะสมตั้งแต่ต้นปี", True),
    ("DATESYTD", "เวลา", "DATESYTD( <คอลัมน์วันที่> )", "คืนช่วงวันที่ตั้งแต่ต้นปีถึงวันสุดท้ายในบริบท", True),
    ("SAMEPERIODLASTYEAR", "เวลา", "SAMEPERIODLASTYEAR( <คอลัมน์วันที่> )", "ช่วงเวลาเดียวกันของปีก่อน", True),
    ("DATEADD", "เวลา", "DATEADD( <คอลัมน์วันที่>, <จำนวน>, <หน่วย> )",
     "เลื่อนช่วงเวลา หน่วยเป็น DAY/MONTH/QUARTER/YEAR", True),
    ("PREVIOUSMONTH", "เวลา", "PREVIOUSMONTH( <คอลัมน์วันที่> )", "เดือนก่อนหน้าทั้งเดือน", True),
    ("DATESINPERIOD", "เวลา", "DATESINPERIOD( <วันที่>, <วันเริ่ม>, <จำนวน>, <หน่วย> )",
     "ช่วงวันที่ยาว N หน่วยจากวันเริ่ม · ใช้ทำค่าเฉลี่ยเคลื่อนที่", True),
    ("CALENDAR", "เวลา", "CALENDAR( <วันเริ่ม>, <วันจบ> )", "สร้างตารางวันที่ต่อเนื่อง", False),
    ("RANKX", "จัดอันดับ", "RANKX( <ตาราง>, <นิพจน์> )", "จัดอันดับ · ต้องอาศัย context transition", False),
    ("TOPN", "จัดอันดับ", "TOPN( <จำนวน>, <ตาราง>, <นิพจน์> )", "คัดอันดับต้น ๆ ออกมาเป็นตาราง", False),
    ("FORMAT", "ข้อความ", 'FORMAT( <ค่า>, "รูปแบบ" )',
     "แปลงเป็นข้อความตามรูปแบบ · อย่าใช้กับตัวเลขที่ต้องพล็อตกราฟ", True),
    ("VAR / RETURN", "โครงสร้าง", "VAR ชื่อ = <นิพจน์> RETURN <นิพจน์>",
     "เก็บผลไว้ใช้ซ้ำ · คำนวณครั้งเดียว ณ จุดที่ประกาศ", True),
    ("USERPRINCIPALNAME", "ความปลอดภัย", "USERPRINCIPALNAME()",
     "อีเมลของผู้ใช้ที่เปิดรายงาน · ใช้ทำ dynamic RLS", False),
]

PATTERNS: list[tuple[str, str, str]] = [
    ("สัดส่วนต่อยอดรวมทั้งหมด",
     "DIVIDE(\n    [Total Good],\n    CALCULATE( [Total Good], ALL( Machine ) )\n)",
     "ตัวส่วนไม่ขึ้นกับตัวกรองของตาราง Machine เลย"),
    ("สัดส่วนต่อกลุ่มแม่",
     "DIVIDE(\n    [Total Good],\n    CALCULATE( [Total Good], ALLEXCEPT( Machine, Machine[Line] ) )\n)",
     "ตัวส่วนเปลี่ยนตามสายของแถวนั้น"),
    ("เทียบปีก่อนพร้อมดักฐานว่าง",
     "VAR cur  = [Total Good]\n"
     "VAR prev = CALCULATE( [Total Good], SAMEPERIODLASTYEAR( DimDate[Date] ) )\n"
     "RETURN\n    IF( NOT ISBLANK( prev ) && prev <> 0, DIVIDE( cur - prev, prev ) )",
     "ไม่ดักฐานว่าง กราฟจะพุ่งเป็น 100% ในเดือนที่ยังไม่มีข้อมูลปีก่อน"),
    ("หัวข้อรายงานไดนามิก",
     '"สรุป OEE — " & SELECTEDVALUE( Machine[Line], "ทุกสายการผลิต" )',
     "เอาไปใส่ที่ Title ของ visual ผ่านปุ่ม fx"),
    ("ซ่อนค่าที่แถวรวม",
     "IF( HASONEVALUE( Machine[MachineName] ), [OEE %], BLANK() )",
     "ใช้เมื่อค่าเฉลี่ยระดับแถวรวมกันแล้วไม่มีความหมาย"),
    ("measure ตรวจสอบบริบท (ใช้ดีบัก)",
     '"เห็น: " & CONCATENATEX( VALUES( Machine[Line] ), Machine[Line], ", " )\n'
     '    & " | แถว: " & COUNTROWS( Production )',
     "วางลงในตารางแล้วจะเห็นทันทีว่าแต่ละช่องมองเห็นข้อมูลอะไร"),
    ("เทียบงวดก่อนหน้าด้วยคอลัมน์ลำดับ (ปฏิทินไม่มาตรฐาน)",
     "VAR i = SELECTEDVALUE( DimDate[MonthIndex] )\n"
     "RETURN\n    CALCULATE( [Total Good], ALL( DimDate ), DimDate[MonthIndex] = i - 1 )",
     "ใช้กับปฏิทิน 4-4-5 หรือรอบตัดยอดที่ไม่ตรงเดือน · เร็วกว่า time intelligence ด้วย"),
    ("ค่าเฉลี่ยเคลื่อนที่ 30 วัน",
     "AVERAGEX(\n    DATESINPERIOD( DimDate[Date], MAX( DimDate[Date] ), -30, DAY ),\n"
     "    [Total Good]\n)",
     "ลดสัญญาณรบกวนของข้อมูลรายวัน"),
]

TROUBLE: list[tuple[str, str, str]] = [
    ("ทุกแถวแสดงยอดรวมเท่ากันหมด",
     "ไม่มีความสัมพันธ์ หรือทิศทางตัวกรองผิด",
     "เปิด Model view ตรวจว่ามีเส้นเชื่อม และเป็น 1:* จาก dimension ไป fact"),
    ("มีแถว (Blank) โผล่ในรายงาน",
     "ตาราง fact มีคีย์ที่ไม่มีในตารางมิติ",
     "ใช้ Merge แบบ Left Anti ใน Power Query หาแถวที่จับคู่ไม่ได้"),
    ("ยอดหายไปบางส่วนหลังสร้างความสัมพันธ์",
     "คีย์ไม่ตรงกันเพราะช่องว่างหรือชนิดข้อมูลต่างกัน",
     "ใช้ Trim กับคอลัมน์คีย์ทั้งสองฝั่ง แล้วตรวจให้ชนิดข้อมูลเหมือนกัน"),
    ("จำนวนแถวบวมขึ้นหลัง Merge",
     "คีย์ฝั่งขวาซ้ำ ทำให้แถวซ้ายถูกทำซ้ำ",
     "ตรวจว่าคีย์ของตารางมิติไม่ซ้ำด้วย Remove Duplicates หรือ Group By"),
    ("% ไม่เปลี่ยนตาม slicer",
     "สร้างเป็น calculated column แทนที่จะเป็น measure",
     "ย้ายไปเป็น measure แล้วใช้ CALCULATE + ALL กำหนดตัวส่วน"),
    ("YTD ให้ตัวเลขผิดแบบไม่มี error",
     "ลืม Mark as date table หรือตารางวันที่ไม่ครบปี",
     "ทำ Mark as date table และขยายตารางวันที่ให้ครบ 1 ม.ค. – 31 ธ.ค."),
    ("เดือนเรียงผิดลำดับ",
     "คอลัมน์ชื่อเดือนเป็นข้อความจึงเรียงตามตัวอักษร",
     "ตั้ง Sort by column ให้เรียงตามคอลัมน์เลขเดือน"),
    ("รายงานช้ามาก",
     "โมเดลไม่ใช่ star schema, คอลัมน์ค่าไม่ซ้ำเยอะ, หรือ Auto date/time เปิดอยู่",
     "วัดด้วย Performance analyzer ก่อน แล้วแก้ตามลำดับผลกระทบ"),
    ("refresh บน Service ล้มเหลว",
     "path เปลี่ยน · ไฟล์ถูกเปิดค้าง · ไม่มี Gateway · รหัสผ่านหมดอายุ",
     "ใช้ parameter เก็บ path และตั้งอีเมลแจ้งเตือนเมื่อ refresh ล้มเหลว"),
    ("RLS ทดสอบแล้วยังเห็นข้อมูลหมด",
     "บัญชีที่ทดสอบมีสิทธิ์แก้ไข workspace ซึ่ง RLS ไม่มีผล",
     "ทดสอบด้วย View as ใน Desktop และ Test as role บน Service"),
]

st.title("คู่มืออ้างอิง")

tab_fn, tab_pat, tab_fix = st.tabs(["ฟังก์ชัน DAX", "สำนวนที่ใช้บ่อย", "แก้ปัญหาที่เจอบ่อย"])

with tab_fn:
    query = st.text_input("ค้นหา", placeholder="พิมพ์ชื่อฟังก์ชันหรือคำในคำอธิบาย",
                          label_visibility="collapsed")
    cats = sorted({f[1] for f in FUNCTIONS})
    picked = st.pills("หมวด", cats, selection_mode="multi")

    rows = FUNCTIONS
    if query:
        q = query.lower()
        rows = [f for f in rows if q in f[0].lower() or q in f[3].lower() or q in f[2].lower()]
    if picked:
        rows = [f for f in rows if f[1] in picked]

    st.caption(f"{len(rows)} ฟังก์ชัน · คอลัมน์ 'ลองในแอปได้' บอกว่าเครื่องจำลอง DAX "
               "ของแอปนี้รองรับหรือไม่ (ที่ไม่รองรับยังใช้ได้ปกติใน Power BI จริง)")
    st.dataframe(
        pd.DataFrame([{"ฟังก์ชัน": f[0], "หมวด": f[1], "ไวยากรณ์": f[2],
                       "คำอธิบาย": f[3], "ลองในแอปได้": "✓" if f[4] else "—"}
                      for f in rows]),
        hide_index=True, height=min(620, 40 + 35 * len(rows)),
    )

with tab_pat:
    st.caption("สำนวนเหล่านี้ครอบคลุมงานจริงส่วนใหญ่ — คัดลอกไปปรับชื่อตารางให้ตรงกับโมเดลของคุณ")
    for title, code, note in PATTERNS:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.code(code, language="dax")
            st.caption(note)

with tab_fix:
    st.caption("ไล่จากอาการที่เห็น ไปหาสาเหตุที่พบบ่อยที่สุด")
    st.dataframe(
        pd.DataFrame(TROUBLE, columns=["อาการ", "สาเหตุที่พบบ่อย", "วิธีตรวจและแก้"]),
        hide_index=True, height=40 + 35 * len(TROUBLE),
    )
