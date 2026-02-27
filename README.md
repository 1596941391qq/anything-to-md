# Anything-to-MD

> 把任何文件变成 AI 能吃的 Markdown。PDF、Office、图片、音视频、YouTube — 一个命令搞定。

```
anything-to-md file report.pdf -o ./output
```

## 为什么需要这个

LLM 不吃 PDF，不吃 PPT，不吃视频。但你的知识全在这些格式里。

Anything-to-MD 是一个统一转换层：**原始多模态输入 → 结构化、可索引、可总结的 Markdown**。

三种使用方式，同一套引擎：

| 方式 | 场景 |
|------|------|
| CLI | 本地命令行，单文件或批量 |
| MCP Server | Claude Code / Cursor / AionUI 等 MCP 客户端直接调用 |
| Skill | Agent 工作流中作为可复用能力 |

## 架构

```
输入文件
  │
  ├─ PDF ──→ MinerU (OCR级) ──→ MarkItDown ──→ pypdf
  │          布局检测+表格识别     文本提取        纯文本兜底
  │          图片提取+公式识别
  │
  ├─ Office (DOCX/XLSX/PPTX) ──→ MarkItDown ──→ openpyxl 兜底
  │
  ├─ 图片 ──→ MarkItDown + OCR 插件
  │
  ├─ 音视频 ──→ MarkItDown 转写 ──→ 内嵌字幕提取 ──→ ffmpeg 分段 + SpeechRecognition
  │
  ├─ YouTube ──→ yt-dlp 字幕/转写
  │
  └─ HTML/EPUB/CSV/JSON/XML ──→ MarkItDown
                                      │
                                      ▼
                              结构化 Markdown 输出
```

每种格式都有多级降级链。上游失败，自动切下游，不丢内容。

## PDF 三级引擎

这是核心差异化能力。大多数工具只有一个 PDF 后端，遇到扫描件或中文图文混排就歇菜。

| 优先级 | 引擎 | 能力 | 适用场景 |
|--------|------|------|----------|
| 1 | **MinerU** | OCR + 布局检测 + 表格识别 + 图片提取 | 扫描件、中文/CJK、PPT导出、图文混排 |
| 2 | **MarkItDown** | 快速文本提取 | 纯文本 PDF、英文文档 |
| 3 | **pypdf** | 基础文本提取 | 最后兜底 |

MinerU 首次运行会下载 ~2GB 模型（后续秒开）。如果你的 PDF 是纯文本英文，MarkItDown 就够了；但凡涉及中文、扫描件、表格 — MinerU 是质的飞跃。

## 安装

```bash
# 基础安装
pip install -e .

# 安装 MinerU（推荐，PDF 质量大幅提升）
pip install magic-pdf[full]
```

建议使用独立虚拟环境。NumPy 2.x 与部分依赖有 ABI 兼容问题，干净 venv 可以避免。

## CLI

```bash
# 单文件转换
anything-to-md file document.pdf -o ./output

# 目录批量转换（保持目录结构）
anything-to-md dir ./my-docs ./my-mds --report

# YouTube 视频转写
anything-to-md youtube "https://www.youtube.com/watch?v=..."

# 查看支持的格式
anything-to-md formats
```

## MCP Server

```bash
# 直接启动
anything-to-md-mcp

# 或
python -m anything_to_md.mcp_server
```

Claude Code 配置：

```json
{
  "mcpServers": {
    "anything-to-md": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "anything_to_md.mcp_server"]
    }
  }
}
```

MCP 提供 4 个工具：

- `convert_file_to_markdown` — 单文件转换
- `convert_directory_to_markdown` — 批量转换
- `convert_youtube_to_markdown` — YouTube 转写
- `get_supported_formats` — 查看支持格式

## 支持格式

| 类别 | 格式 |
|------|------|
| 文档 | PDF, DOCX, XLSX, PPTX, ODT, ODS, ODP |
| 网页 | HTML, HTM, XHTML |
| 电子书 | EPUB, MOBI |
| 数据 | CSV, TSV, JSON, XML |
| 图片 | PNG, JPG, GIF, BMP, TIFF, WEBP (OCR) |
| 音频 | MP3, WAV, M4A, FLAC, OGG, AAC |
| 视频 | MP4, MKV, AVI, MOV, WEBM |
| URL | YouTube, Wikipedia, RSS |

## 音视频处理链路

视频/音频不是简单的"转写"就完事。处理链路：

1. MarkItDown 原生转写（短音视频）
2. 若失败 → 提取内嵌字幕轨（SRT/WebVTT）
3. 若无字幕 → ffmpeg 分段提取音频 + SpeechRecognition 逐段转写（带时间戳）
4. 若全部失败 → 标记失败（不输出空壳文件）

## 依赖兼容性

已知问题：NumPy 2.x 与 pandas/pyarrow 的 ABI 不兼容可能导致 MarkItDown 初始化失败。

解决方案：
```bash
pip install numpy==1.26.4  # 降级到 1.x
```

所有引擎都有降级路径，单个引擎挂了不影响整体。

## Roadmap

- [ ] 视频 OCR 智能路由（关键帧提取 + 画面文字识别 + 语音转写融合）
- [ ] faster-whisper 替代 Google Speech Recognition
- [ ] GPU 加速支持
- [ ] 并行批处理

## License

MIT
