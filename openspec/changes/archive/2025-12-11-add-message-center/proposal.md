# Proposal: add-message-center

## Summary

新增訊息中心功能，提供集中式的訊息、日誌、登入記錄管理系統。支援安全審計、問題除錯、系統監控等需求。

## Motivation

目前系統缺乏集中式的訊息管理機制：
- 伺服器日誌分散在檔案中，難以查詢
- 登入記錄只有 `last_login_at`，缺乏完整歷史
- 應用程式通知是即時的 Toast，沒有持久化
- 無法進行安全審計或異常行為追蹤

訊息中心將成為系統的核心監控與審計設施，為未來的防駭、除錯、合規需求打下基礎。

## Scope

### In Scope
- 訊息資料模型與資料庫設計
- 訊息儲存 API（寫入日誌、事件、通知）
- 訊息查詢 API（搜尋、過濾、分頁）
- 登入記錄完整追蹤（IP、User-Agent、GeoIP、裝置指紋）
- 前端訊息中心視窗應用程式
- WebSocket 即時推送新訊息
- 訊息保留 1 年，自動清理過期資料

### Out of Scope
- 日誌匯出（CSV、JSON）- 後續擴充
- 日誌分析儀表板 - 後續擴充
- 告警規則引擎 - 後續擴充
- 與外部 SIEM 系統整合 - 後續擴充

## Affected Specs

| Spec | Operation | Description |
|------|-----------|-------------|
| message-center | CREATE | 新增訊息中心完整規格 |
| backend-auth | MODIFY | 擴充登入記錄追蹤 |

## Design Decisions

見 `design.md`

## Dependencies

- PostgreSQL 資料庫（已存在）
- Socket.IO（已整合）
- GeoIP2 資料庫（新增，用於地理位置解析）

## Risks

1. **資料量成長**：訊息量可能快速成長
   - 緩解：分區表 + 自動清理過期資料

2. **效能影響**：頻繁寫入日誌可能影響效能
   - 緩解：非同步寫入 + 批次處理

3. **GeoIP 準確性**：IP 地理位置可能不準確
   - 緩解：標註為「估計位置」，定期更新資料庫
