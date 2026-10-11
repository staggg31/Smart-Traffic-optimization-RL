# PPO Training and Evaluation Guide: Traffic-Opt-RL

**Project:** Simulation-Based Safe Multi-Objective Adaptive Traffic Signal Optimization Using Reinforcement Learning
**Working Directory:** `D:\Traffic-Opt-RL`
**Environment:** Windows 11, Python 3.12.10 (`.venv`), Eclipse SUMO 1.28.0

---

## 1. Environment Prerequisites

Ensure the following tools and environment variables are active:
- **Python:** 3.12.10 (located in `.venv/Scripts/python.exe`)
- **SUMO:** Eclipse SUMO 1.28.0 installed at `C:\Program Files (x86)\SUMO`
- **SUMO_HOME:** Set to `C:\Program Files (x86)\SUMO`
- **PATH:** Contains `C:\Program Files (x86)\SUMO\bin`

Verify in PowerShell:
```powershell
.\.venv\Scripts\python.exe -c "import sumo; import traci; print('TraCI OK')"
```

---

## 2. Dependencies and Installation

The project uses CPU-compatible PyTorch and Stable-Baselines3 compatible with Gymnasium 1.0.0 and NumPy 2.x:

| Package | Installed Version |
| :--- | :--- |
| `torch` | `2.5.1+cpu` |
| `torchvision` | `0.20.1+cpu` |
| `torchaudio` | `2.5.1+cpu` |
| `stable-baselines3` | `2.5.0` |
| `gymnasium` | `1.0.0` |
| `numpy` | `2.5.3` |
| `pandas` | `3.0.6` |
| `matplotlib` | `3.11.2` |
| `traci` | `1.28.0` |

If reinstalling into a fresh environment:
```powershell
.\.venv\Scripts\python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install "stable-baselines3==2.5.0" "pandas" "matplotlib"
```

---

## 3. Demand Scenario Generation

Pre-generate reproducible Poisson arrival route files for training and evaluation:

```powershell
# Low demand (400 veh/hr)
.\.venv\Scripts\python.exe scripts/generate_demand.py --flow low --seed 42 --duration 3600 --output data/routes/demand_low_seed42.rou.xml

# Medium demand (1200 veh/hr)
.\.venv\Scripts\python.exe scripts/generate_demand.py --flow medium --seed 42 --duration 3600 --output data/routes/demand_medium_seed42.rou.xml

# High demand (2400 veh/hr)
.\.venv\Scripts\python.exe scripts/generate_demand.py --flow high --seed 42 --duration 3600 --output data/routes/demand_high_seed42.rou.xml
```

Fast regression fixture (8 vehicles) is permanently available at:
- `environment/routes.rou.xml`

---

## 4. Starting a Short Smoke Training Run

Verify the complete training loop, TraCI integration, checkpointing, and exception handling without waiting for a lengthy optimization run:

```powershell
.\.venv\Scripts\python.exe training/train_ppo.py --timesteps 256 --routes environment/routes.rou.xml --outdir models/ppo_smoke --seed 42 --n_steps 128 --batch_size 64
```

Expected outputs:
- Model checkpoint: `models/ppo_smoke/ppo_traffic_final.zip`
- Metadata: `models/ppo_smoke/training_metadata.json`

---

## 5. Starting a Full Production Training Run

Launch a full training run on the reproducible Medium-demand scenario (10,000 steps recommended for initial convergence, 50,000 steps for production):

```powershell
.\.venv\Scripts\python.exe training/train_ppo.py --timesteps 10000 --routes data/routes/demand_medium_seed42.rou.xml --outdir models/ppo_medium --logdir logs/ppo_medium --seed 42 --lr 0.0003 --n_steps 128 --batch_size 64
```

CLI Parameter Reference:
- `--timesteps`: Total simulation decision steps (default `1000`).
- `--routes`: Path to route file (default `data/routes/demand_low_seed42.rou.xml`).
- `--outdir`: Checkpoints directory (default `models/ppo`).
- `--logdir`: Logging directory (default `logs/ppo`).
- `--seed`: Random seed for environment and policy (default `42`).
- `--lr`: Learning rate for Adam optimizer (default `0.0003`).
- `--n_steps`: Rollout buffer size per policy update (default `128`).
- `--batch_size`: Minibatch size for gradient steps (default `64`).

---

## 6. Evaluating Saved Models (Tri-Controller Benchmark)

Compare the trained PPO controller against the Fixed-Time and Actuated baseline controllers on identical demand scenarios and strictly held-out evaluation seeds (e.g., 301, 302, 303):

### Fast smoke evaluation:
```powershell
.\.venv\Scripts\python.exe evaluation/evaluate_all.py --routes environment/routes.rou.xml --model models/ppo_smoke/ppo_traffic_final.zip --seeds 301 302 303 --outdir results/evaluations_smoke --max_steps 300
```

### Full Medium-demand evaluation:
```powershell
.\.venv\Scripts\python.exe evaluation/evaluate_all.py --routes data/routes/demand_medium_seed42.rou.xml --model models/ppo_medium/ppo_traffic_final.zip --seeds 301 302 303 --outdir results/evaluations_medium --max_steps 500
```

---

## 7. Output Locations & Artifacts

All experiment runs generate transparent, reproducible records:

| Filepath | Description |
| :--- | :--- |
| `models/<run>/ppo_traffic_final.zip` | Saved Stable-Baselines3 PPO model zip archive. |
| `models/<run>/training_metadata.json` | Exact hyperparameters, spaces, and timestamps. |
| `results/<eval>/evaluation_raw_results.json` | Complete per-episode telemetry and configuration. |
| `results/<eval>/evaluation_raw_results.csv` | Flat CSV table with per-seed metrics for each controller. |
| `results/<eval>/evaluation_summary.json` | Mean ± sample standard deviation across evaluation seeds. |
| `results/<eval>/evaluation_summary.csv` | Formatted summary comparison table. |

---

## 8. Reproducing Test Results

Run the full automated test suite (the latest recorded verification run passed 117 tests, including unit, mock, API, and real-SUMO integration tests):

```powershell
.\.venv\Scripts\python.exe -m unittest discover tests -v
```

Verify that the run finishes with `OK` (0 errors, 0 failures, 0 skips). Note that test counts and execution timings describe the latest recorded run and may change as the test suite evolves.
