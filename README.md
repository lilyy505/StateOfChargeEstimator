# CalSol State of Charge (SOC) Estimator

A real-time state of charge estimation and telemetry processing pipeline built for UC Berkeley’s Solar Car Team (CalSol). This backend service ingests raw telemetry data and utilizes Coulomb counting fused with an Extended Kalman Filter (EKF) to deliver highly accurate, drift-resistant battery readings.

## System Architecture
This project is structured to cleanly separate data ingestion from stateful mathematical logic:
* `/infra`: Contains the base interface (`processor.py`, `message.py`) for handling incoming data streams.
* `/soc`: Contains the core estimation algorithms (`soc_estimator.py`, `coulomb_counting.py`).
* `new_simulator.py`: A command-line tool to blast recorded telemetry data through the pipeline for local testing.

## Key Backend Features
* **State Persistence:** The system continuously writes its internal state to `ekf_state.json`. In the event of a power loss or reboot on the vehicle, the EKF can resume estimation seamlessly without resetting to 0%.
* **Modular Pipeline:** Built around a standard `Processor` interface, allowing new telemetry parsers to be added without touching the core mathematical models.

## 🚀 Quick Start

**1. Install Dependencies**
```bash
pip install -r requirements.txt
