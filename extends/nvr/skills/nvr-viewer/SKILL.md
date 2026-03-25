---
name: nvr-viewer
description: NVR 即時監控畫面 — 16 路攝影機快照檢視
license: proprietary
compatibility: ctos
allowed-tools: ""
metadata:
  ctos:
    requires_app: nvr-viewer
    requires:
      env:
        - NVR_HOST
        - NVR_ONVIF_USER
        - NVR_ONVIF_PASSWORD
    mcp_servers: ""
  contributes:
    app:
      id: nvr-viewer
      name: 監控畫面
      icon: video
      loader:
        src: frontend/nvr-app.js
        globalName: NVRViewerApp
      css: frontend/nvr-app.css
    permissions:
      nvr-viewer:
        default: true
        display_name: 監控畫面
    api_routes:
      - module: api.nvr_snapshot
        prefix: /api/nvr
---

# NVR 即時監控畫面

透過 ONVIF 快照顯示 16 路攝影機即時畫面。
支援 4x4 網格檢視和單路放大檢視。
