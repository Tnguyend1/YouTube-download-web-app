#!/usr/bin/env python3
"""
Private web UI for YouTube downloads (MP4 or MOV/HEVC).

Usage:
  # Optional for private LAN use. If unset, password is disabled.
  export APP_PASSWORD="choose-a-shared-password"
  python3 web_app.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from flask import Flask, abort, render_template_string, request, send_file, url_for

APP = Flask(__name__)
DOWNLOAD_DIR = Path(__file__).resolve().parent / "web_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)
KEEP_SECONDS = 15 * 60
DOWNLOAD_INDEX: dict[str, Path] = {}

PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YouTube Downloader</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f6f7fb; color: #1e1f24; }
    .wrap { max-width: 700px; margin: 24px auto; background: white; border-radius: 12px; padding: 18px; box-shadow: 0 6px 24px rgba(0,0,0,0.08); }
    h1 { margin: 0 0 14px; font-size: 22px; }
    p { margin: 8px 0; }
    label { display: block; margin: 10px 0 4px; font-weight: 600; }
    input, select { width: 100%; box-sizing: border-box; border: 1px solid #d4d7e2; border-radius: 8px; padding: 10px; font-size: 16px; background: #fff; }
    button { margin-top: 14px; background: #1f6feb; color: white; border: 0; border-radius: 8px; padding: 10px 14px; font-size: 16px; cursor: pointer; }
    pre { background: #111827; color: #e5e7eb; padding: 12px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }
    .err { color: #b00020; font-weight: 600; }
    .ok { color: #0f7b0f; font-weight: 600; }
    .small { font-size: 13px; color: #555; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>YouTube Downloader (Private)</h1>
    <p class="small">For personal use. Downloading may be restricted by platform terms/copyright.</p>
    <form method="post" action="/">
      <label for="url">YouTube URL</label>
      <input id="url" name="url" placeholder="https://www.youtube.com/watch?v=..." required>
      {% if require_password %}
      <label for="password">Shared password</label>
      <input id="password" name="password" type="password" required>
      {% else %}
      <p class="small">Password disabled (APP_PASSWORD is not set).</p>
      {% endif %}
      <label for="format">Format</label>
      <select id="format" name="format">
        <option value="mp4">MP4 (faster)</option>
        <option value="mov-hevc">MOV (HEVC, slower)</option>
      </select>
      <button type="submit">Download</button>
    </form>
    {% if error %}
      <p class="err">{{ error }}</p>
    {% endif %}
    {% if file_url %}
      <p class="ok">Done. Tap to download:</p>
      <p><a href="{{ file_url }}">{{ file_name }}</a></p>
      <p class="small">Link works while this server is running.</p>
    {% endif %}
    {% if log %}
      <p><strong>yt-dlp output</strong></p>
      <pre>{{ log }}</pre>
    {% endif %}
  </div>
</body>
</html>
"""


def find_yt_dlp() -> list[str]:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "yt_dlp"]


def cleanup_old_files() -> None:
    cutoff = time.time() - KEEP_SECONDS
    for path in DOWNLOAD_DIR.glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass
    # Drop stale token mappings for deleted files.
    stale_tokens = [token for token, path in DOWNLOAD_INDEX.items() if not path.exists()]
    for token in stale_tokens:
        DOWNLOAD_INDEX.pop(token, None)


def run_download(url: str, video_format: str) -> tuple[int, str, Path | None]:
    job_id = uuid.uuid4().hex[:10]
    output_template = str(DOWNLOAD_DIR / f"{job_id}-%(title)s [%(id)s].%(ext)s")
    cmd = [
        *find_yt_dlp(),
        "-f",
        "bv*+ba/bestvideo+bestaudio/best",
        "--no-playlist",
        "-o",
        output_template,
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
    proc = subprocess.run(cmd, capture_output=True, text=True)
    merged_log = (proc.stdout or "") + (proc.stderr or "")
    matches = list(DOWNLOAD_DIR.glob(f"{job_id}-*"))
    result_file = matches[0] if matches else None
    return proc.returncode, merged_log, result_file


@APP.get("/")
def index_get():
    cleanup_old_files()
    require_password = bool(os.environ.get("APP_PASSWORD", "").strip())
    return render_template_string(PAGE, require_password=require_password)


@APP.post("/")
def index_post():
    cleanup_old_files()
    shared_password = os.environ.get("APP_PASSWORD", "").strip()
    require_password = bool(shared_password)
    if require_password:
        given_password = (request.form.get("password") or "").strip()
        if given_password != shared_password:
            return (
                render_template_string(PAGE, error="Wrong password.", require_password=True),
                403,
            )

    url = (request.form.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return (
            render_template_string(
                PAGE, error="Please paste a valid URL.", require_password=require_password
            ),
            400,
        )
    video_format = (request.form.get("format") or "mp4").strip().lower()
    if video_format not in {"mp4", "mov-hevc"}:
        return (
            render_template_string(
                PAGE,
                error="Format must be mp4 or mov-hevc.",
                require_password=require_password,
            ),
            400,
        )
    try:
        code, log, file_path = run_download(url, video_format)
    except FileNotFoundError:
        return render_template_string(
            PAGE,
            error="yt-dlp not found on server. Install yt-dlp first.",
            require_password=require_password,
        ), 500

    if code != 0 or file_path is None or not file_path.exists():
        return render_template_string(
            PAGE,
            error="Download failed. See log below.",
            log=log[-6000:],
            require_password=require_password,
        ), 400

    token = uuid.uuid4().hex
    DOWNLOAD_INDEX[token] = file_path
    return render_template_string(
        PAGE,
        file_url=url_for("download_file", token=token),
        file_name=file_path.name,
        log=log[-2000:],
        require_password=require_password,
    )


@APP.get("/download/<token>")
def download_file(token: str):
    # One-time link: consume token and delete the file after sending.
    path = DOWNLOAD_INDEX.pop(token, None)
    if not path or not path.exists():
        abort(404)
    response = send_file(path, as_attachment=True, download_name=path.name)

    def _delete_after_send() -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    response.call_on_close(_delete_after_send)
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    APP.run(host="0.0.0.0", port=port, debug=False)
