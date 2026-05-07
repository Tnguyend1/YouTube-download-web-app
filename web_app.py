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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, Response, abort, render_template_string, request, send_file, url_for

APP = Flask(__name__)
DOWNLOAD_DIR = Path(__file__).resolve().parent / "web_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)
KEEP_SECONDS = 15 * 60
DOWNLOAD_INDEX: dict[str, tuple[Path, float]] = {}
MAX_URLS = 5

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
      <p class="small">Paste up to {{ max_urls }} links (leave blanks empty).</p>
      {% for n in range(1, max_urls + 1) %}
      <label for="url{{ n }}">Link {{ n }}</label>
      <input id="url{{ n }}" name="url{{ n }}" type="text" inputmode="url" placeholder="https://… or youtu.be/…" autocomplete="off" style="margin-bottom:8px;">
      {% endfor %}
      {% if require_password %}
      <label for="password">Shared password</label>
      <input id="password" name="password" type="password" required>
      {% else %}
      <p class="small">Password disabled (APP_PASSWORD is not set).</p>
      {% endif %}
      <label for="format">Format</label>
      <select id="format" name="format">
        <option value="mp4">MP4 (iPhone compatible)</option>
        <option value="mov-hevc">MOV (HEVC, slower)</option>
      </select>
      <button type="submit">Download</button>
    </form>
    {% if error %}
      <p class="err">{{ error }}</p>
    {% endif %}
    {% if downloads %}
      <p class="ok">Done. Tap each link to download:</p>
      <ul style="padding-left:18px;">
      {% for d in downloads %}
        <li style="margin:8px 0;">
          {% if d.ok %}
            <a href="{{ d.file_url }}">{{ d.file_name }}</a>
          {% else %}
            <span class="err">Failed</span> — <span class="small">{{ d.source_url }}</span>
            {% if d.log_snippet %}<pre style="margin-top:6px;font-size:12px;">{{ d.log_snippet }}</pre>{% endif %}
          {% endif %}
        </li>
      {% endfor %}
      </ul>
      <p class="small">Links stay active for a short time, then auto-clean.</p>
    {% elif file_url %}
      <p class="ok">Done. Tap to download:</p>
      <p><a href="{{ file_url }}">{{ file_name }}</a></p>
      <p class="small">Link stays active for a short time, then auto-cleans.</p>
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


def normalize_url(raw: str) -> str:
    """Strip junk from mobile paste; add https if user pasted host without scheme."""
    u = (raw or "").strip()
    for ch in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        u = u.replace(ch, "")
    u = u.strip()
    if not u:
        return ""
    if u.startswith(("http://", "https://")):
        return u
    if u.startswith("www.") or "youtube.com" in u or "youtu.be" in u:
        return "https://" + u.lstrip("/")
    return u


def collect_urls(form) -> list[str]:
    """Read url1..url5; fallback: legacy textarea or single `url` field."""
    out: list[str] = []
    for i in range(1, MAX_URLS + 1):
        u = normalize_url(form.get(f"url{i}") or "")
        if u.startswith(("http://", "https://")):
            out.append(u)
    if out:
        return out[:MAX_URLS]
    blob = (form.get("urls") or "").strip()
    if blob:
        for line in blob.splitlines():
            u = normalize_url(line)
            if u.startswith(("http://", "https://")):
                out.append(u)
        return out[:MAX_URLS]
    single = normalize_url(form.get("url") or "")
    if single.startswith(("http://", "https://")):
        return [single]
    return []


def cleanup_old_files() -> None:
    cutoff = time.time() - KEEP_SECONDS
    for path in DOWNLOAD_DIR.glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass
    # Drop stale token mappings for deleted files.
    stale_tokens = [
        token
        for token, (path, created_at) in DOWNLOAD_INDEX.items()
        if (not path.exists()) or (created_at < cutoff)
    ]
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
        # Re-encode to iPhone-friendly MP4 (H.264 + AAC) with faststart.
        cmd += [
            "--recode-video",
            "mp4",
            "--postprocessor-args",
            "VideoConvertor:-c:v libx264 -pix_fmt yuv420p -profile:v high -level 4.1 -movflags +faststart -c:a aac -b:a 192k",
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
    return render_template_string(
        PAGE, require_password=require_password, max_urls=MAX_URLS
    )


@APP.post("/")
def index_post():
    cleanup_old_files()
    shared_password = os.environ.get("APP_PASSWORD", "").strip()
    require_password = bool(shared_password)
    base = {"require_password": require_password, "max_urls": MAX_URLS}
    if require_password:
        given_password = (request.form.get("password") or "").strip()
        if given_password != shared_password:
            return (
                render_template_string(
                    PAGE, error="Wrong password.", require_password=True, max_urls=MAX_URLS
                ),
                403,
            )

    urls = collect_urls(request.form)
    if not urls:
        return (
            render_template_string(
                PAGE,
                error=(
                    f"Paste at least one valid YouTube URL (https://…), "
                    f"up to {MAX_URLS} lines (one per line)."
                ),
                **base,
            ),
            200,
        )
    video_format = (request.form.get("format") or "mp4").strip().lower()
    if video_format not in {"mp4", "mov-hevc"}:
        video_format = "mp4"

    def run_one(u: str) -> tuple[str, int, str, Path | None]:
        try:
            code, log, path = run_download(u, video_format)
            return u, code, log, path
        except FileNotFoundError:
            return u, -1, "yt-dlp not found on server. Install yt-dlp first.\n", None

    workers = min(len(urls), MAX_URLS)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(run_one, urls))

    downloads: list[dict[str, object]] = []
    log_chunks: list[str] = []
    for u, code, log, file_path in results:
        if code == 0 and file_path is not None and file_path.exists():
            token = uuid.uuid4().hex
            DOWNLOAD_INDEX[token] = (file_path, time.time())
            downloads.append(
                {
                    "ok": True,
                    "source_url": u,
                    "file_url": url_for("download_file", token=token),
                    "file_name": file_path.name,
                }
            )
        else:
            snippet = (log or "")[-2500:]
            downloads.append(
                {
                    "ok": False,
                    "source_url": u,
                    "log_snippet": snippet,
                }
            )
            log_chunks.append(f"--- {u}\n{log}")

    any_ok = any(d.get("ok") for d in downloads)
    return (
        render_template_string(
            PAGE,
            downloads=downloads,
            log=("\n".join(log_chunks))[-8000:] if not any_ok else None,
            error=None if any_ok else "All downloads failed. See logs below.",
            **base,
        ),
        200,
    )


@APP.get("/download/<token>")
def download_file(token: str):
    item = DOWNLOAD_INDEX.get(token)
    if not item:
        abort(404)
    path, created_at = item
    if (not path.exists()) or (time.time() - created_at > KEEP_SECONDS):
        DOWNLOAD_INDEX.pop(token, None)
        abort(404)
    # Force Safari to save into Downloads so users can use their usual Save flow.
    return send_file(path, as_attachment=True, download_name=path.name)


@APP.get("/favicon.ico")
def favicon():
    return Response(status=204)


@APP.get("/apple-touch-icon.png")
@APP.get("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    return Response(status=204)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    APP.run(host="0.0.0.0", port=port, debug=False)
