import zmq
import time
import json

def run_drone_simulator():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    # O drone "publica" na porta 5555
    socket.bind("tcp://*:5555")

    print("🛸 Mock Drone iniciado. Enviando telemetria...")

    while True:
        # Simulando uma mensagem que o seu JSON de mapeamento usará depois
        telemetry = {
            "msg_id": 33, # GLOBAL_POSITION_INT no MAVLink
            "lat": -31.32,
            "lon": -54.10,
            "alt": 100.5
        }
        
        # Convertendo para string/bytes para simular o tráfego de rede
        message = json.dumps(telemetry)
        socket.send_string(message)
        
        print(f"Enviado: {message}")
        time.sleep(1)

if __name__ == "__main__":

