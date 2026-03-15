"""
Core PDF manipulation service using PyMuPDF (fitz).

All methods are static and operate on raw bytes, performing no file I/O.
"""

from __future__ import annotations

import fitz  # PyMuPDF


class PDFService:
    """Stateless service that consolidates all PDF operations."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open(pdf_bytes: bytes) -> fitz.Document:
        """Open a PDF from bytes."""
        return fitz.open(stream=pdf_bytes, filetype="pdf")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def get_page_count(pdf_bytes: bytes) -> int:
        """Return the number of pages in the PDF.

        Args:
            pdf_bytes: Raw PDF content.

        Returns:
            Page count as an integer.
        """
        doc = None
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            return doc.page_count
        except Exception:
            return 0
        finally:
            if doc:
                doc.close()

    @staticmethod
    def get_page_thumbnail(pdf_bytes: bytes, page_num: int, dpi: int = 72) -> bytes:
        """Render a single page as a PNG thumbnail.

        Args:
            pdf_bytes: Raw PDF content.
            page_num: 1-based page number.
            dpi: Resolution in dots-per-inch (default 72).

        Returns:
            PNG image bytes.
        """
        doc = None
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_index = page_num - 1
            if page_index < 0 or page_index >= doc.page_count:
                raise ValueError(
                    f"page_num {page_num} out of range (1..{doc.page_count})"
                )
            page = doc.load_page(page_index)
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            return pix.tobytes("png")
        finally:
            if doc:
                doc.close()

    @staticmethod
    def remove_pages(pdf_bytes: bytes, pages_to_remove: set[int]) -> bytes:
        """Delete the specified pages from a PDF.

        Pages are removed in reverse order to avoid index-shift issues.

        Args:
            pdf_bytes: Raw PDF content.
            pages_to_remove: Set of 1-based page numbers to delete.

        Returns:
            Modified PDF bytes.
        """
        doc = None
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            # Convert to 0-based and sort descending
            indices = sorted(
                [p - 1 for p in pages_to_remove if 0 < p <= doc.page_count],
                reverse=True,
            )
            for idx in indices:
                doc.delete_page(idx)
            return doc.tobytes(garbage=4, deflate=True)
        finally:
            if doc:
                doc.close()

    @staticmethod
    def reorder_pages(pdf_bytes: bytes, new_order: list[int]) -> bytes:
        """Reorder PDF pages according to *new_order*.

        Args:
            pdf_bytes: Raw PDF content.
            new_order: List of 1-based page numbers in the desired order.
                       For example ``[3, 1, 2]`` moves page 3 to the front.

        Returns:
            Reordered PDF bytes.
        """
        src_doc = None
        dst_doc = None
        try:
            src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            dst_doc = fitz.open()  # new empty PDF

            for page_num in new_order:
                page_index = page_num - 1
                if page_index < 0 or page_index >= src_doc.page_count:
                    raise ValueError(
                        f"page_num {page_num} out of range (1..{src_doc.page_count})"
                    )
                dst_doc.insert_pdf(src_doc, from_page=page_index, to_page=page_index)

            return dst_doc.tobytes(garbage=4, deflate=True)
        finally:
            if dst_doc:
                dst_doc.close()
            if src_doc:
                src_doc.close()

    @staticmethod
    def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
        """Merge multiple PDFs into a single document.

        Args:
            pdf_bytes_list: Ordered list of raw PDF contents.

        Returns:
            Merged PDF bytes.
        """
        merged = None
        docs: list[fitz.Document] = []
        try:
            merged = fitz.open()  # new empty PDF

            for pdf_bytes in pdf_bytes_list:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                docs.append(doc)
                merged.insert_pdf(doc)

            return merged.tobytes(garbage=4, deflate=True)
        finally:
            for d in docs:
                d.close()
            if merged:
                merged.close()

    @staticmethod
    def optimize(pdf_bytes: bytes) -> tuple[bytes, int, int]:
        """Optimize a PDF by garbage-collecting and deflating.

        Args:
            pdf_bytes: Raw PDF content.

        Returns:
            Tuple of (optimized_bytes, original_size, optimized_size).
        """
        doc = None
        try:
            original_size = len(pdf_bytes)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            optimized = doc.tobytes(garbage=4, deflate=True)
            optimized_size = len(optimized)
            return optimized, original_size, optimized_size
        finally:
            if doc:
                doc.close()

    @staticmethod
    def resize_to_first_page(pdf_bytes: bytes) -> bytes:
        """Resize every page so that it matches the first page's dimensions.

        The original page content is scaled into the target rectangle using
        ``show_pdf_page``.

        Args:
            pdf_bytes: Raw PDF content.

        Returns:
            PDF bytes with all pages resized.
        """
        src_doc = None
        dst_doc = None
        try:
            src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if src_doc.page_count == 0:
                return pdf_bytes

            first_rect = src_doc[0].rect
            target_width = first_rect.width
            target_height = first_rect.height

            dst_doc = fitz.open()  # new empty PDF

            for page_index in range(src_doc.page_count):
                new_page = dst_doc.new_page(
                    width=target_width, height=target_height
                )
                new_page.show_pdf_page(
                    new_page.rect, src_doc, pno=page_index
                )

            return dst_doc.tobytes(garbage=4, deflate=True)
        finally:
            if dst_doc:
                dst_doc.close()
            if src_doc:
                src_doc.close()

    @staticmethod
    def remove_watermark(
        pdf_bytes: bytes,
        margin_x: int = 106,
        margin_y: int = 21,
        special_pages: set[int] | None = None,
    ) -> bytes:
        """Remove a watermark by sampling adjacent colour and covering with a redaction.

        For each page the method builds a rectangular strip at the bottom of
        the page (controlled by *margin_x* / *margin_y*), samples the pixel
        colour just outside that strip, and applies a redaction annotation
        filled with the sampled colour.

        Args:
            pdf_bytes: Raw PDF content.
            margin_x: Horizontal inset from page edges (default 106).
            margin_y: Height of the strip from the bottom (default 21).
            special_pages: Optional set of 1-based page numbers that need
                different treatment (reserved for future use).

        Returns:
            Modified PDF bytes with watermarks removed.
        """
        doc = None
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if special_pages is None:
                special_pages = set()

            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                rect = page.rect

                # Define the watermark strip at the bottom of the page
                wm_rect = fitz.Rect(
                    margin_x,
                    rect.height - margin_y,
                    rect.width - margin_x,
                    rect.height,
                )

                # Sample colour just above the watermark strip
                sample_y = max(0, rect.height - margin_y - 1)
                sample_rect = fitz.Rect(
                    margin_x, sample_y, margin_x + 1, sample_y + 1
                )
                pix = page.get_pixmap(clip=sample_rect)
                pixel = pix.pixel(0, 0)  # (r, g, b) or (r, g, b, a)
                fill_color = tuple(c / 255.0 for c in pixel[:3])

                # Add redaction annotation over the watermark area
                annot = page.add_redact_annot(wm_rect)
                annot.set_colors(fill=fill_color)
                annot.update()
                page.apply_redactions()

            return doc.tobytes(garbage=4, deflate=True)
        finally:
            if doc:
                doc.close()

    @staticmethod
    def get_page_info(pdf_bytes: bytes) -> list[dict]:
        """Return dimensional information for every page.

        Args:
            pdf_bytes: Raw PDF content.

        Returns:
            List of dicts, each containing ``page_num`` (1-based),
            ``width``, and ``height``.
        """
        doc = None
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            info: list[dict] = []
            for i in range(doc.page_count):
                page = doc.load_page(i)
                rect = page.rect
                info.append(
                    {
                        "page_num": i + 1,
                        "width": rect.width,
                        "height": rect.height,
                    }
                )
            return info
        except Exception:
            return []
        finally:
            if doc:
                doc.close()
