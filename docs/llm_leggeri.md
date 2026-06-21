# Modelli LLM leggeri

I modelli piccoli sono veloci e richiedono meno memoria, ma possono produrre nomi o sintesi meno
precisi. Per email tecniche ambientali in italiano conviene iniziare almeno da `qwen2.5:1.5b`.

- I modelli da 135M e 360M sono soprattutto strumenti di test.
- I modelli da 1B-1.7B sono adatti a PC modesti e controlli brevi.
- I modelli da 3B-4B migliorano generalmente la qualità, usando più memoria e tempo.
- Su dispositivi mobili è preferibile un modello GGUF quantizzato.
- Ollama è la soluzione più semplice su PC; llama.cpp/GGUF è la modalità avanzata.

Il programma non scarica modelli automaticamente. Ogni `ollama pull` richiede conferma esplicita.
