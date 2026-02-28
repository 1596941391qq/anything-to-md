#!/bin/bash
# Anything-to-MD 一键安装脚本
# 支持 Linux / macOS (Intel & Apple Silicon)

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Anything-to-MD Installation Script                 ║"
echo "║     把任何文件变成 AI 能吃的 Markdown                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检测操作系统
OS="$(uname -s)"
case "$OS" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    *)          MACHINE="UNKNOWN:$OS";;
esac

echo -e "${BLUE}[INFO]${NC} 检测到系统: $MACHINE"

# 检查 Python 版本
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
    elif command -v python &> /dev/null; then
        PYTHON_CMD=python
    else
        echo -e "${RED}[ERROR]${NC} 未找到 Python。请先安装 Python 3.10+"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
        echo -e "${RED}[ERROR]${NC} Python 版本过低 ($PYTHON_VERSION)。需要 3.10+"
        exit 1
    fi

    echo -e "${GREEN}[OK]${NC} Python $PYTHON_VERSION"
}

# 检查 ffmpeg
check_ffmpeg() {
    if command -v ffmpeg &> /dev/null && command -v ffprobe &> /dev/null; then
        FFMPEG_VERSION=$(ffmpeg -version | head -1 | awk '{print $3}')
        echo -e "${GREEN}[OK]${NC} ffmpeg $FFMPEG_VERSION"
    else
        echo -e "${YELLOW}[WARN]${NC} 未找到 ffmpeg/ffprobe（视频处理需要）"
        echo ""
        echo "安装方法："
        if [ "$MACHINE" = "Mac" ]; then
            echo "  brew install ffmpeg"
        elif [ "$MACHINE" = "Linux" ]; then
            echo "  # Ubuntu/Debian:"
            echo "  sudo apt install ffmpeg"
            echo "  # CentOS/RHEL:"
            echo "  sudo yum install ffmpeg"
            echo "  # Arch Linux:"
            echo "  sudo pacman -S ffmpeg"
        fi
        echo ""
        read -p "是否继续安装（跳过视频支持）？[y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        SKIP_VIDEO=true
    fi
}

# 创建虚拟环境
create_venv() {
    echo ""
    echo -e "${BLUE}[STEP]${NC} 创建虚拟环境..."

    if [ -d "venv" ]; then
        echo -e "${YELLOW}[WARN]${NC} venv 目录已存在，跳过创建"
    else
        $PYTHON_CMD -m venv venv
        echo -e "${GREEN}[OK]${NC} 虚拟环境已创建"
    fi

    source venv/bin/activate
    echo -e "${GREEN}[OK]${NC} 虚拟环境已激活"
}

# 安装基础依赖
install_base() {
    echo ""
    echo -e "${BLUE}[STEP]${NC} 安装基础依赖..."

    pip install --upgrade pip setuptools wheel

    # 安装 NumPy 1.x（避免 2.x ABI 兼容问题）
    pip install "numpy<2.0"

    # 安装主项目
    pip install -e .

    echo -e "${GREEN}[OK]${NC} 基础依赖安装完成"
}

# 安装 PDF 增强支持（MinerU）
install_pdf() {
    echo ""
    echo -e "${BLUE}[STEP]${NC} 安装 PDF 增强支持（MinerU）..."

    echo -e "${YELLOW}[NOTE]${NC} MinerU 首次运行会下载约 2GB 模型"
    read -p "是否安装 MinerU（推荐用于中文 PDF / 扫描件）？[Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        pip install "magic-pdf[full]"

        # 下载模型（可选，首次运行时会自动下载）
        echo ""
        read -p "是否现在下载模型（约 2GB）？[y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}[INFO]${NC} 开始下载模型..."
            pip install huggingface-hub
            $PYTHON_CMD -c "
from huggingface_hub import snapshot_download
snapshot_download('opendatalab/MinerU', local_dir='./models')
print('模型下载完成')
" || echo -e "${YELLOW}[WARN]${NC} 模型下载失败，首次运行时会自动重试"
        fi

        echo -e "${GREEN}[OK]${NC} PDF 增强支持安装完成"
    else
        echo -e "${YELLOW}[SKIP]${NC} 跳过 MinerU，PDF 将使用 MarkItDown/pypdf"
    fi
}

# 安装视频处理支持
install_video() {
    if [ "$SKIP_VIDEO" = true ]; then
        echo -e "${YELLOW}[SKIP]${NC} 跳过视频支持（未安装 ffmpeg）"
        return
    fi

    echo ""
    echo -e "${BLUE}[STEP]${NC} 安装视频处理支持..."

    pip install rapidocr-onnxruntime
    pip install faster-whisper
    pip install scenedetect[opencv]
    pip install imagehash
    pip install Pillow

    echo -e "${GREEN}[OK]${NC} 视频处理支持安装完成"
}

# 验证安装
verify_installation() {
    echo ""
    echo -e "${BLUE}[STEP]${NC} 验证安装..."

    $PYTHON_CMD -c "
import sys
print(f'Python: {sys.version}')

# 核心依赖
try:
    import markitdown
    print('✓ markitdown')
except ImportError:
    print('✗ markitdown')

try:
    import mcp
    print('✓ mcp')
except ImportError:
    print('✗ mcp')

# PDF（可选）
try:
    import magic_pdf
    print('✓ magic-pdf (MinerU)')
except ImportError:
    print('- magic-pdf (未安装，可选)')

# 视频（可选）
try:
    from rapidocr_onnxruntime import RapidOCR
    print('✓ rapidocr (OCR)')
except ImportError:
    print('- rapidocr (未安装，可选)')

try:
    from faster_whisper import WhisperModel
    print('✓ faster-whisper')
except ImportError:
    print('- faster-whisper (未安装，可选)')

try:
    from scenedetect import detect, ContentDetector
    print('✓ scenedetect')
except ImportError:
    print('- scenedetect (未安装，可选)')

print()
print('安装验证完成')
" || true
}

# 打印使用说明
print_usage() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    安装完成！                                ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo -e "${GREEN}使用方法：${NC}"
    echo ""
    echo "  # 激活虚拟环境"
    echo "  source venv/bin/activate"
    echo ""
    echo "  # 转换单个文件"
    echo "  anything-to-md file document.pdf -o ./output"
    echo ""
    echo "  # 批量转换目录"
    echo "  anything-to-md dir ./docs ./markdown --report"
    echo ""
    echo "  # 启动 MCP Server"
    echo "  anything-to-md-mcp"
    echo ""
    echo -e "${YELLOW}注意事项：${NC}"
    echo "  • 首次处理 PDF/视频会较慢（模型加载）"
    echo "  • MinerU 模型约 2GB，首次运行自动下载"
    echo "  • 视频转写默认使用 CPU，GPU 需额外配置"
    echo ""
}

# 主流程
main() {
    check_python
    check_ffmpeg
    create_venv
    install_base
    install_pdf
    install_video
    verify_installation
    print_usage
}

main "$@"
