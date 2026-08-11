#!/usr/bin/env python3
"""
COSMOS SUDAR — site builder
===========================

You do NOT need to understand or run this file. GitHub runs it for you
automatically every time you publish a story.

What it does: reads your stories from content/news/*.md and turns them into
a complete website in the _site/ folder.

Pure Python standard library — no packages to install, nothing that can break
or expire. Run locally with:  python3 build.py
"""

import json
import os
import re
import shutil
import html as htmlmod
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xesc

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_site"
NEWS_DIR = ROOT / "content" / "news"
PAGES_DIR = ROOT / "content" / "pages"
ASSETS = ROOT / "assets"

PER_PAGE = 12
warnings = []


# ============================================================== front matter
def parse_front_matter(text):
    """Read the `---` block at the top of a story file. Forgiving by design:
    a typo in one story must never take the whole website down."""
    meta, body = {}, text
    if text.lstrip().startswith("---"):
        text = text.lstrip()
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end]
            body = text[end + 4:].lstrip("\n")
            for line in raw.splitlines():
                line = line.rstrip()
                if not line.strip() or line.strip().startswith("#"):
                    continue
                if ":" not in line:
                    continue
                key, _, val = line.partition(":")
                key = key.strip().lower()
                val = val.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                    val = val[1:-1]
                if val.startswith("[") and val.endswith("]"):
                    inner = val[1:-1].strip()
                    val = [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
                meta[key] = val
    return meta, body


# ================================================================= markdown
INLINE_CODE = re.compile(r"`([^`]+)`")
IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
ITAL = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def _tamil(s):
    """Tag Tamil runs so they get the right font and line-height."""
    return re.sub(r"([஀-௿][஀-௿\s -@‘-”]*)",
                  lambda m: f'<span lang="ta">{m.group(1)}</span>', s)


def inline(s, escape=True):
    if escape:
        s = htmlmod.escape(s, quote=False)
    placeholders = []

    def stash(tag):
        placeholders.append(tag)
        return f"\x00{len(placeholders) - 1}\x00"

    s = INLINE_CODE.sub(lambda m: stash(f"<code>{m.group(1)}</code>"), s)
    s = IMG.sub(lambda m: stash(
        f'<img src="{m.group(2)}" alt="{m.group(1)}" loading="lazy" decoding="async">'), s)
    s = LINK.sub(lambda m: stash(
        f'<a href="{m.group(2)}"{" target=_blank rel=noopener" if m.group(2).startswith("http") else ""}>{m.group(1)}</a>'), s)
    s = BOLD.sub(r"<strong>\1</strong>", s)
    s = ITAL.sub(r"<em>\1</em>", s)
    s = _tamil(s)
    for i, tag in enumerate(placeholders):
        s = s.replace(f"\x00{i}\x00", tag)
    return s


def markdown(text):
    """A compact markdown renderer covering everything journalism needs:
    headings, bold, italic, links, images with captions, lists, quotes, rules."""
    lines = text.replace("\r\n", "\n").split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # horizontal rule
        if re.fullmatch(r"(\*\s*){3,}|(-\s*){3,}|(_\s*){3,}", stripped):
            out.append("<hr>")
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            # The story's own title is the page's <h1>, so both '#' and '##'
            # become <h2> section headings. '###' and deeper step down.
            lvl = max(2, min(len(m.group(1)), 4))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        # blockquote (possibly multi-line)
        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f"<blockquote><p>{inline(' '.join(buf))}</p></blockquote>")
            continue

        # lists
        if re.match(r"^[-*+]\s+", stripped) or re.match(r"^\d+[.)]\s+", stripped):
            ordered = bool(re.match(r"^\d+[.)]\s+", stripped))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines):
                s2 = lines[i].strip()
                m2 = re.match(r"^\d+[.)]\s+(.*)$", s2) if ordered else re.match(r"^[-*+]\s+(.*)$", s2)
                if not m2:
                    break
                items.append(f"<li>{inline(m2.group(1))}</li>")
                i += 1
            out.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        # standalone image -> figure with caption
        m = IMG.fullmatch(stripped)
        if m:
            cap = m.group(3) or ""
            fig = f'<figure><img src="{m.group(2)}" alt="{htmlmod.escape(m.group(1))}" loading="lazy" decoding="async">'
            if cap:
                fig += f"<figcaption>{inline(cap)}</figcaption>"
            out.append(fig + "</figure>")
            i += 1
            continue

        # paragraph (join soft-wrapped lines)
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|>|[-*+]\s|\d+[.)]\s)", lines[i].strip()) \
                and not re.fullmatch(r"(\*\s*){3,}|(-\s*){3,}|(_\s*){3,}", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(f"<p>{inline(' '.join(buf))}</p>")
    return "\n".join(out)


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


# ============================================================ site + config
def load_site():
    with open(ROOT / "site.json", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("categories", [])
    cfg["cat_by_id"] = {c["id"]: c for c in cfg["categories"]}
    cfg["url"] = cfg.get("url", "").rstrip("/")
    return cfg


def cat_name(cfg, cid):
    c = cfg["cat_by_id"].get(cid)
    return c["name"] if c else (cid or "News").replace("-", " ").title()


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    return re.sub(r"[\s_]+", "-", s) or "story"


def fmt_date(d, style="long"):
    if style == "long":
        return d.strftime("%d %B %Y")
    return d.strftime("%d %b %Y")


# ============================================================= load stories
def load_stories(cfg):
    stories = []
    if not NEWS_DIR.exists():
        return stories
    for path in sorted(NEWS_DIR.glob("*.md")):
        if path.name.startswith("_") or path.name.upper().startswith("README"):
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception as e:
            warnings.append(f"Could not read {path.name}: {e}")
            continue

        meta, body = parse_front_matter(raw)
        if str(meta.get("draft", "")).lower() in ("true", "yes", "1"):
            continue

        title = meta.get("title") or path.stem
        if isinstance(title, list):
            title = " ".join(title)

        # date: from front matter, else from filename YYYY-MM-DD-
        dstr = str(meta.get("date", "")).strip()
        dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(dstr[:16] if len(dstr) >= 16 else dstr, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", path.name)
            if m:
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:
                dt = datetime.fromtimestamp(path.stat().st_mtime)
                warnings.append(f"{path.name}: no date found, used the file's own date.")

        slug = meta.get("slug") or re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)
        slug = slugify(slug)

        content_html = markdown(body)
        plain = strip_tags(content_html)
        plain = re.sub(r"\s+", " ", plain).strip()

        summary = meta.get("summary") or meta.get("standfirst") or ""
        if not summary:
            summary = (plain[:185].rsplit(" ", 1)[0] + "…") if len(plain) > 185 else plain

        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        image = str(meta.get("image", "")).strip()
        if image and not image.startswith(("http", "/")):
            image = "/" + image.lstrip("./")

        words = len(plain.split())
        # A drop cap only looks right when the story opens with a plain Latin
        # letter — not with Tamil script, a quotation mark, or bold text.
        first_para = re.match(r"\s*<p>([A-Za-z])", content_html)
        stories.append({
            "dropcap": bool(first_para),
            "title": title,
            "slug": slug,
            "date": dt,
            "iso": dt.replace(tzinfo=timezone.utc).isoformat(),
            "category": str(meta.get("category", "")).strip() or "ground-report",
            "location": str(meta.get("location", "")).strip(),
            "image": image,
            "image_caption": str(meta.get("image_caption", "")).strip(),
            "summary": summary,
            "tags": tags,
            "featured": str(meta.get("featured", "")).lower() in ("true", "yes", "1"),
            "html": content_html,
            "plain": plain,
            "read_min": max(1, round(words / 210)),
            "url": f"/news/{slug}/",
            "source_file": path.name,
        })

    dupes = {}
    for s in stories:
        dupes.setdefault(s["slug"], []).append(s["source_file"])
    for slug, files in dupes.items():
        if len(files) > 1:
            warnings.append(f"Two stories share the web address '{slug}': {', '.join(files)}. Rename one.")

    stories.sort(key=lambda s: s["date"], reverse=True)
    return stories


# ================================================================ templates
def icon(name):
    p = {
        "whatsapp": "M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2Zm5.8 14.16c-.24.68-1.42 1.31-1.96 1.36-.5.05-.99.23-3.4-.71-2.86-1.13-4.68-4.06-4.82-4.25-.14-.19-1.15-1.53-1.15-2.92 0-1.39.73-2.07.99-2.35.26-.28.57-.35.76-.35.19 0 .38 0 .55.01.18.01.41-.07.64.49.24.57.81 1.97.88 2.11.07.14.12.31.02.5-.09.19-.14.31-.28.47-.14.16-.29.36-.42.48-.14.14-.28.29-.12.57.16.28.72 1.18 1.54 1.91 1.06.94 1.95 1.23 2.23 1.37.28.14.44.12.6-.07.16-.19.69-.8.88-1.08.19-.28.37-.23.62-.14.26.09 1.65.78 1.93.92.28.14.47.21.54.33.07.12.07.68-.17 1.35Z",
        "instagram": "M12 2.16c3.2 0 3.58.01 4.85.07 1.17.05 1.8.25 2.23.41.56.22.96.48 1.38.9.42.42.68.82.9 1.38.16.42.36 1.06.41 2.23.06 1.27.07 1.65.07 4.85s-.01 3.58-.07 4.85c-.05 1.17-.25 1.8-.41 2.23-.22.56-.48.96-.9 1.38-.42.42-.82.68-1.38.9-.42.16-1.06.36-2.23.41-1.27.06-1.65.07-4.85.07s-3.58-.01-4.85-.07c-1.17-.05-1.8-.25-2.23-.41-.56-.22-.96-.48-1.38-.9-.42-.42-.68-.82-.9-1.38-.16-.42-.36-1.06-.41-2.23-.06-1.27-.07-1.65-.07-4.85s.01-3.58.07-4.85c.05-1.17.25-1.8.41-2.23.22-.56.48-.96.9-1.38.42-.42.82-.68 1.38-.9.42-.16 1.06-.36 2.23-.41 1.27-.06 1.65-.07 4.85-.07M12 0C8.74 0 8.33.01 7.05.07 5.78.13 4.9.33 4.14.63c-.79.3-1.46.72-2.13 1.38C1.35 2.68.93 3.35.63 4.14.33 4.9.13 5.78.07 7.05.01 8.33 0 8.74 0 12s.01 3.67.07 4.95c.06 1.27.26 2.15.56 2.91.3.79.72 1.46 1.38 2.13.67.66 1.34 1.08 2.13 1.38.76.3 1.64.5 2.91.56 1.28.06 1.69.07 4.95.07s3.67-.01 4.95-.07c1.27-.06 2.15-.26 2.91-.56.79-.3 1.46-.72 2.13-1.38.66-.67 1.08-1.34 1.38-2.13.3-.76.5-1.64.56-2.91.06-1.28.07-1.69.07-4.95s-.01-3.67-.07-4.95c-.06-1.27-.26-2.15-.56-2.91-.3-.79-.72-1.46-1.38-2.13C21.32 1.35 20.65.93 19.86.63c-.76-.3-1.64-.5-2.91-.56C15.67.01 15.26 0 12 0Zm0 5.84a6.16 6.16 0 1 0 0 12.32 6.16 6.16 0 0 0 0-12.32ZM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm7.85-10.41a1.44 1.44 0 1 1-2.88 0 1.44 1.44 0 0 1 2.88 0Z",
        "mail": "M2 5.5A2.5 2.5 0 0 1 4.5 3h15A2.5 2.5 0 0 1 22 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 18.5v-13Zm2.2.2 7.8 5.7 7.8-5.7H4.2ZM20 7.6l-7.4 5.4a1 1 0 0 1-1.2 0L4 7.6v10.9h16V7.6Z",
        "youtube": "M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2C0 8.1 0 12 0 12s0 3.9.5 5.8a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1c.5-1.9.5-5.8.5-5.8s0-3.9-.5-5.8ZM9.6 15.6V8.4l6.2 3.6-6.2 3.6Z",
        "x": "M18.24 2.25h3.31l-7.23 8.26 8.5 11.24h-6.65l-5.22-6.82-5.96 6.82H1.68l7.73-8.84L1.25 2.25h6.82l4.71 6.23 5.46-6.23Zm-1.16 17.52h1.83L7.01 4.13H5.05l12.03 15.64Z",
        "facebook": "M24 12.07C24 5.4 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.05V9.41c0-3.02 1.79-4.69 4.53-4.69 1.31 0 2.68.24 2.68.24v2.96h-1.51c-1.49 0-1.96.93-1.96 1.89v2.26h3.33l-.53 3.49h-2.8V24C19.61 23.1 24 18.1 24 12.07Z",
        "link": "M9.3 14.7a1 1 0 0 0 1.4 0l4-4a1 1 0 0 0-1.4-1.4l-4 4a1 1 0 0 0 0 1.4Zm-2.4 3.9a4 4 0 0 1 0-5.7l2.1-2.1a1 1 0 0 1 1.4 1.4l-2.1 2.1a2 2 0 0 0 2.8 2.8l2.1-2.1a1 1 0 1 1 1.4 1.4l-2.1 2.1a4 4 0 0 1-5.6 0Zm10.2-7.5-2.1 2.1a1 1 0 0 1-1.4-1.4l2.1-2.1a2 2 0 1 0-2.8-2.8l-2.1 2.1a1 1 0 0 1-1.4-1.4l2.1-2.1a4 4 0 1 1 5.6 5.6Z",
        "rss": "M4 11a9 9 0 0 1 9 9h-2.5A6.5 6.5 0 0 0 4 13.5V11Zm0-6a15 15 0 0 1 15 15h-2.5A12.5 12.5 0 0 0 4 7.5V5Zm1.8 11.4a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6Z",
    }
    return f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{p[name]}"/></svg>'


def wa_link(cfg, text=None):
    num = re.sub(r"\D", "", str(cfg.get("whatsapp_number", "")))
    msg = text or cfg.get("whatsapp_message", "Hello")
    from urllib.parse import quote
    return f"https://wa.me/{num}?text={quote(msg)}" if num else "#"


def head(cfg, title, desc, url_path, image=None, kind="website", extra=""):
    full_title = title if title == cfg["site_name"] else f"{title} — {cfg['site_name']}"
    img = image or "/assets/img/brand/social-card.jpg"
    if not img.startswith("http"):
        img = cfg["url"] + img
    canon = cfg["url"] + url_path
    desc = re.sub(r"\s+", " ", strip_tags(desc or cfg["description"])).strip()[:300]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{htmlmod.escape(full_title)}</title>
<meta name="description" content="{htmlmod.escape(desc)}">
<link rel="canonical" href="{canon}">
<meta name="theme-color" content="#0a0d1c">
<meta name="author" content="{htmlmod.escape(cfg['author'])}">

<meta property="og:type" content="{kind}">
<meta property="og:site_name" content="{htmlmod.escape(cfg['site_name'])}">
<meta property="og:title" content="{htmlmod.escape(title)}">
<meta property="og:description" content="{htmlmod.escape(desc)}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="en_IN">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{htmlmod.escape(title)}">
<meta name="twitter:description" content="{htmlmod.escape(desc)}">
<meta name="twitter:image" content="{img}">

<link rel="icon" href="/assets/img/brand/mark.jpg">
<link rel="apple-touch-icon" href="/assets/img/brand/mark.jpg">
<link rel="alternate" type="application/rss+xml" title="{htmlmod.escape(cfg['site_name'])}" href="/feed.xml">

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=Inter:wght@400;500;600;700&family=Noto+Serif+Tamil:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/style.css">
{extra}
</head>
<body>
<a class="skip-link" href="#main">Skip to the news</a>
"""


def header(cfg, active=""):
    def na(href, label, key):
        cur = ' aria-current="page"' if key == active else ""
        return f'<a href="{href}"{cur}>{label}</a>'
    return f"""<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="/">
      <img class="brand-mark" src="/assets/img/brand/mark.jpg" alt="" width="38" height="38">
      <span class="brand-text">
        <span class="brand-name">{htmlmod.escape(cfg['site_name'])}</span>
        <span class="brand-sub">Independent Journalism</span>
      </span>
    </a>
    <button class="nav-toggle" id="navToggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
    </button>
    <nav class="nav" id="nav">
      {na('/', 'Home', 'home')}
      {na('/news/', 'All News', 'news')}
      {na('/about/', 'About', 'about')}
      {na('/ethics/', 'Ethics', 'ethics')}
      {na('/contact/', 'Contact', 'contact')}
      <a class="nav-tip" href="/contact/">Send a Tip</a>
    </nav>
  </div>
</header>
"""


def float_contact(cfg):
    bits = []
    if re.sub(r"\D", "", str(cfg.get("whatsapp_number", ""))):
        bits.append(f'<a class="fc-wa" href="{wa_link(cfg)}" target="_blank" rel="noopener" data-label="WhatsApp a tip" aria-label="WhatsApp">{icon("whatsapp")}</a>')
    if cfg.get("instagram"):
        bits.append(f'<a class="fc-ig" href="{cfg["instagram"]}" target="_blank" rel="noopener" data-label="Instagram" aria-label="Instagram">{icon("instagram")}</a>')
    bits.append(f'<a class="fc-mail" href="mailto:{cfg["email"]}" data-label="Email the newsroom" aria-label="Email">{icon("mail")}</a>')
    return f'<div class="float-contact">{"".join(bits)}</div>'


def footer(cfg, categories_present):
    socials = []
    for key, ic in (("instagram", "instagram"), ("youtube", "youtube"),
                    ("twitter", "x"), ("facebook", "facebook")):
        if cfg.get(key):
            socials.append(f'<a href="{cfg[key]}" target="_blank" rel="noopener" aria-label="{key}">{icon(ic)}</a>')
    socials.append(f'<a href="mailto:{cfg["email"]}" aria-label="Email">{icon("mail")}</a>')
    socials.append(f'<a href="/feed.xml" aria-label="RSS feed">{icon("rss")}</a>')

    cat_links = "".join(
        f'<li><a href="/category/{c}/">{htmlmod.escape(cat_name(cfg, c))}</a></li>'
        for c in categories_present)

    return f"""<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div class="footer-brand">
        <a class="brand" href="/">
          <img class="brand-mark" src="/assets/img/brand/mark.jpg" alt="" width="38" height="38">
          <span class="brand-text">
            <span class="brand-name">{htmlmod.escape(cfg['site_name'])}</span>
            <span class="brand-sub">Independent Journalism</span>
          </span>
        </a>
        <p>{htmlmod.escape(cfg['tagline'])}. No advertisers, no political funding — reporting paid for by nobody but the reporter.</p>
        <div class="social-row">{''.join(socials)}</div>
      </div>
      <div class="footer-col">
        <h4>Sections</h4>
        <ul>{cat_links}<li><a href="/news/">All Stories</a></li></ul>
      </div>
      <div class="footer-col">
        <h4>Newsroom</h4>
        <ul>
          <li><a href="/about/">About Cosmos Sudar</a></li>
          <li><a href="/ethics/">Ethics &amp; Corrections</a></li>
          <li><a href="/contact/">Send a News Tip</a></li>
          <li><a href="mailto:{cfg['email']}">{htmlmod.escape(cfg['email'])}</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <span>© {datetime.now().year} {htmlmod.escape(cfg['site_name'])} · {htmlmod.escape(cfg['author'])}</span>
      <span>Built independently · <a href="/feed.xml">RSS</a></span>
    </div>
  </div>
</footer>
{float_contact(cfg)}
<script src="/assets/js/site.js" defer></script>
</body>
</html>"""


def card(cfg, s, variant="mid"):
    """variant: lead | mid | sm"""
    img = s["image"] or "/assets/img/brand/social-card.jpg"
    loc = f'<span class="dot"></span>{htmlmod.escape(s["location"])}' if s["location"] else ""
    return f"""<a class="card card-{variant}" href="{s['url']}">
  <div class="card-media"><img src="{img}" alt="{htmlmod.escape(s['title'])}" loading="lazy" decoding="async"></div>
  <div class="card-body">
    <span class="kicker">{htmlmod.escape(cat_name(cfg, s['category']))}{loc}<span class="dot"></span><time datetime="{s['date']:%Y-%m-%d}">{fmt_date(s['date'], 'short')}</time></span>
    <h3 class="card-title">{htmlmod.escape(s['title'])}</h3>
    <p class="card-excerpt">{htmlmod.escape(s['summary'])}</p>
  </div>
</a>"""


def tip_strip(cfg):
    wa = ""
    if re.sub(r"\D", "", str(cfg.get("whatsapp_number", ""))):
        wa = f'<a class="btn btn-wa" href="{wa_link(cfg)}" target="_blank" rel="noopener">{icon("whatsapp")} WhatsApp a tip</a>'
    return f"""<section class="tip-strip">
  <div class="wrap-narrow">
    <h2>Seen something that should be reported?</h2>
    <p>A broken road, a missing school, a lake being filled in, a promise not kept. Tell me — I go and look. Your identity stays with me.</p>
    <div class="btn-row">
      {wa}
      <a class="btn btn-primary" href="mailto:{cfg['email']}">{icon("mail")} {htmlmod.escape(cfg['email'])}</a>
      <a class="btn btn-ghost" href="/contact/">All ways to reach me</a>
    </div>
  </div>
</section>"""


# ================================================================== writers
ABS_ATTR = re.compile(r'\b(href|src)="/([^"]*)"')


def write(path_rel, content):
    """Write a page, converting site-root links like /assets/... into links
    relative to this page.

    This one step means the site works in three places instead of one:
      - opened straight off the disk by double-clicking,
      - at username.github.io/repo-name before the domain is connected,
      - at cosmossudar.com afterwards.
    Absolute URLs in og:/canonical tags are untouched — those must stay full.
    """
    p = OUT / path_rel
    p.parent.mkdir(parents=True, exist_ok=True)

    depth = len(Path(path_rel).parts) - 1
    prefix = "../" * depth if depth else ""

    def rel(m):
        attr, target = m.group(1), m.group(2)
        if not target:                       # href="/" -> the home page
            return f'{attr}="{prefix or "./"}index.html"'
        # Directory-style links need index.html so they open off the disk too.
        if target.endswith("/"):
            target += "index.html"
        return f'{attr}="{prefix}{target}"'

    p.write_text(ABS_ATTR.sub(rel, content), encoding="utf-8")


def build_home(cfg, stories, cats_present):
    lead = stories[0] if stories else None
    side = stories[1:4]
    rest = stories[4:13]

    if stories:
        featured = f"""<section class="section">
  <div class="wrap">
    <div class="section-head">
      <h2 class="section-title">Latest Report</h2>
      <a class="section-link" href="/news/">All stories →</a>
    </div>
    <div class="lead-grid">
      {card(cfg, lead, 'lead')}
      <div class="lead-side">{''.join(card(cfg, s, 'sm') for s in side)}</div>
    </div>
  </div>
</section>"""
        more = ""
        if rest:
            more = f"""<section class="section">
  <div class="wrap">
    <div class="section-head"><h2 class="section-title">More from the field</h2></div>
    <div class="story-grid">{''.join(card(cfg, s) for s in rest)}</div>
  </div>
</section>"""
    else:
        featured = """<section class="section"><div class="wrap"><div class="empty">
  <h3>No stories published yet</h3>
  <p>Your first report will appear here the moment you publish it.</p>
</div></div></section>"""
        more = ""

    chips = "".join(f'<a class="chip" href="/category/{c}/">{htmlmod.escape(cat_name(cfg, c))}</a>'
                    for c in cats_present)

    body = f"""{header(cfg, 'home')}
<main id="main">
<section class="hero">
  <img class="hero-img" src="/assets/img/brand/cosmos-hero.jpg" alt="" fetchpriority="high">
  <div class="hero-inner"><div class="wrap">
    <h1>{htmlmod.escape(cfg['site_name'])}</h1>
    <p class="hero-tamil">{htmlmod.escape(cfg.get('site_name_tamil',''))}</p>
    <div class="hero-rule"></div>
    <p class="hero-tagline">{htmlmod.escape(cfg['tagline'])}</p>
  </div></div>
</section>
{f'<div class="wrap"><div class="chip-row">{chips}</div></div>' if chips else ''}
{featured}
{tip_strip(cfg)}
{more}
</main>
"""
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "NewsMediaOrganization",
        "name": cfg["site_name"], "url": cfg["url"],
        "logo": cfg["url"] + "/assets/img/brand/mark.jpg",
        "email": cfg["email"], "description": cfg["description"],
        "founder": {"@type": "Person", "name": cfg["author"]},
        "sameAs": [cfg[k] for k in ("instagram", "youtube", "twitter", "facebook") if cfg.get(k)],
    }, ensure_ascii=False)
    extra = f'<script type="application/ld+json">{ld}</script>'
    write("index.html", head(cfg, cfg["site_name"], cfg["description"], "/", extra=extra)
          + body + footer(cfg, cats_present))


def build_story(cfg, s, cfg_cats, prev=None, nxt=None):
    from urllib.parse import quote
    url = cfg["url"] + s["url"]
    share_text = quote(f"{s['title']} — {cfg['site_name']}")
    tags = "".join(f'<span class="tag">#{htmlmod.escape(str(t))}</span>' for t in s["tags"])

    hero = ""
    if s["image"]:
        cap = f'<div class="figcaption">{inline(s["image_caption"])}</div>' if s["image_caption"] else ""
        hero = f'<figure class="article-hero"><img src="{s["image"]}" alt="{htmlmod.escape(s["title"])}" fetchpriority="high"></figure>{cap}'

    nav = ""
    if prev or nxt:
        bits = []
        if nxt:
            bits.append(f'<a class="btn btn-ghost" href="{nxt["url"]}">← {htmlmod.escape(nxt["title"][:52])}</a>')
        if prev:
            bits.append(f'<a class="btn btn-ghost" href="{prev["url"]}">{htmlmod.escape(prev["title"][:52])} →</a>')
        nav = f'<div class="btn-row" style="justify-content:space-between;margin-top:40px">{"".join(bits)}</div>'

    ld = json.dumps({
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": s["title"], "datePublished": s["iso"], "dateModified": s["iso"],
        "description": s["summary"],
        "image": [(cfg["url"] + s["image"]) if s["image"] and not s["image"].startswith("http") else (s["image"] or cfg["url"] + "/assets/img/brand/social-card.jpg")],
        "author": {"@type": "Person", "name": cfg["author"]},
        "publisher": {"@type": "Organization", "name": cfg["site_name"],
                      "logo": {"@type": "ImageObject", "url": cfg["url"] + "/assets/img/brand/mark.jpg"}},
        "mainEntityOfPage": url,
        "articleSection": cat_name(cfg, s["category"]),
    }, ensure_ascii=False)

    loc = f'<span class="sep">·</span><span>{htmlmod.escape(s["location"])}</span>' if s["location"] else ""

    body = f"""{header(cfg, 'news')}
<main id="main">
<article>
  <div class="wrap-narrow article-head">
    <div class="breadcrumb"><a href="/">Home</a><span>/</span><a href="/category/{s['category']}/">{htmlmod.escape(cat_name(cfg, s['category']))}</a></div>
    <h1 class="article-title">{htmlmod.escape(s['title'])}</h1>
    <p class="article-standfirst">{inline(s['summary'])}</p>
    <div class="byline">
      <img src="/assets/img/brand/mark.jpg" alt="" width="40" height="40">
      <span>By <strong>{htmlmod.escape(cfg['author'])}</strong></span>
      <span class="sep">·</span>
      <time datetime="{s['date']:%Y-%m-%d}">{fmt_date(s['date'])}</time>
      <span class="sep">·</span><span>{s['read_min']} min read</span>{loc}
    </div>
    {hero}
    <div class="prose{' dropcap' if s['dropcap'] else ''}">
      {s['html']}
    </div>
    {f'<div class="tag-row">{tags}</div>' if tags else ''}
    <div class="share">
      <span class="share-label">Share</span>
      <a class="share-btn" href="https://wa.me/?text={share_text}%20{quote(url)}" target="_blank" rel="noopener">{icon('whatsapp')} WhatsApp</a>
      <a class="share-btn" href="https://twitter.com/intent/tweet?text={share_text}&url={quote(url)}" target="_blank" rel="noopener">{icon('x')} Post</a>
      <a class="share-btn" href="https://www.facebook.com/sharer/sharer.php?u={quote(url)}" target="_blank" rel="noopener">{icon('facebook')} Share</a>
      <button class="share-btn" data-copy="{url}">{icon('link')} Copy link</button>
    </div>
    <div class="author-box">
      <img src="/assets/img/brand/mark.jpg" alt="" width="66" height="66">
      <div>
        <h3>{htmlmod.escape(cfg['author'])}</h3>
        <p class="role">{htmlmod.escape(cfg['author_role'])}</p>
        <p>{htmlmod.escape(cfg['author_bio'])}</p>
      </div>
    </div>
    {nav}
  </div>
</article>
{tip_strip(cfg)}
</main>
"""
    extra = f'<script type="application/ld+json">{ld}</script>'
    write(f"news/{s['slug']}/index.html",
          head(cfg, s["title"], s["summary"], s["url"], s["image"] or None, "article", extra)
          + body + footer(cfg, cfg_cats))


def build_listing(cfg, stories, cats_present, title, subtitle, base_path, active_cat=None):
    pages = max(1, (len(stories) + PER_PAGE - 1) // PER_PAGE)
    for pg in range(1, pages + 1):
        chunk = stories[(pg - 1) * PER_PAGE: pg * PER_PAGE]
        chips = f'<a class="chip"{"" if active_cat else " aria-current=page"} href="/news/">All</a>' + "".join(
            f'<a class="chip"{" aria-current=page" if c == active_cat else ""} href="/category/{c}/">{htmlmod.escape(cat_name(cfg, c))}</a>'
            for c in cats_present)

        grid = (f'<div class="story-grid">{"".join(card(cfg, s) for s in chunk)}</div>'
                if chunk else '<div class="empty"><h3>Nothing here yet</h3><p>Stories in this section will show up here.</p></div>')

        pager = ""
        if pages > 1:
            links = []
            for n in range(1, pages + 1):
                href = base_path if n == 1 else f"{base_path}page/{n}/"
                links.append(f'<span class="current">{n}</span>' if n == pg else f'<a href="{href}">{n}</a>')
            pager = f'<div class="pager">{"".join(links)}</div>'

        rel = base_path.strip("/") + ("/index.html" if pg == 1 else f"/page/{pg}/index.html")

        # A search box on the main archive page — it grows more useful with
        # every story filed.
        search = ""
        if base_path == "/news/" and pg == 1 and stories:
            search = """
    <div class="searchbar">
      <input type="search" id="siteSearch" placeholder="Search headlines, places, words in stories…"
             aria-label="Search stories" autocomplete="off" data-index="/search.json">
      <p class="search-count" id="searchCount" hidden></p>
    </div>"""

        body = f"""{header(cfg, 'news')}
<main id="main">
  <div class="wrap page-head">
    <h1 class="page-title">{htmlmod.escape(title)}</h1>
    <p class="page-sub">{htmlmod.escape(subtitle)}</p>
    <div class="chip-row">{chips}</div>{search}
  </div>
  <section class="section"><div class="wrap">
    <div id="searchResults" class="story-grid" hidden></div>
    <div id="defaultList">{grid}{pager}</div>
  </div></section>
</main>
"""
        path = base_path if pg == 1 else f"{base_path}page/{pg}/"
        write(rel, head(cfg, title, subtitle, path) + body + footer(cfg, cats_present))


def build_page(cfg, path, cats_present, title, subtitle, inner, active=""):
    body = f"""{header(cfg, active)}
<main id="main">
  <div class="wrap-narrow page-head">
    <h1 class="page-title">{htmlmod.escape(title)}</h1>
    <p class="page-sub">{htmlmod.escape(subtitle)}</p>
  </div>
  <section class="section"><div class="wrap-narrow">{inner}</div></section>
</main>
"""
    write(path.strip("/") + "/index.html" if path != "/" else "index.html",
          head(cfg, title, subtitle, path) + body + footer(cfg, cats_present))


def build_contact(cfg, cats_present):
    cards = []
    if re.sub(r"\D", "", str(cfg.get("whatsapp_number", ""))):
        cards.append(f"""<a class="contact-card" href="{wa_link(cfg)}" target="_blank" rel="noopener">
      <div class="ico">{icon('whatsapp')}</div>
      <h3>WhatsApp</h3>
      <p>Fastest way to reach me. Send photos, videos, voice notes or a location pin from wherever you are.</p>
      <span class="val">Open WhatsApp →</span></a>""")
    cards.append(f"""<a class="contact-card" href="mailto:{cfg['email']}">
      <div class="ico">{icon('mail')}</div>
      <h3>Email the newsroom</h3>
      <p>For documents, RTI replies, longer tip-offs, or anything you want on record.</p>
      <span class="val">{htmlmod.escape(cfg['email'])}</span></a>""")
    if cfg.get("instagram"):
        cards.append(f"""<a class="contact-card" href="{cfg['instagram']}" target="_blank" rel="noopener">
      <div class="ico">{icon('instagram')}</div>
      <h3>Instagram</h3>
      <p>Daily reels, photo stories and field updates. DMs are open.</p>
      <span class="val">Follow @cosmossudar →</span></a>""")
    if cfg.get("youtube"):
        cards.append(f"""<a class="contact-card" href="{cfg['youtube']}" target="_blank" rel="noopener">
      <div class="ico">{icon('youtube')}</div>
      <h3>YouTube</h3>
      <p>Long-form ground reports and full interviews from the constituencies.</p>
      <span class="val">Watch the reports →</span></a>""")

    inner = f"""<div class="contact-grid">{''.join(cards)}</div>
<div class="prose">
  <h2>Sending a tip safely</h2>
  <p>If you are worried about being identified, tell me so in your very first message. I will not publish your name, your village, or any detail that could point back to you without asking you first. If it is safer for you, use a phone that is not your own, or ask someone you trust to write on your behalf.</p>
  <h2>What makes a good tip</h2>
  <ul>
    <li><strong>Where.</strong> Village, town, ward or constituency — as exact as you can manage.</li>
    <li><strong>When.</strong> The date it happened, or the date you noticed it.</li>
    <li><strong>Proof.</strong> Photos, a short video, a bill, a notice, an order copy. Even a blurry photo helps.</li>
    <li><strong>Who is affected.</strong> How many people, and how it changed their day-to-day life.</li>
  </ul>
  <p>I read every message myself. I cannot report every story, but I reply to everyone who sends one.</p>
  <h2>Corrections</h2>
  <p>If something published here is wrong, write to <a href="mailto:{cfg['email']}">{htmlmod.escape(cfg['email'])}</a> with the word <strong>CORRECTION</strong> in the subject. Verified errors are fixed within 24 hours and the change is noted at the bottom of the story.</p>
</div>"""
    build_page(cfg, "/contact/", cats_present, "Contact & News Tips",
               "Tell me what is happening where you live. Every message is read by me personally.",
               inner, "contact")


def build_feeds(cfg, stories):
    items = []
    for s in stories[:30]:
        link = cfg["url"] + s["url"]
        img = ""
        if s["image"]:
            src = s["image"] if s["image"].startswith("http") else cfg["url"] + s["image"]
            img = f'&lt;p&gt;&lt;img src="{xesc(src)}"/&gt;&lt;/p&gt;'
        items.append(f"""  <item>
    <title>{xesc(s['title'])}</title>
    <link>{xesc(link)}</link>
    <guid isPermaLink="true">{xesc(link)}</guid>
    <pubDate>{s['date'].strftime('%a, %d %b %Y %H:%M:%S +0530')}</pubDate>
    <category>{xesc(cat_name(cfg, s['category']))}</category>
    <description>{xesc(s['summary'])}</description>
    <content:encoded>{img}{xesc(s['html'])}</content:encoded>
  </item>""")
    write("feed.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{xesc(cfg['site_name'])}</title>
  <link>{cfg['url']}</link>
  <atom:link href="{cfg['url']}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>{xesc(cfg['description'])}</description>
  <language>en-in</language>
  <lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>""")


def build_sitemap(cfg, stories, cats_present):
    urls = ["/", "/news/", "/about/", "/ethics/", "/contact/"]
    urls += [f"/category/{c}/" for c in cats_present]
    urls += [s["url"] for s in stories]
    body = "".join(f"  <url><loc>{cfg['url']}{u}</loc></url>\n" for u in urls)
    write("sitemap.xml",
          f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>')
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {cfg['url']}/sitemap.xml\n")


def build_404(cfg, cats_present, stories):
    recent = "".join(card(cfg, s, "sm") for s in stories[:3])
    body = f"""{header(cfg)}
<main id="main">
  <div class="wrap-narrow page-head" style="text-align:center">
    <h1 class="page-title">Lost in space</h1>
    <p class="page-sub" style="margin-inline:auto">This page does not exist — or it moved. Try the latest reports instead.</p>
    <div class="btn-row" style="margin-top:28px"><a class="btn btn-primary" href="/">Back to the front page</a><a class="btn btn-ghost" href="/news/">All stories</a></div>
  </div>
  <section class="section"><div class="wrap-narrow"><div class="lead-side">{recent}</div></div></section>
</main>
"""
    write("404.html", head(cfg, "Page not found", "This page does not exist.", "/404.html") + body + footer(cfg, cats_present))


def build_search_index(stories, cfg):
    data = [{"t": s["title"], "u": s["url"], "s": s["summary"],
             "c": cat_name(cfg, s["category"]), "d": f"{s['date']:%Y-%m-%d}",
             "i": s["image"], "b": s["plain"][:600]} for s in stories]
    write("search.json", json.dumps(data, ensure_ascii=False))


def copy_static():
    if ASSETS.exists():
        shutil.copytree(ASSETS, OUT / "assets", dirs_exist_ok=True)
    for name in ("CNAME", "favicon.ico", ".nojekyll"):
        p = ROOT / name
        if p.exists():
            shutil.copy2(p, OUT / name)
    (OUT / ".nojekyll").touch()


# ==================================================================== main
def main():
    cfg = load_site()
    stories = load_stories(cfg)

    # Clear the previous build. Some synced/network folders refuse deletes;
    # if so we simply write over the top rather than failing the whole build.
    if OUT.exists():
        def _ignore(func, path, exc):
            warnings.append(f"Could not remove old file {Path(path).name} (harmless).")
        shutil.rmtree(OUT, onerror=_ignore)
    OUT.mkdir(parents=True, exist_ok=True)

    order = [c["id"] for c in cfg["categories"]]
    present = [c for c in order if any(s["category"] == c for s in stories)]
    for s in stories:
        if s["category"] not in present and s["category"] not in order:
            present.append(s["category"])

    copy_static()
    build_home(cfg, stories, present)
    build_listing(cfg, stories, present, "All Stories",
                  "Every report published by Cosmos Sudar, newest first.", "/news/")

    for c in present:
        sub = [s for s in stories if s["category"] == c]
        build_listing(cfg, sub, present, cat_name(cfg, c),
                      f"{len(sub)} report{'s' if len(sub) != 1 else ''} filed under {cat_name(cfg, c).lower()}.",
                      f"/category/{c}/", active_cat=c)

    for idx, s in enumerate(stories):
        build_story(cfg, s, present,
                    prev=stories[idx + 1] if idx + 1 < len(stories) else None,
                    nxt=stories[idx - 1] if idx > 0 else None)

    # Static pages written in markdown
    for name, title, sub, active in (
        ("about", "About Cosmos Sudar", "Who is behind this, and why it exists.", "about"),
        ("ethics", "Ethics & Corrections", "How this newsroom works, and how to hold it to account.", "ethics"),
    ):
        f = PAGES_DIR / f"{name}.md"
        if f.exists():
            meta, body = parse_front_matter(f.read_text(encoding="utf-8"))
            build_page(cfg, f"/{name}/", present, meta.get("title", title),
                       meta.get("summary", sub), f'<div class="prose">{markdown(body)}</div>', active)

    build_contact(cfg, present)
    build_feeds(cfg, stories)
    build_sitemap(cfg, stories, present)
    build_404(cfg, present, stories)
    build_search_index(stories, cfg)

    print(f"✓ Built {len(stories)} stories, {len(present)} sections → _site/")
    for w in warnings:
        print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
