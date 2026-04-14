"""
Telemetry simulator for the SOC estimator pipeline.

Reads a recorded data file and replays it over a serial port, allowing the
full pipeline to be tested locally without live hardware.

Usage:
    python new_simulator.py --port /dev/ttyUSB0 --file FSGP_day1.csv
    python new_simulator.py --port /dev/ttyUSB0 --file path/to/recorded.txt --baud 230400

The default data file is FSGP_day1.csv in the repo root.
The default baud rate is 230400.
"""

import argparse
import time
import os
import serial
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Defaults 
DEFAULT_FILE = os.path.join(os.path.dirname(__file__), "FSGP_day1.csv")
DEFAULT_BAUD = 230400
INTER_MESSAGE_DELAY_S = 0.5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay recorded telemetry over a serial port.")
    parser.add_argument(
        "--port",
        required=True,
        help="Serial port to write to (e.g. /dev/ttyUSB0 or COM3).",
    )
    parser.add_argument(
        "--file",
        default=DEFAULT_FILE,
        help=f"Path to the recorded data file. Defaults to {DEFAULT_FILE}.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"Baud rate. Defaults to {DEFAULT_BAUD}.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=INTER_MESSAGE_DELAY_S,
        help=f"Seconds between messages. Defaults to {INTER_MESSAGE_DELAY_S}.",
    )
    return parser.parse_args()


def load_messages(filepath: str) -> list[bytes]:
    """
    Load and parse a recorded binary data file.

    Messages are delimited by 0x00 bytes — each message starts after a 0x00
    and includes the terminating 0x00.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")

    with open(filepath, "rb") as f:
        raw = f.read()

    zero_positions = [i for i, b in enumerate(raw) if b == 0]
    messages: list[bytes] = []
    for i in range(len(zero_positions) - 1):
        start = zero_positions[i] + 1
        end = zero_positions[i + 1] + 1
        msg = raw[start:end]
        if msg:
            messages.append(msg)

    return messages


def main() -> None:
    args = parse_args()

    log.info(f"Loading data from: {args.file}")
    messages = load_messages(args.file)

    if not messages:
        log.error("No messages found in the data file. Exiting.")
        return

    log.info(f"Parsed {len(messages)} messages.")
    log.info(f"Opening serial port {args.port} at {args.baud} baud.")

    with serial.Serial(args.port, args.baud) as ser:
        log.info("Connected. Starting replay...")
        for idx, msg in enumerate(messages, start=1):
            ser.write(msg)
            ser.flush()
            log.info(f"Sent message {idx}/{len(messages)}: {msg.hex()}")
            time.sleep(args.delay)

    log.info("Replay complete.")


if __name__ == "__main__":
    main()