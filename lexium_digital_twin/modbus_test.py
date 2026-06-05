from pymodbus.client import ModbusTcpClient
import struct
import time

client = ModbusTcpClient("10.5.5.100", port=6502)

if not client.connect():
    print("Connection failed")
    exit()

def regs_to_float(reg1, reg2):
    # Big-endian word order
    raw = struct.pack(">HH", reg1, reg2)
    return struct.unpack(">f", raw)[0]

try:
    while True:

        result = client.read_input_registers(
            address=382,
            count=12,
            device_id=0
        )

        if not result.isError():

            regs = result.registers

            positions = []

            for i in range(0, 12, 2):
                positions.append(
                    regs_to_float(regs[i], regs[i+1])
                )

            print(
                f"J1={positions[0]:8.2f}°  "
                f"J2={positions[1]:8.2f}°  "
                f"J3={positions[2]:8.2f}°  "
                f"J4={positions[3]:8.2f}°  "
                f"J5={positions[4]:8.2f}°  "
                f"J6={positions[5]:8.2f}°"
            )

        time.sleep(0.1)

except KeyboardInterrupt:
    pass

finally:
    client.close()