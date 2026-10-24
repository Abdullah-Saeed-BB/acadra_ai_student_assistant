"""Minimal settings required to start the MCP transport."""

from __future__ import annotations

import os
from typing import Literal

from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_TRUE_VALUES = {"1", "true", "yes", "on"}


def running_on_vercel() -> bool:
    """Vercel injects VERCEL into builds and every function invocation."""
    return bool(os.getenv("VERCEL"))


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _env_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseModel):
    transport: Literal["stdio", "streamable-http"] = "streamable-http"
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)
    stateless_http: bool = Field(default=False)
    json_response: bool = Field(default=False)
    allowed_hosts: list[str] = Field(default_factory=list)
    allowed_origins: list[str] = Field(default_factory=list)

    def transport_security(self) -> TransportSecuritySettings | None:
        """Build Host/Origin validation for the Streamable HTTP transport.

        FastMCP enables localhost-only DNS-rebinding protection when this is
        ``None``. Vercel terminates TLS and routes by Host, and preview and
        custom domains change without a code change, so an exact allowlist is
        opt-in there. Set ``STUDY_MCP_ALLOWED_HOSTS`` to enforce one.
        """
        if self.allowed_hosts or self.allowed_origins:
            return TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=self.allowed_hosts,
                allowed_origins=self.allowed_origins,
            )
        if running_on_vercel() or self.host not in _LOCAL_HOSTS:
            return TransportSecuritySettings(enable_dns_rebinding_protection=False)
        return None

    @classmethod
    def from_env(cls) -> Settings:
        on_vercel = running_on_vercel()
        return cls.model_validate(
            {
                "transport": os.getenv("STUDY_MCP_TRANSPORT", "streamable-http"),
                "host": os.getenv("STUDY_MCP_HOST", "127.0.0.1"),
                "port": os.getenv("STUDY_MCP_PORT", "8000"),
                "debug": _env_flag("STUDY_MCP_DEBUG"),
                # Stateless requests and JSON responses keep one MCP call
                # independent of the function instance that served the last
                # one, and avoid long-lived SSE streams on serverless hosts.
                "stateless_http": _env_flag("STUDY_MCP_STATELESS_HTTP", on_vercel),
                "json_response": _env_flag("STUDY_MCP_JSON_RESPONSE", on_vercel),
                "allowed_hosts": _env_list("STUDY_MCP_ALLOWED_HOSTS"),
                "allowed_origins": _env_list("STUDY_MCP_ALLOWED_ORIGINS"),
            }
        )
