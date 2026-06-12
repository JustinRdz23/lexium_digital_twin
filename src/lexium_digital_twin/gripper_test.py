import ssl
import socket
import json
import time

# Host IP options from your setup
HOST = '192.168.1.252'
PORT = 10001

# DO6 is 0-indexed to index 5. type 0 = Cabinet IO.
DO6_INDEX = 5
IO_TYPE_CABINET = 0

# --- SSL Setup ---
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def send_raw_command(cmd_dict):
    """Establishes connection, dispatches the JSON command, and returns the parsed reply."""
    try:
        with socket.create_connection((HOST, PORT), timeout=5) as raw:
            with ctx.wrap_socket(raw) as s:
                payload = json.dumps(cmd_dict) + "\n"
                s.send(payload.encode())
                response = s.recv(4096).decode().strip()
                return json.loads(response)
    except Exception as e:
        return {"status": "error", "message": f"Socket failed: {e}"}

def test_gripper_do6():
    print(f"=== TESTING GRIPPER DIGITAL OUTPUT 6 ON {HOST} ===")
    
    # 1. Verify Connection first by getting current IO status
    print("\nReading initial digital input/output states...")
    state_check = send_raw_command({"cmdName": "get_digital_input_status"})
    print(f"Controller Status Query Response: {state_check}")
    
    # 2. Turn DO6 ON (Value = 1)
    print("\n[STEP 1] Activating Gripper (Setting DO6 to 1)...")
    cmd_on = {
        "cmdName": "set_digital_output",
        "type": IO_TYPE_CABINET,
        "index": DO6_INDEX,
        "value": 1
    }
    response_on = send_raw_command(cmd_on)
    print(f"Controller Response: {response_on}")
    
    print("--> Gripper should be ACTIVE/CLOSED now. Holding for 3 seconds...")
    time.sleep(3.0)
    
    # 3. Turn DO6 OFF (Value = 0)
    print("\n[STEP 2] Deactivating Gripper (Setting DO6 to 0)...")
    cmd_off = {
        "cmdName": "set_digital_output",
        "type": IO_TYPE_CABINET,
        "index": DO6_INDEX,
        "value": 0
    }
    response_off = send_raw_command(cmd_off)
    print(f"Controller Response: {response_off}")
    
    print("--> Gripper should be INACTIVE/OPEN now.")
    print("\n=== GRIPPER DO6 TEST COMPLETE ===")

if __name__ == "__main__":
    test_gripper_do6()