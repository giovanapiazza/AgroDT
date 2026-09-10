#!/usr/bin/env python3
import socket
import struct

PORT = 1355
FORMAT = "<I4sHBB7fII3f16s16si"
SIZE = struct.calcsize(FORMAT)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
print(f"Aguardando OutGauge em UDP {PORT}; pacote esperado: {SIZE} bytes")

while True:
    data, address = sock.recvfrom(1024)
    if len(data) not in (92, 96):
        print(f"Pacote de {len(data)} bytes ignorado")
        continue
    data = data.ljust(96, b"\0")
    values = struct.unpack(FORMAT, data[:96])
    speed_mps = values[5]
    rpm = values[6]
    throttle = values[14]
    brake = values[15]
    gear = values[3]
    print(
        f"{address[0]} | {speed_mps * 3.6:6.1f} km/h | "
        f"{rpm:6.0f} RPM | gear={gear} | "
        f"acel={throttle * 100:5.1f}% | freio={brake * 100:5.1f}%"
    )
