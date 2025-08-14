import streamlit as st
import uuid
import json

def render_timeline(items, groups):
    """Render the roadmap timeline with custom styling."""
    timeline_html = f"""
    <head>
      <link href="https://unpkg.com/vis-timeline@latest/styles/vis-timeline-graph2d.min.css" rel="stylesheet" type="text/css" />
      <style>
        /* Custom styles for a modern look */
        .vis-item {{
            border-radius: 8px;
            padding: 4px 8px;
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
        }}
        .vis-item.vis-selected {{
            box-shadow: 0 0 0 2px #007bff;
        }}
        .vis-label {{
            font-weight: 600;
            font-size: 14px;
        }}
        .vis-time-axis .vis-text {{
            font-size: 12px;
            color: #555;
        }}
        .vis-item .vis-item-overflow {{
            overflow: visible !important;
        }}
        .vis-item-content {{
            overflow: visible !important;
        }}
        .vis-item.vis-background {{
            border-radius: 16px;
        }}
        /* Hide built-in delete handles */
        .vis-delete {{ display:none !important; }}
      </style>
    </head>
    <body>
      <div id="visualization"></div>
      <script type="text/javascript" src="https://unpkg.com/vis-timeline@latest/standalone/umd/vis-timeline-graph2d.min.js"></script>
      <script type="text/javascript">
        var container = document.getElementById('visualization');
        var items = new vis.DataSet({json.dumps(items)});
        var groups = new vis.DataSet({json.dumps(groups)});
        var options = {{
          editable: {{
            updateTime: true,
            updateGroup: true,
            remove: false, // we disable delete from the timeline itself
            add: false
          }},
          stack: false,
          orientation: 'top',
          margin: {{
            item: 20,
            axis: 40
          }},
          multiselect: false
        }};
        var timeline = new vis.Timeline(container, items, groups, options);
      </script>
    </body>
    """
    st.components.v1.html(timeline_html, height=600, scrolling=True)