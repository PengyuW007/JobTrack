Option Explicit

Dim shell, fileSystem, projectFolder, pythonWindow, application, command
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

projectFolder = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonWindow = projectFolder & "\venv\Scripts\pythonw.exe"
application = projectFolder & "\JobTrack.pyw"
command = Chr(34) & pythonWindow & Chr(34) & " " & Chr(34) & application & Chr(34)

shell.Run command, 0, False
