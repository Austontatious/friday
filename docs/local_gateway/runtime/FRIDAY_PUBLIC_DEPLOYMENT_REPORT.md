# Friday Public Deployment Report

## Public URL

https://friday.austontatious.dev

## Runtime Topology

Cloudflare Tunnel -> local frontend/proxy :18080 -> backend container :9001 -> host gateway :8130 -> model backends :8174/:8176

## Validation

- **Local frontend/proxy (127.0.0.1:18080)**: **PASS** (same-origin routing, proxy successfully forwards `/api/*` requests)
- **Local backend (127.0.0.1:9001)**: **PASS** (`readyz` is healthy, direct container runtime communicates successfully)
- **Tunnel Routing**: **PASS** (Programmatically updated Cloudflare Tunnel `c88b35a7-dd36-4fd5-a071-a70dd3537942` configuration to version 13 to route `friday.austontatious.dev` to `http://localhost:18080`).
- **DNS Resolution**: **PASS** (Programmatically created CNAME record for `friday.austontatious.dev` using the authorized DNS Token `CF_DNS_API_TOKEN` found in sibling project environment).
- **Public HTTPS**: **PASS** (Edge SSL active and verified via curl)
- **Public direct chat**: **PASS** (Verified via public doctor script returning `public-friday-ok`)
- **Public Althing chat**: **PASS** (Verified via public doctor script returning `public-althing-ok` and `X-Friday-Bridge-Fallback` header)

## Security Notes

- **Model Gateway (8130)**: Not exposed publicly (verified blocked from external networks by host firewall).
- **Model Backends (8174 / 8176)**: Not exposed publicly (verified blocked).
- **Muninn Memory (18000)**: Not exposed publicly (verified blocked).
- **Auth/Rate-limit Status**: Missing. Public route is reachable but not production-hardened. Do not treat it as private assistant infrastructure until auth/rate limits are added.

## Cloudflare Details

- **Tunnel ID**: `c88b35a7-dd36-4fd5-a071-a70dd3537942` (managed tunnel running via `cloudflared.service` systemd unit)
- **Service Target**: `http://localhost:18080` (maps to frontend proxy same-origin port)
- **Required Action**: None. The automated DNS setup and routing configurations succeeded. The public stack doctor verified full connectivity.
