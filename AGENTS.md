# Installing Black Mesa Transit Player

Treat `Robindoris/BlackMesa-Transit-Player` as read-only. Never push commits, branches, or tags to it, regardless of the remote name.

1. Locate the user's installed BRUT.me Half-Life pack. The destination is the directory containing `hl.exe`. If the path is missing or several installations match, ask the user which directory to use.
2. On 64-bit Windows 10 or 11, download the [Windows installer](https://github.com/Robindoris/BlackMesa-Transit-Player/releases/latest/download/Brutmepacklauncher-Setup.exe). Close the dashboard, select the game directory in setup, and install. For unattended setup, pass `/S` and then `/D=C:\path to game` as the final argument. Check the exit code before launching `Brutmepacklauncher.exe` beside `hl.exe`. The installer supplies Python and its runtime DLLs.
3. For Linux or manual installation, download and extract the [main branch ZIP](https://github.com/Robindoris/BlackMesa-Transit-Player/archive/refs/heads/main.zip), or use an existing checkout.
4. From the repository root, copy `Half-Life Launcher.bat`, `Half-Life Launcher.sh`, and the entire `TransitPlayer` directory directly beside `hl.exe`. Preserve existing game files and player data. For an existing working installation, use **Update dashboard** to update it.
5. For a manual installation, start the launcher from the game directory using the instructions below.

| Platform | Requirements and launch command |
| --- | --- |
| Windows | Run `.\Half-Life Launcher.bat` by double-clicking it in Explorer. It uses the included Python runtime. |
| Linux | Check that `python3 --version` reports 3.11 or newer and that `wine --version` succeeds. Run `bash "Half-Life Launcher.sh"`. |

Verify that the local dashboard opens at `http://127.0.0.1:27080/`. If the browser needs to reconnect, open the full link printed by the launcher. Keep the launcher running while using the dashboard.
