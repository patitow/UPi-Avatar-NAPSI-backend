import asyncio
import edge_tts

async def main():

    communicate = edge_tts.Communicate(
        "Olá, eu sou o UPi.",
        voice="pt-BR-BrendaNeural"
    )

    await communicate.save("teste.mp3")

asyncio.run(main())