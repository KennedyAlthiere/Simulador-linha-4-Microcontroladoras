print("main.py iniciou")
 
import time
from machine import Pin, PWM, time_pulse_us
 
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio
 
PIN_TRIG = 5
PIN_ECHO = 18
PIN_BUZZER = 19
 
PINOS_LEDS = [13, 14, 16, 17, 21, 22, 23, 25, 26, 27, 32]
 
LIMIAR_CM = 3
ALCANCE_MAX_CM = 200
AMOSTRAS = 5
INTERVALO_MS = 100
ALFA = 0.2
PARAR_AO_AFASTAR = True
DEPURAR = True
 
LED1_FIXO_MS = 15 * 1000
LED_PISCA_MS = 45 * 1000
LED_FIXO_MS = 15 * 1000
MUSICA_MS = 15 * 1000
PERIODO_PISCA_MS = 500
PAUSA_REPETICAO_MS = 400
 
PAUSA = 0
 
try:
    from musicas import MUSICAS
    print("musicas.py carregado: %d músicas" % len(MUSICAS))
except Exception as erro:
    print("ATENÇÃO: musicas.py não carregou (%s). Usando melodias de exemplo." % erro)
    MUSICAS = [
        ([(330, 1), (330, 1), (349, 1), (392, 1), (392, 1), (349, 1),
          (330, 1), (294, 1), (262, 1), (262, 1), (294, 1), (330, 1),
          (330, 1.5), (294, 0.5), (294, 2)], 120),
        ([(262, 1), (294, 1), (330, 1), (262, 1), (262, 1), (294, 1),
          (330, 1), (262, 1), (330, 1), (349, 1), (392, 2),
          (330, 1), (349, 1), (392, 2)], 130),
    ]
 
trig = Pin(PIN_TRIG, Pin.OUT)
echo = Pin(PIN_ECHO, Pin.IN)
trig.value(0)
 
buzzer = PWM(Pin(PIN_BUZZER), freq=1000, duty_u16=0)
leds = [Pin(p, Pin.OUT, value=0) for p in PINOS_LEDS]
 
def apagar_leds():
    for led in leds:
        led.value(0)
 
def medir_cm():
    """Uma medição. Retorna a distância em cm, ou None se não houver eco."""
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
 
    duracao = time_pulse_us(echo, 1, 30000)
    if duracao < 0:
        return None
    return duracao * 0.0343 / 2
 
async def distancia_filtrada():
    """Mediana de várias leituras para reduzir ruído."""
    leituras = []
    for _ in range(AMOSTRAS):
        d = medir_cm()
        if d is not None:
            leituras.append(d)
        await asyncio.sleep_ms(10)
 
    if not leituras:
        return ALCANCE_MAX_CM
    leituras.sort()
    return min(leituras[len(leituras) // 2], ALCANCE_MAX_CM)
 
async def tocar_musica_por(melodia, bpm, duracao_total_ms):
    """Toca a melodia (repetindo se preciso) por exatamente duracao_total_ms."""
    batida_ms = 60000 // bpm
    fim = time.ticks_add(time.ticks_ms(), duracao_total_ms)
    try:
        while True:
            for nota, batidas in melodia:
                duracao = int(batida_ms * batidas)
                som = int(duracao * 0.9)
 
                restante = time.ticks_diff(fim, time.ticks_ms())
                if restante <= 0:
                    return
                if nota != PAUSA:
                    buzzer.freq(nota)
                    buzzer.duty_u16(32768)
                await asyncio.sleep_ms(min(som, restante))
                buzzer.duty_u16(0)
 
                restante = time.ticks_diff(fim, time.ticks_ms())
                if restante <= 0:
                    return
                await asyncio.sleep_ms(min(duracao - som, restante))
 
            restante = time.ticks_diff(fim, time.ticks_ms())
            if restante <= 0:
                return
            await asyncio.sleep_ms(min(PAUSA_REPETICAO_MS, restante))
    finally:
        buzzer.duty_u16(0)
 
async def musica_no_fim_do_pisca(indice):
    """Espera até faltarem MUSICA_MS para o pisca acabar e então toca."""
    await asyncio.sleep_ms(LED_PISCA_MS - MUSICA_MS)
    melodia, bpm = MUSICAS[indice % len(MUSICAS)]
    print("Tocando música %d" % (indice % len(MUSICAS) + 1))
    await tocar_musica_por(melodia, bpm, MUSICA_MS)
 
async def piscar(led, duracao_ms):
    meio = PERIODO_PISCA_MS // 2
    fim = time.ticks_add(time.ticks_ms(), duracao_ms)
    estado = 0
    while True:
        restante = time.ticks_diff(fim, time.ticks_ms())
        if restante <= 0:
            break
        estado ^= 1
        led.value(estado)
        await asyncio.sleep_ms(min(meio, restante))
    led.value(0)
 
async def sequencia():
    tarefa_musica = None
    try:
 
        print("LED 1: fixo")
        leds[0].value(1)
        await asyncio.sleep_ms(LED1_FIXO_MS)
        leds[0].value(0)
 
        for numero in range(2, len(leds) + 1):
            led = leds[numero - 1]
 
            print("LED %d: piscando" % numero)
            tarefa_musica = asyncio.create_task(musica_no_fim_do_pisca(numero - 2))
            await piscar(led, LED_PISCA_MS)
            await tarefa_musica
            tarefa_musica = None
 
            print("LED %d: fixo" % numero)
            led.value(1)
            await asyncio.sleep_ms(LED_FIXO_MS)
            led.value(0)
 
        print("Sequência concluída.")
    finally:
        if tarefa_musica is not None:
            tarefa_musica.cancel()
        buzzer.duty_u16(0)
        apagar_leds()
 
async def principal():
    referencia = await distancia_filtrada()
    tarefa = None
 
    print("Pronto. Referência: %.1f cm. Aguardando aproximação..." % referencia)
 
    contador = 0
 
    while True:
        atual = await distancia_filtrada()
 
        if DEPURAR:
            contador += 1
            if contador % 5 == 0:
                print("atual: %.1f  referencia: %.1f" % (atual, referencia))
 
        ativo = tarefa is not None and not tarefa.done()
 
        if not ativo:
            if (referencia - atual) > LIMIAR_CM:
                print("Aproximação detectada a %.1f cm" % atual)
                tarefa = asyncio.create_task(sequencia())
            else:
                referencia += (atual - referencia) * ALFA
        else:
            if PARAR_AO_AFASTAR and (atual - referencia) > LIMIAR_CM:
                print("Algo se afastou. Sequência encerrada.")
                tarefa.cancel()
                tarefa = None
                referencia = atual
            else:
                referencia += (atual - referencia) * ALFA
 
        await asyncio.sleep_ms(INTERVALO_MS)
 
asyncio.run(principal())