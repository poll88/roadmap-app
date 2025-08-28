# lib/timeline.py — robust vis loader, Montserrat, ungrouped fallback, tl.fit(),
# on-page debug panel, and one-to-one PNG export (no preview window).

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
            "group": i.get("group"),  # may be "", None, or a real id
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

    today = date.today()
    def next_weekday(dt, weekday):
        return dt + timedelta(days=(weekday - dt.weekday()) % 7)
    ws = next_weekday(today, 5).isoformat()
    we = next_weekday(today, 0).isoformat()

    html_template = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <!-- Montserrat -->
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
      :root {
        --font: 'Montserrat', ui-sans-serif, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, "Noto Sans", "Helvetica Neue", sans-serif;
      }
      html, body { background: transparent; margin:0; padding:0; }
      body, #timeline, .vis-timeline, .vis-item, .vis-item-content, .vis-label, .vis-time-axis { font-family: var(--font); }
      #wrap { position: relative; }
      #timeline {
        height:__HEIGHT__px; background: transparent;
        border-radius:12px; border:1px solid #e7e9f2;
      }
      .vis-time-axis .text { font-size:12px; font-weight:600 }
      .vis-labelset .vis-label .vis-inner { font-weight:700 }
      .vis-item .vis-item-content { line-height:1.15 }
      .ttl { font-weight:700 }
      .sub { font-size:12px; opacity:.9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px }

      /* Debug panel */
      #dbg {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        font-size: 12px; line-height: 1.35;
        background: #0b102016; color: #0b1020;
        border: 1px dashed #c7ccda; border-radius: 8px;
        padding: 10px; margin-top: 10px; white-space: pre-wrap;
      }
      #dbg b { color:#111; }
    </style>
  </head>
  <body>
    <div id="wrap">
      <div id="timeline"></div>
      <details open style="margin-top:8px">
        <summary>Debug</summary>
        <div id="dbg">Booting…</div>
      </details>
    </div>

    <script>
      const __CSS_URLS__ = __CSS_URLS_JSON__;
      const __JS_URLS__  = __JS_URLS_JSON__;
      const __DTI_URLS__ = __DTI_URLS_JSON__;

      const __TL_DATA__ = {
        ITEMS: __ITEMS__,
        GROUPS: __GROUPS__,
        EXPORT: __EXPORT__,
        WS: "__WS__",
        WE: "__WE__",
      };

      (function() {
        const D = window.__TL_DATA__;
        const dbg = (msg) => {
          const el = document.getElementById('dbg');
          if (el) el.textContent = String(msg);
          console.log('[timeline]', msg);
        };

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

          const itemsIn = Array.isArray(D.ITEMS) ? D.ITEMS : [];
          const groupsIn = Array.isArray(D.GROUPS) ? D.GROUPS : [];

          // ---- Debug data echo
          dbg([
            'vis loaded? ' + !!window.vis,
            'items: ' + itemsIn.length,
            itemsIn.length ? 'first item: ' + JSON.stringify(itemsIn[0], null, 2) : 'first item: (none)',
            'groups: ' + groupsIn.length,
            groupsIn.length ? ('group ids: ' + groupsIn.map(g=>g.id).join(', ')) : '(no groups)',
          ].join('\\n'));

          if (!el) return;
          if (!window.vis) {
            el.innerHTML = '<div style="padding:16px;color:#999">Failed to load timeline library.</div>';
            return;
          }

          // Guarantee a valid group for every item: if item has no group, route to "_ungrouped"
          const NEED_UNGROUPED = itemsIn.some(it => !it.group) || groupsIn.length === 0;
          const groupsAll = NEED_UNGROUPED
            ? [{ id: "_ungrouped", content: "Ungrouped" }].concat(groupsIn)
            : groupsIn.slice();

          const items = new vis.DataSet(itemsIn.map(it => {
            const obj = {
              id: it.id,
              content: '<div class="ttl">' + (it.content || '') + '</div><div class="sub">' + (it.subtitle || '') + '</div>',
              start: it.start, end: it.end, style: it.style
            };
            obj.group = (it.group && String(it.group).trim()) ? it.group : "_ungrouped";
            return obj;
          }));

          const groups = new vis.DataSet(groupsAll.map(g => ({ id: g.id, content: g.content })));

          const options = {
            stack: false,
            orientation: 'top',
            horizontalScroll: true,
            zoomKey: 'ctrlKey',
            zoomMax: 1000 * 60 * 60 * 24 * 366 * 10,
            zoomMin: 1000 * 60 * 60 * 12,
            timeAxis: { scale: 'day', step: 1 },
            format: { minorLabels: { day: 'D MMM', month: 'MMM YY' } },
            weekends: true,
            showMajorLabels: true,
            showMinorLabels: true,
            margin: { item: 8, axis: 12 },
          };

          let tl;
          try {
            tl = new vis.Timeline(el, items, groups, options);
            window._tl = tl;
          } catch (e) {
            dbg('Timeline ctor error: ' + (e && e.message ? e.message : e));
            el.innerHTML = '<div style="padding:16px;color:#c00">Timeline init error. See console.</div>';
            return;
          }

          try {
            if (items.length) tl.fit();
          } catch (e) {
            dbg('fit() error: ' + (e && e.message ? e.message : e));
          }
        }

        function init() {
          loadCSSOnce(__CSS_URLS__)
            .then(() => loadJSOnce(__JS_URLS__))
            .then(() => {
              layout();
              const EX = (D.EXPORT || null);
              if (EX && EX.kind === 'png') setTimeout(() => exportPNG(EX), 80);
            })
            .catch((e) => {
              const el = document.getElementById('timeline');
              if (el) el.innerHTML = '<div style="padding:16px;color:#999">Timeline failed to load.</div>';
              const msg = (e && e.message) ? e.message : String(e);
              const d = document.getElementById('dbg'); if (d) d.textContent = 'Loader error: ' + msg;
              console.error(e);
            });
        }

        init();

        async function exportPNG(EXPORT) {
          const tl = document.getElementById('timeline');
          if (!tl) return;

          async function loadScriptOnce(urls) {
            if (window._dtiReady) return;
            for (const u of urls) {
              try {
                await new Promise((res, rej) => {
                  const s = document.createElement('script'); s.src = u; s.async = true;
                  s.onload = () => res(); s.onerror = rej; document.head.appendChild(s);
                });
                window._dtiReady = true; return;
              } catch (e) {}
            }
            throw new Error('Failed to load dom-to-image-more');
          }
          await loadScriptOnce(__DTI_URLS__);

          function isTransparent(c) {
            if (!c) return true;
            return c === 'transparent' || c.startsWith('rgba(0, 0, 0, 0)');
          }
          const tlBg  = getComputedStyle(tl).backgroundColor;
          const bodyBg= getComputedStyle(document.body).backgroundColor;
          const bgcolor = isTransparent(tlBg) ? bodyBg : tlBg;

          const ts = new Date().toISOString().replaceAll(':','-').slice(0,19);
          const filename = 'timeline_' + ts + '.png';

          try {
            const dataUrl = await window.domtoimage.toPng(tl, { bgcolor, cacheBust:true });
            const a = document.createElement('a');
            a.href = dataUrl; a.download = filename;
            document.body.appendChild(a); a.click(); a.remove();
          } catch (err) {
            console.error('PNG export failed', err);
            alert('PNG export failed. See console for details.');
          }
        }
      })();
    </script>
  </body>
</html>
    """

    html = (
        html_template
        .replace("__HEIGHT__", str(height_px))
        .replace("__ITEMS__", items_json)
        .replace("__GROUPS__", groups_json)
        .replace("__EXPORT__", export_json)
        .replace("__WS__", ws)
        .replace("__WE__", we)
        .replace("__CSS_URLS_JSON__", css_urls)
        .replace("__JS_URLS_JSON__", js_urls)
        .replace("__DTI_URLS_JSON__", dti_urls)
    )
    components.html(html, height=height_px + 120, scrolling=False)
