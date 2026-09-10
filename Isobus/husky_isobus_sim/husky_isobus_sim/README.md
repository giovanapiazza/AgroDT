# Husky, ISOBUS e drone PX4

Este guia corresponde à versão dos comandos em Python, preparada para:

- Ubuntu 24.04;
- ROS 2 Jazzy;
- Gazebo Harmonic;
- Husky A200 da Clearpath;
- SocketCAN `vcan0`;
- PX4 v1.17.0 e drone X500.

## 1. Estrutura esperada

Execute os comandos dentro da pasta que contém diretamente `config`,
`ros2_ws`, `scripts` e `third_party`:

```text
husky_isobus_sim/
├── config/
├── ros2_ws/
├── scripts/
├── third_party/
└── COMO_USAR_COMPLETO.md
```

No seu computador, confirme a pasta com:

```bash
cd /home/giovana-piazza/AgroDT/Isobus/husky_isobus_sim/husky_isobus_sim
pwd
ls
```

Não execute os programas de dentro da pasta `scripts`.

## 2. Preparação inicial

Verifique as dependências:

```bash
python3 scripts/preflight.py
```

Na primeira instalação, execute uma vez:

```bash
python3 scripts/setup_all.py
```

Esse processo instala as dependências, prepara o PX4, compila o workspace ROS
e mantém os resultados nas pastas `third_party` e `ros2_ws/install`.

Depois de concluído, normalmente não será necessário executar o setup novamente.

## 3. Iniciar o Husky no Gazebo

Feche simulações anteriores:

```bash
python3 scripts/stop_all.py
```

No Terminal 1:

```bash
python3 scripts/start_simulation.py
```

Espere aparecer:

```text
[OK] mundo 'AgrobotScene' carregado.
[OK] controller_manager encontrado.
[OK] AGROBOTSCENE + HUSKY PRONTOS
```

Mantenha o Terminal 1 aberto.

## 4. Abrir a barra lateral de controle no Gazebo

O programa carrega a configuração gráfica da Clearpath e configura o painel
`Teleop` para publicar em:

```text
/a200_0000/cmd_vel
```

### Se o painel já estiver visível

Procure, normalmente no lado direito da janela, o painel chamado **Teleop**.
Use os botões direcionais para:

- avançar;
- recuar;
- virar à esquerda;
- virar à direita;
- parar.

Comece com velocidades pequenas, por exemplo `0.3 m/s` linear e `0.5 rad/s`
angular.

### Se a barra lateral estiver fechada

1. Na janela do Gazebo, vá ao canto superior direito.
2. Clique no menu de plugins — o ícone pode aparecer como três pontos ou como
   um menu suspenso, dependendo do tema.
3. Procure **Teleop**.
4. Clique em **Teleop** para adicionar ou reabrir o painel lateral.
5. Confirme que o tópico exibido é `/a200_0000/cmd_vel`.

O Gazebo permite adicionar painéis pelo menu de plugins no canto superior
direito. Se o painel for fechado pelo `X`, ele pode ser adicionado novamente
pelo mesmo menu.

### Se Teleop não aparecer na lista

Feche tudo:

```bash
python3 scripts/stop_all.py
```

Confirme que a configuração gráfica foi gerada:

```bash
ls .runtime/gui_agrobot_scene.config
grep -A 12 -B 2 'filename="Teleop"' .runtime/gui_agrobot_scene.config
```

Inicie novamente:

```bash
python3 scripts/start_simulation.py
```

## 5. Controle manual alternativo pelo terminal

Se o painel Teleop não funcionar, controle o Husky por um segundo terminal.

Avançar:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash

ros2 topic pub /a200_0000/cmd_vel \
  geometry_msgs/msg/TwistStamped \
  '{"twist":{"linear":{"x":0.3},"angular":{"z":0.0}}}' \
  -r 20
```

Pare o comando contínuo com `Ctrl+C` e envie velocidade zero:

```bash
ros2 topic pub --once /a200_0000/cmd_vel \
  geometry_msgs/msg/TwistStamped \
  '{"twist":{"linear":{"x":0.0},"angular":{"z":0.0}}}'
```

Valores de referência:

| Movimento | `linear.x` | `angular.z` |
|---|---:|---:|
| Frente | `+0.3` | `0.0` |
| Ré | `-0.3` | `0.0` |
| Esquerda | `0.0` | `+0.5` |
| Direita | `0.0` | `-0.5` |
| Parar | `0.0` | `0.0` |

## 6. Conferir se o Husky realmente se moveu

Em outro terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 topic echo /a200_0000/platform/odom --field twist.twist
```

O teste passou quando:

1. o Husky se move visualmente no Gazebo;
2. `/a200_0000/platform/odom` possui publicador;
3. `linear.x` ou `angular.z` muda durante o movimento.

## 7. Iniciar a comunicação Husky → vCAN

Crie a interface virtual uma vez após cada reinicialização do Ubuntu:

```bash
sudo python3 scripts/setup_vcan.py
```

No Terminal 2:

```bash
python3 scripts/start_bridge.py
```

No Terminal 3:

```bash
python3 scripts/monitor_vcan.py
```

O monitor deve mostrar o movimento decodificado, CAN ID, PGN, velocidades e
payload recebido da `vcan0`.

## 8. Iniciar o drone X500

O mundo e o Husky precisam estar ativos primeiro.

No Terminal 4:

```bash
python3 scripts/start_drone.py
```

O esperado é:

```text
[1/3] Iniciando Micro XRCE-DDS Agent UDP 8888...
[2/3] Iniciando PX4 v1.17.0...
[3/3] PX4 + DDS conectados.
[OK] DRONE X500 PRONTO
```

O programa mostra atualizações enquanto aguarda o DDS. Se o PX4 encerrar, as
últimas linhas de `.runtime/px4.log` são mostradas automaticamente.

## 9. Fazer o drone decolar

No Terminal 5:

```bash
python3 scripts/start_drone_mission.py
```

A missão faz o X500 subir até a altura configurada em `config/drone.yaml`,
pairar e pousar.

## 10. Diagnóstico geral

```bash
python3 scripts/check_all.py
```

Logs importantes:

```text
.runtime/gazebo.log
.runtime/husky_spawn.log
.runtime/clock.log
.runtime/px4.log
.runtime/dds_agent.log
```

Se aparecer `[ERRO] /clock indisponível`, a versão atual detecta
automaticamente tanto `/clock` quanto `/world/AgrobotScene/clock` no Gazebo e
mostra o log da ponte caso ela não consiga iniciar.

Para acompanhar o PX4 em tempo real:

```bash
tail -f .runtime/px4.log
```

## 11. Encerrar a simulação

```bash
python3 scripts/stop_all.py
```

Execute esse comando antes de iniciar uma nova simulação, especialmente se o
Gazebo informar que já existe um mundo ativo.

## 12. Ordem resumida dos terminais

| Terminal | Comando |
|---|---|
| 1 | `python3 scripts/start_simulation.py` |
| 2 | `python3 scripts/start_bridge.py` |
| 3 | `python3 scripts/monitor_vcan.py` |
| 4 | `python3 scripts/start_drone.py` |
| 5 | `python3 scripts/start_drone_mission.py` |

Antes dos Terminais 2 e 3, crie a `vcan0` com:

```bash
sudo python3 scripts/setup_vcan.py
```
