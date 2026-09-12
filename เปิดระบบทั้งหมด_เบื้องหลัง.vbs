' เปิดแดชบอร์ดทุกระบบแบบเบื้องหลัง (ไม่มีหน้าต่างดำ) — ใช้ดับเบิลคลิกเอง
' หรือถูกเรียกอัตโนมัติตอนล็อกอินเครื่อง (มีสำเนาอยู่ในโฟลเดอร์ Startup)
' พอร์ตไหนเปิดอยู่แล้ว ตัวซ้ำจะปิดตัวเองทันที ไม่ชนกัน
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\p\Desktop\Claude-code"

apps = Array( _
    "workcenter_monitor.py|8503", _
    "energy_monitor.py|8504", _
    "maintenance_dashboard.py|8505", _
    "oee_manager.py|8506", _
    "overview_dashboard.py|8507", _
    "powerbi_academy.py|8508", _
    "python_academy.py|8509", _
    "production_dashboard.py|8510", _
    "maintenance_eng_dashboard.py|8511")

For Each a In apps
    parts = Split(a, "|")
    sh.Run "cmd /c python -m streamlit run """ & parts(0) & _
           """ --server.headless true --server.port " & parts(1), 0, False
Next
