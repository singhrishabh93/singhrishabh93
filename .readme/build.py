#!/usr/bin/env python3
"""Builds the GitHub profile README as SVG sections styled like rishabhsingh.tech.

GitHub strips CSS and web fonts from READMEs, so every section is rendered to
an SVG with Geist Mono embedded (subset to the glyphs that SVG uses) and the
site's light/dark tokens. README.md swaps the light/dark files with <picture>.

    pip install fonttools brotli
    python .readme/build.py            # uses live data when reachable
    python .readme/build.py --offline  # cached / fallback data only
"""

import base64
import datetime as dt
import html
import io
import json
import math
import os
import re
import sys
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "assets")
CACHE = os.path.join(HERE, "cache")
OFFLINE = "--offline" in sys.argv

W = 640  # the site's content column: 768px max-width minus 64px padding each side
MONO = 0.6  # Geist Mono advance width, in em

THEMES = {
    "light": {
        "primary": "#000", "body": "#1e2939", "soft": "#364153", "secondary": "#6a7282",
        "border_soft": "#e5e7eb", "border_pill": "#d1d5dc", "bg": "#fdfff4",
        "card": "rgba(249,250,251,0.2)", "pill_bg": "rgba(0,0,0,0.03)", "pill_border": "#e5e7eb",
        "badge_bg": "#000", "badge_fg": "#f5f5f5", "badge_border": "#e5e5e5",
        "deco": "#d4d4d4", "blog_desc": "#4a5565",
        "binary": "#6a7282", "binary_opacity": 0.05,
        "cells": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], "cell_outline": "rgba(27,31,35,0.06)",
    },
    "dark": {
        "primary": "#eee", "body": "#d4d4d4", "soft": "#b5b5b5", "secondary": "#888",
        "border_soft": "rgba(255,255,255,0.1)", "border_pill": "rgba(255,255,255,0.2)", "bg": "#0c0c0c",
        "card": "rgba(255,255,255,0.02)", "pill_bg": "rgba(255,255,255,0.04)", "pill_border": "rgba(255,255,255,0.08)",
        "badge_bg": "#eee", "badge_fg": "#111", "badge_border": "#e5e5e5",
        "deco": "#d4d4d4", "blog_desc": "#b5b5b5",
        "binary": "#d4d4d4", "binary_opacity": 0.06,
        "cells": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"], "cell_outline": "rgba(255,255,255,0.05)",
    },
}

FONT_FILES = {
    (400, "normal"): "GeistMono-Regular.woff2",
    (500, "normal"): "GeistMono-Medium.woff2",
    (600, "normal"): "GeistMono-SemiBold.woff2",
    (700, "normal"): "GeistMono-Bold.woff2",
    (400, "italic"): "GeistMono-Italic.woff2",
}

# Phosphor icons (256 viewBox), same as the site's links row.
ICONS = {
    "github": "M208.31,75.68A59.78,59.78,0,0,0,202.93,28,8,8,0,0,0,196,24a59.75,59.75,0,0,0-48,24H124A59.75,59.75,0,0,0,76,24a8,8,0,0,0-6.93,4,59.78,59.78,0,0,0-5.38,47.68A58.14,58.14,0,0,0,56,104v8a56.06,56.06,0,0,0,48.44,55.47A39.8,39.8,0,0,0,96,192v8H72a24,24,0,0,1-24-24A40,40,0,0,0,8,136a8,8,0,0,0,0,16,24,24,0,0,1,24,24,40,40,0,0,0,40,40H96v16a8,8,0,0,0,16,0V192a24,24,0,0,1,48,0v40a8,8,0,0,0,16,0V192a39.8,39.8,0,0,0-8.44-24.53A56.06,56.06,0,0,0,216,112v-8A58.14,58.14,0,0,0,208.31,75.68ZM200,112a40,40,0,0,1-40,40H112a40,40,0,0,1-40-40v-8a41.74,41.74,0,0,1,6.9-22.48A8,8,0,0,0,80,73.83a43.81,43.81,0,0,1,.79-33.58,43.88,43.88,0,0,1,32.32,20.06A8,8,0,0,0,119.82,64h32.35a8,8,0,0,0,6.74-3.69,43.87,43.87,0,0,1,32.32-20.06A43.81,43.81,0,0,1,192,73.83a8.09,8.09,0,0,0,1,7.65A41.72,41.72,0,0,1,200,104Z",
    "x": "M214.75,211.71l-62.6-98.38,61.77-67.95a8,8,0,0,0-11.84-10.76L143.24,99.34,102.75,35.71A8,8,0,0,0,96,32H48a8,8,0,0,0-6.75,12.3l62.6,98.37-61.77,68a8,8,0,1,0,11.84,10.76l58.84-64.72,40.49,63.63A8,8,0,0,0,160,224h48a8,8,0,0,0,6.75-12.29ZM164.39,208,62.57,48h29L193.43,208Z",
    "linkedin": "M216,24H40A16,16,0,0,0,24,40V216a16,16,0,0,0,16,16H216a16,16,0,0,0,16-16V40A16,16,0,0,0,216,24Zm0,192H40V40H216V216ZM96,112v64a8,8,0,0,1-16,0V112a8,8,0,0,1,16,0Zm88,28v36a8,8,0,0,1-16,0V140a20,20,0,0,0-40,0v36a8,8,0,0,1-16,0V112a8,8,0,0,1,15.79-1.78A36,36,0,0,1,184,140ZM100,84A12,12,0,1,1,88,72,12,12,0,0,1,100,84Z",
    "email": "M224,48H32a8,8,0,0,0-8,8V192a16,16,0,0,0,16,16H216a16,16,0,0,0,16-16V56A8,8,0,0,0,224,48Zm-96,85.15L52.57,64H203.43ZM98.71,128,40,181.81V74.19Zm11.84,10.85,12,11.05a8,8,0,0,0,10.82,0l12-11.05,58,53.15H52.57ZM157.29,128,216,74.18V181.82Z",
    "instagram": "M128,80a48,48,0,1,0,48,48A48.05,48.05,0,0,0,128,80Zm0,80a32,32,0,1,1,32-32A32,32,0,0,1,128,160ZM176,24H80A56.06,56.06,0,0,0,24,80v96a56.06,56.06,0,0,0,56,56h96a56.06,56.06,0,0,0,56-56V80A56.06,56.06,0,0,0,176,24Zm40,152a40,40,0,0,1-40,40H80a40,40,0,0,1-40-40V80A40,40,0,0,1,80,40h96a40,40,0,0,1,40,40ZM192,76a12,12,0,1,1-12-12A12,12,0,0,1,192,76Z",
    "resume": "M213.66,82.34l-56-56A8,8,0,0,0,152,24H56A16,16,0,0,0,40,40V216a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V88A8,8,0,0,0,213.66,82.34ZM160,51.31,188.69,80H160ZM200,216H56V40h88V88a8,8,0,0,0,8,8h48V216Zm-32-80a8,8,0,0,1-8,8H96a8,8,0,0,1,0-16h64A8,8,0,0,1,168,136Zm0,32a8,8,0,0,1-8,8H96a8,8,0,0,1,0-16h64A8,8,0,0,1,168,168Z",
}

GITHUB_MARK = "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"



# --------------------------------------------------------------------------- fonts

_font_cache = {}


def font_face(weight, style, chars):
    key = (weight, style, "".join(sorted(chars)))
    if key not in _font_cache:
        font = TTFont(os.path.join(HERE, "fonts", FONT_FILES[(weight, style)]))
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = []
        opts.name_IDs = []
        opts.notdef_outline = True
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(chars))
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff2"
        font.save(buf)
        _font_cache[key] = base64.b64encode(buf.getvalue()).decode()
    return (
        "@font-face{font-family:'GM';font-weight:%d;font-style:%s;"
        "src:url(data:font/woff2;base64,%s) format('woff2')}" % (weight, style, _font_cache[key])
    )


def tw(s, size):
    """Width of a string set in Geist Mono at `size` px."""
    return len(s) * MONO * size


def esc(s):
    return html.escape(s, quote=True)


_img_cache = {}


def data_uri(name):
    if name not in _img_cache:
        path = os.path.join(HERE, "img", name)
        mime = "image/svg+xml" if name.endswith(".svg") else "image/webp"
        with open(path, "rb") as f:
            _img_cache[name] = "data:%s;base64,%s" % (mime, base64.b64encode(f.read()).decode())
    return _img_cache[name]


# --------------------------------------------------------------------------- svg canvas


class Canvas:
    def __init__(self, theme, width=W):
        self.t = THEMES[theme]
        self.theme = theme
        self.w = width
        self.h = 0
        self.defs = []
        self.els = []
        self.glyphs = {}
        self.extra_css = ""
        self._ids = 0

    def uid(self, prefix):
        self._ids += 1
        return "%s%d" % (prefix, self._ids)

    def text(self, x, y, s, size=14, weight=400, italic=False, fill=None, anchor="start", extra=""):
        style = "italic" if italic else "normal"
        if (weight, style) not in FONT_FILES:
            weight = 400
        self.glyphs.setdefault((weight, style), set()).update(s)
        attrs = 'x="%.2f" y="%.2f" font-size="%s" fill="%s"' % (x, y, size, fill or self.t["primary"])
        if weight != 400:
            attrs += ' font-weight="%d"' % weight
        if italic:
            attrs += ' font-style="italic"'
        if anchor != "start":
            attrs += ' text-anchor="%s"' % anchor
        self.els.append("<text %s%s>%s</text>" % (attrs, extra, esc(s)))

    def raw(self, s):
        self.els.append(s)

    def rect(self, x, y, w, h, rx=0, fill="none", stroke=None, sw=1, extra=""):
        s = '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%s" fill="%s"' % (x, y, w, h, rx, fill)
        if stroke:
            s += ' stroke="%s" stroke-width="%s"' % (stroke, sw)
        self.els.append(s + extra + "/>")

    def line(self, x1, y1, x2, y2, stroke, sw=1, extra=""):
        self.els.append(
            '<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%s"%s/>'
            % (x1, y1, x2, y2, stroke, sw, extra)
        )

    def underline(self, x, baseline, width, color, offset=2, dash=None):
        y = baseline + offset + 1.5
        extra = ' stroke-dasharray="%s"' % dash if dash else ""
        self.line(x, y, x + width, y, color, 1, extra)

    def wavy(self, x, baseline, width, color):
        y = baseline + 3.5
        period, amp = 4.0, 1.2
        d = "M%.2f %.2f" % (x, y)
        n = max(1, int(width // period))
        for i in range(n):
            x0 = x + i * period
            d += " Q%.2f %.2f %.2f %.2f Q%.2f %.2f %.2f %.2f" % (
                x0 + period / 4, y - amp, x0 + period / 2, y,
                x0 + 3 * period / 4, y + amp, x0 + period, y,
            )
        self.els.append('<path d="%s" fill="none" stroke="%s" stroke-width="1"/>' % (d, color))

    def image(self, x, y, w, h, name, extra=""):
        self.els.append(
            '<image x="%.2f" y="%.2f" width="%.2f" height="%.2f" href="%s"%s/>' % (x, y, w, h, data_uri(name), extra)
        )

    def icon(self, x, y, size, d, fill, vb=256):
        s = size / vb
        self.els.append(
            '<path transform="translate(%.2f %.2f) scale(%.5f)" d="%s" fill="%s"/>' % (x, y, s, d, fill)
        )

    def svg(self, title):
        faces = "".join(font_face(w, s, chars) for (w, s), chars in sorted(self.glyphs.items()))
        css = (
            faces
            + "text{font-family:'GM',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre}"
            + self.extra_css
        )
        h = math.ceil(self.h)
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{title}">'
            "<title>{title}</title><defs><style>{css}</style>{defs}</defs>{body}</svg>"
        ).format(w=self.w, h=h, title=esc(title), css=css, defs="".join(self.defs), body="".join(self.els))


# Baselines: the site uses 14px text on a 22.75px line (body line-height 1.625).
LH = 22.75


def baseline_in(line_h, size):
    content = (1.005 + 0.295) * size
    return (line_h - content) / 2 + 1.005 * size


def heading(c, y, label, arrow=False):
    """Section h2: 14px bold, 8px below."""
    c.text(0, y + baseline_in(LH, 14), label + (" ↗" if arrow else ""), 14, 700)
    return y + LH + 8


# --------------------------------------------------------------------------- sections


def binary_rows(width, rows):
    words = (
        "Rishabh Singh Flutter React Native Next.js Mobile Web AI Product Engineer Ships Really Fast "
        "Design Systems Scalable Apps Backend Cloud "
    ) * 2
    groups = [format(ord(ch), "08b") for ch in words]
    per_line = int(width // tw("00000000 ", 12)) + 1  # overflow; the edge fade hides the cut
    lines, i = [], 0
    while len(lines) < rows:
        chunk = [groups[(i + k) % len(groups)] for k in range(per_line)]
        lines.append(" ".join(chunk))
        i += per_line
    return lines


def section_hero(theme, C, gh):
    c = Canvas(theme)
    t = c.t
    top, h = 36, 140
    c.h = h

    # Drifting binary backdrop, faded at the edges so it melts into GitHub's background.
    fade_v, fade_h, mask = c.uid("fv"), c.uid("fh"), c.uid("m")
    c.defs.append(
        '<linearGradient id="%s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".25" stop-color="#fff"/>'
        '<stop offset=".7" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="%s" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#000"/><stop offset=".12" stop-color="#000" stop-opacity="0"/>'
        '<stop offset=".88" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000"/></linearGradient>'
        '<mask id="%s" maskUnits="userSpaceOnUse" x="0" y="0" width="%d" height="%d">'
        '<rect width="%d" height="%d" fill="url(#%s)"/><rect width="%d" height="%d" fill="url(#%s)"/></mask>'
        % (fade_v, fade_h, mask, W, h, W, h, fade_v, W, h, fade_h)
    )
    rows = binary_rows(W, int((h + 100) / 14.4) + 2)
    c.raw('<g mask="url(#%s)" opacity="%s"><g>' % (mask, t["binary_opacity"]))
    for i, row in enumerate(rows):
        c.text(0, 12 + i * 14.4, row, 12, fill=t["binary"])
    c.raw(
        '<animateTransform attributeName="transform" type="translate" from="0 0" to="0 -100" '
        'dur="60s" repeatCount="indefinite"/></g></g>'
    )

    # Left: name, role pill, tagline.
    y = top
    c.text(0, y + baseline_in(LH, 14), C["name"], 14)
    y += LH + 4

    role = C["role"]
    pw, ph = tw(role, 10) + 8, 20.25
    grad = c.uid("g")
    c.defs.append(
        '<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="%.2f" y2="0" spreadMethod="repeat">'
        '<stop offset="0" stop-color="#9b51e0"/><stop offset=".25" stop-color="#06b6d4"/>'
        '<stop offset=".5" stop-color="#ec4899"/><stop offset=".75" stop-color="#06b6d4"/>'
        '<stop offset="1" stop-color="#9b51e0"/>'
        '<animateTransform attributeName="gradientTransform" type="translate" from="0 0" to="%.2f 0" '
        'dur="4s" repeatCount="indefinite"/></linearGradient>' % (grad, pw * 2, pw * 2)
    )
    c.rect(0.5, y + 0.5, pw - 1, ph - 1, 6, stroke="url(#%s)" % grad)
    c.text(4, y + 2 + baseline_in(16.25, 10), role, 10, fill=t["secondary"])
    y += ph + 4

    lead, em = C["tagline"]
    b = y + baseline_in(20, 14)
    c.text(0, b, lead, 14)
    ex = tw(lead, 14)
    c.text(ex, b, em, 14, italic=True)
    c.underline(ex, b, tw(em, 14), t["deco"])

    # Right: handle, join date, portfolio link.
    rx = W
    y = top + 3
    c.text(rx, y + 12, "@" + C["username"], 12, fill=t["secondary"], anchor="end")
    y += 16 + 6
    if gh and gh.get("user", {}).get("created_at"):
        joined = dt.date.fromisoformat(gh["user"]["created_at"][:10])
        c.text(rx, y + 12, "on github since %d" % joined.year, 12, fill=t["secondary"], anchor="end")
    y += 16 + 6
    label = "portfolio ↗"
    rw = tw(label, 12)
    c.text(rx, y + 12, label, 12, anchor="end")
    c.underline(rx - rw, y + 12, rw, t["primary"], offset=3)
    # Sun glyph from the site's theme toggle.
    sx, sy = rx - rw - 6 - 7, y + 8
    c.raw('<g stroke="%s" stroke-width="1.3" stroke-linecap="round" fill="none">' % t["secondary"])
    c.raw('<circle cx="%.2f" cy="%.2f" r="2.6"/>' % (sx, sy))
    for k in range(8):
        a = k * math.pi / 4
        c.raw(
            '<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f"/>'
            % (sx + 4.4 * math.cos(a), sy + 4.4 * math.sin(a), sx + 5.8 * math.cos(a), sy + 5.8 * math.sin(a))
        )
    c.raw("</g>")
    return c


# Inline rich text for the intro. Pieces: ("t", text) plain, ("hi", text) wavy underline,
# ("em", text) italic with dashed underline, ("u", text) underlined link text.
def _piece_width(p):
    return tw(p[1], 14)


def _draw_piece(c, p, x, b):
    t = c.t
    kind, s = p
    if kind == "t":
        c.text(x, b, s, 14, fill=t["body"])
    elif kind == "hi":
        c.text(x, b, s, 14, 500, fill=t["body"])
        c.wavy(x, b, tw(s, 14), t["deco"])
    elif kind == "em":
        c.text(x, b, s, 14, italic=True, fill=t["primary"])
        c.underline(x, b, tw(s, 14), t["primary"], offset=3, dash="2 2")
    elif kind == "u":
        c.text(x, b, s, 14, fill=t["primary"])
        c.underline(x, b, tw(s, 14), t["primary"])


def _atoms(paragraph):
    atoms = []
    for p in paragraph:
        if p[0] == "t":
            for tok in re.findall(r"\S+|\s+", p[1]):
                atoms.append(("space" if tok.isspace() else "word", [("t", tok)]))
        else:
            atoms.append(("word", [p]))
    return atoms


def layout_paragraph(c, paragraph, y, width=W):
    lines, line, x = [], [], 0.0
    for kind, pieces in _atoms(paragraph):
        w = sum(_piece_width(p) for p in pieces)
        if kind == "space":
            if line:
                line.append((x, pieces))
            x += w
            continue
        if x + w > width and line:
            while line and line[-1][1][0][0] == "t" and line[-1][1][0][1].isspace():
                line.pop()
            lines.append(line)
            line, x = [], 0.0
        line.append((x, pieces))
        x += w
    if line:
        lines.append(line)
    for i, ln in enumerate(lines):
        b = y + i * LH + baseline_in(LH, 14)
        for x0, pieces in ln:
            for p in pieces:
                _draw_piece(c, p, x0, b)
                x0 += _piece_width(p)
    return y + len(lines) * LH


def section_intro(theme, C):
    c = Canvas(theme)
    y = heading(c, 0, C["intro_title"])
    paras = C["intro"]
    for i, para in enumerate(paras):
        y = layout_paragraph(c, [tuple(p) for p in para], y)
        if i < len(paras) - 1:
            y += 10
    c.h = y + 6
    return c


def compact(n):
    if n >= 10000:
        return "%.0fk" % (n / 1000)
    if n >= 1000:
        return "%.1fk" % (n / 1000)
    return str(n)


def section_stats(theme, gh, contrib):
    c = Canvas(theme)
    t = c.t
    y = heading(c, 0, "by the numbers")
    tiles = [
        ("public repos", gh["user"]["public_repos"]),
        ("stars earned", gh["stars"]),
        ("pull requests", gh["prs"]),
        ("followers", gh["user"]["followers"]),
    ]
    gap, th = 8, 66
    tw_ = (W - gap * (len(tiles) - 1)) / len(tiles)
    for i, (label, value) in enumerate(tiles):
        x = i * (tw_ + gap)
        c.rect(x + 0.5, y + 0.5, tw_ - 1, th - 1, 8, fill=t["card"], stroke=t["border_soft"])
        c.text(x + 14, y + 22, label.upper(), 10, fill=t["secondary"])
        c.text(x + 14, y + 50, compact(value), 22, 600)
    c.h = y + th + 4
    return c


# GitHub linguist colours for the languages likely to show up.
LANG_COLORS = {
    "Dart": "#00B4AB", "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#663399", "SCSS": "#c6538c", "Java": "#b07219", "Kotlin": "#A97BFF",
    "Swift": "#F05138", "Objective-C": "#438eff", "C++": "#f34b7d", "C": "#555555", "C#": "#178600",
    "Go": "#00ADD8", "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95", "Vue": "#41b883",
    "Svelte": "#ff3e00", "Shell": "#89e051", "ShaderLab": "#222c37", "HLSL": "#aace60",
    "Makefile": "#427819", "Jupyter Notebook": "#DA5B0B", "Dockerfile": "#384d54", "CMake": "#DA3434",
    "Astro": "#ff5a03", "MDX": "#fcb32c", "Lua": "#000080", "Solidity": "#AA6746", "GLSL": "#5686a5",
    "Objective-C++": "#6866fb", "Ruby on Rails": "#701516", "EJS": "#a91e50", "Handlebars": "#f7931e",
}


def section_languages(theme, gh):
    c = Canvas(theme)
    t = c.t
    y = heading(c, 0, "languages")
    langs = gh["languages"]
    total = sum(b for _, b in langs) or 1
    top = langs[:6]
    rest = total - sum(b for _, b in top)
    items = [(n, b, LANG_COLORS.get(n, "#8b949e")) for n, b in top]
    if rest / total >= 0.005:
        items.append(("Other", rest, t["border_pill"]))

    # Segmented bar, like the one on a GitHub repo page.
    clip = c.uid("bar")
    c.defs.append('<clipPath id="%s"><rect x="0" y="%.2f" width="%d" height="8" rx="4"/></clipPath>' % (clip, y + 2, W))
    c.raw('<g clip-path="url(#%s)">' % clip)
    x = 0.0
    for i, (_, b, color) in enumerate(items):
        w = W * b / total
        c.rect(x, y + 2, max(0.0, w - (2 if i < len(items) - 1 else 0)), 8, fill=color)
        x += w
    c.raw("</g>")
    y += 10 + 14

    # Legend: ● name  pct, wrapped.
    x = 0.0
    for name, b, color in items:
        pct = "%.1f%%" % (100 * b / total)
        w = 8 + 6 + tw(name, 12) + 6 + tw(pct, 12)
        if x + w > W:
            x, y = 0.0, y + 22
        c.raw('<circle cx="%.2f" cy="%.2f" r="4" fill="%s"/>' % (x + 4, y + 8, color))
        c.text(x + 14, y + 12, name, 12, 500)
        c.text(x + 14 + tw(name, 12) + 6, y + 12, pct, 12, fill=t["secondary"])
        x += w + 18
    c.h = y + 20
    return c


def streaks(contrib):
    days = [d for wk in contrib["weeks"] for d in wk if d]
    active = [(d.get("count", d["level"]) or 0) > 0 for d in days]
    longest = run = 0
    for a in active:
        run = run + 1 if a else 0
        longest = max(longest, run)
    current = 0
    tail = active[:-1] if active and not active[-1] else active  # today may still be empty
    for a in reversed(tail):
        if not a:
            break
        current += 1
    return current, longest


def section_shiplog(theme, C, contrib):
    c = Canvas(theme)
    t = c.t
    y = heading(c, 0, "ship log")
    card_top = y
    pad_x, pad_y = 16, 12
    inner = W - 2 - pad_x * 2
    x0 = 1 + pad_x
    y += 1 + pad_y

    total = "{:,}".format(contrib["total"])
    b = y + 12
    c.text(x0, b, total, 12, 600)
    c.text(x0 + tw(total, 12), b, " contributions in the last year", 12)
    current, longest = streaks(contrib)
    streak = "streak %dd · longest %dd" % (current, longest)
    c.text(x0 + inner, b, streak, 12, fill=t["secondary"], anchor="end")
    y += 19.5 + 12

    weeks = contrib["weeks"]
    n = len(weeks)
    gap_x = inner * 0.004
    cell = (inner - gap_x * (n - 1)) / n
    gap_y = 2

    # Month labels, same rule as the site: first week a month appears in, skipping week 0.
    seen = set()
    for wi, week in enumerate(weeks):
        first = next((d for d in week if d), None)
        if not first:
            continue
        key = first["date"][:7]
        if key in seen:
            continue
        seen.add(key)
        if wi == 0:
            continue
        label = dt.date.fromisoformat(first["date"]).strftime("%b")
        c.text(x0 + inner * wi / n, y + 10, label, 10, fill=t["secondary"])
    y += 12 + 4

    for wi, week in enumerate(weeks):
        for di, day in enumerate(week):
            if not day:
                continue
            cx = x0 + wi * (cell + gap_x)
            cy = y + di * (cell + gap_y)
            c.raw('<rect x="%.1f" y="%.1f" width="%.2f" height="%.2f" rx="2" fill="%s"/>'
                  % (cx, cy, cell, cell, t["cells"][day["level"]]))
    # One outline for every cell, as the site's 1px inset outline.
    c.extra_css += "rect[rx='2']{stroke:%s;stroke-width:1px}" % t["cell_outline"]
    y += 7 * cell + 6 * gap_y + 12

    # Legend, right-aligned: Less [] [] [] [] [] More
    lx = x0 + inner - tw("More", 11)
    c.text(lx, y + 10, "More", 11, fill=t["secondary"])
    lx -= 4
    for lvl in range(4, -1, -1):
        lx -= 10
        c.rect(lx, y + 1.5, 10, 10, 2, fill=t["cells"][lvl])
        lx -= 4
    c.text(lx - tw("Less", 11), y + 10, "Less", 11, fill=t["secondary"])
    y += 13 + pad_y + 1

    c.rect(0.5, card_top + 0.5, W - 1, y - card_top - 1, 8, fill=t["card"], stroke=t["border_soft"])
    # Card is drawn last but must sit underneath.
    c.els.insert(0, c.els.pop())

    y += 12
    b = y + 12
    c.text(0, b, "live from", 12, fill=t["secondary"])
    gx = tw("live from ", 12)
    c.icon(gx, b - 11, 14, GITHUB_MARK, t["primary"], vb=24)
    lx = gx + 14 + 6
    label = "@%s ↗" % C["username"]
    c.text(lx, b, label, 12)
    c.underline(lx, b, tw(label, 12), t["primary"], offset=2)
    c.h = y + 20
    return c


def row_canvas(theme, title, first):
    """Rows of a list are separate images (so each can link); the first carries the heading."""
    c = Canvas(theme)
    y = heading(c, 0, title) if first else 0
    return c, y


def clip_text(s, size, width):
    n = int(width // tw("a", size))
    return s if len(s) <= n else s[: max(0, n - 1)].rstrip() + "…"


STAR = "M12 .587l3.668 7.431 8.2 1.192-5.934 5.787 1.4 8.168L12 18.896l-7.334 3.857 1.4-8.168L.132 9.21l8.2-1.192z"


def section_repo_row(theme, repo, first, last):
    c, y = row_canvas(theme, "featured repos", first)
    t = c.t
    top = y + 6
    b = top + baseline_in(LH, 14)

    # Right side: ● language   ★ stars
    stars = str(repo["stars"])
    rx = W - tw(stars, 12)
    c.text(rx, b - 1, stars, 12, fill=t["secondary"])
    c.icon(rx - 16, b - 11, 11, STAR, t["secondary"], vb=24)
    rx -= 16 + 14
    if repo.get("language"):
        lang = repo["language"]
        rx -= tw(lang, 12)
        c.text(rx, b - 1, lang, 12, fill=t["secondary"])
        c.raw('<circle cx="%.2f" cy="%.2f" r="4" fill="%s"/>'
              % (rx - 10, b - 5, LANG_COLORS.get(lang, "#8b949e")))
        rx -= 16

    c.text(0, b, clip_text(repo["name"], 14, rx - 16), 14, 500)
    desc = repo.get("description") or "no description yet."
    c.text(0, top + LH + 12, clip_text(desc.lower(), 12, W), 12, fill=t["secondary"])
    row_h = 6 + LH + 18 + 8
    if not last:
        c.line(0, y + row_h - 0.5, W, y + row_h - 0.5, t["border_soft"])
    c.h = y + row_h
    return c


def ago(iso, today):
    days = max(0, (today - dt.date.fromisoformat(iso[:10])).days)
    return "today" if days == 0 else "%dd ago" % days


def section_activity(theme, events, today):
    """Timeline of the public repos pushed to most recently."""
    c = Canvas(theme)
    t = c.t
    y = heading(c, 0, "recently active")
    row = 28
    n = len(events)
    if n > 1:
        c.line(4, y + row / 2, 4, y + row * (n - 1) + row / 2, t["border_soft"])
    for i, ev in enumerate(events):
        cy = y + i * row + row / 2
        c.raw('<circle cx="4" cy="%.2f" r="3.5" fill="%s" stroke="%s"/>' % (cy, t["border_soft"], t["secondary"]))
        when = ago(ev["date"], today)
        b = cy + 4.5
        c.text(W, b, when, 12, fill=t["secondary"], anchor="end")
        room = W - 20 - tw(when, 12) - 16
        verb = ev["verb"] + " "
        target = clip_text(ev["target"], 14, room - tw(verb, 14))
        c.text(20, b, verb, 14, fill=t["body"])
        c.text(20 + tw(verb, 14), b, target, 14, 500)
    c.h = y + n * row + 2
    return c


def shipped_card(theme, doodle, title, desc):
    c = Canvas(theme)
    t = c.t
    c.image(0, 0, 50, 50, doodle, ' preserveAspectRatio="xMidYMid meet"')
    x = 62
    b = baseline_in(LH, 14)
    c.text(x, b, title + " ↗", 14, 700)
    y = LH + 4
    lines = wrap(desc, 12, W - x)
    for i, ln in enumerate(lines):
        c.text(x, y + i * 16 + 12, ln, 12, fill=t["secondary"])
    c.h = max(54, y + len(lines) * 16 + 6)
    return c


def wrap(s, size, width):
    max_chars = int(width // tw("a", size))
    out, line = [], ""
    for wd in s.split(" "):
        cand = (line + " " + wd).strip()
        if len(cand) > max_chars and line:
            out.append(line)
            line = wd
        else:
            line = cand
    out.append(line)
    return out


def section_heading_only(theme, label):
    c = Canvas(theme, width=math.ceil(tw(label, 14)))
    c.h = heading(c, 0, label) - 8
    return c


def section_link(theme, link):
    label = link["label"]
    c = Canvas(theme, width=math.ceil(14 + 8 + tw(label, 14)))
    t = c.t
    b = baseline_in(LH, 14)
    c.icon(0, b - 12, 14, ICONS[link["icon"]], t["primary"])
    c.text(22, b, label, 14)
    c.underline(22, b, tw(label, 14), t["primary"])
    c.h = LH + 2
    return c


def section_footer(theme, today):
    note = "auto-updated daily · last build %s" % today.strftime("%d %b %Y").lower()
    c = Canvas(theme, width=math.ceil(tw(note, 12)))
    c.text(0, baseline_in(LH, 12), note, 12, fill=c.t["secondary"])
    c.h = LH
    return c


# --------------------------------------------------------------------------- data


def fetch(url, headers=None, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers or {"User-Agent": "readme-builder"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def save_cache(name, data):
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, name), "w") as f:
        json.dump(data, f, indent=1)


def load_cache(name):
    try:
        with open(os.path.join(CACHE, name)) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def contributions(username):
    if not OFFLINE:
        token = os.environ.get("GITHUB_TOKEN")
        levels = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
        data = None
        try:
            if not token:
                raise RuntimeError("no GITHUB_TOKEN")
            q = (
                'query{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions '
                "weeks{contributionDays{date weekday contributionCount contributionLevel}}}}}}" % username
            )
            raw = fetch(
                "https://api.github.com/graphql",
                {"Authorization": "bearer " + token, "User-Agent": "readme-builder", "Content-Type": "application/json"},
                json.dumps({"query": q}).encode(),
            )
            cal = json.loads(raw)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            weeks = []
            for wk in cal["weeks"]:
                days = [None] * 7
                for d in wk["contributionDays"]:
                    days[d["weekday"]] = {"date": d["date"], "level": levels[d["contributionLevel"]],
                                          "count": d["contributionCount"]}
                weeks.append(days)
            data = {"total": cal["totalContributions"], "weeks": weeks}
            print("contributions: graphql")
        except Exception as e:
            print("graphql contributions unavailable (%s), trying public API" % e)
            try:
                raw = json.loads(fetch("https://github-contributions-api.jogruber.de/v4/%s?y=last" % username))
                days = raw["contributions"]
                first = dt.date.fromisoformat(days[0]["date"])
                padded = [None] * ((first.weekday() + 1) % 7) + [
                    {"date": d["date"], "level": d["level"], "count": d["count"]} for d in days]
                weeks = [padded[i:i + 7] + [None] * (7 - len(padded[i:i + 7])) for i in range(0, len(padded), 7)]
                total = raw.get("total", {})
                data = {"total": total.get("lastYear", next(iter(total.values()), 0)), "weeks": weeks}
                print("contributions: public API")
            except Exception as e2:
                print("public contributions API unavailable (%s), using cache" % e2)
        if data:
            save_cache("contributions.json", data)
            return data
    return load_cache("contributions.json")


def github(C):
    """Profile numbers, languages, featured and recently pushed repos from the REST API."""
    if OFFLINE:
        return load_cache("github.json")
    u = C["username"]
    headers = {"User-Agent": "readme-builder", "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "bearer " + os.environ["GITHUB_TOKEN"]
    api = lambda path: json.loads(fetch("https://api.github.com" + path, headers))
    try:
        user = api("/users/" + u)
        repos, page = [], 1
        while True:
            batch = api("/users/%s/repos?type=owner&per_page=100&page=%d" % (u, page))
            repos += batch
            if len(batch) < 100:
                break
            page += 1
        own = [r for r in repos if not r["fork"]]

        # Each repo adds sqrt(bytes) per language, so breadth counts and one giant repo
        # (vendored code, notebooks) can't swamp the bar.
        hidden = set(C.get("hide_languages", []))
        langs = {}
        for r in own:
            if r["size"] == 0 or r["name"] in C.get("skip_repos_for_languages", []):
                continue
            for name, n in api("/repos/%s/languages" % r["full_name"]).items():
                if name not in hidden:
                    langs[name] = langs.get(name, 0) + math.sqrt(n)

        wanted = C.get("featured") or []
        by_name = {r["name"]: r for r in own}
        if wanted:
            picks = [by_name[n] for n in wanted if n in by_name]
        else:
            picks = sorted((r for r in own if r["name"] != u),
                           key=lambda r: (r["stargazers_count"], r["pushed_at"]), reverse=True)[:5]
        featured = [{
            "name": r["name"], "description": r["description"], "language": r["language"],
            "stars": r["stargazers_count"], "url": r["html_url"],
        } for r in picks]

        prs = api("/search/issues?q=author:%s+type:pr&per_page=1" % u)["total_count"]
        recent = [{"verb": "pushed to", "target": r["name"], "date": r["pushed_at"], "url": r["html_url"]}
                  for r in sorted((r for r in own if r["name"] != u), key=lambda r: r["pushed_at"], reverse=True)[:5]]

        data = {
            "user": {k: user[k] for k in ("public_repos", "followers", "created_at")},
            "stars": sum(r["stargazers_count"] for r in own),
            "prs": prs,
            "languages": sorted(langs.items(), key=lambda kv: -kv[1]),
            "featured": featured,
            "recent": recent,
        }
        save_cache("github.json", data)
        print("github: live")
        return data
    except Exception as e:
        print("github API unavailable (%s), using cache" % e)
        return load_cache("github.json")


# --------------------------------------------------------------------------- readme


def pic(name, alt, width, href=None):
    img = (
        '<picture><source media="(prefers-color-scheme: dark)" srcset="./assets/dark/{n}.svg">'
        '<img alt="{a}" src="./assets/light/{n}.svg" width="{w}"></picture>'
    ).format(n=name, a=esc(alt), w=width)
    return '<a href="%s">%s</a>' % (esc(href), img) if href else img


def build():
    with open(os.path.join(HERE, "content.json")) as f:
        C = json.load(f)
    contrib = contributions(C["username"])
    gh = github(C)
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    site = C["site"]
    profile = "https://github.com/" + C["username"]

    sections = []  # (name, builder(theme) -> Canvas, alt, href)
    add = lambda name, fn, alt, href=None: sections.append((name, fn, alt, href))

    add("hero", lambda th: section_hero(th, C, gh), "%s — %s%s" % (C["name"], *C["tagline"]), site)
    add("intro", lambda th: section_intro(th, C),
        " ".join("".join(p[1] for p in para) for para in C["intro"]))
    if gh:
        add("stats", lambda th: section_stats(th, gh, contrib),
            "%d public repos, %d stars, %d pull requests, %d followers"
            % (gh["user"]["public_repos"], gh["stars"], gh["prs"], gh["user"]["followers"]),
            profile + "?tab=repositories")
        if gh["languages"]:
            add("languages", lambda th: section_languages(th, gh),
                "languages: " + ", ".join(n for n, _ in gh["languages"][:6]))
    if contrib:
        add("ship-log", lambda th: section_shiplog(th, C, contrib),
            "ship log: %d contributions in the last year" % contrib["total"], profile)
    if gh:
        n = len(gh["featured"])
        for i, r in enumerate(gh["featured"]):
            add("repo-%d" % i, lambda th, r=r, f=(i == 0), l=(i == n - 1): section_repo_row(th, r, f, l),
                "%s — %s" % (r["name"], r["description"] or ""), r["url"])
        if gh["recent"]:
            add("activity", lambda th: section_activity(th, gh["recent"], today),
                "recently active: " + ", ".join(e["target"] for e in gh["recent"]),
                profile + "?tab=repositories&sort=updated")
    add("portfolio", lambda th: shipped_card(th, "shipped_products.webp", C["portfolio_card"][0],
        C["portfolio_card"][1]), C["portfolio_card"][1], site)
    add("links", lambda th: section_heading_only(th, "links"), "links")
    for l in C["links"]:
        add("link-" + l["icon"], lambda th, l=l: section_link(th, l), l["label"], l["url"])
    add("footer", lambda th: section_footer(th, today), "auto-updated daily")

    widths = {}
    for theme in THEMES:
        d = os.path.join(OUT, theme)
        os.makedirs(d, exist_ok=True)
        for old in os.listdir(d):
            os.remove(os.path.join(d, old))
        for name, fn, alt, _ in sections:
            c = fn(theme)
            widths[name] = c.w
            with open(os.path.join(d, name + ".svg"), "w") as f:
                f.write(c.svg(alt))

    by = {s[0]: s for s in sections}

    def P(name):
        _, _, alt, href = by[name]
        return pic(name, alt, widths[name], href)

    def block(names):
        names = [n for n in names if n in by]
        return '<p align="center">\n' + "<br>\n".join(P(n) for n in names) + "\n</p>" if names else ""

    group = lambda prefix: [s[0] for s in sections if s[0].startswith(prefix)]
    parts = [
        "<!-- Generated by .readme/build.py. Edit .readme/content.json, not this file. -->",
        block(["hero"]),
        block(["intro"]),
        block(["stats"]),
        block(["languages"]),
        block(["ship-log"]),
        block(group("repo-")),
        block(["activity"]),
        block(["portfolio"]),
        block(["links"]),
        '<p align="center">\n' + "&nbsp;&nbsp;\n".join(P(n) for n in group("link-")) + "\n</p>",
        block(["footer"]),
    ]
    with open(os.path.join(ROOT, "README.md"), "w") as f:
        f.write("\n\n".join(p for p in parts if p) + "\n")
    print("built %d sections × %d themes" % (len(sections), len(THEMES)))


if __name__ == "__main__":
    build()
