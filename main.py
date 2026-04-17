#!/usr/bin/env python3
"""
YouTube downloader via yt-dlp + ffmpeg.

Default: run `python3 main.py`, paste the link, Enter (saves to ~/Downloads).

Also: --cli URL | --gui (tkinter, optional)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from typing import Optional

# macOS 26+ (Tahoe): help Tcl/Tk see real OS version (may still fail if Tk dylibs mismatch).
os.environ["SYSTEM_VERSION_COMPAT"] = "0"


def find_yt_dlp() -> list[str]:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "yt_dlp"]


def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def ytdlp_cmd(url: str, out_dir: str, video_format: str = "mp4") -> list[str]:
    cmd = [
        *find_yt_dlp(),
        "-f",
        "bv*+ba/bestvideo+bestaudio/best",
        "--no-playlist",
        "-o",
        os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s"),
        "--newline",
        "--progress",
    ]
    if video_format == "mov-hevc":
        cmd += [
            "--recode-video",
            "mov",
            "--postprocessor-args",
            "VideoConvertor:-c:v libx265 -tag:v hvc1 -c:a aac -b:a 192k",
        ]
    else:
        cmd += [
            "--merge-output-format",
            "mp4",
            "--remux-video",
            "mp4",
        ]
    cmd.append(url)
    return cmd


def download_url(url: str, out_dir: str, video_format: str = "mp4") -> int:
    """Run yt-dlp; stream output to stdout. Returns process exit code."""
    out_dir = os.path.expanduser(out_dir.strip())
    if not os.path.isdir(out_dir):
        print(f"Folder does not exist: {out_dir}", file=sys.stderr)
        return 1

    cmd = ytdlp_cmd(url.strip(), out_dir, video_format)
    print("$ " + subprocess.list2cmdline(cmd) + "\n", flush=True)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
        return proc.wait()
    except FileNotFoundError:
        print(
            "yt-dlp not found. Install: brew install yt-dlp\n"
            "or: python3 -m pip install --user -U yt-dlp",
            file=sys.stderr,
        )
        return 127
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_interactive() -> int:
    print("Paste YouTube link, then press Enter (saves to Downloads).")
    print("Type 1 for MP4 (default) or 2 for MOV (HEVC).")
    print("Empty Enter = quit.\n")
    try:
        url = input("URL: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return 130
    if not url:
        return 0
    fmt = input("Format [1=MP4, 2=MOV(HEVC)] (default 1): ").strip()
    video_format = "mov-hevc" if fmt == "2" else "mp4"
    out = os.path.expanduser("~/Downloads")
    code = download_url(url, out, video_format)
    if code == 0:
        print("\nSaved under:", out)
    return code


def run_cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Download a YouTube URL (MP4 or MOV/HEVC).")
    p.add_argument("url", help="Video URL")
    p.add_argument(
        "-o",
        "--output-dir",
        default=os.path.expanduser("~/Downloads"),
        help="Folder for the file (default: ~/Downloads)",
    )
    p.add_argument(
        "--format",
        dest="video_format",
        choices=("mp4", "mov-hevc"),
        default="mp4",
        help="Output format: mp4 (default) or mov-hevc",
    )
    args = p.parse_args(argv)
    return download_url(args.url, args.output_dir, args.video_format)


def run_gui() -> None:
    import queue
    import threading

    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    _DOWNLOAD_DONE = object()

    class App(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title("YouTube → MP4")
            self.minsize(560, 420)
            self.geometry("640x480")

            self._yt_dlp = find_yt_dlp()
            self._ffmpeg_ok = find_ffmpeg() is not None
            self._log_queue: queue.Queue[str | object] = queue.Queue()
            self._proc: subprocess.Popen[str] | None = None
            self._worker: threading.Thread | None = None

            self._build_ui()
            self.after(100, self._drain_log_queue)

        def _build_ui(self) -> None:
            pad = {"padx": 12, "pady": 6}

            frm = ttk.Frame(self, padding=8)
            frm.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frm, text="Video URL").pack(anchor=tk.W, **pad)
            self.url_var = tk.StringVar()
            self.entry = ttk.Entry(frm, textvariable=self.url_var, width=72)
            self.entry.pack(fill=tk.X, **pad)

            row = ttk.Frame(frm)
            row.pack(fill=tk.X, **pad)

            ttk.Label(row, text="Save to:").pack(side=tk.LEFT)
            self.dir_var = tk.StringVar(value=os.path.expanduser("~/Downloads"))
            ttk.Entry(row, textvariable=self.dir_var, width=50).pack(
                side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8)
            )
            ttk.Button(row, text="Browse…", command=self._pick_dir).pack(side=tk.LEFT)

            fmt_row = ttk.Frame(frm)
            fmt_row.pack(fill=tk.X, **pad)
            ttk.Label(fmt_row, text="Format:").pack(side=tk.LEFT)
            self.format_var = tk.StringVar(value="mp4")
            fmt_box = ttk.Combobox(
                fmt_row,
                textvariable=self.format_var,
                values=("mp4", "mov-hevc"),
                state="readonly",
                width=12,
            )
            fmt_box.pack(side=tk.LEFT, padx=(8, 0))

            self.btn = ttk.Button(frm, text="Download", command=self._start_download)
            self.btn.pack(anchor=tk.W, **pad)

            warn = []
            if not self._ffmpeg_ok:
                warn.append("ffmpeg not found in PATH — install it for reliable MP4 merge.")
            ttk.Label(
                frm,
                text=" ".join(warn) if warn else "Uses yt-dlp + ffmpeg to merge to MP4.",
            ).pack(anchor=tk.W, padx=12, pady=(0, 4))

            ttk.Label(frm, text="Log").pack(anchor=tk.W, padx=12)
            self.log = scrolledtext.ScrolledText(
                frm, height=16, state=tk.DISABLED, font=("Menlo", 11)
            )
            self.log.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        def _pick_dir(self) -> None:
            path = filedialog.askdirectory(initialdir=self.dir_var.get())
            if path:
                self.dir_var.set(path)

        def _append_log(self, text: str) -> None:
            self.log.configure(state=tk.NORMAL)
            self.log.insert(tk.END, text)
            self.log.see(tk.END)
            self.log.configure(state=tk.DISABLED)

        def _drain_log_queue(self) -> None:
            try:
                while True:
                    item = self._log_queue.get_nowait()
                    if item is _DOWNLOAD_DONE:
                        self.btn.configure(state=tk.NORMAL)
                    else:
                        self._append_log(item)
            except queue.Empty:
                pass
            self.after(100, self._drain_log_queue)

        def _start_download(self) -> None:
            url = (self.url_var.get() or "").strip()
            if not url:
                messagebox.showinfo("URL needed", "Paste a YouTube link first.")
                return

            out_dir = os.path.expanduser(self.dir_var.get().strip())
            if not os.path.isdir(out_dir):
                messagebox.showerror("Folder", f"Folder does not exist:\n{out_dir}")
                return

            if self._worker and self._worker.is_alive():
                messagebox.showinfo("Busy", "A download is already running.")
                return

            self.btn.configure(state=tk.DISABLED)
            self._append_log("\n---\n")

            def run() -> None:
                cmd = ytdlp_cmd(url, out_dir, self.format_var.get())
                self._log_queue.put("$ " + subprocess.list2cmdline(cmd) + "\n\n")
                try:
                    self._proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )
                    assert self._proc.stdout is not None
                    for line in self._proc.stdout:
                        self._log_queue.put(line)
                    code = self._proc.wait()
                    self._proc = None
                    if code == 0:
                        self._log_queue.put("\nDone.\n")
                    else:
                        self._log_queue.put(f"\nExit code: {code}\n")
                except FileNotFoundError:
                    self._log_queue.put(
                        "yt-dlp not found. Install with: brew install yt-dlp\n"
                        "or: python3 -m pip install --user -U yt-dlp\n"
                    )
                except Exception as e:
                    self._log_queue.put(f"\nError: {e}\n")
                finally:
                    self._log_queue.put(_DOWNLOAD_DONE)

            self._worker = threading.Thread(target=run, daemon=True)
            self._worker.start()

    app = App()
    app.mainloop()


def main() -> None:
    if len(sys.argv) >= 2:
        if sys.argv[1] == "--cli":
            raise SystemExit(run_cli(sys.argv[2:]))
        if sys.argv[1] == "--gui":
            run_gui()
            return
    raise SystemExit(run_interactive())


if __name__ == "__main__":
    main()
