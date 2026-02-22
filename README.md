# Anything-to-MD

**Convert any file to clean, LLM-ready Markdown**

A unified solution combining Microsoft MarkItDown's document processing with Claude Code Skill capabilities for comprehensive file-to-Markdown conversion.

## Features

- **50+ File Formats**: PDF, Word, Excel, PowerPoint, Images (OCR), Audio, Video, HTML, EPUB
- **YouTube Support**: Extract transcripts from YouTube videos
- **Batch Processing**: Convert entire directories while preserving structure
- **MCP Server**: Native Model Context Protocol support for Claude integration
- **CLI Tool**: Powerful command-line interface for automation

## Installation

```bash
# Using pip
pip install anything-to-md

# Using uv (recommended)
uv pip install anything-to-md

# From source
git clone https://github.com/yourusername/anything-to-md.git
cd anything-to-md
pip install -e ".[all]"
```

## Quick Start

### Command Line

```bash
# Convert a single file
anything-to-md file document.pdf -o ./output

# Convert entire directory
anything-to-md dir ./documents ./markdown --report

# Extract YouTube transcript
anything-to-md youtube "https://youtube.com/watch?v=xxx"

# List supported formats
anything-to-md formats
```

### MCP Server

```bash
# Start the MCP server
anything-to-md-mcp

# Or with Python
python -m anything_to_md.mcp_server
```

### Python API

```python
from anything_to_md import AnythingToMD

# Initialize converter
converter = AnythingToMD()

# Convert single file
result = converter.convert_file("document.pdf", output_dir="./output")
print(result.markdown)

# Convert directory
batch_result = converter.convert_directory(
    source_dir="./documents",
    target_dir="./markdown",
    preserve_structure=True
)
print(f"Converted {batch_result.converted} files")

# Extract YouTube transcript
yt_result = converter.convert_youtube("https://youtube.com/watch?v=xxx")
print(yt_result.markdown)
```

## Supported Formats

| Category | Formats |
|----------|---------|
| Documents | PDF, DOCX, XLSX, PPTX, ODT, ODS, ODP, DOC, XLS, PPT |
| Web | HTML, HTM, XHTML |
| eBooks | EPUB, MOBI |
| Data | CSV, TSV, JSON, XML |
| Images | PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP (with OCR) |
| Audio | MP3, WAV, M4A, FLAC, OGG, AAC |
| Video | MP4, MKV, AVI, MOV, WEBM |
| URLs | YouTube, Wikipedia, RSS feeds |
| Other | RTF, TXT, IPYNB, MSG, ZIP |

## Configuration

### Environment Variables

```bash
# Enable MarkItDown plugins
export ANYTHING_TO_MD_ENABLE_PLUGINS=true
```

### Claude Code Integration

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "anything-to-md": {
      "command": "uvx",
      "args": ["anything-to-md-mcp"]
    }
  }
}
```

### AionUI Integration

Add to AionUI configuration:

```yaml
mcp_servers:
  - name: anything-to-md
    command: python -m anything_to_md.mcp_server
    enabled: true
```

## CLI Reference

```
anything-to-md <command> [options]

Commands:
  file <path>           Convert a single file
  dir <source> <target> Convert all files in a directory
  youtube <url>         Extract YouTube transcript
  formats               List supported formats

Options:
  -o, --output-dir DIR  Output directory
  -n, --output-name NAME Output filename
  -p, --print-output    Print output to console
  --flat                Use flat directory structure
  --skip PATTERN        Skip files matching pattern
  --report              Generate conversion report
  --version             Show version
  --help                Show help
```

## Examples

### Convert Research Papers

```bash
anything-to-md dir ./papers ./papers-md --skip "draft_*" --report
```

### Process Document Library

```python
from anything_to_md import AnythingToMD

converter = AnythingToMD()

# Convert with custom skip patterns
result = converter.convert_directory(
    source_dir="./library",
    target_dir="./library-md",
    skip_patterns=["*.bak", "temp_*", "archive/*"]
)

# Check results
print(f"Success rate: {result.success_rate:.1f}%")
for r in result.results:
    if not r.success and not r.skipped:
        print(f"Failed: {r.source_path} - {r.error}")
```

### Batch YouTube Processing

```python
from anything_to_md import AnythingToMD

converter = AnythingToMD()

videos = [
    "https://youtube.com/watch?v=xxx",
    "https://youtube.com/watch?v=yyy",
]

for url in videos:
    result = converter.convert_youtube(url)
    if result.success:
        # Process transcript
        print(f"Transcript length: {len(result.markdown)} chars")
```

## Architecture

```
anything-to-md/
├── src/
│   └── anything_to_md/
│       ├── __init__.py      # Package exports
│       ├── converter.py     # Core conversion logic
│       ├── mcp_server.py    # MCP server implementation
│       └── cli.py           # Command-line interface
├── src/skill/
│   └── SKILL.md            # Claude Code Skill definition
├── tests/
│   └── test_converter.py
├── pyproject.toml
└── README.md
```

## Dependencies

- **markitdown**: Microsoft's document conversion library
- **mcp**: Model Context Protocol implementation
- **yt-dlp**: YouTube video information extraction
- **rich**: Terminal formatting and progress bars
- **pathspec**: Gitignore-style pattern matching

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- [Microsoft MarkItDown](https://github.com/microsoft/markitdown) - Core document conversion
- [Video Insight Skill](https://mcpmarket.com/tools/skills/video-insight) - Inspiration for video processing
- [MCP Protocol](https://modelcontextprotocol.io/) - Claude integration

---

**Made for the AI-assisted development workflow**
