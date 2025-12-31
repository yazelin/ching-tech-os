# 知識庫使用指南

這是一個範例知識庫文件，說明如何建立和管理知識庫內容。

## 檔案格式

每個知識條目是一個 Markdown 檔案，存放在 `data/knowledge/entries/` 目錄下。

### 檔名規則

```
kb-{序號}-{標題}.md
```

例如：
- `kb-001-getting-started.md`
- `kb-002-api-reference.md`

## 內容結構

建議的文件結構：

```markdown
# 標題

簡短描述這個知識條目的內容。

## 章節 1

內容...

## 章節 2

內容...

## 參考資料

- [連結 1](https://example.com)
- [連結 2](https://example.com)
```

## 附件

如果需要附加圖片或檔案，請放在 `data/knowledge/assets/` 目錄下。

在 Markdown 中引用：
```markdown
![圖片說明](assets/images/my-image.png)
```

## 索引檔案

`data/knowledge/index.json` 用於記錄所有知識條目的元資料，系統會自動更新。
