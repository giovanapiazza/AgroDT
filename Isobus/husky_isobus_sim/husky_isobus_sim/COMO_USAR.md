# Como usar

## Preparação inicial

```bash
python3 scripts/preflight.py
python3 scripts/setup_all.py
```

## Gazebo com plantação

```bash
python3 scripts/start_simulation.py
```

Abre somente o mundo `AgroDTField`, com 3 blocos de milho; cada bloco possui 2 fileiras próximas, com um corredor maior entre os blocos.

## Husky, opcional e separado

```bash
python3 scripts/start_husky.py
```

Para ISOBUS:

```bash
sudo python3 scripts/setup_vcan.py
python3 scripts/start_bridge.py
python3 scripts/monitor_vcan.py
```

## Drone, separado

```bash
python3 scripts/start_drone.py
```

## Executor e envio de missão

```bash
python3 scripts/start_drone_mission.py
python3 scripts/send_drone_mission.py config/mission_test.json
```

## Diagnóstico e encerramento

```bash
python3 scripts/check_all.py
python3 scripts/stop_all.py
```

Veja o `README.md` para detalhes sobre tópicos, formato JSON, waypoints e status da missão.
