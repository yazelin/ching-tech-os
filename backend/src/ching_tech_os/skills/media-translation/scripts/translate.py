"""非同步翻譯：立即回傳 job ID，背景程序執行翻譯。"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid as uuid_module
from datetime import datetime
from pathlib import Path


# --- 路徑工具 ---

def _get_ctos_mount_path() -> str:
    return os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")


def _get_translations_base_dir() -> Path:
    return Path(_get_ctos_mount_path()) / "linebot" / "translations"


def _get_allowed_mount_prefixes() -> list[str]:
    """允許的檔案路徑前綴（安全驗證用）"""
    ctos = _get_ctos_mount_path()
    return [ctos, "/mnt/nas"]


def _resolve_source_path(source_path: str) -> Path | None:
    """將 ctos:// 或 shared:// 路徑解析為實際檔案路徑"""
    ctos = _get_ctos_mount_path()
    if source_path.startswith("ctos://"):
        resolved = Path(ctos) / source_path[len("ctos://"):]
    elif source_path.startswith("shared://"):
        resolved = Path(ctos).parent / "shared" / source_path[len("shared://"):]
    elif source_path.startswith("/"):
        resolved = Path(source_path)
    else:
        return None

    # 路徑安全檢查
    try:
        resolved_str = str(resolved.resolve())
        prefixes = _get_allowed_mount_prefixes()
        if not any(resolved_str.startswith(p) for p in prefixes):
            return None
    except Exception:
        return None

    return resolved if resolved.exists() else None


# --- 狀態與推送 ---

def _write_status(status_path: Path, data: dict) -> None:
    """原子寫入狀態檔"""
    data["updated_at"] = datetime.now().isoformat()
    tmp_path = status_path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp_path.replace(status_path)


def _trigger_proactive_push(job_id: str, skill: str) -> None:
    """通知內部端點觸發主動推送（靜默失敗）"""
    try:
        import urllib.request
        data = json.dumps({"job_id": job_id, "skill": skill}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8088/api/internal/proactive-push",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


# --- Chunk 切分 ---

CHUNK_SIZE = 5_000  # 每 chunk 約 5,000 字元（避免 Gemini API hang）


def _split_chunks(text: str) -> list[str]:
    """將文字依字元數切分，優先在空行處切分"""
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= CHUNK_SIZE:
            chunks.append(remaining)
            break

        # 在 CHUNK_SIZE 範圍內找最後一個空行
        boundary = remaining.rfind("\n\n", 0, CHUNK_SIZE)
        if boundary == -1:
            # 找不到空行，找最近的換行
            boundary = remaining.rfind("\n", 0, CHUNK_SIZE)
        if boundary == -1:
            # 完全找不到，硬切
            boundary = CHUNK_SIZE

        chunks.append(remaining[: boundary + 1])
        remaining = remaining[boundary + 1 :].lstrip("\n")

    return chunks


# --- Gemini 翻譯 ---

def _detect_target_language(text_sample: str, client, model: str) -> str:
    """用第一個 chunk 偵測來源語言，決定翻譯方向"""
    from google.genai import types

    prompt = (
        "偵測以下文字的主要語言，只回答一個語言代碼：\n"
        "- 若主要是英文或中英夾雜，回答 zh-TW\n"
        "- 若主要是繁體中文，回答 en\n"
        "- 若主要是日文，回答 zh-TW\n"
        "只回答語言代碼，不要其他文字。\n\n"
        f"{text_sample[:2000]}"
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0),
    )
    result = response.text.strip()
    # 清理回傳值
    for lang in ("zh-TW", "en", "ja", "ko", "zh-CN"):
        if lang in result:
            return lang
    return "zh-TW"  # 預設翻繁中


def _translate_chunk(
    chunk: str, target_language: str, client, model: str
) -> str:
    """翻譯單一 chunk"""
    from google.genai import types

    lang_names = {
        "zh-TW": "繁體中文", "en": "English", "ja": "日本語",
        "ko": "한국어", "zh-CN": "简体中文",
    }
    lang_name = lang_names.get(target_language, target_language)

    prompt = (
        f"你是專業翻譯。將以下內容翻譯成{lang_name}。\n\n"
        "規則：\n"
        "- 保留所有時間戳格式（如 [00:00]、[01:23]）\n"
        "- 保留品牌名/產品名/專有名詞的英文原文\n"
        "- 翻譯要自然流暢，不要逐字翻譯\n"
        "- 保留原文的 Markdown 格式（標題、粗體、列表等）\n"
        "- 不要添加任何額外說明或註解\n\n"
        f"{chunk}"
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    return response.text


# --- 背景執行主函式 ---

def _do_translate(
    job_dir: Path,
    status_path: Path,
    source_text: str,
    source_filename: str,
    source_path: str | None,
    target_language: str | None,
    model: str,
    job_id: str,
    caller_context: dict | None,
    output_path: Path,
    ctos_path: str,
) -> None:
    """子程序中執行的翻譯工作"""
    status_data = {
        "job_id": job_id,
        "status": "reading",
        "progress": "",
        "source_path": source_path or "",
        "source_filename": source_filename,
        "target_language": target_language,
        "model": model,
        "output_path": str(output_path),
        "ctos_path": ctos_path,
        "error": None,
        "warnings": [],
        "created_at": datetime.now().isoformat(),
    }
    if caller_context:
        status_data["caller_context"] = caller_context

    try:
        _write_status(status_path, status_data)

        # 初始化 Gemini client
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY 未設定")

        from google import genai
        import httpx
        client = genai.Client(
            api_key=api_key,
            http_options={"timeout": 120_000},  # 120 秒 timeout
        )

        # 切 chunk
        chunks = _split_chunks(source_text)
        total = len(chunks)

        # 語言偵測（如果未指定）
        if not target_language:
            target_language = _detect_target_language(
                source_text[:5000], client, model
            )
            status_data["target_language"] = target_language
            _write_status(status_path, status_data)

        # 逐 chunk 翻譯
        status_data["status"] = "translating"
        translated_chunks = []
        for i, chunk in enumerate(chunks):
            status_data["progress"] = f"{i + 1}/{total}"
            _write_status(status_path, status_data)

            # 重試最多 3 次
            translated = None
            last_error = None
            for attempt in range(3):
                try:
                    translated = _translate_chunk(
                        chunk, target_language, client, model
                    )
                    break
                except Exception as e:
                    last_error = str(e)
                    time.sleep(2 ** attempt)  # exponential backoff

            if translated is None:
                # 3 次都失敗，保留原文
                translated_chunks.append(chunk)
                warning = f"chunk {i + 1}/{total} 翻譯失敗，保留原文：{last_error}"
                status_data["warnings"].append(warning)
            else:
                translated_chunks.append(translated)

        # 檢查是否全部失敗
        if len(status_data["warnings"]) == total:
            status_data["status"] = "failed"
            status_data["error"] = "所有 chunk 翻譯均失敗"
            _write_status(status_path, status_data)
            return

        # 合併寫入輸出檔
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_text = "\n".join(translated_chunks)
        output_path.write_text(result_text, encoding="utf-8")

        # 完成
        status_data["status"] = "completed"
        status_data["progress"] = f"{total}/{total}"
        _write_status(status_path, status_data)

        # 觸發推送
        _trigger_proactive_push(job_id, "media-translation")

    except Exception as e:
        status_data["status"] = "failed"
        status_data["error"] = str(e)
        try:
            _write_status(status_path, status_data)
        except Exception:
            pass


# --- 主程式 ---

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
MAX_TEXT_LENGTH = 500_000  # 50 萬字元


def main() -> int:
    payload = json.loads(sys.stdin.read())

    source_path_str = payload.get("source_path")
    text = payload.get("text")
    target_language = payload.get("target_language")
    model = payload.get("model", "gemini-2.5-flash")
    caller_context = payload.get("caller_context")

    # 驗證輸入
    if not source_path_str and not text:
        print(json.dumps({
            "success": False,
            "error": "必須提供 source_path 或 text",
        }, ensure_ascii=False))
        return 1

    # 讀取來源內容
    source_filename = ""
    if source_path_str:
        resolved = _resolve_source_path(source_path_str)
        if not resolved:
            print(json.dumps({
                "success": False,
                "error": f"找不到檔案或路徑不允許：{source_path_str}",
            }, ensure_ascii=False))
            return 1

        # 檔案大小檢查
        if resolved.stat().st_size > MAX_FILE_SIZE:
            print(json.dumps({
                "success": False,
                "error": f"檔案超過 {MAX_FILE_SIZE // 1024 // 1024} MB 上限",
            }, ensure_ascii=False))
            return 1

        source_text = resolved.read_text(encoding="utf-8")
        source_filename = resolved.name
    else:
        source_text = text
        if len(source_text) > MAX_TEXT_LENGTH:
            print(json.dumps({
                "success": False,
                "error": f"文字超過 {MAX_TEXT_LENGTH} 字元上限",
            }, ensure_ascii=False))
            return 1

    # 建立 job
    job_id = uuid_module.uuid4().hex[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = _get_translations_base_dir()
    job_dir = base_dir / date_str / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    status_path = job_dir / "status.json"

    # 決定輸出路徑
    lang_suffix = target_language or "zh-TW"
    if source_path_str:
        # 存在來源旁邊
        resolved = _resolve_source_path(source_path_str)
        stem = resolved.stem
        ext = resolved.suffix
        output_path = resolved.parent / f"{stem}_{lang_suffix}{ext}"
        # 計算 ctos_path
        ctos_mount = _get_ctos_mount_path()
        try:
            rel = output_path.resolve().relative_to(Path(ctos_mount).resolve())
            ctos_path = f"ctos://{rel}"
        except ValueError:
            ctos_path = str(output_path)
    else:
        output_path = job_dir / "translation.md"
        ctos_path = f"ctos://linebot/translations/{date_str}/{job_id}/translation.md"

    # 寫初始狀態
    initial_status = {
        "job_id": job_id,
        "status": "starting",
        "progress": "",
        "source_path": source_path_str or "",
        "source_filename": source_filename,
        "target_language": target_language,
        "model": model,
        "output_path": str(output_path),
        "ctos_path": ctos_path,
        "error": None,
        "warnings": [],
        "created_at": datetime.now().isoformat(),
    }
    if caller_context:
        initial_status["caller_context"] = caller_context
    _write_status(status_path, initial_status)

    # Fork
    pid = os.fork()
    if pid > 0:
        # 父程序：立即回傳
        print(json.dumps({
            "success": True,
            "job_id": job_id,
            "status": "started",
            "message": f"翻譯已啟動，使用 check-translation 查詢進度",
        }, ensure_ascii=False))
        return 0
    else:
        # 子程序
        try:
            os.setsid()
            os.chdir(str(job_dir))

            # 重導向 stdout/stderr 到 worker.log
            log_fd = os.open(
                str(job_dir / "worker.log"),
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            )
            devnull = os.open(os.devnull, os.O_RDONLY)
            os.dup2(devnull, 0)
            os.dup2(log_fd, 1)
            os.dup2(log_fd, 2)
            os.close(devnull)
            os.close(log_fd)

            _do_translate(
                job_dir=job_dir,
                status_path=status_path,
                source_text=source_text,
                source_filename=source_filename,
                source_path=source_path_str,
                target_language=target_language,
                model=model,
                job_id=job_id,
                caller_context=caller_context,
                output_path=output_path,
                ctos_path=ctos_path,
            )
        finally:
            os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
