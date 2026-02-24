# Anything-to-MD

把常见多模态内容（PDF、Office、图片、音视频、网页/YouTube）转成适合 AI 消费的 Markdown。

## 项目定位

本项目是一个统一包体，包含三种使用方式：

- CLI：本地命令行批量/单文件转换
- MCP Server：给 Claude Code / AionUI 等 MCP 客户端调用
- Skill：在 Agent 工作流中作为可复用能力描述

核心目标：将“原始多模态输入”转换为“结构化、可索引、可总结”的 Markdown。

## 已实现能力

- 文档：PDF / DOCX / XLSX / PPTX 等（优先走 MarkItDown）
- 图片：通过 MarkItDown 生态插件支持 OCR（依赖插件环境）
- 视频：
  - 优先走 MarkItDown 转写
  - 若失败：自动尝试
    - 提取内嵌字幕轨（SRT/WebVTT）
    - 提取音频并分段转写（SpeechRecognition + Google）
- YouTube：通过 `convert_youtube` 工具输出 Markdown
- 目录批处理：保持目录结构或平铺输出

## 安装

```bash
pip install -e .
```

建议使用独立虚拟环境，避免系统 Python 依赖冲突。

## CLI 用法

```bash
# 单文件
anything-to-md file ./test_data/demo.pdf -o ./output

# 目录批量
anything-to-md dir ./test_data ./output --report

# YouTube
anything-to-md youtube "https://www.youtube.com/watch?v=..."

# 查看格式支持
anything-to-md formats
```

## MCP 用法

### 直接启动

```bash
anything-to-md-mcp
# 或
python -m anything_to_md.mcp_server
```

### Claude Code 侧配置示例

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

## Skill + MCP + CLI 是否开箱即用

是。当前仓库已经具备：

- `project.scripts`：`anything-to-md` / `anything-to-md-mcp`
- `mcp.servers` entry point：`anything-to-md`
- `src/skill/SKILL.md`：Skill 描述文件

只要依赖完整且运行环境正常，即可直接使用。

## 重要说明：依赖兼容性

如果你在系统环境看到类似 `NumPy 2.x 与 pandas/pyarrow ABI 不兼容`，MarkItDown 可能初始化失败。

建议：

1. 使用干净 venv
2. 安装 `markitdown[all]` 并确保 `numpy/pandas/pyarrow` 版本兼容

本项目已提供回退路径，尽量保证产出可用 Markdown，而不是仅输出无用元数据。

## 本轮测试（你提供的 test_data）

输入：3 个 PDF + 3 个 MP4

结果：

- 3/3 PDF 成功转为 Markdown
- 3/3 MP4 成功产出 Markdown，其中无字幕视频通过音频分段转写生成带时间戳内容

输出目录：`test_output/full_run/`

## 许可证

MIT
