# Design: Skill 生態系統完善

## 架構概覽

```
                    ┌─────────────────┐
                    │   Frontend JS   │
                    │  agent-settings │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   FastAPI API   │
                    │  api/skills.py  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼────────┐ ┌──▼───┐ ┌────────▼────────┐
     │  ClawHubClient  │ │ ENV  │ │  SkillManager   │
     │  (httpx async)  │ │ CRUD │ │  (singleton)    │
     └────────┬────────┘ └──┬───┘ └────────┬────────┘
              │             │              │
     ┌────────▼────────┐ ┌──▼───┐ ┌────────▼────────┐
     │  ClawHub REST   │ │  DB  │ │  skills/ 目錄   │
     │  API (外部)     │ │      │ │  (_meta.json)   │
     └─────────────────┘ └──────┘ └─────────────────┘
```

## 檔案結構

### 新增檔案
```
backend/src/ching_tech_os/
  services/clawhub_client.py    # ClawHubClient class (httpx)
  services/skill_env.py         # ENV 加密/解密/CRUD
  
backend/migrations/versions/
  00X_skill_env.py              # Alembic migration

skills/printer/
  SKILL.md                      # Printer skill 定義
```

### 修改檔案
```
backend/src/ching_tech_os/
  api/skills.py                 # API 端點：用 ClawHubClient 替換 CLI，新增 ENV API
  skills/__init__.py            # SkillManager：trust level、status 計算
  services/mcp/skill_script_tools.py  # ENV allowlist injection
  main.py                       # 註冊新路由（如需要）

frontend/
  js/agent-settings.js          # 搜尋卡片升級、ENV UI、狀態燈號、權限引導
  css/agent-settings.css        # 狀態燈號、ENV 表單樣式

backend/pyproject.toml          # 新增 httpx、cryptography
scripts/install-service.sh      # 移除/註解 clawhub CLI 安裝
```

## ClawHubClient 設計

```python
# services/clawhub_client.py
class ClawHubClient:
    BASE_URL = "https://clawhub.ai/api/v1"
    
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(connect=5, read=30, pool=5),
            follow_redirects=False,  # SSRF 防護
        )
    
    async def search(self, query: str, limit: int = 20) -> list[dict]
    async def get_skill(self, slug: str) -> dict
    async def get_versions(self, slug: str) -> list[dict]
    async def download_zip(self, slug: str, version: str) -> bytes
    async def download_and_extract(self, slug: str, version: str, dest_dir: Path) -> dict
    
    # ZIP 處理
    def _validate_zip(self, data: bytes) -> None  # 大小限制 10MB
    def _extract_safe(self, data: bytes, dest: Path) -> None  # zip slip 防護
    def _write_meta(self, dest: Path, slug: str, version: str, owner: str) -> None
```

## ENV 管理設計

```python
# services/skill_env.py
class SkillEnvManager:
    def __init__(self, db_pool, secret_key: str):
        self._fernet = Fernet(secret_key)
    
    async def list_env(self, scope: str) -> list[dict]  # key + mask only
    async def get_env(self, scope: str) -> dict[str, str]  # 解密，server-side only
    async def set_env(self, scope: str, key: str, value: str) -> None
    async def delete_env(self, scope: str, key: str) -> None
    
    def resolve_env(self, skill_slug: str, declared_keys: list[str]) -> dict[str, str]
        # os.environ → _global → per-skill，按 allowlist 過濾
    
    @staticmethod
    def mask_value(value: str) -> str:
        # "sk-1234567890abcdef" → "sk-1****cdef"
```

## 權限與狀態

```python
# skills/__init__.py (SkillManager 擴充)
def get_skill_status(self, name: str) -> dict:
    """計算 skill 健康狀態"""
    skill = self.get_skill(name)
    meta = self._read_meta(name)  # _meta.json
    
    trust = "builtin" if meta is None else ("private" if meta.get("owner") == admin_handle else "community")
    
    # 檢查必填 ENV
    required_env = skill.get("metadata", {}).get("openclaw", {}).get("requires", {}).get("env", [])
    missing_env = [e["name"] for e in required_env if e.get("required") and not env_manager.has_key(name, e["name"])]
    
    if missing_env:
        status = "warning"
    elif skill loading failed:
        status = "error"
    else:
        status = "ok"
    
    return {"trust": trust, "status": status, "missing_env": missing_env}
```

## 前端設計

### 搜尋結果卡片（Phase 1）
```html
<div class="skill-hub-result-item">
  <img class="skill-hub-avatar" src="{owner.image}" />
  <div class="agent-list-item-info">
    <div class="agent-list-item-name">{displayName}</div>
    <div class="skill-hub-author">by {owner.handle}</div>
    <div class="agent-list-item-model">{summary 截斷 2 行}</div>
    <div class="skill-list-item-meta">
      <span class="skill-badge">{version}</span>
      <span class="skill-badge">⭐ {stars}</span>
      <span class="skill-badge">{relativeTime}</span>
    </div>
  </div>
  <div class="skill-hub-result-actions">
    <button data-action="preview-skill">預覽</button>
    <button data-action="install-skill">安裝</button>
  </div>
</div>
```

### 狀態燈號（Phase 3）
```html
<div class="skill-list-item">
  <span class="skill-status-dot skill-status-{ok|warning|error}"></span>
  <div class="agent-list-item-info">...</div>
</div>
```

### ENV 設定 section（Phase 2）
```html
<div class="skill-env-section">
  <h4>環境變數</h4>
  <div class="skill-env-row">
    <label>GEMINI_API_KEY <span class="required">*</span></label>
    <input type="password" placeholder="輸入 API Key" />
    <span class="skill-env-status">●●●●●●</span>
    <button>儲存</button>
  </div>
</div>
```

## 遷移計劃

1. Phase 1 PR: ClawHubClient + 前端搜尋升級 + _meta.json
2. Phase 2 PR: skill_env table + ENV API + 前端 ENV UI + allowlist
3. Phase 3 PR: 權限預設 + 信任等級 + 狀態燈號 + 內建 skill requires_app 補齊
4. Phase 4 PR: Printer skill 化 + 從硬編碼移除
