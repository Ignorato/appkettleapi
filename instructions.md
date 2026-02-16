# AppKettle Control Instructions for AI Agents

This document provides complete instructions for discovering, connecting to, and controlling an AppKettle device on the local network.

**Target Platform**: Debian Linux (Raspberry Pi)

## Critical Requirements for Stable Operation

### 1. Static DHCP Reservation (MANDATORY)
The kettle's IP address **MUST** be set to a static DHCP reservation in your router configuration:
- **Why**: The kettle frequently changes IP addresses when sleeping/waking, causing connection failures
- **How**: Configure your router to assign a fixed IP to the kettle's MAC address
- **MAC Address Discovery**: Use `arp -a | grep <kettle_ip>` after first discovery
- **Example**: MAC `aa:bb:cc:dd:ee:ff` → Static IP `192.168.1.100`

### 2. WiFi Subnet Broadcast (REQUIRED for Raspberry Pi)
On systems with multiple network interfaces (like Raspberry Pi with both Ethernet and WiFi), you **MUST** modify the broadcast address:
- **Location**: Line 58 in `appkettle_mqtt.py`
- **Change From**: `UDP_IP_BCAST = "255.255.255.255"`
- **Change To**: `UDP_IP_BCAST = "<your_wifi_subnet>.255"`
- **Example**: If WiFi IP is `192.168.1.50`, use `UDP_IP_BCAST = "192.168.1.255"`
- **Reason**: Linux kernel only sends broadcast to one interface by default

### 3. Kettle Wake State
The kettle must be in **Ready** state (status `03`) or **Standby** state (status `02`) to accept TCP connections:
- If connection times out repeatedly, physically touch/move the kettle to wake it
- The UDP probe messages will eventually wake it, but physical wake is faster

## Environment Setup

### Prerequisites (Raspberry Pi / Debian)
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv -y

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install pycryptodome "paho-mqtt<2.0"
```

### Initial Configuration Steps

#### Step 1: Identify Your WiFi Interface and Subnet
```bash
# Find WiFi interface (usually wlan0 on Pi)
ip addr show | grep -E "wlan|inet "

# Note your WiFi IP address (e.g., 192.168.1.50/24)
# Calculate broadcast: replace last octet with 255
# Example: 192.168.1.50 → broadcast is 192.168.1.255
```

#### Step 2: Modify Broadcast Address
```bash
# Edit the Python script
nano appkettle_mqtt.py

# Find line 58 (or search for UDP_IP_BCAST)
# Change to your WiFi subnet broadcast
UDP_IP_BCAST = "192.168.1.255"  # WiFi subnet broadcast
```

#### Step 3: First Discovery and MAC Address
```bash
# Run discovery
python appkettle_mqtt.py

# Note the IP address from output
# Check ARP table for MAC address
arp -a | grep <kettle_ip>

# Example output:
# pigarden.dreamweb.local (192.168.1.100) at aa:bb:cc:dd:ee:ff on wlan0
```

#### Step 4: Set Static DHCP Reservation
Configure your router to assign a static IP to the kettle's MAC address. This step is **critical** for reliable operation.

### File Structure
- **Python Script**: `appkettle_mqtt.py` - Main control program
- **Protocol Parser**: `protocol_parser.py` - Message parsing library
- **Requirements**: `requirements.txt` - Python dependencies
- **This File**: `instructions.md` - Complete documentation

## Discovery Protocol

### Command to Discover Kettle
```bash
python appkettle_mqtt.py
```

### Discovery Process
1. **UDP Broadcast**: Sends probe messages to `255.255.255.255:15103` (or WiFi subnet broadcast)
2. **Probe Format**: `Probe#YYYY-MM-DD-HH-MM-SS-N` (e.g., `Probe#2020-05-05-10-47-15-2`)
3. **Kettle Response**: Returns information including:
   - **IP Address**: Extract from UDP source
   - **IMEI**: Format `GD0-xxxxx-xxxx` (e.g., `GD0-12345-abcd`)
   - **Name**: Kettle device name (e.g., `AK_Kettle`)
   - **WiFi SSID**: Network the kettle is connected to
   - **Software Version**: Firmware version (e.g., `0.4.9`)
   - **Device Status**: Current status in hex format

### Expected Discovery Output
```
Discovered kettle with following parameters:
- Name: AK_Kettle
- IP: 192.168.1.100
- IMEI: GD0-12345-abcd
- Wifi SSID: MyWiFiNetwork
- Software version: 0.4.9
```

## Connection Protocol

### Command to Connect
```bash
python appkettle_mqtt.py <IP_ADDRESS> <IMEI>
```

**Example:**
```bash
python appkettle_mqtt.py 192.168.1.100 GD0-12345-abcd
```

### Connection Details
- **Protocol**: TCP
- **Port**: 6002
- **Keepalive**: Sends `KeepConnect` message every 30 seconds
- **Heartbeat**: Kettle sends status messages approximately every 1 second

### Connection Status
- Connected successfully when you see: `Connected succesfully to socket on host <IP>`
- Status messages begin appearing as `K-STAT: aa 0018 03...`

## Control Commands

### Interactive Mode
When connected, press **Ctrl+C** to enter interactive debug mode. Available commands:

| Command | Description | Usage Example |
|---------|-------------|---------------|
| `on` | Turn on kettle at default temperature (100°C) | `on` |
| `on <temp>` | Turn on kettle at specific temperature | `on 80` |
| `off` | Turn off kettle | `off` |
| `wake` | Wake kettle (turn on display, ready state) | `wake` |
| `s` | Show status JSON | `s` |
| `ss` | Show full status dict | `ss` |
| `k` | Send KeepConnect message | `k` |
| `q` | Quit program | `q` |

### Programmatic Command Format

#### Message Structure
All commands follow this format:
```
##<header><length><JSON_payload>&&
```

#### Header Types
- **Plain**: `##00` (recommended for simplicity)
- **Encrypted**: `##80` (requires AES encryption)

#### JSON Payload Format
```json
{
  "app_cmd": "62",
  "imei": "<KETTLE_IMEI>",
  "SubDev": "",
  "data2": "<HEX_COMMAND>"
}
```

#### Hex Command Structure (data2)
```
AA <length> 00 00000000 00 <b090A> <seq> <cmd> 0000 <params> <checksum>
```

**Field Breakdown:**
- `AA`: Header byte (from app)
- `<length>`: 2 bytes - number of bytes following (little-endian hex)
- `00000000`: Padding (4 bytes)
- `00`: Padding (1 byte)
- `<b090A>`: Usually `03B7` or `0000`
- `<seq>`: Sequence number (increments with each command, wraps at 0xFF)
- `<cmd>`: Command byte (see table below)
- `0000`: Padding
- `<params>`: Command-specific parameters
- `<checksum>`: Calculated as `0xFF - (sum(all_bytes_except_first_and_last) % 256)`

### Command Reference Table

| Command | Hex Code | Data2 Example | Description |
|---------|----------|---------------|-------------|
| **ON** | `0x39` | `AA001200000000000003B7{seq}39000000{temp}{kw}0000{checksum}` | Turn on kettle |
| **OFF** | `0x3A` | `AA000D00000000000003B7{seq}3A0000{checksum}` | Turn off kettle |
| **WAKE** | `0x41` | `AA000D00000000000003B7{seq}410000{checksum}` | Wake kettle (display on) |
| **STATUS** | `0x36` | `AA000D00000000000003B7{seq}360000{checksum}` | Request status (optional) |

#### ON Command Parameters
- `{temp}`: Target temperature in Celsius (hex, e.g., `64` = 100°C, `50` = 80°C)
- `{kw}`: Keep warm duration in minutes (hex, e.g., `1E` = 30 minutes, `00` = disabled)

**Example ON Commands:**
- Boil at 100°C: `AA001200000000000003B70139000000640000{checksum}`
- Heat to 80°C with 30min keep warm: `AA001200000000000003B7013900000050001E{checksum}`

### Checksum Calculation
```python
def calc_checksum(hex_string):
    """Calculate checksum for command"""
    msg_bytes = bytes.fromhex(hex_string)
    checksum = 0xFF - (sum(msg_bytes[1:]) % 256)
    return "%0.2x" % checksum
```

## Status Messages

### Status Message Format
Kettle sends heartbeat status messages every ~1 second:
```
K-STAT: aa 0018 03 00000000 00 0000 <seq> 36 0000 c8 <status_data> <checksum>
```

### Status Data Fields (after `c8`)
```
00 <status> <kw_secs> <cur_temp> <tgt_temp> <volume> 0000
```

| Offset | Size | Field | Description | Example |
|--------|------|-------|-------------|---------|
| 0x00 | 1 byte | Padding | Always `00` | `00` |
| 0x01 | 1 byte | Status | Kettle state (see table) | `02` |
| 0x02-03 | 2 bytes | Keep Warm Secs | Countdown in seconds (hex) | `0000` |
| 0x04 | 1 byte | Current Temp | Temperature in °C (hex) | `31` = 49°C |
| 0x05 | 1 byte | Target Temp | Set temperature in °C (hex) | `64` = 100°C |
| 0x06-07 | 2 bytes | Volume | Water volume in ml (hex) | `01b7` = 439ml |
| 0x08-09 | 2 bytes | Padding | Always `0000` | `0000` |

### Status Code Interpretation

| Hex | Decimal | Status | Power | Description |
|-----|---------|--------|-------|-------------|
| `00` | 0 | Not on base | OFF | Kettle removed from base station |
| `01` | 1 | TBD? | OFF | Unknown state |
| `02` | 2 | Standby | OFF | On base, display off, sleeping |
| `03` | 3 | Ready | OFF | On base, display on, ready for command |
| `04` | 4 | Heating | ON | Actively heating water |
| `05` | 5 | Keep Warm | OFF | Maintaining temperature after boiling |

### Example Status Decoding

**Raw Message:**
```
K-STAT: aa 0018 03 00000000 00 0000 fc 36 0000 c8 00 02 0000 31 64 01b7 0000 9b
```

**Decoded:**
- **Status**: `02` = Standby
- **Keep Warm**: `0000` = 0 seconds (disabled)
- **Current Temp**: `31` = 49°C
- **Target Temp**: `64` = 100°C
- **Volume**: `01b7` = 439ml
- **Power**: OFF (standby mode)

**JSON Representation:**
```json
{
  "power": "OFF",
  "status": "Standby",
  "temperature": 49,
  "target_temp": 100,
  "volume": 439,
  "keep_warm_secs": 0
}
```

## MQTT Integration (Optional)

### Setup MQTT Broker
```bash
python appkettle_mqtt.py <IP> <IMEI> --mqtt <BROKER_IP> <BROKER_PORT>
```

**Example:**
```bash
python appkettle_mqtt.py 192.168.1.100 GD0-12345-abcd --mqtt 192.168.1.100 1883
```

### MQTT Topics

#### Command Topics (Subscribe)
- `cmnd/appKettle/power` - Payload: `ON` or `OFF`
- `cmnd/appKettle/keep_warm_onoff` - Payload: `True` or `False`
- `cmnd/appKettle/set_target_temp` - Payload: Temperature in °C (e.g., `80`)

#### Status Topics (Publish)
- `stat/appKettle/STATE` - Full status JSON
- `stat/appKettle/power` - Current power state
- `stat/appKettle/status` - Current status text
- `stat/appKettle/temperature` - Current temperature
- `stat/appKettle/target_temp` - Target temperature
- `stat/appKettle/volume` - Water volume
- `stat/appKettle/keep_warm_secs` - Keep warm countdown
- `stat/appKettle/keep_warm_onoff` - Keep warm enabled/disabled

## Error Handling

### Normal Messages (NOT Errors - Can be Ignored)

**"Length does not match the received packet, ignoring msg"**
- **Status**: Normal, expected behavior
- **Cause**: Initial connection messages from kettle with different packet format
- **Action**: None required - these are safely ignored by the parser
- **Frequency**: Common during connection setup and state transitions
- **Example**: `Length does not match the received packet, ignoring msg: aa000d0100...`

**"Unexpected probe response format"**
- **Status**: Normal when kettle is not responding
- **Cause**: Echo of your own probe message or partial response
- **Action**: Script will retry automatically
- **Example**: `Unexpected probe response format: Probe#2026-02-15-18-33-39`

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| **No kettle discovered** | Kettle not on network or wrong subnet | 1. Verify kettle is powered and on base<br>2. Check broadcast address matches WiFi subnet<br>3. Confirm both devices on same network |
| **Socket error: timed out** (repeated) | Kettle in deep sleep, TCP port not open | 1. Physically touch/move kettle to wake<br>2. Wait 2-3 retry cycles for UDP probes to wake it<br>3. Verify port 6002 accessible |
| **Socket connection broken / no data** | Kettle went to sleep during operation | Script auto-reconnects. If persistent, check:<br>1. Power supply stable<br>2. WiFi signal strength<br>3. Static IP configured |
| **Socket error: [Errno 32] Broken pipe** | Connection closed by kettle | Normal after extended idle. Script reconnects automatically |
| **Changing IP addresses** (192.168.1.100 → 192.168.1.101 → 192.168.1.102) | No static DHCP reservation | **CRITICAL**: Set static DHCP reservation immediately<br>Connection will be unstable without this |
| **Checksum error** | Corrupted network packet | Harmless - ignore message, next heartbeat in ~1 second |
| **Kettle sends back same command** | Command not recognized by kettle | Verify hex command format and checksum calculation |
| **Empty kettle error** | Attempted to boil with insufficient water | Kettle returns ack=`0x00` instead of `0xc8`<br>Add water before retry |

### Connection Recovery Process

When connection is lost, the script automatically:
1. **Attempt 1-3**: Tries to reconnect to TCP socket (60s timeout each)
2. **During retries**: Sends UDP probe messages to wake kettle
3. **Discovery**: If connection fails, runs full discovery to find current IP
4. **Reconnect**: Once kettle responds, establishes new TCP connection

**Manual Recovery** (if auto-recovery fails):
```bash
# Stop the script (Ctrl+C or kill process)
# Physically wake the kettle (touch/move it)
# Restart with known static IP
python appkettle_mqtt.py 192.168.1.100 GD0-12345-abcd
```

### Expected Connection Timeline

1. **Discovery**: 1-5 seconds (first probe usually succeeds with static IP)
2. **Socket Connection**: 5-60 seconds depending on kettle state
   - Ready state (03): Immediate (<5s)
   - Standby state (02): 10-30s (needs wake-up)
   - Deep sleep: 30-60s (multiple probe cycles)
3. **First Status Message**: Within 1 second of connection
4. **Stable Operation**: Heartbeat every ~1 second

## Protocol Notes

### Important Details
- **Encryption**: Commands work in plain text (no encryption required despite AES keys in code)
- **Sequence Numbers**: Increment with each command, wrap at 0xFF (255)
- **Keep Warm Range**: 0-30 minutes (0x00-0x1E)
- **Temperature Range**: Typically 40-100°C (0x28-0x64)
- **Message Terminator**: All messages end with `&&`
- **Message Header**: All messages start with `##`

### Special Sequences
- **aa55 Sequence**: Occasionally appears in messages, adds 1 byte to length. Meaning unclear but handled by parser.

### Timing
- **KeepConnect Frequency**: Every 30 seconds
- **Status Heartbeat**: Every ~1 second from kettle
- **Socket Timeout**: 60 seconds

## Python API for AI Agents (RECOMMENDED)

For AI agents, use the **`kettle_control.py`** Python API instead of the manual console interface. This provides direct Python commands without requiring process management or Ctrl+C interaction.

> **✅ Latest Update (2026-02-16)**: Status reading bug fixed! The `get_status()` method now correctly returns real-time temperature, volume, and status data. Previous version returned zeros/unknowns due to reading non-status messages.

### Quick Start

```python
from kettle_control import KettleController

# Method 1: Auto-discover and connect
kettle = KettleController()
kettle.connect()

# Method 2: Use known IP/IMEI (faster)
kettle = KettleController(host="192.168.1.100", imei="GD0-12345-abcd")
kettle.connect()

# Method 3: Context manager (recommended - auto cleanup)
with KettleController() as kettle:
    kettle.wake()
    kettle.heat(80)
    status = kettle.get_status()
    kettle.turn_off()
```

### API Methods

#### Connection Management

```python
# Discover kettle on network
kettle_info = kettle.discover()
# Returns: {"kettleIP": "192.168.1.100", "imei": "GD0-12345-abcd", ...}

# Connect to kettle
success = kettle.connect(timeout=90)  # Returns True/False

# Disconnect
kettle.disconnect()
```

#### Kettle Control

```python
# Wake up kettle (display on, enter Ready state)
kettle.wake()

# Heat to temperature
kettle.heat(temperature=80, keep_warm=False)  # Heat to 80°C
kettle.heat(temperature=100, keep_warm=True)  # Boil with keep warm

# Turn off
kettle.turn_off()
```

#### Status Monitoring

```python
# Get current status (auto-refreshed)
status = kettle.get_status()
# Returns:
# {
#     "power": "OFF" | "ON",
#     "status": "Ready" | "Standby" | "Heating" | "Keep Warm",
#     "temperature": 49,     # Current temp in °C
#     "target_temp": 100,    # Target temp in °C
#     "volume": 439,         # Water volume in ml
#     "keep_warm_secs": 0    # Keep warm countdown
# }

# Wait for specific status
success = kettle.wait_for_status("Ready", timeout=300)

# Wait for target temperature
success = kettle.wait_for_temperature(80, timeout=300)
```

### AI Agent Example Tasks

#### Task 1: Boil Water
```python
from kettle_control import KettleController

def ai_task_boil_water():
    """Boil water to 100°C and notify when ready"""
    with KettleController() as kettle:
        # Check initial state
        status = kettle.get_status()
        print(f"Initial temp: {status['temperature']}°C")

        # Wake and heat
        kettle.wake()
        kettle.heat(100)

        # Wait for completion
        if kettle.wait_for_temperature(100, timeout=300):
            print("✅ Water is ready!")
            return True
        else:
            print("❌ Timeout - water not ready")
            return False
```

#### Task 2: Heat to Specific Temperature with Monitoring
```python
import time
from kettle_control import KettleController

def ai_task_heat_with_monitoring(target_temp=80):
    """Heat to specific temperature and monitor progress"""
    with KettleController() as kettle:
        kettle.wake()
        kettle.heat(target_temp)

        # Monitor progress
        print(f"Heating to {target_temp}°C...")
        while True:
            status = kettle.get_status()
            current = status['temperature']
            print(f"  Current: {current}°C | Status: {status['status']}")

            # Check if done
            if current >= target_temp or status['status'] in ["Ready", "Keep Warm"]:
                print(f"✅ Reached {current}°C!")
                break

            time.sleep(2)

        return status
```

#### Task 3: Quick Status Check
```python
from kettle_control import KettleController

def ai_task_status_check():
    """Quick status check without heating"""
    with KettleController() as kettle:
        status = kettle.get_status()

        # Return structured data for AI processing
        return {
            "is_heating": status['status'] == "Heating",
            "is_ready": status['power'] == "OFF" and status['temperature'] >= status['target_temp'],
            "current_temp": status['temperature'],
            "water_volume": status['volume'],
            "needs_water": status['volume'] < 200  # Low water warning
        }
```

#### Task 4: Turn Off Kettle
```python
from kettle_control import KettleController

def ai_task_turn_off():
    """Simply turn off the kettle"""
    with KettleController() as kettle:
        kettle.turn_off()
        print("✅ Kettle turned off")
```

### Example Agent Script

A complete example is provided in **`example_agent.py`**:

```bash
# Quick status check
python example_agent.py status

# Boil water (default 100°C)
python example_agent.py boil

# Heat to specific temperature
python example_agent.py heat 80

# Turn off kettle
python example_agent.py off
```

### Advantages of Python API vs Manual Console

| Feature | Manual Console (`appkettle_mqtt.py`) | Python API (`kettle_control.py`) |
|---------|--------------------------------------|----------------------------------|
| **Automation** | Requires Ctrl+C + manual input | Fully automated method calls |
| **AI Integration** | Complex process management | Simple Python imports |
| **Status Access** | Parse console output | Direct dictionary access |
| **Error Handling** | Manual intervention | Programmatic exception handling |
| **Code Complexity** | Process signals, stdin/stdout | Clean function calls |
| **Recommended For** | Manual testing, debugging | AI agents, automation scripts |

### Integration Pattern for AI Agents

```python
from kettle_control import KettleController

class KettleAIAgent:
    """AI Agent for automated kettle control"""

    def __init__(self):
        self.kettle = None

    def initialize(self):
        """Connect to kettle at startup"""
        self.kettle = KettleController()
        return self.kettle.connect()

    def execute_task(self, task_name, **params):
        """Execute a named task"""
        tasks = {
            "boil": lambda: self._boil_water(),
            "heat": lambda: self._heat_to_temp(params.get("temp", 80)),
            "status": lambda: self._get_status(),
            "off": lambda: self._turn_off()
        }

        if task_name in tasks:
            return tasks[task_name]()
        else:
            return {"error": f"Unknown task: {task_name}"}

    def _boil_water(self):
        self.kettle.wake()
        self.kettle.heat(100)
        success = self.kettle.wait_for_temperature(100, timeout=300)
        return {"success": success, "action": "boil"}

    def _heat_to_temp(self, temp):
        self.kettle.wake()
        self.kettle.heat(temp)
        success = self.kettle.wait_for_temperature(temp, timeout=300)
        return {"success": success, "action": "heat", "temp": temp}

    def _get_status(self):
        return self.kettle.get_status()

    def _turn_off(self):
        self.kettle.turn_off()
        return {"success": True, "action": "off"}

    def cleanup(self):
        """Disconnect at shutdown"""
        if self.kettle:
            self.kettle.disconnect()

# Usage
agent = KettleAIAgent()
agent.initialize()
result = agent.execute_task("heat", temp=80)
print(result)
agent.cleanup()
```

## Security Considerations

### AES Encryption Keys (Optional)
- **Key**: `ay3$&dw*ndAD!9)<`
- **IV**: `7e3*WwI(@Dczxcue`
- **Mode**: AES-CBC
- **Note**: Encryption is optional; plain text commands work

### Network Security
- Recommended: Block kettle's internet access via firewall
- All communication should be local network only
- No authentication required for local control

## Raspberry Pi Specific Considerations

### Network Interface Configuration

#### Identify WiFi Interface
```bash
# List all network interfaces
ip link show

# Check WiFi interface details (usually wlan0)
ip addr show wlan0

# Example output:
# wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP>
#   inet 192.168.1.50/24 brd 192.168.1.255 scope global dynamic wlan0
```

#### Determine Broadcast Address
```bash
# Method 1: From ip addr output
ip addr show wlan0 | grep "inet " | awk '{print $4}'
# Output: 192.168.1.255

# Method 2: Calculate from IP/netmask
# If IP is 192.168.1.50/24, broadcast is 192.168.1.255
# If IP is 192.168.1.100/24, broadcast is 192.168.1.255
```

### Running as System Service (Optional)

Create a systemd service for automatic startup:

```bash
# Create service file
sudo nano /etc/systemd/system/appkettle.service
```

```ini
[Unit]
Description=AppKettle Control Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/appkettleapi
ExecStart=/home/pi/appkettleapi/venv/bin/python appkettle_mqtt.py 192.168.1.100 GD0-12345-abcd
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable appkettle.service
sudo systemctl start appkettle.service

# Check status
sudo systemctl status appkettle.service

# View logs
sudo journalctl -u appkettle.service -f
```

### Performance Notes for Raspberry Pi

- **CPU Usage**: Minimal (<5% on Pi 3B+/4)
- **Memory**: ~25-30MB for Python process
- **Network**: Negligible bandwidth (<1 Kbps for heartbeats)
- **Storage**: ~15MB for code + venv
- **Recommended**: Pi 3 Model B+ or newer
- **Works On**: Pi Zero W, Pi 2, Pi 3, Pi 4, Pi 5

### WiFi Power Management (Important)

Disable WiFi power saving to prevent connection drops:

```bash
# Check current power management status
iwconfig wlan0 | grep "Power Management"

# Disable power management temporarily
sudo iwconfig wlan0 power off

# Make permanent (add to /etc/rc.local before 'exit 0'):
/sbin/iwconfig wlan0 power off
```

## Troubleshooting Commands

### Network Diagnostics
```bash
# Check WiFi connection
iwconfig wlan0

# Verify IP and broadcast address
ip addr show wlan0

# Test connectivity to kettle
ping -c 4 192.168.1.100

# Check if kettle port is open (requires netcat)
nc -zv 192.168.1.100 6002

# View ARP table (find MAC address)
arp -a | grep 10.77.77

# Monitor network traffic from kettle
sudo tcpdump -i wlan0 host 192.168.1.100 -A

# Enable keepalive message printing
# Set DEBUG_PRINT_KEEP_CONNECT = True in appkettle_mqtt.py

# Test with specific broadcast address
# Edit UDP_IP_BCAST in appkettle_mqtt.py to your WiFi subnet
# Example: UDP_IP_BCAST = "192.168.1.255"

# Check network interfaces
ifconfig  # macOS/Linux
ipconfig  # Windows

# Test UDP broadcast manually
python3 -c "
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.sendto(b'Probe#2024-01-01-12-00-00-1', ('255.255.255.255', 15103))
"
```

## Quick Reference Card

### Essential Commands
```bash
# Discover
python appkettle_mqtt.py

# Connect
python appkettle_mqtt.py 192.168.1.100 GD0-12345-abcd

# Interactive commands (after Ctrl+C)
on       # Turn on at 100°C
on 80    # Turn on at 80°C
off      # Turn off
wake     # Wake display
s        # Show status
q        # Quit
```

### Key Status Values
- Status `02` = Standby (sleeping)
- Status `03` = Ready (awake)
- Status `04` = Heating
- Temp in hex: `0x64` = 100°C, `0x50` = 80°C
- Volume in hex: `0x01b7` = 439ml

### Critical Files
- `appkettle_mqtt.py` - Main control script
- `protocol_parser.py` - Message parsing
- `requirements.txt` - Python dependencies

## AI Agent Quick Reference

### Pre-Flight Checklist
Before running any kettle operations, verify:

1. ✅ **Static DHCP configured** for kettle MAC address
2. ✅ **Broadcast address set** to WiFi subnet in `appkettle_mqtt.py` line 58
3. ✅ **WiFi power management disabled** on Raspberry Pi
4. ✅ **Virtual environment created** with dependencies installed
5. ✅ **Kettle on base station** and powered

### Operational States Reference

| Status Code | Status Name | Power | Can Connect? | Behavior |
|-------------|-------------|-------|--------------|----------|
| `00` | Not on base | OFF | ❌ No | Kettle removed from base |
| `02` | Standby | OFF | ⚠️ Slow (30-60s) | Sleeping, needs wake-up |
| `03` | Ready | OFF | ✅ Yes (<5s) | Awake, ready to accept commands |
| `04` | Heating | ON | ✅ Yes | Actively boiling |
| `05` | Keep Warm | OFF | ✅ Yes | Maintaining temp after boil |

### Critical Success Patterns

**Pattern 1: First-Time Setup**
```bash
1. Discover kettle → Note IP and MAC
2. Configure static DHCP in router
3. Modify UDP_IP_BCAST in appkettle_mqtt.py
4. Run discovery again → Should find at static IP immediately
5. Connect → Should succeed within 5-60 seconds
```

**Pattern 2: Reliable Connection**
```bash
# Always use static IP with IMEI
python appkettle_mqtt.py 192.168.1.100 GD0-12345-abcd

# Success indicators:
- "Discovered kettle with following parameters:" (1-5s)
- "Connected succesfully to socket on host 192.168.1.100" (5-60s)
- "K-STAT: aa 0018 03..." (status messages flowing)
```

**Pattern 3: Status Monitoring**
```bash
# Filter status messages only (ignore length errors)
tail -f output.log | grep "K-STAT:"

# Decode latest status
tail -1 output.log | grep "K-STAT:" | awk '{print $11, $12, $13}'
# Output: 00 02 0000 → Status=02 (Standby), temp=0°C, keep_warm=0s
```

### Expected Message Flow

**Successful Connection:**
```
1. Sent broadcast messages... (1-3 attempts)
2. Discovered kettle with following parameters: IP: 192.168.1.100
3. Attempting to connect to socket...
4. [May see "Length does not match" warnings - NORMAL]
5. Connected succesfully to socket on host 192.168.1.100
6. K-STAT: aa 0018 03... (heartbeat every ~1s)
```

**Failed Connection (needs intervention):**
```
1. Sent broadcast messages... (3 attempts)
2. Socket error: timed out | 3 attempts remaining
3. [Repeats 3 times]
4. Socket timeout
→ ACTION REQUIRED: Physically wake kettle or wait longer
```

### Parsing Status Messages for AI Agents

**Extract Temperature:**
```python
# From: K-STAT: aa 0018 03 00000000 00 0000 ef 36 0000 c8 00 03 0000 24 64 0316 0000 53
# Position 13 (0-indexed) = temp in hex
import re
match = re.search(r'K-STAT: ([\da-f ]+)', line)
if match:
    hex_values = match.group(1).split()
    temp_hex = hex_values[13]  # e.g., '24'
    temp_celsius = int(temp_hex, 16)  # e.g., 36°C
```

**Extract Status:**
```python
# Position 11 = status code
status_hex = hex_values[11]  # e.g., '03'
status_code = int(status_hex, 16)
status_map = {0: "Not on base", 2: "Standby", 3: "Ready", 4: "Heating", 5: "Keep Warm"}
status = status_map.get(status_code, "Unknown")
```

**Extract Volume:**
```python
# Positions 14-15 = volume in ml (big-endian)
volume_hex = hex_values[14] + hex_values[15]  # e.g., '0316'
volume_ml = int(volume_hex, 16)  # e.g., 790ml
```

### Common AI Agent Pitfalls

❌ **DON'T**: Use `255.255.255.255` broadcast on multi-interface systems
✅ **DO**: Calculate and use WiFi subnet broadcast

❌ **DON'T**: Assume kettle IP is stable without static DHCP
✅ **DO**: Always configure static DHCP reservation first

❌ **DON'T**: Treat "Length does not match" as errors
✅ **DO**: Ignore these - they're normal during connection setup

❌ **DON'T**: Give up after first connection timeout
✅ **DO**: Wait 2-3 retry cycles (kettle may be waking up)

❌ **DON'T**: Run script without checking WiFi status first
✅ **DO**: Verify `ip addr show wlan0` shows active connection

❌ **DON'T**: Parse status from discovery "Device Status" field
✅ **DO**: Parse from `K-STAT:` messages after connection

### Diagnostic Decision Tree

```
Connection failing?
├─ No kettle discovered
│  ├─ Check: Is kettle powered and on base? → Physical check
│  ├─ Check: Is WiFi interface up? → ip addr show wlan0
│  └─ Check: Broadcast address correct? → Verify subnet matches
│
├─ Discovered but connection timeout
│  ├─ Is status = 02 (Standby)? → Wait longer or physically wake
│  ├─ Is status = 03 (Ready)? → Check port 6002 open: nc -zv <ip> 6002
│  └─ Is IP changing? → Static DHCP not configured!
│
└─ Connected but drops frequently
   ├─ Check: WiFi power management disabled? → iwconfig wlan0
   ├─ Check: WiFi signal strength? → iwconfig wlan0 | grep Signal
   └─ Check: Static IP configured? → arp -a | grep <kettle_ip>
```

### Success Metrics

**Good Connection:**
- Discovery: <5 seconds
- Connection: <30 seconds
- Status messages: Every 1-2 seconds
- No reconnections for hours
- IP address: Never changes

**Poor Connection:**
- Discovery: Multiple retries
- Connection: >60 seconds or timeout
- Frequent "Socket connection broken"
- IP address: Changes after disconnect
- → **FIX**: Implement static DHCP immediately

### Integration Example (Pseudocode)

```python
# AI Agent Control Loop
def control_kettle():
    # 1. Verify setup
    if not verify_static_dhcp():
        return error("Static DHCP not configured")

    # 2. Start connection
    process = start_process("python appkettle_mqtt.py 192.168.1.100 GD0-12345-abcd")

    # 3. Wait for connection (with timeout)
    if not wait_for_connection(process, timeout=90):
        return error("Connection timeout - check kettle state")

    # 4. Monitor status
    while True:
        line = read_line(process)

        # Ignore normal warnings
        if "Length does not match" in line:
            continue

        # Parse status
        if "K-STAT:" in line:
            status = parse_status(line)
            handle_status_update(status)

        # Detect reconnection
        if "Socket error" in line:
            log("Connection lost, auto-recovery in progress")
            continue

    # 5. Send commands (interactive mode)
    send_signal(process, SIGINT)
    send_input(process, "on 80\n")  # Boil at 80°C
```

---

## Change Log

**Version 2.1 (2026-02-16)**
- Fixed status reading bug in Python API (`get_status()` now returns accurate data)
- Fixed heating command bug (removed redundant wake() call)
- Added comprehensive documentation for AI agents

**Version 2.0 (2026-02-15)**
- Added Python API (`kettle_control.py`) for AI agent automation
- Added example automation scripts (`example_agent.py`)
- Complete protocol documentation

---

*Document version: 2.1*
*Last Updated: 2026-02-16*
*Compatible with: AppKettle firmware 0.4.9*
*Target Platform: Debian Linux (Raspberry Pi)*
*Tested on: Raspberry Pi 4B, Pi 3B+, macOS (development)*
