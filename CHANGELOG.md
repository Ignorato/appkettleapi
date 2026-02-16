# Changelog

All notable changes to the AppKettle Control project are documented here.

## [2.1.0] - 2026-02-16

### Fixed
- **Status reading bug in Python API** - `get_status()` method now correctly returns real-time data
  - Previous version returned all zeros/unknowns
  - Issue: `_update_status()` was returning after first message (often not a status message)
  - Fix: Now keeps reading until receiving a message with actual status data (data3)
  - Updated timeout from 2s to 5s (10s on initial connect)
  - Added validation to ensure status contains real data before returning

- **Heating command bug** - Kettle now responds to heating commands correctly
  - Issue: Double `wake()` call caused sequence number to increment incorrectly
  - Fix: Removed redundant `wake()` call from inside `turn_on()` method
  - Caller is now responsible for waking kettle before heating if needed

### Changed
- Increased status read timeout for more reliable data retrieval
- Improved error messaging when status update times out
- Updated all documentation to reflect fixes

### Documentation
- Updated README.md with quick start guide and feature list
- Added changelog section to instructions.md
- Updated developer_notes.md with detailed bug analysis
- Created this CHANGELOG.md

## [2.0.0] - 2026-02-15

### Added
- **Python API for automation** (`kettle_control.py`)
  - `KettleController` class with clean, simple interface
  - Auto-discovery support
  - Context manager support for automatic cleanup
  - Methods: `connect()`, `disconnect()`, `wake()`, `heat()`, `turn_off()`, `get_status()`
  - Status monitoring with `wait_for_temperature()` and `wait_for_status()`

- **Example automation scripts** (`example_agent.py`)
  - Command-line interface for common tasks
  - Example AI agent implementation patterns
  - Demonstrates best practices for automation

- **Comprehensive documentation**
  - `instructions.md` - Complete protocol documentation and AI agent guide
  - `developer_notes.md` - Technical details for developers and future AI agents
  - Protocol specification with message formats and command reference
  - Troubleshooting guide with common issues and solutions

### Changed
- Reorganized project structure for better clarity
- Improved code documentation and comments

## [1.0.0] - 2020-ish

### Initial Implementation
- Reverse-engineered AppKettle protocol from Android app
- TCP/IP communication on port 6002
- UDP discovery protocol on port 15103
- Manual console interface with Ctrl+C commands
- MQTT integration for home automation
- Protocol parser for message encoding/decoding
- Support for:
  - ON/OFF commands
  - Temperature control (40-100°C)
  - Keep warm mode (0-30 minutes)
  - Status monitoring (temperature, volume, power state)
  - Optional AES encryption

---

## Version Format

This project uses [Semantic Versioning](https://semver.org/):
- **Major version** (X.0.0): Breaking changes to API or protocol
- **Minor version** (0.X.0): New features, non-breaking changes
- **Patch version** (0.0.X): Bug fixes, documentation updates

## Categories

- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements
- **Documentation**: Documentation changes
