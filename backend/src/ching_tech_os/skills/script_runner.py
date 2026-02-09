"""Skill Script Runner

執行 skill 的 scripts/ 目錄下的腳本。
支援 .py 和 .sh 檔案。
"""

import asyncio
import logging
import os
import re
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_VALID_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9_-]*[a-z0-9])?$")
_DEFAULT_TIMEOUT = 30


class ScriptRunner:
    """執行 skill scripts 的 runner"""

    def __init__(self, skills_dir: Path):
        self._skills_dir = skills_dir

    def _validate_names(self, skill_name: str, script_name: str) -> None:
        """驗證 skill name 和 script name（防止路徑穿越）"""
        for name, label in [(skill_name, "Skill"), (script_name, "Script")]:
            if not name or len(name) > 64:
                raise ValueError(f"{label} name 長度無效: {name!r}")
            if ".." in name or "/" in name or "\\" in name:
                raise ValueError(f"{label} name 含非法字元: {name!r}")
            if not _VALID_NAME_RE.match(name):
                raise ValueError(f"{label} name 格式無效: {name!r}")

    def _resolve_script_path(self, skill_name: str, script_name: str) -> Path | None:
        """解析 script 路徑，嘗試 .py 和 .sh 副檔名"""
        scripts_dir = self._skills_dir / skill_name / "scripts"
        if not scripts_dir.is_dir():
            return None

        for ext in (".py", ".sh"):
            path = scripts_dir / f"{script_name}{ext}"
            if path.is_file():
                # 確保在 scripts_dir 下（防 symlink 攻擊）
                try:
                    path.resolve().relative_to(scripts_dir.resolve())
                except ValueError:
                    return None
                return path
        return None

    def _parse_docstring(self, script_path: Path) -> str:
        """從 script 提取描述"""
        try:
            text = script_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

        if script_path.suffix == ".py":
            # Python docstring: 第一個 triple-quoted string
            import ast
            try:
                tree = ast.parse(text)
                docstring = ast.get_docstring(tree)
                if docstring:
                    return docstring.split("\n")[0].strip()
            except SyntaxError:
                pass
        elif script_path.suffix == ".sh":
            # Shell: # Description: ...
            for line in text.splitlines()[:20]:
                line = line.strip()
                if line.lower().startswith("# description:"):
                    return line.split(":", 1)[1].strip()

        return ""

    def list_scripts(self, skill_name: str) -> list[dict]:
        """列出 skill 的所有 scripts"""
        try:
            self._validate_names(skill_name, "placeholder")
        except ValueError:
            return []

        scripts_dir = self._skills_dir / skill_name / "scripts"
        if not scripts_dir.is_dir():
            return []

        results = []
        for f in sorted(scripts_dir.iterdir()):
            if not f.is_file() or f.suffix not in (".py", ".sh"):
                continue
            name = f.stem
            results.append({
                "name": name,
                "path": str(f.relative_to(self._skills_dir)),
                "description": self._parse_docstring(f),
            })
        return results

    def get_script_info(self, skill_name: str, script_name: str) -> dict | None:
        """取得單一 script 資訊"""
        try:
            self._validate_names(skill_name, script_name)
        except ValueError:
            return None

        path = self._resolve_script_path(skill_name, script_name)
        if not path:
            return None

        return {
            "name": script_name,
            "path": str(path.relative_to(self._skills_dir)),
            "description": self._parse_docstring(path),
        }

    async def execute(
        self,
        skill_name: str,
        script_name: str,
        input_str: str = "",
        env_overrides: dict[str, str] | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> dict:
        """執行 script，回傳 {success, output, error, duration_ms}"""
        self._validate_names(skill_name, script_name)

        script_path = self._resolve_script_path(skill_name, script_name)
        if not script_path:
            return {
                "success": False,
                "output": "",
                "error": f"Script not found: {skill_name}/{script_name}",
                "duration_ms": 0,
            }

        # 組裝 command
        if script_path.suffix == ".py":
            if shutil.which("uv"):
                cmd = ["uv", "run", str(script_path)]
            else:
                cmd = ["python3", str(script_path)]
        elif script_path.suffix == ".sh":
            cmd = ["bash", str(script_path)]
        else:
            return {
                "success": False,
                "output": "",
                "error": f"Unsupported script type: {script_path.suffix}",
                "duration_ms": 0,
            }

        # 注入環境變數
        skill_dir = self._skills_dir / skill_name
        env = os.environ.copy()
        env["SKILL_NAME"] = skill_name
        env["SKILL_DIR"] = str(skill_dir)
        env["SKILL_ASSETS_DIR"] = str(skill_dir / "assets")
        if env_overrides:
            env.update(env_overrides)

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=skill_dir,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_str.encode("utf-8") if input_str else None),
                timeout=timeout,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            return {
                "success": proc.returncode == 0,
                "output": stdout.decode("utf-8", errors="replace").strip(),
                "error": stderr.decode("utf-8", errors="replace").strip(),
                "duration_ms": duration_ms,
            }
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return {
                "success": False,
                "output": "",
                "error": f"Script timed out after {timeout}s",
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "duration_ms": duration_ms,
            }
