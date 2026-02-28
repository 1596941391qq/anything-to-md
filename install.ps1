# Anything-to-MD Windows 安装脚本 (PowerShell)
# 支持 Windows 10/11

param(
    [switch]$SkipPdf,     # 跳过 MinerU 安装
    [switch]$SkipVideo,   # 跳过视频支持
    [switch]$Help         # 显示帮助
)

$ErrorActionPreference = "Stop"

# 颜色函数
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success { Write-ColorOutput Green $args }
function Write-Info { Write-ColorOutput Cyan $args }
function Write-Warn { Write-ColorOutput Yellow $args }
function Write-Err { Write-ColorOutput Red $args }

if ($Help) {
    Write-Host @"
Anything-to-MD Windows 安装脚本

用法:
    .\install.ps1                 # 完整安装
    .\install.ps1 -SkipPdf        # 跳过 MinerU（PDF 增强支持）
    .\install.ps1 -SkipVideo      # 跳过视频支持
    .\install.ps1 -SkipPdf -SkipVideo  # 最小安装

"@
    exit 0
}

Write-Host @"
╔══════════════════════════════════════════════════════════════╗
║           Anything-to-MD Installation Script                 ║
║     把任何文件变成 AI 能吃的 Markdown                          ║
╚══════════════════════════════════════════════════════════════╝
"@

# 检查 Python
Write-Info "[STEP] 检查 Python..."

$pythonCmd = $null
if (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} else {
    Write-Err "[ERROR] 未找到 Python。请先安装 Python 3.10+"
    Write-Host "下载地址: https://www.python.org/downloads/"
    exit 1
}

$pythonVersion = & $pythonCmd --version 2>&1
Write-Success "[OK] $pythonVersion"

# 检查 ffmpeg
Write-Info "[STEP] 检查 ffmpeg..."

$ffmpegInstalled = $false
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $ffmpegVersion = (ffmpeg -version 2>&1 | Select-Object -First 1)
    Write-Success "[OK] $ffmpegVersion"
    $ffmpegInstalled = $true
} else {
    Write-Warn "[WARN] 未找到 ffmpeg（视频处理需要）"
    Write-Host ""
    Write-Host "安装方法:"
    Write-Host "  1. 使用 winget:  winget install ffmpeg"
    Write-Host "  2. 使用 Chocolatey:  choco install ffmpeg"
    Write-Host "  3. 手动下载: https://www.gyan.dev/ffmpeg/builds/"
    Write-Host ""

    if (-not $SkipVideo) {
        $response = Read-Host "是否继续安装（跳过视频支持）？[y/N]"
        if ($response -ne "y" -and $response -ne "Y") {
            exit 1
        }
        $SkipVideo = $true
    }
}

# 创建虚拟环境
Write-Info "[STEP] 创建虚拟环境..."

if (Test-Path "venv") {
    Write-Warn "[WARN] venv 目录已存在，跳过创建"
} else {
    & $pythonCmd -m venv venv
    Write-Success "[OK] 虚拟环境已创建"
}

# 激活虚拟环境
& .\venv\Scripts\Activate.ps1
Write-Success "[OK] 虚拟环境已激活"

# 安装基础依赖
Write-Info "[STEP] 安装基础依赖..."

pip install --upgrade pip setuptools wheel

# NumPy 1.x（避免 2.x 兼容问题）
pip install "numpy<2.0"

# 安装主项目
pip install -e .

Write-Success "[OK] 基础依赖安装完成"

# 安装 PDF 增强（MinerU）
if (-not $SkipPdf) {
    Write-Info "[STEP] 安装 PDF 增强支持（MinerU）..."
    Write-Warn "[NOTE] MinerU 首次运行会下载约 2GB 模型"

    $response = Read-Host "是否安装 MinerU（推荐用于中文 PDF / 扫描件）？[Y/n]"
    if ($response -ne "n" -and $response -ne "N") {
        pip install "magic-pdf[full]"
        Write-Success "[OK] PDF 增强支持安装完成"
    } else {
        Write-Warn "[SKIP] 跳过 MinerU，PDF 将使用 MarkItDown/pypdf"
    }
}

# 安装视频支持
if (-not $SkipVideo -and $ffmpegInstalled) {
    Write-Info "[STEP] 安装视频处理支持..."

    pip install rapidocr-onnxruntime
    pip install faster-whisper
    pip install scenedetect[opencv]
    pip install imagehash
    pip install Pillow

    Write-Success "[OK] 视频处理支持安装完成"
}

# 验证安装
Write-Info "[STEP] 验证安装..."

& python -c @'
import sys
print(f"Python: {sys.version}")

# 核心依赖
try:
    import markitdown
    print("✓ markitdown")
except ImportError:
    print("✗ markitdown")

try:
    import mcp
    print("✓ mcp")
except ImportError:
    print("✗ mcp")

# PDF（可选）
try:
    import magic_pdf
    print("✓ magic-pdf (MinerU)")
except ImportError:
    print("- magic-pdf (未安装，可选)")

# 视频（可选）
try:
    from rapidocr_onnxruntime import RapidOCR
    print("✓ rapidocr (OCR)")
except ImportError:
    print("- rapidocr (未安装，可选)")

try:
    from faster_whisper import WhisperModel
    print("✓ faster-whisper")
except ImportError:
    print("- faster-whisper (未安装，可选)")

try:
    from scenedetect import detect, ContentDetector
    print("✓ scenedetect")
except ImportError:
    print("- scenedetect (未安装，可选)")

print()
print("安装验证完成")
'@

# 使用说明
Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                    安装完成！                                ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Green

Write-Host "使用方法:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  # 激活虚拟环境"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "  # 转换单个文件"
Write-Host "  anything-to-md file document.pdf -o ./output"
Write-Host ""
Write-Host "  # 批量转换目录"
Write-Host "  anything-to-md dir ./docs ./markdown --report"
Write-Host ""
Write-Host "  # 启动 MCP Server"
Write-Host "  anything-to-md-mcp"
Write-Host ""

Write-Warn "注意事项:"
Write-Host "  • 首次处理 PDF/视频会较慢（模型加载）"
Write-Host "  • MinerU 模型约 2GB，首次运行自动下载"
Write-Host "  • 视频转写默认使用 CPU，GPU 需额外配置"
Write-Host ""
