import argparse
import os
from pypdf import PdfReader, PdfWriter

def parse_page_order(order_string):
    """
    "1,3-5" のような文字列を解析し、ページ番号(1始まり)のリストを返す。
    """
    pages = []
    if not order_string:
        return pages
        
    parts = order_string.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                step = 1 if start <= end else -1
                for i in range(start, end + step, step):
                    pages.append(i)
            except ValueError:
                pass
        elif part.isdigit():
            pages.append(int(part))
    return pages

def reorder_with_remaining(input_path, output_path, order_str):
    if not os.path.exists(input_path):
        print(f"エラー: ファイルが見つかりません -> {input_path}")
        return

    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        total_pages = len(reader.pages)
        
        # 1. ユーザーが指定した「先頭に来るページ」リスト
        specified_pages = parse_page_order(order_str)
        
        # 2. 指定ページの追加
        # (1始まりの番号を0始まりのインデックスに変換して処理)
        processed_indices = set()
        
        print(f"--- 処理開始 ---")
        print(f"先頭に移動: {specified_pages}")
        
        for p_num in specified_pages:
            idx = p_num - 1
            if 0 <= idx < total_pages:
                writer.add_page(reader.pages[idx])
                processed_indices.add(idx)
            else:
                print(f"警告: 指定ページ {p_num} は存在しません。スキップします。")

        # 3. 残りのページを順番に追加
        # (すでに指定されたページ以外を、元の順序で追記)
        print("残りのページを追加中...")
        for i in range(total_pages):
            if i not in processed_indices:
                writer.add_page(reader.pages[i])

        # 4. 保存
        with open(output_path, "wb") as f:
            writer.write(f)
            
        print(f"完了: {output_path} (全{len(writer.pages)}ページ)")

    except Exception as e:
        print(f"エラー: {e}")

def main():
    parser = argparse.ArgumentParser(description="PDFの指定ページを先頭にし、残りを後に続けるツール")
    parser.add_argument("input_pdf", help="入力PDFファイル")
    parser.add_argument("order", help="先頭に持ってくるページ番号 (例: '10, 5')")
    parser.add_argument("--output", "-o", help="出力ファイル名")

    args = parser.parse_args()

    if args.output:
        out_path = args.output
    else:
        base, ext = os.path.splitext(args.input_pdf)
        out_path = f"{base}_reordered_full{ext}"

    reorder_with_remaining(args.input_pdf, out_path, args.order)

if __name__ == "__main__":
    main()