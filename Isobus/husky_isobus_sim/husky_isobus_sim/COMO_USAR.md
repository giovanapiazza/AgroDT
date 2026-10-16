# Como usar

## Preparação inicial

```bash
python3 scripts/preflight.py
python3 scripts/setup_all.py
```

Depois de alterações no código ROS 2:

```bash
python3 scripts/build.py
```

## Gazebo com plantação

### Terminal 1

```bash
python3 scripts/start_simulation.py
```

Abre somente o mundo `AgroDTField`, com 3 blocos de milho. Cada bloco possui 2 fileiras próximas, com um corredor maior entre os blocos.

## Husky

### Terminal 2

```bash
python3 scripts/start_husky.py
```

Aguarde aparecer:

```text
[OK] HUSKY PRONTO
```

## Missão automática do Husky

A missão padrão está em:

```text
config/mission_husky.json
```

Ela faz o Husky sair da posição inicial, acessar o corredor acima da plantação e atravessar para o outro lado usando a odometria.

### Terminal 3 — iniciar o executor da missão

```bash
python3 scripts/start_husky_mission.py
```

O esperado é:

```text
Executor do Husky pronto. Aguardando JSON em /agrodt/husky/mission
```

### Terminal 4 — enviar a missão

```bash
python3 scripts/send_husky_mission.py config/mission_husky.json
```

A missão é publicada em:

```text
/agrodt/husky/mission
```

e o progresso em:

```text
/agrodt/husky/mission_status
```

### Terminal 5 — acompanhar o status

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 topic echo /agrodt/husky/mission_status
```

A sequência esperada é:

```text
accepted
started
waypoint_reached
waypoint_reached
waypoint_reached
completed
```

O executor usa:

```text
/a200_0000/platform/odom
```

para saber a posição do Husky e:

```text
/a200_0000/platform/cmd_vel
```

para comandar o movimento.

## Ordem completa da missão do Husky

### Terminal 1

```bash
python3 scripts/start_simulation.py
```

### Terminal 2

```bash
python3 scripts/start_husky.py
```

### Terminal 3

```bash
python3 scripts/start_husky_mission.py
```

### Terminal 4

```bash
python3 scripts/send_husky_mission.py config/mission_husky.json
```

### Terminal 5 — opcional

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 topic echo /agrodt/husky/mission_status
```

## ISOBUS / vCAN do Husky

```bash
sudo python3 scripts/setup_vcan.py
python3 scripts/start_bridge.py
python3 scripts/monitor_vcan.py
```

## Drone

```bash
python3 scripts/start_drone.py
```

Executor e envio da missão:

```bash
python3 scripts/start_drone_mission.py
python3 scripts/send_drone_mission.py config/mission_test.json
```

Para acompanhar:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 topic echo /agrodt/drone/mission_status
```

## Diagnóstico e encerramento

```bash
python3 scripts/check_all.py
python3 scripts/stop_all.py
```
