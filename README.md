# appkettleapi
Python implementation of an API for appkettle

Control your AppKettle smart kettle over local network without cloud dependencies. Includes a clean Python API designed for AI agent automation.

## Quick Start

### For AI Agents (Recommended)

```python
from kettle_control import KettleController

# Simple automation
with KettleController() as kettle:
    kettle.wake()
    kettle.heat(80)  # Heat to 80°C
    status = kettle.get_status()
    print(f"Temperature: {status['temperature']}°C")
    kettle.turn_off()
```

Or use the example script:
```bash
python example_agent.py status  # Check status
python example_agent.py heat 80  # Heat to 80°C
python example_agent.py off      # Turn off
```

### For Manual Testing

```bash
# Discover kettle
python appkettle_mqtt.py

# Connect and use interactive mode (Ctrl+C for commands)
python appkettle_mqtt.py <IP> <IMEI>
```

## Features

- ✅ **Local network control** - No cloud dependencies
- ✅ **Python API** - Clean interface for automation and AI agents
- ✅ **Auto-discovery** - Finds kettle automatically via UDP broadcast
- ✅ **Real-time status** - Temperature, volume, power state monitoring
- ✅ **Full control** - Heat to specific temperatures, keep warm mode
- ✅ **MQTT integration** - Optional MQTT broker support for home automation
- ✅ **Raspberry Pi ready** - Optimized for Debian/Raspberry Pi

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install pycryptodome "paho-mqtt<2.0"
```

## Documentation

- **[instructions.md](instructions.md)** - Complete protocol documentation and AI agent guide
- **[developer_notes.md](developer_notes.md)** - Technical details for developers
- **[example_agent.py](example_agent.py)** - Example automation scripts

## Files

| File | Purpose |
|------|---------|
| `kettle_control.py` | High-level Python API for automation |
| `appkettle_mqtt.py` | Low-level protocol implementation |
| `protocol_parser.py` | Message parsing and encoding |
| `example_agent.py` | Example automation scripts |
| `instructions.md` | Complete documentation |
| `developer_notes.md` | Technical notes for developers |

## Recent Updates (2026-02-16)

- ✅ **Fixed heating bug** - Removed double wake() call that prevented heating
- ✅ **Fixed status reading** - get_status() now returns accurate real-time data
- ✅ **Added Python API** - New KettleController class for easy automation
- ✅ **Added documentation** - Comprehensive guides for AI agents and developers

## Protocol Details

See [protocol_parser.py](protocol_parser.py) for packet structure details. The protocol implements:
- ON/OFF commands with temperature control (40-100°C)
- Keep warm mode (0-30 minutes)
- Real-time status monitoring (temperature, volume, power state)
- UDP discovery protocol
- Optional AES encryption (plain text also works)

## Network Configuration

**Important for Raspberry Pi**: Edit line 58 in `appkettle_mqtt.py` to set the broadcast address to your WiFi subnet:
```python
UDP_IP_BCAST = "192.168.1.255"  # Change to match your network
```

By default, Linux sends broadcasts to only one interface. If you have multiple network interfaces (Ethernet + WiFi), you must specify the WiFi subnet broadcast address.

## Related Projects

- https://github.com/filcole/AppKettle - Cloud API details

This implementation does **not** use the cloud API - it communicates directly with the kettle on the local network. It's recommended to block the kettle's internet access via firewall for security.

## License

See code for licensing details. This is an unofficial reverse-engineered implementation.

---

*For complete usage instructions, see [instructions.md](instructions.md)*
*For technical details and debugging, see [developer_notes.md](developer_notes.md)*
