#!/bin/bash
# 統計專案程式碼行數

cd "$(dirname "$0")/.."

echo "╔════════════════════════════════════════╗"
echo "║   ChingTech OS 程式碼行數統計          ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Python
py_lines=$(find . -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" -exec cat {} + 2>/dev/null | grep -cv '^[[:space:]]*$')
py_files=$(find . -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" 2>/dev/null | wc -l)

# JavaScript
js_lines=$(find . -name "*.js" -not -path "*/node_modules/*" -not -path "*/.venv/*" -exec cat {} + 2>/dev/null | grep -cv '^[[:space:]]*$')
js_files=$(find . -name "*.js" -not -path "*/node_modules/*" -not -path "*/.venv/*" 2>/dev/null | wc -l)

# CSS
css_lines=$(find . -name "*.css" -not -path "*/node_modules/*" -not -path "*/.venv/*" -exec cat {} + 2>/dev/null | grep -cv '^[[:space:]]*$')
css_files=$(find . -name "*.css" -not -path "*/node_modules/*" -not -path "*/.venv/*" 2>/dev/null | wc -l)

# HTML
html_lines=$(find . -name "*.html" -not -path "*/node_modules/*" -not -path "*/.venv/*" -exec cat {} + 2>/dev/null | grep -cv '^[[:space:]]*$')
html_files=$(find . -name "*.html" -not -path "*/node_modules/*" -not -path "*/.venv/*" 2>/dev/null | wc -l)

# Markdown
md_lines=$(find . -name "*.md" -not -path "*/.venv/*" -not -path "*/node_modules/*" -exec cat {} + 2>/dev/null | grep -cv '^[[:space:]]*$')
md_files=$(find . -name "*.md" -not -path "*/.venv/*" -not -path "*/node_modules/*" 2>/dev/null | wc -l)

# 總計
total_lines=$((py_lines + js_lines + css_lines + html_lines))
total_files=$((py_files + js_files + css_files + html_files))

printf "%-15s %8s %8s\n" "類型" "檔案數" "行數"
echo "────────────────────────────────────"
printf "%-15s %8d %8d\n" "Python (.py)" "$py_files" "$py_lines"
printf "%-15s %8d %8d\n" "JavaScript (.js)" "$js_files" "$js_lines"
printf "%-15s %8d %8d\n" "CSS (.css)" "$css_files" "$css_lines"
printf "%-15s %8d %8d\n" "HTML (.html)" "$html_files" "$html_lines"
echo "────────────────────────────────────"
printf "%-15s %8d %8d\n" "程式碼總計" "$total_files" "$total_lines"
echo ""
printf "%-15s %8d %8d\n" "Markdown (.md)" "$md_files" "$md_lines"
echo ""
echo "統計時間: $(date '+%Y-%m-%d %H:%M:%S')"
