#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown to PDF Converter for 513180 Fund Research Report
Using reportlab with Chinese font support
"""

import os
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, Flowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

# Output path
OUTPUT_PATH = "/Volumes/Luis_MacData/AgentSystem/产出/513180_恒生科技ETF_研究报告.pdf"
INPUT_PATH = "/Volumes/Luis_MacData/AgentSystem/docs/513180_report_verified.md"
CHARTS_DIR = "/Volumes/Luis_MacData/AgentSystem/charts"

# Chart files mapping
CHARTS = {
    "performance": os.path.join(CHARTS_DIR, "01_performance.png"),
    "sector": os.path.join(CHARTS_DIR, "02_sector_distribution.png"),
    "holdings": os.path.join(CHARTS_DIR, "03_top_holdings.png"),
    "fund_flow": os.path.join(CHARTS_DIR, "04_fund_flow.png"),
}


def register_chinese_fonts():
    """Register Chinese fonts for PDF generation"""
    # Try to find system fonts
    font_paths = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/PingFang.ttc",
    ]

    font_registered = False
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('Chinese', font_path))
                font_registered = True
                print(f"Registered font: {font_path}")
                break
            except Exception as e:
                print(f"Failed to register {font_path}: {e}")

    # Fallback: Try common Chinese font names
    if not font_registered:
        try:
            pdfmetrics.registerFont(TTFont('Chinese', '/System/Library/Fonts/Helvetica.ttc'))
            font_registered = True
        except:
            pass

    return font_registered


def create_document_styles():
    """Create custom document styles"""
    styles = getSampleStyleSheet()

    # Title style
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#1a365d'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold' if not register_chinese_fonts() else 'Chinese',
    ))

    # Check if Chinese fonts are available
    font_registered = register_chinese_fonts()
    font_name = 'Chinese' if font_registered else 'Helvetica'
    font_bold = 'Helvetica-Bold' if not font_registered else 'Chinese'

    # Heading 1 style
    styles.add(ParagraphStyle(
        name='CustomHeading1',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c5282'),
        spaceAfter=12,
        spaceBefore=20,
        fontName=font_bold,
    ))

    # Heading 2 style
    styles.add(ParagraphStyle(
        name='CustomHeading2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=10,
        spaceBefore=12,
        fontName=font_bold,
    ))

    # Heading 3 style
    styles.add(ParagraphStyle(
        name='CustomHeading3',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#4a5568'),
        spaceAfter=8,
        spaceBefore=8,
        fontName=font_bold,
    ))

    # Body text style
    styles.add(ParagraphStyle(
        name='CustomBodyText',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=10,
        alignment=TA_JUSTIFY,
        leading=16,
    ))

    # Table cell style
    styles.add(ParagraphStyle(
        name='TableCell',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_LEFT,
    ))

    # Caption style
    styles.add(ParagraphStyle(
        name='Caption',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.gray,
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique' if not font_registered else 'Chinese',
    ))

    return styles


def parse_markdown_tables(md_content):
    """Parse markdown tables into list of lists"""
    tables = []
    lines = md_content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('|') and not line.startswith('---'):
            # Found a table
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row_content = lines[i].strip()
                # Skip markdown table separator
                if '---' in row_content:
                    i += 1
                    continue
                # Parse row
                cells = [cell.strip() for cell in row_content.split('|')[1:-1]]
                table_rows.append(cells)
                i += 1
            if table_rows:
                tables.append(table_rows)
        else:
            i += 1
    return tables


def create_table_from_data(data, styles):
    """Create a ReportLab table from markdown table data"""
    if not data:
        return None

    # Convert data to table format
    table_data = []
    for row in data:
        table_data.append(row)

    if not table_data:
        return None

    # Calculate column widths
    num_cols = len(table_data[0]) if table_data else 1
    col_widths = None

    # Check if it's a wide table
    if num_cols > 4:
        # Use smaller widths for wide tables
        col_widths = [2.5*cm] * num_cols

    table = Table(table_data, colWidths=col_widths)

    # Style the table
    font_registered = register_chinese_fonts()
    font_name = 'Helvetica' if not font_registered else 'Chinese'
    font_bold = 'Helvetica-Bold' if not font_registered else 'Chinese'

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), font_bold),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2d3748')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    return table


def create_chart_image(chart_path, width=12*cm):
    """Create an image flowable for the chart"""
    if not os.path.exists(chart_path):
        print(f"Chart not found: {chart_path}")
        return None

    img = Image(chart_path, width=width, height=width*0.6)
    return img


def parse_and_build_story(md_content, styles):
    """Parse markdown content and build PDF story"""
    story = []
    lines = md_content.split('\n')

    # Track current state
    in_table = False
    table_data = []
    i = 0

    # Chart insertion points
    chart_positions = {
        "## 二、业绩分析": "performance",
        "### 2.1 历史业绩表现": "performance",
        "## 三、持仓分析": "holdings",
        "### 3.1 前十大重仓股": "holdings",
        "### 3.2 行业分布": "sector",
        "## 五、资金流向分析": "fund_flow",
    }

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Title (main title)
        if line.startswith('# ') and not line.startswith('##'):
            title = line[2:].strip()
            story.append(Paragraph(title, styles['CustomTitle']))
            i += 1
            continue

        # Heading 1 (##)
        elif line.startswith('## ') and not line.startswith('###'):
            # Check if we need to insert a chart
            heading_text = line[3:].strip()
            if heading_text in chart_positions:
                chart_key = chart_positions[heading_text]
                chart_path = CHARTS.get(chart_key)
                if chart_path and os.path.exists(chart_path):
                    img = create_chart_image(chart_path)
                    if img:
                        story.append(Spacer(1, 10))
                        story.append(img)
                        story.append(Spacer(1, 10))

            h1 = line[3:].strip()
            story.append(Paragraph(h1, styles['CustomHeading1']))
            i += 1
            continue

        # Heading 2 (###)
        elif line.startswith('### '):
            # Check if we need to insert a chart
            heading_text = line[4:].strip()
            if heading_text in chart_positions:
                chart_key = chart_positions[heading_text]
                chart_path = CHARTS.get(chart_key)
                if chart_path and os.path.exists(chart_path):
                    img = create_chart_image(chart_path)
                    if img:
                        story.append(Spacer(1, 10))
                        story.append(img)
                        story.append(Spacer(1, 10))

            h2 = line[4:].strip()
            story.append(Paragraph(h2, styles['CustomHeading2']))
            i += 1
            continue

        # Heading 3 (####)
        elif line.startswith('#### '):
            h3 = line[5:].strip()
            story.append(Paragraph(h3, styles['CustomHeading3']))
            i += 1
            continue

        # Table handling
        elif line.startswith('|') and '---' not in line:
            # Start collecting table rows
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row_content = lines[i].strip()
                if '---' not in row_content:
                    cells = [cell.strip() for cell in row_content.split('|')[1:-1]]
                    table_rows.append(cells)
                i += 1

            if table_rows:
                table = create_table_from_data(table_rows, styles)
                if table:
                    story.append(Spacer(1, 10))
                    story.append(table)
                    story.append(Spacer(1, 10))
            continue

        # Regular paragraph
        else:
            # Clean up markdown formatting
            text = line
            # Remove bold markers
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            # Remove italic markers
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            # Clean up links but keep text
            text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
            # Clean up images
            text = re.sub(r'!\[.*\]\(.+?\)', '', text)

            if text.strip():
                story.append(Paragraph(text, styles['CustomBodyText']))
            i += 1

    return story


def create_footer(canvas, doc):
    """Add footer to each page"""
    canvas.saveState()
    page_num = canvas.getPageNumber()
    text = f"Page {page_num}"
    canvas.drawRightString(200, 20, text)
    canvas.restoreState()


def create_header(canvas, doc):
    """Add header to each page"""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.drawString(40, 780, "513180 恒生科技ETF 研究报告")
    canvas.restoreState()


def main():
    """Main function to generate PDF"""
    print("Starting PDF generation...")

    # Register Chinese fonts
    print("Registering Chinese fonts...")
    register_chinese_fonts()

    # Create output directory if needed
    output_dir = os.path.dirname(OUTPUT_PATH)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Read markdown content
    print(f"Reading markdown from: {INPUT_PATH}")
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Create document
    print("Creating PDF document...")
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    # Create styles
    styles = create_document_styles()

    # Build story from markdown
    print("Building document content...")
    story = parse_and_build_story(md_content, styles)

    # Add page numbers
    doc.build(story, onFirstPage=create_header, onLaterPages=create_header)

    print(f"PDF generated successfully: {OUTPUT_PATH}")

    # Verify file exists
    if os.path.exists(OUTPUT_PATH):
        file_size = os.path.getsize(OUTPUT_PATH)
        print(f"File size: {file_size / 1024:.2f} KB")
    else:
        print("ERROR: PDF file was not created!")


if __name__ == "__main__":
    main()
