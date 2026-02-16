# Developer Notes - AppKettle Control Project

## Project Overview

This project provides Python-based control for the **AppKettle** (a WiFi-enabled smart kettle) over the local network. It reverse-engineers the proprietary protocol used by the AppKettle mobile app to enable programmatic control without cloud dependencies.

**Primary Use Case**: AI agent automation for kettle control (heating water to specific temperatures, monitoring status, etc.)

**Target Platform**: Debian Linux (Raspberry Pi), but also works on macOS for development/testing

## Project History & Context

### Original Implementation
- Started as a packet capture reverse-engineering project
- Protocol decoded from Android app traffic using tcpdump
- Initial version had manual console interface (Ctrl+C debugging commands)
- Used MQTT for integration with home automation systems

### Recent Improvements (2026-02-16)
1. **Fixed critical bug**: Double `wake()` call causing sequence number issues that prevented heating
   - Issue: MQTT callback called `wake()`, then `turn_on()` also called `wake()` internally
   - Fix: Removed redundant wake from `turn_on()` method
   - Location: `appkettle_mqtt.py` line 91-95

2. **Added Python API**: Created `kettle_control.py` for direct programmatic access
   - No longer requires process management or Ctrl+C interaction
   - Clean API designed specifically for AI agents
   - Context manager support for automatic cleanup

3. **Fixed status reading bug**: `get_status()` returning zeros/unknowns
   - Issue: `_update_status()` returned after first message, which might not contain status data
   - Fix: Keep reading until we get a message with actual data3 status information
   - Location: `kettle_control.py` line 117-165
   - Now reads multiple messages and validates status before returning

## File Structure & Purposes

### Core Files

| File | Purpose | Used By |
|------|---------|---------|
| **`appkettle_mqtt.py`** | Main protocol implementation | All control methods |
| **`protocol_parser.py`** | Message parsing/encoding | appkettle_mqtt.py |
| **`kettle_control.py`** | High-level Python API | AI agents, automation |
| **`example_agent.py`** | Example automation scripts | Reference for AI agents |
| **`instructions.md`** | Complete protocol documentation | AI agents (primary reference) |
| **`developer_notes.md`** | This file - technical notes | Future developers/AI agents |
| **`README.md`** | Original project README | General users |
| **`requirements.txt`** | Python dependencies | Installation |

### Dependencies

```python
pycryptodome    # AES encryption (though not required - plain text works)
paho-mqtt<2.0   # MQTT client (only if using MQTT integration)
```

## Architecture

### Protocol Stack

```
Application Layer (AI Agent)
    ↓
Python API (kettle_control.py)
    ↓
Protocol Layer (appkettle_mqtt.py)
    ↓
Socket Layer (KettleSocket class)
    ↓
TCP/IP (port 6002) + UDP Discovery (port 15103)
    ↓
AppKettle Device
```

### Key Classes

#### `AppKettle` (appkettle_mqtt.py)
- Represents the physical kettle state
- Maintains status dictionary with temperature, volume, power, etc.
- Provides control methods: `turn_on()`, `turn_off()`, `wake()`
- Handles sequence number tracking (important!)

#### `KettleSocket` (appkettle_mqtt.py)
- Manages TCP connection to kettle
- Handles message framing (##header...&&)
- Optional AES encryption/decryption (not required)
- UDP discovery protocol

#### `KettleController` (kettle_control.py)
- High-level API wrapper
- Auto-discovery, connection management
- Simplified methods for AI agents
- Context manager support

## Critical Technical Details

### 1. Sequence Numbers

**VERY IMPORTANT**: The kettle tracks a sequence number that must increment with each command.

```python
# Each command must increment the sequence
self.stat["seq"] = (self.stat["seq"] + 1) % 0xFF  # Wraps at 255

# BUG TO AVOID: Never increment sequence multiple times for one command
# This was the heating bug - wake() incremented it, then turn_on() incremented again
```

**Current Implementation**:
- `tick()` method increments sequence
- Called once per command, not per operation
- MQTT callback handles wake separately from turn_on

### 2. Message Format

All messages follow this structure:
```
##<header><len><payload>&&

Examples:
##0080{JSON}&&    (plain text, 0x80 bytes payload)
##80A0{encrypted} (encrypted, 0xA0 bytes payload)
```

**Payload Structure** (data2 field in JSON):
```
AA <len> 00000000 00 03B7 <seq> <cmd> 0000 <params> <checksum>

Commands:
0x39 = Turn ON  (params: temp, keep_warm)
0x3A = Turn OFF
0x41 = Wake
0x36 = Status request (optional - kettle sends automatically)
```

### 3. Kettle States

| Code | Name | Power | Description | Can Send Commands? |
|------|------|-------|-------------|-------------------|
| 0x00 | Not on base | OFF | Kettle removed | ❌ No |
| 0x02 | Standby | OFF | Sleeping | ✅ Yes (slow wake) |
| 0x03 | Ready | OFF | Awake, display on | ✅ Yes (immediate) |
| 0x04 | Heating | ON | Actively boiling | ✅ Yes |
| 0x05 | Keep Warm | OFF | Maintaining temp | ✅ Yes |

**Important**: Always wake kettle before sending heat command if not in Ready state.

### 4. Network Configuration

**CRITICAL for Raspberry Pi**:
- Must set `UDP_IP_BCAST` to WiFi subnet (e.g., "192.168.1.255")
- Default "255.255.255.255" only works on single-interface systems
- Linux kernel sends broadcast to first interface only

**CRITICAL for Reliability**:
- Configure static DHCP reservation for kettle MAC address
- Kettle frequently changes IP when sleeping/waking
- Connection will be unstable without static IP

## Common Issues & Solutions

### Issue 1: Kettle Not Heating (FIXED)

**Symptom**: Connection works, status updates work, but kettle doesn't heat when commanded

**Root Cause**: Sequence number incremented multiple times per command
- MQTT callback: `wake()` → seq++
- Then `turn_on()` → `wake()` → seq++ → seq++ (double increment!)
- Kettle rejects commands with wrong sequence

**Solution**: Removed redundant `wake()` call from inside `turn_on()`
- Caller responsible for waking if needed
- Each command increments sequence exactly once

**File**: `appkettle_mqtt.py` lines 91-95

### Issue 2: Discovery Fails

**Symptoms**: "No kettle discovered" or timeout

**Common Causes**:
1. Wrong broadcast address (multi-interface systems)
   - Fix: Set `UDP_IP_BCAST` to WiFi subnet broadcast
2. Kettle deep sleep
   - Fix: Physically touch/move kettle to wake
3. Different subnet
   - Fix: Ensure both devices on same network

### Issue 3: Connection Timeout

**Symptoms**: "Socket error: timed out" repeatedly

**Solutions**:
1. Wait 2-3 retry cycles (UDP probes will wake kettle)
2. Physically wake kettle by touching it
3. Verify static DHCP is configured
4. Check kettle is on base station

### Issue 4: "Length does not match the received packet"

**Status**: **NORMAL - NOT AN ERROR**
- These messages appear during connection setup
- Parser safely ignores them
- Do not treat as errors in automation

## Code Quality Notes

### What Works Well

1. **Protocol parsing** - Robust message decoder handles various packet formats
2. **Auto-reconnection** - Automatic recovery from connection drops
3. **Python API** - Clean, simple interface for automation
4. **Documentation** - Comprehensive instructions.md for AI agents

### Technical Debt / Areas for Improvement

1. **Error handling** - Some methods return None on success, inconsistent
2. **Logging** - Uses print statements instead of proper logging module
3. **Type hints** - No type annotations (could add for better IDE support)
4. **Unit tests** - No automated tests (hard without physical kettle)
5. **Async support** - All synchronous, could benefit from asyncio

### Design Decisions

**Why not async?**
- Simpler for AI agents to use synchronous API
- Kettle responds quickly (<100ms), no need for async
- Easier to debug and understand

**Why optional encryption?**
- Kettle accepts plain text commands
- AES adds complexity without security benefit (local network only)
- Left encryption code for reference/completeness

**Why context manager?**
- Ensures proper cleanup (disconnect)
- Pythonic pattern AI agents can use easily
- Prevents socket leaks

## Testing Notes

### Manual Testing

```bash
# Discovery test
python appkettle_mqtt.py

# Connection test
python appkettle_mqtt.py 192.168.1.100 GD0-12345-abcd

# Python API test
python example_agent.py status
```

### Integration Testing

```python
# Test sequence (run from Python)
from kettle_control import KettleController

with KettleController() as kettle:
    # Test 1: Discovery and connection
    assert kettle.connected, "Should be connected"

    # Test 2: Status retrieval
    status = kettle.get_status()
    assert "temperature" in status

    # Test 3: Wake
    kettle.wake()
    time.sleep(2)
    status = kettle.get_status()
    assert status["status"] == "Ready"

    # Test 4: Heat (quick test - don't wait)
    kettle.heat(50)  # Low temp for quick test
    time.sleep(3)
    status = kettle.get_status()
    assert status["status"] == "Heating"

    # Test 5: Turn off
    kettle.turn_off()
    time.sleep(2)
    status = kettle.get_status()
    assert status["power"] == "OFF"
```

### Known Kettle Behavior

- **Discovery response time**: 1-5 seconds (usually immediate with static IP)
- **Connection time**: 5-60 seconds depending on kettle state
- **Status heartbeat**: Every ~1 second when connected
- **Heat time**: ~3-4 minutes for full boil (depends on volume/starting temp)
- **Keep warm duration**: Maximum 30 minutes

## Security Considerations

### Local Network Only
- Block internet access to kettle via firewall (recommended)
- No authentication required for local control
- Protocol designed for trusted local network only

### Encryption
- AES-CBC encryption available but optional
- Keys hardcoded in app (not secret)
- Plain text commands work fine for local use

### Best Practices
1. Static DHCP reservation (prevents IP conflicts)
2. Separate IoT VLAN if available
3. Block kettle from internet access
4. Monitor for unusual network activity

## Future Enhancement Ideas

### Potential Features

1. **Async API**: asyncio version for concurrent control
2. **WebSocket API**: Real-time status streaming for web UIs
3. **Home Assistant Integration**: Native HA component
4. **Temperature history**: Log and graph temperature over time
5. **Smart scheduling**: Automated boiling at specific times
6. **Water level tracking**: Alert when kettle needs refilling
7. **Energy monitoring**: Track power consumption patterns

### Protocol Improvements

1. **Better error reporting**: Decode kettle error responses
2. **Command confirmation**: Verify kettle received/executed command
3. **Batch commands**: Queue multiple operations
4. **Firmware detection**: Auto-adapt to different kettle versions

### Code Quality

1. **Type hints**: Add full type annotations
2. **Logging**: Replace print with proper logging module
3. **Unit tests**: Mock socket layer for testing
4. **CI/CD**: Automated testing and deployment
5. **Documentation**: Generate API docs from docstrings

## AI Agent Guidelines

### When Modifying This Project

1. **Always preserve sequence numbering logic** - Critical for reliability
2. **Test with physical kettle** - Protocol quirks only appear in real use
3. **Update instructions.md** - Primary reference for AI agents
4. **Keep API simple** - Don't over-engineer, prioritize clarity
5. **Document protocol changes** - Note any new commands discovered

### Common AI Agent Tasks

**Task: Add new command**
1. Decode hex command from app traffic
2. Add method to `AppKettle` class (with `tick()` call)
3. Add wrapper to `KettleController` class
4. Update instructions.md with command details
5. Add example to example_agent.py

**Task: Fix connection issues**
1. Check sequence number handling first
2. Verify network configuration (static IP, broadcast)
3. Add debug logging to see exact messages
4. Test with both auto-discovery and manual connection
5. Document solution in this file

**Task: Improve error handling**
1. Identify failure modes (timeout, wrong status, etc.)
2. Add specific exception types
3. Update API to return/raise appropriate errors
4. Add retry logic where appropriate
5. Update documentation with new behavior

## Debugging Tips

### Enable Debug Output

```python
# In appkettle_mqtt.py
DEBUG_MSG = True                 # Print all messages
DEBUG_PRINT_STAT_MSG = True      # Print status messages
DEBUG_PRINT_KEEP_CONNECT = True  # Print keepalive messages
```

### Network Packet Capture

```bash
# Monitor all kettle traffic
sudo tcpdump -i wlan0 host 192.168.1.100 -A

# Just UDP discovery
sudo tcpdump -i wlan0 port 15103 -A

# Just TCP control
sudo tcpdump -i wlan0 port 6002 -X
```

### Python Debug Console

```python
# Launch interactive console with kettle connected
python -i << EOF
from kettle_control import KettleController
kettle = KettleController()
kettle.connect()
# Now you can type commands interactively
EOF

# Examples:
>>> status = kettle.get_status()
>>> kettle.kettle.stat  # Access internal state
>>> kettle.kettle_socket.connected  # Check connection
```

## Version History

- **v1.0** (2020-ish): Initial reverse engineering, manual console interface
- **v1.5** (2026-02-15): Added MQTT integration, comprehensive documentation
- **v2.0** (2026-02-16): Fixed heating bug, added Python API for AI agents

## Contact & Support

This is a reverse-engineered, unofficial implementation. No official support from AppKettle manufacturer.

**Resources**:
- Protocol documentation: `instructions.md`
- Example code: `example_agent.py`
- Issue tracking: Document issues in this file or project README

---

*Last Updated: 2026-02-16*
*Maintained by: AI agents + human developer*
*Kettle Firmware Tested: v0.4.9*
*Python Version: 3.8+*
