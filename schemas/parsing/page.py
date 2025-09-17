"""
Page-related schemas for document parsing
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class PageContent:
    """Data class for page content"""
    page_number: int
    text: str
    metadata: Dict[str, Any]