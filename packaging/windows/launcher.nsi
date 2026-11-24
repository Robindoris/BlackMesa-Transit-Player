Unicode true
Name "BRUT.me Pack Launcher"
OutFile "${BUILD}/Brutmepacklauncher.exe"
RequestExecutionLevel user
SilentInstall silent
AutoCloseWindow true
Icon "${PAYLOAD}/TransitPlayer/ui/art/lambda.ico"

Section
  SetOutPath "$EXEDIR"
  ClearErrors
  ExecWait '"$EXEDIR\TransitPlayer\runtime\python.exe" "$EXEDIR\TransitPlayer\launcher.py" player' $0
  IfErrors failed
  StrCmp $0 0 done
  MessageBox MB_ICONSTOP "The dashboard closed with exit code $0. Check whether another launcher is already running."
  SetErrorLevel $0
  Goto done
failed:
  MessageBox MB_ICONSTOP "Could not start the bundled Python runtime. Run the BRUT.me Pack Launcher installer again."
  SetErrorLevel 1
done:
SectionEnd
