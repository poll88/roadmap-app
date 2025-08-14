import express from 'express';
import cors from 'cors';

const app = express();
const port = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// In-memory store for roadmap data
let store = {
  groups: [
    { id: 1, content: 'Hybrid Inverter (3‑phase)' },
    { id: 2, content: 'Hybrid Inverter (1‑phase)' },
    { id: 3, content: 'Residential Battery' }
  ],
  items: []
};

// Health check
app.get('/api/health', (req, res) => res.json({ ok: true }));

// Get all roadmap data
app.get('/api/data', (req, res) => {
  res.json(store);
});

// Save roadmap data
app.post('/api/data', (req, res) => {
  const { groups, items } = req.body || {};
  if (Array.isArray(groups)) store.groups = groups;
  if (Array.isArray(items)) store.items = items;
  res.json({ ok: true });
});

app.listen(port, () => {
  console.log(`Backend running on port ${port}`);
});
