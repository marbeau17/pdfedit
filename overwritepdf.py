import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import time
import os
import re
import warnings
import base64

# ★追加ライブラリのインポート (なければエラー表示)
try:
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st.error("機能拡張のため、追加ライブラリが必要です。ターミナルで `pip install streamlit-drawable-canvas` を実行してください。")
    st.stop()

# --- 1. 設定 & デザイン定数 ---
st.set_page_config(page_title="PDF Workshop: Continuous Master", layout="wide")

try:
    from google import genai
    from google.genai import types
except ImportError:
    st.error("ライブラリ 'google-genai' が見つかりません。 `pip install google-genai` を実行してください。")
    st.stop()

warnings.filterwarnings("ignore")

LOGO_FILENAME = "logo.png"
COLOR_NAVY = (0.11, 0.19, 0.36)
COLOR_GOLD = (0.81, 0.68, 0.44)
COLOR_GREY = (0.5, 0.5, 0.5)
DEFAULT_MASK_X = 106
DEFAULT_MASK_Y = 21

# --- モデル定義 ---
def get_vision_models():
    return ['models/nano-banana-pro-preview']

def get_generation_models():
    return ['models/nano-banana-pro-preview', 'models/gemini-3-pro-preview']

# --- 2. セッション状態の初期化 ---
if "logs" not in st.session_state: st.session_state.logs = []
if "review_data" not in st.session_state: st.session_state.review_data = {}
if "src_pdf_binary" not in st.session_state: st.session_state.src_pdf_binary = None
if "current_pdf_binary" not in st.session_state: st.session_state.current_pdf_binary = None
if "branding_logo_bytes" not in st.session_state: st.session_state.branding_logo_bytes = None

# --- 3. 共通関数 ---
def add_log(msg, level="INFO"):
    timestamp = time.strftime("%H:%M:%S")
    icons = {"INFO": "🔹", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️"}
    icon = icons.get(level, "🔹")
    st.session_state.logs.append(f"[{timestamp}] {icon} {msg}")

def save_xml_content(p_num):
    input_key = f"xml_{p_num}"
    if input_key in st.session_state:
        updated_xml = st.session_state[input_key]
        st.session_state.review_data[p_num]["xml"] = updated_xml
        st.session_state.review_data[p_num]["gen_img_bytes"] = None
        add_log(f"Page {p_num}: XMLの変更を保存しました。", "SUCCESS")

def parse_page_ranges(range_string):
    """ '1, 3-5' などの文字列をページ番号(1始まり)のセットに変換 """
    if not range_string: return None
    pages = set()
    parts = range_string.replace('、', ',').split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                for i in range(start, end + 1):
                    pages.add(i)
            except: pass
        elif part.isdigit():
            pages.add(int(part))
    return pages

# 🆕 ページサイズ統一処理
def resize_to_first_page(pdf_bytes):
    """全ページを1ページ目のサイズにリサイズする"""
    src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if len(src_doc) < 1:
        return pdf_bytes, "ページがありません"

    # 1ページ目のサイズを取得
    target_rect = src_doc[0].rect
    target_width, target_height = target_rect.width, target_rect.height
    
    # 出力用PDFを作成
    out_doc = fitz.open()

    for p_num, page in enumerate(src_doc):
        # ターゲットサイズで新しいページを作成
        new_page = out_doc.new_page(width=target_width, height=target_height)
        # 元のページをターゲット領域いっぱいに描画（拡大縮小）
        new_page.show_pdf_page(target_rect, src_doc, p_num)
    
    out_bytes = out_doc.tobytes(garbage=4, deflate=True)
    return out_bytes, f"サイズを {target_width:.0f}x{target_height:.0f} に統一しました"

def perform_watermark_removal(pdf_bytes, special_pages=[], margin_x=106, margin_y=21):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    log_messages = []
    for i, page in enumerate(doc):
        p_num = i + 1
        r = page.rect
        target_rect = fitz.Rect(r.width - margin_x, r.height - margin_y, r.width, r.height)
        if p_num in special_pages:
            probe_x = r.width - 5
            probe_y = 5
            mode_str = "右上"
        else:
            probe_x = max(0, target_rect.x0 - 2)
            probe_y = target_rect.y0 + 2
            mode_str = "隣接"
        probe_rect = fitz.Rect(probe_x, probe_y, probe_x + 1, probe_y + 1)
        pix = page.get_pixmap(clip=probe_rect, alpha=False)
        fill_color = (1, 1, 1)
        if pix.width > 0 and pix.height > 0:
            try:
                rgb = pix.pixel(0, 0)
                fill_color = (rgb[0]/255, rgb[1]/255, rgb[2]/255)
            except: pass
        page.add_redact_annot(target_rect, fill=fill_color)
        page.apply_redactions()
        log_messages.append(f"P{p_num}: {mode_str}マスク")
    out_bytes = doc.tobytes(garbage=4, deflate=True)
    return out_bytes, log_messages

def replace_area_with_image(page, rect_coords, image_data, keep_aspect=True):
    if not image_data: return False
    rect = fitz.Rect(rect_coords)
    
    # 塗りつぶし処理
    probe_x = max(0, rect.x0 - 5)
    probe_y = max(0, rect.y0 - 5)
    probe_rect = fitz.Rect(probe_x, probe_y, probe_x + 1, probe_y + 1)
    pix = page.get_pixmap(clip=probe_rect, alpha=False)
    fill_color = (1, 1, 1)
    if pix.width > 0 and pix.height > 0:
        try:
            rgb = pix.pixel(0, 0)
            fill_color = (rgb[0]/255, rgb[1]/255, rgb[2]/255)
        except: pass
    page.add_redact_annot(rect, fill=fill_color)
    page.apply_redactions()
    
    # 画像挿入
    page.insert_image(rect, stream=image_data, keep_proportion=keep_aspect)
    return True

def draw_branding_overlay(page, page_num, skip_first_num=False, skip_first_logo=False, settings=None, enable_logo=True, enable_page_num=True):
    w, h = page.rect.width, page.rect.height
    if settings is None:
        settings = {"logo_r": 30, "logo_t": 20, "logo_w": 100, "logo_h": 50, "page_r": 50, "page_b": 30}
    
    logo_data = st.session_state.branding_logo_bytes
    if not logo_data and os.path.exists(LOGO_FILENAME):
        try:
            with open(LOGO_FILENAME, "rb") as f: logo_data = f.read()
        except: logo_data = None

    # --- ロゴ & フッター表示 ---
    if enable_logo:
        if logo_data:
            if not (page_num == 1 and skip_first_logo):
                rect_x1 = w - settings["logo_r"]
                rect_x0 = rect_x1 - settings["logo_w"]
                rect_y0 = settings["logo_t"]
                rect_y1 = rect_y0 + settings["logo_h"]
                page.insert_image(fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1), stream=logo_data, keep_proportion=True)
        
        page.insert_text(fitz.Point(40, h - 30), "Strictly Private & Confidential ", fontsize=9, color=COLOR_GREY)
        page.insert_text(fitz.Point(40 + fitz.get_text_length("Strictly Private & Confidential ", fontsize=9), h - 30), "Internal Use Only", fontsize=9, color=COLOR_GOLD)
        page.insert_text((w - 195 if not (page_num == 1 and skip_first_num) else w - 130, h - 30), "©2026 Meets Consulting Inc.", fontsize=9, color=COLOR_GREY)

    # --- ページ番号表示 ---
    if enable_page_num:
        if not (page_num == 1 and skip_first_num):
            pg_x = w - settings["page_r"]
            pg_y = h - settings["page_b"]
            page.insert_text((pg_x, pg_y), str(page_num), fontsize=12, color=COLOR_NAVY)
            bar_x0 = pg_x - 15
            bar_x1 = pg_x - 13
            bar_y0 = pg_y - 12
            bar_y1 = pg_y + 5
            page.draw_rect(fitz.Rect(bar_x0, bar_y0, bar_x1, bar_y1), color=COLOR_NAVY, fill=COLOR_NAVY)

def render_fallback_text(page, xml_text):
    xml_text = xml_text.replace("```xml", "").replace("```", "").strip()
    t_match = re.search(r"<title>(.*?)</title>", xml_text, re.DOTALL)
    if t_match:
        page.insert_text(fitz.Point(50, 80), t_match.group(1).strip(), fontsize=22, color=(0,0,0))
        page.draw_line(fitz.Point(50, 95), fitz.Point(page.rect.width - 50, 95), color=(0,0,0), width=1)

# --- 4. API処理 ---
def call_vision_api(client, img_data):
    models = get_vision_models()
    prompt = "Analyze slide to XML. JAPANESE ONLY."
    for m in models:
        try:
            res = client.models.generate_content(model=m, contents=[prompt, types.Part.from_bytes(data=img_data, mime_type='image/png')])
            if res.text: return res.text
        except: continue
    return None

def call_generation_api(client, xml_prompt):
    models = get_generation_models()
    prompt = f"Create a slide image based on XML. WHITE background. XML: {xml_prompt}"
    for m in models:
        try:
            res = client.models.generate_content(model=m, contents=prompt)
            if res.candidates and res.candidates[0].content.parts:
                for part in res.candidates[0].content.parts:
                    if part.inline_data: return part.inline_data.data
        except: continue
    return None

# --- 5. メインUI ---
def main():
    st.title("🚀 PDF Iterative Workshop: Continuous Master")

    with st.sidebar:
        st.header("1. 認証 & 設定")
        api_key = st.text_input("Gemini API Key", type="password")
        file = st.file_uploader("PDFを選択", type=["pdf"])
        
        # --- PDF前処理セクション ---
        if file:
            st.write("---")
            # 1. ページサイズ統一 (NEW)
            with st.expander("📏 ページサイズ統一", expanded=False):
                st.caption("全ページを1ページ目のサイズ(縦横)に強制リサイズします。")
                if st.button("⚡ 全ページをP1サイズに統一"):
                    if not st.session_state.src_pdf_binary: st.session_state.src_pdf_binary = file.read()
                    try:
                        new_pdf, msg = resize_to_first_page(st.session_state.src_pdf_binary)
                        st.session_state.src_pdf_binary = new_pdf
                        st.session_state.current_pdf_binary = None
                        add_log(msg, "SUCCESS")
                        st.rerun()
                    except Exception as e:
                        add_log(f"リサイズエラー: {str(e)}", "ERROR")

            # 2. 透かし除去
            with st.expander("🛠 透かし・不要エリア除去", expanded=False):
                st.caption("右下の特定エリアを周囲の色で塗りつぶします。")
                c_mx, c_my = st.columns(2)
                with c_mx: mask_x = st.number_input("右端からの幅(X)", value=DEFAULT_MASK_X, step=1)
                with c_my: mask_y = st.number_input("下端からの高さ(Y)", value=DEFAULT_MASK_Y, step=1)
                special_page_input = st.text_input("例外ページ (例: 1, 3)", placeholder="1, 3")
                if st.button("⚡ マスク除去を実行", key="btn_mask"):
                    if not st.session_state.src_pdf_binary: st.session_state.src_pdf_binary = file.read()
                    try:
                        sp_pages = [int(p.strip()) for p in special_page_input.replace('、', ',').split(',') if p.strip().isdigit()]
                        new_pdf, logs = perform_watermark_removal(st.session_state.src_pdf_binary, sp_pages, mask_x, mask_y)
                        st.session_state.src_pdf_binary = new_pdf
                        st.session_state.current_pdf_binary = None
                        add_log(f"マスク処理完了: 全{len(logs)}ページ", "SUCCESS")
                        st.rerun()
                    except Exception as e: add_log(f"マスクエラー: {str(e)}", "ERROR")

        st.write("---")
        page_sel = st.text_input("対象ページ (例: 5, 7)", value="1")
        st.write("---")
        
        # ロゴ設定
        st.subheader("ロゴ設定")
        logo_dir = "logo"
        logo_files = [f for f in os.listdir(logo_dir) if f.lower().endswith(".png")] if os.path.exists(logo_dir) else []
        if logo_files:
            selected_logo_name = st.selectbox("ロゴを選択", logo_files)
            logo_path = os.path.join(logo_dir, selected_logo_name)
            st.image(logo_path, width=100)
            with open(logo_path, "rb") as f: st.session_state.branding_logo_bytes = f.read()
        elif os.path.exists(LOGO_FILENAME):
            with open(LOGO_FILENAME, "rb") as f: st.session_state.branding_logo_bytes = f.read()

        # 位置調整
        with st.expander("🎨 ブランディング位置調整", expanded=False):
            c_logo, c_page = st.columns(2)
            with c_logo:
                p_logo_r = st.number_input("ロゴ右余白", value=30, step=5)
                p_logo_t = st.number_input("ロゴ上余白", value=20, step=5)
                p_logo_w = st.number_input("ロゴ幅", value=100, step=5)
                p_logo_h = st.number_input("ロゴ高さ", value=50, step=5)
            with c_page:
                p_page_r = st.number_input("頁番号右余白", value=50, step=5)
                p_page_b = st.number_input("頁番号下余白", value=30, step=5)
            brand_settings = {"logo_r": p_logo_r, "logo_t": p_logo_t, "logo_w": p_logo_w, "logo_h": p_logo_h, "page_r": p_page_r, "page_b": p_page_b}

        # 🆕 エリア画像置換設定 (Canvas導入・Base64修正・サイズ合わせ)
        with st.expander("🖼️ エリア画像置換 (マウス操作)", expanded=True):
            st.caption("対象ページを選択し、画像上で「置換したいエリア」をマウスで囲ってください。")
            enable_replace = st.checkbox("画像置換を有効にする")
            
            keep_aspect = st.checkbox("アスペクト比を維持する", value=False, help="ON: 元画像の形を保ちます。 OFF: 選択範囲いっぱいに引き伸ばします。")
            rep_page_str = st.text_input("対象ページ (1ページのみ)", value="1")
            
            rep_x, rep_y, rep_w, rep_h = 30, 30, 250, 80 

            if enable_replace and st.session_state.src_pdf_binary:
                try:
                    doc_cv = fitz.open(stream=st.session_state.src_pdf_binary, filetype="pdf")
                    target_p_idx = int(re.split(r'[,\s]+', rep_page_str.strip())[0]) - 1
                    
                    if 0 <= target_p_idx < len(doc_cv):
                        page_cv = doc_cv[target_p_idx]
                        pix_cv = page_cv.get_pixmap(dpi=72)
                        img_cv = Image.frombytes("RGB", [pix_cv.width, pix_cv.height], pix_cv.samples)
                        
                        buffered = io.BytesIO()
                        img_cv.save(buffered, format="PNG")
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        bg_image_url = f"data:image/png;base64,{img_str}"
                        
                        st.markdown("👇 **画像の上でマウスをドラッグして範囲指定してください**")
                        canvas_result = st_canvas(
                            fill_color="rgba(255, 0, 0, 0.2)",
                            stroke_width=2,
                            stroke_color="#ff0000",
                            background_image=bg_image_url,
                            update_streamlit=True,
                            height=pix_cv.height,
                            width=pix_cv.width,
                            drawing_mode="rect",
                            key="canvas_replace",
                        )

                        if canvas_result.json_data is not None and len(canvas_result.json_data["objects"]) > 0:
                            obj = canvas_result.json_data["objects"][-1]
                            rep_x = int(obj["left"])
                            rep_y = int(obj["top"])
                            rep_w = int(obj["width"] * obj["scaleX"])
                            rep_h = int(obj["height"] * obj["scaleY"])
                            st.success(f"範囲選択中: x={rep_x}, y={rep_y}, w={rep_w}, h={rep_h}")
                    else:
                        st.warning("ページ番号が範囲外です")
                except Exception as e:
                    st.error(f"プレビューエラー: {e}")

        # --- ブランディング設定 ---
        st.subheader("ブランディング適用設定")
        branding_target_input = st.text_input("適用対象ページ (空欄で全ページ)", placeholder="例: 1-5, 10")
        
        c_b1, c_b2 = st.columns(2)
        with c_b1: enable_logo_draw = st.checkbox("ロゴ・フッターを表示", value=True)
        with c_b2: enable_page_num_draw = st.checkbox("ページ番号を表示", value=True)

        skip_first_num = st.checkbox("最初のページ番号非表示", value=True)
        skip_first_logo = st.checkbox("最初のページロゴ非表示", value=True)

        # 💡 ① 解析スタート
        if st.button("① 解析スタート", type="primary", disabled=not (api_key and file)):
            try:
                client = genai.Client(api_key=api_key.strip())
                if not st.session_state.src_pdf_binary: st.session_state.src_pdf_binary = file.read()
                doc = fitz.open(stream=st.session_state.src_pdf_binary, filetype="pdf")
                indices = [int(p)-1 for p in page_sel.replace('-',',').split(',') if p.strip().isdigit()]
                for idx in indices:
                    if 0 <= idx < len(doc):
                        p_num = idx + 1
                        with st.spinner(f"P{p_num} 解析中..."):
                            add_log(f"P{p_num} 解析開始...", "INFO")
                            pix = doc[idx].get_pixmap(dpi=150)
                            xml = call_vision_api(client, pix.tobytes("png"))
                            if xml:
                                st.session_state.review_data[p_num] = {"idx": idx, "xml": xml, "orig_img": pix.tobytes("png"), "w": doc[idx].rect.width, "h": doc[idx].rect.height, "gen_img_bytes": None}
                                add_log(f"P{p_num} 解析成功", "SUCCESS")
                            else: add_log(f"P{p_num} 解析失敗", "ERROR")
                st.rerun()
            except Exception as e: add_log(f"解析エラー: {str(e)}", "ERROR")

        # 💡 ② PDF生成
        if st.session_state.review_data:
            st.write("---")
            if st.button("② PDFを生成・更新 (Execute)", type="primary", use_container_width=True):
                try:
                    client = genai.Client(api_key=api_key.strip())
                    doc = fitz.open(stream=st.session_state.src_pdf_binary, filetype="pdf")
                    for p_num, data in sorted(st.session_state.review_data.items()):
                        with st.spinner(f"P{p_num} 画像生成中..."):
                            if not data.get("gen_img_bytes"):
                                img_bytes = call_generation_api(client, data["xml"])
                                st.session_state.review_data[p_num]["gen_img_bytes"] = img_bytes
                            else: img_bytes = data["gen_img_bytes"]
                            page = doc[data["idx"]]
                            page.clean_contents()
                            page.draw_rect(page.rect, color=(1,1,1), fill=(1,1,1))
                            if img_bytes:
                                margin = 60 if enable_logo_draw else 0
                                page.insert_image(fitz.Rect(0, margin, data["w"], data["h"]-40), stream=img_bytes)
                            else: render_fallback_text(page, data["xml"])
                            
                            draw_branding_overlay(page, p_num, skip_first_num, skip_first_logo, brand_settings, enable_logo=enable_logo_draw, enable_page_num=enable_page_num_draw)
                            st.session_state.review_data[p_num]["gen_img_preview"] = page.get_pixmap(dpi=150).tobytes("png")
                    st.session_state.current_pdf_binary = doc.tobytes()
                    add_log("🏁 生成完了", "SUCCESS")
                    st.rerun()
                except Exception as e: add_log(f"生成エラー: {str(e)}", "ERROR")

        # 💡 ③ ブランディングのみ適用
        st.write("---")
        if st.button("⚡ 元画像のままブランディングのみ適用", disabled=not file):
            try:
                if not st.session_state.src_pdf_binary: st.session_state.src_pdf_binary = file.read()
                doc = fitz.open(stream=st.session_state.src_pdf_binary, filetype="pdf")
                
                rep_pages = []
                if enable_replace and rep_page_str:
                    try: rep_pages = [int(re.split(r'[,\s]+', rep_page_str.strip())[0])]
                    except: pass

                branding_targets = None
                if branding_target_input: branding_targets = parse_page_ranges(branding_target_input)

                for i in range(len(doc)):
                    p_num = i + 1
                    page = doc[i]
                    if enable_replace and p_num in rep_pages:
                        rect_coords = (rep_x, rep_y, rep_x + rep_w, rep_y + rep_h)
                        if replace_area_with_image(page, rect_coords, st.session_state.branding_logo_bytes, keep_aspect=keep_aspect):
                            add_log(f"P{p_num}: エリア画像置換", "INFO")
                    
                    if branding_targets is None or p_num in branding_targets:
                        draw_branding_overlay(page, p_num, skip_first_num, skip_first_logo, brand_settings, enable_logo=enable_logo_draw, enable_page_num=enable_page_num_draw)
                
                st.session_state.current_pdf_binary = doc.tobytes()
                add_log("🏁 ブランディング適用完了", "SUCCESS")
                st.rerun()
            except Exception as e: add_log(f"ブランディングエラー: {str(e)}", "ERROR")

        # 💡 ④ ベース更新
        if st.session_state.current_pdf_binary:
            st.write("---")
            if st.button("🔄 このPDFをベースに設定して継続", use_container_width=True):
                st.session_state.src_pdf_binary = st.session_state.current_pdf_binary
                st.session_state.review_data = {} 
                st.session_state.current_pdf_binary = None
                add_log("📥 ベース更新完了", "SUCCESS")
                st.rerun()
            st.download_button("📥 完成版PDFを保存", st.session_state.current_pdf_binary, "workshop_final.pdf", use_container_width=True)

    if st.session_state.review_data:
        for p_num, data in sorted(st.session_state.review_data.items()):
            with st.expander(f"📄 Page {p_num} 編集", expanded=True):
                c1, c2, c3 = st.columns([1,1,1])
                with c1: st.image(data["orig_img"], caption="元画像")
                with c2:
                    st.text_area(f"XML P{p_num}", value=data["xml"], height=400, key=f"xml_{p_num}")
                    if st.button(f"💾 保存 P{p_num}", key=f"save_{p_num}"):
                        save_xml_content(p_num)
                        st.rerun()
                with c3:
                    if "gen_img_preview" in data: st.image(data["gen_img_preview"], caption="結果")
                    else: st.info("生成待ち")

    with st.expander("🛠 システムログ", expanded=True):
        if st.button("ログクリア"): st.session_state.logs=[]; st.rerun()
        st.text("\n".join(st.session_state.logs[::-1]))

if __name__ == "__main__":
    try: main()
    except Exception as e: st.error(f"起動エラー: {e}")