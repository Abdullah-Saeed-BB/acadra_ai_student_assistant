"""Minimal settings required to start the MCP transport."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    transport: Literal["stdio", "streamable-http"] = "stdio"
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)

    @classmethod
    def from_env(cls) -> Settings:
        return cls.model_validate(
            {
                "transport": os.getenv("STUDY_MCP_TRANSPORT", "stdio"),
                "host": os.getenv("STUDY_MCP_HOST", "127.0.0.1"),
                "port": os.getenv("STUDY_MCP_PORT", "8000"),
                "debug": os.getenv("STUDY_MCP_DEBUG", "True"),
            }
        )
