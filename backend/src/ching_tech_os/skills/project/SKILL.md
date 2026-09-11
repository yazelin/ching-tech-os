---
name: project
description: 專案管理（新前端 os.ching-tech.com/projects）
metadata:
  ctos:
    requires_app: project-management
---

【專案管理】
專案、里程碑與任務在 CTOS 自己的資料庫（`projects`／`project_members`／
`milestones`／`tasks`），2026-09 起不再走 ERPNext。

■ 目前沒有專案的 MCP 工具
這個模組只有 REST API 與網頁，沒有可以呼叫的工具。使用者要查專案進度、
里程碑、任務或成員時，請引導他到新前端：

  os.ching-tech.com/projects

單一專案的網址是 os.ching-tech.com/projects/<專案 id>，可以直接分享。

■ 相關的東西在哪裡
- 群組綁定的專案會影響知識庫的 scope：群組已綁定專案時，`add_note` 建立的
  知識會落在該專案（專案成員可編輯）。這一段用知識庫的工具處理，不用專案工具。
- 專案相關的廠商、採購單可以從往來對象查：`get_party` 的回應含「相關專案」。
- 專案圖面與檔案在 NAS，用 `search_nas_files` 找。
