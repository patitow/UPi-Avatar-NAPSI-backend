# Checklist — o que já está coberto e o que falta

## Já integrado no UPi

- [x] Missão, local, horário, e-mail NAPSI (`napsi_info.txt`)
- [x] Serviços, TEA/PAI, adaptações em provas, laudo
- [x] Expectativas ACI (calouros, semana de provas, Escolaridade vs NAPSI)
- [x] Redes CVV 188, SAMU 192, CAPS (`napsi_redes_apoio.txt`)
- [x] Rotas fixas: saudação, acolhimento (`distress`), crise (`crisis`)
- [x] Monitoria voluntária (menção em redes_apoio — fonte pública ABENGE)
- [x] Quebra-gelos alinhados no front (`conversationFlows.ts`)

## Validar com o NAPSI antes de afirmar ao aluno

- [ ] Telefone oficial atualizado da POLI/NAPSI (não fixamos número sem confirmação)
- [ ] Passo a passo oficial de segunda chamada e abono (Manual do Estudante / Escolaridade)
- [ ] Prazos e documentos exatos para tempo adicional / ambiente separado
- [ ] Lista de disciplinas do Programa de Nivelamento

## Fontes externas úteis (não ingeridas automaticamente)

- Site www.poli.br — seção NAPSI (PDFs institucionais → `data/sources/` + `rebuild_knowledge.py`)
- Manual do Estudante UPE/POLI (trechos sobre adaptações, se autorizado)
- Novos questionários ACI → `data/knowledge/napsi_expectativas_aci.txt` ou arquivo novo

## Operação após mudanças

1. `python scripts/rebuild_knowledge.py` (com uvicorn parado para reindex limpa)
2. Reiniciar backend
3. `python scripts/audit_conduct_cases.py` (com API no ar)
4. `npm run test:e2e` no front (backend em `:8000`)
