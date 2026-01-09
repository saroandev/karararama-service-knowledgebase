"""
Orchestrators for document ingestion

This module provides:
- IngestOrchestrator: Coordinates document ingestion pipeline

Note: QueryOrchestrator has been moved to onedocs-service-orchestrator.
This service now only handles collection queries and document ingestion.
"""

from app.core.orchestrator.ingest_orchestrator import IngestOrchestrator, IngestResult

__all__ = [
    "IngestOrchestrator",
    "IngestResult"
]
