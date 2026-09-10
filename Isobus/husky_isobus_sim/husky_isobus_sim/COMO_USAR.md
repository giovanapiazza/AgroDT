# Como usar

Execute os comandos na pasta principal do projeto.

## Primeira execução


python3 scripts/preflight.py
python3 scripts/setup_all.py


## Iniciar a simulação

### Terminal 1 — Husky e Gazebo


python3 scripts/start_simulation.py


### Terminal 2 — criar a vCAN


sudo python3 scripts/setup_vcan.py


### Terminal 2 — ponte Husky para ISOBUS


python3 scripts/start_bridge.py


### Terminal 3 — monitor da vCAN


python3 scripts/monitor_vcan.py


### Terminal 4 — drone PX4 X500


python3 scripts/start_drone.py


### Terminal 5 — missão do drone


python3 scripts/start_drone_mission.py


## Verificar o sistema


python3 scripts/check_all.py


## Encerrar tudo


python3 scripts/stop_all.py



As explicações e soluções de problemas estão no `README.md`.
