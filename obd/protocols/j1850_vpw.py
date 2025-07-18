"""
SAE J1850 VPW Protocol Handler (Advanced, Demo Version)
"""
import time


class J1850VPW:
    SOF = b'\x00'
    EOF = b'\xFF'

    def __init__(self, bitrate=10416):
        self.bitrate = bitrate  # Bits per second

    def calculate_crc(self, data: bytes) -> int:
        """Calculate SAE J1850 VPW CRC (XOR of all data bytes, inverted)."""
        crc = 0xFF
        for byte in data:
            crc ^= byte
        return crc ^ 0xFF

    def encode(self, data: bytes) -> bytes:
        """Frame a message: SOF | DATA | CRC | EOF."""
        crc = self.calculate_crc(data)
        frame = self.SOF + data + bytes([crc]) + self.EOF
        return frame

    def decode(self, frame: bytes) -> bytes:
        """Extract and verify frame."""
        if not (frame.startswith(self.SOF) and frame.endswith(self.EOF)):
            raise ValueError("Invalid frame boundaries")
        data = frame[1:-2]
        crc = frame[-2]
        if crc != self.calculate_crc(data):
            raise ValueError("CRC mismatch")
        return data

    def send(self, send_func, data: bytes):
        frame = self.encode(data)
        send_func(frame)

    def receive(self, recv_func, timeout=1.0) -> bytes:
        start = time.time()
        buffer = b''
        while time.time() - start < timeout:
            chunk = recv_func(1)
            if chunk:
                buffer += chunk
                # Try frame parsing
                if buffer.startswith(self.SOF) and buffer.endswith(self.EOF) and len(buffer) >= 4:
                    try:
                        return self.decode(buffer)
                    except Exception:
                        pass
            else:
                time.sleep(0.01)
        return b''
