"""
Configuration package for RAG system.

This module provides centralized configuration management with backward compatibility.
All existing imports like 'from app.config import settings' will continue to work.
"""

# Import from the new location
from app.config.settings import Settings

# Create the settings singleton instance
settings = Settings()

# Export for backward compatibility
__all__ = ['settings', 'Settings']

# Optional: Add deprecation warning for direct imports (uncomment later)
# import warnings
# warnings.warn(
#     "Importing from app.config is deprecated. Use app.config.settings instead.",
#     DeprecationWarning,
#     stacklevel=2
# )