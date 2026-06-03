# Revisão do Projeto — UPi Backend (ACI/UPE)

## Objetivo
Desenvolver o backend de um assistente virtual (avatar) para o NAPSI/UPE, demonstrando a aplicação prática de técnicas de IA: RAG, cache semântico vetorial e orquestração de LLMs.

## Arquitetura

```
Usuário → FastAPI → AIService
                        ├── Redis (cache semântico via RedisVL)
                        ├── PGVector (RAG)
                        ├── OllamaEmbeddings (vetorização local)
                        └── OpenAI GPT-4o-mini → fallback ChatOllama llama3.2:3b
```

## Técnicas de IA Aplicadas

| Técnica | Implementação |
|---|---|
| RAG (Retrieval-Augmented Generation) | LangChain + PGVector para busca semântica em documentos institucionais |
| Cache Semântico | RedisVL com busca por similaridade de vetores (threshold cosine < 0.12) |
| Embeddings Locais | OllamaEmbeddings (llama3.2:3b, 3072 dims) — sem envio a APIs externas |
| LLM Orquestrado | GPT-4o-mini com fallback automático para Ollama (llama3.2:3b) |
| Resposta Estruturada | JSON com campos `response` e `emotion` para controle do avatar |

## Decisões de Design

- **Fallback em dupla camada**: LLM (OpenAI → Ollama) e respostas por palavra-chave se o modelo estiver offline.
- **Cache semântico manual via RedisVL**: evita reprocessamento de perguntas semanticamente equivalentes, reduzindo custo de tokens e latência.
- **Personalidade regional**: system prompt com expressões pernambucanas para maior acolhimento dos estudantes.
- **JSON obrigatório na resposta**: permite ao frontend controlar o estado emocional do avatar de forma programática.

## Limitações e Trabalhos Futuros

- Histórico de conversa por `user_id` ainda não é persistido entre sessões.
- A base de conhecimento (`data/napsi_info.txt`) é estática; seria mais robusto ingerir documentos PDF diretamente do site da POLI/UPE.
- O threshold do cache semântico (0.12) foi definido empiricamente; validação com usuários reais pode indicar ajuste fino.
