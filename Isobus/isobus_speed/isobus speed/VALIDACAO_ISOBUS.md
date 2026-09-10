# Validação técnica da demonstração

## Identificação das ECUs pelo NAME

### Tractor ECU

| Campo | Valor usado |
|---|---:|
| Arbitrary Address Capable | `1` |
| Industry Group | `2` — Agricultural and Forestry Equipment |
| Device Class | `0` — Non-specific System |
| Function | `134` — Tractor ECU |
| Preferred Address | `0xF0` |
| Manufacturer Code | `1407` — permitido pela Open-Agriculture para demonstrações não comerciais |
| Identity Number | `1001` |

A combinação `Device Class 1 + Function 134` não representa a TECU; nessa classe, o código 134 representa Center Hitch Control. Por isso a TECU foi configurada com Device Class 0.

### Pulverizador

| Campo | Valor usado |
|---|---:|
| Arbitrary Address Capable | `1` |
| Industry Group | `2` |
| Device Class | `6` — Sprayer |
| Function | `128` — Rate Control |
| Preferred Address | `0x90` |
| Manufacturer Code | `1407` |
| Identity Number | `2001` |

A combinação anterior `Sprayer + ProductDosing (136)` seria interpretada como a função 136 da classe Sprayer, isto é, Frame Control. O controle de taxa do pulverizador deve usar a função 128.

## PGN transmitido

| Propriedade | Valor |
|---|---:|
| Nome | Machine Selected Speed |
| PGN decimal | `61474` |
| PGN hexadecimal | `0xF022` |
| Comprimento | `8 bytes` |
| Prioridade | `3` |
| Periodicidade | aproximadamente `100 ms` |
| Endereçamento | PDU2 / broadcast |

## Codificação feita pela AgIsoStack++

A biblioteca monta os bytes da seguinte forma:

```text
B1 = velocidade & 0xFF
B2 = velocidade >> 8
B3 = distância & 0xFF
B4 = distância >> 8
B5 = distância >> 16
B6 = distância >> 24
B7 = 0xC0 | exit_reason
B8 = direction | (speed_source << 2) | (limit_status << 5)
```

Nesta demonstração:

```text
speed_source = 4  -> Simulated
direction    = 1  -> Forward, ou 0 -> Reverse
limit_status = 0  -> Not Limited
exit_reason  = 0  -> No Reason / All Clear
```

Logo, para movimento para frente, o byte 8 é:

```text
1 | (4 << 2) | (0 << 5) = 0x11
```

Para marcha a ré:

```text
0 | (4 << 2) | (0 << 5) = 0x10
```

## Exemplo calculado

Para `8 km/h`:

```text
8 / 3,6 = 2,222... m/s
2,222... m/s = 2222 mm/s
2222 decimal = 0x08AE
```

Para uma distância de `100 m`:

```text
100 m = 100000 mm
100000 decimal = 0x000186A0
```

Mensagem para frente, fonte simulada:

```text
AE 08 A0 86 01 00 C0 11
```

Com endereço de origem `0xF0`, prioridade 3 e PGN `0xF022`, o identificador CAN é:

```text
0x0CF022F0
```

## Rollover da distância

O maior valor válido utilizado é:

```text
4.211.081.215 mm
```

O contador é reiniciado no valor seguinte, evitando transmitir valores da faixa reservada. O programa conserva a parte fracionária do cálculo em um acumulador `double` e transmite apenas a parte inteira em milímetros.

## Limites desta demonstração

O código demonstra corretamente:

- SocketCAN;
- duas ECUs virtuais;
- ISO 11783 Address Claim pela AgIsoStack++;
- NAME coerente para TECU e controle de taxa de pulverizador;
- recepção e transmissão do PGN Machine Selected Speed;
- velocidade, distância, direção, fonte, limit status e exit reason;
- detecção de perda da mensagem periódica.

O código não pretende implementar:

- uma TECU completa;
- todos os PGNs definidos na ISO 11783-7;
- Virtual Terminal;
- Task Controller;
- DDOP;
- TIM;
- diagnóstico completo;
- mensagens padronizadas de controle de taxa ou seções.

O cálculo de `L/min` e a ativação visual das seis seções acontecem apenas dentro do processo do pulverizador para demonstrar como um implemento pode consumir a velocidade recebida.
