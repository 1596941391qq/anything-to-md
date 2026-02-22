"""
MCP Server for Anything-to-MD

Provides tools to convert files and directories to Markdown.
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Any

from mcp.server.fastmcp import FastMCP

from .converter import AnythingToMD, ConversionResult, BatchResult

# Create the MCP server
mcp = FastMCP("anything-to-md")


# Global converter instance
_converter: Optional[AnythingToMD] = None


def get_converter() -> AnythingToMD:
    """Get or create the converter instance"""
    global _converter
    if _converter is None:
        enable_plugins = os.getenv("ANYTHING_TO_MD_ENABLE_PLUGINS", "").lower() in ("true", "1", "yes")
        _converter = AnythingToMD(enable_plugins=enable_plugins)
    return _converter


@mcp.tool()
async def convert_file_to_markdown(
    file_path: str,
    output_dir: Optional[str] = None,
    output_name: Optional[str] = None
) -> str:
    """
    Convert a single file to Markdown format.
    
    Supports: PDF, Word, Excel, PowerPoint, Images (OCR), Audio, Video, HTML, EPUB
    
    Args:
        file_path: Path to the file to convert (local path or URL)
        output_dir: Directory to save the output (optional, defaults to same directory)
        output_name: Name for the output file (optional, defaults to original_name.md)
    
    Returns:
        JSON string with conversion result including markdown content
    """
    converter = get_converter()
    
    source = Path(file_path)
    out_dir = Path(output_dir) if output_dir else None
    
    result = converter.convert_file(
        source=source,
        output_dir=out_dir,
        output_name=output_name
    )
    
    return json.dumps({
        "success": result.success,
        "source": str(result.source_path),
        "target": str(result.target_path) if result.target_path else None,
        "markdown": result.markdown,
        "error": result.error,
        "skipped": result.skipped,
        "skip_reason": result.skip_reason
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def convert_directory_to_markdown(
    source_dir: str,
    target_dir: str,
    preserve_structure: bool = True,
    skip_patterns: Optional[List[str]] = None
) -> str:
    """
    Convert all files in a directory to Markdown.
    
    Recursively processes all convertible files and creates corresponding .md files
    in the target directory, optionally preserving the original directory structure.
    
    Args:
        source_dir: Source directory to process
        target_dir: Target directory for output markdown files
        preserve_structure: Keep the original directory structure (default: True)
        skip_patterns: Additional glob patterns for files to skip
    
    Returns:
        JSON string with batch conversion results
    """
    converter = get_converter()
    
    # Add custom skip patterns if provided
    if skip_patterns:
        converter = AnythingToMD(skip_patterns=skip_patterns)
    
    result = converter.convert_directory(
        source_dir=Path(source_dir),
        target_dir=Path(target_dir),
        preserve_structure=preserve_structure
    )
    
    # Prepare results for JSON serialization
    results_list = []
    for r in result.results:
        results_list.append({
            "source": str(r.source_path),
            "target": str(r.target_path) if r.target_path else None,
            "success": r.success,
            "skipped": r.skipped,
            "skip_reason": r.skip_reason,
            "error": r.error
        })
    
    return json.dumps({
        "source_dir": str(result.source_dir),
        "target_dir": str(result.target_dir),
        "total_files": result.total_files,
        "converted": result.converted,
        "skipped": result.skipped,
        "failed": result.failed,
        "success_rate": result.success_rate,
        "results": results_list
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def convert_youtube_to_markdown(
    url: str,
    output_path: Optional[str] = None
) -> str:
    """
    Convert a YouTube video to Markdown transcript.
    
    Extracts the transcript from a YouTube video and converts it to
    a structured Markdown format with timestamps.
    
    Args:
        url: YouTube video URL
        output_path: Path to save the output (optional)
    
    Returns:
        JSON string with conversion result including transcript
    """
    converter = get_converter()
    
    out_path = Path(output_path) if output_path else None
    result = converter.convert_youtube(url=url, output_path=out_path)
    
    return json.dumps({
        "success": result.success,
        "source": str(result.source_path),
        "target": str(result.target_path) if result.target_path else None,
        "markdown": result.markdown,
        "error": result.error
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_supported_formats() -> str:
    """
    Get list of supported file formats for conversion.
    
    Returns:
        JSON string with categorized list of supported formats
    """
    formats = {
        "documents": [
            ".pdf", ".docx", ".doc", ".xlsx", ".xls", 
            ".pptx", ".ppt", ".odt", ".ods", ".odp"
        ],
        "web": [
            ".html", ".htm", ".xhtml", ".url"
        ],
        "ebooks": [
            ".epub", ".mobi"
        ],
        "data": [
            ".csv", ".tsv", ".json", ".xml"
        ],
        "images": [
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", 
            ".tiff", ".webp"
        ],
        "audio": [
            ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"
        ],
        "video": [
            ".mp4", ".mkv", ".avi", ".mov", ".webm"
        ],
        "code": [
            ".py", ".js", ".ts", ".java", ".c", ".cpp",
            ".go", ".rs", ".rb", ".php"
        ],
        "other": [
            ".rtf", ".txt", ".ipynb", ".msg"
        ],
        "urls": [
            "youtube.com/*", "youtu.be/*", "wikipedia.org/*"
        ]
    }
    
    return json.dumps(formats, indent=2)


def main():
    """Main entry point for the MCP server"""
    mcp.run()


def create_server():
    """Factory function for creating the server instance"""
    return mcp


if __name__ == "__main__":
    main()
