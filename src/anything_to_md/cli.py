"""
Command Line Interface for Anything-to-MD
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .converter import AnythingToMD
from . import __version__

console = Console()


def cmd_convert_file(args):
    """Handle single file conversion"""
    converter = AnythingToMD(verbose=True)
    
    source = Path(args.file)
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    result = converter.convert_file(
        source=source,
        output_dir=output_dir,
        output_name=args.output_name
    )
    
    if result.success:
        console.print(f"\n[green]✓ Successfully converted to:[/green] {result.target_path}")
        if args.print_output and result.markdown:
            console.print("\n[bold]--- Markdown Content ---[/bold]")
            print(result.markdown)
    else:
        console.print(f"\n[red]✗ Conversion failed:[/red] {result.error}")
        sys.exit(1)


def cmd_convert_dir(args):
    """Handle directory conversion"""
    skip_patterns = args.skip or []
    source_dir = Path(args.source)
    target_dir = Path(args.target) if args.target else (source_dir / "anything-to-md")
    
    converter = AnythingToMD(
        verbose=True,
        skip_patterns=skip_patterns
    )
    
    result = converter.convert_directory(
        source_dir=source_dir,
        target_dir=target_dir,
        preserve_structure=not args.flat
    )
    
    if args.report:
        # Generate detailed report
        report_path = target_dir / "conversion_report.md"
        generate_report(result, report_path)
        console.print(f"\n[cyan]Report saved to:[/cyan] {report_path}")
    
    sys.exit(0 if result.failed == 0 else 1)


def cmd_convert_youtube(args):
    """Handle YouTube conversion"""
    converter = AnythingToMD(verbose=True)
    
    output_path = Path(args.output) if args.output else None
    
    result = converter.convert_youtube(
        url=args.url,
        output_path=output_path
    )
    
    if result.success:
        console.print(f"\n[green]✓ Successfully extracted transcript[/green]")
        if output_path:
            console.print(f"[green]  Saved to:[/green] {output_path}")
        if args.print_output and result.markdown:
            console.print("\n[bold]--- Transcript ---[/bold]")
            print(result.markdown)
    else:
        console.print(f"\n[red]✗ Extraction failed:[/red] {result.error}")
        sys.exit(1)


def cmd_list_formats(args):
    """List supported formats"""
    table = Table(title="Supported Formats")
    table.add_column("Category", style="cyan")
    table.add_column("Extensions", style="green")
    
    formats = {
        "Documents": ".pdf, .docx, .xlsx, .pptx, .odt, .ods, .odp",
        "Web": ".html, .htm, .xhtml",
        "eBooks": ".epub, .mobi",
        "Data": ".csv, .tsv, .json, .xml",
        "Images": ".png, .jpg, .jpeg, .gif, .bmp, .tiff, .webp",
        "Audio": ".mp3, .wav, .m4a, .flac, .ogg, .aac",
        "Video": ".mp4, .mkv, .avi, .mov, .webm",
        "URLs": "YouTube, Wikipedia, RSS feeds",
    }
    
    for category, extensions in formats.items():
        table.add_row(category, extensions)
    
    console.print(table)


def generate_report(result, output_path):
    """Generate a markdown report of conversion results"""
    report = f"""# Conversion Report

## Summary

- **Source Directory**: `{result.source_dir}`
- **Target Directory**: `{result.target_dir}`
- **Total Files**: {result.total_files}
- **Converted**: {result.converted}
- **Skipped**: {result.skipped}
- **Failed**: {result.failed}
- **Success Rate**: {result.success_rate:.1f}%

## Details

### Converted Files

"""
    for r in result.results:
        if r.success:
            report += f"- ✅ `{r.source_path}` → `{r.target_path}`\n"
    
    if result.skipped > 0:
        report += "\n### Skipped Files\n\n"
        for r in result.results:
            if r.skipped:
                report += f"- ⏭️ `{r.source_path}` - {r.skip_reason}\n"
    
    if result.failed > 0:
        report += "\n### Failed Files\n\n"
        for r in result.results:
            if not r.success and not r.skipped:
                report += f"- ❌ `{r.source_path}` - {r.error}\n"
    
    output_path.write_text(report, encoding='utf-8')


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="anything-to-md",
        description="Convert any file to LLM-ready Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Convert file command
    file_parser = subparsers.add_parser('file', help='Convert a single file')
    file_parser.add_argument('file', help='Path to the file to convert')
    file_parser.add_argument('-o', '--output-dir', help='Output directory')
    file_parser.add_argument('-n', '--output-name', help='Output filename')
    file_parser.add_argument('-p', '--print-output', action='store_true', 
                            help='Print the markdown output')
    file_parser.set_defaults(func=cmd_convert_file)
    
    # Convert directory command
    dir_parser = subparsers.add_parser('dir', help='Convert all files in a directory')
    dir_parser.add_argument('source', help='Source directory')
    dir_parser.add_argument(
        'target',
        nargs='?',
        help='Target directory (default: <source>/anything-to-md)'
    )
    dir_parser.add_argument('--flat', action='store_true', 
                           help='Use flat directory structure')
    dir_parser.add_argument('--skip', action='append', 
                           help='Patterns to skip (can be used multiple times)')
    dir_parser.add_argument('--report', action='store_true',
                           help='Generate conversion report')
    dir_parser.set_defaults(func=cmd_convert_dir)
    
    # Convert YouTube command
    yt_parser = subparsers.add_parser('youtube', aliases=['yt'], 
                                      help='Convert YouTube video')
    yt_parser.add_argument('url', help='YouTube URL')
    yt_parser.add_argument('-o', '--output', help='Output file path')
    yt_parser.add_argument('-p', '--print-output', action='store_true',
                          help='Print the transcript')
    yt_parser.set_defaults(func=cmd_convert_youtube)
    
    # List formats command
    formats_parser = subparsers.add_parser('formats', aliases=['list'],
                                          help='List supported formats')
    formats_parser.set_defaults(func=cmd_list_formats)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()
