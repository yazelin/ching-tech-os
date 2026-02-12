"""MD 驗證器測試。"""

from ching_tech_os.services.md_validators import (
    ValidationError,
    ValidationResult,
    validate_content,
    validate_md2doc,
    validate_md2ppt,
)


def test_validation_result_to_error_message() -> None:
    ok = ValidationResult(valid=True)
    assert ok.to_error_message() == "驗證通過"

    failed = ValidationResult(
        valid=False,
        errors=[
            ValidationError(line=3, message="錯誤一", suggestion="修正一"),
            ValidationError(line=0, message="錯誤二"),
        ],
    )
    message = failed.to_error_message()
    assert "第 3 行：錯誤一" in message
    assert "建議：修正一" in message
    assert "錯誤二" in message


def test_validate_md2ppt_valid_content() -> None:
    content = """---
theme: amber
title: 測試投影片
---

# 首頁

:: right ::

右欄內容

::: chart-bar {"title": "圖表"}

| 項目 | 值 |
| --- | --- |
| A | 1 |

:::

===

---
layout: two-column
---

## 第二頁
"""
    result = validate_md2ppt(content)
    assert result.valid is True
    assert result.errors == []


def test_validate_md2ppt_invalid_content() -> None:
    content = """---
theme: invalid_theme
---
標題
===
下一頁
::: chart-bar {'title': 'x'}
:: right ::
文字
"""
    result = validate_md2ppt(content)
    assert result.valid is False
    messages = [e.message for e in result.errors]
    assert any("無效的 theme 值" in m for m in messages)
    assert any("`===` 前面必須有空行" in m for m in messages)
    assert any("`===` 後面必須有空行" in m for m in messages)
    assert any("圖表 JSON 中不能使用單引號" in m for m in messages)
    assert any("`:: right ::` 後面必須有空行" in m for m in messages)


def test_validate_md2doc_valid_content() -> None:
    content = """---
title: "文件標題"
author: "作者"
---

# H1
## H2
### H3

> [!TIP]
> 這是提示

角色 "::
內容

角色 ::"
內容

角色 :":
內容
"""
    result = validate_md2doc(content)
    assert result.valid is True


def test_validate_md2doc_invalid_content() -> None:
    content = """---
title: 未加引號 # 造成風險
---

#### 不允許的標題

> [!DANGER]
> 不允許的類型

角色 :: "
"""
    result = validate_md2doc(content)
    assert result.valid is False
    messages = [e.message for e in result.errors]
    assert any("Frontmatter 缺少 author 設定" in m for m in messages)
    assert any("YAML 中的值包含 # 符號" in m for m in messages)
    assert any("不支援 H4 標題" in m for m in messages)
    assert any("不支援的 Callout 類型" in m for m in messages)
    assert any("對話語法錯誤" in m for m in messages)


def test_validate_content_router() -> None:
    assert validate_content("---\ntheme: amber\n---", "md2ppt").valid is True
    assert validate_content("---\ntitle: a\nauthor: b\n---", "md2doc").valid is True

    unknown = validate_content("x", "unknown-type")
    assert unknown.valid is False
    assert "不支援的內容類型" in unknown.errors[0].message
