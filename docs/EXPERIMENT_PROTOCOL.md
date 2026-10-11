# Experiment Protocol: Multi-Objective Traffic Signal Optimization

**Project Title:** Simulation-Based Safe Multi-Objective Adaptive Traffic Signal Optimization Using Reinforcement Learning
**Working Directory:** `D:\Traffic-Opt-RL`
**Date:** 2026-10-10

---

## 1. Scope & Objective

This document establishes the reproducible experimental protocol for evaluating and comparing traffic signal control strategies on the research intersection. The evaluation measures efficiency, safety, and environmental impact under identical conditions.

---

## 2. Experimental Setup

### A. Network & Topology
- **Network File:** [`environment/single_intersection.net.xml`](file:///D:/Traffic-Opt-RL/environment/single_intersection.net.xml)
- **Signalized Junction ID:** `C`
- **Incoming Lanes (8):** `N_in_0`, `N_in_1`, `S_in_0`, `S_in_1`, `E_in_0`, `E_in_1`, `W_in_0`, `W_in_1`
- **Exit Lanes (8):** `N_out_0`, `N_out_1`, `S_out_0`, `S_out_1`, `E_out_0`, `E_out_1`, `W_out_0`, `W_out_1`
- **Signal Logic:**
  - Phase 0: North–South Green (`GGGggrrrrrGGGggrrrrr`, default 42s)
  - Phase 1: North–South Yellow Clearance (`yyyyyrrrrryyyyyrrrrr`, 3s)
  - Phase 2: East–West Green (`rrrrrGGGggrrrrrGGGgg`, default 42s)
  - Phase 3: East–West Yellow Clearance (`rrrrryyyyyrrrrryyyyy`, 3s)

### B. Route Demand Files
- **Functional Validation:** [`environment/routes.rou.xml`](file:///D:/Traffic-Opt-RL/environment/routes.rou.xml) (8 vehicles, deterministic departures t=0 to 14s).
- **Benchmark Evaluation:** Evaluated across distinct random seeds to verify simulator stability.

### C. Timing Guardrails
- **Minimum Green:** 5.0 seconds (hard constraint enforced by transition manager).
- **Maximum Green:** 45.0 seconds (forced switch trigger).
- **Yellow Clearance:** 3.0 seconds (executed actively in SUMO before entering conflicting green).
- **Control Interval:** 1.0 second per decision point.

---

## 3. Evaluated Controllers

1. **FixedTimeController (`controllers/fixed_time.py`):**
   - Deterministic cyclic green phases.
   - Fixed green duration: 42.0 seconds per phase.
   - Action 0 (Phase 0) $\to$ Action 1 (Phase 2) $\to$ Action 0.

2. **ActuatedController (`controllers/actuated.py`):**
   - Vehicle-actuated gap-out control.
   - Monitors queue length and vehicle counts on incoming lanes for the active approach.
   - If demand is present, extends green up to 45.0s maximum.
   - If approach is clear and min green (5.0s) has elapsed, gaps out and commands conflicting green.

3. **Reinforcement Learning Agent (PPOController in `controllers/ppo.py`):**
   - Deep RL agent with policy network trained via Stable-Baselines3 PPO.
   - Emits discrete action indices in `{0, 1}` indicating desired target green phase.
   - Strictly wrapped under `BaseTrafficController`; never commands TraCI directly.
   - Subject to identical transition manager and clearance constraints.

---

## 4. Performance Metrics & Definitions

| Metric | Source | Definition / Aggregation | Units |
|:---|:---|:---|:---|
| **Completed Throughput** | Exit Lane Arrivals | Total vehicles that traversed the intersection and exited via verified exit lanes | vehicles |
| **Completion Rate** | Exit vs Inflow | Ratio of completed vehicles to total inserted vehicles | % |
| **Mean Waiting Time** | TraCI `lane.getWaitingTime` | Average accumulated waiting time (>0.1 m/s halt) per step across all incoming lanes | seconds / step |
| **Mean Queue Length** | TraCI `lane.getLastStepHaltingNumber` | Average number of halting vehicles per step across all incoming lanes | vehicles / step |
| **Total Stops** | TraCI Vehicle Speeds | Total deceleration events below 0.1 m/s recorded during the episode | count |
| **Total Emissions ($CO_2$)** | TraCI `lane.getCO2Emission` | Cumulative $CO_2$ emissions integrated over simulation steps | milligrams (mg) |
| **Simulation Time** | TraCI `simulation.getTime` | Total simulator time from t=0 until all vehicles arrive or max_steps reached | seconds |
| **Phase Switches** | Environment Info | Total green phase changes executed | count |
| **Clearance Episodes** | Environment Info | Number of times yellow clearance was actively executed | count |

---

## 5. Execution & Reproducibility Commands

### Run Full Test Suite (117 Tests in the Latest Verified Run)
```powershell
.\.venv\Scripts\python.exe -m unittest discover tests -v
```

### Run SUMO Smoke Test
```powershell
.\.venv\Scripts\python.exe tests\smoke_test.py
```

### Run Baseline Comparison Benchmark
```powershell
.\.venv\Scripts\python.exe evaluation\benchmark.py
```
Outputs are automatically saved to `results/baselines/baseline_comparison_results.json` and `results/baselines/baseline_comparison_results.csv`.

### Generate Multi-Demand Scenarios
```powershell
.\.venv\Scripts\python.exe scripts\generate_demand.py --duration 300 --seed 42
```
Generates verified reproducible demand files in `data/routes/`: `demand_low_seed42.rou.xml` (400 veh/hr), `demand_medium_seed42.rou.xml` (1,200 veh/hr), and `demand_high_seed42.rou.xml` (2,400 veh/hr).

### Train PPO Agent (Smoke / Full)
```powershell
# Fast smoke run:
.\.venv\Scripts\python.exe training\train_ppo.py --timesteps 256 --routes environment\routes.rou.xml --outdir models\ppo_smoke --seed 42

# Production training:
.\.venv\Scripts\python.exe training\train_ppo.py --timesteps 10000 --routes data\routes\demand_medium_seed42.rou.xml --outdir models\ppo_medium --seed 42
```

### Run Tri-Controller Evaluation Benchmark
```powershell
.\.venv\Scripts\python.exe evaluation\evaluate_all.py --routes environment\routes.rou.xml --model models\ppo_smoke\ppo_traffic_final.zip --seeds 301 302 303 --outdir results\evaluations_smoke --max_steps 300
```
Raw per-run records: `results/evaluations_smoke/evaluation_raw_results.csv` and `.json`.
Summary table (mean ± sample std): `results/evaluations_smoke/evaluation_summary.csv` and `.json`.
