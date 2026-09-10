# Rigs of Rods -> ISOBUS

Esta demonstracao recebe a telemetria **OutGauge** do Rigs of Rods por UDP e a converte para o PGN ISOBUS `0xF022` (Machine Selected Speed and Distance) na interface `can0`.

## Estrutura esperada

```text
~/AgroDT/Isobus/
├── AgIsoStack-plus-plus/
└── ror_isobus_game_demo/
```

## 1. Corrigir o OutGauge no Linux

O codigo atual do jogo deixa o envio OutGauge desativado no Linux. Rode:

```bash
cd ~/AgroDT/Isobus/ror_isobus_game_demo
./patch_ror_outgauge_linux.py
```

Se o jogo estiver em outro diretorio, localize o arquivo:

```bash
find ~ -path '*/source/main/network/OutGauge.cpp' -print
```

E passe o caminho encontrado:

```bash
./patch_ror_outgauge_linux.py /caminho/do/jogo/source/main/network/OutGauge.cpp
```

Recompile apenas a alteracao:

```bash
cd ~/rigs-of-rods-source/rigs-of-rods
ninja -C build -j4
```

O script cria o backup `OutGauge.cpp.before-isobus`.

## 2. Configurar o jogo

No Rigs of Rods, abra as configuracoes de controles/telemetria e use:

```text
Enable OutGauge protocol: ligado
OutGauge IP: 127.0.0.1
OutGauge Port: 1355
OutGauge ID: 0
OutGauge delay: 1.000
```

Ou edite `~/.rigsofrods/config/RoR.cfg` e defina:

```text
OutGauge Mode=1
OutGauge IP=127.0.0.1
OutGauge Port=1355
OutGauge Delay=1.000000
OutGauge ID=0
```

Feche o jogo antes de editar o arquivo.

## 3. Compilar a ponte

```bash
cd ~/AgroDT/Isobus/ror_isobus_game_demo
./build_demo.sh
```

## 4. Executar

Terminal 1:

```bash
cd ~/AgroDT/Isobus/ror_isobus_game_demo
./setup_can.sh
./build/ror_to_isobus
```

Terminal 2:

```bash
cd ~/AgroDT/Isobus/ror_isobus_game_demo
./build/sprayer_sim
```

Terminal 3:

```bash
candump -tz can0
```

Agora abra o jogo, entre em um veiculo com motor e dirija. A ponte mostrara velocidade, RPM, marcha, acelerador e freio. A velocidade e a distancia serao publicadas no ISOBUS.

Nao execute `tractor_sim` ao mesmo tempo, pois `ror_to_isobus` ja representa a TECU do trator.

## Teste somente do UDP

Para verificar a telemetria sem abrir `can0`:

```bash
cd ~/AgroDT/Isobus/ror_isobus_game_demo
./outgauge_monitor.py
```

Depois abra o jogo e dirija. Pare o monitor antes de iniciar `ror_to_isobus`, porque somente um deles deve ocupar a porta UDP 1355.
