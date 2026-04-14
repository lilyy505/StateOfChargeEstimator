import serial
import time
from socat_manager import get_ports

sim_port, _ = get_ports()
ser = serial.Serial(sim_port, 230400)

print(f"[new_simulator] Connected to simulator port: {sim_port}")

filename = "2026-02-07 RFS Roadtest + Coastdown/recorded_data_2026-02-07_11-21-14.txt"
#filename = "recorded_data_2025-11-21_14-52-45.txt"

# so we're reading the recorded data file in binary mode
with open(filename, "rb") as f:
    raw_content = f.read()

data_bytes = raw_content

# split the data by 0x00 bytes, start after a 00 and include the 0x00 at the end
zero_positions = [i for i, b in enumerate(data_bytes) if b == 0]
messages = []
for i in range(len(zero_positions) - 1):
    start_idx = zero_positions[i] + 1
    end_idx = zero_positions[i + 1] + 1
    message = data_bytes[start_idx:end_idx]
    if message:
        messages.append(message)

print(f"Parsed {len(messages)} messages from recorded_data-original")

if not messages:
    print("No messages to send.")
else:
    for idx, current_message in enumerate(messages, start=1):
        ser.write(current_message)
        ser.flush()
        print(f"Sent message {idx}: {current_message.hex()}")
        time.sleep(0.5)
    print("Finished sending all messages.")
