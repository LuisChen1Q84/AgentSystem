#!/usr/bin/env python3
"""Image creator hub: route to subagents, validate inputs, and generate assets with real backend + fallback."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import ssl
import sys
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.registry.delivery_protocol import build_delivery_protocol
from core.skill_intelligence import build_loop_closure, compose_prompt_v2
CFG_DEFAULT = ROOT / "config" / "image_creator_hub.toml"

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+6X8AAAAASUVORK5CYII="
)


class ImageHubError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _cert_issue(msg: str) -> bool:
    low = (msg or "").lower()
    return "certificate verify failed" in low or ("ssl" in low and "certificate" in low)


def _urlopen_with_ssl_strategy(
    req: urllib.request.Request,
    timeout: int,
    verify_ssl: bool,
    insecure_fallback: bool,
):
    full_url = str(getattr(req, "full_url", ""))
    if not full_url.lower().startswith("https://"):
        return urllib.request.urlopen(req, timeout=timeout)
    if not verify_ssl:
        ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except Exception as first_err:
        if _cert_issue(str(first_err)):
            try:
                import certifi  # type: ignore

                ctx = ssl.create_default_context(cafile=certifi.where())
                return urllib.request.urlopen(req, timeout=timeout, context=ctx)
            except Exception:
                pass
            if insecure_fallback:
                ctx = ssl._create_unverified_context()
                return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        raise


@dataclass
class StyleSpec:
    style_id: str
    group: str
    display_name_zh: str
    display_name_en: str
    required: List[str]
    optional: List[str]
    template: str


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def detect_language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text or ""):
        return "zh"
    return "en"


def _style_catalog() -> Dict[str, StyleSpec]:
    return {
        "action_figure": StyleSpec(
            "action_figure",
            "character-generator",
            "收藏级动作手办",
            "Action Figure",
            ["character"],
            ["reference_image"],
            "Create a 1/7 scale commercialized 3D action figure of [CHARACTER DESCRIPTION]. "
            "Use a realistic style with accurate proportions and surface details. "
            "Place the figure on a circular transparent acrylic base. "
            "Use studio-quality lighting, shallow depth of field, and photorealistic materials. "
            "High detail, clean composition, professional collectible figure presentation.",
        ),
        "caricature": StyleSpec(
            "caricature",
            "character-generator",
            "卡通肖像",
            "Caricature Portrait",
            ["character"],
            ["reference_image"],
            "Create a playful 3D caricature portrait of [CHARACTER]. Blend cartoon-style exaggeration with realistic skin shading. "
            "Use an oversized head, stylized hair, and large expressive eyes. Apply soft cinematic lighting with clean, simplified materials. "
            "Keep the background minimal with a gentle blur.",
        ),
        "chibi": StyleSpec(
            "chibi",
            "character-generator",
            "Q版/Chibi形象",
            "Chibi Figure",
            ["character"],
            ["action", "expression", "reference_image"],
            "Create a chibi figurine-style 3D character based on [CHARACTER]. "
            "The figure has a big head and small body, made of matte PVC material. "
            "[ACTION] pose with [EXPRESSION] expression. Photoreal materials, neutral background, ultra-clean composition.",
        ),
        "city_diorama": StyleSpec(
            "city_diorama",
            "scene-generator",
            "城市微缩景观",
            "City Diorama",
            ["city"],
            [],
            "Create a hyper-realistic 3D square diorama of [CITY]. The city appears carved out as a solid block with a visible underground cross-section showing soil, rocks, roots, and earth layers. "
            "Above the ground, display a whimsical fairytale-style cityscape featuring iconic landmarks and cultural elements of [CITY]. "
            "Use a pure white studio background with soft natural lighting. DSLR photo quality, crisp details, vibrant colors, magical realism style. 1080x1080 resolution.",
        ),
        "landmark_render": StyleSpec(
            "landmark_render",
            "scene-generator",
            "地标建筑渲染",
            "Landmark Render",
            ["landmark"],
            [],
            "Create a highly detailed isometric 3D rendering of [LANDMARK] in professional architectural visualization style. "
            "Show the structure at a 45-degree angle from above. Use photorealistic textures such as stone, glass, metal, and brick. "
            "Include a detailed base with tiny people, cars, trees for scale. Clean white background with soft ambient shadows. 1080x1080 resolution.",
        ),
        "movie_scene": StyleSpec(
            "movie_scene",
            "scene-generator",
            "电影场景还原",
            "Movie Scene Diorama",
            ["movie", "scene"],
            [],
            "Present a clear 45-degree top-down isometric miniature 3D cartoon scene of [SCENE NAME] from [MOVIE]. "
            "Use refined textures, realistic PBR materials, and soft lifelike lighting. Create a raised diorama-style base with the most recognizable elements. "
            "Display the movie title at top center in large bold text. 1080x1080 resolution.",
        ),
        "isometric_room": StyleSpec(
            "isometric_room",
            "scene-generator",
            "等轴测房间",
            "Isometric Room",
            ["room_theme"],
            ["atmosphere", "light_sources"],
            "Create an isometric 3D cube-shaped miniature room with a shallow cutaway. "
            "Room description: [ROOM THEME, FURNITURE, DECOR]. Lighting: [ATMOSPHERE], using [LIGHT SOURCES]. "
            "Include realistic reflections, soft colored shadows. Camera: slightly elevated isometric three-quarter view, cube centered. "
            "Photoreal materials, neutral background. No watermark.",
        ),
        "city_weather": StyleSpec(
            "city_weather",
            "scene-generator",
            "城市天气可视化",
            "City Weather",
            ["city", "weather"],
            ["date", "temperature"],
            "Present a clear 45-degree top-down isometric miniature 3D cartoon scene of [CITY]. Feature iconic landmarks. "
            "Use soft refined textures, realistic PBR materials. Integrate [WEATHER] conditions into the environment. "
            "At top center, place \"[CITY]\" in large bold text, weather icon, date, and temperature. 1080x1080.",
        ),
        "sticker_logo": StyleSpec(
            "sticker_logo",
            "product-generator",
            "贴纸轰炸Logo",
            "Sticker-Bombed Logo",
            ["logo_or_brand"],
            ["reference_image"],
            "Create a hyper-realistic 3D physical object shaped like [LOGO/BRAND]. Apply soft studio lighting. "
            "Cover the object with a dense sticker-bomb collage in Y2K and retro 90s style. Include acid graphics, bold typography, smiley faces, stars, and vector badges. "
            "Stickers wrap naturally around curves with slight peeling edges and high-resolution textures. Isolated black background. Octane render, 8K quality.",
        ),
        "chibi_store": StyleSpec(
            "chibi_store",
            "product-generator",
            "Q版品牌店铺",
            "Chibi Brand Store",
            ["brand"],
            ["brand_color"],
            "Create a 3D chibi-style miniature concept store of [BRAND]. Design the exterior inspired by the brand's most iconic product. "
            "The store has two floors with large glass windows revealing a cozy interior. Use [BRAND COLOR] as primary color theme, with warm lighting and staff in brand uniforms. "
            "Add adorable tiny figures walking, sitting along the street. Include benches, street lamps, potted plants. "
            "Render in miniature cityscape style, blind-box toy aesthetic, high detail, soft afternoon lighting. Aspect ratio 2:3.",
        ),
        "product_3d": StyleSpec(
            "product_3d",
            "product-generator",
            "产品3D渲染",
            "Product 3D Render",
            ["product"],
            ["reference_image"],
            "Create a photorealistic 3D render of [PRODUCT]. Use studio-quality lighting with soft shadows. "
            "Show material details and textures clearly. Clean white or gradient background. Professional product photography style. 8K quality.",
        ),
        "product_ad": StyleSpec(
            "product_ad",
            "product-generator",
            "产品广告设计",
            "Product Ad Design",
            ["product", "brand"],
            ["brand_color", "headline", "features", "model_description", "product_color"],
            "An advertising image presents a large [PRODUCT] and a model on a two-toned [BRAND COLOR] background. "
            "Include brand logo [BRAND] at top corner. Add headline text '[HEADLINE]' in bold. "
            "Add product feature tags: [FEATURES]. Add large decorative brand name text in background. "
            "Professional advertising design, 1080x1080.",
        ),
        "low_poly": StyleSpec(
            "low_poly",
            "style-transformer",
            "低多边形风格",
            "Low-Poly",
            ["subject"],
            ["color1", "color2", "reference_image"],
            "A low-poly 3D render of [SUBJECT], constructed from clean triangular facets and shaded in flat [COLOR1] and [COLOR2] tones. "
            "Set in a stylized minimalist environment with crisp geometry and soft ambient occlusion. "
            "Playful digital diorama with sharp edges and visual simplicity.",
        ),
        "meme_3d": StyleSpec(
            "meme_3d",
            "style-transformer",
            "表情包转3D",
            "Meme to 3D",
            ["meme_description"],
            ["reference_image"],
            "Turn [MEME DESCRIPTION] into a photorealistic 3D render. Keep composition identical. "
            "Convert the character into a plush toy with realistic lighting and materials.",
        ),
        "glassesfree_3d": StyleSpec(
            "glassesfree_3d",
            "style-transformer",
            "裸眼3D效果",
            "Glasses-free 3D",
            ["scene_description"],
            [],
            "An enormous L-shaped glasses-free 3D LED screen at a bustling urban intersection. "
            "The screen displays [SCENE DESCRIPTION] with striking depth extending beyond edges. "
            "Under realistic daylight, elements cast lifelike shadows onto surrounding buildings. Rich detail, vibrant colors.",
        ),
        "knolling": StyleSpec(
            "knolling",
            "style-transformer",
            "Knolling整理摆拍",
            "Knolling",
            ["city"],
            ["weather", "temperature"],
            "Present a clear, directly top-down photograph of [CITY] landmarks as 3D magnets, arranged neatly in parallel lines and right angles, knolling. "
            "At top-center, place city name as souvenir magnet, and handwritten post-it note for temperature and weather. No repeats.",
        ),
        "stylized_character": StyleSpec(
            "stylized_character",
            "style-transformer",
            "风格化3D角色",
            "Stylized 3D Character",
            ["character"],
            ["reference_image"],
            "Transform the subject into a stylized 3D character with soft clay-like materials. "
            "Use rounded sculptural forms, exaggerated facial features, and a pastel plus vibrant color palette. "
            "Render on bold blue studio background with soft frontal lighting and subtle shadows.",
        ),
    }


def _replace_tokens(template: str, values: Dict[str, Any]) -> str:
    token_map = {
        "[CHARACTER DESCRIPTION]": values.get("character", "stylized character"),
        "[CHARACTER]": values.get("character", "character"),
        "[ACTION]": values.get("action", "standing"),
        "[EXPRESSION]": values.get("expression", "smiling"),
        "[CITY]": values.get("city", "Tokyo"),
        "[LANDMARK]": values.get("landmark", "Eiffel Tower"),
        "[SCENE NAME]": values.get("scene", "iconic scene"),
        "[MOVIE]": values.get("movie", "classic movie"),
        "[ROOM THEME, FURNITURE, DECOR]": values.get("room_theme", "cozy home office with wood desk and plants"),
        "[ATMOSPHERE]": values.get("atmosphere", "warm"),
        "[LIGHT SOURCES]": values.get("light_sources", "desk lamp and window light"),
        "[WEATHER]": values.get("weather", "sunny"),
        "[LOGO/BRAND]": values.get("logo_or_brand", values.get("brand", "brand")),
        "[BRAND]": values.get("brand", "Brand"),
        "[BRAND COLOR]": values.get("brand_color", "teal"),
        "[PRODUCT]": values.get("product", "product"),
        "[HEADLINE]": values.get("headline", "New Arrival"),
        "[FEATURES]": values.get("features", "premium, durable, lightweight"),
        "[SUBJECT]": values.get("subject", "subject"),
        "[COLOR1]": values.get("color1", "cyan"),
        "[COLOR2]": values.get("color2", "orange"),
        "[MEME DESCRIPTION]": values.get("meme_description", "meme character"),
        "[SCENE DESCRIPTION]": values.get("scene_description", "futuristic creature jumping out of screen"),
    }
    out = template
    for k, v in token_map.items():
        out = out.replace(k, str(v))
    return out


def _wizard(language: str, title: str, options: List[Dict[str, str]], field: str = "style") -> Dict[str, Any]:
    return {
        "type": "genui-form-wizard",
        "title": title,
        "field": field,
        "options": options,
    }


def _style_options(language: str, styles: Dict[str, StyleSpec], groups: List[str] | None = None) -> List[Dict[str, str]]:
    opts: List[Dict[str, str]] = []
    for sid, spec in styles.items():
        if groups and spec.group not in groups:
            continue
        opts.append({"value": sid, "label": spec.display_name_zh if language == "zh" else spec.display_name_en})
    return opts


def _capabilities(language: str, styles: Dict[str, StyleSpec]) -> Dict[str, Any]:
    group_zh = {
        "character-generator": "角色类",
        "scene-generator": "场景类",
        "product-generator": "产品类",
        "style-transformer": "风格类",
    }
    group_en = {
        "character-generator": "Character",
        "scene-generator": "Scene",
        "product-generator": "Product",
        "style-transformer": "Style",
    }
    out: Dict[str, List[Dict[str, str]]] = {}
    for spec in styles.values():
        name = group_zh[spec.group] if language == "zh" else group_en[spec.group]
        out.setdefault(name, []).append(
            {
                "style_id": spec.style_id,
                "name": spec.display_name_zh if language == "zh" else spec.display_name_en,
            }
        )
    return {
        "ui": _wizard(language, "请选择风格" if language == "zh" else "Choose a style", _style_options(language, styles, None)),
        "capabilities": out,
    }


def _missing_required(spec: StyleSpec, values: Dict[str, Any]) -> List[str]:
    has_ref = bool(str(values.get("reference_image", "")).strip()) or bool(values.get("reference_files"))
    missing = []
    for key in spec.required:
        # 对图生图场景放宽：有参考图时，可不强制要求部分文本字段
        if has_ref and key in {"character", "subject", "product", "logo_or_brand", "meme_description"}:
            continue
        val = values.get(key)
        if val is None or str(val).strip() == "":
            missing.append(key)
    return missing


def _route_group(text: str, cfg: Dict[str, Any]) -> str | None:
    low = text.lower()
    routes = cfg.get("routes", {})
    score: Dict[str, int] = {}
    for group, kws in routes.items():
        for kw in kws:
            if str(kw).lower() in low:
                score[group] = score.get(group, 0) + 1
    if not score:
        return None
    return sorted(score.items(), key=lambda x: x[1], reverse=True)[0][0]


def _infer_style_by_inputs(group: str, values: Dict[str, Any]) -> str | None:
    has = lambda k: bool(str(values.get(k, "")).strip())
    has_ref = has("reference_image") or bool(values.get("reference_files"))

    if group == "product-generator":
        if has("product") and has("brand"):
            return "product_ad"
        if has("product"):
            return "product_3d"
        if has("logo_or_brand") and has_ref:
            return "sticker_logo"
        if has("brand"):
            return "chibi_store"
    if group == "scene-generator":
        if has("movie") and has("scene"):
            return "movie_scene"
        if has("landmark"):
            return "landmark_render"
        if has("room_theme"):
            return "isometric_room"
        if has("city") and has("weather"):
            return "city_weather"
        if has("city"):
            return "city_diorama"
    if group == "character-generator":
        if has_ref:
            return "stylized_character"
        if has("action") or has("expression"):
            return "chibi"
        return "action_figure"
    if group == "style-transformer":
        if has("meme_description"):
            return "meme_3d"
        if has("scene_description"):
            return "glassesfree_3d"
        if has("city"):
            return "knolling"
        if has("character"):
            return "stylized_character"
        if has("subject"):
            return "low_poly"
        if has_ref:
            return "stylized_character"
    return None


def _resolve_style_id(text: str, values: Dict[str, Any], styles: Dict[str, StyleSpec], cfg: Dict[str, Any]) -> str | None:
    sid = str(values.get("style_id", "")).strip()
    if sid in styles:
        return sid

    low = text.lower()
    group = _route_group(text, cfg)

    alias_map = cfg.get("style_alias", {})
    alias_hits: List[Tuple[int, str]] = []
    for alias, mapped in alias_map.items():
        a = str(alias).lower()
        if a in low and mapped in styles:
            alias_hits.append((len(a), str(mapped)))

    if group:
        group_hits = [x for x in alias_hits if styles[x[1]].group == group]
        if group_hits:
            return sorted(group_hits, key=lambda x: x[0], reverse=True)[0][1]
        guessed = _infer_style_by_inputs(group, values)
        if guessed and guessed in styles:
            return guessed

    if group is None:
        if alias_hits:
            return sorted(alias_hits, key=lambda x: x[0], reverse=True)[0][1]
        return None

    defaults = cfg.get("defaults", {})
    default_per_group = defaults.get("default_style_by_group", {})
    preferred = str(default_per_group.get(group, "")).strip()
    if preferred in styles:
        return preferred

    for sid2, spec in styles.items():
        if spec.group == group:
            return sid2
    return None


def _is_try_mode(text: str, values: Dict[str, Any]) -> bool:
    if bool(values.get("try_mode", False)):
        return True
    low = text.lower()
    markers = ["试试看", "看个例子", "随机生成", "先看效果", "example", "try", "sample"]
    return any(m in low for m in markers)


def _default_example_values(style_id: str) -> Dict[str, Any]:
    examples = {
        "action_figure": {"character": "anime hero in techwear"},
        "caricature": {"character": "young professional portrait"},
        "chibi": {"character": "school idol", "action": "waving", "expression": "happy"},
        "city_diorama": {"city": "Tokyo"},
        "landmark_render": {"landmark": "Eiffel Tower"},
        "movie_scene": {"movie": "Interstellar", "scene": "tesseract library"},
        "isometric_room": {"room_theme": "cozy gamer bedroom", "atmosphere": "night", "light_sources": "neon strip and monitor"},
        "city_weather": {"city": "Shanghai", "weather": "rainy", "temperature": "12C", "date": "2026-02-26"},
        "sticker_logo": {"logo_or_brand": "Nike"},
        "chibi_store": {"brand": "Starbucks", "brand_color": "green"},
        "product_3d": {"product": "wireless earbuds"},
        "product_ad": {"product": "running shoes", "brand": "Nike", "brand_color": "orange", "headline": "Run Beyond", "features": "lightweight, cushioning, breathable"},
        "low_poly": {"subject": "snow mountain", "color1": "teal", "color2": "pink"},
        "meme_3d": {"meme_description": "surprised cat meme"},
        "glassesfree_3d": {"scene_description": "giant whale jumping out over crossroad"},
        "knolling": {"city": "Paris", "weather": "cloudy", "temperature": "8C"},
        "stylized_character": {"character": "young woman portrait"},
    }
    return examples.get(style_id, {})


def _is_url(s: str) -> bool:
    t = (s or "").strip().lower()
    return t.startswith("http://") or t.startswith("https://")


def _is_data_url(s: str) -> bool:
    return (s or "").strip().lower().startswith("data:image/")


def _local_file_to_data_url(path: str) -> str:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    if not p.exists() or not p.is_file():
        return ""
    mime, _ = mimetypes.guess_type(str(p))
    if not mime or not mime.startswith("image/"):
        mime = "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _normalize_reference_files(values: Dict[str, Any], cfg: Dict[str, Any]) -> List[str]:
    defaults = cfg.get("defaults", {})
    max_refs = max(1, int(defaults.get("reference_max_count", 4)))
    embed_local = bool(defaults.get("embed_local_reference_as_data_url", True))
    raw: List[str] = [str(x).strip() for x in values.get("reference_files", []) if str(x).strip()]
    if values.get("reference_image"):
        raw.append(str(values.get("reference_image")).strip())

    out: List[str] = []
    for x in raw:
        if _is_url(x) or _is_data_url(x):
            out.append(x)
            continue
        if embed_local:
            as_data = _local_file_to_data_url(x)
            if as_data:
                out.append(as_data)
                continue
        # 本地文件无法编码时，跳过，避免下游 API 报错
    return out[:max_refs]


def _generation_mode(reference_files: List[str]) -> str:
    return "img2img" if reference_files else "text2img"


def _quality_suffix(language: str, cfg: Dict[str, Any], mode: str) -> str:
    d = cfg.get("defaults", {})
    if not bool(d.get("prompt_enhance", True)):
        return ""
    if language == "zh":
        base = str(
            d.get(
                "prompt_quality_suffix_zh",
                "画面需主体明确、构图干净、细节真实、材质可信、光影自然、无水印无文字。",
            )
        )
        if mode == "img2img":
            base += " 保持参考图核心特征与轮廓，不改变主体身份。"
        return base
    base = str(
        d.get(
            "prompt_quality_suffix_en",
            "Clean composition, clear subject, realistic materials, natural lighting, high detail, no watermark, no text.",
        )
    )
    if mode == "img2img":
        base += " Preserve key identity and silhouette from reference image."
    return base


def _enhance_prompt(prompt: str, language: str, cfg: Dict[str, Any], mode: str) -> str:
    suffix = _quality_suffix(language, cfg, mode).strip()
    if not suffix:
        return prompt
    sep = " " if language == "en" else "。"
    return f"{prompt}{sep}{suffix}"


def _negative_constraints(language: str) -> List[str]:
    if language == "zh":
        return [
            "不要生成水印、二维码、版权签名",
            "不要生成多余文字覆盖主体",
            "不要出现畸形手部、错位五官、重复肢体",
            "不要让主体出画或严重遮挡",
        ]
    return [
        "No watermark, QR code, or signature",
        "No unnecessary text overlay",
        "No deformed hands/faces or duplicated limbs",
        "No severe cropping of the main subject",
    ]


def _classify_error(msg: str) -> str:
    low = (msg or "").lower()
    if "401" in low or "unauthorized" in low:
        return "auth"
    if "429" in low or "rate limit" in low:
        return "rate_limit"
    if "timed out" in low or "timeout" in low:
        return "timeout"
    if "nodename nor servname provided" in low or "name or service not known" in low or "temporary failure in name resolution" in low:
        return "dns"
    if "ssl" in low or "certificate" in low:
        return "ssl"
    if "connection" in low or "name or service" in low:
        return "network"
    return "other"


def _out_dir_from_cfg(cfg: Dict[str, Any]) -> Path:
    out_dir_raw = str(cfg.get("defaults", {}).get("output_dir", ROOT / "产出/image_creator"))
    out_dir = Path(out_dir_raw)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _log_dir_from_cfg(cfg: Dict[str, Any]) -> Path:
    log_dir_raw = str(cfg.get("defaults", {}).get("log_dir", ROOT / "日志/image_creator"))
    log_dir = Path(log_dir_raw)
    if not log_dir.is_absolute():
        log_dir = ROOT / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


class ObserveLogger:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir

    def write(self, event: Dict[str, Any]) -> None:
        day = dt.datetime.now().strftime("%Y-%m-%d")
        path = self.log_dir / f"calls_{day}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


class FileRateLimiter:
    def __init__(self, log_dir: Path, per_minute: int):
        self.state_path = log_dir / "rate_limit_state.json"
        self.per_minute = max(1, int(per_minute))

    def check(self) -> None:
        now = int(time.time())
        window = now // 60
        state = {"window": window, "count": 0}
        if self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                state = {"window": window, "count": 0}
        if int(state.get("window", window)) != window:
            state = {"window": window, "count": 0}
        if int(state.get("count", 0)) >= self.per_minute:
            raise ImageHubError("RATE_LIMIT", f"rate limit reached: {self.per_minute}/min")
        state["count"] = int(state.get("count", 0)) + 1
        self.state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


class MockImageBackend:
    name = "mock"

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir

    def generate(self, prompt: str, n: int, reference_files: List[str], meta: Dict[str, Any]) -> List[str]:
        out = []
        now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        seed_base = hashlib.sha256((prompt + "|" + now).encode("utf-8")).hexdigest()[:8]
        for i in range(n):
            name = f"image_{now}_{seed_base}_{i+1}.png"
            path = self.out_dir / name
            path.write_bytes(PNG_1X1)
            sidecar = path.with_suffix(".json")
            sidecar.write_text(
                json.dumps(
                    {
                        "prompt": prompt,
                        "reference_files": reference_files,
                        "meta": meta,
                        "backend": self.name,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            out.append(str(path))
        return out


class OpenAICompatibleBackend:
    name = "openai_compatible"

    def __init__(self, cfg: Dict[str, Any], out_dir: Path):
        defaults = cfg.get("defaults", {})
        self.endpoint = str(defaults.get("openai_endpoint", "https://api.openai.com/v1/images/generations"))
        self.model = str(defaults.get("openai_model", "gpt-image-1"))
        self.size = str(defaults.get("openai_size", "1024x1024"))
        self.quality = str(defaults.get("openai_quality", "high"))
        self.timeout = int(defaults.get("request_timeout_sec", 90))
        self.ssl_verify = bool(defaults.get("ssl_verify", True))
        self.ssl_insecure_fallback = bool(defaults.get("ssl_insecure_fallback", False))
        self.api_key_env = str(defaults.get("openai_api_key_env", "OPENAI_API_KEY"))
        self.out_dir = out_dir

    def _save_png_bytes(self, blob: bytes, prompt: str, idx: int) -> str:
        now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        seed_base = hashlib.sha256((prompt + "|" + str(idx) + "|" + now).encode("utf-8")).hexdigest()[:8]
        name = f"image_{now}_{seed_base}_{idx+1}.png"
        path = self.out_dir / name
        path.write_bytes(blob)
        return str(path)

    def _download(self, url: str) -> bytes:
        req = urllib.request.Request(url, method="GET")
        with _urlopen_with_ssl_strategy(
            req,
            timeout=self.timeout,
            verify_ssl=self.ssl_verify,
            insecure_fallback=self.ssl_insecure_fallback,
        ) as resp:
            return resp.read()

    def generate(self, prompt: str, n: int, reference_files: List[str], meta: Dict[str, Any]) -> List[str]:
        key = os.getenv(self.api_key_env, "").strip()
        if not key:
            raise ImageHubError("AUTH_MISSING", f"missing env: {self.api_key_env}")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "n": n,
            "size": self.size,
            "quality": self.quality,
            "response_format": "b64_json",
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with _urlopen_with_ssl_strategy(
                req,
                timeout=self.timeout,
                verify_ssl=self.ssl_verify,
                insecure_fallback=self.ssl_insecure_fallback,
            ) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
            raise ImageHubError("HTTP_ERROR", f"http {e.code}: {detail[:240]}") from e
        except Exception as e:
            raise ImageHubError("NETWORK", str(e)) from e

        try:
            parsed = json.loads(raw)
        except Exception as e:
            raise ImageHubError("PARSE", f"invalid response json: {e}") from e

        data = parsed.get("data", [])
        if not isinstance(data, list) or not data:
            raise ImageHubError("EMPTY", "image api returned empty data")

        out: List[str] = []
        for i, item in enumerate(data[:n]):
            if isinstance(item, dict) and item.get("b64_json"):
                out.append(self._save_png_bytes(base64.b64decode(item["b64_json"]), prompt, i))
                continue
            if isinstance(item, dict) and item.get("url"):
                out.append(self._save_png_bytes(self._download(str(item["url"])), prompt, i))
                continue
            raise ImageHubError("FORMAT", "unsupported image response format")
        return out


class MiniMaxBackend:
    name = "minimax"

    # MiniMax API 错误码映射
    ERROR_CODES = {
        0: ("success", "成功"),
        1002: ("rate_limit", "触发限流，请稍后再试"),
        1004: ("auth_failed", "账号鉴权失败，请检查 API-Key 是否正确"),
        1008: ("insufficient_balance", "账号余额不足，请充值"),
        1026: ("content_sensitive", "图片描述涉及敏感内容，请修改prompt"),
        2013: ("invalid_params", "传入参数异常，请检查输入格式"),
        2049: ("invalid_api_key", "无效的API Key，请检查配置"),
    }

    def __init__(self, cfg: Dict[str, Any], out_dir: Path):
        defaults = cfg.get("defaults", {})
        self.endpoint = str(defaults.get("minimax_endpoint", "https://api.minimaxi.com/v1/image_generation"))
        self.model = str(defaults.get("minimax_model", "image-01"))
        self.aspect_ratio = str(defaults.get("minimax_aspect_ratio", "1:1"))
        self.timeout = int(defaults.get("request_timeout_sec", 90))
        self.ssl_verify = bool(defaults.get("ssl_verify", True))
        self.ssl_insecure_fallback = bool(defaults.get("ssl_insecure_fallback", False))
        self.api_key_env = str(defaults.get("minimax_api_key_env", "MINIMAX_API_KEY"))
        self.out_dir = out_dir
        # 新增配置
        self.enable_prompt_optimizer = bool(defaults.get("minimax_enable_prompt_optimizer", False))
        self.enable_live_style = bool(defaults.get("minimax_enable_live_style", False))
        self.default_style_type = str(defaults.get("minimax_default_style_type", "漫画"))
        self.default_style_weight = float(defaults.get("minimax_default_style_weight", 0.8))
        self.add_aigc_watermark = bool(defaults.get("minimax_add_aigc_watermark", False))

    def _save_image_bytes(self, blob: bytes, prompt: str, idx: int) -> str:
        now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        seed_base = hashlib.sha256((prompt + "|" + str(idx) + "|" + now).encode("utf-8")).hexdigest()[:8]
        name = f"image_{now}_{seed_base}_{idx+1}.jpeg"
        path = self.out_dir / name
        path.write_bytes(blob)
        return str(path)

    def generate(self, prompt: str, n: int, reference_files: List[str], meta: Dict[str, Any]) -> List[str]:
        key = os.getenv(self.api_key_env, "").strip()
        if not key:
            raise ImageHubError("AUTH_MISSING", f"missing env: {self.api_key_env}")

        # 构建payload
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "aspect_ratio": str(meta.get("aspect_ratio", self.aspect_ratio)),
            "response_format": "base64",
            "n": min(max(1, n), 9),  # MiniMax支持1-9张
        }

        # prompt_optimizer（用户可覆盖配置）
        prompt_optimizer = meta.get("prompt_optimizer", self.enable_prompt_optimizer)
        if prompt_optimizer:
            payload["prompt_optimizer"] = True

        # aigc_watermark（用户可覆盖配置）
        aigc_watermark = meta.get("aigc_watermark", self.add_aigc_watermark)
        if aigc_watermark:
            payload["aigc_watermark"] = True

        # seed（用于结果复现）
        seed = meta.get("seed")
        if seed is not None:
            payload["seed"] = int(seed)

        # style参数（仅image-01-live支持）
        style_type = meta.get("style_type")
        if not style_type:
            style_type = self.default_style_type if self.enable_live_style else None
        if style_type and self.model == "image-01-live":
            style_weight = meta.get("style_weight", self.default_style_weight)
            payload["style"] = {
                "style_type": style_type,
                "style_weight": style_weight
            }

        # 图生图：subject_reference
        if reference_files:
            refs = []
            for ref in reference_files[:4]:
                url = str(ref).strip()
                # 支持 http/https URL
                if url.startswith("http://") or url.startswith("https://"):
                    refs.append({"type": "character", "image_file": url})
                # 支持 Base64 Data URL
                elif url.startswith("data:image/"):
                    refs.append({"type": "character", "image_file": url})
            if refs:
                payload["subject_reference"] = refs

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with _urlopen_with_ssl_strategy(
                req,
                timeout=self.timeout,
                verify_ssl=self.ssl_verify,
                insecure_fallback=self.ssl_insecure_fallback,
            ) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
            raise ImageHubError("HTTP_ERROR", f"http {e.code}: {detail[:240]}") from e
        except Exception as e:
            raise ImageHubError("NETWORK", str(e)) from e

        try:
            parsed = json.loads(raw)
        except Exception as e:
            raise ImageHubError("PARSE", f"invalid response json: {e}") from e

        # 检查API错误码
        base_resp = parsed.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code != 0:
            error_info = self.ERROR_CODES.get(status_code, ("unknown", f"未知错误码: {status_code}"))
            error_code, error_msg = error_info
            detail_msg = base_resp.get("status_msg", "")
            raise ImageHubError(
                f"API_{error_code}",
                f"[{status_code}] {error_msg}" + (f" - {detail_msg}" if detail_msg else "")
            )

        data = parsed.get("data", {})
        b64_list = data.get("image_base64", []) if isinstance(data, dict) else []
        if not isinstance(b64_list, list) or not b64_list:
            raise ImageHubError("EMPTY", "minimax returned empty image_base64")

        out: List[str] = []
        for i, b64 in enumerate(b64_list[: max(1, n)]):
            out.append(self._save_image_bytes(base64.b64decode(b64), prompt, i))
        return out


def _provider_order(cfg: Dict[str, Any], values: Dict[str, Any]) -> List[str]:
    backend = str(values.get("backend", "")).strip().lower()
    defaults = cfg.get("defaults", {})
    order = [str(x).strip().lower() for x in defaults.get("providers_order", ["minimax", "openai_compatible", "mock"])]
    if backend in {"mock", "openai_compatible", "minimax"}:
        return [backend] + [x for x in order if x != backend]
    return order


def _generate_with_fallback(
    cfg: Dict[str, Any],
    prompt: str,
    n: int,
    reference_files: List[str],
    meta: Dict[str, Any],
    logger: ObserveLogger,
) -> Tuple[List[str], Dict[str, Any]]:
    defaults = cfg.get("defaults", {})
    out_dir = _out_dir_from_cfg(cfg)
    log_dir = _log_dir_from_cfg(cfg)
    limiter = FileRateLimiter(log_dir, int(defaults.get("rate_limit_per_minute", 30)))
    limiter.check()

    max_retries = int(defaults.get("max_retries", 2))
    backoff = float(defaults.get("retry_backoff_sec", 1.0))
    providers = _provider_order(cfg, meta.get("values", {}))

    attempts: List[Dict[str, Any]] = []
    for provider in providers:
        if provider == "minimax":
            backend = MiniMaxBackend(cfg, out_dir)
        elif provider == "openai_compatible":
            backend = OpenAICompatibleBackend(cfg, out_dir)
        else:
            backend = MockImageBackend(out_dir)

        for attempt in range(max_retries + 1):
            t0 = time.time()
            try:
                paths = backend.generate(prompt, n=n, reference_files=reference_files, meta=meta)
                latency_ms = int((time.time() - t0) * 1000)
                event = {
                    "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "ok",
                    "backend": backend.name,
                    "attempt": attempt + 1,
                    "latency_ms": latency_ms,
                    "style_id": meta.get("style_id", ""),
                    "subagent": meta.get("subagent", ""),
                    "try_mode": bool(meta.get("try_mode", False)),
                    "n": n,
                }
                logger.write(event)
                return paths, {"backend": backend.name, "attempts": attempts + [event]}
            except Exception as e:
                latency_ms = int((time.time() - t0) * 1000)
                msg = str(e)
                fail = {
                    "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "error",
                    "backend": backend.name,
                    "attempt": attempt + 1,
                    "latency_ms": latency_ms,
                    "error": msg,
                    "error_class": _classify_error(msg),
                    "style_id": meta.get("style_id", ""),
                    "subagent": meta.get("subagent", ""),
                    "try_mode": bool(meta.get("try_mode", False)),
                    "n": n,
                }
                logger.write(fail)
                attempts.append(fail)
                if attempt < max_retries and backend.name != "mock":
                    time.sleep(backoff * (attempt + 1))
                    continue
                break

    raise ImageHubError("ALL_BACKENDS_FAILED", json.dumps(attempts, ensure_ascii=False))


def aggregate_logs(log_dir: Path, days: int = 7) -> Dict[str, Any]:
    now = dt.datetime.now()
    rows: List[Dict[str, Any]] = []
    for i in range(max(1, days)):
        day = (now - dt.timedelta(days=i)).strftime("%Y-%m-%d")
        p = log_dir / f"calls_{day}.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    total = len(rows)
    ok = [r for r in rows if r.get("status") == "ok"]
    fail = [r for r in rows if r.get("status") != "ok"]
    latencies = sorted([int(r.get("latency_ms", 0)) for r in ok if isinstance(r.get("latency_ms", 0), int)])
    p95 = 0
    if latencies:
        idx = int(0.95 * (len(latencies) - 1))
        p95 = latencies[idx]

    backend_counts: Dict[str, int] = {}
    for r in rows:
        b = str(r.get("backend", "unknown"))
        backend_counts[b] = backend_counts.get(b, 0) + 1

    fail_classes: Dict[str, int] = {}
    for r in fail:
        c = str(r.get("error_class", "other"))
        fail_classes[c] = fail_classes.get(c, 0) + 1

    return {
        "days": days,
        "total_calls": total,
        "success": len(ok),
        "failure": len(fail),
        "success_rate": round((len(ok) / total) * 100, 2) if total else 0.0,
        "latency_p95_ms": p95,
        "backend_counts": backend_counts,
        "failure_classes": fail_classes,
    }


def run_request(cfg: Dict[str, Any], text: str, values: Dict[str, Any]) -> Dict[str, Any]:
    def finish(payload: Dict[str, Any]) -> Dict[str, Any]:
        payload["delivery_protocol"] = build_delivery_protocol("image.generate", payload, entrypoint="scripts.image_creator_hub")
        return payload

    styles = _style_catalog()
    language = detect_language(text)
    logger = ObserveLogger(_log_dir_from_cfg(cfg))

    low = text.lower()
    ask_cap = ("你能做什么" in text) or ("what can you do" in low)
    if ask_cap:
        return finish({
            "ok": True,
            "mode": "capabilities",
            "language": language,
            **_capabilities(language, styles),
        })

    style_id = _resolve_style_id(text, values, styles, cfg)
    if not style_id:
        title = "请选择要生成的风格" if language == "zh" else "Choose a style"
        return finish({
            "ok": True,
            "mode": "choose-style",
            "language": language,
            "ui": _wizard(language, title, _style_options(language, styles)),
        })

    spec = styles[style_id]
    try_mode = _is_try_mode(text, values)
    merged = dict(values)
    if try_mode:
        ex = _default_example_values(style_id)
        for k, v in ex.items():
            merged.setdefault(k, v)

    missing = _missing_required(spec, merged)
    if missing:
        field_zh = {
            "character": "人物描述或人物图",
            "city": "城市名",
            "landmark": "地标名",
            "movie": "电影名",
            "scene": "场景名",
            "room_theme": "房间主题描述",
            "weather": "天气",
            "logo_or_brand": "Logo图或品牌名",
            "brand": "品牌名",
            "product": "产品图或产品描述",
            "subject": "主体图或描述",
            "meme_description": "表情包描述或图片",
            "scene_description": "场景描述",
        }
        ask = [field_zh.get(m, m) if language == "zh" else m for m in missing]
        msg = (
            f"缺少必需输入：{', '.join(ask)}。也可以先试试看示例效果。"
            if language == "zh"
            else f"Missing required inputs: {', '.join(ask)}. You can also try a sample first."
        )
        return finish({
            "ok": True,
            "mode": "need-input",
            "language": language,
            "route": {"subagent": spec.group, "style_id": spec.style_id},
            "message": msg,
        })

    prompt = _replace_tokens(spec.template, merged)
    ref_files = _normalize_reference_files(values, cfg)
    gen_mode = _generation_mode(ref_files)
    prompt = _enhance_prompt(prompt, language, cfg, gen_mode)
    prompt_packet = compose_prompt_v2(
        objective=f"Generate {spec.style_id}",
        language=language,
        context={"subagent": spec.group, "style_id": spec.style_id, "generation_mode": gen_mode},
        references=ref_files,
        constraints=[
            "Prefer realistic material and lighting consistency",
            "Keep composition clean and centered",
            "Respect selected style identity",
        ],
        output_contract=["Return image assets only", "At least 1 valid image path"],
        negative_constraints=_negative_constraints(language),
    )
    prompt = f"{prompt}\n\n{prompt_packet['user_prompt']}"

    n = 2 if try_mode else 1

    # 提取用户传递的新参数
    user_params = {
        "prompt_optimizer": values.get("prompt_optimizer"),
        "seed": values.get("seed"),
        "aspect_ratio": values.get("aspect_ratio"),
        "style_type": values.get("style_type"),
        "style_weight": values.get("style_weight"),
        "aigc_watermark": values.get("aigc_watermark"),
        "n": values.get("n"),  # 用户可指定生成数量(1-9)
    }
    # 过滤掉 None 值
    user_params = {k: v for k, v in user_params.items() if v is not None}

    # 如果用户指定了n，覆盖默认值
    if "n" in user_params:
        n = min(max(1, int(user_params["n"])), 9)

    paths, gen_meta = _generate_with_fallback(
        cfg,
        prompt,
        n=n,
        reference_files=ref_files,
        meta={
            "style_id": spec.style_id,
            "subagent": spec.group,
            "try_mode": try_mode,
            "values": values,
            **user_params,  # 合并用户参数
        },
        logger=logger,
    )

    payload = {
        "ok": True,
        "mode": "generated",
        "language": language,
        "route": {"subagent": spec.group, "style_id": spec.style_id, "generation_mode": gen_mode},
        "prompt_packet": prompt_packet,
        "prompt": prompt,
        "backend": gen_meta.get("backend", "unknown"),
        "deliver_assets": {"items": [{"path": p} for p in paths]},
        "response_text": "<deliver_assets>\n"
        + "\n".join([f"<item><path>{p}</path></item>" for p in paths])
        + "\n</deliver_assets>",
        "loop_closure": build_loop_closure(
            skill="image-creator-hub",
            status="generated",
            evidence={"backend": gen_meta.get("backend", ""), "assets": len(paths), "generation_mode": gen_mode},
            next_actions=["提升一致性可增加参考图", "对风格偏差可切换 style_id 重试"],
        ),
    }
    return finish(payload)


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Image creator hub")
    p.add_argument("--config", default=str(CFG_DEFAULT))
    sub = p.add_subparsers(dest="command")

    run = sub.add_parser("run", help="run request")
    run.add_argument("--text", required=True)
    run.add_argument("--params-json", default="{}")

    cap = sub.add_parser("capabilities", help="show capabilities wizard")
    cap.add_argument("--lang", default="zh")

    obs = sub.add_parser("observe", help="aggregate image creator observability")
    obs.add_argument("--days", type=int, default=7)

    return p


def main() -> int:
    args = build_cli().parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = load_cfg(cfg_path)

    if args.command == "capabilities":
        styles = _style_catalog()
        lang = "zh" if args.lang.startswith("zh") else "en"
        print(json.dumps(_capabilities(lang, styles), ensure_ascii=False, indent=2))
        return 0

    if args.command == "observe":
        out = aggregate_logs(_log_dir_from_cfg(cfg), max(1, int(args.days)))
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run":
        try:
            values = json.loads(args.params_json or "{}")
            if not isinstance(values, dict):
                raise ValueError("params-json must be object")
        except Exception as e:
            raise SystemExit(json.dumps({"ok": False, "error": f"invalid params-json: {e}"}, ensure_ascii=False))

        try:
            result = run_request(cfg, args.text, values)
        except ImageHubError as e:
            print(json.dumps({"ok": False, "error": str(e), "code": e.code}, ensure_ascii=False, indent=2))
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    raise SystemExit("usage: run or capabilities or observe")


if __name__ == "__main__":
    raise SystemExit(main())
