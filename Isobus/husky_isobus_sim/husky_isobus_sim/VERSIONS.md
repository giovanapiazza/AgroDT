# Dependências fixadas

- PX4-Autopilot: v1.17.0
- px4_msgs: release/1.17
- Micro-XRCE-DDS-Agent: v2.4.3
- ROS 2: Jazzy
- Gazebo: Harmonic
- Clearpath simulator: pacote Debian ros-jazzy-clearpath-simulator

As três versões PX4/DDS acima foram escolhidas para manter as definições ROS 2 alinhadas com a versão estável do PX4 e com Fast DDS 2.14 usado pelo ROS 2 Jazzy.

- Correção ros2_control: Gazebo iniciado via `ros_gz_sim gz_sim.launch.py` para preservar caminhos de plugins ROS/Gazebo.
- Compatibilidade DDS: detecção automática de tópicos PX4 versionados (`_vN`) no PX4 v1.17.
- PX4 runtime: inicialização direta de `build/px4_sitl_default/bin/px4`; setup preserva build funcional e repara submódulos apenas quando necessário.
- Configuração: o mundo usado pelo drone agora é lido de `config/drone.yaml`, sem nome fixo no script.
- J1939/ISO 11783: validação de PGNs PDU1 e descarte seguro de payloads inválidos no monitor CAN.
- Diagnóstico: `scripts/preflight.sh` verifica dependências, YAML e metadados ROS antes da simulação.
