# CDN 部署與資源快取建議（ChingTech OS）

目標：將靜態資源（CSS/JS/Font/Images）透過 CDN 提供以加速全球用戶存取、減少延遲並提高 LCP 與 Speed Index。

建議概要
- CDN 選項：Cloudflare（簡易）、AWS CloudFront（細緻控制）、Google Cloud CDN、Fastly
- 主要策略：將 `frontend/dist/` 輸出上傳至 CDN（或透過 origin 指向 S3/Storage），並正確設定 Cache-Control/Immutable。

最佳實踐
1. 版本化資源
   - 使用 hashed filenames（已由 build 工具產出，如 `assets/main-<hash>.js`），搭配長期快取 `Cache-Control: public, max-age=31536000, immutable`

2. 靜態資源快取策略（範例）
   - CSS/JS/Fonts/Images: `Cache-Control: public, max-age=31536000, immutable`
   - HTML (index.html, login.html, public.html): `Cache-Control: no-cache`（保證 HTML 更新後能快速反映）
   - API 回應（敏感資訊或需即時）：`Cache-Control: private, no-store`

3. HTTP Header 範例（Nginx）

```nginx
location /assets/ {
  add_header Cache-Control "public, max-age=31536000, immutable";
}

location ~* \.(html)$ {
  add_header Cache-Control "no-cache";
}
```

4. 使用 CDN 的 Edge Caching 與 Purge
   - 部署後每次 build，呼叫 CDN 的 Purge API 以移除舊資源（或僅針對 index.html），避免長期快取造成舊資源殘留問題。

5. 圖片與字型
   - 圖片：上傳 webp/avif 到 CDN，並支援 content negotiation（Accept header），或透過 `picture` 元素提供 webp source
   - 字型：設定 `crossorigin` 並 `Cache-Control` 最長時間，同時在 font-face 使用 `font-display: swap`。

6. SSL/TLS 與 HTTP/2
   - 啟用 TLS 1.2+，支援 HTTP/2，利用多路複用減少請求延遲

7. Analytics 與 實驗
   - 設定 CDN Edge 的命中率監控，定期檢視 LCP/SI 的變化

部署流程建議
1. Build pipeline（CI）產生 frontend/dist
2. 上傳 artifacts 到 S3 或 CDN 的 object storage
3. 透過 CDN API（CloudFront invalidation 或 Cloudflare purge）刷新 index.html 或新發布的資源
4. 通知 Deploy 通道（Slack/PR）發布完成

工具與 CLI 範例
- AWS CLI 上传至 S3
```bash
aws s3 sync frontend/dist s3://<bucket-name>/ --delete --acl public-read
aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/index.html"
```
- Cloudflare Purge
```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/purge_cache" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{"files":["https://example.com/index.html"]}'
```

結語
- 建議先於 Staging 環境測試 CDN 行為，再切換 Production
- 若需，我可協助產生 CI pipeline 的 S3/CloudFront 上傳步驟範例（GitHub Actions）並建立 PR
