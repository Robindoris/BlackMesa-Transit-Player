# Black Mesa Transit Player

[English](#english) · [Slovenčina](#slovenčina)

## English

A local launcher and player dashboard for the BRUT.me Half-Life pack.

Download the repository ZIP and copy the two launcher scripts and the TransitPlayer folder beside hl.exe. On Windows, open **Half-Life Launcher.bat**. On Linux, run **bash "Half-Life Launcher.sh"** with Python 3.11 or newer and Wine installed.

To install the dashboard as an app, start the launcher and choose **Install** in Chrome or Edge. Keep the launcher running while using the app. On later starts, the launcher opens the installed app when it finds its desktop shortcut. It uses the same local address, `http://127.0.0.1:27080/`, each time. If you clear browser storage, open the full link printed by the launcher once to reconnect that browser profile.

Use **Update dashboard** to check the public main branch. After an update downloads, the launcher automatically restarts the dashboard and reloads the same app window or browser tab. Game files, catalog settings and player history are kept separately.

Under **Settings and updates → Player name**, choose **Create profile**, enter your in-game name, and save the private token. On another computer, choose **Use existing profile** and paste it. **Switch player** changes the profile for the next game. **My stats** combines recorded sessions across computers. An offline launcher queues changes until the same profile syncs again. On a shared computer, leave **Remember me on this computer** unchecked and **Sign out** when finished.

Existing local sessions stay under the local player. Use **Import local history** only if those sessions belong to you. A profile can use **Replace token** to invalidate the old token and other device sign-ins.

## Slovenčina

Black Mesa Transit Player je spúšťač hier a hráčsky panel pre balík BRUT.me Half-Life.

1. Stiahnite si ZIP archív repozitára a rozbaľte ho.
2. Skopírujte oba spúšťacie skripty a priečinok `TransitPlayer` do priečinka s hrou, v ktorom sa nachádza súbor `hl.exe`.
3. Vo Windowse spustite **Half-Life Launcher.bat**. V Linuxe potrebujete Python vo verzii 3.11 alebo novšej a Wine. V priečinku s hrou spustite príkaz `bash "Half-Life Launcher.sh"`.

Ak chcete panel nainštalovať ako aplikáciu, spustite spúšťač a v prehliadači Chrome alebo Edge vyberte možnosť **Inštalovať**. Počas používania aplikácie nechajte spúšťač bežať. Pri ďalšom spustení otvorí nainštalovanú aplikáciu, ak nájde jej odkaz v systéme. Vždy používa rovnakú lokálnu adresu `http://127.0.0.1:27080/`. Ak vymažete údaje prehliadača, otvorte v danom profile celý odkaz z terminálu spúšťača.

Ak chcete skontrolovať dostupnosť aktualizácie, kliknite v hráčskom paneli na **Update dashboard**. Spúšťač skontroluje verejnú vetvu `main` a stiahne dostupnú aktualizáciu. Po stiahnutí aktualizácie sa panel automaticky reštartuje a nová verzia sa načíta v tom istom okne aplikácie alebo na tej istej karte prehliadača. Súbory hry, nastavenia katalógu a história hrania sa ukladajú samostatne.


V časti **Nastavenia a aktualizácie → Meno hráča** vyberte **Vytvoriť profil**, zadajte meno v hre a uložte si súkromný token. Na inom počítači vyberte **Použiť existujúci profil** a vložte token. Voľba **Prepnúť hráča** zmení profil pre ďalšiu hru. **Moje štatistiky** zobrazujú spoločnú históriu zo všetkých počítačov. Na zdieľanom počítači nechajte možnosť **Zapamätať si ma na tomto počítači** vypnutú a po hraní vyberte **Odhlásiť sa**. Ak vám patria aj staršie miestne relácie, môžete ich pridať cez **Importovať miestnu históriu**.
