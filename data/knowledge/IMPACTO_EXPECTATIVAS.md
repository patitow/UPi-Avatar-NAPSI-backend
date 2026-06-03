# Impacto das expectativas ACI/NAPSI no UPi

Fonte processada: `Respostas -ACI napsi.pdf` → `napsi_expectativas_aci.txt`.

## O que foi filtrado (válido)

| Trecho do questionário | Uso no projeto |
|------------------------|----------------|
| Calouros: ritmo acadêmico, nivelamento mat/física, pressão de provas | RAG + quebra-gelos; respostas sobre nivelamento e acolhimento em provas |
| Demandas frequentes: ambiente separado, tempo extra, ansiedade na semana de provas | Intent `services`/RAG; fallbacks e fluxo de sugestões |
| TEA: ruído, comunicação clara, conscientização docente/discente | RAG `tea` + PAI; não inventar adaptações sem laudo |
| Segunda chamada, abono, acompanhamento especial | Orientar NAPSI + Escolaridade; **não** inventar normas |
| Canais: Escolaridade e-mail/presencial | Respostas citam Escolaridade para trâmites acadêmicos e NAPSI para inclusão/psicossocial |

## O que não entrou (inválido ou fora de escopo)

- “Não consigo pensar agora” sobre adaptação ao ambiente → ignorado.
- “Não sei se é dúvida dos estudantes” (item 4) → tratado como **hipótese** do NAPSI, não como fato auditado.
- Detalhes legais de segunda chamada/abono sem texto oficial no PDF → UPi só **encaminha**, não legisla.

## Como altera cada camada do serviço

| Camada | Alteração |
|--------|-----------|
| `intent` + `ai_service` | Rota **crisis** (CVV 188 + SAMU 192) antes de acolhimento leve |
| `data/knowledge/napsi_redes_apoio.txt` | Redes de emergência e papéis institucionais |
| `data/napsi_info.txt` | Seções calouros, provas/adaptações, canais Escolaridade vs NAPSI |
| `data/knowledge/*.txt` | Corpus RAG (Chroma) após `scripts/rebuild_knowledge.py` |
| `intent.py` | Hints e snippets para provas, acolhimento, calouros |
| `upi_prompts.py` | Regras: semana de provas, não inventar normas, Escolaridade |
| `ai_service.py` | Carrega todos os `.txt` de `data/knowledge/` no seed |
| `conversationFlows.ts` | Sugestões alinhadas às demandas frequentes |
| Cache semântico | Limpar após rebuild (`dev_semantic_cache.json`) |

## Treinamento (reindexação)

```bash
cd UPi-Avatar-NAPSI-backend
python scripts/rebuild_knowledge.py
# Reiniciar uvicorn
```
