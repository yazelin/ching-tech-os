"""簡報生成服務

使用 Marp 生成 HTML/PDF 簡報，Claude CLI 生成大綱，Pexels/AI 配圖。
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

import httpx

from ..config import settings
from .smb import SMBService
from .workers import run_in_smb_pool
from .claude_agent import call_claude
from .huggingface_image import generate_image_with_flux, is_fallback_available

logger = logging.getLogger("presentation")

# Pexels API Key
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# 簡報輸出路徑（相對於 NAS ctos 根目錄）
PRESENTATION_NAS_PATH = "ai-presentations"


# ============================================================
# Marp 主題配置
# ============================================================

MARP_THEMES = {
    "default": {
        "name": "簡約白",
        "marp_theme": "default",
        "class": "",
    },
    "gaia": {
        "name": "暖色調",
        "marp_theme": "gaia",
        "class": "",
    },
    "gaia-invert": {
        "name": "專業藍",
        "marp_theme": "gaia",
        "class": "invert",
    },
    "uncover": {
        "name": "深色投影",
        "marp_theme": "uncover",
        "class": "",
    },
}


# ============================================================
# Claude API 呼叫
# ============================================================


async def generate_outline(
    topic: str,
    num_slides: int = 5,
    theme: str = "uncover",
) -> dict:
    """
    使用 Claude CLI 生成簡報大綱

    Args:
        topic: 簡報主題
        num_slides: 頁數
        theme: Marp 主題

    Returns:
        簡報大綱 dict
    """
    theme_name = MARP_THEMES.get(theme, MARP_THEMES["uncover"])["name"]

    prompt = f"""請為以下主題生成一份 {num_slides} 頁的簡報大綱，風格為{theme_name}風格。

主題：{topic}

請用 JSON 格式回傳，結構如下：
{{
    "title": "簡報標題",
    "slides": [
        {{
            "layout": "title",
            "title": "標題",
            "subtitle": "副標題（選填）"
        }},
        {{
            "layout": "content",
            "title": "頁面標題",
            "content": ["重點1", "重點2", "重點3"],
            "image_keyword": "搜尋圖片的關鍵字（英文）"
        }}
    ]
}}

layout 類型說明：
- "title": 封面頁（大標題+副標題）
- "section": 章節分隔頁（章節標題）
- "content": 標題+項目符號（最常用）
- "quote": 引言頁
- "thanks": 感謝頁

規則：
1. 第一頁必須是 layout="title" 的封面
2. 內容頁使用 layout="content"
3. 章節開頭可用 layout="section" 作為分隔
4. 最後一頁可用 layout="thanks"
5. 每頁 content 最多 5 個重點
6. 只回傳 JSON，不要其他文字或 markdown 標記"""

    try:
        response = await call_claude(
            prompt=prompt,
            model="sonnet",
            timeout=120,
        )

        if not response.success:
            raise ValueError(f"Claude 回應失敗: {response.error}")

        text = response.message.strip()

        # 移除可能的 markdown 標記
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        outline = json.loads(text)
        return outline

    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失敗: {e}, 原始回應: {text[:500]}")
        raise ValueError("AI 回應格式錯誤，請稍後重試")
    except Exception as e:
        logger.error(f"Claude CLI 呼叫失敗: {e}")
        raise


# ============================================================
# 圖片來源
# ============================================================


async def fetch_pexels_image(keyword: str) -> Optional[bytes]:
    """從 Pexels 下載圖片"""
    if not PEXELS_API_KEY:
        logger.warning("PEXELS_API_KEY 未設定，跳過配圖")
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.pexels.com/v1/search",
                params={
                    "query": keyword,
                    "per_page": 1,
                    "orientation": "landscape",
                },
                headers={"Authorization": PEXELS_API_KEY},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("photos"):
                logger.warning(f"Pexels 找不到圖片: {keyword}")
                return None

            image_url = data["photos"][0]["src"]["large"]
            image_response = await client.get(image_url, timeout=30.0)
            image_response.raise_for_status()

            return image_response.content

    except Exception as e:
        logger.warning(f"Pexels API 錯誤: {e}")
        return None


async def generate_huggingface_image(keyword: str) -> Optional[bytes]:
    """使用 Hugging Face FLUX 生成圖片"""
    if not is_fallback_available():
        logger.warning("HUGGINGFACE_API_TOKEN 未設定，跳過 AI 配圖")
        return None

    try:
        image_path, error = await generate_image_with_flux(
            f"Professional presentation slide image about {keyword}, clean modern style, high quality"
        )

        if error or not image_path:
            logger.warning(f"Hugging Face 圖片生成失敗: {error}")
            return None

        full_path = f"{settings.linebot_local_path}/{image_path}"
        with open(full_path, "rb") as f:
            return f.read()

    except Exception as e:
        logger.warning(f"Hugging Face 圖片生成錯誤: {e}")
        return None


async def generate_nanobanana_image(keyword: str) -> Optional[bytes]:
    """使用 nanobanana (Gemini) 生成圖片"""
    try:
        prompt = f"""請使用 mcp__nanobanana__generate_image 工具生成一張圖片。

圖片描述：Professional presentation slide image about {keyword}, clean modern style, high quality, suitable for business presentation

只需要呼叫工具生成圖片，不需要其他說明。"""

        response = await call_claude(
            prompt=prompt,
            model="haiku",
            timeout=120,
            tools=["mcp__nanobanana__generate_image"],
        )

        if not response.success:
            logger.warning(f"Nanobanana 呼叫失敗: {response.error}")
            return None

        for tc in response.tool_calls:
            if tc.name == "mcp__nanobanana__generate_image" and tc.output:
                output_str = tc.output if isinstance(tc.output, str) else str(tc.output)

                match = re.search(
                    r"(?:nanobanana-output|ai-images)/[\w\-\.]+\.(?:jpg|jpeg|png|webp)",
                    output_str,
                    re.IGNORECASE,
                )
                if match:
                    relative_path = match.group(0)
                    if "nanobanana-output/" in relative_path:
                        relative_path = "ai-images/" + relative_path.split(
                            "nanobanana-output/"
                        )[-1]

                    full_path = f"{settings.linebot_local_path}/{relative_path}"
                    if os.path.exists(full_path):
                        with open(full_path, "rb") as f:
                            return f.read()

        logger.warning("Nanobanana 未回傳有效的圖片路徑")
        return None

    except Exception as e:
        logger.warning(f"Nanobanana 圖片生成錯誤: {e}")
        return None


async def fetch_image(keyword: str, source: str = "pexels") -> Optional[bytes]:
    """根據來源取得圖片"""
    if source == "huggingface":
        return await generate_huggingface_image(keyword)
    elif source == "nanobanana":
        return await generate_nanobanana_image(keyword)
    else:
        return await fetch_pexels_image(keyword)


# ============================================================
# 工具函數
# ============================================================


def sanitize_filename(name: str) -> str:
    """清理檔名，移除不允許的字元"""
    cleaned = re.sub(r'[<>:"/\\|?*]', "", name)
    cleaned = " ".join(cleaned.split())
    return cleaned[:50] if len(cleaned) > 50 else cleaned


# ============================================================
# Marp 簡報生成
# ============================================================


def generate_marp_markdown(
    outline: dict,
    theme: str = "uncover",
    include_images: bool = True,
) -> str:
    """將大綱轉換為 Marp Markdown 格式"""
    theme_config = MARP_THEMES.get(theme, MARP_THEMES["uncover"])
    marp_theme = theme_config["marp_theme"]
    theme_class = theme_config.get("class", "")

    class_directive = f"\n_class: {theme_class}" if theme_class else ""
    # uncover 主題強制使用深色模式
    color_scheme = "color-scheme: dark;" if marp_theme == "uncover" else ""
    frontmatter = f"""---
marp: true
theme: {marp_theme}
paginate: true{class_directive}
style: |
  section {{
    font-family: 'Noto Sans TC', 'Microsoft JhengHei', sans-serif;
    {color_scheme}
  }}
  img {{
    border-radius: 8px;
  }}
---

"""

    slides_md = []

    for i, slide_data in enumerate(outline.get("slides", [])):
        slide_type = slide_data.get("layout", slide_data.get("type", "content"))
        title = slide_data.get("title", "")
        subtitle = slide_data.get("subtitle", "")
        content = slide_data.get("content", [])
        image_url = slide_data.get("image_url", "")

        slide_md = ""

        if slide_type == "title":
            slide_md = f"""<!-- _class: lead -->

# {title}

{subtitle}

"""
        elif slide_type == "section":
            slide_md = f"""<!-- _class: lead -->

# {title}

"""
        else:
            slide_md = f"## {title}\n\n"

            if content:
                for item in content:
                    if "：" in item:
                        slide_md += f"- **{item.split('：')[0]}**{item[len(item.split('：')[0]):]}\n"
                    else:
                        slide_md += f"- {item}\n"

            if include_images and image_url:
                slide_md += f"\n![bg right:40%]({image_url})\n"

        slides_md.append(slide_md)

    return frontmatter + "\n---\n\n".join(slides_md)


async def generate_html_presentation(
    topic: str = "",
    num_slides: int = 5,
    theme: str = "uncover",
    include_images: bool = True,
    image_source: str = "pexels",
    outline_json: Optional[str | dict] = None,
    output_format: str = "html",
) -> dict:
    """
    生成 Marp 簡報（HTML 或 PDF）

    Args:
        topic: 簡報主題（當 outline_json 為 None 時使用）
        num_slides: 頁數（預設 5）
        theme: 主題（default, gaia, gaia-invert, uncover）
        include_images: 是否配圖（預設 True）
        image_source: 圖片來源（pexels, huggingface, nanobanana）
        outline_json: 直接傳入大綱 JSON
        output_format: 輸出格式（html 或 pdf）

    Returns:
        包含簡報資訊和 NAS 路徑的 dict
    """
    import subprocess
    import tempfile

    # 1. 取得大綱
    if outline_json:
        if isinstance(outline_json, str):
            outline = json.loads(outline_json)
        else:
            outline = outline_json
    else:
        outline = await generate_outline(topic, num_slides, theme)

    # 2. 為每張投影片配圖
    if include_images:
        for slide_data in outline.get("slides", []):
            slide_type = slide_data.get("layout", slide_data.get("type", "content"))
            if slide_type not in ["title", "section"] and slide_data.get("image_keyword"):
                image_bytes = await fetch_image(slide_data["image_keyword"], image_source)
                if image_bytes:
                    import base64
                    b64 = base64.b64encode(image_bytes).decode("utf-8")
                    slide_data["image_url"] = f"data:image/jpeg;base64,{b64}"

    # 3. 生成 Marp Markdown
    marp_md = generate_marp_markdown(outline, theme, include_images)

    # 4. 使用 marp-cli 轉換
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as md_file:
        md_file.write(marp_md)
        md_path = md_file.name

    if output_format == "pdf":
        output_ext = ".pdf"
        marp_args = ["--pdf", "--allow-local-files", "--no-stdin"]
    else:
        output_ext = ".html"
        marp_args = ["--html", "--no-stdin"]

    output_path = md_path.replace(".md", output_ext)

    # 使用本地安裝的 marp-cli（避免 npx 每次下載）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    marp_bin = os.path.join(backend_dir, "node_modules", ".bin", "marp")

    # 如果本地沒有，fallback 到 npx
    if not os.path.exists(marp_bin):
        marp_cmd = ["npx", "--yes", "@marp-team/marp-cli"]
    else:
        marp_cmd = [marp_bin]

    try:
        result = subprocess.run(
            marp_cmd + [md_path, "-o", output_path] + marp_args,
            capture_output=True,
            text=True,
            timeout=180,  # 增加超時時間到 3 分鐘
        )
        if result.returncode != 0:
            logger.error(f"marp-cli 錯誤: {result.stderr}")
            raise RuntimeError(f"marp-cli 轉換失敗: {result.stderr}")

        with open(output_path, "rb" if output_format == "pdf" else "r", encoding=None if output_format == "pdf" else "utf-8") as f:
            output_content = f.read()

    finally:
        if os.path.exists(md_path):
            os.unlink(md_path)
        if os.path.exists(output_path):
            os.unlink(output_path)

    # 5. 儲存到 NAS
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pres_title = outline.get("title", topic) or "簡報"
    safe_topic = sanitize_filename(pres_title)
    filename = f"{safe_topic}_{timestamp}{output_ext}"

    relative_path = PRESENTATION_NAS_PATH

    # 確保目錄存在（使用本機掛載點建立）
    local_dir = f"{settings.ctos_mount_path}/{relative_path}"
    os.makedirs(local_dir, exist_ok=True)

    try:
        smb = SMBService(
            host=settings.nas_host,
            username=settings.nas_user,
            password=settings.nas_password,
        )
        nas_file_path = f"ching-tech-os/{relative_path}/{filename}"
        file_data = output_content if output_format == "pdf" else output_content.encode("utf-8")

        def _upload():
            with smb:
                smb.write_file(settings.nas_share, nas_file_path, file_data)

        await run_in_smb_pool(_upload)

        logger.info(f"{output_format.upper()} 簡報已儲存: {nas_file_path}")

    except Exception as e:
        logger.error(f"上傳 NAS 失敗: {e}")
        local_path = f"{local_dir}/{filename}"

        write_mode = "wb" if output_format == "pdf" else "w"
        with open(local_path, write_mode, encoding=None if output_format == "pdf" else "utf-8") as f:
            f.write(output_content)
        logger.info(f"{output_format.upper()} 簡報已儲存到本機: {local_path}")

    return {
        "success": True,
        "title": outline.get("title", topic),
        "slides_count": len(outline.get("slides", [])),
        "nas_path": f"{relative_path}/{filename}",
        "filename": filename,
        "format": output_format,
    }
