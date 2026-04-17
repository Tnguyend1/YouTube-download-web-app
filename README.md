# YouTube → MP4 (simple downloader)

Small Python helper around **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** and **ffmpeg**: paste a YouTube link and save as **MP4** (default) or **MOV (HEVC)**.

Now includes a **private web mode** so you can use it from your phone browser.

## Requirements

- **Python 3**
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** (`yt-dlp` on your `PATH`, or install with `pip`: `python3 -m pip install -U yt-dlp`)
- **[ffmpeg](https://ffmpeg.org/)** (needed for merging best video + audio into MP4 for most videos)

**macOS (Homebrew):**

```bash
brew install yt-dlp ffmpeg
```

On **Windows** or **Linux**, install Python 3, yt-dlp, and ffmpeg using your usual package manager or the official installers.

## Quick start

Clone or download this repo, then:

```bash
cd youtube-mp4-downloader
python3 main.py
```

When you see `URL:`, **paste the YouTube link** and press **Enter**. Files are saved under **`~/Downloads`** (your user Downloads folder on that machine).

## Other ways to run

| Mode | Command |
|------|---------|
| **Interactive** (default) | `python3 main.py` |
| **One-shot** (scripting) | `python3 main.py --cli "https://..."` |
| **MOV (HEVC)** | `python3 main.py --cli "https://..." --format mov-hevc` |
| **Custom folder** | `python3 main.py --cli "https://..." -o /path/to/folder` |
| **GUI** (optional, needs Tk) | `python3 main.py --gui` |

## Private web mode (phone-friendly)

This mode runs a small password-protected website:

- You and your friend open it in a browser
- Paste a YouTube URL
- Tap download

### 1) Install dependencies

```bash
cd youtube-mp4-downloader
python3 -m pip install -r requirements.txt
```

Also make sure system tools are installed:

```bash
brew install yt-dlp ffmpeg
```

### 2) Start the web server

Set a shared password and run (recommended):

```bash
cd youtube-mp4-downloader
export APP_PASSWORD="choose-a-strong-password"
python3 web_app.py
```

No-password mode for private LAN only:

```bash
cd youtube-mp4-downloader
unset APP_PASSWORD
python3 web_app.py
```

Server starts at:

- `http://localhost:8000` (same machine)
- `http://YOUR_COMPUTER_IP:8000` (from phone on same Wi-Fi)

### 3) Open from phone

On the same network, open:

```text
http://YOUR_COMPUTER_IP:8000
```

Paste the URL, choose format (**MP4** or **MOV (HEVC)**), and if enabled, enter shared password.

### 4) Optional: public hosting

If you deploy to a VPS/cloud, switch to HTTPS and keep `APP_PASSWORD` secret.
For better security, put it behind auth (Cloudflare Access, reverse proxy auth, etc.).

### macOS shortcuts

- **`YouTube Download.command`** — double-click in Finder to open Terminal and run the interactive flow (executable shell script).
- **`run-gui.sh`** — same as `python3 main.py` by default; pass `--gui` if you want the window: `./run-gui.sh --gui`

## Output files

Default output is **MP4**. You can switch to **MOV (HEVC)** in CLI (`--format mov-hevc`), GUI, and web mode.
The path is chosen in code (`~/Downloads` for the interactive mode; `--cli` defaults to the same unless you pass `-o`).

## Notes

- **Another computer:** Works if that machine has Python 3, yt-dlp, and ffmpeg. Copy the project folder and run `python3 main.py` there. This repo does not bundle yt-dlp or ffmpeg.
- **Web mode storage:** web downloads are saved temporarily in `web_downloads/` and old files are cleaned automatically.
- **Web mode auth:** password is optional. If `APP_PASSWORD` is unset, the web form is open (recommended only for private/local network).
- **macOS 26 (Tahoe) + Tk:** If `python3 main.py --gui` crashes with a macOS version / Tcl-Tk message, use the **interactive** or **`--cli`** modes (no Tk), or install a Tk build that matches your OS (e.g. Homebrew `python-tk` / `tcl-tk` for your Python).
- **Legal use:** Respect YouTube’s Terms of Service and copyright. Only download content you are allowed to save.

## License

No license is set in this repo by default. Add a `LICENSE` file if you want to specify one.
