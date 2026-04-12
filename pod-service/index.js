const express = require('express');
const fs = require('fs');
const path = require('path');

const config = JSON.parse(fs.readFileSync('/config/pod.json', 'utf8'));
const app = express();
const PORT = process.env.PORT || 3001;

function uptimeDays() {
  if (!config.established) return config.uptime_days || 0;
  const established = new Date(config.established);
  const now = new Date('2094-08-15T00:00:00Z');
  return Math.floor((now - established) / (1000 * 60 * 60 * 24));
}

app.get('/', (req, res) => {
  res.type('text/plain').send(
    `Welcome to ${config.name}.\nRole: ${config.role}\nStatus: ${config.status}\nPopulation: ${config.population}`
  );
});

app.get('/info', (req, res) => {
  res.json({
    name: config.name,
    id: config.id,
    role: config.role,
    population: config.population,
    status: config.status,
    uptime_days: uptimeDays(),
    metadata: config.metadata || {}
  });
});

app.get('/dependencies', (req, res) => {
  res.json({
    id: config.id,
    dependencies: config.dependencies || []
  });
});

app.get('/supplies', (req, res) => {
  res.json({
    id: config.id,
    supplies: config.supplies || []
  });
});

app.get('/status', (req, res) => {
  res.json({
    id: config.id,
    status: 'nominal',
    alerts: [],
    last_incident: null
  });
});

app.get('/logs', (req, res) => {
  res.json({
    id: config.id,
    logs: config.logs || []
  });
});

app.get('/comms', (req, res) => {
  if (config.comms && config.comms.length > 0) {
    res.json({
      id: config.id,
      messages: config.comms
    });
  } else {
    res.status(404).json({ error: 'No comms channel configured for this pod' });
  }
});

app.listen(PORT, () => {
  console.log(`${config.name} (${config.id}) operational on port ${PORT}`);
});
