import os
import shutil
import json
import io
import click
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

# 外部ライブラリ
from rich.console import Console
from rich.table import Table
from rich.progress import track
from PIL import Image
import fitz  # PyMuPDF

# コンソール設定
console = Console()

@dataclass
class InspectionResult:
    original_size: int
    potential_size: int
    bloat_type: str
    message: str

    @property
    def reduction(self) -> int:
        return self.original_size - self.potential_size

    @property
    def reduction_percent(self) -> float:
        if self.original_size == 0:
            return 0.0
        return (self.reduction / self.original_size) * 100

class BaseInspector(ABC):
    """検査・最適化を行う基底クラス"""

    @abstractmethod
    def inspect(self, file_path: Path) -> InspectionResult:
        """削減可能なサイズと詳細を返す（非破壊）"""
        pass

    @abstractmethod
    def optimize(self, file_path: Path, output_path: Path) -> bool:
        """実際に削減処理を行う"""
        pass

class ImageInspector(BaseInspector):
    """画像 (JPG, PNG) の最適化: メタデータ削除と最適化保存"""

    def inspect(self, file_path: Path) -> InspectionResult:
        original_size = file_path.stat().st_size
        bloat_info = []
        
        try:
            with Image.open(file_path) as img:
                # Exif等の確認
                if "exif" in img.info:
                    bloat_info.append("Exif Metadata")
                if img.info.get("icc_profile"):
                    bloat_info.append("ICC Profile")
                
                # 削減サイズの見積もり（メモリ上で最適化保存を試みる）
                buffer = io.BytesIO()
                # フォーマット維持、品質維持、メタデータ削除
                save_args = {"format": img.format, "optimize": True}
                if img.format == "JPEG":
                    save_args["quality"] = "keep"
                    save_args["subsampling"] = "keep"
                
                # メタデータを含めずに保存
                img.save(buffer, **save_args)
                potential_size = buffer.tell()

            bloat_type = ", ".join(bloat_info) if bloat_info else "Compressible Encoding"
            return InspectionResult(original_size, potential_size, bloat_type, "Image optimization")

        except Exception as e:
            return InspectionResult(original_size, original_size, "Error", str(e))

    def optimize(self, file_path: Path, output_path: Path) -> bool:
        try:
            with Image.open(file_path) as img:
                save_args = {"format": img.format, "optimize": True}
                
                # JPEGの場合、品質を維持
                if img.format == "JPEG":
                    save_args["quality"] = "keep"
                    save_args["subsampling"] = "keep"
                
                img.save(output_path, **save_args)
            return True
        except Exception as e:
            console.print(f"[red]Error optimizing image {file_path}: {e}[/red]")
            return False

class PDFInspector(BaseInspector):
    """PDFの最適化: 未使用オブジェクト削除とストリーム圧縮"""

    def inspect(self, file_path: Path) -> InspectionResult:
        original_size = file_path.stat().st_size
        try:
            doc = fitz.open(file_path)
            
            pdf_bytes = doc.tobytes(garbage=4, deflate=True)
            potential_size = len(pdf_bytes)
            
            doc.close()
            
            diff = original_size - potential_size
            bloat_type = "Unused Objects / Uncompressed Stream" if diff > 0 else "None"
            
            return InspectionResult(original_size, potential_size, bloat_type, "PDF Garbage Collection")
        except Exception as e:
            return InspectionResult(original_size, original_size, "Error", str(e))

    def optimize(self, file_path: Path, output_path: Path) -> bool:
        try:
            doc = fitz.open(file_path)
            doc.save(output_path, garbage=4, deflate=True)
            doc.close()
            return True
        except Exception as e:
            console.print(f"[red]Error optimizing PDF {file_path}: {e}[/red]")
            return False

class TextInspector(BaseInspector):
    """JSONテキストの最適化: 空白・インデント削除"""

    def inspect(self, file_path: Path) -> InspectionResult:
        original_size = file_path.stat().st_size
        if file_path.suffix.lower() != '.json':
            return InspectionResult(original_size, original_size, "Unsupported Text", "Skipped")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            minified = json.dumps(data, separators=(',', ':'))
            potential_size = len(minified.encode('utf-8'))
            
            return InspectionResult(original_size, potential_size, "Whitespace / Indentation", "JSON Minify")
        except Exception as e:
            return InspectionResult(original_size, original_size, "Parse Error", str(e))

    def optimize(self, file_path: Path, output_path: Path) -> bool:
        if file_path.suffix.lower() != '.json':
            return False
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, separators=(',', ':'))
            return True
        except Exception:
            return False

class InspectorFactory:
    """ファイル拡張子に応じて適切なInspectorを返す"""
    
    @staticmethod
    def get_inspector(file_path: Path) -> Optional[BaseInspector]:
        ext = file_path.suffix.lower()
        
        if ext in ['.jpg', '.jpeg', '.png']:
            return ImageInspector()
        elif ext in ['.pdf']:
            return PDFInspector()
        elif ext in ['.json']:
            return TextInspector()
        else:
            return None

@click.command()
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
@click.option('--mode', '-m', type=click.Choice(['inspect', 'optimize']), default='inspect', help='動作モード (inspect: 検査のみ, optimize: 実行)')
@click.option('--recursive', '-r', is_flag=True, help='ディレクトリを再帰的に処理する')
@click.option('--no-backup', is_flag=True, help='最適化時にバックアップを作成しない')
@click.option('--outdir', '-o', type=click.Path(), help='出力先のフォルダ。指定すると元のファイルは上書きされず、ここに保存されます。')
def main(paths, mode, recursive, no_backup, outdir):
    """
    BitTrimInspector: ファイルサイズ膨張の原因を特定し、無駄なデータを削除するツール。
    
    PATHS: 処理対象のファイルまたはディレクトリ
    """
    
    target_files = []
    for p in paths:
        path_obj = Path(p)
        if path_obj.is_file():
            target_files.append(path_obj)
        elif path_obj.is_dir():
            pattern = '**/*' if recursive else '*'
            target_files.extend([f for f in path_obj.glob(pattern) if f.is_file()])

    if not target_files:
        console.print("[yellow]対象ファイルが見つかりませんでした。[/yellow]")
        return

    # 出力先ディレクトリの準備
    outdir_path = Path(outdir) if outdir else None
    if outdir_path and not outdir_path.exists() and mode == 'optimize':
        outdir_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]出力先ディレクトリを作成しました: {outdir_path}[/green]")

    table = Table(title=f"BitTrimInspector Report ({mode.upper()})")
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Original", justify="right")
    table.add_column("Result/Potential", justify="right", style="green")
    table.add_column("Reduction", justify="right", style="bold magenta")
    table.add_column("Bloat Type / Status")

    total_orig = 0
    total_reduced = 0

    with click.progressbar(target_files, label=f"Processing files...") as bar:
        for file_path in bar:
            inspector = InspectorFactory.get_inspector(file_path)
            
            if not inspector:
                continue

            # 1. 検査
            res = inspector.inspect(file_path)
            
            if res.reduction <= 0:
                continue

            final_size = res.potential_size
            status_msg = res.bloat_type

            # 2. 最適化
            if mode == 'optimize':
                if outdir_path:
                    # 【新機能】指定した出力先ディレクトリに保存
                    final_output_path = outdir_path / file_path.name
                    success = inspector.optimize(file_path, final_output_path)
                    
                    if success and final_output_path.exists() and final_output_path.stat().st_size > 0:
                        final_size = final_output_path.stat().st_size
                        status_msg = "[bold green]Saved to Outdir[/bold green]"
                    else:
                        if final_output_path.exists():
                            final_output_path.unlink()
                        status_msg = "[red]Optimization Failed[/red]"
                        final_size = res.original_size
                else:
                    # 【従来機能】上書き＆バックアップ処理
                    if not no_backup:
                        backup_path = file_path.with_name(file_path.name + ".bak")
                        shutil.copy2(file_path, backup_path)
                    
                    temp_path = file_path.with_name(file_path.name + ".tmp")
                    success = inspector.optimize(file_path, temp_path)
                    
                    if success:
                        if temp_path.stat().st_size > 0:
                            temp_path.replace(file_path)
                            final_size = file_path.stat().st_size
                            status_msg = "[bold green]Optimized[/bold green]"
                        else:
                            temp_path.unlink(missing_ok=True)
                            status_msg = "[red]Validation Failed[/red]"
                            final_size = res.original_size
                    else:
                        status_msg = "[red]Optimization Failed[/red]"
                        final_size = res.original_size

            # 集計
            reduction = res.original_size - final_size
            if reduction > 0:
                total_orig += res.original_size
                total_reduced += reduction
                
                table.add_row(
                    file_path.name,
                    f"{res.original_size / 1024:.1f} KB",
                    f"{final_size / 1024:.1f} KB",
                    f"-{reduction / 1024:.1f} KB ({ (reduction/res.original_size)*100:.1f}%)",
                    status_msg
                )

    console.print(table)
    
    if total_orig > 0:
        console.print(f"\n[bold]Total Reduction:[/bold] -{total_reduced / 1024 / 1024:.2f} MB")
    else:
        console.print("\n削減可能なファイルは見つかりませんでした。")

if __name__ == '__main__':
    main()