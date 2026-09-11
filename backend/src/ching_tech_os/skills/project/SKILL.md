---
name: project
description: 專案管理（find_project／get_project／create_task 等 MCP 工具）
metadata:
  ctos:
    requires_app: project-management
---

【專案管理】
專案、里程碑與任務在 CTOS 自己的資料庫（`projects`／`project_members`／
`milestones`／`tasks`），2026-09 起不再走 ERPNext。工具在
`services/mcp/project_tools.py`，SQL 在 `services/project.py`。

■ 查詢
- `find_project(query, status?)`：名稱或客戶模糊搜尋，回候選清單。
  `status` 只能是 planning／active／on_hold／completed／cancelled。
- `get_project(project_id | name)`：明細＝主檔＋進度＋成員＋里程碑（含 `is_overdue`）
  ＋任務＋綁定群組＋知識條目數。
- `list_overdue_milestones()`：逾期里程碑清單（依到期日升冪，最多 20 筆）
  與進行中專案數。逾期＝到期日已過、里程碑未完成，且專案還是 active。
- `list_tasks(project, status?, assignee?)`：任務清單，狀態只有 todo／doing／done。

■ 寫入（只有專案成員或管理員能做）
- `create_task(project, title, assignee?, milestone?, due_date?)`
- `update_task(project, task, fields)`：`fields` 例 `{"status": "done"}`、
  `{"assignee": "亞澤"}`、`{"due_date": "2026-10-01"}`；
  送 `{"assignee": null}` 是拿掉負責人、`{"milestone": null}` 是脫離里程碑。
  欄位名稱拼錯會回「沒有可更新的欄位」，不會假裝改好了。
- `create_milestone(project, name, due_date)`、`complete_milestone(project, milestone)`
- `add_project_member(project, user)`：`user` 吃 username 或顯示名稱。

被權限擋下來時工具回 `{"ok": false, "error": "只有專案成員能編輯"}`，
照實告訴使用者，不要換個講法重試。

■ 三條規矩
1. **先 find 再寫**：改任務前先 `find_project`／`list_tasks` 確認是哪一個專案、
   哪一筆任務。
2. **多個候選要問人**：專案、任務、里程碑、使用者都吃名稱，解析不唯一時工具回
   `{"need_confirmation": true, "candidates": [...]}`（最多三個），把候選唸給使用者挑，
   不要自己選第一個；再帶 `"more": true` 表示候選被截掉了，
   請使用者把名字講具體一點；零命中回 `{"not_found": true}`。
3. **建立專案不走工具**：開新專案、刪專案是管理員在網頁做的事，
   請使用者到 os.ching-tech.com/projects（單一專案網址是
   os.ching-tech.com/projects/<專案 id>，可以直接分享）。

■ 相關的東西在哪裡
- 群組綁定的專案會影響知識庫的 scope：群組已綁定專案時，`add_note` 建立的
  知識會落在該專案（專案成員可編輯）。這一段用知識庫的工具處理，不用專案工具。
- 專案相關的廠商、採購單可以從往來對象查：`get_party` 的回應含「相關專案」。
- 專案圖面與檔案在 NAS，用 `search_nas_files` 找。
