"""
Backward compatibility module for config.

This file is kept for backward compatibility.
All imports from 'app.config' will be redirected to the new package structure.
New code should use 'from app.config.settings import settings' directly.
"""

# Re-export from the new location for backward compatibility
from app.config.settings import Settings, settings

# Export everything that was previously available
__all__ = ['Settings', 'settings']

# Note: This file will be deprecated in future versions
# Please update your imports to use app.config.settings directly