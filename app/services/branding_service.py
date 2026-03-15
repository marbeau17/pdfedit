"""Branding overlay service for PDF pages."""
import os
import fitz


# Brand colors
COLOR_NAVY = (0.11, 0.19, 0.36)
COLOR_GOLD = (0.81, 0.68, 0.44)
COLOR_GREY = (0.5, 0.5, 0.5)


class BrandingService:
    """Apply branding overlays to PDF pages."""

    @staticmethod
    def apply_branding(
        pdf_bytes: bytes,
        logo_bytes: bytes | None = None,
        target_pages: set[int] | None = None,
        enable_logo: bool = True,
        enable_page_num: bool = True,
        skip_first_logo: bool = True,
        skip_first_num: bool = True,
        logo_right_margin: int = 30,
        logo_top_margin: int = 20,
        logo_width: int = 100,
        logo_height: int = 50,
        page_num_right: int = 50,
        page_num_bottom: int = 30,
        footer_text: str = "Strictly Private & Confidential",
        copyright_text: str = "\u00a92026 Meets Consulting Inc.",
    ) -> bytes:
        """Apply branding to specified pages of a PDF.

        Args:
            pdf_bytes: Input PDF as bytes
            logo_bytes: Logo image as bytes (PNG/JPG), or None
            target_pages: Set of 1-based page numbers to apply branding to. None = all pages.
            enable_logo: Whether to draw logo and footer
            enable_page_num: Whether to draw page numbers
            skip_first_logo: Skip logo on page 1
            skip_first_num: Skip page number on page 1
            logo_right_margin: Distance from right edge to logo right edge
            logo_top_margin: Distance from top to logo top
            logo_width: Logo width in points
            logo_height: Logo height in points
            page_num_right: Page number X position from right edge
            page_num_bottom: Page number Y position from bottom edge
            footer_text: Footer text (left side)
            copyright_text: Copyright text (right side)

        Returns:
            Modified PDF as bytes
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        try:
            for i in range(len(doc)):
                page_num = i + 1

                # Skip if not in target pages
                if target_pages is not None and page_num not in target_pages:
                    continue

                page = doc[i]
                w, h = page.rect.width, page.rect.height

                # --- Logo ---
                if enable_logo:
                    if logo_bytes and not (page_num == 1 and skip_first_logo):
                        rect_x1 = w - logo_right_margin
                        rect_x0 = rect_x1 - logo_width
                        rect_y0 = logo_top_margin
                        rect_y1 = rect_y0 + logo_height
                        page.insert_image(
                            fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1),
                            stream=logo_bytes,
                            keep_proportion=True,
                        )

                    # Footer text (left side)
                    footer_y = h - 30
                    page.insert_text(
                        fitz.Point(40, footer_y),
                        footer_text + " ",
                        fontsize=9,
                        color=COLOR_GREY,
                    )
                    footer_width = fitz.get_text_length(footer_text + " ", fontsize=9)
                    page.insert_text(
                        fitz.Point(40 + footer_width, footer_y),
                        "Internal Use Only",
                        fontsize=9,
                        color=COLOR_GOLD,
                    )

                    # Copyright text (right side)
                    cr_x = w - 195 if not (page_num == 1 and skip_first_num) else w - 130
                    page.insert_text(
                        (cr_x, footer_y),
                        copyright_text,
                        fontsize=9,
                        color=COLOR_GREY,
                    )

                # --- Page number ---
                if enable_page_num and not (page_num == 1 and skip_first_num):
                    pg_x = w - page_num_right
                    pg_y = h - page_num_bottom
                    page.insert_text((pg_x, pg_y), str(page_num), fontsize=12, color=COLOR_NAVY)
                    # Vertical bar before page number
                    bar_x0 = pg_x - 15
                    bar_x1 = pg_x - 13
                    bar_y0 = pg_y - 12
                    bar_y1 = pg_y + 5
                    page.draw_rect(
                        fitz.Rect(bar_x0, bar_y0, bar_x1, bar_y1),
                        color=COLOR_NAVY,
                        fill=COLOR_NAVY,
                    )

            result = doc.tobytes(garbage=4, deflate=True)
        finally:
            doc.close()

        return result

    @staticmethod
    def parse_page_ranges(s: str) -> set[int] | None:
        """Parse page range string like '1-5, 10' to set of ints. Returns None if empty."""
        if not s or not s.strip():
            return None
        pages = set()
        for part in s.replace("\u3001", ",").split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = map(int, part.split("-", 1))
                    pages.update(range(start, end + 1))
                except ValueError:
                    pass
            elif part.isdigit():
                pages.add(int(part))
        return pages if pages else None
