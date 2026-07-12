# Benchmark di scalabilita

## Run di accettazione del 2026-07-12

Il benchmark usa esclusivamente email sintetiche locali generate da
`scripts/scalability_benchmark.py`. Gli artifact completi restano in
`.codex/runs/scale-20260712/` e non sono dati di prodotto.

Comando:

```powershell
& '.\.venv\Scripts\python.exe' scripts\scalability_benchmark.py --messages 10000 --run-dir .codex\runs\scale-20260712
```

Risultati:

| Metrica | Valore |
| --- | ---: |
| Messaggi richiesti/esportati | 10.000 / 10.000 |
| Conversazioni esportate | 5.000 |
| Tempo pipeline completa | 326,061 s |
| Picco memoria Python (`tracemalloc`) | 21,722 MiB |
| Dimensione workspace | 40,615 MiB |
| Stage completati | 12 / 12 |

La misurazione del picco riguarda le allocazioni Python tracciate e non il resident set
complessivo del processo. La run ha completato tutti gli stage senza errori di memoria.
I limiti `sample-size`, `limit-messages` e `limit-conversations` sono coperti dai test
automatici. I filtri data/cartella sono trasferiti nel task non bloccante
`EA-EPIC8-FILTERS`.
