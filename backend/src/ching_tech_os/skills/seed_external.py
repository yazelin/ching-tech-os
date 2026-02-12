"""外部 Skill 種子檔案（~/SDD/skill）。

僅在目錄不存在時初始化，避免覆蓋管理員手動修改。
"""

from pathlib import Path


SEED_SKILLS: dict[str, dict] = {
    "base": {
        "skill_md": """---
name: base
description: 對話附件查詢（script-first）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: null
    mcp_servers: ching-tech-os
    script_mcp_fallback:
      get_message_attachments: get_message_attachments
      summarize_chat: summarize_chat
---

【對話附件管理（script-first）】
- 優先使用 run_skill_script 呼叫 scripts：
  ・run_skill_script(skill="base", script="get_message_attachments", input="{\\"days\\":3}")
  ・run_skill_script(skill="base", script="summarize_chat", input="{\\"target\\":\\"today\\"}")
- input 必須為 JSON 物件字串。
""",
        "scripts": {
            "get_message_attachments.py": """#!/usr/bin/env python3
\"\"\"標準化附件查詢參數，交由 MCP fallback 執行。\"\"\"

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    payload = {}
    if raw:
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("input 必須是 JSON 物件")
        except Exception as exc:
            print(json.dumps({"success": False, "error": f"invalid_input: {exc}"}, ensure_ascii=False))
            return 1

    payload.setdefault("days", 3)
    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
""",
            "summarize_chat.py": """#!/usr/bin/env python3
\"\"\"標準化聊天摘要參數，交由 MCP fallback 執行。\"\"\"

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    payload = {}
    if raw:
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("input 必須是 JSON 物件")
        except Exception as exc:
            print(json.dumps({"success": False, "error": f"invalid_input: {exc}"}, ensure_ascii=False))
            return 1

    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
""",
        },
    },
    "share-links": {
        "skill_md": """---
name: share-links
description: 公開分享連結（script-first）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: null
    mcp_servers: ching-tech-os
    script_mcp_fallback:
      create_share_link: create_share_link
---

【公開分享連結（script-first）】
- 使用 run_skill_script(skill="share-links", script="create_share_link", input="{...JSON...}")。
- input 至少包含 resource_type 與 resource_id。
""",
        "scripts": {
            "create_share_link.py": """#!/usr/bin/env python3
\"\"\"標準化分享連結參數，交由 MCP fallback 執行。\"\"\"

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"invalid_input: {exc}"}, ensure_ascii=False))
        return 1

    if not isinstance(payload, dict):
        print(json.dumps({"success": False, "error": "input 必須是 JSON 物件"}, ensure_ascii=False))
        return 1

    if "resource_type" not in payload or "resource_id" not in payload:
        print(json.dumps({"success": False, "error": "缺少 resource_type/resource_id"}, ensure_ascii=False))
        return 1

    payload.setdefault("expires_in", "24h")
    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
""",
        },
    },
    "file-manager": {
        "skill_md": """---
name: file-manager
description: NAS 檔案查找與發送（script-first）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: file-manager
    mcp_servers: ching-tech-os
    script_mcp_fallback:
      search_nas_files: search_nas_files
      get_nas_file_info: get_nas_file_info
      prepare_file_message: prepare_file_message
---

【NAS 檔案（script-first）】
- 優先用 run_skill_script 呼叫 scripts/search_nas_files。
- 找到路徑後可呼叫 get_nas_file_info / prepare_file_message。
""",
        "scripts": {
            "search_nas_files.py": """#!/usr/bin/env python3
\"\"\"標準化 NAS 搜尋參數，交由 MCP fallback 執行。\"\"\"

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"invalid_input: {exc}"}, ensure_ascii=False))
        return 1

    if not isinstance(payload, dict):
        print(json.dumps({"success": False, "error": "input 必須是 JSON 物件"}, ensure_ascii=False))
        return 1

    if "keywords" not in payload:
        print(json.dumps({"success": False, "error": "缺少 keywords"}, ensure_ascii=False))
        return 1

    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
""",
            "get_nas_file_info.py": """#!/usr/bin/env python3
\"\"\"標準化檔案資訊查詢參數，交由 MCP fallback 執行。\"\"\"

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"invalid_input: {exc}"}, ensure_ascii=False))
        return 1

    if not isinstance(payload, dict):
        print(json.dumps({"success": False, "error": "input 必須是 JSON 物件"}, ensure_ascii=False))
        return 1

    if "file_path" not in payload:
        print(json.dumps({"success": False, "error": "缺少 file_path"}, ensure_ascii=False))
        return 1

    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
""",
            "prepare_file_message.py": """#!/usr/bin/env python3
\"\"\"標準化檔案發送參數，交由 MCP fallback 執行。\"\"\"

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"invalid_input: {exc}"}, ensure_ascii=False))
        return 1

    if not isinstance(payload, dict):
        print(json.dumps({"success": False, "error": "input 必須是 JSON 物件"}, ensure_ascii=False))
        return 1

    if "file_path" not in payload:
        print(json.dumps({"success": False, "error": "缺少 file_path"}, ensure_ascii=False))
        return 1

    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
""",
        },
    },
    "pdf-converter": {
        "skill_md": """---
name: pdf-converter
description: PDF 轉圖片（script-first）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: file-manager
    mcp_servers: ching-tech-os
    script_mcp_fallback:
      convert_pdf_to_images: convert_pdf_to_images
---

【PDF 轉圖片（script-first）】
- 使用 run_skill_script(skill="pdf-converter", script="convert_pdf_to_images", input="{...JSON...}")。
""",
        "scripts": {
            "convert_pdf_to_images.py": """#!/usr/bin/env python3
\"\"\"標準化 PDF 轉圖參數，交由 MCP fallback 執行。\"\"\"

import json
import sys


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"invalid_input: {exc}"}, ensure_ascii=False))
        return 1

    if not isinstance(payload, dict):
        print(json.dumps({"success": False, "error": "input 必須是 JSON 物件"}, ensure_ascii=False))
        return 1

    if "pdf_path" not in payload:
        print(json.dumps({"success": False, "error": "缺少 pdf_path"}, ensure_ascii=False))
        return 1

    payload.setdefault("pages", "all")
    payload.setdefault("output_format", "png")
    print(json.dumps({
        "success": False,
        "error": "fallback_required",
        "normalized_input": payload,
    }, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
""",
        },
    },
}


def ensure_seed_skills(external_root: Path) -> None:
    """初始化 external root 的預設 split skills。"""
    external_root.mkdir(parents=True, exist_ok=True)

    for skill_name, skill_def in SEED_SKILLS.items():
        skill_dir = external_root / skill_name
        if skill_dir.exists():
            continue

        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(skill_def["skill_md"], encoding="utf-8")

        scripts = skill_def.get("scripts") or {}
        if scripts:
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            for filename, content in scripts.items():
                script_path = scripts_dir / filename
                script_path.write_text(content, encoding="utf-8")
                script_path.chmod(0o755)
