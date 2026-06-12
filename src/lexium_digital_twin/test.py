import ssl
import socket
import json
import time

# --- Configuration ---
HOST = '192.168.1.252'
PORT = 10001
DO6_INDEX = 5
IO_TYPE_CABINET = 0

MOTION_TIMEOUT    = 20.0   # Max seconds to wait for any single move to complete
ARRIVE_TOLERANCE  = 0.15   # Degrees — how close counts as "arrived"
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
    """Send one JSON command, return parsed response or None on failure."""
    try:
        with socket.create_connection((HOST, PORT), timeout=5) as raw:
            with ctx.wrap_socket(raw) as s:
                s.send((json.dumps(cmd_dict) + "\n").encode())
                response = s.recv(4096).decode()
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


def move_to(position, speed=5.0, accel=5.0):
    """Send joint_move and block until the arm physically arrives."""
    packet = {
        "cmdName":       "joint_move",
        "relFlag":       0,
        "jointPosition": position,
        "speed":         speed,
        "accel":         accel
    }
    reply = send_command(packet)
    print(f"   [MOVE CMD] {reply}")

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
        "name":       "HOME",
        "position":   [0.0, 90.0, 0.0, 90.0, 0.0, 0.0],
        "action":     None,
        "post_delay": None
    },
    {
        "name":       "ABOVE CONVEYOR",
        "position":   [39.2580, 67.3787, -40.7220, 60.8752, 88.3291, -0.5988],
        "action":     None,
        "post_delay": None
    },
    {
        "name":       "PICK CAFI 1",
        "position":   [47.2740, 57.7760, -77.5513, 107.2994, 88.2996, -0.0096],
        "action":     "pick",    # Magnet already ON; part is now acquired
        "post_delay": None
    },
    {
        "name":       "ABOVE CONVEYOR (REPEAT)",
        "position":   [39.2580, 67.3787, -40.7220, 60.8752, 88.3291, -0.5988],
        "action":     None,
        "post_delay": None
    },
    {
        "name":       "NEW TRANSITION POINT",
        "position":   [-67.8441, 89.5120, -46.3201, 46.4578, 87.3110, 24.4764],
        "action":     None,
        "post_delay": None
    },
    {
        "name":       "ABOVE RIVETING",
        "position":   [-91.0336, 68.1251, -40.0538, 64.1423, 86.3255, 46.0431],
        "action":     None,
        "post_delay": None
    },
    {
        "name":       "RIVETING FIXTURE",
        "position":   [-99.7945, 61.4152, -81.0583, 108.1301, 90.4883, 35.0759],
        "action":     "drop",    # Place part into riveting fixture
        "post_delay": None
    },
    {
        # Wait here while secondary riveting system fires
        "name":       "ABOVE RIVETING (POST PLACE)",
        "position":   [-99.8021, 100.4385, -81.0562, 69.5977, 91.4784, 35.0766],
        "action":     None,
        "post_delay": 10.0       # 10-second dwell for riveting operation
    },
    {
        "name":       "PICK RIVETING",
        "position":   [-99.7945, 61.4152, -81.0583, 108.1301, 90.4883, 35.0759],
        "action":     "pick",    # Re-acquire the part after riveting
        "post_delay": None
    },
    {
        "name":       "ABOVE RIVETING (POST PLACE - REPEAT)",
        "position":   [-99.8021, 100.4385, -81.0562, 69.5977, 91.4784, 35.0766],
        "action":     None,
        "post_delay": None
    },
    {
        "name":       "ABOVE INSPECTION",
        "position":   [-267.7562, 100.4268, -81.0590, 69.5977, 91.4674, 35.0766],
        "action":     None,
        "post_delay": None
    },
    {
        "name":       "PLACE INSPECTION",
        "position":   [-263.8775, 68.2913, -57.9142, 75.4803, 92.8694, 35.1171],
        "action":     "drop",    # Place part at inspection station
        "post_delay": None
    },
    {
        "name":       "ABOVE INSPECTION (AFTER)",
        "position":   [-263.9057, 109.3211, -57.8943, 39.3386, 92.8701, 35.1151],
        "action":     None,
        "post_delay": None
    },
    {
        "name":       "PICK INSPECTION",
        "position":   [-263.8775, 68.2913, -57.9142, 75.4803, 92.8694, 35.1171],
        "action":     "pick",    # Re-acquire after inspection
        "post_delay": None
    },
    {
        "name":       "ABOVE BINS",
        "position":   [-268.3204, 57.2877, -16.2568, 65.2655, 95.8679, 35.1206],
        "action":     None,
        "post_delay": None
    },
    {
        "name":       "PASS",
        "position":   [-274.0567, 45.0818, -16.2815, 85.5217, 92.8021, 35.1199],
        "action":     "drop",    # Sort to pass bin
        "post_delay": None
    },
    {
        # NOTE: In the current routine the arm always goes to PASS.
        # If inspection logic is added later, SCRAP would be a conditional
        # branch here instead. For now it is kept in the step list but
        # never reached in normal flow.
        "name":       "SCRAP",
        "position":   [-263.8521, 42.1101, -15.2974, 84.6024, 110.9360, 35.1213],
        "action":     "drop",
        "post_delay": None
    },
    {
        "name":       "FINAL HOME",
        "position":   [0.0, 90.0, 0.0, 90.0, 0.0, 0.0],
        "action":     None,
        "post_delay": None
    }
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
        move_to(pos)

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