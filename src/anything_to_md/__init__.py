"""
Anything-to-MD: Convert any file to LLM-ready Markdown

Combines Microsoft MarkItDown with Claude Code Skill capabilities
for comprehensive document processing.
"""

__version__ = "0.1.0"

from .converter import AnythingToMD

__all__ = ["AnythingToMD", "__version__"]
