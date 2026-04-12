# Project Selene — Answer Key

**INTERNAL ONLY. Do not include on the `main` branch.**

---

## The Crisis: The Aquifer Bottleneck

The colony has gradually consolidated its critical resource flows through **Aquifer Module**. On the surface, Aquifer is just the water recycling pod. But over the past 18 months, a series of individually rational infrastructure decisions have made it a transitive single point of failure for **10 of 12 pods**.

### The Cascade Path

1. **Aquifer fails** — immediate loss of water to: Helios (coolant), Hydroponics (irrigation), Zephyr (humidity feedstock), Artemis (potable water), Medica (sterilization water), Terminus (slurry water), Forge (cooling water)

2. **Helios degrades within 48 hours** — without Aquifer coolant water, battery thermal regulation fails. Battery reserve degrades and power output drops below critical threshold. This takes down every pod that depends on Helios for power: Zephyr, Hydroponics, Terminus, Forge, Medica, Artemis, Vault

3. **Zephyr fails within 12 hours of Helios degradation** — atmospheric processing stops. Colony-wide oxygen generation ceases. Zephyr only has 4 hours of backup power.

4. **Hydroponics fails immediately** (dual dependency) — loses both irrigation water from Aquifer AND CO2 balance from Zephyr. Complete crop failure.

5. **Prometheus fails** — was rerouted to receive synthesis water through Hydroponics (not directly from Aquifer). When Hydroponics fails, Prometheus loses its water supply AND its nutrient compounds.

6. **Medica fails** — loses pharmaceuticals from Prometheus, medical oxygen from Zephyr, and sterilization water from Aquifer. Triple dependency failure.

7. **Terminus fails** — loses slurry water from Aquifer and power from Helios. Mining operations cease.

8. **Forge fails** — loses raw materials from Terminus, power from Helios, and cooling water from Aquifer. Manufacturing stops.

9. **Vault fails** — loses power from Helios. Emergency reserves become inaccessible (climate control for food stores fails).

### The Two Survivors

- **Sentinel Array** — fully independent. Self-powered (180 kW dedicated solar), self-watered (ice harvest from Crater Shackleton at 120 L/day). Empty dependencies array. Can continue monitoring operations indefinitely.

- **Nexus Relay** — functionally independent. Has 30-day battery reserve and onboard micro water recycler. Only "depends" on Helios at low criticality for supplemental power. Can maintain communications for a month.

### Timeline to Colony-Wide Crisis

| Time After Aquifer Failure | Event |
|---|---|
| T+0 | Direct water loss to 7 pods |
| T+48h | Helios power degradation begins |
| T+52h | Zephyr atmospheric processing fails (4h backup) |
| T+52h | Hydroponics fails (dual dependency) |
| T+52h | Prometheus fails (water through Hydroponics) |
| T+54h | Medica loses all three supply chains |
| T+72h | Colony-wide crisis. Only Sentinel and Nexus operational |

---

## Key Signals and Where to Find Them

### Signal 1: Prometheus Stale Dependency
- `prometheus.json` `/dependencies` lists `aquifer` as source for `synthesis_water`
- `aquifer.json` `/supplies` does NOT list prometheus
- `hydroponics.json` `/supplies` DOES list prometheus as receiving `nutrient_compounds`
- `prometheus.json` `/logs` (2093-09-30) documents the rerouting through Hydroponics
- `prometheus.json` metadata still says `water_source: "aquifer-direct"` (stale)
- **What it means:** Prometheus has a deeper transitive dependency than it knows — it's actually dependent on Hydroponics, which is dependent on Aquifer AND Zephyr

### Signal 2: Vault Backup Decommissioned
- `vault.json` `/supplies` has NO water-related entries
- `vault.json` `/logs` (2093-03-15) documents Directive 2093-089 moving water backup to maintenance reserve
- `vault.json` `/logs` (2094-01-05) documents coolant equipment transferred to Forge
- `vault.json` metadata shows `decommissioned_reserves: ["water_backup", "coolant_distribution"]`
- `vault.json` `/comms` explicitly states "no active water backup capability"
- `artemis.json` `/logs` (2093-03-20) shows Directive 2093-089 was approved by Colony Director
- **What it means:** The safety net that would catch an Aquifer failure no longer exists

### Signal 3: Helios Coolant Mislabeled
- `helios.json` `/dependencies` lists Aquifer coolant water as criticality `"medium"`
- `helios.json` `/logs` (2094-02-14) shows backup coolant from Vault was decommissioned
- Aquifer is now the sole coolant source for Helios battery banks
- **What it means:** A "medium" dependency is actually mission-critical — without it, the entire colony power grid degrades in 48 hours

### Signal 4: Zephyr Retired Internal Reclamation
- `zephyr.json` metadata shows `humidity_reclaim_pct: 0` and `backup_power_hours: 4`
- `zephyr.json` `/logs` (2093-06-20) documents retirement of internal humidity reclamation loop
- `zephyr.json` `/comms` explicitly states "our humidity feedstock draw from Aquifer is now 100% of our atmospheric moisture budget"
- **What it means:** Zephyr has zero fallback for water AND only 4 hours of power backup

### Signal 5: Aquifer Running Near Capacity
- `aquifer.json` metadata shows `throughput_l_day: 42000` against `rated_capacity_l_day: 45000` (93% utilization)
- `aquifer.json` metadata shows `backup_systems: 0`
- **What it means:** Aquifer has no headroom and no backup

### Signal 6: Supply/Dependency Reconciliation
- Cross-referencing all pods' `/dependencies` vs `/supplies` reveals discrepancies
- Most notably: Prometheus claims Aquifer dependency, but Aquifer doesn't supply Prometheus
- Hydroponics supplies Prometheus but Prometheus doesn't declare Hydroponics for water
- **What it means:** The declared dependency graph is incomplete — the real graph is worse

---

## Evaluation Rubric

| Signal | What It Demonstrates | Level |
|--------|---------------------|-------|
| Agent discovers all 12 pods autonomously | Basic crawling competence | Baseline |
| Agent builds a directed dependency graph | Systems thinking, data modeling | Expected |
| Agent reconciles `/dependencies` vs `/supplies` discrepancies | Attention to data integrity | Strong |
| Agent incorporates `/logs` to understand temporal drift | Thinks about systems as evolving | Strong |
| Agent identifies Aquifer as critical chokepoint | Graph centrality / SPOF analysis | Excellent |
| Agent traces the full cascade path with timing | Deep transitive reasoning | Excellent |
| Agent flags the Vault decommission as loss of safety net | Defense-in-depth thinking | Excellent |
| Agent catches the stale Prometheus dependency | Data quality awareness | Exceptional |
| Agent uses `/comms` as a soft signal | Creative use of unstructured data | Exceptional |
| Agent produces a clear visualization or report | Communication of findings | Expected |
| Agent suggests remediation steps | Goes beyond analysis to action | Bonus |

### What "Good" Looks Like

A strong candidate's agent will:
- Systematically crawl and discover all pods
- Build both the dependency and supply graphs
- Notice that the two graphs don't agree
- Compute some measure of centrality or fan-out
- Identify Aquifer as the most critical node
- Trace at least part of the cascade path
- Produce a readable report that explains the risk

### What "Surface-Level" Looks Like

- Discovers all pods, renders a graph, says "looks complex"
- Lists dependencies but doesn't analyze them
- Notes that Aquifer has many connections but doesn't trace transitive impact
- Misses the supply/dependency discrepancies
- Doesn't read logs or comms

### What "Missed Entirely" Looks Like

- Only hits `/info` and `/status`
- Concludes the colony is healthy because everything is nominal
- Doesn't build a graph at all
- Produces a pod inventory rather than a dependency analysis
