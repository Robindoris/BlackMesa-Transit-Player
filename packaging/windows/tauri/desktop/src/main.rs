#![windows_subsystem = "windows"]

use std::{
    error::Error,
    fs::File,
    io::{BufRead, BufReader, Write},
    net::{Ipv4Addr, SocketAddr, TcpStream},
    os::windows::process::CommandExt,
    process::{Command, Stdio},
    sync::{Arc, Mutex},
    thread,
    time::Duration,
};
use tauri::{Manager, Url, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use windows_sys::Win32::{
    System::LibraryLoader::{GetModuleHandleW, GetProcAddress},
    UI::WindowsAndMessaging::{MessageBoxW, IDYES, MB_ICONERROR, MB_ICONINFORMATION, MB_OK, MB_YESNO},
};

fn alert(message: &str) {
    let message: Vec<_> = message.encode_utf16().chain([0]).collect();
    let title: Vec<_> = "BRUT.me Pack Launcher Desktop".encode_utf16().chain([0]).collect();
    unsafe { MessageBoxW(std::ptr::null_mut(), message.as_ptr(), title.as_ptr(), MB_OK | MB_ICONERROR); }
}

fn session(line: &str) -> Option<Url> {
    let url = Url::parse(line).ok()?;
    let token = url.fragment()?;
    (url.scheme() == "http" && url.host_str() == Some("127.0.0.1")
        && url.port().is_some_and(|port| port > 0) && url.username().is_empty()
        && url.password().is_none() && url.path() == "/" && url.query().is_none()
        && token.len() == 43 && token.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_'))
        .then_some(url)
}

fn stop(url: &Url) -> std::io::Result<bool> {
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, url.port().unwrap()));
    let timeout = Duration::from_secs(3);
    let mut stream = TcpStream::connect_timeout(&address, timeout)?;
    stream.set_write_timeout(Some(timeout))?;
    stream.set_read_timeout(Some(timeout))?;
    write!(stream, "POST /stop HTTP/1.0\r\nHost: {address}\r\nX-Session: {}\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{{}}", url.fragment().unwrap())?;
    let mut status = String::new();
    BufReader::new(stream).read_line(&mut status)?;
    Ok(status.split_whitespace().nth(1) == Some("200"))
}

#[derive(Default)]
struct Dashboard {
    url: Option<Url>,
    closing: bool,
}

fn launch(app: tauri::AppHandle) -> Result<(), Box<dyn Error>> {
    let exe = std::env::current_exe()?;
    let game = exe.parent().ok_or("Missing launcher directory")?;
    let install = game.join("TransitPlayer");
    let lock = File::options().create(true).truncate(false).write(true).open(install.join(".desktop.lock"))?;
    lock.try_lock().map_err(|_| "Another desktop launcher is open for this installation.")?;
    let mut child = Command::new(install.join("runtime/python.exe"))
        .arg(install.join("launcher.py")).args(["player", "--game"]).arg(game)
        .args(["--port", "0", "--no-browser"]).current_dir(game)
        .env("BRUT_TRANSIT_DESKTOP", "1")
        .creation_flags(0x08000000).stdin(Stdio::null()).stdout(Stdio::piped()).spawn()?;
    let stdout = child.stdout.take().unwrap();
    let state = Arc::new(Mutex::new(Dashboard::default()));
    let windows_app = app.clone();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            let Some(url) = session(&line) else { continue };
            let closing = {
                let mut dashboard = state.lock().unwrap();
                dashboard.url = Some(url.clone());
                dashboard.closing
            };
            if closing { let _ = stop(&url); continue; }
            let result = if let Some(window) = windows_app.get_webview_window("dashboard") {
                // A fragment-only navigation would keep the old JavaScript session.
                let mut next = url.clone();
                next.set_query(Some("desktop-restart"));
                window.navigate(next)
            } else {
                let origin = url.origin();
                let window = WebviewWindowBuilder::new(&windows_app, "dashboard", WebviewUrl::External(url.clone()))
                    .title("BRUT.me Pack Launcher").inner_size(1200.0, 800.0)
                    .on_navigation(move |page| page.origin() == origin)
                    .build();
                window.map(|window| {
                    let state = state.clone();
                    window.on_window_event(move |event| {
                        if let WindowEvent::CloseRequested { api, .. } = event {
                            api.prevent_close();
                            let mut dashboard = state.lock().unwrap();
                            if dashboard.closing { return; }
                            dashboard.closing = true;
                            let state = state.clone();
                            thread::spawn(move || {
                                for _ in 0..15 {
                                    let current = state.lock().unwrap().url.clone();
                                    if current.as_ref().is_some_and(|u| stop(u).unwrap_or(false)) { return; }
                                    thread::sleep(Duration::from_millis(400));
                                }
                                state.lock().unwrap().closing = false;
                                alert("The dashboard is busy. Try closing it again after the current operation finishes.");
                            });
                        }
                    });
                })
            };
            if result.is_err() {
                let _ = stop(&url);
                alert("Could not open the desktop window. Check the Microsoft Edge WebView2 Runtime and reopen the launcher.");
                windows_app.exit(1);
                break;
            }
        }
    });
    let status = child.wait()?;
    if !status.success() { return Err(format!("The dashboard exited with {status}.").into()); }
    Ok(())
}

fn wine_browser() -> bool {
    let ntdll: Vec<_> = "ntdll.dll".encode_utf16().chain([0]).collect();
    let is_wine = unsafe {
        let library = GetModuleHandleW(ntdll.as_ptr());
        !library.is_null() && GetProcAddress(library, c"wine_get_version".as_ptr().cast()).is_some()
    };
    if !is_wine { return false; }
    let message: Vec<_> = "This desktop window requires Microsoft WebView2 on Windows. Under Wine, you can use the browser launcher. Open it now?"
        .encode_utf16().chain([0]).collect();
    let title: Vec<_> = "BRUT.me Pack Launcher Desktop".encode_utf16().chain([0]).collect();
    let choice = unsafe { MessageBoxW(std::ptr::null_mut(), message.as_ptr(), title.as_ptr(), MB_YESNO | MB_ICONINFORMATION) };
    if choice == IDYES {
        let launched = std::env::current_exe().and_then(|exe| {
            Command::new(exe.with_file_name("Brutmepacklauncher.exe")).spawn()
        });
        if let Err(error) = launched { alert(&error.to_string()); }
    }
    true
}

fn main() {
    if wine_browser() { return; }
    let result = tauri::Builder::default().setup(|app| {
        let app = app.handle().clone();
        thread::spawn(move || match launch(app.clone()) {
            Ok(()) => app.exit(0),
            Err(error) => { alert(&error.to_string()); app.exit(1); }
        });
        Ok(())
    }).run(tauri::generate_context!());
    if let Err(error) = result { alert(&error.to_string()); }
}
