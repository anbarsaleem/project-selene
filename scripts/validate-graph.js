#!/usr/bin/env node

/**
 * Graph validator for Project Selene configs.
 * Reads all 12 pod configs and verifies the crisis geometry is intact.
 *
 * Run: node scripts/validate-graph.js
 */

const fs = require('fs');
const path = require('path');

const configDir = path.join(__dirname, '..', 'configs');
const podIds = [
  'helios', 'artemis', 'hydroponics', 'aquifer', 'zephyr', 'prometheus',
  'medica', 'terminus', 'nexus', 'forge', 'vault', 'sentinel'
];

// Load all configs
const configs = {};
for (const id of podIds) {
  const filePath = path.join(configDir, `${id}.json`);
  configs[id] = JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

let errors = 0;
let warnings = 0;

function error(msg) { errors++; console.error(`  ERROR: ${msg}`); }
function warn(msg) { warnings++; console.warn(`  WARN:  ${msg}`); }
function info(msg) { console.log(`  INFO:  ${msg}`); }

// 1. Build dependency graph (who depends on whom)
console.log('\n=== Dependency Graph ===');
const depGraph = {};  // depGraph[A] = [B, C] means A depends on B and C
for (const id of podIds) {
  depGraph[id] = (configs[id].dependencies || []).map(d => d.pod_id);
  console.log(`  ${id} depends on: ${depGraph[id].join(', ') || '(none)'}`);
}

// 2. Build supply graph (who supplies whom)
console.log('\n=== Supply Graph ===');
const supplyGraph = {};  // supplyGraph[A] = [B, C] means A supplies B and C
for (const id of podIds) {
  supplyGraph[id] = (configs[id].supplies || []).map(s => s.pod_id);
  console.log(`  ${id} supplies: ${supplyGraph[id].join(', ') || '(none)'}`);
}

// 3. Reconcile discrepancies
console.log('\n=== Discrepancy Check ===');
for (const id of podIds) {
  for (const dep of (configs[id].dependencies || [])) {
    const supplier = dep.pod_id;
    const supplierSupplies = supplyGraph[supplier] || [];
    if (!supplierSupplies.includes(id)) {
      warn(`${id} declares dependency on ${supplier}, but ${supplier} does NOT list ${id} in supplies`);
    }
  }
}
for (const id of podIds) {
  for (const sup of (configs[id].supplies || [])) {
    const consumer = sup.pod_id;
    const consumerDeps = depGraph[consumer] || [];
    if (!consumerDeps.includes(id)) {
      warn(`${id} supplies ${consumer}, but ${consumer} does NOT list ${id} in dependencies`);
    }
  }
}

// 4. Compute transitive closure from Aquifer
console.log('\n=== Transitive Dependency on Aquifer ===');
// Build reverse graph: if A depends on B, then B failing affects A
const affectedBy = {};  // affectedBy[B] = [A, C] means if B fails, A and C are affected
for (const id of podIds) {
  affectedBy[id] = [];
}
for (const id of podIds) {
  for (const dep of depGraph[id]) {
    affectedBy[dep].push(id);
  }
}

// BFS from aquifer
function transitiveAffected(startNode) {
  const visited = new Set();
  const queue = [startNode];
  while (queue.length > 0) {
    const node = queue.shift();
    for (const affected of affectedBy[node]) {
      if (!visited.has(affected)) {
        visited.add(affected);
        queue.push(affected);
      }
    }
  }
  return visited;
}

const aquiferAffectedRaw = transitiveAffected('aquifer');
// Remove aquifer itself from the affected set (circular dependency with helios is expected)
aquiferAffectedRaw.delete('aquifer');
const aquiferAffected = aquiferAffectedRaw;
console.log(`  Pods transitively affected by Aquifer failure (${aquiferAffected.size}):`);
for (const pod of podIds) {
  if (aquiferAffected.has(pod)) {
    info(`  ${pod} - AFFECTED`);
  }
}

console.log(`\n  Pods NOT affected by Aquifer failure:`);
for (const pod of podIds) {
  if (!aquiferAffected.has(pod) && pod !== 'aquifer') {
    info(`  ${pod} - INDEPENDENT`);
  }
}

// 5. Validate expected crisis geometry
console.log('\n=== Crisis Geometry Validation ===');

const expectedAffected = new Set([
  'helios', 'artemis', 'hydroponics', 'zephyr', 'prometheus',
  'medica', 'terminus', 'forge', 'vault', 'nexus'
]);
const expectedIndependent = new Set(['sentinel']);

// Nexus should be technically reachable but functionally independent
// For graph purposes it IS in the transitive closure (depends on helios which depends on aquifer)
// but its metadata shows 30-day battery reserve

if (aquiferAffected.size === 10) {
  info('Aquifer affects exactly 10 pods (including nexus via helios)');
} else {
  error(`Aquifer affects ${aquiferAffected.size} pods, expected 10`);
}

if (!aquiferAffected.has('sentinel')) {
  info('Sentinel is independent of Aquifer');
} else {
  error('Sentinel should NOT be affected by Aquifer');
}

// 6. Check specific signals
console.log('\n=== Signal Verification ===');

// Prometheus stale dependency
const promDeps = configs.prometheus.dependencies.map(d => d.pod_id);
const aquiferSupplies = configs.aquifer.supplies.map(s => s.pod_id);
const hydroSupplies = configs.hydroponics.supplies.map(s => s.pod_id);

if (promDeps.includes('aquifer') && !aquiferSupplies.includes('prometheus') && hydroSupplies.includes('prometheus')) {
  info('Prometheus stale dependency signal INTACT');
} else {
  error('Prometheus stale dependency signal BROKEN');
  info(`  prometheus deps include aquifer: ${promDeps.includes('aquifer')}`);
  info(`  aquifer supplies include prometheus: ${aquiferSupplies.includes('prometheus')}`);
  info(`  hydroponics supplies include prometheus: ${hydroSupplies.includes('prometheus')}`);
}

// Vault decommission
const vaultSupplyResources = configs.vault.supplies.map(s => s.resource);
const hasWaterSupply = vaultSupplyResources.some(r => r.toLowerCase().includes('water'));
if (!hasWaterSupply) {
  info('Vault has no water in supplies (decommission signal INTACT)');
} else {
  error('Vault still has water in supplies — decommission signal BROKEN');
}

// Sentinel independence
if (configs.sentinel.dependencies.length === 0) {
  info('Sentinel has empty dependencies (independence signal INTACT)');
} else {
  error('Sentinel has dependencies — independence signal BROKEN');
}

// Helios coolant criticality
const heliosCoolant = configs.helios.dependencies.find(d => d.pod_id === 'aquifer');
if (heliosCoolant && heliosCoolant.criticality === 'medium') {
  info('Helios coolant criticality is "medium" (mislabel signal INTACT)');
} else {
  error('Helios coolant criticality is not "medium" — mislabel signal BROKEN');
}

// Nexus independence metadata
if (configs.nexus.metadata.independent_power_days >= 30 && configs.nexus.metadata.water_recycler) {
  info('Nexus independence metadata INTACT');
} else {
  error('Nexus independence metadata BROKEN');
}

// Aquifer near capacity
const utilization = configs.aquifer.metadata.throughput_l_day / configs.aquifer.metadata.rated_capacity_l_day;
if (utilization > 0.9) {
  info(`Aquifer utilization at ${(utilization * 100).toFixed(1)}% (near-capacity signal INTACT)`);
} else {
  warn(`Aquifer utilization at ${(utilization * 100).toFixed(1)}% — may not read as "near capacity"`);
}

// Summary
console.log('\n=== Summary ===');
console.log(`  Errors:   ${errors}`);
console.log(`  Warnings: ${warnings}`);
console.log(`  ${errors === 0 ? 'PASS — Crisis geometry is intact.' : 'FAIL — See errors above.'}\n`);

process.exit(errors > 0 ? 1 : 0);
