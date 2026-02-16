#!/usr/bin/env python3
"""
Simple Python API for controlling AppKettle programmatically.

Usage:
    from kettle_control import KettleController

    # Auto-discover and connect
    kettle = KettleController()
    kettle.connect()

    # Or connect with known parameters
    kettle = KettleController(host="10.77.77.216", imei="GD0-12900-1f7d")
    kettle.connect()

    # Control the kettle
    kettle.wake()
    kettle.heat(80)  # Heat to 80°C
    status = kettle.get_status()
    print(f"Temperature: {status['temperature']}°C")
    kettle.turn_off()

    # Clean up
    kettle.disconnect()
"""

import time
import socket
import select
from appkettle_mqtt import AppKettle, KettleSocket, KEEP_WARM_MINS


class KettleController:
    """High-level controller for AppKettle with simple Python API"""

    def __init__(self, host=None, imei=None, port=6002):
        """
        Initialize kettle controller.

        Args:
            host: Kettle IP address (if None, will auto-discover)
            imei: Kettle IMEI (if None, will auto-discover)
            port: Kettle port (default 6002)
        """
        self.host = host
        self.imei = imei
        self.port = port
        self.kettle_socket = None
        self.kettle = None
        self.connected = False
        self._last_keepalive = time.time()

    def discover(self):
        """
        Discover kettle on network using UDP broadcast.

        Returns:
            dict: Kettle information including IP, IMEI, name, etc.
            None: If no kettle found
        """
        print("Discovering kettle on network...")
        temp_socket = KettleSocket(imei="")
        kettle_info = temp_socket.kettle_probe()

        if kettle_info:
            self.host = kettle_info.get("kettleIP")
            self.imei = kettle_info.get("imei")
            print(f"Discovered kettle: {kettle_info.get('AP_ssid')} at {self.host}")
            return kettle_info
        else:
            print("No kettle discovered")
            return None

    def connect(self, timeout=90):
        """
        Connect to the kettle.

        Args:
            timeout: Connection timeout in seconds (default 90)

        Returns:
            bool: True if connected successfully, False otherwise
        """
        # Auto-discover if host/imei not provided
        if not self.host or not self.imei:
            if not self.discover():
                return False

        print(f"Connecting to kettle at {self.host}:{self.port}...")

        # Create kettle objects
        self.kettle_socket = KettleSocket(imei=self.imei)
        self.kettle = AppKettle(self.kettle_socket)

        # Connect
        self.kettle_socket.connect((self.host, self.port))

        if self.kettle_socket.connected:
            self.connected = True
            print(f"Connected successfully to {self.host}")

            # Read initial status (longer timeout for first read)
            self._update_status(timeout=10)
            return True
        else:
            print("Failed to connect")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the kettle."""
        if self.kettle_socket:
            self.kettle_socket.close()
        self.connected = False
        print("Disconnected from kettle")

    def _update_status(self, timeout=5):
        """
        Internal method to read and update kettle status.

        Keeps reading messages until we get a valid status update (with actual data)
        or timeout expires. The kettle sends various message types, but only messages
        with "data3" contain actual status information.

        Args:
            timeout: How long to wait for status update (seconds)
        """
        if not self.connected or not self.kettle_socket:
            return

        start_time = time.time()
        messages_read = 0

        while time.time() - start_time < timeout:
            # Send keepalive if needed
            if time.time() - self._last_keepalive > 30:
                self.kettle_socket.keep_connect()
                self._last_keepalive = time.time()

            # Check for incoming data
            try:
                infds, _, _ = select.select([self.kettle_socket.sock], [], [], 0.5)
                if infds:
                    msg = self.kettle_socket.receive()
                    if msg:
                        self.kettle.update_status(msg)
                        messages_read += 1

                        # Check if we got a real status update (not "unk" and has valid data)
                        # Status messages contain data3 and update these fields
                        if (self.kettle.stat.get("status") != "unk" and
                            self.kettle.stat.get("temperature", 0) >= 0):
                            # Got valid status with actual data
                            return

                        # Also accept if we've read multiple messages (likely got status by now)
                        if messages_read >= 3:
                            return
            except Exception as e:
                print(f"Error reading status: {e}")
                break

        # Warn if we timed out without getting valid status
        if self.kettle.stat.get("status") == "unk":
            print("Warning: Timed out waiting for status update from kettle")

    def get_status(self, refresh=True):
        """
        Get current kettle status.

        Args:
            refresh: If True, wait for fresh status from kettle (default True)

        Returns:
            dict: Status dictionary with keys:
                - power: "ON" or "OFF"
                - status: Status string (e.g., "Ready", "Standby", "Heating")
                - temperature: Current temperature in °C
                - target_temp: Target temperature in °C
                - volume: Water volume in ml
                - keep_warm_secs: Keep warm countdown in seconds
        """
        if refresh:
            self._update_status()

        return {
            "power": self.kettle.stat.get("power", "UNKNOWN"),
            "status": self.kettle.stat.get("status", "UNKNOWN"),
            "temperature": self.kettle.stat.get("temperature", 0),
            "target_temp": self.kettle.stat.get("target_temp", 0),
            "volume": self.kettle.stat.get("volume", 0),
            "keep_warm_secs": self.kettle.stat.get("keep_warm_secs", 0),
        }

    def wake(self):
        """
        Wake up the kettle (turn on display, enter Ready state).

        Returns:
            bool: True if command sent successfully
        """
        if not self.connected:
            print("Not connected to kettle")
            return False

        print("Waking kettle...")
        result = self.kettle.wake()
        time.sleep(0.5)  # Give kettle time to process
        self._update_status()
        return result is None  # wake() returns None on success

    def heat(self, temperature=100, keep_warm=False):
        """
        Heat water to specified temperature.

        Args:
            temperature: Target temperature in °C (default 100)
            keep_warm: Enable keep warm mode (default False)

        Returns:
            bool: True if command sent successfully
        """
        if not self.connected:
            print("Not connected to kettle")
            return False

        # Set keep warm preference
        self.kettle.stat["keep_warm_onoff"] = keep_warm

        # Wake if not ready
        status = self.get_status(refresh=True)
        if status["status"] != "Ready":
            print("Kettle not ready, waking up...")
            self.wake()
            time.sleep(1)

        print(f"Heating to {temperature}°C (keep warm: {keep_warm})...")
        result = self.kettle.turn_on(temp=temperature)
        time.sleep(0.5)
        self._update_status()
        return result is None  # turn_on() returns None on success

    def turn_off(self):
        """
        Turn off the kettle.

        Returns:
            bool: True if command sent successfully
        """
        if not self.connected:
            print("Not connected to kettle")
            return False

        print("Turning off kettle...")
        result = self.kettle.turn_off()
        time.sleep(0.5)
        self._update_status()
        return result is None  # turn_off() returns None on success

    def wait_for_status(self, target_status, timeout=300):
        """
        Wait for kettle to reach a specific status.

        Args:
            target_status: Status to wait for (e.g., "Ready", "Heating", "Standby")
            timeout: Maximum time to wait in seconds (default 300 = 5 minutes)

        Returns:
            bool: True if target status reached, False if timeout
        """
        print(f"Waiting for status '{target_status}'...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_status(refresh=True)
            if status["status"] == target_status:
                print(f"Status reached: {target_status}")
                return True
            time.sleep(1)

        print(f"Timeout waiting for status '{target_status}'")
        return False

    def wait_for_temperature(self, target_temp, timeout=300):
        """
        Wait for kettle to reach target temperature.

        Args:
            target_temp: Temperature to wait for in °C
            timeout: Maximum time to wait in seconds (default 300 = 5 minutes)

        Returns:
            bool: True if temperature reached, False if timeout
        """
        print(f"Waiting for temperature {target_temp}°C...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_status(refresh=True)
            if status["temperature"] >= target_temp:
                print(f"Temperature reached: {status['temperature']}°C")
                return True
            time.sleep(1)

        print(f"Timeout waiting for temperature {target_temp}°C")
        return False

    def __enter__(self):
        """Context manager entry."""
        if not self.connected:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False


# Example usage
if __name__ == "__main__":
    # Example 1: Auto-discover and control
    print("=== Example 1: Auto-discover ===")
    kettle = KettleController()
    if kettle.connect():
        status = kettle.get_status()
        print(f"Status: {status}")

        kettle.wake()
        time.sleep(2)

        kettle.heat(80, keep_warm=False)
        time.sleep(5)

        status = kettle.get_status()
        print(f"Status after heating: {status}")

        kettle.turn_off()
        kettle.disconnect()

    print("\n=== Example 2: Context manager ===")
    # Example 2: Using context manager with known parameters
    with KettleController(host="10.77.77.216", imei="GD0-12900-1f7d") as kettle:
        print(f"Current status: {kettle.get_status()}")
        kettle.wake()
        kettle.heat(90)
        time.sleep(5)
        print(f"Status: {kettle.get_status()}")
        kettle.turn_off()
