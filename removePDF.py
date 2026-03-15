import argparse
import os
from pypdf import PdfReader, PdfWriter

def parse_page_ranges(range_string):
    """
    "1,3-5, 8" のような文字列を解析し、0始まりのインデックスのセットを返す。
    例: "1,3-5" -> {0, 2, 3, 4}
    """
    pages = set()
    parts = range_string.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                # ユーザーは1始まり、Pythonは0始まりなので -1 する
                # rangeのエンドは含まれないので、endはそのままでOK (実質 end+1-1)
                for i in range(start - 1, end):
                    pages.add(i)
            except ValueError:
                print(f"警告: 不正な範囲指定です -> {part}")
        elif part.isdigit():
            # 1始まりを0始まりに変換
            pages.add(int(part) - 1)
            
    return pages

def remove_pages(input_file, output_file, delete_str):
    if not os.path.exists(input_file):
        print(f"エラー: ファイルが見つかりません -> {input_file}")
        return

    try:
        reader = PdfReader(input_file)
        writer = PdfWriter()
        
        # 削除対象のページインデックスを取得
        delete_indices = parse_page_ranges(delete_str)
        
        total_pages = len(reader.pages)
        print(f"総ページ数: {total_pages}")
        print(f"削除対象: {delete_str} (内部インデックス: {sorted(list(delete_indices))})")
        
        kept_count = 0
        for i in range(total_pages):
            if i in delete_indices:
                print(f"  - ページ {i+1} をスキップ（削除）しました。")
                continue
            
            writer.add_page(reader.pages[i])
            kept_count += 1
            
        # 何も残らなかった場合の警告
        if kept_count == 0:
            print("警告: 全てのページが削除対象となりました。空のPDFは作成されません。")
            return

        with open(output_file, "wb") as f:
            writer.write(f)
            
        print(f"\n完了: {output_file} を作成しました。（{kept_count}ページ）")

    except Exception as e:
        print(f"エラーが発生しました: {e}")

def main():
    parser = argparse.ArgumentParser(description="PDFから指定ページを削除するツール")
    parser.add_argument("input_pdf", help="入力PDFファイルのパス")
    parser.add_argument("delete_pages", help="削除したいページ番号 (例: 1,3-5)")
    parser.add_argument("--output", "-o", help="出力ファイル名 (指定がない場合は '_removed.pdf' が付く)")

    args = parser.parse_args()

    # 出力ファイル名の決定
    if args.output:
        out_path = args.output
    else:
        base, ext = os.path.splitext(args.input_pdf)
        out_path = f"{base}_removed{ext}"

    remove_pages(args.input_pdf, out_path, args.delete_pages)

if __name__ == "__main__":
    main()