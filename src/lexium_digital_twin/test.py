import ssl
import socket
import json
import time
from turtle import pos

# --- Configuration ---
HOST = '192.168.1.252'
PORT = 10001
DO6_INDEX = 5
IO_TYPE_CABINET = 0

MOTION_TIMEOUT    = 7.5   # Max seconds to wait for any single move to complete
ARRIVE_TOLERANCE  = 0.50   # Degrees — how close counts as "arrived"
POLL_INTERVAL     = 0.05   # Seconds between position polls (20 Hz)
RELEASE_HOLD_TIME = 1.2    # Seconds to hold magnet OFF before re-energizing after a drop

# --- SSL Context ---
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode    = ssl.CERT_NONE


# ---------------------------------------------------------------------------
# Low-level comms
# ---------------------------------------------------------------------------

def send_command(cmd_dict):
    try:
        with socket.create_connection((HOST, PORT), timeout=5) as raw:
            with ctx.wrap_socket(raw) as s:
                s.send((json.dumps(cmd_dict) + "\n").encode())

                response = s.recv(4096).decode().strip()

                if not response:
                    return None

                return json.loads(response)

    except Exception as e:
        print(f"   [COMMS ERROR] {e}")
        return None


def get_joint_pos():
    """Return live joint positions as a 6-float list, or None."""
    resp = send_command({"cmdName": "get_joint_pos"})
    if resp and "jVal" in resp:
        return resp["jVal"]
    return None


# ---------------------------------------------------------------------------
# Magnet helpers
# ---------------------------------------------------------------------------

def magnet_on():
    result = send_command({
        "cmdName": "set_digital_output",
        "type":    IO_TYPE_CABINET,
        "index":   DO6_INDEX,
        "value":   1
    })
    print("   [MAGNET] ON")
    return result


def magnet_off():
    result = send_command({
        "cmdName": "set_digital_output",
        "type":    IO_TYPE_CABINET,
        "index":   DO6_INDEX,
        "value":   0
    })
    print("   [MAGNET] OFF")
    return result


# ---------------------------------------------------------------------------
# Motion helpers
# ---------------------------------------------------------------------------

def joints_within_tolerance(current, target, tol):
    if not current or len(current) != 6:
        return False
    return all(abs(c - t) <= tol for c, t in zip(current, target))


def wait_for_arrival(target_pos, timeout=MOTION_TIMEOUT, tolerance=ARRIVE_TOLERANCE):
    """
    Block until all 6 joints are within `tolerance` degrees of target_pos,
    or until `timeout` seconds have elapsed.
    Returns True if arrived, False if timed out.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = get_joint_pos()
        if joints_within_tolerance(current, target_pos, tolerance):
            return True
        time.sleep(POLL_INTERVAL)
    return False


def move_to(position, motion="joint", speed=100, accel=10.0):
    """Send either joint_move or line_move and block until arrival."""

    packet = {
        "cmdName": "joint_move" if motion == "joint" else "linear_move",
        "relFlag": 0,
        "jointPosition": position,
        "speed": speed,
        "accel": accel
    }

    reply = send_command(packet)

    print(f"   [{motion.upper()} MOVE CMD] {reply}")

    arrived = wait_for_arrival(position)

    if not arrived:
        print("   [WARNING] Motion timeout — arm may not have fully arrived. Proceeding.")

    return arrived


# ---------------------------------------------------------------------------
# Routine definition
#
# Each step has:
#   name         — label for logging
#   position     — 6-DOF joint angles in degrees
#   action       — what to do with the magnet ON ARRIVAL (see below)
#   post_delay   — optional dwell after the action (e.g. riveting station wait)
#
# action values:
#   None        — no magnet change; magnet stays in whatever state it was
#   "pick"      — arm has arrived at a pick point; magnet should already be ON
#                 (we just confirm and log — the part is now held)
#   "drop"      — arm has arrived at a drop point; turn magnet OFF, wait
#                 RELEASE_HOLD_TIME, then turn magnet ON again before moving away
# ---------------------------------------------------------------------------


routine_steps = [
    {
        "name": "HOME",
        "position": [0.0, 36.92, 88.02, 146.84, -89.96, 0.0],
        "motion": "joint",
        "action": None,
        "post_delay": None
    },
    {
        "name": "ABOVE CONVEYOR",
        "position": [-113.03, 114.85, 32.04, 123.23, -91.64, 0.04],
        "motion": "joint",
        "action": None,
        "post_delay": None
    },
    {
        "name": "PICK CAFI 1",
        "position": [-108.61, 123.88, 75.75, 72.36, -87.95, 0.05],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE CONVEYOR (REPEAT)",
        "position": [-113.03, 114.85, 32.04, 123.23, -91.64, 0.04],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE RIVETING",
        "position": [-245.51, 114.37, 3.31, 154.06, -88.80, 42.96],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "RIVETING FIXTURE",
        "position": [-253.14, 116.89, 79.58, 78.87, -90.02, 35.68],
        "motion": "joint",
        "action": "drop",
        "post_delay": None
    },
    {
        "name": "ABOVE RIVETING (POST PLACE)",
        "position": [-245.51, 114.37, 3.31, 154.06, -88.80, 42.96],
        "motion": "joint",
        "action": None,
        "post_delay": 20.0
    },
    {
        "name": "PICK RIVETING", #the error is most likely here
        "position": [-253.14, 119.27, 79.96, 78.15, -90.03, 35.68],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE RIVETING (POST PLACE - REPEAT)",
        "position": [-245.51, 114.37, 3.31, 154.06, -88.80, 42.96],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE INSPECTION",
        "position": [-54.34, 122.20, 1.25, 145.10, -87.93, 51.79],
        "motion": "joint",
        "action": None,
        "post_delay": None
    },
    {
        "name": "PLACE INSPECTION",
        "position": [-56.42, 112.79, 55.79, 104.16, -84.41, 52.49],
        "motion": "joint",
        "action": "drop",
        "post_delay": None
    },
    {
        "name": "ABOVE INSPECTION (AFTER)",
        "position": [-55.31, 122.20, 1.25, 145.10, -87.93, 52.49],
        "motion": "joint",
        "action": None,
        "post_delay": None
    },
    {
        "name": "PICK INSPECTION",
        "position": [-55.54, 107.21, 70.20, 93.15, -87.08, 44.09],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE INSPECTION (ONCE MORE)",
        "position": [-57.23, 108.59, 44.19, 115.14, -86.17, 44.08],
        "motion": "joint",
        "action": None,
        "post_delay": None
    },
    {
        "name": "ABOVE BINS PASS",
        "position": [-72.83, 145.62, 6.29, 110.98, -85.72, 26.99],
        "motion": "joint",
        "action": "drop",
        "post_delay": None
    },
    {
        "name": "HOME",
        "position": [0.0, 36.92, 88.02, 146.84, -89.96, 0.0],
        "motion": "joint",
        "action": None,
        "post_delay": None
    },
        {
        "name": "ABOVE CONVEYOR",
        "position": [-113.03, 114.85, 32.04, 123.23, -91.64, 0.04],
        "motion": "joint",
        "action": None,
        "post_delay": None
    },
    {
        "name": "PICK CAFI 1",
        "position": [-108.61, 123.88, 75.75, 72.36, -87.95, 0.05],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE CONVEYOR (REPEAT)",
        "position": [-113.03, 114.85, 32.04, 123.23, -91.64, 0.04],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE RIVETING",
        "position": [-245.51, 114.37, 3.31, 154.06, -88.80, 42.96],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "RIVETING FIXTURE",
        "position": [-253.14, 116.89, 79.58, 78.87, -90.02, 35.68],
        "motion": "joint",
        "action": "drop",
        "post_delay": None
    },
    {
        "name": "ABOVE RIVETING (POST PLACE)",
        "position": [-245.51, 114.37, 3.31, 154.06, -88.80, 42.96],
        "motion": "joint",
        "action": None,
        "post_delay": 16.0
    },
    {
        "name": "PICK RIVETING",
        "position": [-253.14, 119.27, 79.96, 78.15, -90.03, 35.68],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE RIVETING (POST PLACE - REPEAT)",
        "position": [-245.51, 114.37, 3.31, 154.06, -88.80, 42.96],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE INSPECTION",
        "position": [-54.34, 122.20, 1.25, 145.10, -87.93, 51.79],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "PLACE INSPECTION",
        "position": [-56.42, 112.79, 55.79, 104.16, -84.41, 52.49],
        "motion": "joint",
        "action": "drop",
        "post_delay": None
    },
    {
        "name": "ABOVE INSPECTION (AFTER)",
        "position": [-55.31, 122.20, 1.25, 145.10, -87.93, 52.49],
        "motion": "joint",
        "action": None,
        "post_delay": None
    },
    {
        "name": "PICK INSPECTION",
        "position": [-55.54, 107.21, 70.20, 93.15, -87.08, 44.09],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE INSPECTION (ONCE MORE)",
        "position": [-57.23, 108.59, 44.19, 115.14, -86.17, 44.08],
        "motion": "joint",
        "action": "pick",
        "post_delay": None
    },
    {
        "name": "ABOVE BINS FAIL",
        "position": [-57.56, 147.53, 6.30, 112.01, -85.42, 38.48],
        "motion": "joint",
        "action": "drop",
        "post_delay": None
    },
    {
        "name": "HOME",
        "position": [0.0, 36.92, 88.02, 146.84, -89.96, 0.0],
        "motion": "joint",
        "action": None,
        "post_delay": None
    },


]

# ---------------------------------------------------------------------------
# Main sequencer
# ---------------------------------------------------------------------------

def run_routine():
    total = len(routine_steps)
    print("=== COBOT SEQUENCER INITIALIZING ===\n")

    # Energize magnet immediately and confirm before anything moves.
    # The arm must never transit with the magnet in an unknown state.
    print("-> Charging electromagnet before motion begins...")
    magnet_on()
    time.sleep(0.3)  # Brief stabilization — field needs ~200ms to fully saturate

    print("\n-> Checking starting position...")
    start_pos = get_joint_pos()
    print(f"   Current joints: {start_pos}\n")
    print("=" * 55)

    for i, step in enumerate(routine_steps, start=1):
        name    = step["name"]
        pos     = step["position"]
        action  = step["action"]
        dwell   = step["post_delay"]

        print(f"\n[{i:02d}/{total}] {name}")

        # --- Command the move and block until physically arrived ---
        motion = step.get("motion", "joint")
        move_to(pos, motion=motion)

        # --- Magnet action on arrival ---
        if action == "pick":
            # Arm is at the pick point. Magnet is already ON from initialization
            # or was re-energized after the previous drop. Just confirm the state
            # so a dropout since the last drop cycle gets caught and corrected.
            print("   [PICK] Confirming magnet is energized — part acquisition.")
            magnet_on()

        elif action == "drop":
            # Arm has physically arrived at a drop zone.
            # Turn magnet off, wait for part to fully release, then re-energize
            # so the magnet is live again before the arm starts moving away.
            print("   [DROP] Releasing part...")
            magnet_off()
            time.sleep(RELEASE_HOLD_TIME)
            print("   [DROP] Re-energizing before departure...")
            magnet_on()

        # --- Optional dwell (e.g. riveting station firing) ---
        if dwell is not None:
            print(f"   [DWELL] Holding at {name} for {dwell}s...")
            time.sleep(dwell)
            print("   [DWELL] Complete.")

        print(f"   Done: {name}")
        print("-" * 55)

    print("\n=== ROUTINE COMPLETED ===")


if __name__ == "__main__":
    run_routine()