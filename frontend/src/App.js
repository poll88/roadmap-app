import React, { useEffect, useRef, useState } from 'react';
import { DataSet, Timeline } from 'vis-timeline/standalone';
import 'vis-timeline/styles/vis-timeline-graph2d.css';

const apiUrl = process.env.REACT_APP_API_URL || '/api';

export default function App() {
  const containerRef = useRef(null);
  const timelineRef = useRef(null);

  const [groupsDS] = useState(() => new DataSet([
    { id: 1, content: 'Hybrid Inverter (3‑phase)' },
    { id: 2, content: 'Hybrid Inverter (1‑phase)' },
    { id: 3, content: 'Residential Battery' }
  ]));
  const [itemsDS] = useState(() => new DataSet([]));

  const [form, setForm] = useState({
    title: 'New item',
    group: 1,
    start: '2025-01-01',
    end: '2025-06-01',
    color: '#7dd3fc',
    comment: ''
  });

  const [windowStart, setWindowStart] = useState('2025-01-01');
  const [windowEnd, setWindowEnd] = useState('2026-01-01');
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    const options = {
      stack: false,
      editable: { updateTime: true, updateGroup: true },
      orientation: 'top',
      start: windowStart,
      end: windowEnd,
      onMove: (item, cb) => { itemsDS.update(item); cb(item); saveAll(); }
    };
    timelineRef.current = new Timeline(containerRef.current, itemsDS, groupsDS, options);
    timelineRef.current.on('select', (props) => { setSelectedId(props.items[0] || null); });
    loadAll();
    return () => { if (timelineRef.current) timelineRef.current.destroy(); };
  }, []);

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.setWindow(windowStart, windowEnd);
    }
  }, [windowStart, windowEnd]);

  const addItem = () => {
    const id = Date.now();
    itemsDS.add({
      id,
      group: Number(form.group),
      content: form.title,
      start: form.start,
      end: form.end,
      title: form.comment,
      style: `background-color:${form.color}; border-color:${form.color};`
    });
    setSelectedId(id);
    saveAll();
  };

  const deleteSelected = () => {
    if (!selectedId) return;
    itemsDS.remove(selectedId);
    setSelectedId(null);
    saveAll();
  };

  const updateSelected = () => {
    if (!selectedId) return;
    itemsDS.update({
      id: selectedId,
      group: Number(form.group),
      content: form.title,
      title: form.comment,
      style: `background-color:${form.color}; border-color:${form.color};`
    });
    saveAll();
  };

  const addGroup = () => {
    const name = prompt('New category name');
    if (!name) return;
    const id = Date.now();
    groupsDS.add({ id, content: name });
    saveAll();
  };

  async function loadAll() {
    try {
      const r = await fetch(`${apiUrl}/data`);
      if (!r.ok) return;
      const data = await r.json();
      groupsDS.clear();
      itemsDS.clear();
      groupsDS.add(data.groups || []);
      itemsDS.add(data.items || []);
    } catch (e) { console.warn('Load failed', e); }
  }

  async function saveAll() {
    try {
      const payload = { groups: groupsDS.get(), items: itemsDS.get() };
      await fetch(`${apiUrl}/data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch (e) { console.warn('Save failed', e); }
  }

  return (
    <>
      <header>
        <h2>Roadmap Timeline</h2>
      </header>
      <div className="container">
        <div className="controls">
          <div>
            <label>Title</label>
            <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
          </div>
          <div>
            <label>Group</label>
            <select value={form.group} onChange={e => setForm({ ...form, group: e.target.value })}>
              {groupsDS.get().map(g => <option key={g.id} value={g.id}>{g.content}</option>)}
            </select>
          </div>
          <div>
            <label>Start</label>
            <input type="date" value={form.start} onChange={e => setForm({ ...form, start: e.target.value })} />
          </div>
          <div>
            <label>End</label>
            <input type="date" value={form.end} onChange={e => setForm({ ...form, end: e.target.value })} />
          </div>
          <div>
            <label>Color</label>
            <input type="color" value={form.color} onChange={e => setForm({ ...form, color: e.target.value })} />
          </div>
          <div>
            <label>Comment</label>
            <input value={form.comment} onChange={e => setForm({ ...form, comment: e.target.value })} />
          </div>
          <button className="primary" onClick={addItem}>Add Item</button>
          <button className="secondary" onClick={updateSelected} disabled={!selectedId}>Update</button>
          <button className="secondary" onClick={deleteSelected} disabled={!selectedId}>Delete</button>
        </div>
        <div style={{ marginTop: '10px' }}>
          <button onClick={addGroup}>+ Add Category</button>
          <span style={{ marginLeft: '20px' }}>View from</span>
          <input type="date" value={windowStart} onChange={e => setWindowStart(e.target.value)} />
          <span>-</span>
          <input type="date" value={windowEnd} onChange={e => setWindowEnd(e.target.value)} />
        </div>
        <div id="timeline" ref={containerRef} style={{ marginTop: 12 }}></div>
      </div>
    </>
  );
}
