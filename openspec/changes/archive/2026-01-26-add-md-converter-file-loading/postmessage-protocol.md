# PostMessage Protocol for md2ppt / md2doc

CTOS 與外部 App（md2ppt / md2doc）之間的 postMessage 通訊協議。

## 訊息格式

### 1. Ready 訊號（外部 App → CTOS）

外部 App 初始化完成後，發送 ready 訊號告知 CTOS 可以開始傳送檔案內容。

```javascript
{
  type: 'ready',
  appId: 'md2ppt'  // 或 'md2doc'
}
```

### 2. Load File 訊息（CTOS → 外部 App）

CTOS 傳送檔案內容給外部 App。

```javascript
{
  type: 'load-file',
  filename: 'example.md2ppt',  // 檔案名稱
  content: '# Markdown 內容...'  // 檔案內容（純文字）
}
```

## 外部 App 實作範例

在 md2ppt / md2doc 的 JavaScript 中加入以下程式碼：

```javascript
// 監聽來自 CTOS 的訊息
window.addEventListener('message', function(event) {
  const { data } = event;

  // 忽略非物件訊息
  if (!data || typeof data !== 'object') return;

  // 處理 load-file 訊息
  if (data.type === 'load-file') {
    console.log('收到檔案:', data.filename);

    // TODO: 將 data.content 載入到編輯器
    // 例如: editor.setValue(data.content);

    loadContentToEditor(data.content, data.filename);
  }
});

// 發送 ready 訊號（在 App 初始化完成後呼叫）
function sendReadySignal() {
  if (window.parent !== window) {
    window.parent.postMessage({
      type: 'ready',
      appId: 'md2ppt'  // md2doc 請改為 'md2doc'
    }, '*');
    console.log('已發送 ready 訊號');
  }
}

// 在 App 初始化完成後呼叫
// 例如: document.addEventListener('DOMContentLoaded', sendReadySignal);
// 或在編輯器初始化完成後呼叫
```

## 時序圖

```
CTOS                          外部 App (iframe)
  |                                 |
  |  -------- 載入 iframe --------> |
  |                                 |
  |                                 | (初始化完成)
  |                                 |
  |  <-- { type: 'ready' } -------- |
  |                                 |
  |  -- { type: 'load-file' } ----> |
  |                                 |
  |                                 | (載入內容)
  |                                 |
```

## 注意事項

1. **超時機制**：CTOS 會在 iframe 載入後 3 秒內等待 ready 訊號。如果超時，會直接嘗試傳送檔案內容。

2. **跨域安全**：postMessage 使用 `'*'` 作為 targetOrigin，在生產環境中建議改為指定的 origin。

3. **重複開啟**：如果使用者在同一個視窗中開啟不同檔案，外部 App 會收到新的 `load-file` 訊息，應該用新內容取代舊內容。
