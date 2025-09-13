"""
Custom JSON Response for proper UTF-8 handling
"""
from typing import Any
from fastapi.responses import JSONResponse
import json


class CustomJSONResponse(JSONResponse):
    """Custom JSON response class with UTF-8 support for Turkish characters"""

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(" , ", " : ")
        ).encode("utf-8")