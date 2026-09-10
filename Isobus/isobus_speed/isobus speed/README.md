# Demonstração ISOBUS — Tractor ECU e pulverizador

Este projeto simula duas ECUs conectadas à mesma rede CAN virtual:

- **`tractor_sim`**: representa uma **Tractor ECU (TECU)** e transmite a mensagem padronizada **Machine Selected Speed**, PGN `61474` (`0xF022`), periodicamente.
- **`sprayer_sim`**: representa uma ECU de **controle de taxa de um pulverizador**, recebe o PGN de velocidade e calcula localmente a vazão necessária para manter `150 L/ha` em uma barra de `12 m`.

O projeto usa a biblioteca [AgIsoStack++](https://github.com/Open-Agriculture/AgIsoStack-plus-plus) e uma interface SocketCAN.

## O que foi corrigido nesta versão

- NAME da Tractor ECU configurado como:
  - Industry Group `2` — Agricultural and Forestry Equipment;
  - Device Class `0` — Non-specific System;
  - Function `134` — Tractor ECU.
- Endereço preferencial da Tractor ECU alterado para `0xF0`.
- NAME do pulverizador configurado como:
  - Industry Group `2`;
  - Device Class `6` — Sprayer;
  - Function `128` — Rate Control.
- Fonte da velocidade alterada para `Simulated`, pois o valor é digitado pelo usuário.
- Distância acumulada corrigida para reiniciar após o maior valor válido `4.211.081.215 mm`.
- Acumulador de distância passou a manter as frações de milímetro entre ciclos.
- Entrada negativa passou a representar marcha a ré usando o campo padronizado de direção.
- Removido o uso de `std::async` na reivindicação de endereço, evitando bloqueio em caso de timeout.
- Interface CAN configurável pela variável `ISOBUS_CAN_INTERFACE`.
- Adicionado decodificador dos 8 bytes do PGN para conferência manual.

## Escopo da conformidade

A mensagem transmitida é compatível com a codificação utilizada pela AgIsoStack++ para o PGN `61474`:

| Bytes | Conteúdo |
|---|---|
| 1–2 | Velocidade selecionada, little-endian, resolução de `1 mm/s` |
| 3–6 | Distância acumulada, little-endian, resolução de `1 mm` |
| 7 | Código de saída nos 6 bits inferiores; bits reservados em `1` |
| 8, bits 1–2 | Direção de deslocamento |
| 8, bits 3–5 | Fonte da velocidade |
| 8, bits 6–8 | Estado de limitação |

A AgIsoStack++ envia o PGN com prioridade `3` e período de aproximadamente `100 ms`.

> Este projeto é uma demonstração educacional do Address Claim e do PGN Machine Selected Speed. Ele não implementa todas as funções de uma TECU comercial, Virtual Terminal, Task Controller, TIM, diagnóstico completo ou controle de seções padronizado. A vazão e as seções mostradas no painel do pulverizador são uma lógica local da demonstração.

## Requisitos

Ubuntu ou outra distribuição Linux com:

```bash
sudo apt update
sudo apt install -y build-essential cmake git can-utils iproute2
```

A AgIsoStack++ deve estar instalada. Uma organização recomendada é:

```text
Isobus/
├── AgIsoStack-plus-plus/
└── isobus speed/
```

Caso a biblioteca esteja em outro lugar, informe o caminho:

```bash
export AGISOSTACK_DIR=/caminho/para/AgIsoStack-plus-plus
```

## 1. Preparar a CAN virtual

Dentro da pasta do projeto:

```bash
./setup_can.sh
```

Por padrão, o script cria ou ativa `can0`. Para usar outro nome:

```bash
./setup_can.sh vcan0
export ISOBUS_CAN_INTERFACE=vcan0
```

## 2. Compilar

```bash
./build_demo.sh
```

Se a AgIsoStack++ não estiver ao lado do projeto:

```bash
AGISOSTACK_DIR=/caminho/AgIsoStack-plus-plus ./build_demo.sh
```

Os executáveis serão criados em:

```text
build/tractor_sim
build/sprayer_sim
```

## 3. Executar

Abra três terminais na pasta do projeto.

### Terminal 1 — pulverizador

```bash
./build/sprayer_sim
```

### Terminal 2 — Tractor ECU

```bash
./build/tractor_sim
```

Digite valores como:

```text
0
4
8
12
20
-5
```

Valores positivos representam movimento para frente. Valores negativos representam marcha a ré. O valor `0` mantém a última direção transmitida, conforme o comportamento esperado para o campo de direção quando a máquina está parada.

### Terminal 3 — monitoramento do CAN

```bash
./monitor_can.sh
```

Com a TECU no endereço `0xF0`, o quadro do PGN deve aparecer normalmente com o identificador:

```text
0CF022F0
```

Se houver conflito de endereço, a ECU poderá reivindicar outro endereço porque está marcada como arbitrarily address capable.

## Conferir os bytes da mensagem

Exemplo correspondente aproximadamente a `8 km/h`, `100 m`, direção para frente, fonte simulada e sem limitação:

```text
AE 08 A0 86 01 00 C0 11
```

Decodifique com:

```bash
./decode_machine_selected_speed.py AE 08 A0 86 01 00 C0 11
```

Saída esperada:

```text
Velocidade         : 2222 mm/s (7.999 km/h)
Distancia          : 100000 mm (100.000 m)
Exit reason        : 0
Direcao            : Forward
Fonte              : Simulated
Limit status       : Not Limited
Bits reservados B7 : corretos (11b)
```

## Usar uma interface CAN física

Não execute `setup_can.sh` para criar uma interface virtual quando estiver usando hardware real. Configure a interface conforme o bitrate da rede e informe seu nome, por exemplo:

```bash
export ISOBUS_CAN_INTERFACE=can1
./build/sprayer_sim
```

O ISOBUS clássico trabalha sobre CAN com identificadores estendidos de 29 bits. A configuração elétrica, terminação, transceptor e bitrate da rede física devem estar corretos antes de conectar o computador ao barramento.

## Referências

- ISOBUS Data Dictionary: <https://www.isobus.net/isobus/>
- AgIsoStack++: <https://github.com/Open-Agriculture/AgIsoStack-plus-plus>
- Documentação da AgIsoStack++: <https://isobus-plus-plus.readthedocs.io/>
