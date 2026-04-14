from enum import Enum
from datetime import datetime
import logging
from typing import Any, Never

log = logging.getLogger(__name__)


class RawMessage:
    def __init__(self, can_id: int, data: bytes, timestamp: datetime):
        self.can_id = can_id
        self.data = data
        self.timestamp = timestamp  # Timestamps are datetime objects in UTC
        self.data_len = len(data)
        self.reserved = 2 if self.can_id >= 0x800 else 0
        self.passed_checksum = True

    @classmethod
    def from_array(cls, can_id: int, data: bytearray, timestamp: datetime):
        return cls(can_id, data, timestamp)

    @classmethod
    def from_bytes(cls, data: bytes, timestamp: datetime):
        if len(data) < 3:
            log.error(f"CAN Message Build Failure: too short {data}")
            return cls(0, bytearray(), timestamp)
        can_id = data[0] | (data[1] & 0x0F) << 8
        data_len = (data[1] & 0xF0) >> 4
        if len(data) != 3 + data_len:
            log.error(f"CAN Message Build Failure: incorrect length {data} len={data_len}")
            return cls(0, bytearray(), timestamp)
        if data_len > 8:
            log.error(f"CAN Message Build Failure: too long {data} len={data_len}")
            return cls(0, bytearray(), timestamp)
        data_without_start_or_checksum = bytearray(data[2:-1])
        x = cls(can_id, data_without_start_or_checksum, timestamp)
        # verify checksum
        sum = 0
        for b in data:
            sum += b
        if sum % 256 != 0:
            log.error(f"CAN Message Build Failure: checksum failed {data}")
            x.passed_checksum = False
        return x

    def to_bytes(self):
        return bytes()
        # TODO: implement (needed for sending data back into ingestors)

    def __str__(self):
        # return f"[{self.timestamp.astimezone().strftime('%m/%d %H:%M:%S.%f')[:-3]}] id={hex(self.can_id)} : 0x{self.data.hex()}"
        return f"RawCANMessage(id={hex(self.can_id)}, {self.data})"


# A message that has been named and interpreted
class Message:
    def __init__(self, can_id: int | Enum, data: Any | dict[str,Any], timestamp: datetime, telem_name: str | None = None):
        if isinstance(can_id, Enum):
            self.can_id: int = can_id.value
        else: 
            self.can_id: int = can_id
        
        if not isinstance(data, dict):
            self.data: dict[str, Any] = {"value": data}
        else:
            self.data = data
        self.telem_name = telem_name
        self.timestamp = timestamp  # Timestamps are datetime objects in UTC

    def __str__(self):
        # return f"[{self.timestamp.astimezone().strftime('%m/%d %H:%M:%S.%f')[:-3]}] id={hex(self.can_id)} name='{self.telem_name}' : {self.data}"
        #return f"CANMessage(id={hex(self.can_id)}, name='{self.telem_name}', {self.data})"
        ts = self.timestamp.astimezone().strftime('%m/%d %H:%M:%S.%f')[:-3]  # trim to milliseconds
        return f"CANMessage(time={ts}, id={hex(self.can_id)}, name='{self.telem_name}', data={self.data})"
