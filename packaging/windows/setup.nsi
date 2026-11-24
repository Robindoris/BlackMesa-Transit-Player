Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"

Name "BRUT.me Pack Launcher"
OutFile "${BUILD}/Brutmepacklauncher-Setup.exe"
RequestExecutionLevel user
SetCompressor /SOLID lzma
InstallDir "$EXEDIR"
Icon "${PAYLOAD}/TransitPlayer/ui/art/lambda.ico"
!define MUI_WELCOMEPAGE_TEXT "This wizard installs the launcher and its private Python runtime into your existing BRUT.me Half-Life pack. You can run setup offline."
!insertmacro MUI_PAGE_WELCOME
!define MUI_DIRECTORYPAGE_TEXT_TOP "Select the BRUT.me Half-Life game folder containing hl.exe. Close any running dashboard before continuing."
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE ValidateFolder
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_TEXT "Open Brutmepacklauncher.exe in your game folder to start the dashboard."
!define MUI_FINISHPAGE_RUN "$INSTDIR\Brutmepacklauncher.exe"
!define MUI_FINISHPAGE_RUN_NOTCHECKED
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
  ${OrIfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "This release requires 64-bit Windows 10 or later." /SD IDOK
    SetErrorLevel 1
    Abort
  ${EndIf}
FunctionEnd

Function ValidateFolder
  IfFileExists "$INSTDIR\hl.exe" +4
    MessageBox MB_ICONEXCLAMATION "Select the game folder that contains hl.exe." /SD IDOK
    SetErrorLevel 1
    Abort
FunctionEnd

Section "Launcher"
  Call ValidateFolder
  SetErrorLevel 0
  SetOutPath "$INSTDIR\TransitPlayer"
  File "${PAYLOAD}/TransitPlayer/launcher.py"
  File "${PAYLOAD}/TransitPlayer/dashboard.py"
  File /r "${PAYLOAD}/TransitPlayer/player" "${PAYLOAD}/TransitPlayer/shared" "${PAYLOAD}/TransitPlayer/ui" "${PAYLOAD}/TransitPlayer/runtime"
  SetOverwrite off
  File "${PAYLOAD}/TransitPlayer/catalog-url.txt"
  SetOverwrite on
  nsExec::ExecToLog '"$OUTDIR\runtime\python.exe" "$OUTDIR\launcher.py" player --help'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "The bundled runtime could not load the dashboard. Close the launcher and retry setup in a writable game folder." /SD IDOK
    SetErrorLevel 1
    Abort
  ${EndIf}
  SetOutPath "$INSTDIR"
  File "${BUILD}/Brutmepacklauncher.exe"
SectionEnd
