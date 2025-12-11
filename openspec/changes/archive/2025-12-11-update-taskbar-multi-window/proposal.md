# Change: 更新視窗管理與 Taskbar 多視窗支援

## Why
1. **Taskbar 多視窗問題**：目前 Taskbar 假設每個應用程式只有一個視窗，但終端機等應用程式已支援多開，點擊行為和運行指示器需要調整。
2. **缺少視窗 Snap 功能**：現代桌面系統都支援拖曳視窗到螢幕邊緣自動調整大小的功能，提升多視窗工作效率。

## What Changes

### Taskbar 多視窗支援
- 修改 Taskbar 點擊行為：當應用程式有多個視窗時，顯示視窗選單讓使用者選擇
- 修改運行指示器：多個視窗時顯示多個小點

### 視窗 Snap 功能
- **左/右邊緣**：拖曳視窗到左或右邊緣，自動調整為 1/2 桌面寬度並貼齊該側
- **四個角落**：拖曳視窗到四個角落，自動調整為 1/4 桌面大小並貼齊對應角
- **正上緣**：拖曳視窗到正上緣，自動最大化

## Impact
- 修改 spec: `web-desktop` (Taskbar requirement, 新增 Window Snap requirement)
- 修改: `frontend/js/taskbar.js` - 多視窗選單
- 修改: `frontend/js/window.js` - Snap 邏輯
- 修改: `frontend/css/taskbar.css` - 視窗選單樣式
- 修改: `frontend/css/window.css` - Snap 預覽樣式
