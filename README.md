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
  ├─ 视频 ──→ VideoRouter (智能路由)
  │     │
  │     ├─ PROBE: 探测字幕轨/音频轨/画面文字
  │     ├─ DECIDE: 选择最优策略
  │     ├─ EXTRACT: 字幕提取 / faster-whisper / 关键帧OCR
  │     └─ FUSE: 时间轴对齐 + 内容去重
  │
  ├─ 音频 ──→ faster-whisper 转写
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

## 视频智能路由（NEW）

视频不是简单的"转写"就完事。很多视频（教程、PPT录屏、带字幕的讲座）的核心信息在画面上。

### 4 阶段流水线

```
PROBE → DECIDE → EXTRACT → FUSE
```

**Phase 1: PROBE** (< 5 秒)
- ffprobe 探测：内嵌字幕轨、音频轨
- 旁白文件检测：.srt/.vtt
- 采样帧 OCR：5 帧快速 OCR 检测画面文字

**Phase 2: DECIDE** - 智能选路

| 视频类型 | 策略 | 成本 |
|----------|------|------|
| 有内嵌字幕 | `embedded_subtitle` | 极低，秒级 |
| 有旁白 .srt | `sidecar_subtitle` | 极低 |
| 纯人声（播客） | `audio_transcribe` | 中 |
| PPT录屏 + 旁白 | `hybrid` | 高 |
| 硬编码字幕 | `visual_ocr` | 高 |
| 未知/混合 | `full_pipeline` | 最高 |

**Phase 3: EXTRACT**
- **字幕**：ffmpeg 直接提取 SRT
- **音频**：faster-whisper（比 OpenAI Whisper 快 4x）
- **画面**：PySceneDetect 场景检测 + 感知哈希去重 + RapidOCR

**Phase 4: FUSE**
- 时间轴对齐
- 内容去重（字幕 vs 转写 vs OCR）
- 优先级：字幕 > 音频 > OCR

### 关键优化

不要 OCR 每一帧。场景检测 + 感知哈希把 1 小时视频从 ~108,000 帧降到 50-200 关键帧。

## 安装

### 方式一：一键安装（推荐）

**Linux / macOS:**
```bash
git clone https://github.com/your-repo/anything-to-md.git
cd anything-to-md
chmod +x install.sh
./install.sh
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/your-repo/anything-to-md.git
cd anything-to-md
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

安装脚本会：
1. 创建独立虚拟环境
2. 安装基础依赖
3. 询问是否安装 PDF 增强（MinerU）
4. 询问是否安装视频支持
5. 验证安装

### 方式二：手动安装

```bash
# 基础安装（纯文本 PDF、Office、HTML、JSON 等）
pip install -e .

# PDF 增强（中文 PDF、扫描件、表格）
pip install -e ".[pdf]"

# 视频处理支持
pip install -e ".[video]"

# 完整安装（所有功能）
pip install -e ".[full]"
```

### 外部依赖

| 功能 | 依赖 | 安装方法 |
|------|------|----------|
| 视频处理 | ffmpeg | `brew install ffmpeg` / `apt install ffmpeg` / `winget install ffmpeg` |
| PDF OCR | MinerU 模型 (~2GB) | 首次运行自动下载 |

### 常见问题

**NumPy 兼容性:**
```bash
pip install "numpy<2.0"  # 避免 ABI 兼容问题
```

**PyTorch CUDA 问题:**
```bash
# faster-whisper CUDA DLL 加载失败时，自动降级到 openai-whisper
pip install openai-whisper
```

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

## Roadmap

- [ ] GPU 加速支持（CUDA/Metal）
- [ ] 并行批处理
- [ ] 更多 OCR 引擎（EasyOCR, Tesseract）

## 致谢 / Acknowledgments

本项目基于以下优秀开源项目构建：

| 项目 | 用途 | 链接 |
|------|------|------|
| **MarkItDown** | 核心文档转换引擎 | [github.com/microsoft/markitdown](https://github.com/microsoft/markitdown) |
| **MinerU (magic-pdf)** | PDF OCR + 布局检测 + 表格识别 | [github.com/opendatalab/MinerU](https://github.com/opendatalab/MinerU) |
| **Video Insight** | 视频智能路由设计灵感 | Claude Code Skill |
| **faster-whisper** | 高效音频转写 | [github.com/systran/faster-whisper](https://github.com/systran/faster-whisper) |
| **RapidOCR** | 中英文 OCR 引擎 | [github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR) |
| **PySceneDetect** | 视频场景检测 | [github.com/Breakthrough/PySceneDetect](https://github.com/Breakthrough/PySceneDetect) |
| **imagehash** | 感知哈希去重 | [github.com/JohannesBuchner/imagehash](https://github.com/JohannesBuchner/imagehash) |

特别感谢这些项目的作者和贡献者，让文档转换变得更简单。

## License

MIT
