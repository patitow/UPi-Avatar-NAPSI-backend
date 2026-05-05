import requests
import time

questions = [
    'Quem é você?',
    'Quem você é?',
    'O que o NAPSI faz?',
    'Qual o horário de atendimento do NAPSI?',
    'Como posso entrar em contato com vocês?',
    'Onde fica a POLI/UPE?',
    'Vocês dão apoio psicológico?',
    'Qual o email do NAPSI?',
    'Quem pode usar o NAPSI?',
    'O UPi é um robô?'
]

print("Iniciando bateria de 10 testes...")

for q in questions:
    print(f"\nPergunta: {q}")
    start = time.time()
    try:
        r = requests.post('http://localhost:8000/chat', json={'message': q}, timeout=180).json()
        duration = time.time() - start
        print(f"Tempo: {duration:.2f}s")
        print(f"Resposta: {r.get('response')}")
        print(f"Emoção: {r.get('emotion')}")
    except Exception as e:
        print(f"Erro no teste: {e}")

print("\n--- Fim dos testes ---")
