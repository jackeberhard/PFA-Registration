#!/usr/bin/env python3
"""
PRT Score Sheet Generator — NAVPERS 6110/11 (Rev. 12-2025)

Reads a CSV of PFA registrations, groups by Date/Day/TimeSlot,
sorts alphabetically by last name, and overlays participant data
onto the official PRT Score Sheet PDF form.

Usage:
    python pfa_form_generator.py <registrations.csv> <blank_form.pdf> [output.pdf]

Requirements:
    pip install pypdf reportlab
"""

import csv
import os
import sys
import math
import webbrowser
import subprocess
from collections import defaultdict
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Image-coordinate layout of NAVPERS 6110/11 (Rev. 12-2025)
# Measured from 1000 x 772 pixel rendering of the form
# ---------------------------------------------------------------------------
IMG_W, IMG_H = 1000, 772

# Vertical column boundaries (image-pixel x coordinates)
# Columns: #, Name, Sex, Rank/Rate, Age, Push-Ups, Plank, *Cardio, Cardio Time, Signature
COL_X = [44, 68, 318, 363, 409, 454, 499, 545, 625, 704, 954]

# Data row boundaries (image-pixel y coordinates)
ROW_Y_TOPS = [
    236, 258, 281, 304, 327, 349, 372, 394, 417, 440,
    462, 485, 508, 531, 553, 576, 599, 622, 644, 667,
]
ROW_Y_BOTTOMS = [
    258, 281, 304, 327, 349, 372, 394, 417, 440, 462,
    485, 508, 531, 553, 576, 599, 622, 644, 667, 690,
]
ROWS_PER_PAGE = 20

# PRT Date field location (image pixels)
PRT_DATE_X = 110
PRT_DATE_Y_MID = 121

# PDF page size (landscape letter)
PDF_W, PDF_H = landscape(letter)  # 792 x 612


def img_to_pdf(ix, iy):
    """Convert image pixel coords to PDF coords (origin bottom-left)."""
    pdf_x = ix * (PDF_W / IMG_W)
    pdf_y = PDF_H - (iy * (PDF_H / IMG_H))
    return pdf_x, pdf_y


def create_overlay(participants, date_str, timeslot_str, page_idx):
    """Create a single-page transparent PDF overlay with participant data."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(letter))

    # --- Fill PRT Date ---
    dx, dy = img_to_pdf(PRT_DATE_X, PRT_DATE_Y_MID)
    c.setFont("Helvetica", 8)
    c.drawString(dx, dy - 3, f"{date_str} / {timeslot_str}")

    # --- Fill data rows ---
    start = page_idx * ROWS_PER_PAGE
    end = start + ROWS_PER_PAGE
    page_participants = participants[start:end]

    for row_idx, p in enumerate(page_participants):
        row_mid_y = (ROW_Y_TOPS[row_idx] + ROW_Y_BOTTOMS[row_idx]) / 2
        name_str = f"{p['LastName']}, {p['FirstName']}, {p['MI']}"

        # (column_index, text, font_size, centered)
        cells = [
            (0, str(row_idx + 1 + start), 7, True),   # #
            (1, name_str, 7, False),                    # Name (Last, First, MI)
            (2, p['Sex'], 7, True),                     # Sex (M/F)
            (3, p['Rank'], 6.5, True),                  # Rank/Rate
            (4, p['Age'], 7, True),                     # Age
            # 5 = Number of Push Ups   (blank — filled by hand)
            # 6 = Forearm Plank Time   (blank — filled by hand)
            (7, p['Event'], 7, True),                   # *Cardio Modality
            # 8 = Cardio Time/Calories (blank — filled by hand)
            # 9 = Member's Signature   (blank — signed on site)
        ]

        for col_idx, text, font_size, centered in cells:
            col_left = COL_X[col_idx]
            col_right = COL_X[col_idx + 1]

            if centered:
                cx = (col_left + col_right) / 2
                px, py = img_to_pdf(cx, row_mid_y)
                c.setFont("Helvetica", font_size)
                c.drawCentredString(px, py - 3, text)
            else:
                px, py = img_to_pdf(col_left + 4, row_mid_y)
                c.setFont("Helvetica", font_size)
                c.drawString(px, py - 3, text)

    c.save()
    buf.seek(0)
    return buf


def load_csv(filepath):
    """Load CSV and return list of dicts, stripping BOM and whitespace from headers."""
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # Strip whitespace/BOM from header names
        reader.fieldnames = [name.strip().lstrip('\ufeff') for name in reader.fieldnames]
        records = []
        for row in reader:
            # Also strip whitespace from all keys and values
            cleaned = {k.strip(): (v.strip() if v else '') for k, v in row.items()}
            records.append(cleaned)
        return records


def generate_pdf(csv_path, form_path, output_path, filters=None):
    """Overlay data onto the blank form for each Date/Day/TimeSlot group.

    filters is a dict with optional keys: 'date', 'day', 'timeslot', 'event'.
    Each value is a list of acceptable values (case-insensitive).
    """
    records = load_csv(csv_path)
    filters = filters or {}

    # Apply filters
    if filters:
        filtered = []
        for r in records:
            keep = True
            if 'date' in filters:
                if r['Date'].strip().upper() not in filters['date']:
                    keep = False
            if 'day' in filters:
                if r['Day'].strip().upper() not in filters['day']:
                    keep = False
            if 'timeslot' in filters:
                if r['TimeSlot'].strip().upper() not in filters['timeslot']:
                    keep = False
            if 'event' in filters:
                if r['Event'].strip().upper() not in filters['event']:
                    keep = False
            if keep:
                filtered.append(r)
        records = filtered

    if not records:
        print("No participants match the given filters.")
        sys.exit(0)

    # Group by (Date, Day, TimeSlot)
    groups = defaultdict(list)
    for r in records:
        key = (r['Date'].strip(), r['Day'].strip(), r['TimeSlot'].strip())
        groups[key].append(r)

    sorted_keys = sorted(groups.keys(), key=lambda k: (k[0], k[2]))

    writer = PdfWriter()
    total_pages = 0

    for key in sorted_keys:
        date_str, day_str, timeslot_str = key
        participants = groups[key]

        # Sort by cardio modality (Event) first, then alphabetically by last name
        participants.sort(key=lambda p: (
            p['Event'].strip().upper(),
            p['LastName'].strip().upper(),
            p['FirstName'].strip().upper(),
        ))

        num_pages = max(1, math.ceil(len(participants) / ROWS_PER_PAGE))

        for page_idx in range(num_pages):
            overlay_buf = create_overlay(participants, date_str, timeslot_str, page_idx)
            overlay_reader = PdfReader(overlay_buf)
            overlay_page = overlay_reader.pages[0]

            # Re-read the blank form fresh each time to avoid copy issues
            fresh_reader = PdfReader(form_path)
            base_page = fresh_reader.pages[0]
            base_page.merge_page(overlay_page)
            writer.add_page(base_page)
            total_pages += 1

    with open(output_path, 'wb') as f:
        writer.write(f)

    print(f"\nGenerated: {output_path}")
    print(f"  {len(records)} participant(s) across {len(sorted_keys)} group(s), "
          f"{total_pages} total page(s)\n")
    for key in sorted_keys:
        d, day, ts = key
        n = len(groups[key])
        pg = math.ceil(n / ROWS_PER_PAGE)
        print(f"  {day} {d} {ts}: {n} participants ({pg} page(s))")

    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="prt_generator.py",
        description="PRT Score Sheet Generator — NAVPERS 6110/11 (Rev. 12-2025)\n\n"
                    "Reads a CSV of PFA registrations, groups by Date/Day/TimeSlot,\n"
                    "sorts by cardio modality then alphabetically by last name, and\n"
                    "overlays participant data onto the official PRT Score Sheet PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""expected CSV format:
  LastName,FirstName,MI,Sex,Age,Rank,Email,Event,Day,Date,TimeSlot,Timestamp

filter examples:
  %(prog)s reg.csv form.pdf --event Swim
  %(prog)s reg.csv form.pdf --date 22MAR26 --event Run
  %(prog)s reg.csv form.pdf --day Tuesday --timeslot 0800-0900
  %(prog)s reg.csv form.pdf --event Swim Run   (multiple values OK)

requirements:
  pip install pypdf reportlab""",
    )

    parser.add_argument("csv", help="CSV file with registration data")
    parser.add_argument("form", help="Blank NAVPERS 6110/11 PRT Score Sheet PDF")
    parser.add_argument("-o", "--output", default=None,
                        help="Output PDF path (default: PRT_Score_Sheets_Filled.pdf "
                             "in same folder as CSV)")

    # Filter flags
    parser.add_argument("--date", nargs="+", metavar="DATE",
                        help="Only include these date(s), e.g. 22MAR26 23MAR26")
    parser.add_argument("--day", nargs="+", metavar="DAY",
                        help="Only include these day(s), e.g. Monday Tuesday")
    parser.add_argument("--timeslot", nargs="+", metavar="SLOT",
                        help="Only include these timeslot(s), e.g. 0800-0900 1000-1100")
    parser.add_argument("--event", "--modality", nargs="+", metavar="EVENT",
                        help="Only include these cardio modality(ies), e.g. Run Swim")

    args = parser.parse_args()

    # Validate input files exist
    for path, label in [(args.csv, "CSV"), (args.form, "Form PDF")]:
        if not os.path.exists(path):
            parser.error(f"{label} not found: {path}")

    # Build output path
    output_path = args.output
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(args.csv)),
            "PRT_Score_Sheets_Filled.pdf"
        )

    # Build filters dict (uppercase for case-insensitive matching)
    filters = {}
    if args.date:
        filters['date'] = [d.upper() for d in args.date]
    if args.day:
        filters['day'] = [d.upper() for d in args.day]
    if args.timeslot:
        filters['timeslot'] = [t.upper() for t in args.timeslot]
    if args.event:
        filters['event'] = [e.upper() for e in args.event]

    if filters:
        print("Filters applied:")
        for k, v in filters.items():
            print(f"  {k}: {', '.join(v)}")

    pdf_path = generate_pdf(args.csv, args.form, output_path, filters)

    # Open for print preview
    print("\nOpening PDF for print preview...")
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", pdf_path])
        elif sys.platform == "win32":
            os.startfile(pdf_path)
        else:
            try:
                subprocess.Popen(["xdg-open", pdf_path])
            except FileNotFoundError:
                webbrowser.open("file://" + os.path.abspath(pdf_path))
        print("PDF opened — press Ctrl+P (Cmd+P on Mac) to print when ready.")
    except Exception as e:
        print(f"Could not auto-open: {e}")
        print(f"Open manually: {pdf_path}")


if __name__ == "__main__":
    main()
