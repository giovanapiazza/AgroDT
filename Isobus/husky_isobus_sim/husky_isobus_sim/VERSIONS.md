# Dependências fixadas

- Ubuntu: 24.04
- ROS 2: Jazzy
- Gazebo: Harmonic
- PX4-Autopilot: v1.17.0
- px4_msgs: release/1.17
- Micro-XRCE-DDS-Agent: v2.4.3
- Clearpath simulator: ros-jazzy-clearpath-simulator

## Arquitetura atual

- Mundo local: `worlds/AgroDTField.sdf`.
- Gazebo, Husky e PX4 X500 são iniciados separadamente.
- O Gazebo abre com 3 fileiras de milho sem depender de um repositório externo de mundo.
- O executor ROS 2 recebe missões JSON em `/agrodt/drone/mission`.
- O progresso é publicado em `/agrodt/drone/mission_status`.
- A execução dos waypoints usa `px4_msgs/TrajectorySetpoint`.
- A conclusão da missão publica `status=completed` e `command=end_mission`.
- Tópicos PX4 versionados (`_vN`) são detectados automaticamente.
