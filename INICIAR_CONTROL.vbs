Option Explicit
Dim shell, fs, base, pythonw, script, extra
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
base = fs.GetParentFolderName(WScript.ScriptFullName)
pythonw = fs.BuildPath(base, ".venv\Scripts\pythonw.exe")
script = fs.BuildPath(base, "control.py")
extra = ""
If WScript.Arguments.Count > 0 Then
  If WScript.Arguments.Count <> 1 Then WScript.Quit 2
  If WScript.Arguments(0) <> "--smoke" Then WScript.Quit 2
  extra = " --smoke"
End If
If Not fs.FileExists(pythonw) Then
  MsgBox "Primero ejecuta PREPARAR_DESARROLLO.bat. El instalador final se entregara en la fase 7.", 48, "Bio-Gesture Control Pro"
  WScript.Quit 1
End If
shell.CurrentDirectory = base
shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & script & Chr(34) & extra, 0, False
