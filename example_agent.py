#!/usr/bin/env python3
"""
Example AI agent script demonstrating kettle automation.

This shows how an AI agent can programmatically control the kettle
without manual intervention or interactive console commands.
"""

import time
from kettle_control import KettleController


def agent_boil_water(temperature=100, keep_warm=False):
    """
    AI Agent task: Boil water to specified temperature.

    Args:
        temperature: Target temperature in °C
        keep_warm: Whether to enable keep warm mode

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"AI AGENT TASK: Boil water to {temperature}°C")
    print(f"{'='*60}\n")

    # Step 1: Connect to kettle (auto-discover)
    kettle = KettleController()

    if not kettle.connect():
        print("❌ Failed to connect to kettle")
        return False

    try:
        # Step 2: Check initial status
        status = kettle.get_status()
        print(f"\n📊 Initial Status:")
        print(f"   - Power: {status['power']}")
        print(f"   - Status: {status['status']}")
        print(f"   - Temperature: {status['temperature']}°C")
        print(f"   - Volume: {status['volume']}ml")

        # Step 3: Wake kettle if needed
        if status['status'] != "Ready":
            print(f"\n🔔 Kettle is in '{status['status']}' state, waking up...")
            kettle.wake()
            time.sleep(2)

        # Step 4: Start heating
        print(f"\n🔥 Starting to heat water to {temperature}°C...")
        kettle.heat(temperature=temperature, keep_warm=keep_warm)

        # Step 5: Monitor heating progress
        print("\n📈 Monitoring temperature:")
        start_time = time.time()
        last_temp = 0

        while True:
            status = kettle.get_status()
            current_temp = status['temperature']

            # Print progress if temperature changed
            if current_temp != last_temp:
                elapsed = int(time.time() - start_time)
                print(f"   [{elapsed:3d}s] {current_temp:3d}°C - Status: {status['status']}")
                last_temp = current_temp

            # Check if finished heating
            if status['status'] in ["Ready", "Keep Warm", "Standby"]:
                if current_temp >= temperature or status['power'] == "OFF":
                    print(f"\n✅ Heating complete! Final temperature: {current_temp}°C")
                    break

            # Safety timeout (5 minutes)
            if time.time() - start_time > 300:
                print("\n⚠️  Timeout reached (5 minutes)")
                break

            time.sleep(1)

        # Step 6: Final status
        final_status = kettle.get_status()
        print(f"\n📊 Final Status:")
        print(f"   - Temperature: {final_status['temperature']}°C")
        print(f"   - Status: {final_status['status']}")
        print(f"   - Power: {final_status['power']}")

        print("\n✅ Task completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Error during operation: {e}")
        return False

    finally:
        # Always disconnect
        kettle.disconnect()


def agent_quick_status_check():
    """
    AI Agent task: Quick status check of the kettle.

    Returns:
        dict: Kettle status or None if failed
    """
    print(f"\n{'='*60}")
    print(f"AI AGENT TASK: Quick status check")
    print(f"{'='*60}\n")

    with KettleController() as kettle:
        status = kettle.get_status()
        print(f"📊 Kettle Status:")
        print(f"   - Power: {status['power']}")
        print(f"   - Status: {status['status']}")
        print(f"   - Temperature: {status['temperature']}°C")
        print(f"   - Target: {status['target_temp']}°C")
        print(f"   - Volume: {status['volume']}ml")
        print(f"   - Keep Warm: {status['keep_warm_secs']}s")
        return status


def agent_heat_to_temp_and_notify(temperature=80):
    """
    AI Agent task: Heat to specific temperature and return when ready.

    Args:
        temperature: Target temperature in °C

    Returns:
        bool: True if water reached temperature, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"AI AGENT TASK: Heat to {temperature}°C and notify")
    print(f"{'='*60}\n")

    with KettleController() as kettle:
        # Wake and heat
        kettle.wake()
        time.sleep(1)
        kettle.heat(temperature)

        # Wait for target temperature
        success = kettle.wait_for_temperature(temperature, timeout=300)

        if success:
            print(f"\n✅ Water ready at {temperature}°C!")
            return True
        else:
            print(f"\n❌ Failed to reach {temperature}°C")
            return False


def agent_turn_off_kettle():
    """
    AI Agent task: Simply turn off the kettle.

    Returns:
        bool: True if successful
    """
    print(f"\n{'='*60}")
    print(f"AI AGENT TASK: Turn off kettle")
    print(f"{'='*60}\n")

    with KettleController() as kettle:
        success = kettle.turn_off()
        if success:
            print("✅ Kettle turned off")
        else:
            print("❌ Failed to turn off kettle")
        return success


# Example usage
if __name__ == "__main__":
    import sys

    print("\n🤖 AppKettle AI Agent Controller")
    print("=" * 60)

    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "status":
            agent_quick_status_check()

        elif command == "boil":
            temp = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            agent_boil_water(temperature=temp)

        elif command == "heat":
            temp = int(sys.argv[2]) if len(sys.argv) > 2 else 80
            agent_heat_to_temp_and_notify(temperature=temp)

        elif command == "off":
            agent_turn_off_kettle()

        else:
            print(f"Unknown command: {command}")
            print("\nUsage:")
            print("  python example_agent.py status")
            print("  python example_agent.py boil [temp]")
            print("  python example_agent.py heat [temp]")
            print("  python example_agent.py off")

    else:
        # Default: run a demo sequence
        print("\nRunning demo sequence...\n")

        # Task 1: Check status
        agent_quick_status_check()
        time.sleep(2)

        # Task 2: Heat to 80°C
        agent_heat_to_temp_and_notify(temperature=80)
        time.sleep(2)

        # Task 3: Turn off
        agent_turn_off_kettle()

        print("\n✅ All demo tasks completed!")
