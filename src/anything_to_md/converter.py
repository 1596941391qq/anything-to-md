"""
Core converter module - wraps MarkItDown with additional capabilities
"""

import os
import shutil
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass, field

# Lazy import to avoid import errors when markitdown is not installed
_markitdown = None

def _get_markitdown():
    global _markitdown
    if _markitdown is None:
        try:
            from markitdown import MarkItDown
            _markitdown = MarkItDown
        except ImportError:
            raise ImportError(
                "markitdown is required. Install it with: pip install markitdown"
            )
    return _markitdown

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import pathspec

console = Console()


@dataclass
class ConversionResult:
    """Result of a single file conversion"""
    source_path: Path
    target_path: Path
    success: bool
    markdown: Optional[str] = None
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


@dataclass
class BatchResult:
    """Result of a batch conversion"""
    source_dir: Path
    target_dir: Path
    total_files: int = 0
    converted: int = 0
    skipped: int = 0
    failed: int = 0
    results: List[ConversionResult] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.converted / self.total_files * 100


class AnythingToMD:
    """
    Universal document to Markdown converter.
    
    Supports:
    - PDF, Word, Excel, PowerPoint
    - Images (with OCR)
    - Audio/Video (transcription)
    - YouTube URLs
    - HTML, EPUB, and more
    """
    
    # File types that should be skipped
    SKIP_EXTENSIONS = {
        # Already text/markdown
        '.md', '.txt', '.json', '.xml', '.yaml', '.yml',
        # Code files (optional - can be converted to MD with syntax highlighting)
        '.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.hpp',
        '.go', '.rs', '.rb', '.php', '.swift', '.kt',
        # Config files
        '.toml', '.ini', '.cfg', '.conf',
        # Lock files
        '.lock', '.sum',
        # Binary non-convertible
        '.exe', '.dll', '.so', '.dylib', '.bin',
        '.zip', '.tar', '.gz', '.rar', '.7z',  # archives are handled by markitdown
        # Database files
        '.db', '.sqlite', '.sqlite3',
    }
    
    # Extensions that are already Markdown-friendly
    KEEP_AS_IS_EXTENSIONS = {
        '.md', '.markdown', '.rst'
    }
    
    def __init__(
        self,
        enable_plugins: bool = False,
        skip_patterns: Optional[List[str]] = None,
        verbose: bool = True
    ):
        MarkItDown = _get_markitdown()
        self.markitdown = MarkItDown(enable_plugins=enable_plugins)
        self.verbose = verbose
        
        # Default skip patterns (gitignore style)
        default_skips = [
            '.git/',
            '__pycache__/',
            'node_modules/',
            '.venv/',
            'venv/',
            '.env',
            '*.pyc',
            '*.pyo',
            '.DS_Store',
            'Thumbs.db',
        ]
        self.skip_patterns = default_skips + (skip_patterns or [])
        self.spec = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern,
            self.skip_patterns
        )
    
    def should_skip(self, path: Path, base_dir: Path) -> tuple[bool, str]:
        """Check if a file should be skipped"""
        rel_path = path.relative_to(base_dir)
        rel_str = str(rel_path).replace('\\', '/')
        
        # Check gitignore patterns
        if self.spec.match_file(rel_str):
            return True, "Matched skip pattern"
        
        # Check extension
        ext = path.suffix.lower()
        if ext in self.SKIP_EXTENSIONS:
            return True, f"Extension {ext} in skip list"
        
        return False, ""
    
    def convert_file(
        self,
        source: Path,
        output_dir: Optional[Path] = None,
        output_name: Optional[str] = None
    ) -> ConversionResult:
        """Convert a single file to Markdown"""
        
        if not source.exists():
            return ConversionResult(
                source_path=source,
                target_path=Path(""),
                success=False,
                error=f"Source file not found: {source}"
            )
        
        # Determine output path
        if output_dir is None:
            output_dir = source.parent
        
        if output_name is None:
            output_name = source.stem + '.md'
        elif not output_name.endswith('.md'):
            output_name = output_name + '.md'
        
        target_path = output_dir / output_name
        
        try:
            # Use MarkItDown to convert
            result = self.markitdown.convert(str(source))
            # Handle different API versions - result may be string or object
            if hasattr(result, 'text_content'):
                markdown_content = result.text_content
            elif hasattr(result, 'markdown'):
                markdown_content = result.markdown
            else:
                markdown_content = str(result)
            
            # Write output
            output_dir.mkdir(parents=True, exist_ok=True)
            target_path.write_text(markdown_content, encoding='utf-8')
            
            if self.verbose:
                console.print(f"[green]✓[/green] {source.name} -> {output_name}")
            
            return ConversionResult(
                source_path=source,
                target_path=target_path,
                success=True,
                markdown=markdown_content
            )
            
        except Exception as e:
            if self.verbose:
                console.print(f"[red]✗[/red] {source.name}: {e}")
            
            return ConversionResult(
                source_path=source,
                target_path=target_path,
                success=False,
                error=str(e)
            )
    
    def convert_directory(
        self,
        source_dir: Path,
        target_dir: Path,
        preserve_structure: bool = True,
        copy_non_convertible: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> BatchResult:
        """
        Convert all files in a directory to Markdown.
        
        Args:
            source_dir: Source directory to process
            target_dir: Target directory for output
            preserve_structure: Keep the original directory structure
            copy_non_convertible: Copy files that can't be converted
            progress_callback: Optional callback(current, total, filename)
        
        Returns:
            BatchResult with conversion statistics
        """
        source_dir = Path(source_dir).resolve()
        target_dir = Path(target_dir).resolve()
        
        if not source_dir.exists():
            raise ValueError(f"Source directory not found: {source_dir}")
        
        # Collect all files
        all_files = [f for f in source_dir.rglob('*') if f.is_file()]
        convertible_files = []
        skip_results = []
        
        for f in all_files:
            should_skip, reason = self.should_skip(f, source_dir)
            if should_skip:
                skip_results.append(ConversionResult(
                    source_path=f,
                    target_path=Path(""),
                    success=False,
                    skipped=True,
                    skip_reason=reason
                ))
            else:
                convertible_files.append(f)
        
        result = BatchResult(
            source_dir=source_dir,
            target_dir=target_dir,
            total_files=len(convertible_files),
            skipped=len(skip_results),
            results=skip_results
        )
        
        if not convertible_files:
            if self.verbose:
                console.print("[yellow]No convertible files found[/yellow]")
            return result
        
        if self.verbose:
            console.print(f"[cyan]Processing {len(convertible_files)} files...[/cyan]")
        
        # Process files with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            disable=not self.verbose
        ) as progress:
            task = progress.add_task("Converting...", total=len(convertible_files))
            
            for i, file_path in enumerate(convertible_files):
                progress.update(task, description=f"Converting {file_path.name}")
                
                # Calculate relative path and target
                rel_path = file_path.relative_to(source_dir)
                
                if preserve_structure:
                    # Keep directory structure
                    target_subdir = target_dir / rel_path.parent
                    output_name = file_path.stem + '.md'
                else:
                    # Flat structure
                    target_subdir = target_dir
                    # Add parent dir prefix to avoid name collisions
                    if rel_path.parent != Path('.'):
                        output_name = f"{rel_path.parent}_{file_path.stem}".replace('/', '_').replace('\\', '_') + '.md'
                    else:
                        output_name = file_path.stem + '.md'
                
                target_subdir.mkdir(parents=True, exist_ok=True)
                
                conv_result = self.convert_file(
                    source=file_path,
                    output_dir=target_subdir,
                    output_name=output_name
                )
                
                result.results.append(conv_result)
                
                if conv_result.success:
                    result.converted += 1
                else:
                    result.failed += 1
                
                progress.advance(task)
                
                if progress_callback:
                    progress_callback(i + 1, len(convertible_files), file_path.name)
        
        if self.verbose:
            console.print(
                f"\n[bold]Results:[/bold] "
                f"[green]{result.converted} converted[/green], "
                f"[yellow]{result.skipped} skipped[/yellow], "
                f"[red]{result.failed} failed[/red]"
            )
        
        return result
    
    def convert_youtube(
        self,
        url: str,
        output_path: Optional[Path] = None
    ) -> ConversionResult:
        """Convert YouTube video to Markdown transcript"""
        
        try:
            result = self.markitdown.convert(url)
            # Handle different API versions
            if hasattr(result, 'text_content'):
                content = result.text_content
            elif hasattr(result, 'markdown'):
                content = result.markdown
            else:
                content = str(result)
            
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content, encoding='utf-8')
            
            return ConversionResult(
                source_path=Path(url),
                target_path=output_path or Path(""),
                success=True,
                markdown=content
            )
            
        except Exception as e:
            return ConversionResult(
                source_path=Path(url),
                target_path=Path(""),
                success=False,
                error=str(e)
            )
