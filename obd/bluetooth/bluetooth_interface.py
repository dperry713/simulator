"""
Bluetooth (BLE) Interface for OBD Communication using Bleak
"""
import asyncio
from bleak import BleakScanner, BleakClient


class BluetoothInterface:
    def __init__(self):
        self.client = None
        self.device = None
        self.is_connected = False

    async def discover_devices(self):
        print("Scanning for BLE devices...")
        devices = await BleakScanner.discover()
        # Return list of (address, name)
        return [(d.address, d.name or d.address) for d in devices]

    async def connect(self, address):
        self.client = BleakClient(address)
        await self.client.connect()
        self.is_connected = self.client.is_connected
        print(f"Connected to {address}")

    async def send(self, data: bytes, char_uuid: str):
        # Write data to BLE characteristic (char_uuid)
        if self.client and self.is_connected:
            await self.client.write_gatt_char(char_uuid, data)

    async def receive(self, char_uuid: str, timeout=5.0):
        # Read data from BLE characteristic (char_uuid)
        if self.client and self.is_connected:
            return await self.client.read_gatt_char(char_uuid)
        return b''

    async def close(self):
        if self.client and self.is_connected:
            await self.client.disconnect()
            self.client = None
            self.is_connected = False
