# AgroDT — Gazebo, Husky, ISOBUS e drone PX4

Simulação preparada para Ubuntu 24.04, ROS 2 Jazzy e Gazebo Harmonic.

A inicialização foi desacoplada:

- **Gazebo** abre sozinho e já carrega um campo agrícola com 4 talhões de milho em disposição 2×2, separados por corredores;
- **Husky A200** é inserido apenas quando `start_husky.py` é executado;
- **PX4 X500** é inserido apenas quando `start_drone.py` é executado;
- o **executor de missões** recebe JSON por ROS 2 e envia `TrajectorySetpoint` ao PX4.

## Estrutura principal

```text
config/
  simulation.yaml
  drone.yaml
  mission_test.json
worlds/
  AgroDTField.sdf
ros2_ws/src/
  drone_offboard/
  husky_isobus_bridge/
scripts/
  start_simulation.py
  start_husky.py
  start_drone.py
  start_drone_mission.py
  send_drone_mission.py
  start_bridge.py
  monitor_vcan.py
  stop_all.py
```

## 1. Primeira preparação

Dentro da pasta que contém `config`, `worlds`, `ros2_ws` e `scripts`:

```bash
python3 scripts/preflight.py
python3 scripts/setup_all.py
```

Depois de alterações no pacote ROS 2:

```bash
python3 scripts/build.py
```

## 2. Abrir apenas o Gazebo

Terminal 1:

```bash
python3 scripts/start_simulation.py
```

O mundo `AgroDTField` abre com solo marrom, muretas escuras e **4 talhões de milho em disposição 2×2**, separados por corredores centrais. Cada talhão possui 20 plantas, totalizando 80 plantas.

Esse comando não inicia Husky nem drone.

## 3. Inserir o Husky separadamente

Com o Gazebo já aberto:

```bash
python3 scripts/start_husky.py
```

Para usar ISOBUS/vCAN:

```bash
sudo python3 scripts/setup_vcan.py
python3 scripts/start_bridge.py
python3 scripts/monitor_vcan.py
```

## 4. Inserir o drone separadamente

Com o Gazebo já aberto:

```bash
python3 scripts/start_drone.py
```

O script inicia o Micro XRCE-DDS Agent quando necessário e conecta o PX4 SITL ao X500 no mundo já aberto.

## 5. Iniciar o receptor de missões

Em outro terminal:

```bash
python3 scripts/start_drone_mission.py
```

Ele assina:

```text
/agrodt/drone/mission
```

e publica progresso em:

```text
/agrodt/drone/mission_status
```

## 6. Enviar a missão de teste

Em outro terminal:

```bash
python3 scripts/send_drone_mission.py config/mission_test.json
```

A missão de exemplo sobe o X500 e faz uma varredura sobre os quatro talhões, aproximadamente 4 m acima da origem local, e ao terminar solicita pouso.

Os waypoints usam o frame local NED do PX4:

- `x` e `y`: posição local em metros;
- `z` negativo: altura acima da origem;
- `yaw`: orientação em radianos.

Como o X500 é criado no lado sudoeste do campo, os waypoints do arquivo de teste foram ajustados para cobrir os quatro talhões e os corredores do novo layout.

## 7. Formato da missão

```json
{
  "version": 1,
  "type": "mission.upload",
  "mission_id": 1,
  "device": {
    "id": "uav-01",
    "frame": "LOCAL_NED"
  },
  "payload": {
    "command": "start_mission",
    "tolerance_m": 0.6,
    "hold_seconds": 1.0,
    "auto_land": true,
    "waypoints": [
      {"x": 0.0, "y": 0.0, "z": -4.0, "yaw": 0.0},
      {"x": 2.0, "y": 1.5, "z": -4.0, "yaw": 0.0}
    ]
  }
}
```

## 8. Status da missão

O executor publica mensagens JSON como:

```json
{"mission_id":1,"status":"accepted","waypoint_count":7}
{"mission_id":1,"status":"started"}
{"mission_id":1,"status":"waypoint_reached","waypoint":1}
{"mission_id":1,"status":"landing"}
{"mission_id":1,"status":"completed","command":"end_mission"}
```

Para observar:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 topic echo /agrodt/drone/mission_status
```

## 9. Diagnóstico

```bash
python3 scripts/check_all.py
```

Cada componente pode aparecer como ativo ou não iniciado, pois Gazebo, Husky e drone são independentes.

Logs:

```text
.runtime/gazebo.log
.runtime/clock.log
.runtime/husky_spawn.log
.runtime/px4.log
.runtime/dds_agent.log
```

## 10. Encerrar

```bash
python3 scripts/stop_all.py
```

## Ordem recomendada para demonstração com drone

```bash
# Terminal 1
python3 scripts/start_simulation.py

# Terminal 2
python3 scripts/start_drone.py

# Terminal 3
python3 scripts/start_drone_mission.py

# Terminal 4
python3 scripts/send_drone_mission.py config/mission_test.json
```

O Husky é opcional e pode ser iniciado em outro terminal, depois do Gazebo.


## Reparar PX4 sem gz_bridge

Se `start_drone.py` informar que a build do PX4 não contém `gz_bridge`, execute uma vez:

```bash
python3 scripts/repair_px4.py
```

Esse comando sincroniza o PX4 v1.17.0, executa o instalador oficial de dependências para Ubuntu/Gazebo Harmonic, remove a configuração SITL antiga e recompila `px4_sitl`.

Depois:

```bash
python3 scripts/start_drone.py
```

O erro fatal correspondente é:

```text
px4-rc.gzsim: gz_bridge: not found
ERROR [init] gz_bridge failed to start and spawn model
```

Os avisos sobre parâmetros `SIM_GZ_*` que podem aparecer antes disso não são a causa desse encerramento.
