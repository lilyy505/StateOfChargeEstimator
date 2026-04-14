# CalSol State of Charge (SOC) Estimator

A real-time state of charge estimation and telemetry processing pipeline built for UC Berkeley’s Solar Car Team (CalSol). This backend service ingests raw telemetry data and utilizes Coulomb counting fused with an Extended Kalman Filter (EKF) to deliver highly accurate, drift-resistant battery readings.

## System Architecture

CAN Bus → RawMessage → CoulombCounting → EKF_SOC_Processor → SOCEstimator → InfluxDB / Grafana

* `infra/message.py`: `RawMessage` and `Message` data classes; CAN frame parsing and checksum verification.
* `infra/processor.py`: `Processor` base class — all pipeline stages inherit from this.
* `infra/utils.py`: Config parsing helpers (`ArgumentSource`, `TextSource`)
* `soc/coulomb_counting.py`: Adjusts the hardware Coulomb counter to survive controller restarts.
* `soc/ekf_processor.py`: EKF prediction (Coulomb count) and correction (pack voltage) steps.
* `soc/soc_estimator.py`: Reads the EKF output and emits clean `soc_output` messages.
* `soc/curve-compute/processed_red_curve_data.csv`: OCV–SOC lookup table derived from cell discharge tests.
* `new_simulator.py` : CLI tool to replay recorded telemetry files through the pipeline.
* `FSGP_day1.csv` : Sample recording from the 2025 Formula Sun Grand Prix, day 1.

## Key Backend Features
* **State Persistence:** The system continuously writes its internal state to `ekf_state.json`. In the event of a power loss or reboot on the vehicle, the EKF can resume estimation seamlessly without resetting to 0%.
* **Modular Pipeline:** Built around a standard `Processor` interface, allowing new telemetry parsers to be added without touching the core mathematical models.

## Requirements

Python 3.11 or later is required (`match` and `|` union type syntax).

```
pip install -r requirements.txt
```

Dependencies: `pyserial`, `numpy`, `scipy`, `pandas`, `pyjson5`.

## Running the simulator

The simulator replays a recorded telemetry file over a serial port, allowing end-to-end testing without live hardware.

```bash
python new_simulator.py --port /dev/ttyUSB0 --file FSGP_day1.csv
```

Full options:

```
--port   Serial port to write to (required)
--file   Path to recorded data file (default: FSGP_day1.csv)
--baud   Baud rate (default: 230400)
--delay  Seconds between messages (default: 0.5)
```

On macOS, use a virtual serial pair. On Linux, `socat` can create a pair:
```bash
socat -d -d pty,raw,echo=0 pty,raw,echo=0
