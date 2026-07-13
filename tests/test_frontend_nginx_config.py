from pathlib import Path


NGINX_CONFIG = Path(__file__).resolve().parents[1] / "frontend" / "nginx.conf"


def test_frontend_proxy_uses_docker_dns_and_preserves_api_uri() -> None:
    config = NGINX_CONFIG.read_text(encoding="utf-8")

    assert "resolver 127.0.0.11 valid=5s ipv6=off;" in config
    assert "resolver_timeout 2s;" in config
    assert "location /api/" in config
    assert "proxy_pass $upstream$request_uri;" in config
    assert "proxy_pass $upstream/api/;" not in config
    assert "proxy_read_timeout 300s;" in config


def test_frontend_health_proxy_uses_the_dynamic_upstream() -> None:
    config = NGINX_CONFIG.read_text(encoding="utf-8")

    assert "location /healthz" in config
    assert "proxy_pass $upstream/healthz;" in config
