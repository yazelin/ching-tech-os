"""MD2PPT 和 MD2DOC 格式驗證器

用於驗證 AI 產生的 Markdown 內容是否符合格式規範。
驗證失敗時回傳詳細錯誤清單，方便 AI 修正。
"""

import re
import json
from dataclasses import dataclass, field


@dataclass
class ValidationError:
    """驗證錯誤"""
    line: int  # 行號（從 1 開始，0 表示全域錯誤）
    message: str  # 錯誤訊息
    suggestion: str = ""  # 修正建議


@dataclass
class ValidationResult:
    """驗證結果"""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    def to_error_message(self) -> str:
        """轉換為可讀的錯誤訊息（給 AI 看）"""
        if self.valid:
            return "驗證通過"

        lines = ["格式驗證失敗，請修正以下錯誤：", ""]
        for err in self.errors:
            if err.line > 0:
                lines.append(f"- 第 {err.line} 行：{err.message}")
            else:
                lines.append(f"- {err.message}")
            if err.suggestion:
                lines.append(f"  建議：{err.suggestion}")

        return "\n".join(lines)


# ============================================
# MD2PPT 驗證器
# ============================================

# 有效的 theme 值
VALID_MD2PPT_THEMES = {"amber", "midnight", "academic", "material"}

# 有效的 layout 值
VALID_MD2PPT_LAYOUTS = {"default", "impact", "center", "grid", "two-column", "quote", "alert"}

# 有效的 transition 值
VALID_MD2PPT_TRANSITIONS = {"slide", "fade", "zoom", "none"}


def validate_md2ppt(content: str) -> ValidationResult:
    """驗證 MD2PPT 格式

    驗證規則：
    1. 全域 Frontmatter 在開頭，theme 必須是有效值
    2. `===` 分頁符前後必須有空行
    3. 每頁 layout 必須是有效值
    4. 圖表 `::: chart-xxx {JSON}` 的 JSON 必須有效（雙引號）
    5. 圖表區塊與表格前後必須有空行
    6. `:: right ::` 前後必須有空行
    """
    errors = []
    lines = content.split("\n")

    # 1. 檢查全域 Frontmatter
    if not content.strip().startswith("---"):
        errors.append(ValidationError(
            line=1,
            message="文件必須以 YAML Frontmatter 開頭（---）",
            suggestion="在第一行加上 ---，然後設定 theme, title 等屬性"
        ))
    else:
        # 解析全域 Frontmatter
        frontmatter_end = content.find("\n---", 3)
        if frontmatter_end == -1:
            errors.append(ValidationError(
                line=1,
                message="Frontmatter 沒有正確結束（缺少結尾的 ---）",
                suggestion="確保 Frontmatter 以 --- 結尾"
            ))
        else:
            frontmatter_content = content[3:frontmatter_end].strip()
            # 檢查 theme
            theme_match = re.search(r'^theme:\s*(\S+)', frontmatter_content, re.MULTILINE)
            if not theme_match:
                errors.append(ValidationError(
                    line=0,
                    message="全域 Frontmatter 缺少 theme 設定",
                    suggestion=f"請加入 theme 設定，有效值：{', '.join(VALID_MD2PPT_THEMES)}"
                ))
            else:
                theme = theme_match.group(1).strip('"\'')
                if theme not in VALID_MD2PPT_THEMES:
                    errors.append(ValidationError(
                        line=0,
                        message=f"無效的 theme 值：{theme}",
                        suggestion=f"有效值：{', '.join(VALID_MD2PPT_THEMES)}"
                    ))

    # 2. 檢查 === 分頁符前後空行
    for i, line in enumerate(lines):
        if line.strip() == "===":
            # 檢查前一行是否為空
            if i > 0 and lines[i - 1].strip() != "":
                errors.append(ValidationError(
                    line=i + 1,
                    message="`===` 前面必須有空行",
                    suggestion="在 === 前面加一個空行"
                ))
            # 檢查後一行是否為空
            if i < len(lines) - 1 and lines[i + 1].strip() != "":
                errors.append(ValidationError(
                    line=i + 1,
                    message="`===` 後面必須有空行",
                    suggestion="在 === 後面加一個空行"
                ))

    # 3. 檢查每頁的 layout 值
    layout_pattern = re.compile(r'^layout:\s*(\S+)', re.MULTILINE)
    for match in layout_pattern.finditer(content):
        layout = match.group(1).strip('"\'')
        if layout not in VALID_MD2PPT_LAYOUTS:
            # 找出行號
            line_num = content[:match.start()].count('\n') + 1
            errors.append(ValidationError(
                line=line_num,
                message=f"無效的 layout 值：{layout}",
                suggestion=f"有效值：{', '.join(VALID_MD2PPT_LAYOUTS)}"
            ))

    # 4. 檢查圖表語法
    chart_pattern = re.compile(r'^(\s*):::\s*chart-(\w+)\s*(\{.*\})?', re.MULTILINE)
    for match in chart_pattern.finditer(content):
        line_num = content[:match.start()].count('\n') + 1
        json_str = match.group(3)

        if json_str:
            # 檢查 JSON 是否有效
            try:
                json.loads(json_str)
            except json.JSONDecodeError as e:
                errors.append(ValidationError(
                    line=line_num,
                    message=f"圖表 JSON 格式錯誤：{e.msg}",
                    suggestion="確保 JSON 使用雙引號，例如：{ \"title\": \"標題\" }"
                ))

            # 檢查是否使用單引號
            if "'" in json_str:
                errors.append(ValidationError(
                    line=line_num,
                    message="圖表 JSON 中不能使用單引號",
                    suggestion="請將所有單引號 ' 改為雙引號 \""
                ))

        # 檢查前一行是否為空（除非是頁面開頭）
        if match.start() > 0:
            prev_content = content[:match.start()]
            prev_lines = prev_content.split('\n')
            if len(prev_lines) > 0 and prev_lines[-1].strip() != "" and prev_lines[-1].strip() != "---":
                errors.append(ValidationError(
                    line=line_num,
                    message="`:::` 圖表區塊前面必須有空行",
                    suggestion="在 ::: chart-xxx 前面加一個空行"
                ))

    # 檢查圖表結束標記 ::: 前是否有空行
    # 注意：使用 [ \t]* 而不是 \s*，避免匹配到換行符
    chart_end_pattern = re.compile(r'\n([ \t]*):::[ \t]*$', re.MULTILINE)
    for match in chart_end_pattern.finditer(content):
        line_num = content[:match.start()].count('\n') + 2
        # 檢查前一行是否為空
        prev_content = content[:match.start()]
        prev_lines = prev_content.split('\n')
        if len(prev_lines) > 0 and prev_lines[-1].strip() != "":
            # 確認這是圖表結束標記而不是其他用途
            # 往回找是否有對應的 ::: chart-
            before_end = content[:match.start()]
            if "::: chart-" in before_end:
                errors.append(ValidationError(
                    line=line_num,
                    message="圖表結束標記 `:::` 前面必須有空行",
                    suggestion="在表格和 ::: 之間加一個空行"
                ))

    # 5. 檢查 :: right :: 前後空行
    # 注意：使用 [ \t]* 而不是 \s*，避免匹配到換行符
    right_col_pattern = re.compile(r'^[ \t]*::[ \t]*right[ \t]*::', re.MULTILINE | re.IGNORECASE)
    for match in right_col_pattern.finditer(content):
        line_num = content[:match.start()].count('\n') + 1

        # 檢查前一行（緊接著 :: right :: 的那一行）
        if match.start() > 0:
            prev_newline_idx = content.rfind('\n', 0, match.start())
            if prev_newline_idx >= 0:
                # 取得緊接著的前一行內容
                prev_line_start = content.rfind('\n', 0, prev_newline_idx)
                if prev_line_start == -1:
                    # :: right :: 在第二行，前一行是第一行
                    prev_line = content[0:prev_newline_idx]
                else:
                    prev_line = content[prev_line_start + 1:prev_newline_idx]

                if prev_line.strip() != "":
                    errors.append(ValidationError(
                        line=line_num,
                        message="`:: right ::` 前面必須有空行",
                        suggestion="在 :: right :: 前面加一個空行"
                    ))

        # 檢查後一行（緊接著 :: right :: 的那一行）
        next_newline_idx = content.find('\n', match.end())
        if next_newline_idx >= 0:
            next_line_end = content.find('\n', next_newline_idx + 1)
            if next_line_end == -1:
                next_line_end = len(content)
            next_line = content[next_newline_idx + 1:next_line_end]
            if next_line.strip() != "":
                errors.append(ValidationError(
                    line=line_num,
                    message="`:: right ::` 後面必須有空行",
                    suggestion="在 :: right :: 後面加一個空行"
                ))

    return ValidationResult(valid=len(errors) == 0, errors=errors)


# ============================================
# MD2DOC 驗證器
# ============================================

# 有效的 Callout 類型
VALID_MD2DOC_CALLOUTS = {"TIP", "NOTE", "WARNING"}


def validate_md2doc(content: str) -> ValidationResult:
    """驗證 MD2DOC 格式

    驗證規則：
    1. Frontmatter 必須有 title 和 author
    2. 只支援 H1-H3，禁止 H4 以上
    3. Callout 只支援 TIP/NOTE/WARNING
    4. 對話語法正確：`"::` (左)、`::"` (右)、`:":` (中)
    """
    errors = []
    lines = content.split("\n")

    # 1. 檢查 Frontmatter
    if not content.strip().startswith("---"):
        errors.append(ValidationError(
            line=1,
            message="文件必須以 YAML Frontmatter 開頭（---）",
            suggestion="在第一行加上 ---，然後設定 title, author"
        ))
    else:
        frontmatter_end = content.find("\n---", 3)
        if frontmatter_end == -1:
            errors.append(ValidationError(
                line=1,
                message="Frontmatter 沒有正確結束（缺少結尾的 ---）",
                suggestion="確保 Frontmatter 以 --- 結尾"
            ))
        else:
            frontmatter_content = content[3:frontmatter_end].strip()

            # 檢查 title
            if not re.search(r'^title:', frontmatter_content, re.MULTILINE):
                errors.append(ValidationError(
                    line=0,
                    message="Frontmatter 缺少 title 設定",
                    suggestion="請加入 title: \"文件標題\""
                ))

            # 檢查 author
            if not re.search(r'^author:', frontmatter_content, re.MULTILINE):
                errors.append(ValidationError(
                    line=0,
                    message="Frontmatter 缺少 author 設定",
                    suggestion="請加入 author: \"作者名稱\""
                ))

            # 檢查是否在 YAML 中使用了 #（除了註解）
            for fm_line in frontmatter_content.split('\n'):
                fm_line_stripped = fm_line.strip()
                # 跳過空行和註解行
                if fm_line_stripped and not fm_line_stripped.startswith('#'):
                    # 檢查值中是否有未引號包裹的 #
                    if ':' in fm_line:
                        key_value = fm_line.split(':', 1)
                        if len(key_value) == 2:
                            value = key_value[1].strip()
                            # 如果值不是用引號包裹且包含 #
                            if value and not (value.startswith('"') or value.startswith("'")):
                                if '#' in value:
                                    errors.append(ValidationError(
                                        line=0,
                                        message="YAML 中的值包含 # 符號，可能導致解析錯誤",
                                        suggestion="請用雙引號包裹含有特殊字元的值"
                                    ))

    # 2. 檢查標題層級（禁止 H4 以上）
    heading_pattern = re.compile(r'^(#{4,})\s+', re.MULTILINE)
    for match in heading_pattern.finditer(content):
        line_num = content[:match.start()].count('\n') + 1
        level = len(match.group(1))
        errors.append(ValidationError(
            line=line_num,
            message=f"不支援 H{level} 標題（只支援 H1-H3）",
            suggestion="請將 H4 以下的標題改為 **粗體文字** 或列表項目"
        ))

    # 3. 檢查 Callout 類型
    callout_pattern = re.compile(r'>\s*\[!(\w+)\]', re.MULTILINE)
    for match in callout_pattern.finditer(content):
        callout_type = match.group(1).upper()
        if callout_type not in VALID_MD2DOC_CALLOUTS:
            line_num = content[:match.start()].count('\n') + 1
            errors.append(ValidationError(
                line=line_num,
                message=f"不支援的 Callout 類型：[!{match.group(1)}]",
                suggestion=f"有效類型：{', '.join(VALID_MD2DOC_CALLOUTS)}"
            ))

    # 4. 檢查對話語法
    # 正確格式：
    # - 左側：角色 "::  （引號在冒號前）
    # - 右側：角色 ::"  （引號在冒號後）
    # - 置中：角色 :":  （引號在中間）

    # 檢查可能的錯誤對話語法
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # 跳過空行和程式碼區塊
        if not line_stripped or line_stripped.startswith('```'):
            continue

        # 檢查是否有對話標記但格式錯誤
        if '::' in line and '"' in line:
            # 正確格式
            valid_left = re.search(r'\S+\s+"::$', line_stripped)  # 角色 "::
            valid_right = re.search(r'\S+\s+::"$', line_stripped)  # 角色 ::"
            valid_center = re.search(r'\S+\s+:":$', line_stripped)  # 角色 :":

            # 錯誤格式檢測
            if not (valid_left or valid_right or valid_center):
                # 可能的錯誤模式
                if re.search(r'::\s*"', line_stripped):  # :: " 中間有空格
                    errors.append(ValidationError(
                        line=i + 1,
                        message="對話語法錯誤：:: 和 \" 之間不應有空格",
                        suggestion="正確格式：角色 \":: 或 角色 ::\" 或 角色 :\":\""
                    ))
                elif re.search(r'"\s*::', line_stripped) and not valid_left:
                    # 有 ":: 但不是結尾
                    if not line_stripped.endswith('"::'):
                        errors.append(ValidationError(
                            line=i + 1,
                            message="左側對話語法應以 \":: 結尾",
                            suggestion="格式：角色 \":: （換行後接內容）"
                        ))

    return ValidationResult(valid=len(errors) == 0, errors=errors)


# ============================================
# 統一入口
# ============================================

def validate_content(content: str, content_type: str) -> ValidationResult:
    """根據類型驗證內容

    Args:
        content: Markdown 內容
        content_type: 'md2ppt' 或 'md2doc'

    Returns:
        ValidationResult: 驗證結果
    """
    if content_type.lower() == "md2ppt":
        return validate_md2ppt(content)
    elif content_type.lower() == "md2doc":
        return validate_md2doc(content)
    else:
        return ValidationResult(
            valid=False,
            errors=[ValidationError(
                line=0,
                message=f"不支援的內容類型：{content_type}",
                suggestion="有效類型：md2ppt, md2doc"
            )]
        )
