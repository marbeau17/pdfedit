import os
import re
import argparse
from pypdf import PdfReader, PdfWriter

def natural_sort_key(s):
    """
    ファイル名から数字を抽出し、数値として比較できるようにする。
    例: "part10.pdf" -> ["part", 10, ".pdf"]
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]

def combine_pdfs(args):
    writer = PdfWriter()
    
    # 1. 結合するファイルリストの決定
    if args.order:
        # 手動指定モード：カンマ区切りのリストを作成
        pdf_files = [f.strip() for f in args.order.split(",")]
        # フルパスでない場合はinput_dirを補完
        pdf_files = [f if os.path.isabs(f) else os.path.join(args.input_dir, f) for f in pdf_files]
        print("Mode: 手動指定された順序で結合します。")
    else:
        # 自動モード：フォルダ内のファイルを取得してソート
        files_in_dir = [f for f in os.listdir(args.input_dir) if f.lower().endswith('.pdf')]
        
        # 出力ファイル自体が混ざっていたら除外
        output_filename = os.path.basename(args.output)
        if output_filename in files_in_dir:
            files_in_dir.remove(output_filename)
            
        # フィルタリング
        if args.pattern:
            files_in_dir = [f for f in files_in_dir if args.pattern in f]
            
        # 【重要】自然順（番号順）にソート
        files_in_dir.sort(key=natural_sort_key)
        pdf_files = [os.path.join(args.input_dir, f) for f in files_in_dir]
        print(f"Mode: ファイル名の番号順（昇順）で結合します。")

    if not pdf_files:
        print("Error: 対象となるPDFファイルが見つかりません。")
        return

    # 2. 結合処理
    print("\n結合順序:")
    for path in pdf_files:
        if not os.path.exists(path):
            print(f"  [!] エラー: ファイルが存在しません。スキップします: {path}")
            continue
            
        print(f"  [+] {os.path.basename(path)}")
        try:
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
        except Exception as e:
            print(f"  [!] エラー: {path} の読み込み失敗 ({e})")

    # 3. 保存
    try:
        with open(args.output, "wb") as f:
            writer.write(f)
        print(f"\nSuccess: 結合完了 -> {args.output}")
    except Exception as e:
        print(f"Error: 保存に失敗しました。({e})")

def main():
    parser = argparse.ArgumentParser(description="PDF結合ツール (番号順/手動順対応)")
    parser.add_argument("--input_dir", default=".", help="PDFがあるフォルダ")
    parser.add_argument("--output", default="merged_output.pdf", help="出力ファイル名")
    parser.add_argument("--pattern", help="特定の文字を含むファイルのみ対象にする")
    parser.add_argument("--order", help="結合したい順にファイル名を指定 (例: b.pdf,a.pdf,c.pdf)")

    args = parser.parse_args()
    combine_pdfs(args)

if __name__ == "__main__":
    main()