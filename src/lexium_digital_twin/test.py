import ssl
import socket
import json
import time

# --- Configuration ---
HOST = '192.168.1.252'
PORT = 10001
DO6_INDEX = 5
IO_TYPE_CABINET = 0

# --- SSL Context Setup ---
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def send_command(cmd_dict):
    """Sends a single JSON command packet over the encrypted socket connection."""
    try:
        with socket.create_connection((HOST, PORT), timeout=10) as raw:
            with ctx.wrap_socket(raw) as s:
                s.send((json.dumps(cmd_dict) + "\n").encode())
                response = s.recv(4096).decode()
                return json.loads(response)
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Define Routine Points with Safe Operational Triggers ---
# gripper_action: 1 = Turn ON/Hold, 0 = Turn OFF/Release, None = Maintain last state
# post_delay: If set, freezes all action and holds for X seconds BEFORE moving to the next step
routine_steps = [
    {
        "name": "HOME",
        "position": [0.0, 90.0, 0.0, 90.0, 0.0, 0.0],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "ABOVE CONVEYOR",
        "position": [39.2580, 67.3787, -40.7220, 60.8752, 88.3291, -0.5988],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "PICK CAFI 1",
        "position": [47.2740, 57.7760, -77.5513, 107.2994, 88.2996, -0.0096],
        "gripper_action": 1,  # <--- Turn ON immediately as we target/reach this point
        "post_delay": None
    },
    {
        "name": "ABOVE CONVEYOR (REPEAT)",
        "position": [39.2580, 67.3787, -40.7220, 60.8752, 88.3291, -0.5988],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "NEW TRANSITION POINT",
        "position": [-67.8441, 89.5120, -46.3201, 46.4578, 87.3110, 24.4764],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "ABOVE RIVETING",
        "position": [-91.0336, 68.1251, -40.0538, 64.1423, 86.3255, 46.0431],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "RIVETING FIXTURE",
        "position": [-99.7945, 61.4152, -81.0583, 108.1301, 90.4883, 35.0759],
        "gripper_action": 0,  # <--- Turn OFF immediately to drop component
        "post_delay": None
    },
    {
        "name": "ABOVE RIVETING (POST PLACE)",
        "position": [-99.8021, 100.4385, -81.0562, 69.5977, 91.4784, 35.0766],
        "gripper_action": None,
        "post_delay": 10.0   # <--- DWELL WINDOW: Freeze movement for 10s here
    },
    {
        "name": "PICK RIVETING",
        "position": [-99.7945, 61.4152, -81.0583, 108.1301, 90.4883, 35.0759],
        "gripper_action": 1,  # <--- Turn ON to grab part
        "post_delay": None
    },
    {
        "name": "ABOVE RIVETING (POST PLACE - REPEAT)",
        "position": [-99.8021, 100.4385, -81.0562, 69.5977, 91.4784, 35.0766],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "ABOVE INSPECTION",
        "position": [-267.7562, 100.4268, -81.0590, 69.5977, 91.4674, 35.0766],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "PLACE INSPECTION",
        "position": [-263.8775, 68.2913, -57.9142, 75.4803, 92.8694, 35.1171],
        "gripper_action": 0,  # <--- Turn OFF to release part
        "post_delay": None
    },
    {
        "name": "ABOVE INSPECTION (AFTER)",
        "position": [-263.9057, 109.3211, -57.8943, 39.3386, 92.8701, 35.1151],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "PICK INSPECTION (DUPLICATE)",
        "position": [-263.8775, 68.2913, -57.9142, 75.4803, 92.8694, 35.1171],
        "gripper_action": 1,  # <--- Turn ON to grab part again
        "post_delay": None
    },
    {
        "name": "ABOVE BINS",
        "position": [-268.3204, 57.2877, -16.2568, 65.2655, 95.8679, 35.1206],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "PASS",
        "position": [-274.0567, 45.0818, -16.2815, 85.5217, 92.8021, 35.1199],
        "gripper_action": 0,  # <--- Turn OFF to drop part in pass bin
        "post_delay": None
    },
    {
        "name": "SCRAP",
        "position": [-263.8521, 42.1101, -15.2974, 84.6024, 110.9360, 35.1213],
        "gripper_action": None,
        "post_delay": None
    },
    {
        "name": "FINAL HOME",
        "position": [0.0, 90.0, 0.0, 90.0, 0.0, 0.0],
        "gripper_action": None,
        "post_delay": None
    }
]

# --- Main Automation Loop ---
def run_routine():
    print("=== STARTING COMPLETE AUTOMATION ROUTINE ===")
    
    # 1. Check Initial State
    print("\nChecking starting position...")
    initial_pos = send_command({"cmdName": "get_joint_pos"})
    print(f"Current Joint Position: {initial_pos}\n")
    
    # 2. Iterate through the automation points
    for index, step in enumerate(routine_steps, start=1):
        print(f"[{index}/{len(routine_steps)}] Initiating waypoint sequence for: **{step['name']}**")
        
        # Change gripper state BEFORE/DURING transit so it doesn't wait for the motion cushion
        if step['gripper_action'] is not None:
            action_str = "ENERGIZING (ON)" if step['gripper_action'] == 1 else "DE-ENERGIZING (OFF)"
            print(f"-> Changing IO State: {action_str} Gripper on DO6...")
            
            gripper_packet = {
                "cmdName": "set_digital_output",
                "type": IO_TYPE_CABINET,
                "index": DO6_INDEX,
                "value": step['gripper_action']
            }
            gripper_reply = send_command(gripper_packet)
            print(f"   Controller Response: {gripper_reply}")
            time.sleep(0.5) # Quick hardware transition settle
        
        # Build the arm trajectory packet
        print(f"-> Moving arm to: {step['position']}")
        move_packet = {
            "cmdName":       "joint_move",
            "relFlag":       0,               
            "jointPosition": step['position'],
            "speed":         15.0,             
            "accel":         5.0              
        }
        
        # Dispatch motion command
        move_reply = send_command(move_packet)
        print(f"-> Arm Response: {move_reply}")
        
        # Standard safety window to allow the arm to complete its physical trajectory
        print(f"-> Motion active. Holding 5-second movement buffer...")
        time.sleep(5.0)
        
        # Handle secondary system safety lock / actuator delay if configured
        if step['post_delay'] is not None:
            print(f"SAFETY LOCKOUT ACTIVE: Holding position at **{step['name']}** for {step['post_delay']} seconds...")
            time.sleep(step['post_delay'])
            print("-> Lockout complete. Resuming routine.")
            
        print("-" * 50)

    print("\n=== ROUTINE RUN COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_routine()