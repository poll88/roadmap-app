import json
from datetime import date, datetime
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
    from datetime import date, datetime
    if isinstance(d, (date, datetime)):
        return d.isoformat()
    return d

def render_timeline(items, groups, selected_id: str = "", export=None, stack: bool = True, height_px: int | None = None):
    items_json  = json.dumps([{**i, "start": _dt(i.get("start")), "end": _dt(i.get("end"))} for i in items])
    groups_json = json.dumps([{"id": g.get("id"), "content": g.get("content")} for g in groups])
    export_json = json.dumps(export or {})
    css_urls = json.dumps(_VIS_CSS_URLS)
    js_urls  = json.dumps(_VIS_JS_URLS)
    dti_urls = json.dumps(_DOM_TO_IMG_URLS)

    rows = max(1, len(groups))
    default_height = max(260, 80 * rows + 120)
    H = int(height_px or default_height)

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{ --font: 'Montserrat', ui-sans-serif, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }}
    html, body {{ background: transparent; margin:0; padding:0; }}
    body, #timeline, .vis-timeline, .vis-item, .vis-item-content, .vis-label, .vis-time-axis {{ font-family: var(--font); }}
    #wrap {{ position: relative; }}
    #timeline {{ height:{H}px; background: transparent; border-radius:12px; border:1px solid #e7e9f2; }}
    .ttl {{ font-weight:700 }}
    .sub {{ font-size:12px; opacity:.9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px }}

    #timeline.exporting,
    #timeline.exporting .vis-timeline,
    #timeline.exporting .vis-panel,
    #timeline.exporting .vis-foreground,
    #timeline.exporting .vis-background,
    #timeline.exporting .vis-time-axis {{ background: transparent !important; }}

    .hint {{
      position:absolute; right:12px; top:8px; padding:4px 8px; border-radius:8px;
      background: rgba(99,102,241,.08); color:#444; font-size:12px; user-select:none;
    }}
  </style>
</head>
<body>
  <div id="wrap">
    <div class="hint">Drag to move • Drag up/down to change row</div>
    <div id="timeline"></div>
  </div>

  <script>
    const CSS = {css_urls};
    const JS  = {js_urls};
    const DTI = {dti_urls};
    const ITEMS  = {items_json};
    const GROUPS = {groups_json};
    const EXPORT = {export_json};

    function loadCSSOnce(urls) {{
      return Promise.all(urls.map(u => new Promise(res => {{
        const l = document.createElement('link'); l.rel='stylesheet'; l.href=u;
        l.onload=() => res(); l.onerror=() => res(); document.head.appendChild(l);
      }})));
    }}
    function loadJSOnce(urls) {{
      if (window._visReady) return Promise.resolve();
      return new Promise((resolve, reject) => {{
        let i=0; const next=() => {{
          if (i>=urls.length) return reject(new Error('vis load failed'));
          const s=document.createElement('script'); s.src=urls[i++]; s.async=true;
          s.onload=() => {{ window._visReady=true; resolve(); }};
          s.onerror=next; document.head.appendChild(s);
        }}; next();
      }});
    }}

    function layout() {{
      const el=document.getElementById('timeline'); if (!el || !window.vis) return;

      const NEED_UNGROUPED = (ITEMS||[]).some(it => !it.group) || (GROUPS||[]).length===0;
      const groupsAll = NEED_UNGROUPED ? [{{id:'_ungrouped', content:'Ungrouped'}}].concat(GROUPS||[]) : (GROUPS||[]);

      const items = new vis.DataSet((ITEMS||[]).map(it => {{
        const o = {{
          id: it.id,
          content: '<div class="ttl">'+(it.content||'')+'</div><div class="sub">'+(it.subtitle||'')+'</div>',
          start: it.start, end: it.end, style: it.style, orderKey: it.orderKey
        }};
        o.group = (it.group && String(it.group).trim()) ? it.group : '_ungrouped';
        return o;
      }}));
      const groups = new vis.DataSet(groupsAll.map(g => ({{id:g.id, content:g.content}})));

      const opts = {{
        stack: true,                // always on (your new request)
        editable: {{
          updateTime: true,         // drag left/right
          updateGroup: true,        // drag up/down to other row
          add: false,
          remove: false
        }},
        multiselect: true,
        snap: null,                 // free drag (no day snapping)
        orientation: 'top',
        horizontalScroll: true,
        zoomKey: 'ctrlKey',
        zoomMax: 1000*60*60*24*366*10,
        zoomMin: 1000*60*60*12,
        showMajorLabels: true,
        showMinorLabels: true,
        margin: {{ item: 8, axis: 12 }},
        order: function(a,b) {{
          const ka = (a.orderKey ?? 0), kb = (b.orderKey ?? 0);
          if (ka !== kb) return ka - kb;
          return (+new Date(a.start||0)) - (+new Date(b.start||0));
        }}
      }};

      const tl = new vis.Timeline(el, items, groups, opts);
      window._tl = tl;

      // nice initial window
      try {{
        if (items.length) {{
          const arr = items.get();
          const mins = Math.min.apply(null, arr.map(x => +new Date(x.start)));
          const maxs = Math.max.apply(null, arr.map(x => +new Date(x.end || x.start)));
          const pad = Math.max(3*86400000, Math.round((maxs-mins)*0.05));
          tl.setWindow(new Date(mins-pad), new Date(maxs+pad), {{animation:false}});
        }}
      }} catch(e) {{}}

      // NOTE: edits stay client-side (visual only) with components.html.
      // Later we can promote this to a real Streamlit component and post changes back.
    }}

    (function init(){{
      loadCSSOnce(CSS).then(() => loadJSOnce(JS)).then(() => {{
        layout();
        if (EXPORT && EXPORT.kind==='png') setTimeout(()=>exportPNG(EXPORT), 60);
      }}).catch(() => {{
        const el = document.getElementById('timeline');
        if (el) el.innerHTML = '<div style="padding:16px;color:#999">Timeline failed to load.</div>';
      }});
    }})();

    // --- PNG export (unchanged: Montserrat + background checkbox) ---
    async function exportPNG(EXPORT) {{
      const tl = document.getElementById('timeline'); if (!tl) return;

      async function script(urls) {{
        if (window._dtiReady) return;
        for (const u of urls) {{
          try {{
            await new Promise((res, rej)=>{{ const s=document.createElement('script'); s.src=u; s.async=true;
              s.onload=()=>res(); s.onerror=rej; document.head.appendChild(s); }});
            window._dtiReady = true; return;
          }} catch(e){{}}
        }}
        throw new Error('dom-to-image load failed');
      }}
      await script({dti_urls});

      async function ensureFonts(){{
        if (document.fonts && document.fonts.ready){{
          try {{ await document.fonts.ready; }} catch(e){{}}
          const req = ["400 14px 'Montserrat'","600 14px 'Montserrat'","700 14px 'Montserrat'"];
          try {{ await Promise.all(req.map(r=>document.fonts.load(r))); }} catch(e){{}}
        }} else {{
          const span=document.createElement('span'); span.textContent='A';
          span.style.visibility='hidden'; span.style.fontFamily="'Montserrat', sans-serif";
          document.body.appendChild(span); await new Promise(r=>setTimeout(r,120)); span.remove();
        }}
        await new Promise(r=>setTimeout(r,50));
      }}
      await ensureFonts();

      const includeBg = !!(EXPORT && EXPORT.includeBg);
      function isT(c){{ return !c || c==='transparent' || c.startsWith('rgba(0, 0, 0, 0)'; }}
      const csTl = getComputedStyle(tl), csBody = getComputedStyle(document.body);
      let bg = includeBg
        ? (!isT(csTl.backgroundColor) ? csTl.backgroundColor
          : (!isT(csBody.backgroundColor) ? csBody.backgroundColor : '#ffffff'))
        : 'transparent';

      const old = {{ border:tl.style.border, borderRadius:tl.style.borderRadius, background:tl.style.background, backgroundColor:tl.style.backgroundColor }};
      tl.style.border='none'; tl.style.borderRadius='0px';
      if (!includeBg) {{ tl.classList.add('exporting'); tl.style.background='transparent'; tl.style.backgroundColor='transparent'; }}

      function walk(el,fn){{ fn(el); for(let i=0;i<el.children.length;i++) walk(el.children[i],fn); }}
      const touched=[]; const fam="'Montserrat', ui-sans-serif, -apple-system, Segoe UI, Roboto, Helvetica, Arial";
      walk(tl, n=>{{ const p=n.style.fontFamily; n.style.fontFamily=fam; touched.push([n,p]); }});

      const ts = new Date().toISOString().replaceAll(':','-').slice(0,19);
      const filename = 'timeline_'+ts+'.png';
      try {{
        const dataUrl = await window.domtoimage.toPng(tl, {{ bgcolor:bg, cacheBust:true }});
        const a=document.createElement('a'); a.href=dataUrl; a.download=filename; document.body.appendChild(a); a.click(); a.remove();
      }} catch(err) {{
        console.error('PNG export failed', err); alert('PNG export failed.');
      }} finally {{
        for (const [el,p] of touched) el.style.fontFamily = p || '';
        tl.style.border = old.border; tl.style.borderRadius = old.borderRadius; tl.style.background = old.background; tl.style.backgroundColor = old.backgroundColor;
        tl.classList.remove('exporting');
      }}
    }}
  </script>
</body>
</html>
"""
    components.html(html, height=H + 20, scrolling=False)
