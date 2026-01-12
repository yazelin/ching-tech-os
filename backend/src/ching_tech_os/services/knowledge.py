"""知識庫服務"""

import json
import logging
import os
import re
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

from ching_tech_os.config import settings
from ching_tech_os.models.knowledge import (
    HistoryEntry,
    HistoryResponse,
    IndexEntry,
    KnowledgeAttachment,
    KnowledgeCreate,
    KnowledgeIndex,
    KnowledgeListItem,
    KnowledgeListResponse,
    KnowledgeResponse,
    KnowledgeSource,
    KnowledgeTags,
    KnowledgeUpdate,
    TagsResponse,
    VersionResponse,
)
from ching_tech_os.services.local_file import (
    LocalFileService,
    LocalFileError,
    create_knowledge_file_service,
    create_linebot_file_service,
)
from ching_tech_os.database import get_connection


class KnowledgeError(Exception):
    """知識庫操作錯誤"""

    pass


class KnowledgeNotFoundError(KnowledgeError):
    """知識不存在"""

    pass


# 知識庫路徑
KNOWLEDGE_BASE_PATH = Path("/home/ct/SDD/ching-tech-os/data/knowledge")
ENTRIES_PATH = KNOWLEDGE_BASE_PATH / "entries"
ASSETS_PATH = KNOWLEDGE_BASE_PATH / "assets"
INDEX_PATH = KNOWLEDGE_BASE_PATH / "index.json"


def _slugify(text: str) -> str:
    """將文字轉換為 slug 格式"""
    # 簡單的中英文轉換，保留英文字母和數字
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:50]


def _load_index() -> KnowledgeIndex:
    """載入知識索引"""
    if not INDEX_PATH.exists():
        return KnowledgeIndex()

    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return KnowledgeIndex(**data)
    except Exception as e:
        raise KnowledgeError(f"載入索引失敗：{e}") from e


def _save_index(index: KnowledgeIndex) -> None:
    """儲存知識索引"""
    try:
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        index.last_updated = datetime.now().isoformat()
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(index.model_dump(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise KnowledgeError(f"儲存索引失敗：{e}") from e


def _parse_front_matter(content: str) -> tuple[dict[str, Any], str]:
    """解析 YAML Front Matter

    Returns:
        (metadata_dict, markdown_content)
    """
    if not content.startswith("---"):
        return {}, content

    # 找到第二個 ---
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    yaml_content = content[3 : end_match.start() + 3]
    markdown_content = content[end_match.end() + 3 :].strip()

    try:
        metadata = yaml.safe_load(yaml_content)
        return metadata or {}, markdown_content
    except yaml.YAMLError:
        return {}, content


def _generate_front_matter(metadata: dict[str, Any]) -> str:
    """產生 YAML Front Matter"""
    # 自訂 YAML 輸出格式
    yaml_content = yaml.dump(
        metadata,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{yaml_content}---\n\n"


def _find_knowledge_file(kb_id: str) -> Path | None:
    """根據 ID 找到知識檔案"""
    pattern = f"{kb_id}-*.md"
    files = list(ENTRIES_PATH.glob(pattern))
    return files[0] if files else None


def _metadata_to_response(
    metadata: dict[str, Any], content: str, file_path: Path
) -> KnowledgeResponse:
    """將元資料轉換為回應物件"""
    tags_data = metadata.get("tags", {})
    tags = KnowledgeTags(
        projects=tags_data.get("projects", []),
        roles=tags_data.get("roles", []),
        topics=tags_data.get("topics", []),
        level=tags_data.get("level"),
    )

    source_data = metadata.get("source", {})
    source = KnowledgeSource(
        project=source_data.get("project"),
        path=source_data.get("path"),
        commit=source_data.get("commit"),
    )

    attachments = []
    for att_data in metadata.get("attachments", []):
        attachments.append(
            KnowledgeAttachment(
                type=att_data.get("type", "file"),
                path=att_data.get("path", ""),
                size=att_data.get("size"),
                description=att_data.get("description"),
            )
        )

    created_at = metadata.get("created_at", date.today())
    updated_at = metadata.get("updated_at", date.today())

    # 處理日期格式
    if isinstance(created_at, str):
        created_at = date.fromisoformat(created_at)
    if isinstance(updated_at, str):
        updated_at = date.fromisoformat(updated_at)

    return KnowledgeResponse(
        id=metadata.get("id", ""),
        title=metadata.get("title", ""),
        type=metadata.get("type", "knowledge"),
        category=metadata.get("category", "technical"),
        scope=metadata.get("scope", "global"),
        owner=metadata.get("owner"),
        project_id=metadata.get("project_id"),
        tags=tags,
        source=source,
        related=metadata.get("related", []),
        attachments=attachments,
        author=metadata.get("author", "system"),
        created_at=created_at,
        updated_at=updated_at,
        content=content,
    )


def get_knowledge(kb_id: str) -> KnowledgeResponse:
    """取得單一知識

    Args:
        kb_id: 知識 ID（如 kb-001）

    Returns:
        知識完整內容
    """
    file_path = _find_knowledge_file(kb_id)
    if not file_path:
        raise KnowledgeNotFoundError(f"知識 {kb_id} 不存在")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        metadata, content = _parse_front_matter(raw_content)
        return _metadata_to_response(metadata, content, file_path)
    except KnowledgeNotFoundError:
        raise
    except Exception as e:
        raise KnowledgeError(f"讀取知識失敗：{e}") from e


def search_knowledge(
    query: str | None = None,
    project: str | None = None,
    kb_type: str | None = None,
    category: str | None = None,
    role: str | None = None,
    level: str | None = None,
    topics: list[str] | None = None,
    scope: str | None = None,
    current_username: str | None = None,
) -> KnowledgeListResponse:
    """搜尋知識

    Args:
        query: 關鍵字搜尋（使用 ripgrep）
        project: 專案過濾
        kb_type: 類型過濾
        category: 分類過濾
        role: 角色過濾
        level: 層級過濾
        topics: 主題過濾
        scope: 範圍過濾（global、personal、all）
        current_username: 目前使用者帳號（用於過濾個人知識）

    Returns:
        符合條件的知識列表
    """
    index = _load_index()
    results: list[KnowledgeListItem] = []

    # 先用 ripgrep 搜尋內容（如果有關鍵字）
    matching_files: set[str] | None = None
    snippets: dict[str, str] = {}

    if query:
        try:
            # 使用 ripgrep 搜尋
            result = subprocess.run(
                [
                    "rg",
                    "-i",  # 不分大小寫
                    "-l",  # 只輸出檔名
                    "--type",
                    "md",
                    query,
                    str(ENTRIES_PATH),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            matching_files = set()
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        matching_files.add(Path(line).name)

            # 取得匹配片段
            result_context = subprocess.run(
                [
                    "rg",
                    "-i",
                    "-C",
                    "1",  # 前後各 1 行
                    "--type",
                    "md",
                    query,
                    str(ENTRIES_PATH),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result_context.returncode == 0:
                current_file = None
                for line in result_context.stdout.split("\n"):
                    if ":" in line:
                        parts = line.split(":", 1)
                        file_path = Path(parts[0]).name
                        if file_path not in snippets:
                            snippets[file_path] = parts[1][:200] if len(parts) > 1 else ""

        except subprocess.TimeoutExpired:
            pass  # 搜尋逾時，回退到全部列出
        except FileNotFoundError:
            pass  # ripgrep 未安裝

    # 遍歷索引項目
    for entry in index.entries:
        # 檔案內容過濾
        if matching_files is not None and entry.filename not in matching_files:
            continue

        # Scope 過濾
        entry_scope = getattr(entry, "scope", "global")
        entry_owner = getattr(entry, "owner", None)

        if scope:
            if scope == "global" and entry_scope != "global":
                continue
            if scope == "personal":
                if entry_scope != "personal":
                    continue
                # 個人知識只顯示自己的
                if current_username and entry_owner != current_username:
                    continue
        else:
            # 預設行為：全域知識 + 自己的個人知識
            if entry_scope == "personal" and entry_owner != current_username:
                continue

        # 專案過濾
        if project and project not in entry.tags.projects:
            continue

        # 類型過濾
        if kb_type and entry.type != kb_type:
            continue

        # 分類過濾
        if category and entry.category != category:
            continue

        # 角色過濾
        if role and role not in entry.tags.roles:
            continue

        # 層級過濾
        if level and entry.tags.level != level:
            continue

        # 主題過濾
        if topics:
            if not any(t in entry.tags.topics for t in topics):
                continue

        # 轉換日期
        updated_at = entry.updated_at
        if isinstance(updated_at, str):
            updated_at = date.fromisoformat(updated_at)

        entry_project_id = getattr(entry, "project_id", None)
        results.append(
            KnowledgeListItem(
                id=entry.id,
                title=entry.title,
                type=entry.type,
                category=entry.category,
                scope=entry_scope,
                owner=entry_owner,
                project_id=entry_project_id,
                tags=entry.tags,
                author=entry.author,
                updated_at=updated_at,
                snippet=snippets.get(entry.filename),
            )
        )

    # 按更新時間排序（最新在前）
    results.sort(key=lambda x: x.updated_at, reverse=True)

    return KnowledgeListResponse(items=results, total=len(results), query=query)


def create_knowledge(data: KnowledgeCreate, owner: str | None = None, project_id: str | None = None) -> KnowledgeResponse:
    """建立新知識

    Args:
        data: 知識資料
        owner: 擁有者帳號（建立個人知識時設定）
        project_id: 關聯專案 UUID（建立專案知識時設定，會覆蓋 data.project_id）

    Returns:
        建立的知識
    """
    index = _load_index()

    # 分配 ID
    kb_id = f"kb-{index.next_id:03d}"
    index.next_id += 1

    # 產生 slug
    slug = data.slug or _slugify(data.title)
    if not slug:
        slug = f"knowledge-{index.next_id}"

    # 確保 slug 唯一
    existing_slugs = {e.filename.split("-", 2)[-1].replace(".md", "") for e in index.entries}
    original_slug = slug
    counter = 2
    while slug in existing_slugs:
        slug = f"{original_slug}-{counter}"
        counter += 1

    # 檔名
    filename = f"{kb_id}-{slug}.md"
    file_path = ENTRIES_PATH / filename

    # 準備元資料
    today = date.today()

    # 設定 scope、owner 和 project_id
    knowledge_scope = data.scope
    knowledge_owner = owner if knowledge_scope == "personal" else None
    knowledge_project_id = project_id or data.project_id if knowledge_scope == "project" else None

    metadata = {
        "id": kb_id,
        "title": data.title,
        "type": data.type,
        "category": data.category,
        "scope": knowledge_scope,
        "owner": knowledge_owner,
        "project_id": knowledge_project_id,
        "tags": {
            "projects": data.tags.projects,
            "roles": data.tags.roles,
            "topics": data.tags.topics,
            "level": data.tags.level,
        },
        "source": {
            "project": data.source.project if data.source else None,
            "path": data.source.path if data.source else None,
            "commit": data.source.commit if data.source else None,
        },
        "related": data.related,
        "attachments": [],
        "author": data.author,
        "created_at": today.isoformat(),
        "updated_at": today.isoformat(),
    }

    # 產生檔案內容
    front_matter = _generate_front_matter(metadata)
    file_content = front_matter + data.content

    # 寫入檔案（自動建立目錄）
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
    except Exception as e:
        raise KnowledgeError(f"建立知識檔案失敗：{e}") from e

    # 更新索引
    index_entry = IndexEntry(
        id=kb_id,
        title=data.title,
        filename=filename,
        type=data.type,
        category=data.category,
        scope=knowledge_scope,
        owner=knowledge_owner,
        project_id=knowledge_project_id,
        tags=data.tags,
        author=data.author,
        created_at=today.isoformat(),
        updated_at=today.isoformat(),
    )
    index.entries.append(index_entry)

    # 更新主題標籤
    for topic in data.tags.topics:
        if topic not in index.tags.topics:
            index.tags.topics.append(topic)

    _save_index(index)

    return get_knowledge(kb_id)


def update_knowledge(kb_id: str, data: KnowledgeUpdate) -> KnowledgeResponse:
    """更新知識

    Args:
        kb_id: 知識 ID
        data: 更新資料

    Returns:
        更新後的知識
    """
    file_path = _find_knowledge_file(kb_id)
    if not file_path:
        raise KnowledgeNotFoundError(f"知識 {kb_id} 不存在")

    # 讀取現有內容
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        metadata, content = _parse_front_matter(raw_content)
    except Exception as e:
        raise KnowledgeError(f"讀取知識失敗：{e}") from e

    # 更新元資料
    if data.title is not None:
        metadata["title"] = data.title
    if data.type is not None:
        metadata["type"] = data.type
    if data.category is not None:
        metadata["category"] = data.category
    if data.tags is not None:
        metadata["tags"] = {
            "projects": data.tags.projects,
            "roles": data.tags.roles,
            "topics": data.tags.topics,
            "level": data.tags.level,
        }
    if data.source is not None:
        metadata["source"] = {
            "project": data.source.project,
            "path": data.source.path,
            "commit": data.source.commit,
        }
    if data.related is not None:
        metadata["related"] = data.related

    # 更新內容
    if data.content is not None:
        content = data.content

    # 更新時間戳
    metadata["updated_at"] = date.today().isoformat()

    # 寫入檔案
    front_matter = _generate_front_matter(metadata)
    file_content = front_matter + content

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
    except Exception as e:
        raise KnowledgeError(f"更新知識檔案失敗：{e}") from e

    # 更新索引
    index = _load_index()
    for entry in index.entries:
        if entry.id == kb_id:
            if data.title is not None:
                entry.title = data.title
            if data.type is not None:
                entry.type = data.type
            if data.category is not None:
                entry.category = data.category
            if data.tags is not None:
                entry.tags = data.tags
            entry.updated_at = date.today().isoformat()
            break

    # 更新主題標籤
    if data.tags:
        for topic in data.tags.topics:
            if topic not in index.tags.topics:
                index.tags.topics.append(topic)

    _save_index(index)

    return get_knowledge(kb_id)


def delete_knowledge(kb_id: str) -> None:
    """刪除知識

    Args:
        kb_id: 知識 ID
    """
    file_path = _find_knowledge_file(kb_id)
    if not file_path:
        raise KnowledgeNotFoundError(f"知識 {kb_id} 不存在")

    # 先讀取附件列表
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
        metadata, _ = _parse_front_matter(raw_content)
        attachments = metadata.get("attachments", [])
    except Exception:
        attachments = []

    # 刪除所有附件（忽略錯誤，確保知識可以被刪除）
    file_service = create_knowledge_file_service()
    for attachment in attachments:
        attachment_path = attachment.get("path", "")
        try:
            if attachment_path.startswith("nas://knowledge/"):
                # NAS 檔案（透過掛載路徑存取）
                nas_path = attachment_path.replace("nas://knowledge/", "")
                file_service.delete_file(nas_path)
            elif attachment_path.startswith("../assets/images/"):
                # 本機檔案
                filename = attachment_path.split("/")[-1]
                local_path = ASSETS_PATH / "images" / filename
                if local_path.exists():
                    local_path.unlink()
        except Exception:
            # 附件刪除失敗不阻止知識刪除
            pass

    # 嘗試刪除 NAS 上的 kb_id 目錄（如果為空）
    try:
        file_service.delete_directory(f"attachments/{kb_id}")
    except Exception:
        pass  # 目錄可能不存在或不為空

    # 刪除知識檔案
    try:
        file_path.unlink()
    except Exception as e:
        raise KnowledgeError(f"刪除知識檔案失敗：{e}") from e

    # 更新索引
    index = _load_index()
    index.entries = [e for e in index.entries if e.id != kb_id]
    _save_index(index)


async def get_all_tags() -> TagsResponse:
    """取得所有標籤（專案從資料庫動態載入）"""
    index = _load_index()

    # 從資料庫取得專案列表
    try:
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT name FROM projects WHERE status = 'active' ORDER BY name"
            )
            db_projects = [row["name"] for row in rows]
    except Exception as e:
        logger.error(f"從資料庫取得專案列表失敗: {e}")
        # 資料庫查詢失敗時使用索引中的專案
        db_projects = []

    # 合併資料庫專案和索引中的主題
    # 保留 "common" 作為通用專案選項
    all_projects = list(set(db_projects + ["common"]))
    all_projects.sort()

    return TagsResponse(
        projects=all_projects,
        types=index.tags.types,
        categories=index.tags.categories,
        roles=index.tags.roles,
        levels=index.tags.levels,
        topics=index.tags.topics,
    )


def rebuild_index() -> dict[str, Any]:
    """重建索引

    Returns:
        重建結果統計
    """
    entries: list[IndexEntry] = []
    topics: set[str] = set()
    errors: list[str] = []

    # 掃描所有知識檔案
    for file_path in ENTRIES_PATH.glob("kb-*.md"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            metadata, _ = _parse_front_matter(raw_content)

            if not metadata.get("id"):
                errors.append(f"{file_path.name}: 缺少 id")
                continue

            tags_data = metadata.get("tags", {})
            tags = KnowledgeTags(
                projects=tags_data.get("projects", []),
                roles=tags_data.get("roles", []),
                topics=tags_data.get("topics", []),
                level=tags_data.get("level"),
            )

            # 收集主題
            for topic in tags.topics:
                topics.add(topic)

            entry = IndexEntry(
                id=metadata["id"],
                title=metadata.get("title", ""),
                filename=file_path.name,
                type=metadata.get("type", "knowledge"),
                category=metadata.get("category", "technical"),
                scope=metadata.get("scope", "global"),
                owner=metadata.get("owner"),
                project_id=metadata.get("project_id"),
                tags=tags,
                author=metadata.get("author", "system"),
                created_at=str(metadata.get("created_at", date.today().isoformat())),
                updated_at=str(metadata.get("updated_at", date.today().isoformat())),
            )
            entries.append(entry)

        except Exception as e:
            errors.append(f"{file_path.name}: {e}")

    # 計算 next_id
    max_id = 0
    for entry in entries:
        match = re.match(r"kb-(\d+)", entry.id)
        if match:
            max_id = max(max_id, int(match.group(1)))

    # 建立新索引
    index = _load_index()
    index.entries = entries
    index.next_id = max_id + 1
    index.tags.topics = sorted(list(topics))
    _save_index(index)

    return {
        "total": len(entries),
        "errors": errors,
        "next_id": index.next_id,
    }


def get_history(kb_id: str) -> HistoryResponse:
    """取得知識版本歷史

    Args:
        kb_id: 知識 ID

    Returns:
        版本歷史列表
    """
    file_path = _find_knowledge_file(kb_id)
    if not file_path:
        raise KnowledgeNotFoundError(f"知識 {kb_id} 不存在")

    entries: list[HistoryEntry] = []

    try:
        # 使用 git log --follow 取得歷史
        result = subprocess.run(
            [
                "git",
                "log",
                "--follow",
                "--pretty=format:%H|%an|%aI|%s",
                "--",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            cwd=KNOWLEDGE_BASE_PATH,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    entries.append(
                        HistoryEntry(
                            commit=parts[0],
                            author=parts[1],
                            date=parts[2],
                            message=parts[3],
                        )
                    )

    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    return HistoryResponse(id=kb_id, entries=entries)


def get_version(kb_id: str, commit: str) -> VersionResponse:
    """取得特定版本的知識內容

    Args:
        kb_id: 知識 ID
        commit: Git commit hash

    Returns:
        該版本的內容（不含 frontmatter）
    """
    file_path = _find_knowledge_file(kb_id)
    if not file_path:
        raise KnowledgeNotFoundError(f"知識 {kb_id} 不存在")

    try:
        # 取得相對路徑
        rel_path = file_path.relative_to(KNOWLEDGE_BASE_PATH.parent.parent)

        result = subprocess.run(
            ["git", "show", f"{commit}:{rel_path}"],
            capture_output=True,
            text=True,
            cwd=KNOWLEDGE_BASE_PATH.parent.parent,
            timeout=10,
        )

        if result.returncode != 0:
            raise KnowledgeError(f"無法取得版本 {commit}")

        # 解析 frontmatter，只回傳內容部分
        _, content = _parse_front_matter(result.stdout)
        return VersionResponse(id=kb_id, commit=commit, content=content)

    except subprocess.TimeoutExpired:
        raise KnowledgeError("取得版本內容逾時")
    except Exception as e:
        if isinstance(e, KnowledgeError):
            raise
        raise KnowledgeError(f"取得版本內容失敗：{e}") from e


def upload_attachment(
    kb_id: str, filename: str, data: bytes, description: str | None = None
) -> KnowledgeAttachment:
    """上傳附件

    小於 1MB 存本機，大於等於 1MB 存 NAS

    Args:
        kb_id: 知識 ID
        filename: 檔名
        data: 檔案內容
        description: 附件說明

    Returns:
        附件資訊
    """
    file_size = len(data)
    size_str = f"{file_size / 1024:.1f}KB" if file_size < 1024 * 1024 else f"{file_size / 1024 / 1024:.1f}MB"

    # 判斷檔案類型
    ext = Path(filename).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
        file_type = "image"
    elif ext in (".mp4", ".avi", ".mov", ".webm"):
        file_type = "video"
    elif ext in (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"):
        file_type = "document"
    else:
        file_type = "file"

    # 小於 1MB 存本機
    if file_size < 1024 * 1024:
        local_path = ASSETS_PATH / "images" / f"{kb_id}-{filename}"
        local_path.parent.mkdir(parents=True, exist_ok=True)

        with open(local_path, "wb") as f:
            f.write(data)

        attachment_path = f"../assets/images/{kb_id}-{filename}"
    else:
        # 大於等於 1MB 存 NAS（透過掛載路徑）
        nas_path = f"attachments/{kb_id}/{filename}"

        try:
            file_service = create_knowledge_file_service()
            # 確保目錄存在並寫入檔案
            file_service.write_file(nas_path, data)
        except LocalFileError as e:
            raise KnowledgeError(f"上傳附件到 NAS 失敗：{e}") from e

        attachment_path = f"nas://knowledge/{nas_path}"

    attachment = KnowledgeAttachment(
        type=file_type,
        path=attachment_path,
        size=size_str,
        description=description,
    )

    # 更新知識的附件列表
    file_path = _find_knowledge_file(kb_id)
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            metadata, content = _parse_front_matter(raw_content)

            if "attachments" not in metadata:
                metadata["attachments"] = []

            metadata["attachments"].append(attachment.model_dump())
            metadata["updated_at"] = date.today().isoformat()

            front_matter = _generate_front_matter(metadata)
            file_content = front_matter + content

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)

        except Exception:
            pass  # 更新元資料失敗不影響附件上傳

    return attachment


def copy_linebot_attachment_to_knowledge(
    kb_id: str, linebot_nas_path: str, description: str | None = None
) -> KnowledgeAttachment:
    """從 Line Bot NAS 複製附件到知識庫

    Args:
        kb_id: 知識 ID
        linebot_nas_path: Line Bot NAS 相對路徑（如 groups/xxx/images/2026-01-05/abc.jpg）
        description: 附件說明

    Returns:
        附件資訊

    Raises:
        KnowledgeError: 複製失敗
    """
    # 從路徑取得檔名
    filename = Path(linebot_nas_path).name

    # 從 Line Bot NAS 讀取檔案（透過掛載路徑）
    try:
        linebot_file_service = create_linebot_file_service()
        data = linebot_file_service.read_file(linebot_nas_path)
    except LocalFileError as e:
        raise KnowledgeError(f"讀取 Line Bot 附件失敗 ({linebot_nas_path})：{e}") from e

    # 使用現有的 upload_attachment 函數處理儲存邏輯
    return upload_attachment(kb_id, filename, data, description)


def get_nas_attachment(path: str) -> bytes:
    """從 NAS 讀取附件

    Args:
        path: 附件路徑（不含 nas://knowledge/ 前綴）

    Returns:
        檔案內容
    """
    try:
        file_service = create_knowledge_file_service()
        return file_service.read_file(f"attachments/{path}")
    except LocalFileError as e:
        raise KnowledgeError(f"讀取 NAS 附件失敗：{e}") from e


def update_attachment(
    kb_id: str,
    attachment_idx: int,
    description: str | None = None,
    attachment_type: str | None = None,
) -> KnowledgeAttachment:
    """更新附件資訊

    Args:
        kb_id: 知識 ID
        attachment_idx: 附件索引（從 0 開始）
        description: 附件說明
        attachment_type: 附件類型 (file, image, video, document)

    Returns:
        更新後的附件資訊
    """
    file_path = _find_knowledge_file(kb_id)
    if not file_path:
        raise KnowledgeNotFoundError(f"知識 {kb_id} 不存在")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        metadata, content = _parse_front_matter(raw_content)
        attachments = metadata.get("attachments", [])

        if attachment_idx < 0 or attachment_idx >= len(attachments):
            raise KnowledgeError(f"附件索引 {attachment_idx} 超出範圍")

        # 更新附件資訊
        if description is not None:
            attachments[attachment_idx]["description"] = description
        if attachment_type is not None:
            attachments[attachment_idx]["type"] = attachment_type

        metadata["attachments"] = attachments
        metadata["updated_at"] = date.today().isoformat()

        front_matter = _generate_front_matter(metadata)
        file_content = front_matter + content

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        # 回傳更新後的附件
        att = attachments[attachment_idx]
        return KnowledgeAttachment(
            type=att.get("type", "file"),
            path=att.get("path", ""),
            size=att.get("size"),
            description=att.get("description"),
        )

    except KnowledgeError:
        raise
    except Exception as e:
        raise KnowledgeError(f"更新附件失敗：{e}") from e


def delete_attachment(kb_id: str, attachment_idx: int) -> None:
    """刪除附件

    Args:
        kb_id: 知識 ID
        attachment_idx: 附件索引（從 0 開始）
    """
    file_path = _find_knowledge_file(kb_id)
    if not file_path:
        raise KnowledgeNotFoundError(f"知識 {kb_id} 不存在")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        metadata, content = _parse_front_matter(raw_content)
        attachments = metadata.get("attachments", [])

        if attachment_idx < 0 or attachment_idx >= len(attachments):
            raise KnowledgeError(f"附件索引 {attachment_idx} 超出範圍")

        attachment = attachments[attachment_idx]
        attachment_path = attachment.get("path", "")

        # 刪除實體檔案（檔案不存在也繼續刪除參考）
        if attachment_path.startswith("nas://knowledge/"):
            # NAS 檔案（透過掛載路徑存取）
            nas_path = attachment_path.replace("nas://knowledge/", "")
            try:
                file_service = create_knowledge_file_service()
                file_service.delete_file(nas_path)
            except Exception:
                # 檔案可能已不存在，忽略錯誤繼續刪除參考
                pass
        else:
            # 本機檔案
            filename = attachment_path.split("/")[-1]
            local_path = ASSETS_PATH / "images" / filename
            if local_path.exists():
                local_path.unlink()

        # 更新元資料
        attachments.pop(attachment_idx)
        metadata["attachments"] = attachments
        metadata["updated_at"] = date.today().isoformat()

        front_matter = _generate_front_matter(metadata)
        file_content = front_matter + content

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)

    except KnowledgeError:
        raise
    except Exception as e:
        raise KnowledgeError(f"刪除附件失敗：{e}") from e
