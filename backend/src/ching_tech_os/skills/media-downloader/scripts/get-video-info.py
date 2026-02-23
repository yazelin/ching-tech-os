#!/usr/bin/env python3
"""查詢影片資訊（不下載），回傳 metadata。"""

import json
import sys


def _format_duration(seconds: int | float | None) -> str:
    """將秒數格式化為 HH:MM:SS 或 MM:SS。"""
    if not seconds:
        return "未知"
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_filesize(bytes_val: int | float | None) -> str:
    """將位元組格式化為可讀大小。"""
    if not bytes_val:
        return "未知"
    bytes_val = float(bytes_val)
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"無效的輸入：{exc}"}, ensure_ascii=False))
        return 1

    url = payload.get("url", "").strip()
    if not url:
        print(json.dumps({"success": False, "error": "缺少 url 參數"}, ensure_ascii=False))
        return 1

    try:
        import yt_dlp

        # 不下載，僅取得資訊
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "no_color": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            print(json.dumps({"success": False, "error": "無法取得影片資訊"}, ensure_ascii=False))
            return 1

        # 整理可用格式（僅列出有影片+音訊的格式）
        formats_summary = []
        seen = set()
        for f in info.get("formats", []):
            ext = f.get("ext", "?")
            height = f.get("height")
            # 僅列出主要格式
            if height and ext in ("mp4", "webm"):
                key = f"{ext}-{height}p"
                if key not in seen:
                    seen.add(key)
                    formats_summary.append({
                        "format": key,
                        "ext": ext,
                        "resolution": f"{height}p",
                        "filesize": _format_filesize(f.get("filesize") or f.get("filesize_approx")),
                    })

        # 預估最佳品質大小
        best_size = None
        for f in reversed(info.get("formats", [])):
            size = f.get("filesize") or f.get("filesize_approx")
            if size:
                best_size = size
                break

        result = {
            "success": True,
            "title": info.get("title", "未知"),
            "duration": info.get("duration"),
            "duration_formatted": _format_duration(info.get("duration")),
            "uploader": info.get("uploader") or info.get("channel") or "未知",
            "thumbnail": info.get("thumbnail"),
            "webpage_url": info.get("webpage_url", url),
            "extractor": info.get("extractor", "未知"),
            "estimated_size": _format_filesize(best_size),
            "formats": formats_summary[:10],  # 最多列出 10 個格式
        }

        print(json.dumps(result, ensure_ascii=False))
        return 0

    except Exception as exc:
        error_msg = str(exc)
        # 常見錯誤轉為友善訊息
        if "Unsupported URL" in error_msg or "No video formats found" in error_msg:
            error_msg = f"不支援的 URL 或找不到影片：{url}"
        elif "is not a valid URL" in error_msg:
            error_msg = f"無效的 URL 格式：{url}"
        elif "HTTP Error 403" in error_msg:
            error_msg = "影片存取被拒絕（可能需要登入或有地區限制）"
        elif "HTTP Error 404" in error_msg:
            error_msg = "影片不存在或已被移除"

        print(json.dumps({"success": False, "error": error_msg}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
