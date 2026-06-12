# Friday Public Deployment Report

## Public URL

https://friday.austontatious.dev

## Runtime Topology

Cloudflare Tunnel -> local frontend/proxy :18080 -> backend container :9001 -> host gateway :8130 -> model backends :8174/:8176

## Validation

- **Local frontend/proxy (127.0.0.1:18080)**: **PASS** (same-origin安全路由, 代理成功转发 `/api/*` 请求)
- **Local backend (127.0.0.1:9001)**: **PASS** (`readyz` 状态健康, 通信无阻)
- **Tunnel Routing**: **PASS** (Programmatically updated Cloudflare Tunnel `c88b35a7-dd36-4fd5-a071-a70dd3537942` configuration to version 13 to route `friday.austontatious.dev` to `http://localhost:18080`).
- **DNS Resolution**: **PENDING MANUAL DNS RECORD** (Cloudflare API tokens lack DNS edit permission on `austontatious.dev`).
- **Public HTTPS**: **PENDING DNS**
- **Public direct chat**: **PENDING DNS**
- **Public Althing chat**: **PENDING DNS**

## Security Notes

- **Model Gateway (8130)**: Not exposed publicly (protected by host firewall INPUT rules, only accessible inside the container/local networks).
- **Model Backends (8174 / 8176)**: Not exposed publicly.
- **Muninn Memory (18000)**: Not exposed publicly.
- **Auth/Rate-limit Status**: Missing. Public route is reachable but not production-hardened. Do not treat it as private assistant infrastructure until auth/rate limits are added.

## Cloudflare Details

- **Tunnel ID**: `c88b35a7-dd36-4fd5-a071-a70dd3537942` (managed tunnel running via `cloudflared.service` systemd unit)
- **Service Target**: `http://localhost:18080` (maps to frontend proxy same-origin port)
- **Required Action**:
  The Cloudflare API Token lacks DNS modification permissions on `austontatious.dev`. Please manually add the DNS CNAME record in your Cloudflare dashboard:
  - **Name/Subdomain**: `friday`
  - **Domain**: `austontatious.dev`
  - **Type**: `CNAME`
  - **Content/Target**: `c88b35a7-dd36-4fd5-a071-a70dd3537942.cfargotunnel.com`
  - **Proxy Status**: `Proxied` (Orange Cloud enabled)
  
  Once the DNS CNAME record is added, `https://friday.austontatious.dev` will immediately resolve and route to the local frontend proxy port, securing same-origin chat routing.
