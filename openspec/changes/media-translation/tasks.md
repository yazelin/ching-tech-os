# media-translation 實作計畫

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立背景翻譯 skill，使用 Gemini SDK 分 chunk 翻譯長文，支援 NAS 檔案和直接文字輸入，完成後 proactive-push 通知使用者。

**Architecture:** 沿用 media-downloader / media-transcription 的 `os.fork()` + `status.json` + `proactive-push` 模式。翻譯引擎使用 Google Gemini SDK（`google-genai`），分 chunk（每 20,000 字元）呼叫 Gemini 2.5 Flash 翻譯。

**Tech Stack:** Python 3.11+, google-genai SDK, os.fork(), FastAPI (internal push)

**Spec:** `docs/superpowers/specs/2026-03-18-media-translation-design.md`

---

## Task 1: translate.py — 啟動翻譯腳本

**Files:**
- Create: `backend/src/ching_tech_os/skills/media-translation/scripts/translate.py`

- [ ] **Step 1: 建立 translate.py 骨架**

建立翻譯啟動腳本，包含完整的 os.fork 背景執行模式。

```python
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

CHUNK_SIZE = 20_000  # 每 chunk 約 20,000 字元


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
        client = genai.Client(api_key=api_key)

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
    # 先用預設的 target_language 來命名；若為 null 會在子程序偵測後更新
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
```

- [ ] **Step 2: 驗證腳本語法正確**

Run: `cd /home/ct/SDD/ching-tech-os && python3 -c "import ast; ast.parse(open('backend/src/ching_tech_os/skills/media-translation/scripts/translate.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/ching_tech_os/skills/media-translation/scripts/translate.py
git commit -m "feat: 新增 media-translation skill 翻譯啟動腳本"
```

---

## Task 2: check-translation.py — 查詢進度腳本

**Files:**
- Create: `backend/src/ching_tech_os/skills/media-translation/scripts/check-translation.py`

- [ ] **Step 1: 建立 check-translation.py**

參照 `check-transcription.py` 的模式：

```python
"""查詢翻譯進度與狀態。"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

STALE_TIMEOUT_MINUTES = 30

STATUS_LABELS = {
    "starting": "準備中",
    "reading": "讀取來源中",
    "translating": "翻譯中",
    "completed": "完成",
    "failed": "失敗",
}


def _get_ctos_mount_path() -> str:
    return os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")


def _find_status_file(job_id: str) -> Path | None:
    """搜尋最近 7 天的日期目錄找 status.json"""
    base = Path(_get_ctos_mount_path()) / "linebot" / "translations"
    if not base.exists():
        return None

    resolved_base = base.resolve()
    today = datetime.now()

    for days_ago in range(7):
        date_str = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        date_dir = base / date_str
        if not date_dir.is_dir():
            continue
        status_path = date_dir / job_id / "status.json"
        if not status_path.exists():
            continue
        # 路徑安全驗證
        try:
            status_path.resolve().relative_to(resolved_base)
        except ValueError:
            continue
        return status_path

    return None


def main() -> int:
    payload = json.loads(sys.stdin.read())
    job_id = payload.get("job_id", "").strip()

    if not job_id or not job_id.isalnum() or len(job_id) != 8:
        print(json.dumps({
            "success": False,
            "error": "無效的 job_id（需為 8 位英數字元）",
        }, ensure_ascii=False))
        return 1

    status_path = _find_status_file(job_id)
    if not status_path:
        print(json.dumps({
            "success": False,
            "error": f"找不到翻譯任務：{job_id}",
        }, ensure_ascii=False))
        return 1

    try:
        status_data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"讀取狀態失敗：{e}",
        }, ensure_ascii=False))
        return 1

    status = status_data.get("status", "unknown")

    # 逾時判定
    if status in ("starting", "reading", "translating"):
        updated_at = status_data.get("updated_at", "")
        if updated_at:
            try:
                last_update = datetime.fromisoformat(updated_at)
                elapsed = (datetime.now() - last_update).total_seconds()
                if elapsed > STALE_TIMEOUT_MINUTES * 60:
                    status_data["status"] = "failed"
                    status_data["error"] = f"逾時：超過 {STALE_TIMEOUT_MINUTES} 分鐘無更新"
                    status = "failed"
            except Exception:
                pass

    status_label = STATUS_LABELS.get(status, status)
    result = {
        "success": True,
        "job_id": job_id,
        "status": status,
        "status_label": status_label,
        "progress": status_data.get("progress", ""),
        "target_language": status_data.get("target_language", ""),
        "model": status_data.get("model", ""),
        "source_filename": status_data.get("source_filename", ""),
        "warnings": status_data.get("warnings", []),
        "error": status_data.get("error"),
    }

    if status == "completed":
        ctos_path = status_data.get("ctos_path", "")
        result["ctos_path"] = ctos_path

        # 解析 file_path（絕對路徑）
        output_path = status_data.get("output_path", "")
        if output_path and Path(output_path).exists():
            result["file_path"] = output_path
        elif ctos_path:
            # 從 ctos_path 推算
            ctos_mount = _get_ctos_mount_path()
            if ctos_path.startswith("ctos://"):
                fs_path = Path(ctos_mount) / ctos_path[len("ctos://"):]
                if fs_path.exists():
                    result["file_path"] = str(fs_path)

    if status == "failed":
        result["error"] = status_data.get("error", "未知錯誤")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 驗證語法**

Run: `cd /home/ct/SDD/ching-tech-os && python3 -c "import ast; ast.parse(open('backend/src/ching_tech_os/skills/media-translation/scripts/check-translation.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/ching_tech_os/skills/media-translation/scripts/check-translation.py
git commit -m "feat: 新增 media-translation 進度查詢腳本"
```

---

## Task 3: SKILL.md — Skill 定義與 AI prompt

**Files:**
- Create: `backend/src/ching_tech_os/skills/media-translation/SKILL.md`

- [ ] **Step 1: 建立 SKILL.md**

```markdown
---
name: media-translation
description: 長文翻譯（Gemini，背景執行）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: file-manager
    mcp_servers: ching-tech-os
---

【長文翻譯（Gemini 背景執行）】

將長文（逐字稿、文章等）翻譯成指定語言。使用 Google Gemini 翻譯，背景執行不阻塞。
翻譯流程為非同步：啟動翻譯 → 查詢進度 → 取得翻譯結果。

**可用 scripts：**

1. **translate** — 啟動翻譯（非同步，立即回傳 job ID）
   - `run_skill_script(skill="media-translation", script="translate", input='{"source_path":"ctos://...","caller_context":{...}}')`
   - source_path：要翻譯的檔案路徑（支援 `ctos://`、`shared://` 格式，限 .md/.txt 純文字）
   - 或 text：直接傳入要翻譯的文字（二擇一）
   - 可選參數：
     · target_language：目標語言代碼（如 zh-TW、en），預設自動偵測
     · model：Gemini 模型（預設 gemini-2.5-flash）
   - **必須附帶 caller_context**
   - 限制：檔案 ≤ 2MB，文字 ≤ 500,000 字元

2. **check-translation** — 查詢翻譯進度（同步）
   - `run_skill_script(skill="media-translation", script="check-translation", input='{"job_id":"之前取得的job_id"}')`
   - 回傳翻譯狀態（starting/reading/translating/completed/failed）
   - 翻譯中顯示進度（如「3/12」表示第 3 段，共 12 段）
   - 完成時回傳：file_path（絕對路徑，可用 Read 工具讀取）、ctos_path

**典型使用流程：**
1. 使用者要求翻譯某篇文章或逐字稿
2. 呼叫 translate 啟動翻譯，取得 job_id
3. 告知使用者「翻譯已啟動，完成後會通知」，結束本次回應
4. （系統自動：翻譯完成後 proactive-push 通知使用者）
5. 使用者再次詢問時，用 check-translation 確認狀態

**語言偵測邏輯：**
- 未指定 target_language 時自動偵測：
  · 英文/中英夾雜 → 翻譯成繁體中文
  · 繁體中文 → 翻譯成英文

**AI 行為指引：**
- 當使用者要求翻譯長文件（逐字稿、文章、文件）時使用此 skill
- 短文翻譯（幾段話）直接回覆即可，不需要用此 skill
- **嚴禁使用 sleep 等待翻譯完成**。啟動後只需查詢一次進度：
  - 若仍在翻譯中：回覆「翻譯進行中（進度 3/12），完成後會通知」，結束本次回應
  - 若已完成：讀取翻譯結果並回覆
- **務必附帶 caller_context**，否則完成後無法推送通知
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/ching_tech_os/skills/media-translation/SKILL.md
git commit -m "feat: 新增 media-translation SKILL.md 定義與 AI prompt"
```

---

## Task 4: internal_push.py — 新增翻譯完成推送

**Files:**
- Modify: `backend/src/ching_tech_os/api/internal_push.py:34-37` (skill_subdir mapping)
- Modify: `backend/src/ching_tech_os/api/internal_push.py:87-98` (build_message)

- [ ] **Step 1: 在 `_find_status_file` 加入 media-translation 對應**

在 `internal_push.py:34-38` 的 skill_subdir dict 加入 `"media-translation": "translations"`：

```python
    skill_subdir = {
        "research-skill": "research",
        "media-downloader": "videos",
        "media-transcription": "transcriptions",
        "media-translation": "translations",
    }.get(skill)
```

- [ ] **Step 2: 在 `_build_message` 加入翻譯完成訊息**

在 `internal_push.py` 的 `_build_message` 函式中，`media-transcription` 區塊之後（約第 98 行後）加入：

```python
    if skill == "media-translation":
        source_filename = status.get("source_filename", "")
        ctos_path = status.get("ctos_path", "")
        warnings = status.get("warnings", [])
        lines = ["✅ 翻譯完成"]
        if source_filename:
            lines.append(f"來源：{source_filename}")
        if ctos_path:
            lines.append(f"翻譯檔：{ctos_path}")
        if warnings:
            lines.append(f"⚠️ {len(warnings)} 段翻譯失敗，保留原文")
        lines.append(f"（job_id: {job_id}）")
        return "\n".join(lines)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/ching_tech_os/api/internal_push.py
git commit -m "feat: internal_push 支援 media-translation 完成通知"
```

---

## Task 5: linebot_agents.py — 禁止 background Task 規則

**Files:**
- Modify: `backend/src/ching_tech_os/services/linebot_agents.py:316-321` (LINEBOT_PERSONAL_PROMPT)
- Modify: `backend/src/ching_tech_os/services/linebot_agents.py:410-414` (LINEBOT_GROUP_PROMPT)

- [ ] **Step 1: 在 LINEBOT_PERSONAL_PROMPT 的「對話歷史注意事項」之後加入規則**

在 `linebot_agents.py:321` 之後（「遇到矛盾時…」那行後）加入：

```
【工具使用限制】
- 禁止使用 Task 工具的 run_in_background 模式，背景任務會在 session 結束後死亡
- 需要背景執行的長時間任務，請使用對應的 skill script（如 media-translation、media-transcription、media-downloader）
```

- [ ] **Step 2: 在 LINEBOT_GROUP_PROMPT 同樣加入此規則**

在 `linebot_agents.py:414` 之後（group prompt 的「對話歷史注意事項」後）加入相同規則。

- [ ] **Step 3: Commit**

```bash
git add backend/src/ching_tech_os/services/linebot_agents.py
git commit -m "fix: 禁止 AI 在 Line Bot 中使用 Task run_in_background"
```

---

## Task 6: 整合測試

- [ ] **Step 1: 驗證 skill 被 SkillManager 正確載入**

```bash
cd /home/ct/SDD/ching-tech-os/backend
uv run python3 -c "
from ching_tech_os.skills import get_skill_manager
sm = get_skill_manager()
skill = sm.get_skill('media-translation')
print(f'Skill: {skill.name}')
print(f'Scripts: {[s.name for s in skill.scripts]}')
print(f'Requires app: {skill.metadata}')
"
```

Expected: 顯示 skill 名稱、兩個 scripts（translate、check-translation）

- [ ] **Step 2: 驗證 translate.py 輸入驗證（無 source_path 也無 text）**

```bash
cd /home/ct/SDD/ching-tech-os/backend
echo '{}' | uv run python3 src/ching_tech_os/skills/media-translation/scripts/translate.py
```

Expected: `{"success": false, "error": "必須提供 source_path 或 text"}`

- [ ] **Step 3: 驗證 check-translation.py 無效 job_id**

```bash
cd /home/ct/SDD/ching-tech-os/backend
echo '{"job_id": "invalid!"}' | uv run python3 src/ching_tech_os/skills/media-translation/scripts/check-translation.py
```

Expected: `{"success": false, "error": "無效的 job_id（需為 8 位英數字元）"}`

- [ ] **Step 4: Commit 整合測試通過確認**

確認所有測試通過後，不需要額外 commit（測試是手動驗證）。
