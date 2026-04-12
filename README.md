# YouTube → MP4 (simple downloader)

Small Python helper around **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** and **ffmpeg**: paste a YouTube link and save an **MP4** to your **Downloads** folder (default).

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
| **Custom folder** | `python3 main.py --cli "https://..." -o /path/to/folder` |
| **GUI** (optional, needs Tk) | `python3 main.py --gui` |

### macOS shortcuts

- **`YouTube Download.command`** — double-click in Finder to open Terminal and run the interactive flow (executable shell script).
- **`run-gui.sh`** — same as `python3 main.py` by default; pass `--gui` if you want the window: `./run-gui.sh --gui`

## Output files

Default template: **`Title [videoId].mp4`** in **Downloads**. The path is chosen in code (`~/Downloads` for the interactive mode; `--cli` defaults to the same unless you pass `-o`).

## Notes

- **Another computer:** Works if that machine has Python 3, yt-dlp, and ffmpeg. Copy the project folder and run `python3 main.py` there. This repo does not bundle yt-dlp or ffmpeg.
- **macOS 26 (Tahoe) + Tk:** If `python3 main.py --gui` crashes with a macOS version / Tcl-Tk message, use the **interactive** or **`--cli`** modes (no Tk), or install a Tk build that matches your OS (e.g. Homebrew `python-tk` / `tcl-tk` for your Python).
- **Legal use:** Respect YouTube’s Terms of Service and copyright. Only download content you are allowed to save.

## License

No license is set in this repo by default. Add a `LICENSE` file if you want to specify one.
