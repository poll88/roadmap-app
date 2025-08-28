# lib/timeline.py — dynamic axis, Montserrat, robust loader, ungrouped fallback,
# PNG export without frame + optional transparent background

import json
from datetime import date, datetime, timedelta
import streamlit.components.v1 as components

_VIS_CSS_URLS = [
    "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.css",
    "https://cdn.jsdelivr.net/npm/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.7.3/vis-timeline-graph2d.min.css",
]
_VIS_JS_URLS = [
    "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.js",
    "https://cdn.jsdelivr.net/npm/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.7.3/vis-timeline-graph2d.min.js",
]
_DOM_TO_IMG_URLS = [
    "https://cdn.jsdelivr.net/npm/dom-to-image-more@3.3.0/dist/dom-to-image-more.min.js",
    "https://unpkg.com/dom-to-image-more@3.3.0/dist/dom-to-image-more.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/dom-to-image-more/3.3.0/dom-to-image-more.min.js",
]

def _dt(d):
    if isinstance(d, (date, datetime)):
        return d.isoformat()
    return d

def render_timeline(items: list, groups: list, selected_id: str = "", export=None):
    items_json = json.dumps([
        {
            "id": i.get("id"),
            "content": i.get("content"),
            "start": _dt(i.get("start")),
            "end": _dt(i.get("end")),
            "group": i.get("group"),
            "style": i.get("style"),
            "subtitle": i.get("subtitle", ""),
        } for i in items
    ])
    groups_json = json.dumps([
        {"id": g.get("id"), "content": g.get("content")}
        for g in groups
    ])
    export_json = json.dumps(export or {})
    css_urls = json.dumps(_VIS_CSS_URLS)
    js_urls  = json.dumps(_VIS_JS_URLS)
    dti_urls = json.dumps(_DOM_TO_IMG_URLS)

    rows = max(1, len(groups))
    height_px = max(260, 80 * rows + 120)

    html_template = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
      :root {
        --font: 'Montserrat', ui-sans-serif, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, "Noto Sans", "Helvetica Neue", sans-serif;
      }
      html, body { background: transparent; margin:0; padding:0; }
      body, #timeline, .vis-timeline, .vis-item, .vis-item-content, .vis-label, .vis-time-axis { font-family: var(--font); }
      #wrap { position: relative; }
      #timeline {
        height:__HEIGHT__px;
        background: transparent;
        border-radius:12px; border:1px solid #e7e9f2; /* on-screen frame only (we strip it for export) */
      }
      .ttl { font-weight:700 }
      .sub { font-size:12px; opacity:.9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px }
    </style>
  </head>
  <body>
    <div id="wrap"><div id="timeline"></div></div>

    <script>
      const __CSS_URLS__ = __CSS_URLS_JSON__;
      const __JS_URLS__  = __JS_URLS_JSON__;
      const __DTI_URLS__ = __DTI_URLS_JSON__;

      window.__TL_DATA__ = {
        ITEMS: __ITEMS__,
        GROUPS: __GROUPS__,
        EXPORT: __EXPORT__
      };

      (function() {
        const D = window.__TL_DATA__;

        function loadCSSOnce(urls) {
          return Promise.all(urls.map(url => new Promise((resolve) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet'; link.href = url;
            link.onload = () => resolve();
            link.onerror = () => resolve();
            document.head.appendChild(link);
          })));
        }

        function loadJSOnce(urls) {
          if (window._visReady) return Promise.resolve();
          return new Promise((resolve, reject) => {
            let i = 0;
            const tryNext = () => {
              if (i >= urls.length) return reject(new Error('Failed to load vis-timeline'));
              const s = document.createElement('script');
              s.src = urls[i++]; s.async = true;
              s.onload = () => { window._visReady = true; resolve(); };
              s.onerror = () => tryNext();
              document.head.appendChild(s);
            };
            tryNext();
          });
        }

        function layout() {
          const el = document.getElementById('timeline');
          if (!el || !window.vis) return;

          const itemsIn = Array.isArray(D.ITEMS) ? D.ITEMS : [];
          const groupsIn = Array.isArray(D.GROUPS) ? D.GROUPS : [];

          // Fallback group so items with empty group still show.
          const NEED_UNGROUPED = itemsIn.some(it => !it.group) || groupsIn.length === 0;
          const groupsAll = NEED_UNGROUPED
            ? [{ id: "_ungrouped", content: "Ungrouped" }].concat(groupsIn)
            : groupsIn.slice();

          const items = new vis.DataSet(itemsIn.map(it => {
            const obj = {
              id: it.id,
              content
