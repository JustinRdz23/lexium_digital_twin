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

# --- Define Routine Points with Integrated Gripper Commands ---
# gripper_action: 1 = Close/Turn ON right after moving, 0 = Open/Turn OFF right after moving, None = Do nothing
routine_steps = [
    {
        "name": "HOME",
        "position": [0.0, 90.0, 0.0, 90.0, 0.0, 0.0],
        "gripper_action": None
    },
    {
        "name": "ABOVE CONVEYOR",
        "position": [39.2580, 67.3787, -40.7220, 60.8752, 88.3291, -0.5988],
        "gripper_action": None
    },
    {
        "name": "PICK CAFI 1",
        "position": [47.2740, 57.7760, -77.5513, 107.2994, 88.2996, -0.0096],
        "gripper_action": 1  # <--- ACTIVATE Gripper right after arriving here
    },
    {
        "name": "ABOVE CONVEYOR (REPEAT)",
        "position": [39.2580, 67.3787, -40.7220, 60.8752, 88.3291, -0.5988],
        "gripper_action": None
    },
    {
        "name": "NEW TRANSITION POINT",
        "position": [-67.8441, 89.5120, -46.3201, 46.4578, 87.3110, 24.4764],
        "gripper_action": None
    },
    {
        "name": "ABOVE RIVETING",
        "position": [-91.0336, 68.1251, -40.0538, 64.1423, 86.3255, 46.0431],
        "gripper_action": None
    },
    {
        "name": "RIVETING FIXTURE",
        "position": [-99.7945, 61.4152, -81.0583, 108.1301, 90.4883, 35.0759],
        "gripper_action": 0  # <--- DEACTIVATE Gripper right after arriving here
    },
    {
        "name": "ABOVE RIVETING (POST PLACE)",
        "position": [-99.8021, 100.4385, -81.0562, 69.5977, 91.4784, 35.0766],
        "gripper_action": None
    },
    {
        "name": "PICK RIVETING",
        "position": [-99.7945, 61.4152, -81.0583, 108.1301, 90.4883, 35.0759],
        "gripper_action": 1  # <--- ACTIVATE Gripper right after arriving here
    },
    {
        "name": "ABOVE RIVETING (POST PLACE - REPEAT)",
        "position": [-99.8021, 100.4385, -81.0562, 69.5977, 91.4784, 35.0766],
        "gripper_action": None
    },
    {
        "name": "ABOVE INSPECTION",
        "position": [-267.7562, 100.4268, -81.0590, 69.5977, 91.4674, 35.0766],
        "gripper_action": None
    },
    {
        "name": "PLACE INSPECTION",
        "position": [-263.8775, 68.2913, -57.9142, 75.4803, 92.8694, 35.1171],
        "gripper_action": 0  # <--- DEACTIVATE Gripper right after arriving here
    },
    {
        "name": "ABOVE INSPECTION (AFTER)",
        "position": [-263.9057, 109.3211, -57.8943, 39.3386, 92.8701, 35.1151],
        "gripper_action": None
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
        print(f"[{index}/{len(routine_steps)}] Moving to: **{step['name']}**")
        print(f"-> Target angles (deg): {step['position']}")
        
        # Build the arm trajectory packet
        move_packet = {
            "cmdName":       "joint_move",
            "relFlag":       0,               
            "jointPosition": step['position'],
            "speed":         10.0,             # Throttled at 5% max speed
            "accel":         5.0              
        }
        
        # Dispatch motion command
        move_reply = send_command(move_packet)
        print(f"-> Arm Response: {move_reply}")
        
        # Wait out the safety cushion for the arm to reach destination
        print(f"-> Motion active. Holding a 5-second delay buffer...")
        time.sleep(5.0)
        
        # Check if this specific milestone needs a gripper modification
        if step['gripper_action'] is not None:
            action_str = "ACTIVATING (ON)" if step['gripper_action'] == 1 else "DEACTIVATING (OFF)"
            print(f"-> Milestone reached. {action_str} Gripper on DO6...")
            
            gripper_packet = {
                "cmdName": "set_digital_output",
                "type": IO_TYPE_CABINET,
                "index": DO6_INDEX,
                "value": step['gripper_action']
            }
            
            gripper_reply = send_command(gripper_packet)
            print(f"-> Gripper Response: {gripper_reply}")
            
            # Give the magnetic circuit or jaws a brief moment to settle
            time.sleep(1.0)
            
        print("-" * 50)

    print("\n=== ROUTINE RUN COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_routine()