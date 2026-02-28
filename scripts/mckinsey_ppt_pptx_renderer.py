#!/usr/bin/env python3
"""Minimal native PPTX exporter for McKinsey-style deck specs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

EMU = 914400
SLIDE_CX = 12192000
SLIDE_CY = 6858000


def _hex(value: Any, default: str) -> str:
    text = str(value or default).strip().replace("#", "")
    if len(text) != 6:
        return default
    return text.upper()


def _text(value: Any) -> str:
    return escape(str(value or ""))


def _paragraph_xml(text: str, *, size: int, color: str, bold: bool = False) -> str:
    style_bits = [f'sz="{size}"', f'lang="en-US"']
    if bold:
        style_bits.append('b="1"')
    return (
        "<a:p>"
        "<a:pPr algn=\"l\"/>"
        f"<a:r><a:rPr {' '.join(style_bits)}><a:solidFill><a:srgbClr val=\"{color}\"/></a:solidFill></a:rPr>"
        f"<a:t>{_text(text)}</a:t></a:r>"
        f"<a:endParaRPr sz=\"{size}\" lang=\"en-US\"/>"
        "</a:p>"
    )


def _textbox_shape(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    paragraphs: Iterable[str],
    *,
    font_size: int,
    color: str,
    fill: str | None = None,
    line: str | None = None,
    bold_first: bool = False,
) -> str:
    body = []
    for idx, paragraph in enumerate(paragraphs):
        body.append(_paragraph_xml(paragraph, size=font_size if idx == 0 or not bold_first else font_size - 200, color=color, bold=bold_first and idx == 0))
    fill_xml = (
        f"<a:solidFill><a:srgbClr val=\"{fill}\"/></a:solidFill>" if fill else "<a:noFill/>"
    )
    line_xml = (
        f"<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"{line}\"/></a:solidFill></a:ln>" if line else "<a:ln><a:noFill/></a:ln>"
    )
    return (
        "<p:sp>"
        f"<p:nvSpPr><p:cNvPr id=\"{shape_id}\" name=\"{_text(name)}\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>"
        "<p:spPr>"
        f"<a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        f"{fill_xml}{line_xml}"
        "</p:spPr>"
        "<p:txBody><a:bodyPr wrap=\"square\" lIns=\"91440\" tIns=\"45720\" rIns=\"91440\" bIns=\"45720\"/>"
        "<a:lstStyle/>"
        f"{''.join(body)}"
        "</p:txBody>"
        "</p:sp>"
    )


def _background_shape(shape_id: int, paper: str, accent_soft: str) -> str:
    return (
        "<p:sp>"
        f"<p:nvSpPr><p:cNvPr id=\"{shape_id}\" name=\"Background\"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
        "<p:spPr>"
        f"<a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"{SLIDE_CX}\" cy=\"{SLIDE_CY}\"/></a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        f"<a:solidFill><a:srgbClr val=\"{paper}\"/></a:solidFill>"
        "<a:ln><a:noFill/></a:ln>"
        "</p:spPr>"
        "</p:sp>"
        "<p:sp>"
        f"<p:nvSpPr><p:cNvPr id=\"{shape_id + 1}\" name=\"Accent Band\"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
        "<p:spPr>"
        f"<a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"{SLIDE_CX}\" cy=\"420000\"/></a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        f"<a:solidFill><a:srgbClr val=\"{accent_soft}\"/></a:solidFill>"
        "<a:ln><a:noFill/></a:ln>"
        "</p:spPr>"
        "</p:sp>"
    )


def _cover_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    evidence = slide.get("evidence_needed", []) if isinstance(slide.get("evidence_needed", []), list) else []
    metrics = request.get("key_metrics", []) if isinstance(request.get("key_metrics", []), list) else []
    shapes = [
        _background_shape(2, colors["paper"], colors["accent_soft"]),
        _textbox_shape(4, "Brand", 700000, 540000, 2200000, 380000, [str(request.get("brand", ""))], font_size=1400, color=colors["accent"], fill=None),
        _textbox_shape(5, "Title", 700000, 1100000, 9500000, 1350000, [str(slide.get("title_assertion", ""))], font_size=2800, color=colors["ink"], bold_first=True),
        _textbox_shape(6, "Objective", 700000, 2550000, 9000000, 700000, [str(request.get("objective", "")), str(slide.get("so_what", ""))], font_size=1600, color=colors["muted"], fill=None),
        _textbox_shape(7, "Decision Ask", 700000, 3600000, 4500000, 900000, ["Decision Ask", str(request.get("decision_ask", ""))], font_size=1600, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True),
        _textbox_shape(8, "Metrics", 5600000, 3600000, 4900000, 900000, ["Signal Metrics", " | ".join(str(item) for item in metrics[:3])], font_size=1500, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True),
        _textbox_shape(9, "Evidence", 700000, 4880000, 9800000, 1100000, ["Critical Proof"] + [f"• {item}" for item in evidence[:3]], font_size=1400, color=colors["ink"], fill=None, line=None, bold_first=True),
        _textbox_shape(10, "Footer", 700000, 6180000, 10300000, 280000, [f"{slide.get('section', '')} | {slide.get('layout', '')} | native pptx export"], font_size=1000, color=colors["muted"], fill=None),
    ]
    return _slide_xml_from_shapes(shapes)


def _content_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    evidence = slide.get("evidence_needed", []) if isinstance(slide.get("evidence_needed", []), list) else []
    notes = slide.get("speaker_notes", []) if isinstance(slide.get("speaker_notes", []), list) else []
    handoff = slide.get("designer_handoff", {}) if isinstance(slide.get("designer_handoff", {}), dict) else {}
    shapes = [
        _background_shape(2, colors["paper"], colors["accent_soft"]),
        _textbox_shape(4, "Section", 700000, 530000, 2600000, 300000, [str(slide.get("section", ""))], font_size=1200, color=colors["accent"], fill=None),
        _textbox_shape(5, "Title", 700000, 900000, 10300000, 850000, [str(slide.get("title_assertion", ""))], font_size=2200, color=colors["ink"], bold_first=True),
        _textbox_shape(6, "So What", 700000, 1850000, 5000000, 850000, ["So what", str(slide.get("so_what", ""))], font_size=1450, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True),
        _textbox_shape(7, "Decision", 5900000, 1850000, 4400000, 850000, ["Decision link", str(slide.get("decision_link", ""))], font_size=1450, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True),
        _textbox_shape(8, "Evidence", 700000, 2950000, 5000000, 2050000, ["Evidence needed"] + [f"• {item}" for item in evidence[:4]], font_size=1350, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True),
        _textbox_shape(9, "Design Handoff", 5900000, 2950000, 4400000, 2050000, ["Designer handoff", f"Primary visual: {handoff.get('primary_visual', '')}", f"Headline trim: {handoff.get('headline_density_flag', '')}"] + [f"• {item}" for item in handoff.get("asset_requests", [])[:2]], font_size=1300, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True),
        _textbox_shape(10, "Speaker Notes", 700000, 5200000, 9600000, 900000, ["Presenter cue"] + [f"• {item}" for item in notes[:2]] + [f"Metric focus: {' / '.join(str(x) for x in request.get('key_metrics', [])[:2])}"], font_size=1200, color=colors["muted"], fill=None, line=None, bold_first=True),
        _textbox_shape(11, "Footer", 10700000, 530000, 700000, 260000, [f"{slide.get('index', ''):02d}"], font_size=1300, color=colors["muted"], fill=None),
    ]
    return _slide_xml_from_shapes(shapes)


def _slide_xml_from_shapes(shapes: List[str]) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:sld xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">"
        "<p:cSld><p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        f"{''.join(shapes)}"
        "</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sld>"
    )


def _slide_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" "
        "Target=\"../slideLayouts/slideLayout1.xml\"/>"
        "</Relationships>"
    )


def _theme_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="PrivateAgentTheme">
  <a:themeElements>
    <a:clrScheme name="PrivateAgent">
      <a:dk1><a:srgbClr val="1C1917"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="0F172A"/></a:dk2>
      <a:lt2><a:srgbClr val="F7F4ED"/></a:lt2>
      <a:accent1><a:srgbClr val="0F766E"/></a:accent1>
      <a:accent2><a:srgbClr val="8C4A2F"/></a:accent2>
      <a:accent3><a:srgbClr val="1D4ED8"/></a:accent3>
      <a:accent4><a:srgbClr val="B45309"/></a:accent4>
      <a:accent5><a:srgbClr val="667085"/></a:accent5>
      <a:accent6><a:srgbClr val="DDD0C3"/></a:accent6>
      <a:hlink><a:srgbClr val="0563C1"/></a:hlink>
      <a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="PrivateAgentFont">
      <a:majorFont><a:latin typeface="Avenir Next"/><a:ea typeface="PingFang SC"/><a:cs typeface="Arial"/></a:majorFont>
      <a:minorFont><a:latin typeface="IBM Plex Sans"/><a:ea typeface="Source Han Sans SC"/><a:cs typeface="Arial"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="PrivateAgentFmt">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:gradFill rotWithShape="1"><a:gsLst><a:gs pos="0"><a:schemeClr val="phClr"><a:lumMod val="110000"/><a:satMod val="105000"/></a:schemeClr></a:gs><a:gs pos="100000"><a:schemeClr val="phClr"><a:lumMod val="103000"/><a:satMod val="103000"/></a:schemeClr></a:gs></a:gsLst><a:lin ang="5400000" scaled="0"/></a:gradFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="9525"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:ln>
        <a:ln w="25400"><a:solidFill><a:schemeClr val="accent2"/></a:solidFill></a:ln>
        <a:ln w="38100"><a:solidFill><a:schemeClr val="accent3"/></a:solidFill></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="lt1"/></a:solidFill><a:solidFill><a:schemeClr val="lt2"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/>
  <a:extraClrSchemeLst/>
</a:theme>"""


def _slide_layout_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def _slide_layout_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" "
        "Target=\"../slideMasters/slideMaster1.xml\"/>"
        "</Relationships>"
    )


def _slide_master_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld name="Master">
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="F7F4ED"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle/><p:bodyStyle/><p:otherStyle/>
  </p:txStyles>
</p:sldMaster>"""


def _slide_master_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" "
        "Target=\"../slideLayouts/slideLayout1.xml\"/>"
        "<Relationship Id=\"rId2\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" "
        "Target=\"../theme/theme1.xml\"/>"
        "</Relationships>"
    )


def _presentation_xml(slide_count: int) -> str:
    slide_ids = "".join(
        f'<p:sldId id="{256 + idx}" r:id="rId{idx + 2}"/>' for idx in range(slide_count)
    )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:presentation xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">"
        "<p:sldMasterIdLst><p:sldMasterId id=\"2147483648\" r:id=\"rId1\"/></p:sldMasterIdLst>"
        f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        f"<p:sldSz cx=\"{SLIDE_CX}\" cy=\"{SLIDE_CY}\"/>"
        "<p:notesSz cx=\"6858000\" cy=\"9144000\"/>"
        "<p:defaultTextStyle/>"
        "</p:presentation>"
    )


def _presentation_rels_xml(slide_count: int) -> str:
    items = [
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"slideMasters/slideMaster1.xml\"/>"
    ]
    for idx in range(slide_count):
        items.append(
            f"<Relationship Id=\"rId{idx + 2}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide{idx + 1}.xml\"/>"
        )
    items.extend(
        [
            "<Relationship Id=\"rId99\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps\" Target=\"presProps.xml\"/>",
            "<Relationship Id=\"rId100\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps\" Target=\"viewProps.xml\"/>",
            "<Relationship Id=\"rId101\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles\" Target=\"tableStyles.xml\"/>",
        ]
    )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        + "".join(items)
        + "</Relationships>"
    )


def _content_types_xml(slide_count: int) -> str:
    slide_overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{idx + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for idx in range(slide_count)
    )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/ppt/presentation.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml\"/>"
        "<Override PartName=\"/ppt/slideMasters/slideMaster1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml\"/>"
        "<Override PartName=\"/ppt/slideLayouts/slideLayout1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml\"/>"
        "<Override PartName=\"/ppt/theme/theme1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.theme+xml\"/>"
        "<Override PartName=\"/ppt/presProps.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.presProps+xml\"/>"
        "<Override PartName=\"/ppt/viewProps.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml\"/>"
        "<Override PartName=\"/ppt/tableStyles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml\"/>"
        "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>"
        "<Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>"
        f"{slide_overrides}"
        "</Types>"
    )


def _root_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"ppt/presentation.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>"
        "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>"
        "</Relationships>"
    )


def _core_xml(topic: str) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
        "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" "
        "xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
        f"<dc:title>{_text(topic)}</dc:title>"
        "<dc:creator>AgentSystem</dc:creator>"
        "<cp:lastModifiedBy>AgentSystem</cp:lastModifiedBy>"
        "</cp:coreProperties>"
    )


def _app_xml(slide_count: int) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" "
        "xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">"
        "<Application>AgentSystem</Application>"
        f"<Slides>{slide_count}</Slides>"
        "<PresentationFormat>On-screen Show (16:9)</PresentationFormat>"
        "</Properties>"
    )


def _pres_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentationPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>"""


def _view_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:viewPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>"""


def _table_styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>"""


def render_deck_pptx(payload: Dict[str, Any], out_path: Path) -> Path:
    request = payload.get("request", {}) if isinstance(payload.get("request", {}), dict) else {}
    design = payload.get("design_system", {}) if isinstance(payload.get("design_system", {}), dict) else {}
    colors_raw = design.get("color_tokens", {}) if isinstance(design.get("color_tokens", {}), dict) else {}
    colors = {
        "ink": _hex(colors_raw.get("ink"), "0F172A"),
        "accent": _hex(colors_raw.get("accent"), "0F766E"),
        "accent_soft": _hex(colors_raw.get("accent_soft"), "D6F3EE"),
        "warn": _hex(colors_raw.get("warn"), "B45309"),
        "paper": _hex(colors_raw.get("paper"), "F7F4ED"),
        "panel": _hex(colors_raw.get("panel"), "FFFDFC"),
        "line": _hex(colors_raw.get("line"), "D7CEC2"),
        "muted": _hex(colors_raw.get("muted"), "667085"),
    }
    slides = payload.get("slides", []) if isinstance(payload.get("slides", []), list) else []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types_xml(len(slides)))
        zf.writestr("_rels/.rels", _root_rels_xml())
        zf.writestr("docProps/core.xml", _core_xml(str(request.get("topic", "Premium deck"))))
        zf.writestr("docProps/app.xml", _app_xml(len(slides)))
        zf.writestr("ppt/presentation.xml", _presentation_xml(len(slides)))
        zf.writestr("ppt/_rels/presentation.xml.rels", _presentation_rels_xml(len(slides)))
        zf.writestr("ppt/theme/theme1.xml", _theme_xml())
        zf.writestr("ppt/slideMasters/slideMaster1.xml", _slide_master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _slide_master_rels_xml())
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", _slide_layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _slide_layout_rels_xml())
        zf.writestr("ppt/presProps.xml", _pres_props_xml())
        zf.writestr("ppt/viewProps.xml", _view_props_xml())
        zf.writestr("ppt/tableStyles.xml", _table_styles_xml())
        for idx, slide in enumerate(slides, start=1):
            xml = _cover_slide_xml(slide, request, colors) if idx == 1 else _content_slide_xml(slide, request, colors)
            zf.writestr(f"ppt/slides/slide{idx}.xml", xml)
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", _slide_rels_xml())
    return out_path


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render native PPTX deck from JSON spec")
    parser.add_argument("--spec-json", required=True)
    parser.add_argument("--out-pptx", required=True)
    return parser


def main() -> int:
    args = build_cli().parse_args()
    payload = json.loads(Path(args.spec_json).read_text(encoding="utf-8"))
    render_deck_pptx(payload, Path(args.out_pptx))
    print(json.dumps({"ok": True, "out_pptx": args.out_pptx}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
