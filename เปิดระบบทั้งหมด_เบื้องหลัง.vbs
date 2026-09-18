' เปิดแดชบอร์ดทุกระบบแบบเบื้องหลัง (ไม่มีหน้าต่างดำ) — ใช้ดับเบิลคลิกเอง
' หรือถูกเรียกอัตโนมัติตอนล็อกอินเครื่อง (มีสำเนาอยู่ในโฟลเดอร์ Startup)
'
' พอร์ตไหนเปิดอยู่แล้ว จะข้ามไป ไม่สั่งเปิดซ้ำ
'
' ทำไมต้องเช็กพอร์ตก่อน
'   ของเดิมเขียนคอมเมนต์ไว้ว่า "ตัวซ้ำจะปิดตัวเองทันที" แต่ในโค้ดไม่มีการเช็กเลย
'   มันสั่งเปิดทั้ง 9 ตัวรวดทุกครั้ง ถ้าพอร์ตนั้นมีคนใช้อยู่ streamlit ตัวใหม่
'   จะยึดพอร์ตค้างไว้เป็นตัวที่สอง แต่ไม่เคยได้รับ request สักอัน
'   (เกิดจริง 17 ก.ย. 2569 พอร์ต 8507 มีสองตัว ตัวที่เปิดทีหลังรับงาน 0 จาก 8 ครั้ง
'    ทำให้กดรีสตาร์ตแล้วเหมือนไม่มีอะไรเกิดขึ้น)
'
'   พอเช็กพอร์ตแล้ว ไฟล์นี้กดซ้ำได้ปลอดภัย ตัวไหนล่มก็เปิดให้ ตัวไหนอยู่ก็ปล่อยไว้
'   ใช้เป็นตัวกู้คืนได้เลยเวลาแดชบอร์ดหายไปบางตัว

Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
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

' อ่านรายการพอร์ตที่เปิดอยู่ทีเดียว เร็วกว่าเรียก netstat ทีละพอร์ต
listening = ""
tmp = fso.GetSpecialFolder(2) & "\dash_ports.txt"
On Error Resume Next
sh.Run "cmd /c netstat -ano -p TCP | findstr LISTENING > """ & tmp & """", 0, True
If fso.FileExists(tmp) Then
    Set f = fso.OpenTextFile(tmp, 1)
    If Not f.AtEndOfStream Then listening = f.ReadAll()
    f.Close
    fso.DeleteFile tmp
End If
On Error Goto 0

started = 0
skipped = 0
For Each a In apps
    parts = Split(a, "|")
    ' netstat พิมพ์ที่อยู่แบบ 0.0.0.0:8503 แล้วตามด้วยช่องว่าง
    ' จึงค้น ":8503 " ไม่ใช่ "8503" เฉย ๆ กันไปตรงกับเลขอื่นที่มี 8503 อยู่ข้างใน
    If InStr(listening, ":" & parts(1) & " ") > 0 Then
        skipped = skipped + 1
    Else
        sh.Run "cmd /c python -m streamlit run """ & parts(0) & _
               """ --server.headless true --server.port " & parts(1), 0, False
        started = started + 1
    End If
Next

' บอกผลทุกครั้งที่คนดับเบิลคลิกเอง รวมถึงตอนที่ครบอยู่แล้วและไม่ได้เปิดอะไรเพิ่ม
' ไม่งั้นกดแล้วเงียบสนิท คนกดจะนึกว่ากดไม่ติดแล้วกดซ้ำอีก
'
' ตอนบูตเครื่องไม่ต้องขึ้นกล่องข้อความ เพราะไม่มีใครนั่งอยู่หน้าจอ
' แยกสองกรณีด้วยเวลาที่ผ่านไปตั้งแต่บูต ถ้าเกิน 3 นาทีแปลว่าคนกดเอง
Set wmi = GetObject("winmgmts:\\.\root\cimv2")
For Each os In wmi.ExecQuery("Select LastBootUpTime from Win32_OperatingSystem")
    bootStr = Left(os.LastBootUpTime, 14)
Next
bootTime = CDate(Mid(bootStr,7,2) & "/" & Mid(bootStr,5,2) & "/" & Left(bootStr,4) & " " & _
                 Mid(bootStr,9,2) & ":" & Mid(bootStr,11,2) & ":" & Mid(bootStr,13,2))

If DateDiff("n", bootTime, Now) > 3 Then
    If started = 0 Then
        msg = "ทุกระบบเปิดอยู่ครบแล้ว (" & skipped & " ระบบ)" & vbCrLf & vbCrLf & _
              "ไม่ต้องทำอะไรเพิ่ม ถ้าหน้าเว็บยังไม่ขึ้น ให้กดรีเฟรชหน้าเว็บ"
    Else
        msg = "เปิดเพิ่ม " & started & " ระบบ" & vbCrLf & _
              "เปิดอยู่แล้ว " & skipped & " ระบบ" & vbCrLf & vbCrLf & _
              "รอสักครู่แล้วรีเฟรชหน้าเว็บ"
    End If
    MsgBox msg, 64, "เปิดระบบแดชบอร์ด"
End If
