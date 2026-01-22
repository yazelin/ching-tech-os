"""簡報生成 API"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.presentation import generate_html_presentation

router = APIRouter(prefix="/api/presentation", tags=["presentation"])


class PresentationRequest(BaseModel):
    """簡報生成請求"""

    topic: str = Field("", description="簡報主題（與 outline_json 擇一）")
    num_slides: int = Field(5, ge=2, le=20, description="頁數（2-20）")
    theme: str = Field(
        "uncover",
        description="Marp 主題：uncover（深色投影）、gaia（暖色調）、gaia-invert（專業藍）、default（簡約白）",
    )
    include_images: bool = Field(True, description="是否自動配圖")
    image_source: str = Field(
        "pexels",
        description="圖片來源：pexels（圖庫）、huggingface（AI）、nanobanana（Gemini AI）",
    )
    outline_json: str | None = Field(None, description="直接傳入大綱 JSON，跳過 AI 生成")
    output_format: str = Field(
        "html",
        description="輸出格式：html（網頁，可直接瀏覽）、pdf（可下載列印）",
    )


class PresentationResponse(BaseModel):
    """簡報生成回應"""

    success: bool
    title: str
    slides_count: int
    nas_path: str
    filename: str
    format: str
    message: str


@router.post("/generate", response_model=PresentationResponse, summary="生成簡報")
async def api_generate_presentation(request: PresentationRequest) -> PresentationResponse:
    """生成 Marp 簡報（HTML 或 PDF）

    有兩種使用方式：
    1. 提供 topic，AI 自動生成大綱
    2. 提供 outline_json，直接使用傳入的大綱製作簡報
    """
    # 驗證：必須有 topic 或 outline_json
    if not request.topic and not request.outline_json:
        raise HTTPException(status_code=400, detail="請提供 topic 或 outline_json")

    # 驗證主題
    valid_themes = ["default", "gaia", "gaia-invert", "uncover"]
    if request.theme not in valid_themes:
        raise HTTPException(
            status_code=400,
            detail=f"無效的主題：{request.theme}，可用主題：{', '.join(valid_themes)}",
        )

    # 驗證輸出格式
    valid_formats = ["html", "pdf"]
    if request.output_format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"無效的輸出格式：{request.output_format}，可用格式：{', '.join(valid_formats)}",
        )

    try:
        result = await generate_html_presentation(
            topic=request.topic or "簡報",
            num_slides=request.num_slides,
            theme=request.theme,
            include_images=request.include_images,
            image_source=request.image_source,
            outline_json=request.outline_json,
            output_format=request.output_format,
        )

        format_names = {"html": "HTML", "pdf": "PDF"}
        return PresentationResponse(
            success=True,
            title=result["title"],
            slides_count=result["slides_count"],
            nas_path=result["nas_path"],
            filename=result["filename"],
            format=result["format"],
            message=f"已生成《{result['title']}》{format_names.get(result['format'], result['format'])} 簡報，共 {result['slides_count']} 頁",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成簡報失敗：{str(e)}")
