# Design: add-circuits-mount

## 掛載架構

現有：
```
/mnt/nas/ctos     → //NAS_HOST/擎添開發/ching-tech-os     (讀寫)
/mnt/nas/projects → //NAS_HOST/擎添共用區/在案資料分享      (唯讀)
```

新增：
```
/mnt/nas/circuits → //NAS_HOST/擎添線路圖/圖檔             (唯讀)
```

## 搜尋來源架構

### 現狀
`search_nas_files` 硬寫 `settings.projects_mount_path`，只搜單一路徑，結果路徑為 `shared://相對路徑`。

### 新設計
引入「搜尋來源」字典，定義 shared zone 下的子來源：

```python
# config.py
circuits_mount_path: str = _get_env("CIRCUITS_MOUNT_PATH", "/mnt/nas/circuits")

# search_nas_files 內部
SHARED_SEARCH_SOURCES = {
    "projects": settings.projects_mount_path,   # /mnt/nas/projects
    "circuits": settings.circuits_mount_path,    # /mnt/nas/circuits
}
```

搜尋結果路徑格式改為帶來源名稱：
- `shared://projects/亦達光學/Layout/xxx.pdf`
- `shared://circuits/線路圖A/xxx.dwg`

### 未來權限擴充點
```python
# 未來實作時，在搜尋前過濾來源：
# allowed_sources = filter_by_user_permission(user_id, SHARED_SEARCH_SOURCES)
# 目前直接使用全部來源
```

## path_manager 變更

`SHARED` zone 目前對應單一 `projects_mount_path`。改為支援子路徑解析：

```python
# shared://projects/xxx → /mnt/nas/projects/xxx
# shared://circuits/xxx → /mnt/nas/circuits/xxx
# shared://xxx（舊格式，無子來源）→ /mnt/nas/projects/xxx（向後相容）
```

`_zone_mounts` 的 `SHARED` 改為字典：
```python
self._shared_mounts = {
    "projects": settings.projects_mount_path,
    "circuits": settings.circuits_mount_path,
}
```

## 向後相容
- 現有 `shared://亦達光學/...` 格式（無 `projects/` 前綴）須繼續支援
- 判斷邏輯：如果 `shared://` 後的第一段不是已知來源名稱，則 fallback 到 `projects`
