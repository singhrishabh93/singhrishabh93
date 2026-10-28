#!/usr/bin/env python3
"""Builds the profile README as SVG sections styled like rishabhsingh.tech.

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
import xml.etree.ElementTree as ET

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

# Mostly-black logos that vanish on a dark background.
DARK_LIFT = {"f1.webp", "stack/nextjs-original.svg", "stack/amazonwebservices-original-wordmark.svg"}

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

AWS_TEXT = "M86.4,66.4c0,3.7,0.4,6.7,1.1,8.9c0.8,2.2,1.8,4.6,3.2,7.2c0.5,0.8,0.7,1.6,0.7,2.3c0,1-0.6,2-1.9,3l-6.3,4.2 c-0.9,0.6-1.8,0.9-2.6,0.9c-1,0-2-0.5-3-1.4C76.2,90,75,88.4,74,86.8c-1-1.7-2-3.6-3.1-5.9c-7.8,9.2-17.6,13.8-29.4,13.8 c-8.4,0-15.1-2.4-20-7.2c-4.9-4.8-7.4-11.2-7.4-19.2c0-8.5,3-15.4,9.1-20.6c6.1-5.2,14.2-7.8,24.5-7.8c3.4,0,6.9,0.3,10.6,0.8 c3.7,0.5,7.5,1.3,11.5,2.2v-7.3c0-7.6-1.6-12.9-4.7-16c-3.2-3.1-8.6-4.6-16.3-4.6c-3.5,0-7.1,0.4-10.8,1.3c-3.7,0.9-7.3,2-10.8,3.4 c-1.6,0.7-2.8,1.1-3.5,1.3c-0.7,0.2-1.2,0.3-1.6,0.3c-1.4,0-2.1-1-2.1-3.1v-4.9c0-1.6,0.2-2.8,0.7-3.5c0.5-0.7,1.4-1.4,2.8-2.1 c3.5-1.8,7.7-3.3,12.6-4.5c4.9-1.3,10.1-1.9,15.6-1.9c11.9,0,20.6,2.7,26.2,8.1c5.5,5.4,8.3,13.6,8.3,24.6V66.4z M45.8,81.6 c3.3,0,6.7-0.6,10.3-1.8c3.6-1.2,6.8-3.4,9.5-6.4c1.6-1.9,2.8-4,3.4-6.4c0.6-2.4,1-5.3,1-8.7v-4.2c-2.9-0.7-6-1.3-9.2-1.7 c-3.2-0.4-6.3-0.6-9.4-0.6c-6.7,0-11.6,1.3-14.9,4c-3.3,2.7-4.9,6.5-4.9,11.5c0,4.7,1.2,8.2,3.7,10.6 C37.7,80.4,41.2,81.6,45.8,81.6z M126.1,92.4c-1.8,0-3-0.3-3.8-1c-0.8-0.6-1.5-2-2.1-3.9L96.7,10.2c-0.6-2-0.9-3.3-0.9-4 c0-1.6,0.8-2.5,2.4-2.5h9.8c1.9,0,3.2,0.3,3.9,1c0.8,0.6,1.4,2,2,3.9l16.8,66.2l15.6-66.2c0.5-2,1.1-3.3,1.9-3.9c0.8-0.6,2.2-1,4-1 h8c1.9,0,3.2,0.3,4,1c0.8,0.6,1.5,2,1.9,3.9l15.8,67l17.3-67c0.6-2,1.3-3.3,2-3.9c0.8-0.6,2.1-1,3.9-1h9.3c1.6,0,2.5,0.8,2.5,2.5 c0,0.5-0.1,1-0.2,1.6c-0.1,0.6-0.3,1.4-0.7,2.5l-24.1,77.3c-0.6,2-1.3,3.3-2.1,3.9c-0.8,0.6-2.1,1-3.8,1h-8.6c-1.9,0-3.2-0.3-4-1 c-0.8-0.7-1.5-2-1.9-4L156,23l-15.4,64.4c-0.5,2-1.1,3.3-1.9,4c-0.8,0.7-2.2,1-4,1H126.1z M254.6,95.1c-5.2,0-10.4-0.6-15.4-1.8 c-5-1.2-8.9-2.5-11.5-4c-1.6-0.9-2.7-1.9-3.1-2.8c-0.4-0.9-0.6-1.9-0.6-2.8v-5.1c0-2.1,0.8-3.1,2.3-3.1c0.6,0,1.2,0.1,1.8,0.3 c0.6,0.2,1.5,0.6,2.5,1c3.4,1.5,7.1,2.7,11,3.5c4,0.8,7.9,1.2,11.9,1.2c6.3,0,11.2-1.1,14.6-3.3c3.4-2.2,5.2-5.4,5.2-9.5 c0-2.8-0.9-5.1-2.7-7c-1.8-1.9-5.2-3.6-10.1-5.2L246,52c-7.3-2.3-12.7-5.7-16-10.2c-3.3-4.4-5-9.3-5-14.5c0-4.2,0.9-7.9,2.7-11.1 c1.8-3.2,4.2-6,7.2-8.2c3-2.3,6.4-4,10.4-5.2c4-1.2,8.2-1.7,12.6-1.7c2.2,0,4.5,0.1,6.7,0.4c2.3,0.3,4.4,0.7,6.5,1.1 c2,0.5,3.9,1,5.7,1.6c1.8,0.6,3.2,1.2,4.2,1.8c1.4,0.8,2.4,1.6,3,2.5c0.6,0.8,0.9,1.9,0.9,3.3v4.7c0,2.1-0.8,3.2-2.3,3.2 c-0.8,0-2.1-0.4-3.8-1.2c-5.7-2.6-12.1-3.9-19.2-3.9c-5.7,0-10.2,0.9-13.3,2.8c-3.1,1.9-4.7,4.8-4.7,8.9c0,2.8,1,5.2,3,7.1 c2,1.9,5.7,3.8,11,5.5l14.2,4.5c7.2,2.3,12.4,5.5,15.5,9.6c3.1,4.1,4.6,8.8,4.6,14c0,4.3-0.9,8.2-2.6,11.6 c-1.8,3.4-4.2,6.4-7.3,8.8c-3.1,2.5-6.8,4.3-11.1,5.6C264.4,94.4,259.7,95.1,254.6,95.1z"
AWS_SMILE = "M273.5,143.7c-32.9,24.3-80.7,37.2-121.8,37.2c-57.6,0-109.5-21.3-148.7-56.7c-3.1-2.8-0.3-6.6,3.4-4.4 c42.4,24.6,94.7,39.5,148.8,39.5c36.5,0,76.6-7.6,113.5-23.2C274.2,133.6,278.9,139.7,273.5,143.7z"
AWS_ARROW = "M287.2,128.1c-4.2-5.4-27.8-2.6-38.5-1.3c-3.2,0.4-3.7-2.4-0.8-4.5c18.8-13.2,49.7-9.4,53.3-5 c3.6,4.5-1,35.4-18.6,50.2c-2.7,2.3-5.3,1.1-4.1-1.9C282.5,155.7,291.4,133.4,287.2,128.1z"


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
        if self.theme == "dark" and name in DARK_LIFT:
            # invert(1) hue-rotate(180deg) as one matrix: same hues, flipped lightness.
            # An SVG filter rather than CSS so Safari applies it too.
            if not any('id="lift"' in d for d in self.defs):
                self.defs.append(
                    '<filter id="lift" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" '
                    'values="0.574 -1.43 -0.144 0 1 -0.426 -0.43 -0.144 0 1 -0.426 -1.43 0.856 0 1 0 0 0 1 0"/></filter>'
                )
            extra += ' filter="url(#lift)"'
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


def section_hero(theme, C):
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

    # Right: location, timezone, resume.
    rx = W
    y = top + 3
    c.text(rx, y + 12, C["location"], 12, fill=t["secondary"], anchor="end")
    y += 16 + 6
    c.text(rx, y + 12, C["timezone"], 12, fill=t["secondary"], anchor="end")
    y += 16 + 6
    rw = tw("resume", 12)
    c.text(rx, y + 12, "resume", 12, anchor="end")
    c.underline(rx - rw, y + 12, rw, t["primary"], offset=3)
    # Sun glyph from the theme toggle.
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


# Inline rich-text layout for the "today" paragraphs. Pieces: (kind, ...) tuples.
def _piece_width(p):
    kind = p[0]
    if kind in ("t", "hi", "em"):
        return tw(p[1], 14)
    if kind == "badge":
        return 2 + 4 + 16 + 4 + tw(p[1], 14) + 4 + 2 + 2  # margin, padding, logo, gap, text, padding, border
    if kind == "img":
        return 4 + p[2] + 4
    if kind == "aws":
        return 2 + 14 * 304 / 182 + 2
    raise ValueError(kind)


def _draw_piece(c, p, x, b):
    t = c.t
    kind = p[0]
    if kind == "t":
        c.text(x, b, p[1], 14, fill=t["body"])
    elif kind == "hi":
        c.text(x, b, p[1], 14, 500, fill=t["body"])
        c.wavy(x, b, tw(p[1], 14), t["deco"])
    elif kind == "em":
        c.text(x, b, p[1], 14, italic=True, fill=t["primary"])
        c.underline(x, b, tw(p[1], 14), t["primary"], offset=3, dash="2 2")
    elif kind == "badge":
        bw = _piece_width(p) - 4
        top = b - 18
        c.rect(x + 2.5, top + 0.5, bw - 1, 25, 4, fill=t["badge_bg"], stroke=t["badge_border"])
        c.image(x + 2 + 5, top + 5, 16, 16, p[2])
        c.text(x + 2 + 5 + 16 + 4, b, p[1], 14, fill=t["badge_fg"])
    elif kind == "img":
        _, name, w, h, valign = p
        c.image(x + 4, b - h - valign, w, h, name)
    elif kind == "aws":
        h = 14
        w = h * 304 / 182
        s = h / 182
        g = '<g transform="translate(%.2f %.2f) scale(%.5f)">' % (x + 2, b - h + 2, s)
        c.raw(
            g + '<path d="%s" fill="%s"/><path d="%s" fill="#FF9900" fill-rule="evenodd"/>'
            '<path d="%s" fill="#FF9900" fill-rule="evenodd"/></g>' % (AWS_TEXT, t["primary"], AWS_SMILE, AWS_ARROW)
        )


def _atoms(paragraph):
    """Split a paragraph into breakable atoms; ("nowrap", [...]) stays on one line."""
    atoms = []
    for p in paragraph:
        if p[0] == "nowrap":
            atoms.append(("group", p[1]))
        elif p[0] == "t":
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


TODAY = [
    [("t", "i'm a software engineer at "), ("badge", "9x Technology", "9x.webp"),
     ("t", ", building scalable mobile and web applications using flutter and modern cloud technologies.")],
    [("t", "enjoys "), ("hi", "travelling"), ("t", ", building products, fast cars "),
     ("img", "car.webp", 72, 32, -10), ("t", " and "), ("img", "f1.webp", 45, 20, -6), ("t", " racing.")],
    [("t", "i was on the organising team for "), ("hi", "events"), ("t", ", and i'm an "),
     ("nowrap", [("hi", "aws community builder"), ("t", " "), ("aws",), ("t", ",")]),
     ("t", " 3 years and counting.")],
    [("t", "i design systems, build scalable "), ("hi", "applications"),
     ("t", " and ship reliable software used by real users.")],
    [("t", "got an idea or a project in mind? let's "), ("em", "collaborate"), ("t", ".")],
]


def section_today(theme, C):
    c = Canvas(theme)
    y = heading(c, 0, "today")
    for i, para in enumerate(TODAY):
        y = layout_paragraph(c, para, y)
        if i < len(TODAY) - 1:
            y += 10
    c.h = y + 6
    return c


def row_canvas(theme, title, first):
    """Rows of a list are separate images (so each can link); the first carries the heading."""
    c = Canvas(theme)
    y = heading(c, 0, title) if first else 0
    return c, y


def section_past_row(theme, item, first):
    c, y = row_canvas(theme, "past", first)
    t = c.t
    b = y + baseline_in(LH, 14)
    clip = c.uid("r")
    c.defs.append('<clipPath id="%s"><rect x="0" y="%.2f" width="16" height="16" rx="4"/></clipPath>' % (clip, y + 3.4))
    c.image(0, y + 3.4, 16, 16, item["logo"], ' clip-path="url(#%s)"' % clip)
    x = 22
    c.text(x, b, item["name"], 14, fill=t["body"])
    c.underline(x, b, tw(item["name"], 14), t["body"])
    x += tw(item["name"], 14)
    c.text(x, b, ", " + item["role"], 14, fill=t["body"])
    c.h = y + LH
    return c


def section_stack(theme, C):
    c = Canvas(theme)
    t = c.t
    y = heading(c, 0, "stack")
    ph, gap = 26, 8
    x = 0
    for icon, label in C["stack"]:
        pw = 1 + 8 + 14 + 6 + tw(label, 12) + 8 + 1
        if x + pw > W:
            x, y = 0, y + ph + gap
        c.rect(x + 0.5, y + 0.5, pw - 1, ph - 1, 6, fill=t["pill_bg"], stroke=t["pill_border"])
        c.image(x + 9, y + 6, 14, 14, "stack/" + icon, ' preserveAspectRatio="xMidYMid meet"')
        c.text(x + 9 + 14 + 6, y + 17.3, label, 12)
        x += pw + gap
    c.h = y + ph + 4
    return c


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


def section_project_row(theme, p, first, last):
    c, y = row_canvas(theme, "personal projects", first)
    t = c.t
    row_h = 4 + LH + 4
    b = y + 4 + baseline_in(LH, 14)
    c.text(0, b, p["name"], 14, 500)
    arrow_w = tw("↗", 12)
    c.text(W, b - 1, "↗", 12, fill=t["secondary"], anchor="end")
    tags = ", ".join(p["tags"])
    tgw = tw(tags, 10) + 8 + 2
    tx = W - arrow_w - 8 - tgw
    c.rect(tx + 0.5, y + (row_h - 20.25) / 2 + 0.5, tgw - 1, 20.25 - 1, 6, stroke=t["border_pill"])
    c.text(tx + 5, y + (row_h - 20.25) / 2 + 1 + baseline_in(18.25, 10), tags, 10, fill=t["secondary"])
    if not last:
        c.line(0, y + row_h - 0.5, W, y + row_h - 0.5, t["border_soft"])
    c.h = y + row_h
    return c


def shipped_card(theme, doodle, title, desc, badge=True):
    c = Canvas(theme)
    t = c.t
    c.image(0, 0, 50, 50, doodle, ' preserveAspectRatio="xMidYMid meet"')
    x = 62
    b = baseline_in(LH, 14)
    label = title + " ↗"
    c.text(x, b, label, 14, 700)
    if badge:
        bx = x + tw(label, 14) + 8
        bw = tw("NEW", 9) + 12
        c.rect(bx, b - 10.5, bw, 13, 6.5, fill=t["primary"])
        c.text(bx + bw / 2, b - 1, "NEW", 9, 600, fill=t["bg"], anchor="middle")
    y = LH + 4
    # Wrap the description at the card's text width.
    words, line, lines = desc.split(" "), "", []
    max_chars = int((W - x) // tw("a", 12))
    for wd in words:
        cand = (line + " " + wd).strip()
        if len(cand) > max_chars:
            lines.append(line)
            line = wd
        else:
            line = cand
    lines.append(line)
    for i, ln in enumerate(lines):
        c.text(x, y + i * 16 + 12, ln, 12, fill=t["secondary"])
    c.h = max(54, y + len(lines) * 16 + 6)
    return c


def section_reading_row(theme, r, first):
    c, y = row_canvas(theme, "currently learning", first)
    t = c.t
    h = 46
    c.rect(0.5, y + 0.5, W - 1, h - 1, 8, fill=t["card"], stroke=t["border_soft"])
    mid = y + h / 2
    kw = tw(r["kind"], 10) + 8 + 2
    c.rect(16.5, mid - 8.6, kw - 1, 17.25, 6, stroke=t["border_pill"])
    c.text(16 + 5, mid + 3.5, r["kind"], 10, fill=t["secondary"])
    c.text(16 + kw + 8, mid + 5, r["title"], 14, 500)
    c.text(W - 16, mid + 4, r["by"], 12, fill=t["secondary"], anchor="end")
    c.h = y + h
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


def section_blog_row(theme, post, first, today):
    c = Canvas(theme)
    t = c.t
    y = heading(c, 0, "recent blogs", arrow=True) if first else 0
    pad_x, pad_y = 16, 12
    days = max(0, (today - dt.datetime.fromisoformat(post["date"].replace("Z", "+00:00")).date()).days)
    when = "today" if days == 0 else "%dd ago" % days
    title_w = W - 2 - pad_x * 2 - 16 - tw(when, 12)
    title = wrap(post["title"].lower(), 14, title_w)
    desc = wrap(post["description"].lower(), 12, W - 2 - pad_x * 2)
    h = 1 + pad_y + len(title) * 20 + 4 + len(desc) * 16 + pad_y + 1
    c.rect(0.5, y + 0.5, W - 1, h - 1, 8, fill=t["card"], stroke=t["border_soft"])
    ty = y + 1 + pad_y
    for i, ln in enumerate(title):
        c.text(1 + pad_x, ty + i * 20 + baseline_in(20, 14), ln, 14, 600)
    c.text(W - 1 - pad_x, ty + baseline_in(20, 12), when, 12, fill=t["secondary"], anchor="end")
    dy = ty + len(title) * 20 + 4
    for i, ln in enumerate(desc):
        c.text(1 + pad_x, dy + i * 16 + baseline_in(16, 12), ln, 12, fill=t["blog_desc"])
    c.h = y + h
    return c


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


def section_footer(theme, year):
    note = "© %d Rishabh Singh · all rights reserved." % year
    c = Canvas(theme, width=math.ceil(tw(note, 14)))
    c.text(0, baseline_in(LH, 14), note, 14, fill=c.t["secondary"])
    c.h = LH
    return c


# --------------------------------------------------------------------------- data


def fetch(url, headers=None, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers or {"User-Agent": "readme-builder"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def contributions(username):
    path = os.path.join(CACHE, "contributions.json")
    if not OFFLINE:
        token = os.environ.get("GITHUB_TOKEN")
        levels = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
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
                    days[d["weekday"]] = {"date": d["date"], "level": levels[d["contributionLevel"]]}
                weeks.append(days)
            data = {"total": cal["totalContributions"], "weeks": weeks}
        except Exception as e:
            print("graphql contributions unavailable (%s), trying public API" % e)
            try:
                raw = json.loads(fetch("https://github-contributions-api.jogruber.de/v4/%s?y=last" % username))
                days = raw["contributions"]
                first = dt.date.fromisoformat(days[0]["date"])
                padded = [None] * ((first.weekday() + 1) % 7) + [{"date": d["date"], "level": d["level"]} for d in days]
                weeks = [padded[i:i + 7] + [None] * (7 - len(padded[i:i + 7])) for i in range(0, len(padded), 7)]
                total = raw.get("total", {})
                data = {"total": total.get("lastYear", next(iter(total.values()), 0)), "weeks": weeks}
            except Exception as e2:
                print("public contributions API unavailable (%s), using cache" % e2)
                data = None
        if data:
            os.makedirs(CACHE, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f)
            return data
    with open(path) as f:
        return json.load(f)


def blogs(C):
    if not OFFLINE:
        try:
            root = ET.fromstring(fetch(C["site"] + "/rss.xml"))
            posts = []
            for item in root.iter("item"):
                pub = dt.datetime.strptime(item.findtext("pubDate"), "%a, %d %b %Y %H:%M:%S %Z")
                posts.append({
                    "title": item.findtext("title"),
                    "description": item.findtext("description"),
                    "date": pub.replace(tzinfo=dt.timezone.utc).isoformat(),
                    "url": item.findtext("link"),
                })
            posts.sort(key=lambda p: p["date"], reverse=True)
            if posts:
                return posts[:2]
        except Exception as e:
            print("rss unavailable (%s), using fallback posts" % e)
    return C["blogs_fallback"][:2]


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
    posts = blogs(C)
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    today = now.date()
    site = C["site"]

    sections = []  # (name, builder(theme) -> Canvas, alt, href)
    add = lambda name, fn, alt, href=None: sections.append((name, fn, alt, href))

    add("hero", lambda th: section_hero(th, C), "rishabh singh — ships really fast.", site)
    add("today", lambda th: section_today(th, C), "today: software engineer at 9x Technology, building scalable mobile and web apps with flutter.", site)
    for i, item in enumerate(C["past"]):
        add("past-%d" % i, lambda th, it=item, f=(i == 0): section_past_row(th, it, f),
            "%s, %s" % (item["name"], item["role"]), item["url"])
    add("stack", lambda th: section_stack(th, C), "stack: " + ", ".join(l for _, l in C["stack"]))
    add("ship-log", lambda th: section_shiplog(th, C, contrib),
        "ship log: %d contributions in the last year" % contrib["total"], "https://github.com/" + C["username"])
    n = len(C["projects"])
    for i, p in enumerate(C["projects"]):
        add("project-%d" % i, lambda th, p=p, f=(i == 0), l=(i == n - 1): section_project_row(th, p, f, l),
            "%s — %s" % (p["name"], ", ".join(p["tags"])), p["url"])
    add("mini-apps", lambda th: shipped_card(th, "mini-apps.svg", "mini apps",
        "small tools for flutter and app development, sharing them in case they're useful to you too."),
        "mini apps", site + "/mini-apps")
    for i, r in enumerate(C["reading"]):
        add("reading-%d" % i, lambda th, r=r, f=(i == 0): section_reading_row(th, r, f),
            "%s: %s by %s" % (r["kind"], r["title"], r["by"]), r["url"])
    for i, p in enumerate(posts):
        add("blog-%d" % i, lambda th, p=p, f=(i == 0): section_blog_row(th, p, f, today), p["title"], p["url"])
    add("shipped-products", lambda th: shipped_card(th, "shipped_products.webp", "shipped products",
        "live products i've designed and built end to end."), "shipped products", site + "/products")
    add("links", lambda th: section_heading_only(th, "links"), "links")
    for l in C["links"]:
        add("link-" + l["icon"], lambda th, l=l: section_link(th, l), l["label"], l["url"])
    add("footer", lambda th: section_footer(th, today.year), "© %d Rishabh Singh" % today.year)

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
        return '<p align="center">\n' + "<br>\n".join(P(n) for n in names) + "\n</p>"

    group = lambda prefix: [s[0] for s in sections if s[0].startswith(prefix)]
    parts = [
        "<!-- Generated by .readme/build.py. Edit .readme/content.json (and TODAY in build.py for the intro), not this file. -->",
        block(["hero"]),
        block(["today"]),
        block(group("past-")),
        block(["stack"]),
        block(["ship-log"]),
        block(group("project-")),
        block(["mini-apps"]),
        block(group("reading-")),
        block(group("blog-")),
        block(["shipped-products"]),
        block(["links"]),
        '<p align="center">\n' + "&nbsp;&nbsp;\n".join(P(n) for n in group("link-")) + "\n</p>",
        block(["footer"]),
    ]
    with open(os.path.join(ROOT, "README.md"), "w") as f:
        f.write("\n\n".join(parts) + "\n")
    print("built %d sections × %d themes" % (len(sections), len(THEMES)))


if __name__ == "__main__":
    build()
