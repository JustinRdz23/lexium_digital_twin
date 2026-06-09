import ssl, socket, json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def send_command(cmd_dict, port=10001):
    with socket.create_connection(('10.5.5.100', port)) as raw:
        with ctx.wrap_socket(raw) as s:
            s.send((json.dumps(cmd_dict) + "\n").encode())
            return json.loads(s.recv(4096).decode())

# First check current position
print(send_command({"cmdName": "get_joint_pos"}))

# Then send a SLOW move — only 5% speed
result = send_command({
    "cmdName":       "joint_move",
    "relFlag":       0,
    "jointPosition": [0.0, 90.0, 0.0, 90.0, 0.0, 0.0],
    "speed":         5.0,
    "accel":         5.0
})
print(result)