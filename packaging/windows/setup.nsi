Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"

Name "BRUT.me Pack Launcher"
OutFile "${BUILD}/Brutmepacklauncher-Setup.exe"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "${PAYLOAD}/TransitPlayer/ui/art/lambda.ico"
!define MUI_WELCOMEPAGE_TEXT "This wizard installs the launcher and its private Python runtime for the BRUT.me Half-Life pack. You can run setup offline."
!insertmacro MUI_PAGE_WELCOME
!define MUI_DIRECTORYPAGE_TEXT_TOP "Select a writable game folder containing hl.exe, or use an empty launcher folder to download the game later. Close any running dashboard before continuing."
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

  ; Keep an explicit /D= destination, including during unattended setup.
  StrCmp $INSTDIR "" 0 done
  GetKnownFolderPath $0 {4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4} ; FOLDERID_SavedGames
  ${If} $0 == ""
    ReadEnvStr $0 USERPROFILE
    StrCpy $0 "$0\Saved Games"
  ${EndIf}
  StrCpy $INSTDIR "$0"
  IfFileExists "$INSTDIR\hl.exe" done
  StrCpy $INSTDIR "$0\BRUT.me Half-Life"
  IfFileExists "$INSTDIR\hl.exe" done

  ; Use a unique existing pack, even if the player renamed its folder.
  StrCpy $INSTDIR "$0\BRUT.me Pack Launcher"
  StrCpy $4 ""
  FindFirst $1 $2 "$0\*"
  scan:
    StrCmp $2 "" scanned
    StrCmp $2 "." next
    StrCmp $2 ".." next
    IfFileExists "$0\$2\hl.exe" 0 next
    StrCmp $4 "" 0 ambiguous
    StrCpy $4 "$0\$2"
  next:
    FindNext $1 $2
    Goto scan
  scanned:
    StrCmp $4 "" ambiguous
    StrCpy $INSTDIR "$4"
  ambiguous:
    FindClose $1
  done:
FunctionEnd

Function ValidateFolder
  IfFileExists "$INSTDIR\hl.exe" done
  IfFileExists "$INSTDIR\Brutmepacklauncher.exe" 0 checkContents
  IfFileExists "$INSTDIR\TransitPlayer\launcher.py" done
  checkContents:
  FindFirst $0 $1 "$INSTDIR\*"
  loop:
    StrCmp $1 "" finished
    StrCmp $1 "." next
    StrCmp $1 ".." next
    FindClose $0
    MessageBox MB_ICONEXCLAMATION "Select an empty folder or the game folder containing hl.exe." /SD IDOK
    SetErrorLevel 1
    Abort
  next:
    FindNext $0 $1
    Goto loop
  finished:
    FindClose $0
  done:
    ClearErrors
    CreateDirectory "$INSTDIR"
    IfErrors blocked
    GetTempFileName $0 "$INSTDIR"
    IfErrors blocked
    Delete "$0"
    Return
  blocked:
    MessageBox MB_ICONEXCLAMATION "Setup could not write to the selected folder. Choose a folder your Windows account can write to. If Windows Security showed an alert, check its Protection history for the blocked file." /SD IDOK
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
