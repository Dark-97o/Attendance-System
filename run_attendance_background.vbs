' VBScript to launch Attendance System Python Backend silently in the background (no CMD window)
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get project directory from script location
strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Check if backend is already listening on port 8080
Set objExec = objShell.Exec("powershell.exe -NoProfile -Command ""(Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue).Count""")
strOutput = Trim(objExec.StdOut.ReadAll())

If strOutput = "0" Or strOutput = "" Then
    ' Start backend via python run.py hidden (0 = hidden window)
    objShell.CurrentDirectory = strScriptDir
    objShell.Run "python run.py", 0, False
End If
