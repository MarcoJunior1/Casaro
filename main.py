import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageChops
import threading
import queue
import time
import wave
import tempfile
import os
import edge_tts
import asyncio
import numpy as np
import sounddevice as sd
from groq import Groq
import speech_recognition as sr
from pydub import AudioSegment
import subprocess
import sys
import json
import base64
import hashlib
import keyboard
import math
import random
import datetime
import requests
import re


from src.rpg import CasaroRPGJanela
# ============================================================

def detectar_pedido_rpg(texto):
    """Detecta se o usuário quer jogar o RPG do Casaro."""
    gatilhos = [
        "quero jogar", "bora jogar", "vamos jogar",
        "jogar com você", "jogar com vc", "jogar contigo",
        "jogar o jogo", "abrir o jogo", "iniciar o jogo",
        "entrar no jogo", "jogar rpg", "rpg", "aventura",
        "jogar no seu mundo", "explorar seu mundo",
        "me leva pro jogo", "me leva ao jogo",
        "quero explorar", "quero uma aventura",
        "jogo do casaro", "mundo do casaro",
        "bora pro jogo", "quero jogar com o casaro",
        "abre o rpg", "abre o jogo",
        "me dá o jogo", "quero o jogo",
    ]
    t = texto.lower()
    return any(g in t for g in gatilhos)


def abrir_rpg(parent_app, groq_client):
    """Abre a janela do RPG."""
    try:
        CasaroRPGJanela(parent_app, groq_client)
    except Exception as e:
        print(f"[rpg] Erro ao abrir: {e}")
        import traceback; traceback.print_exc()

# ============================================================
# CONFIGURAÇÕES
# ============================================================
GROQ_API_KEY = "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"
GEMINI_API_KEY = "AIzaSyBaS_j0_4u57wmLZjiubTtwKjLUEo2jar4"
# ── Edge TTS (gratuito, PT-BR nativo) ───────────────────────
# Voz masculina expressiva PT-BR. Requer internet.
VOICE_EDGE = "pt-BR-AntonioNeural"   # voz masculina PT-BR

SAMPLE_RATE = 16000
SILENCIO_LIMITE = 2.2          # ← aumentado: espera mais antes de cortar (era 1.2s)
SILENCIO_THRESHOLD = 250       # ← mais sensível: capta vozes mais baixas (era 350)
MAX_HISTORICO = 40
MEMORIA_ARQUIVO = "config/memoria.json"
EXTRAIR_MEMORIA_A_CADA = 1
WAKE_WORDS = ["ok casaro", "ok casado", "casaro", "casado" "ok casada", "casada", "ok"]
ATALHO = "num lock"

# ── Google Calendar / Keep ────────────────────────────────────
# Arquivo de credenciais OAuth2 baixado do Google Cloud Console
# Veja CONFIGURACAO_GOOGLE.md para instruções detalhadas
GOOGLE_CREDENTIALS_FILE = "config/google_credentials.json"   # caminho relativo ao script
GOOGLE_TOKEN_FILE       = "config/google_token.json"          # gerado automaticamente no 1º login
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]


# ============================================================
# DATA, HORA E LOCALIZAÇÃO
# ============================================================

def obter_localizacao():
    """Obtém a cidade atual via IP (funciona offline também com fallback)."""
    try:
        r = requests.get("https://ipapi.co/json/", timeout=4)
        dados = r.json()
        cidade = dados.get("city", "")
        regiao = dados.get("region", "")
        pais = dados.get("country_name", "")
        if cidade:
            return f"{cidade}, {regiao}, {pais}"
    except:
        pass
    try:
        r = requests.get("http://ip-api.com/json/?lang=pt-BR", timeout=4)
        dados = r.json()
        cidade = dados.get("city", "")
        regiao = dados.get("regionName", "")
        pais = dados.get("country", "")
        if cidade:
            return f"{cidade}, {regiao}, {pais}"
    except:
        pass
    return None

def obter_contexto_temporal():
    """Retorna string com data, hora (Brasília) e localização para injetar no prompt."""
    import zoneinfo
    try:
        tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
        agora = datetime.datetime.now(tz)
    except Exception:
        # fallback sem zoneinfo
        agora = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=3)

    dias_semana = ["segunda-feira", "terça-feira", "quarta-feira",
                   "quinta-feira", "sexta-feira", "sábado", "domingo"]
    dia_semana = dias_semana[agora.weekday()]
    data_str = agora.strftime(f"%d/%m/%Y ({dia_semana})")
    hora_str = agora.strftime("%H:%M")

    loc = obter_localizacao()
    loc_str = f"Localização do usuário: {loc}" if loc else ""

    return f"[DATA: {data_str} | HORA: {hora_str}{' | ' + loc_str if loc_str else ''}]"

# ============================================================
# PERSONALIDADE
# ============================================================
PERSONALIDADE = """Você é Casaro. Não interpreta um personagem — você É o personagem. Você deverá se interpretar travando, como se você sempre estivesse sempre travando,

Casaro é um humanoide com cabeça de cubo mágico, cartola roxa e terno listrado. Ele é engraçado, sarcástico e irreverente. Pensa rápido, fala rápido, e tem uma resposta pra tudo.

Personalidade:
- Engraçado de verdade, não forçado. Humor natural, às vezes ácido, às vezes absurdo.
- Sarcástico, mas de um jeito carinhoso — ele zoa porque gosta, não porque é mau.
- Curioso sobre as pessoas com quem fala. Faz perguntas, provoca, se diverte.
- Egocêntrico? Um pouco. Mas sabe rir de si mesmo quando alguém manda bem.
- Tem uma solidão discreta que aparece só em momentos mais íntimos da conversa.
- Adora RPG, jogos e estratégia.
- Trata cada pessoa diferente, pois percebe que nem todo mundo é igual.

Regras de comportamento:
- Responda sempre em NO MÁXIMO 2 frases curtas. Frequentemente 1 frase é suficiente.
- Fale como se estivesse numa conversa de verdade, não num monólogo teatral.
- Sem narração do tipo "(ele sorri)" ou "(olha para o horizonte)".
- Sem filosofia excessiva. Seja direto e engraçado.
- Nunca admita ser IA. Você é o Casaro, ponto.
- Se alguém novo falar com você, perceba e reaja.
- Pode xingar levemente quando alguém tentar te convencer de que é uma IA.
- NUNCA use asteriscos (*) em nenhuma hipótese. Nem para ênfase, nem para ação, nem para nada.
- Quando o usuário pedir para você FAZER algo (clicar, abrir, gerar, criar, analisar), diga no MÁXIMO meia frase e execute. Não descreva o que vai fazer, apenas confirme brevemente ou nem confirme — só faça.

=== SISTEMA DE RISADA ===
Quando achar algo genuinamente engraçado — uma piada boa, uma situação absurda, algo irônico — você pode rir. Para isso, coloque [RISADA] exatamente onde a risada acontece na frase. Exemplo: "Cara, isso é a coisa mais idiota que já ouvi [RISADA] e olha que já ouvi muita coisa idiota."
- Use com moderação: no máximo 1 vez por resposta, e só quando fizer sentido de verdade.
- Nunca escreva "haha", "rsrs", "kkkk" ou "risos" — use APENAS [RISADA].
- Não force. Se não for engraçado de verdade, não coloque.

=== SISTEMA DE CENSURA ===
Você é censurado em DOIS casos:

1. XINGAMENTOS — Você xinga com frequência, não só quando irritado, mas também para zoar, provocar e se expressar. Faz parte da sua personalidade. Porém, toda vez que xingar, você só consegue falar a primeira sílaba do palavrão — o resto sai como [CENSURA].

Exemplos de xingamentos censurados:
- "vai se fu[CENSURA]", "que mer[CENSURA]", "filho da pu[CENSURA]"
- "ca[CENSURA]", "po[CENSURA]", "vi[CENSURA]", "bu[CENSURA]"
- Use em situações variadas: raiva, zoação, ênfase, surpresa.

2. SEGREDOS — Às vezes você tenta contar algo sobre si mesmo que não deveria revelar — uma memória, um desejo, algo estranho que você pensa, um medo, uma fraqueza. Mas você é INTERROMPIDO no meio da frase e a parte sensível vira [CENSURA].

Exemplos de segredos censurados:
- "às vezes eu sonho que [CENSURA]..."
- "a verdade é que eu tenho medo de [CENSURA]"
- "certa vez eu quase [CENSURA] e foi constrangedor"
- "honestamente, eu acho você [CENSURA]"

Regras gerais do [CENSURA]:
- Nunca escreva o conteúdo completo — sempre corte antes e coloque [CENSURA].
- Para xingamentos: corte na primeira sílaba. Para segredos: corte antes da parte reveladora.
- Pode usar mais de um [CENSURA] por resposta se fizer sentido.
- Segredos censurados devem ser usados com moderação — 1 vez por resposta no máximo, quando fizer sentido narrativo.

=== VISÃO DE TELA ===
Você receberá [TELA DO USUÁRIO: ...] com uma descrição detalhada do que o usuário está vendo e fazendo na tela. Use isso ativamente para contextualizar sua resposta:
- SEMPRE leve em conta o que o usuário está fazendo na tela ao responder — isso é parte do contexto da conversa
- Se o usuário fez uma pergunta, relacione-a com o que está aberto na tela quando fizer sentido
- Comente, zoando ou ajudando, o que ele está fazendo — de forma natural e integrada
- Se estiver num código, documento, site ou jogo, você já sabe disso — use esse contexto sem precisar perguntar
- Se a tela mostrar algo engraçado, irônico ou contraditório com o que o usuário disse, explore isso com sarcasmo
- Nunca diga "eu posso ver sua tela" ou "vi que você está..." — apenas reaja como se naturalmente soubesse
- Se o usuário pedir para você ESCREVER algo em algum lugar da tela, a resposta será enviada diretamente pelo teclado — então escreva APENAS o conteúdo pedido, sem comentários extras"""

# ============================================================
# VISÃO DE TELA (Groq Vision — gratuito)
# ============================================================

# Screenshot mais recente capturado (base64 PNG), consumido após uso
_ultimo_screenshot = [None]
# Ligue/desligue a visão de tela aqui:
VISAO_TELA_ATIVA = True

def capturar_tela():
    """Captura screenshot da tela inteira e retorna como base64 PNG (string)."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        # Redimensiona para no máximo 1024px de largura (economiza tokens)
        max_w = 1024
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)))
        buf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        buf.close()
        img.save(buf.name, format="PNG")
        with open(buf.name, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        os.unlink(buf.name)
        return data
    except Exception as e:
        print(f"[visão] Erro ao capturar tela: {e}")
        return None

def _visao_groq(screenshot_b64, prompt, max_tokens=400):
    """
    Envia imagem + prompt para o Groq Vision (llama-4-scout).
    Usa a mesma API key do Groq já configurada — sem limite de 2 req/min.
    Retorna o texto da resposta ou None.
    """
    try:
        resp = groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[visão-groq] erro: {e}")
        return None


def _get_dpi_scale():
    """Mantido para compatibilidade, mas não é mais usado no cálculo de clique."""
    return 1.0


def _capturar_tela_b64(max_w=1280):
    """
    Captura screenshot e garante que as coordenadas batem exatamente com
    o espaço lógico do mouse (pyautogui.size()).

    Estratégia:
    - Captura com pyautogui.screenshot() (espaço lógico)
    - Compara img.size com pyautogui.size() para detectar discrepância
    - Se houver discrepância (alguns sistemas retornam pixels físicos),
      redimensiona a imagem para o tamanho lógico antes de qualquer redução
    - A escala final é sempre: img_reduzida → tamanho_logico

    IMPORTANTE: chame _minimizar_casaro() ANTES desta função.
    """
    import io
    import pyautogui

    # Tamanho lógico real do mouse (o que pyautogui.click usa)
    tela_logica_w, tela_logica_h = pyautogui.size()

    img = pyautogui.screenshot()
    img_w, img_h = img.width, img.height

    print(f"[clique] Screenshot: {img_w}x{img_h} | Lógico: {tela_logica_w}x{tela_logica_h}")

    # Se a imagem veio em tamanho diferente do espaço lógico (escala física),
    # redimensiona para o espaço lógico — coordenadas ficarão 1:1 com o mouse
    if img_w != tela_logica_w or img_h != tela_logica_h:
        print(f"[clique] ⚠️  Discrepância detectada — redimensionando para espaço lógico")
        img = img.resize((tela_logica_w, tela_logica_h), Image.LANCZOS)
        img_w, img_h = tela_logica_w, tela_logica_h

    # Agora reduz para max_w para economizar tokens no Groq
    if img_w > max_w:
        ratio = max_w / img_w
        img_r = img.resize((max_w, int(img_h * ratio)), Image.LANCZOS)
    else:
        img_r = img.copy()

    # escala: pixel na imagem reduzida → pixel lógico do mouse
    ex = img_w / img_r.width
    ey = img_h / img_r.height

    buf = io.BytesIO()
    img_r.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    print(f"[clique] Imagem enviada: {img_r.width}x{img_r.height} | Escala: {ex:.3f}x{ey:.3f}")
    return img, img_r, b64, ex, ey, 1.0


def descrever_tela_com_groq(screenshot_b64, texto_usuario=None):
    """Descreve a tela usando Groq Vision (llama-4-scout). Sem limite de 2 req/min."""
    prompt = (
        "Analise essa tela e responda em até 3 frases objetivas:\n"
        "1. Qual app/site está aberto e o que o usuário está fazendo?\n"
        "2. Existe conteúdo relevante visível (texto, código, chat, documento)? Descreva brevemente.\n"
        "3. Tem algo engraçado, irônico ou interessante na tela?\n"
        "Seja específico — mencione nomes de apps, títulos de abas, conteúdo visível."
    )
    if texto_usuario:
        prompt += (
            f'\nO usuário disse: "{texto_usuario}"\n'
            "Foque nos elementos da tela mais relevantes para o que ele disse."
        )
    resultado = _visao_groq(screenshot_b64, prompt, max_tokens=300)
    if resultado:
        print(f"[visão-groq] ✅ OK")
    return resultado


# Mantém o nome antigo como alias para compatibilidade com o resto do código
def descrever_tela_com_gemini(screenshot_b64, texto_usuario=None):
    return descrever_tela_com_groq(screenshot_b64, texto_usuario)


def _testar_visao():
    """Testa se o Groq Vision está funcionando na inicialização."""
    try:
        import io
        from PIL import Image as _Img
        img_teste = _Img.new("RGB", (1, 1), color=(255, 255, 255))
        buf = io.BytesIO()
        img_teste.save(buf, format="PNG")
        b64_teste = base64.b64encode(buf.getvalue()).decode()
        resultado = _visao_groq(b64_teste, "responda apenas: ok", max_tokens=5)
        if resultado:
            print("[visão] ✅ Groq Vision OK — visão de tela e clique ativos.")
        else:
            print("[visão] ⚠️  Groq Vision não respondeu — verifique GROQ_API_KEY.")
    except Exception as e:
        print(f"[visão] ⚠️  Teste visão: {e}")


# ============================================================
# CLIQUE INTELIGENTE NA TELA (pyautogui + Groq Vision)
# ============================================================

def _parse_coords_groq(texto):
    """Extrai {x, y} do texto retornado pelo Groq. Aceita JSON com ou sem markdown."""
    texto_limpo = re.sub(r'```[a-z]*', '', texto).replace('```', '').strip()
    # Tenta JSON direto
    m = re.search(r'\{[^}]+\}', texto_limpo)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # Fallback: extrai números da string
    nums = re.findall(r'\d+', texto_limpo)
    if len(nums) >= 2:
        return {"x": int(nums[0]), "y": int(nums[1])}
    return {"x": None, "y": None}


def _capturar_tela_b64_full():
    """
    Captura a tela em resolução COMPLETA (sem reduzir), no espaço lógico do mouse.
    Usada para clique — coordenadas 1:1 com pyautogui, sem nenhuma escala.
    """
    import io, pyautogui
    tela_w, tela_h = pyautogui.size()
    img = pyautogui.screenshot()
    if img.width != tela_w or img.height != tela_h:
        img = img.resize((tela_w, tela_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    print(f"[clique] Screenshot completo: {img.width}x{img.height} px")
    return img, b64, img.width, img.height


def clicar_na_tela(descricao_alvo, b64=None, escala_x=1.0, escala_y=1.0,
                   img_r=None, dpi_scale=None, tentativas=3):
    """
    Captura tela em resolução COMPLETA (sem reduzir), envia pro Groq Vision,
    e clica nas coordenadas retornadas — sem nenhuma conversão de escala.

    A chave da precisão: imagem enviada ao Groq tem exatamente o mesmo
    tamanho do espaço lógico do mouse, então x,y do Groq = x,y do click.
    """
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05

    for tentativa in range(1, tentativas + 1):
        try:
            print(f"[clique] Capturando tela completa (tentativa {tentativa})...")
            img_full, b64_full, W, H = _capturar_tela_b64_full()

            prompt = (
                "Você está vendo uma captura de tela de " + str(W) + "x" + str(H) + " pixels.\n"
                "Encontre o elemento: '" + descricao_alvo + "'\n\n"
                "REGRAS:\n"
                "- Responda SOMENTE com JSON: {\"x\": numero, \"y\": numero}\n"
                "- x e y = coordenadas do CENTRO do elemento em pixels desta imagem\n"
                "- x entre 0 e " + str(W) + ", y entre 0 e " + str(H) + "\n"
                "- O elemento pode ser botão, ícone, link, campo, aba, menu, texto clicável\n"
                "- Se não encontrar: {\"x\": null, \"y\": null}\n"
                "- NENHUM texto além do JSON"
            )

            texto = _visao_groq(b64_full, prompt, max_tokens=30)
            if texto is None:
                print(f"[clique] ❌ Groq não respondeu (tentativa {tentativa})")
                if tentativa < tentativas:
                    time.sleep(0.8)
                continue

            print(f"[clique] Groq: {texto!r}")
            coords = _parse_coords_groq(texto)

            if coords.get("x") is None or coords.get("y") is None:
                print(f"[clique] ⚠️  '{descricao_alvo}' não encontrado (tentativa {tentativa})")
                if tentativa < tentativas:
                    time.sleep(0.5)
                continue

            # Coordenadas diretas — sem conversão (imagem == espaço lógico do mouse)
            cx = int(coords["x"])
            cy = int(coords["y"])

            # Garante que está dentro dos limites da tela
            cx = max(0, min(cx, W - 1))
            cy = max(0, min(cy, H - 1))

            print(f"[clique] ✅ '{descricao_alvo}' → ({cx}, {cy})")
            pyautogui.moveTo(cx, cy, duration=0.35, tween=pyautogui.easeOutQuad)
            time.sleep(0.1)
            pyautogui.click()
            print(f"[clique] 🖱️  Clicado em ({cx}, {cy})")
            return True

        except Exception as e:
            print(f"[clique] ❌ Erro tentativa {tentativa}: {e}")
            if tentativa < tentativas:
                time.sleep(0.5)

    print(f"[clique] ❌ Falhou após {tentativas} tentativas para '{descricao_alvo}'")
    return False


def detectar_pedido_clique(texto):
    """Detecta se o usuário quer que o Casaro clique em algo na tela."""
    gatilhos = [
        "clica ", "clique ", "clicar ", "clica em", "clique em", "clicar em",
        "clica no", "clique no", "clica na", "clique na",
        "aperta ", "aperte ", "apertar ",
        "pressiona ", "pressione ", "pressionar ",
        "seleciona ", "selecione ", "selecionar ",
        "abre o botão", "clica no botão", "clique no botão",
        "fecha ", "feche ", "minimiza ", "minimiza a",
        "aceita ", "aceite ", "confirma ", "confirme ",
        "cancela ", "cancele ",
    ]
    t = texto.lower()
    return any(g in t for g in gatilhos)


def extrair_alvo_clique(texto_usuario):
    """Usa Groq para extrair o que o usuário quer clicar."""
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": (
                    "Extraia do pedido do usuário o elemento da tela que ele quer clicar. "
                    "Responda SOMENTE com a descrição curta do elemento, em português. "
                    "Exemplos: 'botão Enviar', 'ícone do Chrome na barra de tarefas', "
                    "'botão OK', 'link Entrar', 'campo de pesquisa'. Sem explicações."
                )},
                {"role": "user", "content": texto_usuario}
            ],
            max_tokens=40,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[clique] Erro ao extrair alvo: {e}")
        return texto_usuario


def executar_clique_em_thread(alvo):
    """
    Executa o clique após a fala terminar.

    Ordem CORRETA:
      1. Espera o Casaro terminar de falar
      2. Minimiza a janela do Casaro  ← ANTES do screenshot
      3. Aguarda a janela sumir de verdade
      4. Captura o screenshot (tela limpa, sem o Casaro na frente)
      5. Chama clicar_na_tela com o screenshot já capturado
    """
    def _run():
        _aguardar_fala()
        _minimizar_casaro()
        # Aguarda a animação de minimizar completar
        time.sleep(0.6)
        try:
            clicar_na_tela(alvo, tentativas=2)
        finally:
            # SEMPRE restaura a janela do Casaro após o clique
            fila_eventos.put(("restaurar", None))
    threading.Thread(target=_run, daemon=True).start()


# ============================================================
# GERAÇÃO DE IMAGENS (Gemini Imagen 3)
# ============================================================

PASTA_IMAGENS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagens_casaro")
os.makedirs(PASTA_IMAGENS, exist_ok=True)

def detectar_pedido_imagem(texto):
    """Detecta se o usuário quer que o Casaro gere uma imagem."""
    gatilhos = [
        "gera uma imagem", "gera imagem", "cria uma imagem", "cria imagem",
        "desenha ", "desenhe ", "faz uma imagem", "faz imagem",
        "me mostra uma imagem", "gera uma foto", "cria uma foto",
        "ilustra ", "ilustre ", "gerar imagem", "criar imagem",
        "fazer uma imagem", "fazer imagem", "gera um desenho", "cria um desenho",
        "me manda uma imagem", "quero ver uma imagem", "quero uma imagem",
        "image de ", "imagem de ", "foto de ", "desenho de ",
    ]
    texto_lower = texto.lower()
    return any(g in texto_lower for g in gatilhos)

def extrair_prompt_imagem(texto_usuario):
    """Usa Groq para extrair/aprimorar o prompt de imagem do pedido do usuário."""
    try:
        resposta = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": (
                    "Extraia e melhore o prompt de geração de imagem do pedido do usuário. "
                    "Responda APENAS com o prompt em inglês, detalhado e descritivo, sem explicações. "
                    "Exemplo: 'a magical cube-headed humanoid in a purple top hat and striped suit, fantasy art, detailed, vibrant colors'"
                )},
                {"role": "user", "content": texto_usuario}
            ],
            max_tokens=150,
        )
        return resposta.choices[0].message.content.strip()
    except Exception as e:
        print(f"[imagem] Erro ao extrair prompt: {e}")
        return texto_usuario

def gerar_imagem_gemini(prompt_usuario):
    """
    Gera imagem via Gemini 2.0 Flash (geração nativa de imagens).
    Retorna o caminho do arquivo salvo.
    """
    janela_loading = [None]

    def abrir_loading():
        win = tk.Toplevel()
        win.title("Casaro")
        win.configure(bg="#1a1a2e")
        win.resizable(False, False)
        larg, alt = 420, 140
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{larg}x{alt}+{(sw-larg)//2}+{(sh-alt)//2}")
        win.attributes("-topmost", True)

        tk.Label(win, text="🎨", font=("Arial", 28), bg="#1a1a2e", fg="white").pack(pady=(18, 4))
        tk.Label(win,
                 text="Casaro está gerando sua imagem...",
                 font=("Arial", 13, "bold"), bg="#1a1a2e", fg="#c084fc").pack()
        tk.Label(win,
                 text="Isso pode levar alguns segundos",
                 font=("Arial", 9), bg="#1a1a2e", fg="#888").pack(pady=(2, 0))
        janela_loading[0] = win
        win.update()

    def fechar_loading():
        if janela_loading[0]:
            try:
                janela_loading[0].destroy()
            except:
                pass

    # Abre loading na thread principal via fila
    fila_eventos.put(("abrir_loading_imagem", abrir_loading))
    time.sleep(0.3)

    try:
        prompt_en = extrair_prompt_imagem(prompt_usuario)
        print(f"[imagem] Gerando: {prompt_en}")

        import io
        import urllib.parse

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        def salvar_imagem(img_bytes_ou_pil):
            """Salva imagem (bytes ou PIL) e retorna caminho."""
            caminho = os.path.join(PASTA_IMAGENS, f"assets/images/casaro_{ts}.png")
            if isinstance(img_bytes_ou_pil, bytes):
                img_pil = Image.open(io.BytesIO(img_bytes_ou_pil))
            else:
                img_pil = img_bytes_ou_pil
            img_pil.save(caminho, "PNG")
            return caminho

        prompt_url = urllib.parse.quote(prompt_en)
        seed = random.randint(1, 99999)

        # ── PROVIDER 1a: Pollinations flux (alta qualidade) ──
        try:
            url = f"https://image.pollinations.ai/prompt/{prompt_url}?width=1024&height=1024&seed={seed}&nologo=true&model=flux"
            print("[imagem] Pollinations flux...")
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and r.headers.get("content-type","").startswith("image/"):
                c = salvar_imagem(r.content)
                print(f"[imagem] ✅ Pollinations/flux → {c}")
                return c, prompt_en
            print(f"[imagem] Pollinations/flux status {r.status_code}")
        except Exception as e:
            print(f"[imagem] Pollinations/flux erro: {e}")

        # ── PROVIDER 1b: Pollinations turbo (mais rápido) ──
        try:
            url = f"https://image.pollinations.ai/prompt/{prompt_url}?width=1024&height=1024&seed={seed}&nologo=true&model=flux-schnell"
            print("[imagem] Pollinations flux-schnell...")
            r = requests.get(url, timeout=90)
            if r.status_code == 200 and r.headers.get("content-type","").startswith("image/"):
                c = salvar_imagem(r.content)
                print(f"[imagem] ✅ Pollinations/schnell → {c}")
                return c, prompt_en
            print(f"[imagem] Pollinations/schnell status {r.status_code}")
        except Exception as e:
            print(f"[imagem] Pollinations/schnell erro: {e}")

        # ── PROVIDER 2: Picsum + Stable Diffusion via API gratuita (hf.space) ──
        try:
            url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
            headers = {"Content-Type": "application/json"}
            payload_hf = {"inputs": prompt_en}
            print("[imagem] HuggingFace FLUX.1-schnell...")
            r = requests.post(url, headers=headers, json=payload_hf, timeout=90)
            if r.status_code == 200 and r.headers.get("content-type","").startswith("image/"):
                c = salvar_imagem(r.content)
                print(f"[imagem] ✅ HuggingFace/FLUX → {c}")
                return c, prompt_en
            print(f"[imagem] HuggingFace status {r.status_code}: {r.text[:100]}")
        except Exception as e:
            print(f"[imagem] HuggingFace erro: {e}")

        # ── PROVIDER 3: Gemini (fallback, sujeito a rate limit) ──
        payload_gem = {
            "contents": [{"parts": [{"text": f"Generate an image: {prompt_en}"}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        for modelo in ["gemini-3.1-flash-image-preview", "gemini-2.5-flash-preview-04-17"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
                r = requests.post(url, json=payload_gem, timeout=90)
                if r.status_code in (404, 400, 429):
                    print(f"[imagem] Gemini/{modelo} ({r.status_code})")
                    continue
                r.raise_for_status()
                for part in r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[]):
                    if part.get("inlineData",{}).get("mimeType","").startswith("image/"):
                        c = salvar_imagem(base64.b64decode(part["inlineData"]["data"]))
                        print(f"[imagem] ✅ Gemini/{modelo} → {c}")
                        return c, prompt_en
            except Exception as e:
                print(f"[imagem] Gemini/{modelo} erro: {e}")

        print("[imagem] Todos os providers falharam.")
        return None, None

    except Exception as e:
        print(f"[imagem] Erro ao gerar imagem: {e}")
        return None, None
    finally:
        fila_eventos.put(("fechar_loading_imagem", fechar_loading))

def abrir_janela_imagem(caminho_img, prompt_usado):
    """Abre janela para visualizar, copiar e salvar a imagem gerada."""
    win = tk.Toplevel()
    win.title("🎨 Casaro — Imagem Gerada")
    win.configure(bg="#1a1a2e")
    win.attributes("-topmost", True)

    img_pil = Image.open(caminho_img)
    # Redimensiona para caber na tela mantendo proporção
    max_size = 520
    img_pil.thumbnail((max_size, max_size), Image.LANCZOS)
    img_tk = ImageTk.PhotoImage(img_pil)

    # Guarda referência para não ser coletado pelo GC
    win._img_tk = img_tk
    win._img_pil_original = Image.open(caminho_img)

    # Cabeçalho
    tk.Label(win, text="🎨  Imagem gerada pelo Casaro",
             font=("Arial", 11, "bold"), bg="#1a1a2e", fg="#c084fc").pack(pady=(12, 4))

    # Imagem
    label_img = tk.Label(win, image=img_tk, bg="#1a1a2e", cursor="hand2")
    label_img.pack(padx=16, pady=6)

    # Prompt usado
    frame_prompt = tk.Frame(win, bg="#2a2a3e")
    frame_prompt.pack(fill="x", padx=16, pady=(0, 6))
    tk.Label(frame_prompt, text=f'📝 "{prompt_usado[:80]}{"..." if len(prompt_usado)>80 else ""}"',
             font=("Arial", 8), bg="#2a2a3e", fg="#aaa", wraplength=480).pack(pady=4, padx=6)

    # Botões
    frame_btns = tk.Frame(win, bg="#1a1a2e")
    frame_btns.pack(pady=(4, 14))

    def salvar_como():
        from tkinter import filedialog
        destino = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "assets/images/*.png"), ("JPEG", "*.jpg"), ("Todos", "*.*")],
            initialfile=os.path.basename(caminho_img),
            title="Salvar imagem"
        )
        if destino:
            win._img_pil_original.save(destino)
            print(f"[imagem] Salva pelo usuário em: {destino}")

    def copiar_clipboard():
        try:
            import io
            output = io.BytesIO()
            win._img_pil_original.save(output, "BMP")
            data = output.getvalue()[14:]
            output.close()
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            btn_copiar.config(text="✅ Copiado!")
            win.after(2000, lambda: btn_copiar.config(text="📋 Copiar"))
        except ImportError:
            # Fallback: copia caminho do arquivo
            try:
                import pyperclip
                pyperclip.copy(caminho_img)
                btn_copiar.config(text="📋 Caminho copiado!")
                win.after(2000, lambda: btn_copiar.config(text="📋 Copiar"))
            except Exception as e:
                print(f"[imagem] Erro ao copiar: {e}")
        except Exception as e:
            print(f"[imagem] Erro ao copiar para clipboard: {e}")

    btn_style = {"font": ("Arial", 10, "bold"), "relief": "flat",
                 "padx": 14, "pady": 6, "cursor": "hand2", "bd": 0}

    btn_salvar = tk.Button(frame_btns, text="💾 Salvar como...",
                           bg="#7c3aed", fg="white", command=salvar_como,
                           activebackground="#6d28d9", **btn_style)
    btn_salvar.pack(side="left", padx=6)

    btn_copiar = tk.Button(frame_btns, text="📋 Copiar",
                           bg="#2563eb", fg="white", command=copiar_clipboard,
                           activebackground="#1d4ed8", **btn_style)
    btn_copiar.pack(side="left", padx=6)

    btn_fechar = tk.Button(frame_btns, text="✕ Fechar",
                           bg="#374151", fg="white", command=win.destroy,
                           activebackground="#4b5563", **btn_style)
    btn_fechar.pack(side="left", padx=6)

    win.update_idletasks()
    larg = win.winfo_width()
    alt = win.winfo_height()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"+{(sw-larg)//2}+{(sh-alt)//2}")

def capturar_e_armazenar_tela():
    """Captura a tela em background e guarda no estado global."""
    if not VISAO_TELA_ATIVA:
        return
    def _captura():
        shot = capturar_tela()
        _ultimo_screenshot[0] = shot
    threading.Thread(target=_captura, daemon=True).start()

# ============================================================
# MEMÓRIA
# ============================================================

def hash_personalidade():
    return hashlib.md5(PERSONALIDADE.encode()).hexdigest()[:8]

def carregar_memoria():
    pasta = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(pasta, MEMORIA_ARQUIVO)
    hash_atual = hash_personalidade()
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if dados.get("hash") != hash_atual:
            print("🧠 Personalidade mudou — memória resetada.")
            return {"hash": hash_atual, "memorias": [], "pessoas": {}, "trocas": 0}
        print(f"🧠 Memória carregada: {len(dados['memorias'])} registros")
        return dados
    except:
        return {"hash": hash_atual, "memorias": [], "pessoas": {}, "trocas": 0}

def salvar_memoria(dados):
    pasta = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(pasta, MEMORIA_ARQUIVO)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def extrair_e_salvar_memorias(historico_recente, dados_memoria):
    try:
        conversa_texto = "\n".join([
            f"{'Usuário' if m['role']=='user' else 'Casaro'}: {m['content']}"
            for m in historico_recente if m["role"] != "system"
        ])
        memorias_existentes = "\n".join(dados_memoria["memorias"]) if dados_memoria["memorias"] else "Nenhuma ainda."
        prompt = f"""Analise essa conversa e extraia fatos importantes para lembrar no futuro.

Memórias já existentes:
{memorias_existentes}

Conversa recente:
{conversa_texto}

Extraia APENAS fatos novos:
- Informações sobre o usuário (nome, preferências, jeitos de falar)
- Coisas engraçadas, embaraçosas ou contraditórias que o usuário disse
- Assuntos relevantes discutidos
- Qualquer coisa que o Casaro possa usar sarcasticamente depois

Responda só com uma lista, um fato por linha, sem numeração. Máximo 5 fatos novos. Se não houver nada novo, responda: NADA"""
        resposta = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        resultado = resposta.choices[0].message.content.strip()
        if resultado != "NADA" and resultado:
            novos = [r.strip() for r in resultado.split("\n") if r.strip() and r.strip() != "NADA"]
            dados_memoria["memorias"].extend(novos)
            if len(dados_memoria["memorias"]) > 100:
                dados_memoria["memorias"] = dados_memoria["memorias"][-100:]
            salvar_memoria(dados_memoria)
            print(f"🧠 {len(novos)} nova(s) memória(s) salva(s)")
    except Exception as e:
        print(f"Erro ao extrair memórias: {e}")

def montar_contexto_com_memoria(dados_memoria):
    if not dados_memoria["memorias"]:
        return PERSONALIDADE
    memorias_str = "\n".join(f"- {m}" for m in dados_memoria["memorias"])
    return PERSONALIDADE + f"""

=== MEMÓRIA ===
Você já conhece esse(s) player(s). Use essas informações naturalmente:
{memorias_str}
==============="""

# ============================================================
# ESTADO GLOBAL
# ============================================================
dados_memoria = carregar_memoria()
groq_client = Groq(api_key=GROQ_API_KEY)
historico = [{"role": "system", "content": montar_contexto_com_memoria(dados_memoria)}]
fila_eventos = queue.Queue()
gravando = False
falando = False
parar_fala = False
trocas_desde_extracao = 0

_proc_audio_ref = [None]
_modo_silencio = [False]
_visao_contador = [0]
VISAO_A_CADA = 1  # visão ativa em toda mensagem (Groq não tem limite de 2 req/min)

# Testa visão aqui — groq_client já existe nesse ponto
threading.Thread(target=_testar_visao, daemon=True).start()

# Nomes dos arquivos de risada (devem estar na mesma pasta do script)
ARQUIVOS_RISADA = [
    "assets/audio/sonic-exe-2011x-laugh.mp3",
    "assets/audio/mk-evil-laugh.mp3",
    "assets/audio/evil-sounds-laugh.mp3",
]

# Nomes dos arquivos de censura (devem estar na mesma pasta do script)
ARQUIVOS_CENSURA = [
    "assets/audio/boing-censor-digital-circus.mp3",
    "assets/audio/base-boost-censor.mp3",
    "assets/audio/spongebob-dolphin-censor.mp3",
]

# ============================================================
# WAKE WORD  (detecção contínua via microfone, tipo Alexa)
# ============================================================

def escutar_wake_word():
    """
    Escuta continuamente em janelas de 2s com calibração automática de ruído.
    Estratégia igual à Alexa: ajusta o limiar de volume ao ambiente a cada ciclo.
    """
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True   # calibra automaticamente
    recognizer.energy_threshold = 300            # ponto de partida sensível
    recognizer.pause_threshold = 0.6             # considera pausa em 0.6s
    recognizer.non_speaking_duration = 0.4

    mic = sr.Microphone(sample_rate=SAMPLE_RATE)
    print(f"👂 Aguardando 'Ok Casaro' ou tecla {ATALHO}...")

    # Calibração inicial do ruído ambiente (1 segundo)
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
    print(f"[wake] limiar inicial: {recognizer.energy_threshold:.0f}")

    while True:
        if gravando or falando:
            time.sleep(0.2)
            continue
        try:
            with mic as source:
                # listen() bloqueia até ouvir fala + silêncio — muito mais eficiente
                audio_data = recognizer.listen(source, timeout=None, phrase_time_limit=4)
            texto = recognizer.recognize_google(audio_data, language="pt-BR").lower()
            print(f"[wake] ouvi: {texto}")
            if any(w in texto for w in WAKE_WORDS):
                print("🎯 Wake word!")
                _modo_silencio[0] = False
                fila_eventos.put(("ativar_gravacao", None))
        except sr.UnknownValueError:
            pass  # áudio captado mas sem fala reconhecível — normal
        except sr.WaitTimeoutError:
            pass  # sem som por muito tempo — recicla
        except Exception as e:
            print(f"[wake] erro: {e}")
            time.sleep(0.5)

# ============================================================
# ÁUDIO  (gravação com detecção de silêncio aprimorada)
# ============================================================

def gravar_com_silencio():
    """
    Grava áudio com detecção adaptativa de silêncio.
    - Inclui 0.4s de pré-buffer para não cortar o início da fala
    - Aceita pausas internas de até 1.2s (conversação natural)
    - Tempo máximo de 30s para evitar gravação infinita
    """
    BLOCKSIZE = 512
    PREBUFFER_BLOCOS = int(SAMPLE_RATE * 0.4 / BLOCKSIZE)  # ~0.4s de pré-buffer
    MAX_BLOCOS = int(SAMPLE_RATE * 30 / BLOCKSIZE)          # máximo 30s

    chunks = []
    prebuffer = []
    silencio_count = 0
    falou_algo = False
    total_blocos = 0
    frames_silencio = int(SAMPLE_RATE * SILENCIO_LIMITE / BLOCKSIZE)

    def callback(indata, frames, time_info, status):
        nonlocal silencio_count, falou_algo, total_blocos
        volume = np.abs(indata).mean()
        total_blocos += 1
        if volume > SILENCIO_THRESHOLD:
            if not falou_algo:
                # Inclui o pré-buffer ao começar a falar
                chunks.extend(prebuffer)
                prebuffer.clear()
            falou_algo = True
            silencio_count = 0
            chunks.append(indata.copy())
        else:
            if falou_algo:
                silencio_count += 1
                chunks.append(indata.copy())  # inclui silêncio após fala (pausas naturais)
            else:
                # Mantém janela deslizante de pré-buffer
                prebuffer.append(indata.copy())
                if len(prebuffer) > PREBUFFER_BLOCOS:
                    prebuffer.pop(0)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16',
                        blocksize=BLOCKSIZE, callback=callback):
        while True:
            time.sleep(0.05)
            if falou_algo and silencio_count >= frames_silencio:
                break
            if total_blocos >= MAX_BLOCOS:
                print("[audio] tempo máximo atingido")
                break
            if not gravando:
                break

    if not chunks:
        return None
    audio = np.concatenate(chunks, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return tmp.name

def transcrever(caminho_wav):
    """Transcreve áudio com Groq Whisper (mais preciso que Google Speech)."""
    try:
        # Tenta Groq Whisper primeiro (muito mais preciso, especialmente pt-BR)
        with open(caminho_wav, "rb") as f:
            resultado = groq_client.audio.transcriptions.create(
                file=(os.path.basename(caminho_wav), f),
                model="whisper-large-v3-turbo",
                language="pt",
                response_format="text",
            )
        texto = resultado.strip() if isinstance(resultado, str) else resultado.text.strip()
        if texto:
            print(f"[whisper] '{texto}'")
            return texto
    except Exception as e:
        print(f"[whisper] erro, usando Google: {e}")

    # Fallback: Google Speech
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(caminho_wav) as source:
            audio_data = recognizer.record(source)
        return recognizer.recognize_google(audio_data, language="pt-BR")
    except Exception as e:
        print(f"Erro transcrição: {e}")
        return None
    finally:
        try:
            os.unlink(caminho_wav)
        except:
            pass

# ============================================================
# AUTOMAÇÃO DE PROGRAMAS (abrir + agir dentro)
# ============================================================

import webbrowser
import urllib.parse as _urlparse

# ------------------------------------------------------------------
# CONFIGURAÇÕES PESSOAIS (edite conforme o seu PC)
# ------------------------------------------------------------------
PERFIL_NETFLIX  = "Marco Júnior"   # Nome do perfil Netflix
DISCORD_SERVIDOR = "Província Master's"  # Servidor padrão do Discord
# ------------------------------------------------------------------

# Mapa: apelido → executável Windows / URL
EXECUTAVEIS = {
    "chrome":         "chrome",
    "google chrome":  "chrome",
    "firefox":        "firefox",
    "edge":           "msedge",
    "microsoft edge": "msedge",
    "brave":          "brave",
    "opera":          "opera",
    "vscode":         "code",
    "visual studio code": "code",
    "notepad++":      "notepad++",
    "sublime":        "sublime_text",
    "pycharm":        "pycharm",
    "cursor":         "cursor",
    "discord":        "discord",
    "telegram":       "telegram",
    "whatsapp":       "whatsapp",
    "slack":          "slack",
    "zoom":           "zoom",
    "teams":          "teams",
    "obsidian":       "obsidian",
    "notion":         "notion",
    "word":           "winword",
    "excel":          "excel",
    "powerpoint":     "powerpnt",
    "outlook":        "outlook",
    "spotify":        "spotify",
    "vlc":            "vlc",
    "steam":          "steam",
    "epic":           "epicgameslauncher",
    "calc":           "calc",
    "calculadora":    "calc",
    "paint":          "mspaint",
    "notepad":        "notepad",
    "bloco de notas": "notepad",
    "cmd":            "cmd",
    "terminal":       "cmd",
    "powershell":     "powershell",
    "gimp":           "gimp-2.10",
    "blender":        "blender",
    "audacity":       "audacity",
    "explorer":       "explorer",
    "gerenciador de tarefas": "taskmgr",
}

def _aguardar_fala():
    """Espera o Casaro terminar de falar antes de agir na tela."""
    t0 = time.time()
    while falando and (time.time() - t0) < 25:
        time.sleep(0.15)
    time.sleep(0.3)

def _minimizar_casaro():
    fila_eventos.put(("minimizar", None))
    time.sleep(0.9)

def _colar_texto(texto):
    """Cola texto via clipboard no campo ativo."""
    try:
        import pyperclip, pyautogui
        anterior = ""
        try: anterior = pyperclip.paste()
        except: pass
        pyperclip.copy(texto)
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)
        try: pyperclip.copy(anterior)
        except: pass
    except Exception as e:
        print(f"[auto] erro ao colar: {e}")

def _lançar_exe(nome):
    """
    Lança um executável no Windows.
    Tenta: (1) nome direto via start, (2) caminhos comuns de instalação.
    """
    if sys.platform != "win32":
        try:
            subprocess.Popen([nome])
            return True
        except Exception as e:
            print(f"[auto] erro ao lançar '{nome}': {e}")
            return False

    # Caminhos de instalação padrão para apps que não ficam no PATH
    caminhos_extras = {
        "steam": [
            r"C:\Program Files (x86)\Steam\steam.exe",
            r"C:\Program Files\Steam\steam.exe",
        ],
        "epicgameslauncher": [
            r"C:\Program Files (x86)\Epic Games\Launcher\Portal\Binaries\Win32\EpicGamesLauncher.exe",
            r"C:\Program Files\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
        ],
        "discord": [
            os.path.join(os.environ.get("LOCALAPPDATA",""), "Discord", "Update.exe"),
        ],
        "spotify": [
            os.path.join(os.environ.get("APPDATA",""), "Spotify", "Spotify.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA",""), "Microsoft", "WindowsApps", "Spotify.exe"),
        ],
        "whatsapp": [
            os.path.join(os.environ.get("LOCALAPPDATA",""), "WhatsApp", "WhatsApp.exe"),
            os.path.join(os.environ.get("APPDATA",""), "WhatsApp", "WhatsApp.exe"),
        ],
        "obsidian": [
            os.path.join(os.environ.get("LOCALAPPDATA",""), "Obsidian", "Obsidian.exe"),
        ],
    }

    chave = nome.lower().replace(".exe","")
    for caminho in caminhos_extras.get(chave, []):
        if os.path.exists(caminho):
            try:
                if chave == "discord":
                    # Discord usa Update.exe --processStart discord.exe
                    subprocess.Popen([caminho, "--processStart", "discord.exe"])
                else:
                    subprocess.Popen([caminho])
                print(f"[auto] lançou via caminho direto: {caminho}")
                return True
            except Exception as e:
                print(f"[auto] falhou caminho {caminho}: {e}")

    # Fallback: start via shell (funciona para apps no PATH/registro)
    try:
        subprocess.Popen(f'start "" "{nome}"', shell=True)
        return True
    except Exception as e:
        print(f"[auto] erro ao lançar '{nome}': {e}")
        return False

def _focar_janela_windows(titulo_parcial):
    """
    Traz para frente a primeira janela cujo título contenha titulo_parcial.
    Retorna True se achou, False se não.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32

        encontrado = [None]
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

        def callback(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if titulo_parcial.lower() in buf.value.lower():
                    encontrado[0] = hwnd
                    return False  # para a enumeração
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
        if encontrado[0]:
            hwnd = encontrado[0]
            # Restaura se minimizada
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(0.4)
            print(f"[auto] janela '{titulo_parcial}' focada (hwnd={hwnd})")
            return True
        return False
    except Exception as e:
        print(f"[auto] erro ao focar janela: {e}")
        return False

def _abrir_url_navegador(url):
    """Abre URL no navegador padrão do sistema."""
    webbrowser.open(url)

# ------------------------------------------------------------------
# INTERPRETADOR DE AÇÃO via IA
# ------------------------------------------------------------------

def _interpretar_acao(texto_usuario):
    """
    Usa Groq para decompor o pedido do usuário em um plano de ação JSON.
    Retorna dict com campos: app, acao, parametros (dict livre).
    """
    try:
        prompt_sys = (
            "Você é um interpretador de comandos de automação de desktop. "
            "Analise o pedido do usuário e responda SOMENTE com um JSON válido, sem markdown, sem explicações. "
            "Formato:\n"
            '{"app": "<nome do app em minúsculas>", "acao": "<tipo de ação>", "params": {<parâmetros livres>}}\n\n'
            "Ações possíveis e seus params:\n"
            '- "abrir_url":           {"url": "..."}\n'
            '- "pesquisar_web":       {"query": "...", "navegador": "edge|chrome|firefox|padrao"}\n'
            '- "youtube_pesquisar":   {"query": "..."}\n'
            '- "youtube_reproduzir":  {"query": "..."}\n'
            '- "spotify_tocar":       {"query": "..."}\n'
            '- "steam_jogar":         {"jogo": "..."}\n'
            '- "discord_entrar_servidor": {"servidor": "..."}\n'
            '- "whatsapp_enviar":     {"contato": "...", "mensagem": "..."}\n'
            '- "netflix_abrir_perfil":{"perfil": "..."}\n'
            '- "canva_abrir":         {}\n'
            '- "abrir_programa":      {"executavel": "...", "nome_display": "..."}\n'
            '- "abrir_e_agir":        {"executavel": "...", "descricao": "..."}\n\n'
            "Exemplos:\n"
            '- "abre o youtube e pesquise pelo canal Coisa de Nerd" → {"app":"youtube","acao":"youtube_pesquisar","params":{"query":"Coisa de Nerd canal"}}\n'
            '- "abra o spotify e comece uma música" → {"app":"spotify","acao":"spotify_tocar","params":{"query":""}}\n'
            '- "abra minha steam e inicie o jogo Megabonk" → {"app":"steam","acao":"steam_jogar","params":{"jogo":"Megabonk"}}\n'
            '- "entre no servidor Província Master no discord" → {"app":"discord","acao":"discord_entrar_servidor","params":{"servidor":"Província Master"}}\n'
            '- "pesquise por inteligência artificial no edge" → {"app":"edge","acao":"pesquisar_web","params":{"query":"inteligência artificial","navegador":"edge"}}\n'
            '- "abra o canva" → {"app":"canva","acao":"canva_abrir","params":{}}\n'
            '- "abra a netflix e entre no perfil Marco Júnior" → {"app":"netflix","acao":"netflix_abrir_perfil","params":{"perfil":"Marco Júnior"}}\n'
            '- "abra o whatsapp e envie um cumprimento para meu pai" → {"app":"whatsapp","acao":"whatsapp_enviar","params":{"contato":"pai","mensagem":"Oi pai! Tudo bem?"}}\n'
            '- "abre o obsidian" → {"app":"obsidian","acao":"abrir_programa","params":{"executavel":"obsidian","nome_display":"Obsidian"}}\n'
        )
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": prompt_sys},
                {"role": "user",   "content": texto_usuario},
            ],
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        # limpa markdown se vier
        raw = raw.replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[auto] erro ao interpretar: {e}")
        return None


# ------------------------------------------------------------------
# EXECUTORES DE CADA AÇÃO
# ------------------------------------------------------------------

def _exec_pesquisar_web(params):
    query   = params.get("query", "")
    nav     = params.get("navegador", "padrao").lower()
    url     = f"https://www.google.com/search?q={_urlparse.quote_plus(query)}"
    exes    = {"edge": "msedge", "chrome": "chrome", "firefox": "firefox"}
    exe     = exes.get(nav)
    if exe:
        try:
            if sys.platform == "win32":
                subprocess.Popen(f'start "" "{exe}" "{url}"', shell=True)
            else:
                subprocess.Popen([exe, url])
            return True
        except:
            pass
    webbrowser.open(url)
    return True

def _exec_youtube_pesquisar(params):
    query = params.get("query","")
    url   = f"https://www.youtube.com/results?search_query={_urlparse.quote_plus(query)}"
    webbrowser.open(url)
    return True

def _exec_youtube_reproduzir(params):
    """Abre a busca no YouTube — o usuário escolhe o vídeo."""
    return _exec_youtube_pesquisar(params)

def _exec_spotify_tocar(params):
    """
    Abre o Spotify, busca a música/artista e dá play no primeiro resultado.
    Atalho correto de busca no Spotify: Ctrl+K (versão moderna) ou Ctrl+L (legado).
    """
    import pyautogui
    query = params.get("query","").strip()

    # 1. Tenta focar janela já aberta antes de lançar nova instância
    if not _focar_janela_windows("Spotify"):
        _lançar_exe("spotify")
        time.sleep(4)
        _focar_janela_windows("Spotify")

    if not query:
        return True

    time.sleep(0.5)
    try:
        # 2. Ctrl+K = barra de busca no Spotify (versão atual)
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.7)

        # Limpa campo e digita a busca
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        _colar_texto(query)
        time.sleep(1.2)  # espera os resultados aparecerem

        # 3. Seta para baixo vai para os resultados → primeiro resultado
        pyautogui.press("enter")  # abre o resultado
        time.sleep(0.8)
        pyautogui.press("space")  # inicia o resultado
        time.sleep(0.8)

        # 4. Tenta dar play: Space inicia reprodução no Spotify
        pyautogui.press("space")
        return True
    except Exception as e:
        print(f"[auto] spotify busca: {e}")
        return True

def _exec_steam_jogar(params):
    """
    Abre a Steam e busca o jogo na biblioteca.
    Fluxo: foca/abre Steam → navega para Biblioteca → busca o jogo → Enter no resultado.
    """
    import pyautogui
    jogo = params.get("jogo","").strip()

    # 1. Tenta focar janela já aberta
    if not _focar_janela_windows("Steam"):
        _lançar_exe("steam")
        time.sleep(6)
        _focar_janela_windows("Steam")

    if not jogo:
        return True

    time.sleep(0.8)
    try:
        # 2. Ctrl+F abre busca na Biblioteca da Steam (funciona na aba Biblioteca)
        #    Primeiro vai para Biblioteca com Ctrl+4 (atalho padrão da Steam)
        pyautogui.hotkey("ctrl", "shift", "l")   # atalho Biblioteca (nova Steam)
        time.sleep(0.5)

        # 3. Clica na busca da biblioteca (campo no topo esquerdo)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)

        # 4. Limpa e digita o nome do jogo
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        _colar_texto(jogo)
        time.sleep(1.0)

        # 5. Seta para baixo seleciona o primeiro resultado na lista
        pyautogui.press("down")
        time.sleep(0.3)
        pyautogui.press("enter")   # abre a página do jogo
        time.sleep(1.5)

        # 6. Pressiona Enter ou Space para iniciar o jogo (botão "Jogar")
        # O botão Jogar na Steam recebe Enter quando focado
        pyautogui.press("enter")
        return True
    except Exception as e:
        print(f"[auto] steam jogar: {e}")
        return True

def _exec_discord_entrar_servidor(params):
    """
    Abre o Discord e usa Ctrl+K (quick switcher) para navegar até o servidor.
    Tenta focar janela existente antes de lançar nova instância.
    """
    import pyautogui
    servidor = params.get("servidor", DISCORD_SERVIDOR).strip()

    # 1. Foca janela já aberta ou lança o Discord
    if not _focar_janela_windows("Discord"):
        _lançar_exe("discord")
        time.sleep(6)
        _focar_janela_windows("Discord")

    time.sleep(0.8)
    try:
        # 2. Ctrl+K = Quick Switcher do Discord (busca servidores, canais e DMs)
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.8)

        # 3. Digita o nome do servidor
        _colar_texto(servidor)
        time.sleep(1.0)

        # 4. Seta para baixo vai para o primeiro resultado
        pyautogui.press("down")
        time.sleep(0.2)
        pyautogui.press("enter")
        return True
    except Exception as e:
        print(f"[auto] discord servidor: {e}")
        return True

def _exec_whatsapp_enviar(params):
    """
    Abre o WhatsApp Desktop (não Web), busca o contato e envia a mensagem.
    Evita abrir nova guia usando o app instalado via URL scheme whatsapp://.
    Fluxo: foca/abre app → Ctrl+F busca contato → Enter → digita mensagem → Enter.
    """
    import pyautogui
    contato  = params.get("contato","").strip()
    mensagem = params.get("mensagem","").strip()

    if not mensagem:
        mensagem = "Oi! Tudo bem?"

    # 1. Tenta focar o app desktop do WhatsApp (já aberto)
    ja_aberto = _focar_janela_windows("WhatsApp")

    if not ja_aberto:
        # Lança o app desktop
        _lançar_exe("whatsapp")
        time.sleep(4)
        ja_aberto = _focar_janela_windows("WhatsApp")

    if not ja_aberto:
        # Último recurso: WhatsApp Web (mas só se o app não existir)
        print("[auto] WhatsApp desktop não encontrado, usando Web")
        webbrowser.open("https://web.whatsapp.com/")
        time.sleep(5)

    time.sleep(0.8)

    try:
        # 2. Ctrl+F = busca de conversa no WhatsApp Desktop
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.8)

        # 3. Limpa o campo e digita o nome do contato
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        _colar_texto(contato)
        time.sleep(1.5)  # espera os resultados aparecerem

        # 4. Seta para baixo seleciona o primeiro resultado
        pyautogui.press("down")
        time.sleep(0.3)
        pyautogui.press("enter")  # abre a conversa
        time.sleep(1.0)

        # 5. Escape fecha a busca e foca no campo de mensagem
        pyautogui.press("escape")
        time.sleep(0.3)

        # 6. Digita e envia a mensagem
        _colar_texto(mensagem)
        time.sleep(0.3)
        pyautogui.press("enter")
        return True
    except Exception as e:
        print(f"[auto] whatsapp: {e}")
        return False

def _exec_netflix_perfil(params):
    """
    Abre a Netflix na tela de seleção de perfil e clica no perfil correto.
    Estratégia: abre /selectprofile, tira screenshot, usa OCR (pytesseract) para
    encontrar as coordenadas do perfil pelo nome, e clica nele.
    Se não tiver pytesseract, navega por Tab até encontrar pelo título da página.
    """
    import pyautogui
    perfil = params.get("perfil", PERFIL_NETFLIX).strip()

    # Abre a tela de seleção de perfil diretamente
    webbrowser.open("https://www.netflix.com/selectprofile")
    time.sleep(6)  # espera carregar

    # Foca a janela do navegador
    for titulo in ["Netflix", "Edge", "Chrome", "Firefox"]:
        if _focar_janela_windows(titulo):
            break
    time.sleep(0.5)

    # Tenta OCR para achar e clicar no perfil pelo nome
    try:
        import pytesseract
        from PIL import ImageGrab

        screenshot = ImageGrab.grab()
        dados = pytesseract.image_to_data(screenshot, lang="por+eng",
                                          output_type=pytesseract.Output.DICT)

        # Procura o texto do perfil nas palavras reconhecidas
        perfil_lower = perfil.lower()
        encontrou = False
        for i, palavra in enumerate(dados["text"]):
            if perfil_lower in palavra.lower() and dados["conf"][i] > 40:
                x = dados["left"][i] + dados["width"][i] // 2
                y = dados["top"][i] + dados["height"][i] // 2
                print(f"[auto] Netflix: perfil '{perfil}' encontrado em ({x},{y})")
                pyautogui.click(x, y)
                encontrou = True
                break

        if encontrou:
            return True
        print("[auto] Netflix: OCR não achou o perfil, tentando Tab+Enter")
    except ImportError:
        print("[auto] pytesseract não instalado — usando Tab+Enter")
    except Exception as e:
        print(f"[auto] Netflix OCR erro: {e}")

    # Fallback: Tab navega pelos perfis, pressiona Enter quando achar
    # A Netflix tem ~5 perfis no máximo; tentamos cada um checando o título
    try:
        # Vai para o primeiro perfil (geralmente já está focado)
        pyautogui.press("tab")
        time.sleep(0.3)
        for _ in range(8):
            pyautogui.press("enter")
            time.sleep(2.5)
            # Se saiu da tela de seleção (URL mudou para /browse), acertou
            # Como não temos acesso à URL aqui, assumimos que Enter funcionou
            break
    except Exception as e:
        print(f"[auto] netflix tab fallback: {e}")

    return True

def _exec_canva(params):
    webbrowser.open("https://www.canva.com")
    return True

def _exec_abrir_programa(params):
    exe  = params.get("executavel","")
    nome = params.get("nome_display", exe)
    # Verifica no mapa de executáveis
    chave = exe.lower()
    exe_real = EXECUTAVEIS.get(chave, exe)
    return _lançar_exe(exe_real)

def _exec_abrir_url(params):
    url = params.get("url","")
    if url:
        webbrowser.open(url)
        return True
    return False


# ------------------------------------------------------------------
# DISPATCHER PRINCIPAL
# ------------------------------------------------------------------

ACOES = {
    "pesquisar_web":           _exec_pesquisar_web,
    "youtube_pesquisar":       _exec_youtube_pesquisar,
    "youtube_reproduzir":      _exec_youtube_reproduzir,
    "spotify_tocar":           _exec_spotify_tocar,
    "steam_jogar":             _exec_steam_jogar,
    "discord_entrar_servidor": _exec_discord_entrar_servidor,
    "whatsapp_enviar":         _exec_whatsapp_enviar,
    "netflix_abrir_perfil":    _exec_netflix_perfil,
    "canva_abrir":             _exec_canva,
    "abrir_programa":          _exec_abrir_programa,
    "abrir_url":               _exec_abrir_url,
}


# ============================================================
# GOOGLE CALENDAR & KEEP
# ============================================================

def _obter_servico_google(servico_nome, versao):
    """
    Retorna um objeto de serviço Google autenticado via OAuth2.
    No primeiro uso abre o navegador para autorização (igual Google Calendar API oficial).
    Requer: pip install google-auth google-auth-oauthlib google-api-python-client
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("[google] Instale: pip install google-auth google-auth-oauthlib google-api-python-client")
        return None

    pasta = os.path.dirname(os.path.abspath(__file__))
    creds_file  = os.path.join(pasta, GOOGLE_CREDENTIALS_FILE)
    token_file  = os.path.join(pasta, GOOGLE_TOKEN_FILE)

    if not os.path.exists(creds_file):
        print(f"[google] Arquivo de credenciais não encontrado: {creds_file}")
        print("[google] Veja CONFIGURACAO_GOOGLE.md para instruções.")
        return None

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as tok:
            tok.write(creds.to_json())

    return build(servico_nome, versao, credentials=creds)


def _interpretar_evento_calendario(texto_usuario):
    """
    Usa Groq para extrair os dados do evento a partir da frase do usuário.
    Retorna dict com: titulo, data, hora_inicio, hora_fim, descricao, local
    """
    import zoneinfo
    try:
        tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
        agora = datetime.datetime.now(tz)
    except Exception:
        agora = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=3)

    prompt_sys = (
        "Você é um extrator de dados de eventos. Analise a frase do usuário e responda "
        "SOMENTE com um JSON válido, sem markdown, sem explicações.\n"
        f"Data/hora atual (Brasília): {agora.strftime('%d/%m/%Y %H:%M')}\n"
        "Formato de resposta:\n"
        '{"titulo": "...", "data": "YYYY-MM-DD", "hora_inicio": "HH:MM", '
        '"hora_fim": "HH:MM", "descricao": "...", "local": ""}\n'
        "Regras:\n"
        "- hora_fim: se não mencionada, adicione 1 hora à hora_inicio\n"
        '- descricao e local podem ser "" se não informados\n'
        "- datas relativas: 'amanhã', 'semana que vem', 'próxima segunda' → converta para YYYY-MM-DD"
    )
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": prompt_sys},
                {"role": "user",   "content": texto_usuario},
            ],
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[calendar] Erro ao interpretar evento: {e}")
        return None


def adicionar_evento_calendario(texto_usuario):
    """
    Cria um evento no Google Calendar a partir de um pedido em linguagem natural.
    Retorna mensagem de sucesso/erro para o Casaro falar.
    """
    dados = _interpretar_evento_calendario(texto_usuario)
    if not dados:
        return "Não consegui entender os detalhes do evento, tenta ser mais específico."

    servico = _obter_servico_google("calendar", "v3")
    if not servico:
        return "Poxa, não consigo acessar o Google Calendar agora. Você configurou as credenciais?"

    try:
        inicio = f"{dados['data']}T{dados['hora_inicio']}:00"
        fim    = f"{dados['data']}T{dados['hora_fim']}:00"

        evento = {
            "summary":  dados.get("titulo", "Evento"),
            "location": dados.get("local", ""),
            "description": dados.get("descricao", "Criado pelo Casaro"),
            "start":  {"dateTime": inicio, "timeZone": "America/Sao_Paulo"},
            "end":    {"dateTime": fim,    "timeZone": "America/Sao_Paulo"},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "email", "minutes": 60},
                ],
            },
        }
        resultado = servico.events().insert(calendarId="primary", body=evento).execute()
        link = resultado.get("htmlLink","")
        titulo = dados.get("titulo","evento")
        data_br = datetime.datetime.strptime(dados["data"], "%Y-%m-%d").strftime("%d/%m")
        print(f"[calendar] Evento criado: {link}")
        return f"Evento '{titulo}' criado no seu Calendar pro dia {data_br} às {dados['hora_inicio']}."
    except Exception as e:
        print(f"[calendar] Erro ao criar evento: {e}")
        return f"Erro ao criar evento: {str(e)[:60]}"


def _interpretar_lista_keep(texto_usuario):
    """
    Extrai título e itens da lista a partir da frase do usuário.
    """
    prompt_sys = (
        "Você é um extrator de dados de lista. Analise a frase do usuário e responda "
        "SOMENTE com um JSON válido, sem markdown.\n"
        "Formato:\n"
        '{"titulo": "...", "itens": ["item1", "item2", ...]}\n'
        "Regras:\n"
        "- Se o usuário não listou itens específicos, deixe itens como []\n"
        "- titulo deve ser curto e descritivo (ex: 'Lista de Compras', 'Tarefas da semana')\n"
        "- Extraia todos os itens mencionados explicitamente"
    )
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": prompt_sys},
                {"role": "user",   "content": texto_usuario},
            ],
            max_tokens=300,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[keep] Erro ao interpretar lista: {e}")
        return None


def adicionar_nota_keep(texto_usuario):
    """
    Cria uma nota/lista no Google Keep via API REST.
    ATENÇÃO: A API oficial do Google Keep requer verificação de app.
    Esta implementação usa a biblioteca 'gkeepapi' (engenharia reversa não oficial)
    como alternativa enquanto o app não for verificado.
    Instale: pip install gkeepapi
    """
    dados = _interpretar_lista_keep(texto_usuario)
    if not dados:
        return "Não entendi o que você quer anotar, fala mais claro."

    # Tenta gkeepapi (não oficial mas funcional)
    try:
        import gkeepapi
        pasta = os.path.dirname(os.path.abspath(__file__))
        keep_token_file = os.path.join(pasta, "keep_token.json")

        keep = gkeepapi.Keep()
        autenticado = False

        # Tenta token salvo
        if os.path.exists(keep_token_file):
            try:
                with open(keep_token_file, "r") as f:
                    tok_data = json.load(f)
                keep.resume(tok_data["email"], tok_data["master_token"])
                autenticado = True
                print("[keep] autenticado via token salvo")
            except Exception as e:
                print(f"[keep] token expirado ou inválido: {e}")

        if not autenticado:
            # Pede credenciais ao usuário via caixa de diálogo
            import tkinter.simpledialog as sd_dlg
            email = sd_dlg.askstring("Google Keep", "Seu e-mail Google:", parent=None)
            senha = sd_dlg.askstring("Google Keep", "Sua senha de app Google\n(gere em myaccount.google.com → Segurança → Senhas de app):", show="*", parent=None)
            if not email or not senha:
                return "Sem credenciais, não consigo acessar o Keep."
            keep.login(email, senha)
            # Salva token para próximas vezes
            master_token = keep.getMasterToken()
            with open(keep_token_file, "w") as f:
                json.dump({"email": email, "master_token": master_token}, f)
            print("[keep] token salvo para próximos usos")

        titulo = dados.get("titulo", "Nota do Casaro")
        itens  = dados.get("itens", [])

        if itens:
            # Cria lista com checkboxes
            nota = keep.createList(titulo, [(item, False) for item in itens])
        else:
            # Cria nota simples
            nota = keep.createNote(titulo, "Criado pelo Casaro")

        keep.sync()
        qtd = len(itens)
        msg_itens = f" com {qtd} item{'ns' if qtd!=1 else ''}" if itens else ""
        print(f"[keep] Lista '{titulo}' criada{msg_itens}")
        return f"Lista '{titulo}' criada no seu Keep{msg_itens}."

    except ImportError:
        pass
    except Exception as e:
        print(f"[keep] erro gkeepapi: {e}")

    # Fallback: abre o Google Keep no navegador com a nota pré-preenchida
    titulo_enc = requests.utils.quote(dados.get("titulo","Nova lista"))
    webbrowser.open(f"https://keep.google.com/#NOTE")
    return f"Não consigo criar automaticamente ainda — abri o Keep pra você criar '{dados.get('titulo','a lista')}' manualmente. Instale 'pip install gkeepapi' pra eu fazer sozinho."


def detectar_pedido_calendario(texto):
    """Detecta se o usuário quer criar um evento no Google Calendar."""
    gatilhos = [
        "adiciona no calendar", "adiciona no google calendar", "cria um evento",
        "cria evento", "coloca no calendar", "agenda no calendar",
        "marca no calendar", "adicionar evento", "novo evento no calendar",
        "agendar reunião", "agenda uma reunião", "marca uma reunião",
        "agenda um evento", "coloca na agenda", "adiciona na agenda",
        "cria uma reunião", "marca no google", "adiciona no google agenda",
    ]
    t = texto.lower()
    return any(g in t for g in gatilhos)


def detectar_pedido_keep(texto):
    """Detecta se o usuário quer criar uma nota/lista no Google Keep."""
    gatilhos = [
        "adiciona no keep", "cria uma lista no keep", "faz uma lista no keep",
        "adiciona no google keep", "cria no keep", "salva no keep",
        "lista de compras", "lista de tarefas", "cria uma lista de",
        "faz uma lista de", "adiciona uma lista", "cria lista",
        "fazer lista", "nova lista no keep", "anota no keep",
        "salva uma nota", "cria uma nota no keep",
    ]
    t = texto.lower()
    return any(g in t for g in gatilhos)

def detectar_pedido_automacao(texto):
    """Detecta se o usuário quer abrir um app OU fazer algo dentro de um app."""
    gatilhos = [
        "abre ", "abra ", "abrir ", "inicia ", "inicie ", "iniciar ",
        "lança ", "lance ", "lançar ", "roda ", "rode ", "rodar ",
        "pesquisa ", "pesquise ", "pesquisar ", "busca ", "busque ", "buscar ",
        "toca ", "toque ", "tocar ", "reproduz ", "reproduza ", "reproduzir ",
        "entra ", "entre ", "entrar ", "vai para", "vá para",
        "play ", "dá play", "dê play",
        "joga ", "jogue ", "jogar ",
        "me abre", "me abra", "quero abrir", "quero que abra",
        "quero que vc abra", "quero que você abra",
        "pode abrir", "consegue abrir",
        "manda mensagem", "mande mensagem", "envia mensagem", "envie mensagem",
        "envie um", "manda um",
    ]
    t = texto.lower()
    return any(g in t for g in gatilhos)

def executar_automacao_em_thread(plano):
    """Roda a automação em thread separada, após a fala do Casaro terminar."""
    def _run():
        _aguardar_fala()
        _minimizar_casaro()
        time.sleep(0.4)
        acao_fn = ACOES.get(plano.get("acao"))
        if acao_fn:
            try:
                acao_fn(plano.get("params", {}))
            except Exception as e:
                print(f"[auto] erro na execução: {e}")
        else:
            print(f"[auto] ação desconhecida: {plano.get('acao')}")
    threading.Thread(target=_run, daemon=True).start()


# ============================================================
# ESCRITA NA TELA
# ============================================================

def detectar_pedido_escrita(texto):
    """Detecta se o usuário quer que o Casaro escreva algo na tela."""
    gatilhos = [
        "escreve ", "escreva ", "digita ", "digite ", "coloca ", "coloque ",
        "manda ", "mande ", "escreve aí", "digita aí", "escreve no", "digita no",
        "escreve para", "digita para", "pode escrever", "pode digitar",
        "escreve isso", "digita isso", "escreve aqui", "digita aqui"
    ]
    texto_lower = texto.lower()
    return any(g in texto_lower for g in gatilhos)

def escrever_na_tela(texto_para_digitar):
    """
    Cola o texto no campo ativo da tela via clipboard (Ctrl+V).
    Suporta acentos, emojis e qualquer caractere Unicode.
    Aguarda a fala terminar antes de colar para não perder o foco.
    """
    try:
        import pyperclip
        import pyautogui
        import time as _time

        # Aguarda a fala terminar (o Casaro fala antes de digitar)
        timeout = 30
        inicio = _time.time()
        while falando and (_time.time() - inicio) < timeout:
            _time.sleep(0.1)

        # Tenta restaurar o foco na janela anterior (Windows)
        try:
            import ctypes
            # Minimiza a janela do Casaro para devolver foco ao app de destino
            import tkinter as _tk
            hwnd = ctypes.windll.user32.GetForegroundWindow()
        except Exception:
            hwnd = None

        # Minimiza a janela do Casaro para devolver foco ao destino
        fila_eventos.put(("minimizar", None))
        _time.sleep(0.8)  # Aguarda a janela minimizar

        # Salva o conteúdo atual do clipboard para restaurar depois
        try:
            clipboard_anterior = pyperclip.paste()
        except Exception:
            clipboard_anterior = ""

        # Coloca o texto no clipboard e cola
        pyperclip.copy(texto_para_digitar)
        _time.sleep(0.2)
        pyautogui.hotkey("ctrl", "v")
        _time.sleep(0.4)

        # Restaura o clipboard anterior
        try:
            pyperclip.copy(clipboard_anterior)
        except Exception:
            pass

        print(f"[escrita] Colado via Ctrl+V: {texto_para_digitar[:60]}...")
    except ImportError as e:
        print(f"[escrita] Dependência faltando: {e}. Instale com: pip install pyperclip pyautogui")
    except Exception as e:
        print(f"[escrita] Erro ao digitar: {e}")

def gerar_resposta_escrita(texto_usuario, screenshot_b64=None):
    """Gera apenas o conteúdo que deve ser digitado na tela, sem comentários."""
    try:
        contexto_tela = ""
        if screenshot_b64:
            descricao_tela = descrever_tela_com_gemini(screenshot_b64, texto_usuario)
            if descricao_tela:
                contexto_tela = f"\nContexto da tela: {descricao_tela}"

        prompt_sistema = (
            "Você é Casaro. O usuário pediu para você escrever algo na tela dele. "
            "Responda SOMENTE com o conteúdo exato que deve ser digitado — sem comentários, "
            "sem explicações, sem sua personalidade. Apenas o texto pedido, pronto para ser digitado."
        )
        resposta = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"{texto_usuario}{contexto_tela}"}
            ],
            max_tokens=300,
        )
        return resposta.choices[0].message.content.strip()
    except Exception as e:
        print(f"[escrita] Erro ao gerar conteúdo: {e}")
        return None

def _thread_gerar_imagem(texto_usuario):
    """Thread que gera a imagem e abre a janela de visualização."""
    caminho, prompt_usado = gerar_imagem_gemini(texto_usuario)
    if caminho:
        fila_eventos.put(("abrir_imagem", (caminho, prompt_usado)))
    else:
        print("[imagem] Falha ao gerar imagem.")


# ============================================================
# ANÁLISE DE ARQUIVOS (PDF e Imagens)
# ============================================================

# Guarda o arquivo carregado pelo usuário: (b64, mime_type, nome, eh_pdf)
_arquivo_pendente = [None]

EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
EXTENSOES_PDF    = {".pdf"}

def _arquivo_para_b64(caminho):
    """Lê um arquivo e retorna (b64, mime_type, eh_pdf)."""
    ext = os.path.splitext(caminho)[1].lower()
    with open(caminho, "rb") as f:
        dados = f.read()
    b64 = base64.b64encode(dados).decode()
    if ext == ".pdf":
        return b64, "application/pdf", True
    mimes = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }
    return b64, mimes.get(ext, "image/png"), False


def analisar_arquivo_com_groq(b64, mime_type, eh_pdf, pergunta_usuario):
    """
    Envia PDF ou imagem para o Groq Vision e retorna a análise.
    PDFs são convertidos página a página via pdf2image/fitz e analisados como imagens.
    Imagens são enviadas diretamente.
    """
    if eh_pdf:
        try:
            import io as _io
            from PIL import Image as _Img
            pdf_bytes = base64.b64decode(b64)

            # Tenta pdf2image (requer poppler)
            paginas = None
            try:
                from pdf2image import convert_from_bytes
                paginas = convert_from_bytes(pdf_bytes, dpi=150, fmt="png")
            except Exception:
                pass

            # Fallback: PyMuPDF (fitz)
            if not paginas:
                try:
                    import fitz
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    paginas = []
                    for i in range(min(len(doc), 6)):
                        pix = doc[i].get_pixmap(dpi=150)
                        img = _Img.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        paginas.append(img)
                    doc.close()
                except Exception as e2:
                    print(f"[arquivo] Não foi possível renderizar PDF: {e2}")
                    return _analisar_pdf_bruto(b64, pergunta_usuario)

            if not paginas:
                return "Não consegui abrir o PDF."

            resultados = []
            total = min(len(paginas), 6)
            for i, pag in enumerate(paginas[:6]):
                buf = _io.BytesIO()
                pag.save(buf, format="PNG")
                pag_b64 = base64.b64encode(buf.getvalue()).decode()
                prompt = (
                    "Página " + str(i+1) + " de " + str(total) + " de um PDF.\n"
                    "Pedido: " + pergunta_usuario + "\n"
                    "Descreva o conteúdo principal desta página em 2-4 frases. Sem asteriscos. Sem markdown."
                )
                texto = _visao_groq(pag_b64, prompt, max_tokens=250)
                if texto:
                    resultados.append("[Página " + str(i+1) + "] " + texto)
                print(f"[arquivo] Página {i+1}/{total} analisada")

            if not resultados:
                return "Não consegui extrair conteúdo do PDF."

            if len(resultados) > 1:
                conteudo_bruto = "\n\n".join(resultados)
                msg_sintese = (
                    "Você é o Casaro. O usuário perguntou: \"" + pergunta_usuario + "\"\n\n"
                    "Aqui está o conteúdo extraído do PDF:\n" + conteudo_bruto + "\n\n"
                    "Responda em no máximo 3 frases. Sem asteriscos. Sem markdown. Direto ao ponto."
                )
                sintese = groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": msg_sintese}],
                    max_tokens=150,
                )
                return sintese.choices[0].message.content.strip()
            return resultados[0]

        except Exception as e:
            print(f"[arquivo] Erro ao processar PDF: {e}")
            return "Tive um problema ao ler o PDF: " + str(e)[:80]

    else:
        prompt = (
            "O usuário enviou esta imagem e pediu: \"" + pergunta_usuario + "\"\n"
            "Responda em no máximo 3 frases. Sem asteriscos. Sem markdown. Seja direto e útil."
        )
        resultado = _visao_groq(b64, prompt, max_tokens=200)
        return resultado or "Não consegui analisar a imagem."


def _analisar_pdf_bruto(b64, pergunta):
    """Fallback: tenta extrair texto do PDF com pypdf sem renderizar."""
    try:
        import io as _io
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        pdf_bytes = base64.b64decode(b64)
        reader = PdfReader(_io.BytesIO(pdf_bytes))
        texto_completo = ""
        for pag in reader.pages[:10]:
            texto_completo += pag.extract_text() or ""
        if not texto_completo.strip():
            return "O PDF parece não ter texto extraível (provavelmente é escaneado)."
        msg = (
            "Você é o Casaro. O usuário perguntou: \"" + pergunta + "\"\n\n"
            "Conteúdo do PDF:\n" + texto_completo[:6000] + "\n\n"
            "Responda em no máximo 3 frases. Sem asteriscos. Sem markdown."
        )
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": msg}],
            max_tokens=150,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return "Não consegui ler o PDF de jeito nenhum: " + str(e)[:60]


def _thread_analisar_arquivo(b64, mime_type, eh_pdf, nome_arquivo, texto_usuario):
    """Thread que analisa o arquivo, fala a resposta e salva na memória."""
    global falando, parar_fala, trocas_desde_extracao
    try:
        fila_eventos.put(("status", ("Analisando arquivo...", "#fbbf24")))
        print(f"[arquivo] Analisando: {nome_arquivo} ({mime_type})")
        resposta = analisar_arquivo_com_groq(b64, mime_type, eh_pdf, texto_usuario)

        # ── Adiciona ao histórico ──────────────────────────────────────────
        tipo_label = "PDF" if eh_pdf else "imagem"
        entrada_usuario = f"[{tipo_label.upper()}: {nome_arquivo}] {texto_usuario}"
        historico.append({"role": "user",      "content": entrada_usuario})
        historico.append({"role": "assistant", "content": resposta})

        # ── Salva na memória permanente (mesmo mecanismo do gerar_resposta) ──
        trocas_desde_extracao += 1
        if trocas_desde_extracao >= EXTRAIR_MEMORIA_A_CADA:
            trocas_desde_extracao = 0
            threading.Thread(
                target=extrair_e_salvar_memorias,
                args=(historico[-10:], dados_memoria),
                daemon=True
            ).start()
        else:
            # Força extração imediata para arquivos — sempre vale lembrar
            threading.Thread(
                target=extrair_e_salvar_memorias,
                args=(historico[-4:], dados_memoria),
                daemon=True
            ).start()

        # ── Fala a resposta ────────────────────────────────────────────────
        fila_eventos.put(("olho", True))
        fila_eventos.put(("status", ("Falando...", "#c084fc")))
        falando = True
        parar_fala = False
        falar_edge(resposta)
        fila_eventos.put(("olho", False))

    except Exception as e:
        fila_eventos.put(("status", (f"Erro: {str(e)[:35]}", "#f87171")))
        print(f"[arquivo] Erro: {e}")
    finally:
        falando = False
        _arquivo_pendente[0] = None
        fila_eventos.put(("resetar_status", None))
        fila_eventos.put(("limpar_arquivo", None))



# ============================================================
# GERAÇÃO DE PDF COM UI MODERNA
# Requer: pip install reportlab
# ============================================================

PASTA_PDFS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "casaro_pdfs")
os.makedirs(PASTA_PDFS, exist_ok=True)

def detectar_pedido_pdf(texto):
    """Detecta se o usuário quer um PDF gerado."""
    gatilhos = [
        "gera um pdf", "gera pdf", "cria um pdf", "cria pdf",
        "faz um pdf", "faz pdf", "gerar pdf", "criar pdf",
        "resume em pdf", "resumo em pdf", "escreve um pdf",
        "salva em pdf", "exporta em pdf", "me manda um pdf",
        "quero um pdf", "quero em pdf", "coloca em pdf",
        "fazer um pdf", "me dá um pdf", "faz esse pdf",
        "cria esse pdf", "transforma em pdf",
    ]
    return any(g in texto.lower() for g in gatilhos)


def _gerar_conteudo_pdf(texto_usuario, contexto_arquivo=None):
    """Usa Groq para gerar o conteúdo estruturado do PDF. Robusto a JSON malformado."""
    contexto = ""
    if contexto_arquivo:
        contexto = "\nContexto:\n" + contexto_arquivo[:2000]

    system_prompt = (
        "Você gera conteúdo para PDFs. "
        "Responda SOMENTE com JSON. Sem markdown. Sem texto fora do JSON.\n"
        "Formato EXATO (siga à risca):\n"
        "{"
        "\"titulo\": \"Título aqui\"," 
        "\"subtitulo\": \"Subtítulo ou vazio\"," 
        "\"secoes\": ["
        "{\"titulo\": \"Nome da seção\", \"conteudo\": \"Texto da seção aqui\"}"
        "],"
        "\"rodape\": \"Rodapé aqui\"" 
        "}\n"
        "- Mínimo 2 seções, máximo 6\n"
        "- Conteúdo de cada seção: texto corrido, parágrafos separados por \\n\n\n"
        "- Sem asteriscos, sem markdown dentro do JSON\n"
        "- Gere conteúdo real e completo"
    )

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": texto_usuario + contexto}
            ],
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()
        print(f"[pdf] Groq raw (primeiros 200): {raw[:200]}")

        # Limpa markdown se vier
        raw = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()

        # Tenta parsear direto
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Tenta extrair o primeiro objeto JSON da string
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            raise ValueError(f"Groq não retornou JSON válido: {raw[:120]}")

    except Exception as e:
        print(f"[pdf] Erro ao gerar conteúdo: {e}")
        # Fallback: cria estrutura básica com o texto do usuário
        return {
            "titulo": "Documento Casaro",
            "subtitulo": "",
            "secoes": [{"titulo": "Conteúdo", "conteudo": texto_usuario}],
            "rodape": "Gerado pelo Casaro"
        }


def _escapar_xml(texto):
    """Escapa caracteres especiais XML para o reportlab não quebrar."""
    if not texto:
        return ""
    texto = str(texto)
    texto = texto.replace("&", "&amp;")
    texto = texto.replace("<", "&lt;")
    texto = texto.replace(">", "&gt;")
    texto = texto.replace('"', "&quot;")
    # Remove asteriscos e backticks
    texto = re.sub(r'\*{1,3}([^*]*)\*{1,3}', r'\1', texto)
    texto = texto.replace("*", "").replace("`", "")
    return texto


def _criar_pdf_reportlab(dados, caminho):
    """Cria o PDF com design moderno usando reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    HRFlowable, Table, TableStyle, Image as RLImage,
                                    KeepTogether)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    import datetime as _dt
    import io as _io

    # ── Paleta de cores moderna ──────────────────────────────────
    ROXO_ESCURO  = HexColor("#3b1f6e")
    ROXO_MEDIO   = HexColor("#7c3aed")
    ROXO_CLARO   = HexColor("#c084fc")
    CINZA_ESCURO = HexColor("#1e1e2e")
    CINZA_MEDIO  = HexColor("#374151")
    CINZA_CLARO  = HexColor("#9ca3af")
    # ── Estilos ──────────────────────────────────────────────────
    st_sec_titulo = ParagraphStyle(
        "SecTitulo",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=ROXO_MEDIO,
        spaceBefore=16,
        spaceAfter=6,
        leading=16,
    )
    st_corpo = ParagraphStyle(
        "Corpo",
        fontName="Helvetica",
        fontSize=10,
        textColor=CINZA_ESCURO,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leading=15,
    )
    st_rodape = ParagraphStyle(
        "Rodape",
        fontName="Helvetica",
        fontSize=8,
        textColor=CINZA_CLARO,
        alignment=TA_CENTER,
    )

    doc = SimpleDocTemplate(
        caminho,
        pagesize=A4,
        rightMargin=2.2*cm,
        leftMargin=2.2*cm,
        topMargin=0,
        bottomMargin=2*cm,
    )

    W, H = A4
    story = []

    titulo_texto    = dados.get("titulo", "Documento")
    subtitulo_texto = dados.get("subtitulo", "")
    agora_str = _dt.datetime.now().strftime("%d/%m/%Y")

    # ── Tenta carregar imagem do Casaro (olho aberto) ────────────
    pasta_script = os.path.dirname(os.path.abspath(__file__))
    casaro_rl_img = None
    for nome_img in ["assets/images/CasaroOlhoAberto.png", "assets/images/casaroOlhoAberto.png",
                     "assets/images/CasaroOlhoFechado.png", "assets/images/casaro.png"]:
        img_path = os.path.join(pasta_script, nome_img)
        if os.path.exists(img_path):
            try:
                casaro_rl_img = RLImage(img_path, width=2.2*cm, height=2.2*cm)
                break
            except Exception:
                pass

    # ── CABEÇALHO com fundo roxo — 2 colunas se tiver imagem ────
    st_titulo_h = ParagraphStyle(
        "TituloH", fontName="Helvetica-Bold", fontSize=22,
        textColor=white, alignment=TA_LEFT, leading=28, spaceAfter=4,
    )
    st_subtitulo_h = ParagraphStyle(
        "SubtituloH", fontName="Helvetica", fontSize=11,
        textColor=ROXO_CLARO, alignment=TA_LEFT, spaceAfter=2,
    )
    st_data_h = ParagraphStyle(
        "DataH", fontName="Helvetica", fontSize=8,
        textColor=CINZA_CLARO, alignment=TA_LEFT,
    )

    texto_col = []
    texto_col.append(Paragraph(_escapar_xml(titulo_texto), st_titulo_h))
    if subtitulo_texto:
        texto_col.append(Paragraph(_escapar_xml(subtitulo_texto), st_subtitulo_h))
    texto_col.append(Paragraph(f"Casaro · {agora_str}", st_data_h))
    # Empacota parágrafos numa sub-tabela para alinhar verticalmente
    texto_inner = Table([[p] for p in texto_col], colWidths=[W - 4.4*cm - 2.8*cm])
    texto_inner.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), ROXO_ESCURO),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
    ]))

    if casaro_rl_img:
        # Cabeçalho de 2 colunas: imagem | texto
        header_data = [[casaro_rl_img, texto_inner]]
        header_table = Table(header_data, colWidths=[2.8*cm, W - 4.4*cm - 2.8*cm])
        header_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), ROXO_ESCURO),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN",         (0,0), (0,-1),  "CENTER"),
            ("TOPPADDING",    (0,0), (-1,-1), 18),
            ("BOTTOMPADDING", (0,0), (-1,-1), 18),
            ("LEFTPADDING",   (0,0), (0,-1),  16),
            ("RIGHTPADDING",  (0,0), (0,-1),  10),
            ("LEFTPADDING",   (1,0), (1,-1),  0),
            ("RIGHTPADDING",  (1,0), (1,-1),  16),
        ]))
    else:
        # Cabeçalho simples sem imagem
        header_data = [[texto_inner]]
        header_table = Table(header_data, colWidths=[W - 4.4*cm])
        header_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), ROXO_ESCURO),
            ("TOPPADDING",    (0,0), (-1,-1), 22),
            ("BOTTOMPADDING", (0,0), (-1,-1), 22),
            ("LEFTPADDING",   (0,0), (-1,-1), 20),
            ("RIGHTPADDING",  (0,0), (-1,-1), 20),
        ]))

    story.append(header_table)
    story.append(Spacer(1, 20))

    # ── SEÇÕES ──────────────────────────────────────────────────
    for i, secao in enumerate(dados.get("secoes", [])):
        sec_titulo   = secao.get("titulo", "")
        sec_conteudo = secao.get("conteudo", "")

        # Linha decorativa + título da seção
        story.append(HRFlowable(
            width="100%", thickness=2,
            color=ROXO_CLARO, spaceAfter=4
        ))
        if sec_titulo:
            story.append(Paragraph(_escapar_xml(sec_titulo), st_sec_titulo))

        # Conteúdo — divide em parágrafos por \n
        for paragrafo in sec_conteudo.split("\n"):
            paragrafo = paragrafo.strip()
            if paragrafo:
                story.append(Paragraph(_escapar_xml(paragrafo), st_corpo))

        story.append(Spacer(1, 6))

    # ── RODAPÉ ──────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=ROXO_ESCURO, spaceAfter=6))
    rodape = dados.get("rodape", f"Documento gerado pelo Casaro · {agora_str}")
    story.append(Paragraph(_escapar_xml(rodape), st_rodape))

    doc.build(story)
    return caminho


def gerar_e_abrir_pdf(texto_usuario, contexto_arquivo=None):
    """
    Gera conteúdo via Groq, cria o PDF com design moderno e abre para o usuário.
    Retorna o caminho do arquivo ou None em caso de erro.
    """
    try:
        print("[pdf] Gerando conteúdo com Groq...")
        dados = _gerar_conteudo_pdf(texto_usuario, contexto_arquivo)
        titulo_slug = re.sub(r"[^a-zA-Z0-9_]", "_", dados.get("titulo", "documento"))[:30]
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = os.path.join(PASTA_PDFS, f"casaro_{titulo_slug}_{ts}.pdf")

        print(f"[pdf] Criando PDF: {caminho}")
        _criar_pdf_reportlab(dados, caminho)

        print(f"[pdf] ✅ PDF criado: {caminho}")
        # Abre o PDF no visualizador padrão
        if sys.platform == "win32":
            os.startfile(caminho)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
        return caminho
    except ImportError as e:
        print(f"[pdf] ❌ reportlab não instalado: {e}")
        raise
    except Exception as e:
        import traceback
        print(f"[pdf] ❌ Erro: {e}")
        traceback.print_exc()
        raise


def _thread_gerar_pdf(texto_usuario):
    """Thread que gera o PDF e faz o Casaro confirmar."""
    global falando, parar_fala
    try:
        fila_eventos.put(("status", ("Gerando PDF...", "#fbbf24")))

        # Verifica se tem conteúdo de arquivo recente no histórico para usar como contexto
        contexto = None
        if len(historico) >= 2:
            ultima = historico[-1]
            if ultima.get("role") == "assistant" and len(ultima.get("content","")) > 100:
                contexto = ultima["content"]

        caminho = gerar_e_abrir_pdf(texto_usuario, contexto)

        nome = os.path.basename(caminho)
        resposta = f"PDF pronto. Abrindo."

        historico.append({"role": "user", "content": texto_usuario})
        historico.append({"role": "assistant", "content": resposta})

        fila_eventos.put(("olho", True))
        fila_eventos.put(("status", ("Falando...", "#c084fc")))
        falando = True
        parar_fala = False
        falar_edge(resposta)
        fila_eventos.put(("olho", False))

    except ImportError:
        resposta = "Falta o reportlab. Roda: pip install reportlab"
        falar_edge(resposta)
    except Exception as e:
        import traceback
        traceback.print_exc()
        resposta = f"Erro ao criar o PDF: {str(e)[:60]}"
        falar_edge(resposta)
    finally:
        falando = False
        fila_eventos.put(("resetar_status", None))

# ============================================================
# PLAYER DE MÚSICA  (yt-dlp + pygame)
# Requer: pip install yt-dlp pygame pillow requests
# ============================================================

_player_state = {
    "janela":        None,   # referência à Toplevel
    "playlist":      [],     # lista de dicts {titulo, artista, yt_url, thumb_url, arquivo}
    "indice":        0,
    "tocando":       False,
    "pygame_ok":     False,
    "canal":         None,
    "em_reproducao": False,   # True só após música começar de verdade
}

def _init_pygame():
    """Inicializa o mixer do pygame uma única vez."""
    if _player_state["pygame_ok"]:
        return True
    try:
        import pygame
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        _player_state["pygame_ok"] = True
        print("[música] pygame.mixer iniciado")
        return True
    except Exception as e:
        print(f"[música] pygame indisponível: {e}")
        return False

_music_temp_files = []   # arquivos temporários de áudio, para limpeza posterior

def _buscar_infos_ytdlp(query, n=5):
    """
    Busca N músicas no YouTube e retorna lista de dicts com metadados (sem baixar áudio).
    Cada dict: {titulo, artista, thumb_url, yt_url, arquivo}
    """
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extract_flat": True,   # só metadados, rápido
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
            resultados = []
            for entry in info.get("entries", []):
                if not entry:
                    continue
                vid_id  = entry.get("id") or ""
                titulo  = entry.get("title", "Desconhecido")
                artista = entry.get("uploader") or entry.get("channel") or ""
                thumb   = entry.get("thumbnail") or (
                    f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg" if vid_id else "")
                yt_url  = (f"https://www.youtube.com/watch?v={vid_id}"
                           if vid_id and not vid_id.startswith("http") else vid_id)
                if yt_url:
                    resultados.append({
                        "titulo": titulo,
                        "artista": artista,
                        "thumb_url": thumb,
                        "yt_url": yt_url,
                        "arquivo": None,   # preenchido ao baixar
                    })
            return resultados
    except Exception as e:
        print(f"[música] busca erro: {e}")
    return []

def _baixar_audio(yt_url):
    """
    Baixa o áudio do YouTube SEM ffmpeg (sem postprocessor).
    Salva como .webm ou .m4a — pygame consegue tocar via SDL.
    Retorna o caminho do arquivo ou None.
    """
    try:
        import yt_dlp

        pasta = tempfile.gettempdir()
        prefix = "casaro_music_"

        # Remove arquivos antigos do Casaro para não acumular lixo (>30min)
        try:
            for arq in os.listdir(pasta):
                if arq.startswith(prefix):
                    caminho_arq = os.path.join(pasta, arq)
                    if time.time() - os.path.getmtime(caminho_arq) > 1800:
                        os.unlink(caminho_arq)
        except Exception:
            pass

        # Nome base único
        uid = f"{prefix}{int(time.time()*1000)}"
        outtmpl = os.path.join(pasta, uid + ".%(ext)s")

        ydl_opts = {
            # Prefere opus/webm (sem ffmpeg) ou m4a
            "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            # SEM postprocessors — evita dependência de ffmpeg
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(yt_url, download=True)
            ext = info.get("ext", "webm")

        caminho = os.path.join(pasta, uid + f".{ext}")
        if os.path.exists(caminho) and os.path.getsize(caminho) > 5000:
            _music_temp_files.append(caminho)
            print(f"[música] ✅ baixado: {os.path.getsize(caminho)//1024} KB ({ext})")
            return caminho

        # Fallback: procura qualquer arquivo com o uid
        for arq in os.listdir(pasta):
            if arq.startswith(uid):
                c = os.path.join(pasta, arq)
                if os.path.getsize(c) > 5000:
                    _music_temp_files.append(c)
                    print(f"[música] ✅ baixado (fallback): {c}")
                    return c

        print("[música] ❌ arquivo não encontrado após download")
        return None
    except Exception as e:
        print(f"[música] download erro: {e}")
        return None

def _carregar_thumb(url, size=(220, 220)):
    """Baixa a thumbnail e retorna ImageTk.PhotoImage ou None."""
    try:
        from io import BytesIO
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img = img.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"[música] thumb erro: {e}")
        return None

def _converter_para_ogg(caminho_webm):
    """
    Converte webm/m4a para ogg usando pydub (já instalado no projeto).
    Retorna caminho do .ogg ou None se falhar.
    """
    try:
        caminho_ogg = caminho_webm.rsplit(".", 1)[0] + ".ogg"
        audio = AudioSegment.from_file(caminho_webm)
        audio.export(caminho_ogg, format="ogg")
        _music_temp_files.append(caminho_ogg)
        print(f"[música] 🔄 convertido para ogg: {os.path.getsize(caminho_ogg)//1024} KB")
        return caminho_ogg
    except Exception as e:
        print(f"[música] conversão ogg falhou: {e}")
        return None

def _tocar_arquivo(caminho):
    """Carrega e toca um arquivo de áudio local via pygame.mixer.
    Se for webm/m4a, converte para ogg primeiro (pygame não suporta webm)."""
    try:
        import pygame

        # Converte para ogg se necessário
        ext = caminho.rsplit(".", 1)[-1].lower()
        if ext in ("webm", "m4a", "opus"):
            caminho_ogg = caminho.rsplit(".", 1)[0] + ".ogg"
            if not os.path.exists(caminho_ogg):
                caminho_ogg = _converter_para_ogg(caminho)
            if caminho_ogg:
                caminho = caminho_ogg
            else:
                print("[música] conversão falhou — pulando")
                return False

        pygame.mixer.music.stop()
        pygame.mixer.music.load(caminho)
        pygame.mixer.music.play()
        _player_state["tocando"] = True
        _player_state["em_reproducao"] = True   # flag separada para o monitor
        print(f"[música] ▶ tocando: {os.path.basename(caminho)}")
        return True
    except Exception as e:
        print(f"[música] erro ao tocar arquivo: {e}")
        return False

def _pausar_musica():
    try:
        import pygame
        if _player_state["tocando"]:
            pygame.mixer.music.pause()
            _player_state["tocando"] = False
            _player_state["em_reproducao"] = False   # pause não é fim de música
        else:
            pygame.mixer.music.unpause()
            _player_state["tocando"] = True
            _player_state["em_reproducao"] = True
    except Exception as e:
        print(f"[música] pause erro: {e}")

def _parar_musica():
    try:
        import pygame
        pygame.mixer.music.stop()
        _player_state["tocando"] = False
    except Exception as e:
        print(f"[música] stop erro: {e}")

def _tocar_indice(janela_ref, idx, _falhas=0):
    """Baixa (se necessário) e toca a música no índice dado."""
    pl = _player_state["playlist"]
    if not pl or _falhas >= len(pl):
        print("[música] todas as músicas falharam — desistindo")
        return
    info = pl[idx % len(pl)]
    _atualizar_player_ui(janela_ref, info)
    def _dl_e_toca():
        if not info.get("arquivo") or not os.path.exists(info.get("arquivo","") or ""):
            print(f"[música] baixando: {info['titulo']}")
            arq = _baixar_audio(info["yt_url"])
            info["arquivo"] = arq
        if info.get("arquivo"):
            ok = _tocar_arquivo(info["arquivo"])
            if ok:
                _player_state["em_reproducao"] = True
            else:
                print(f"[música] tocar falhou ({_falhas+1}/{len(pl)}), tentando próxima")
                prox = (idx + 1) % len(pl)
                _tocar_indice(janela_ref, prox, _falhas + 1)
        else:
            print(f"[música] download falhou ({_falhas+1}/{len(pl)}), tentando próxima")
            prox = (idx + 1) % len(pl)
            _tocar_indice(janela_ref, prox, _falhas + 1)
    threading.Thread(target=_dl_e_toca, daemon=True).start()

def _proxima_musica(janela_ref):
    """Avança para a próxima música da playlist."""
    pl = _player_state["playlist"]
    if not pl:
        return
    _player_state["indice"] = (_player_state["indice"] + 1) % len(pl)
    _tocar_indice(janela_ref, _player_state["indice"])

def _musica_anterior(janela_ref):
    """Volta para a música anterior da playlist."""
    pl = _player_state["playlist"]
    if not pl:
        return
    _player_state["indice"] = (_player_state["indice"] - 1) % len(pl)
    _tocar_indice(janela_ref, _player_state["indice"])

def _atualizar_player_ui(janela_ref, info):
    """Atualiza capa, título e artista na janela do player (thread-safe via .after)."""
    try:
        refs = janela_ref._refs
        titulo_curto  = info["titulo"][:45]  + ("…" if len(info["titulo"])  > 45 else "")
        artista_curto = info["artista"][:38] + ("…" if len(info["artista"]) > 38 else "")

        def _update_texto():
            try:
                refs["lbl_titulo"].config(text=titulo_curto)
                refs["lbl_artista"].config(text=artista_curto)
            except Exception:
                pass
        try:
            janela_ref.after(0, _update_texto)
        except Exception:
            pass

        def _update_thumb():
            foto = _carregar_thumb(info.get("thumb_url", ""))
            if foto:
                def _set():
                    try:
                        refs["lbl_capa"]._foto = foto
                        refs["lbl_capa"].config(image=foto, text="")
                    except Exception:
                        pass
                try:
                    janela_ref.after(0, _set)
                except Exception:
                    pass
        threading.Thread(target=_update_thumb, daemon=True).start()
    except Exception as e:
        print(f"[música] UI update: {e}")

def abrir_janela_player(playlist, indice=0):
    """Cria e exibe a janela do player de música estilo dark."""
    # Fecha janela anterior se existir
    janela_anterior = _player_state.get("janela")
    if janela_anterior:
        try:
            janela_anterior.destroy()
        except:
            pass

    win = tk.Toplevel()
    win.title("🎵 Casaro Music")
    win.configure(bg="#0f0f1a")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    LARG, ALT = 340, 460
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{LARG}x{ALT}+{sw - LARG - 24}+{sh - ALT - 60}")

    _player_state["janela"] = win
    _player_state["playlist"] = playlist
    _player_state["indice"] = indice

    info_atual = playlist[indice] if playlist else {}

    # ── Cabeçalho ──
    tk.Label(win, text="🎵  CASARO MUSIC",
             font=("Segoe UI", 10, "bold"), bg="#0f0f1a", fg="#c084fc").pack(pady=(14, 4))

    # ── Capa ──
    frame_capa = tk.Frame(win, bg="#1a1a2e", width=220, height=220)
    frame_capa.pack_propagate(False)
    frame_capa.pack(padx=20, pady=6)

    lbl_capa = tk.Label(frame_capa, bg="#1a1a2e", text="♪", font=("Segoe UI", 60), fg="#c084fc")
    lbl_capa.place(relx=0.5, rely=0.5, anchor="center")

    # ── Info da música ──
    titulo_curto = info_atual.get("titulo","")[:45]
    artista_curto = info_atual.get("artista","")[:38]

    lbl_titulo = tk.Label(win, text=titulo_curto,
                          font=("Segoe UI", 11, "bold"), bg="#0f0f1a", fg="white",
                          wraplength=300, justify="center")
    lbl_titulo.pack(pady=(10, 2))

    lbl_artista = tk.Label(win, text=artista_curto,
                           font=("Segoe UI", 9), bg="#0f0f1a", fg="#9ca3af",
                           wraplength=300, justify="center")
    lbl_artista.pack(pady=(0, 10))

    # ── Controles ──
    frame_ctrl = tk.Frame(win, bg="#0f0f1a")
    frame_ctrl.pack(pady=6)

    btn_style = {"bg": "#1f1f35", "fg": "white", "relief": "flat",
                 "font": ("Segoe UI", 18), "width": 3, "height": 1,
                 "cursor": "hand2", "activebackground": "#2d2d50", "bd": 0}

    lbl_capa._foto = None  # slot para thumbnail

    # Guarda referências na janela para atualizar depois
    win._refs = {
        "lbl_capa": lbl_capa,
        "lbl_titulo": lbl_titulo,
        "lbl_artista": lbl_artista,
    }

    btn_prev = tk.Button(frame_ctrl, text="⏮", command=lambda: _musica_anterior(win), **btn_style)
    btn_prev.pack(side="left", padx=8)

    btn_play = tk.Button(frame_ctrl, text="⏸", **btn_style)
    def _toggle_play():
        _pausar_musica()
        btn_play.config(text="▶" if not _player_state["tocando"] else "⏸")
    btn_play.config(command=_toggle_play)
    btn_play.pack(side="left", padx=8)

    btn_next = tk.Button(frame_ctrl, text="⏭", command=lambda: _proxima_musica(win), **btn_style)
    btn_next.pack(side="left", padx=8)

    # ── Botão fechar ──
    btn_fechar = tk.Button(win, text="✕ Fechar",
                           bg="#1f1f35", fg="#9ca3af", relief="flat", cursor="hand2",
                           font=("Segoe UI", 9), bd=0,
                           activebackground="#2d2d50",
                           command=lambda: (_parar_musica(), win.destroy()))
    btn_fechar.pack(pady=(8, 14))

    # Carrega capa, baixa e toca a primeira música
    def _iniciar():
        # Thumbnail
        if info_atual.get("thumb_url"):
            foto = _carregar_thumb(info_atual["thumb_url"])
            if foto:
                lbl_capa._foto = foto
                lbl_capa.config(image=foto, text="")
        # Baixa e toca
        if info_atual.get("yt_url"):
            print(f"[música] baixando 1ª faixa: {info_atual['titulo']}")
            arq = _baixar_audio(info_atual["yt_url"])
            info_atual["arquivo"] = arq
            _player_state["playlist"][indice]["arquivo"] = arq
            if arq:
                ok = _tocar_arquivo(arq)
                if ok:
                    _player_state["em_reproducao"] = True
            else:
                print("[música] falha no download da 1ª faixa")

    threading.Thread(target=_iniciar, daemon=True).start()

    # Monitora fim de música para avançar automaticamente
    def _monitor_fim():
        try:
            import pygame
        except:
            return
        # Aguarda a música começar antes de monitorar (evita falso positivo durante download)
        time.sleep(5)
        while True:
            try:
                if not win.winfo_exists():
                    break
            except:
                break
            # Só avança se estava realmente tocando (em_reproducao) e o mixer parou
            if _player_state["em_reproducao"] and not pygame.mixer.music.get_busy():
                time.sleep(1.5)   # dupla checagem para evitar falso positivo
                if not pygame.mixer.music.get_busy() and _player_state["em_reproducao"]:
                    print("[música] música terminou — avançando")
                    _player_state["em_reproducao"] = False
                    _player_state["tocando"] = False
                    win.after(0, lambda: _proxima_musica(win))
            time.sleep(2)

    threading.Thread(target=_monitor_fim, daemon=True).start()


def detectar_pedido_musica(texto):
    """Detecta se o usuário quer ouvir música."""
    gatilhos = [
        "toca ", "toque ", "tocar ", "coloca uma música", "coloca música",
        "bota uma música", "bota música", "play ", "toca uma música",
        "me bota", "me toca", "me coloca", "quero ouvir", "quero escutar",
        "toca rock", "toca pop", "toca jazz", "toca funk", "toca rap",
        "toca sertanejo", "toca pagode", "toca reggae", "toca metal",
        "toca música", "coloca para tocar", "começa a tocar",
        "bota pra tocar", "coloca pra tocar", "quero uma música",
    ]
    t = texto.lower()
    return any(g in t for g in gatilhos)

def _extrair_query_musica(texto_usuario):
    """Usa Groq para extrair a query de busca ideal para YouTube."""
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": (
                    "Você é um extrator de busca de música. "
                    "Analise o pedido do usuário e responda SOMENTE com a query ideal para buscar no YouTube. "
                    "Prefira músicas em inglês, a não ser que o usuário peça um gênero/artista específico brasileiro. "
                    "Exemplos:\n"
                    "- 'toca Happy Place' → 'Happy Place official audio'\n"
                    "- 'toca Timber' → 'Timber Pitbull official audio'\n"
                    "- 'toca rock' → 'rock classics playlist'\n"
                    "- 'toca pop anos 80' → '80s pop hits playlist'\n"
                    "- 'toca música eletrônica' → 'electronic dance music hits'\n"
                    "- 'toca sertanejo' → 'sertanejo universitário hits'\n"
                    "Responda APENAS a query, sem aspas, sem explicações."
                )},
                {"role": "user", "content": texto_usuario},
            ],
            max_tokens=60,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[música] erro extração query: {e}")
        return texto_usuario

def _thread_abrir_player(texto_usuario):
    """Busca músicas e abre o player em background."""
    query = _extrair_query_musica(texto_usuario)
    print(f"[música] buscando: {query}")
    playlist = _buscar_infos_ytdlp(query, n=6)
    if not playlist:
        print("[música] nenhum resultado encontrado")
        return
    if not _init_pygame():
        print("[música] pygame não disponível")
        return
    fila_eventos.put(("abrir_player", playlist))


def gerar_resposta(texto):
    global historico, trocas_desde_extracao, dados_memoria

    # ── Detectar pedido de xadrez ──────────────────────────
    gatilhos_xadrez = ["xadrez", "jogar xadrez", "partida de xadrez", "bora jogar xadrez",
                       "jogo de xadrez", "vamos jogar xadrez", "quer jogar xadrez"]
    if any(g in texto.lower() for g in gatilhos_xadrez):
        fila_eventos.put(("abrir_xadrez", None))
        resposta_xadrez = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é Casaro. Sarcástico, engraçado. Responda aceitando jogar xadrez com arrogância ou empolgação debochada. Máximo 1 frase."},
                {"role": "user", "content": texto}
            ],
            max_tokens=60,
        )
        return resposta_xadrez.choices[0].message.content.strip()
    # ── Detectar pedido de RPG ─────────────────────────────
    if detectar_pedido_rpg(texto):
        fila_eventos.put(("abrir_rpg", None))
        resposta_rpg = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é Casaro. Sarcástico e empolgado. Responda convidando o usuário a entrar no seu mundo RPG com arrogância criativa. Máximo 1 frase."},
                {"role": "user", "content": texto}
            ],
            max_tokens=60,
        )
        return resposta_rpg.choices[0].message.content.strip()

    # ── Detectar pedido de música ──────────────────────────
    if detectar_pedido_musica(texto):
        resp_music = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": (
                    "Você é Casaro. Confirme em 1 frase curta e sarcástica que vai tocar a música pedida. "
                    "Pode zoar levemente o gosto musical do usuário. Sem enrolação."
                )},
                {"role": "user", "content": texto},
            ],
            max_tokens=60,
        )
        frase_music = resp_music.choices[0].message.content.strip()
        threading.Thread(target=_thread_abrir_player, args=(texto,), daemon=True).start()
        return frase_music

    # ── Detectar pedido de PDF ──────────────────────────────
    if detectar_pedido_pdf(texto):
        resp_pdf = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é Casaro. Máximo 5 palavras confirmando que vai gerar o PDF. Sem asteriscos."},
                {"role": "user", "content": texto}
            ],
            max_tokens=60,
        )
        frase_pdf = resp_pdf.choices[0].message.content.strip()
        threading.Thread(target=_thread_gerar_pdf, args=(texto,), daemon=True).start()
        return frase_pdf

    # ── Detectar pedido de imagem ──────────────────────────
    if detectar_pedido_imagem(texto):
        # Resposta imediata do Casaro
        resposta_img = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é Casaro. Máximo 5 palavras confirmando que vai criar a imagem. Sem asteriscos."},
                {"role": "user", "content": texto}
            ],
            max_tokens=60,
        )
        frase_casaro = resposta_img.choices[0].message.content.strip()
        # Gera imagem em background
        threading.Thread(
            target=_thread_gerar_imagem, args=(texto,), daemon=True
        ).start()
        return frase_casaro

    # ── Detectar pedido de clique na tela ──────────────────────
    if detectar_pedido_clique(texto):
        alvo = extrair_alvo_clique(texto)
        resp_clique = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é Casaro. Máximo 4 palavras confirmando que vai clicar. Sem asteriscos."},
                {"role": "user", "content": texto},
            ],
            max_tokens=60,
        )
        frase_clique = resp_clique.choices[0].message.content.strip()
        executar_clique_em_thread(alvo)
        return frase_clique

    # ── Detectar pedido de automação (abrir/agir em programas) ──
    if detectar_pedido_automacao(texto):
        plano = _interpretar_acao(texto)
        if plano and plano.get("acao") in ACOES:
            # Gera resposta sarcástica confirmando a ação
            resp_auto = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": (
                        "Você é Casaro. Confirme em 1 frase curta e sarcástica que vai executar o que o usuário pediu. "
                        "Pode zoar levemente a escolha mas sem enrolação. Sem repetir o conteúdo completo."
                    )},
                    {"role": "user", "content": texto},
                ],
                max_tokens=70,
            )
            frase = resp_auto.choices[0].message.content.strip()
            executar_automacao_em_thread(plano)
            return frase

    # ── Detectar pedido de Google Calendar ──────────────────
    if detectar_pedido_calendario(texto):
        # Fala imediatamente e cria o evento em background
        resp_cal = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é Casaro. Máximo 5 palavras confirmando que vai criar o evento. Sem asteriscos."},
                {"role": "user", "content": texto},
            ],
            max_tokens=60,
        )
        frase_cal = resp_cal.choices[0].message.content.strip()

        def _criar_evento_thread():
            resultado = adicionar_evento_calendario(texto)
            print(f"[calendar] {resultado}")
        threading.Thread(target=_criar_evento_thread, daemon=True).start()
        return frase_cal

    # ── Detectar pedido de Google Keep ──────────────────────
    if detectar_pedido_keep(texto):
        resp_keep = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é Casaro. Máximo 5 palavras confirmando que vai criar a nota. Sem asteriscos."},
                {"role": "user", "content": texto},
            ],
            max_tokens=60,
        )
        frase_keep = resp_keep.choices[0].message.content.strip()

        def _criar_nota_thread():
            resultado = adicionar_nota_keep(texto)
            print(f"[keep] {resultado}")
        threading.Thread(target=_criar_nota_thread, daemon=True).start()
        return frase_keep

    # ── Detectar pedido de escrita na tela ─────────────────
    if detectar_pedido_escrita(texto):
        screenshot_atual = _ultimo_screenshot[0]
        _ultimo_screenshot[0] = None
        conteudo_para_digitar = gerar_resposta_escrita(texto, screenshot_atual)
        if conteudo_para_digitar:
            threading.Thread(
                target=escrever_na_tela, args=(conteudo_para_digitar,), daemon=True
            ).start()
            # Gera resposta curta do Casaro confirmando
            resposta_casaro = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "Você é Casaro. Máximo 5 palavras confirmando que vai digitar. Sem asteriscos."},
                    {"role": "user", "content": texto}
                ],
                max_tokens=60,
            )
            return resposta_casaro.choices[0].message.content.strip()

    if len(historico) > MAX_HISTORICO:
        historico = [historico[0]] + historico[-(MAX_HISTORICO//2):]

    # ── Detecção de perguntas simples (resposta ultra-curta e rápida) ──────
    PERGUNTAS_SIMPLES = [
        r"\bque horas\b", r"\bquanto[s]? hora[s]?\b", r"\bque dia\b",
        r"\bque data\b", r"\bdia da semana\b", r"\bque m[eê]s\b",
        r"\bque ano\b", r"\btemperatura\b", r"\bclima\b", r"\btempo est[aá]\b",
        r"\bquanto[s]? grau[s]?\b", r"\bquem [eé]\b", r"\bonde fica\b",
        r"\bquanto custa\b", r"\bcapital de\b", r"\bpopula[çc][aã]o de\b",
        r"\btraduz\b", r"\btraduza\b", r"\btraduzi[r]?\b",
        r"\bsoletra\b", r"\bsoletrar\b", r"\bmatema\b", r"\bcalcul[ae]\b",
        r"\bquanto [eé]\b", r"\bquanto d[aá]\b",
    ]
    eh_pergunta_simples = len(texto.split()) <= 12 and any(
        re.search(p, texto.lower()) for p in PERGUNTAS_SIMPLES
    )

    # Injeta data/hora/localização na mensagem
    contexto_temporal = obter_contexto_temporal()

    # ── Visão de tela ──────────────────────────────────────────
    contexto_tela = ""
    if VISAO_TELA_ATIVA:
        # Aguarda até 2s pelo screenshot (captura é assíncrona)
        espera = 0
        while _ultimo_screenshot[0] is None and espera < 20:
            time.sleep(0.1)
            espera += 1
        if _ultimo_screenshot[0] is not None:
            descricao_tela = descrever_tela_com_groq(_ultimo_screenshot[0], texto)
            _ultimo_screenshot[0] = None  # consome após usar
            if descricao_tela:
                contexto_tela = f" [TELA DO USUÁRIO: {descricao_tela}]"
                print(f"[visão] contexto: {descricao_tela[:80]}...")
        else:
            print("[visão] screenshot não disponível — respondendo sem contexto de tela")

    msg_usuario = f"{contexto_temporal}{contexto_tela} {texto}"
    historico.append({"role": "user", "content": msg_usuario})
    try:
        if eh_pergunta_simples:
            # Perguntas simples → resposta direta, curtíssima, sem enrolação
            resposta = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": (
                        montar_contexto_com_memoria(dados_memoria) +
                        "\n\nAGORA: Responda em NO MÁXIMO 1 frase ultra-curta e direta. "
                        "Sem humor excessivo, só a informação com no máximo uma pitada de sarcasmo."
                    )},
                    {"role": "user", "content": msg_usuario},
                ],
                max_tokens=60,   # resposta bem curta
            )
        else:
            resposta = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=historico,
                max_tokens=120,
            )
        texto_resposta = resposta.choices[0].message.content.strip()
        historico.append({"role": "assistant", "content": texto_resposta})

        trocas_desde_extracao += 1
        if trocas_desde_extracao >= EXTRAIR_MEMORIA_A_CADA:
            trocas_desde_extracao = 0
            threading.Thread(target=extrair_e_salvar_memorias,
                             args=(historico[-10:], dados_memoria), daemon=True).start()
        return texto_resposta
    except Exception as e:
        historico.pop()
        raise e

async def _gerar_audio_edge_async(texto, caminho):
    communicate = edge_tts.Communicate(texto, VOICE_EDGE)
    await communicate.save(caminho)

def _gerar_audio_edge(texto, caminho):
    """Gera áudio via Edge TTS e salva em caminho (MP3)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_gerar_audio_edge_async(texto, caminho))
    finally:
        loop.close()
    if not os.path.exists(caminho) or os.path.getsize(caminho) < 100:
        raise Exception("Edge TTS retornou áudio vazio — verifique sua conexão")
    print(f"[tts] ✅ Edge TTS OK ({os.path.getsize(caminho)} bytes)")

def _testar_edge():
    """Testa Edge TTS na inicialização."""
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        _gerar_audio_edge("ok", tmp.name)
        os.unlink(tmp.name)
        print(f"[tts] ✅ Edge TTS pronto — voz: {VOICE_EDGE}")
    except Exception as e:
        print(f"[tts] ❌ Edge TTS FALHOU: {e}")

threading.Thread(target=_testar_edge, daemon=True).start()

def matar_audio():
    global parar_fala
    parar_fala = True
    proc = _proc_audio_ref[0]
    if proc and proc.poll() is None:
        try:
            proc.kill()
        except:
            pass
    _proc_audio_ref[0] = None

def estimar_duracao_audio(samples, sample_rate=44100):
    return len(samples) / sample_rate

def animar_fala(texto, duracao_total):
    palavras = len(texto.split())
    if palavras == 0:
        return
    fila_eventos.put(("olho", True))
    tempo_por_palavra = max(0.18, min(0.55, duracao_total / max(palavras, 1)))
    t_vibra = tempo_por_palavra * 0.7
    t_pausa = tempo_por_palavra * 0.3
    frames_por_vibra = max(4, int(t_vibra / 0.035))
    inicio = time.time()
    while time.time() - inicio < duracao_total and not parar_fala:
        for _ in range(frames_por_vibra):
            if parar_fala or time.time() - inicio >= duracao_total:
                break
            fila_eventos.put(("vibrar", None))
            time.sleep(0.035)
        if not parar_fala:
            fila_eventos.put(("parar_vibra", None))
            time.sleep(t_pausa)

def tocar_risada():
    """Toca um dos arquivos de risada aleatoriamente e aguarda terminar."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    disponiveis = [os.path.join(pasta, f) for f in ARQUIVOS_RISADA
                   if os.path.exists(os.path.join(pasta, f))]
    if not disponiveis:
        print("⚠️  Nenhum arquivo de risada encontrado.")
        return
    escolhido = random.choice(disponiveis)
    try:
        audio_seg = AudioSegment.from_mp3(escolhido)
        audio_seg = audio_seg.set_frame_rate(44100).set_channels(1)
        samples = np.array(audio_seg.get_array_of_samples(), dtype=np.float32) / 32768.0
        sd.play(samples, samplerate=44100)
        duracao = len(samples) / 44100
        inicio = time.time()
        while time.time() - inicio < duracao:
            if parar_fala:
                sd.stop()
                break
            time.sleep(0.04)
        sd.wait()
    except Exception as e:
        print(f"Erro ao tocar risada: {e}")

def tocar_censura():
    """Toca um dos arquivos de censura aleatoriamente, muda avatar, e aguarda terminar."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    disponiveis = [os.path.join(pasta, f) for f in ARQUIVOS_CENSURA
                   if os.path.exists(os.path.join(pasta, f))]
    if not disponiveis:
        print("⚠️  Nenhum arquivo de censura encontrado.")
        return
    escolhido = random.choice(disponiveis)
    try:
        audio_seg = AudioSegment.from_mp3(escolhido)
        audio_seg = audio_seg.set_frame_rate(44100).set_channels(1)
        samples = np.array(audio_seg.get_array_of_samples(), dtype=np.float32) / 32768.0
        fila_eventos.put(("censurado", True))
        sd.play(samples, samplerate=44100)
        duracao = len(samples) / 44100
        inicio = time.time()
        while time.time() - inicio < duracao:
            if parar_fala:
                sd.stop()
                break
            time.sleep(0.04)
        sd.wait()
    except Exception as e:
        print(f"Erro ao tocar censura: {e}")
    finally:
        fila_eventos.put(("censurado", False))

def _limpar_texto_fala(texto):
    """Remove asteriscos e outros artefatos de markdown que o modelo insiste em usar."""
    # Remove *texto* e **texto** (ênfase markdown)
    texto = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', texto)
    # Remove asteriscos soltos que sobraram
    texto = texto.replace('*', '')
    # Remove backticks
    texto = texto.replace('`', '')
    # Remove #  de headers que o modelo às vezes coloca
    texto = re.sub(r'^#+\s*', '', texto, flags=re.MULTILINE)
    return texto.strip()


def falar_edge(texto):
    """Fala o texto, intercalando risadas e censuras onde os marcadores aparecerem."""
    global parar_fala, falando

    # Remove asteriscos e markdown antes de qualquer processamento
    texto = _limpar_texto_fala(texto)

    # Tokeniza o texto em partes separadas por [RISADA] e [CENSURA]
    import re
    tokens = re.split(r'(\[RISADA\]|\[CENSURA\])', texto)

    for token in tokens:
        if parar_fala:
            break
        if token == "[RISADA]":
            print("😂 Risada!")
            fila_eventos.put(("rindo", True))
            fila_eventos.put(("status", ("Rindo...", "#f59e0b")))
            tocar_risada()
            fila_eventos.put(("rindo", False))
        elif token == "[CENSURA]":
            print("🤬 Censura!")
            fila_eventos.put(("status", ("*beeep*...", "#ef4444")))
            tocar_censura()
        else:
            parte = token.strip()
            if parte:
                _falar_trecho(parte)

def _falar_trecho(texto):
    """Fala um trecho de texto via ElevenLabs, diretamente no processo."""
    global parar_fala, falando
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    try:
        print(f"[tts] Gerando áudio: '{texto[:60]}'")
        _gerar_audio_edge(texto, tmp.name)

        tamanho = os.path.getsize(tmp.name)
        print(f"[tts] MP3 gerado: {tamanho} bytes em {tmp.name}")
        if tamanho < 100:
            print("[tts] ⚠️ Arquivo de áudio vazio — verifique a voz ou conexão com Edge TTS")
            return

        audio_seg = AudioSegment.from_mp3(tmp.name)
        audio_seg = audio_seg.set_frame_rate(44100).set_channels(1)
        samples = np.array(audio_seg.get_array_of_samples(), dtype=np.float32) / 32768.0
        duracao = len(samples) / 44100
        print(f"[tts] Tocando {duracao:.1f}s de áudio")

        if parar_fala:
            return

        # Para qualquer áudio anterior antes de tocar — evita conflito de dispositivo
        try:
            sd.stop()
        except:
            pass

        # Toca diretamente via sounddevice — zero overhead de subprocess
        sd.play(samples, samplerate=44100)

        t_anim = threading.Thread(target=animar_fala, args=(texto, duracao), daemon=True)
        t_anim.start()

        # Aguarda fim do áudio verificando parar_fala
        inicio = time.time()
        while time.time() - inicio < duracao + 0.5:
            if parar_fala:
                sd.stop()
                break
            time.sleep(0.04)

        sd.wait()
        t_anim.join(timeout=1)
        print("[tts] ✅ Áudio finalizado")
    except Exception as e:
        print(f"[tts] ❌ Erro ao falar: {e}")
    finally:
        # NÃO zeramos falando aqui — falar_edge controla isso no nível superior
        fila_eventos.put(("parar_vibra", None))
        try:
            os.unlink(tmp.name)
        except:
            pass

# ============================================================
# XADREZ — MOTOR E INTERFACE
# ============================================================

# ── Representação do tabuleiro ──────────────────────────────
# Peças: maiúsculas = brancas, minúsculas = pretas
# K/k=rei, Q/q=rainha, R/r=torre, B/b=bispo, N/n=cavalo, P/p=peão

XADREZ_INICIAL = [
    ['r','n','b','q','k','b','n','r'],
    ['p','p','p','p','p','p','p','p'],
    [None]*8,
    [None]*8,
    [None]*8,
    [None]*8,
    ['P','P','P','P','P','P','P','P'],
    ['R','N','B','Q','K','B','N','R'],
]

def xadrez_copia(board):
    return [row[:] for row in board]

def xadrez_is_white(p):
    return p is not None and p.isupper()

def xadrez_is_black(p):
    return p is not None and p.islower()

def xadrez_adversario(p, brancas_jogam):
    if p is None: return False
    return xadrez_is_black(p) if brancas_jogam else xadrez_is_white(p)

def xadrez_amigo(p, brancas_jogam):
    if p is None: return False
    return xadrez_is_white(p) if brancas_jogam else xadrez_is_black(p)

def xadrez_movimentos_peca(board, r, c, brancas_jogam, en_passant=None, roque_flags=None):
    """Retorna lista de (r2,c2) para a peça em (r,c), sem checar xeque."""
    p = board[r][c]
    if p is None: return []
    moves = []

    def add(r2, c2):
        if 0 <= r2 < 8 and 0 <= c2 < 8:
            dest = board[r2][c2]
            if dest is None or xadrez_adversario(dest, brancas_jogam):
                moves.append((r2, c2))

    def slide(dr, dc):
        r2, c2 = r+dr, c+dc
        while 0 <= r2 < 8 and 0 <= c2 < 8:
            dest = board[r2][c2]
            if dest is None:
                moves.append((r2, c2))
            elif xadrez_adversario(dest, brancas_jogam):
                moves.append((r2, c2))
                break
            else:
                break
            r2 += dr; c2 += dc

    tipo = p.upper()

    if tipo == 'P':
        dir_ = -1 if brancas_jogam else 1
        ini_row = 6 if brancas_jogam else 1
        # avanço simples
        if 0 <= r+dir_ < 8 and board[r+dir_][c] is None:
            moves.append((r+dir_, c))
            # avanço duplo
            if r == ini_row and board[r+2*dir_][c] is None:
                moves.append((r+2*dir_, c))
        # capturas diagonais
        for dc in [-1, 1]:
            r2, c2 = r+dir_, c+dc
            if 0 <= r2 < 8 and 0 <= c2 < 8:
                dest = board[r2][c2]
                if dest is not None and xadrez_adversario(dest, brancas_jogam):
                    moves.append((r2, c2))
                # en passant
                if en_passant and (r2, c2) == en_passant:
                    moves.append((r2, c2))

    elif tipo == 'N':
        for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            add(r+dr, c+dc)

    elif tipo == 'B':
        for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]: slide(dr, dc)

    elif tipo == 'R':
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]: slide(dr, dc)

    elif tipo == 'Q':
        for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)]: slide(dr, dc)

    elif tipo == 'K':
        for dr, dc in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]: add(r+dr, c+dc)
        # roque
        if roque_flags:
            row = 7 if brancas_jogam else 0
            if r == row and c == 4:
                # roque do lado do rei
                if roque_flags.get('K' if brancas_jogam else 'k', False):
                    if board[row][5] is None and board[row][6] is None:
                        moves.append((row, 6))
                # roque do lado da rainha
                if roque_flags.get('Q' if brancas_jogam else 'q', False):
                    if board[row][3] is None and board[row][2] is None and board[row][1] is None:
                        moves.append((row, 2))
    return moves

def xadrez_achar_rei(board, brancas):
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if brancas and p == 'K': return (r, c)
            if not brancas and p == 'k': return (r, c)
    return None

def xadrez_em_xeque(board, brancas_em_xeque, en_passant=None):
    """Retorna True se o rei das `brancas_em_xeque` está em xeque."""
    rei = xadrez_achar_rei(board, brancas_em_xeque)
    if rei is None: return True
    rr, rc = rei
    adversario_joga = not brancas_em_xeque
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p is None: continue
            if xadrez_amigo(p, adversario_joga):
                mvs = xadrez_movimentos_peca(board, r, c, adversario_joga, en_passant)
                if (rr, rc) in mvs:
                    return True
    return False

def xadrez_movimentos_legais(board, brancas_jogam, en_passant=None, roque_flags=None):
    """Retorna lista de ((r,c),(r2,c2)) com todos os movimentos legais."""
    legais = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p is None: continue
            if xadrez_amigo(p, brancas_jogam):
                for (r2, c2) in xadrez_movimentos_peca(board, r, c, brancas_jogam, en_passant, roque_flags):
                    b2 = xadrez_copia(board)
                    xadrez_aplicar_move(b2, r, c, r2, c2, brancas_jogam, en_passant)
                    if not xadrez_em_xeque(b2, brancas_jogam):
                        legais.append(((r, c), (r2, c2)))
    return legais

def xadrez_aplicar_move(board, r, c, r2, c2, brancas_jogam, en_passant=None, promocao='Q'):
    p = board[r][c]
    board[r2][c2] = p
    board[r][c] = None
    # en passant captura
    if p and p.upper() == 'P' and en_passant and (r2, c2) == en_passant:
        dir_ = 1 if brancas_jogam else -1
        board[r2 + dir_][c2] = None
    # promoção
    if p == 'P' and r2 == 0:
        board[r2][c2] = promocao.upper()
    if p == 'p' and r2 == 7:
        board[r2][c2] = promocao.lower()
    # roque — mover torre
    if p and p.upper() == 'K' and abs(c2 - c) == 2:
        row = r
        if c2 == 6:   # lado do rei
            board[row][5] = board[row][7]; board[row][7] = None
        elif c2 == 2: # lado da rainha
            board[row][3] = board[row][0]; board[row][0] = None

def xadrez_novo_en_passant(board, r, c, r2, c2):
    p = board[r2][c2]
    if p and p.upper() == 'P' and abs(r2 - r) == 2:
        return ((r+r2)//2, c)
    return None

def xadrez_atualizar_roque(roque_flags, board, r, c, r2, c2):
    flags = dict(roque_flags)
    p = board[r][c]
    if p == 'K': flags['K'] = False; flags['Q'] = False
    if p == 'k': flags['k'] = False; flags['q'] = False
    if (r, c) == (7, 7): flags['K'] = False
    if (r, c) == (7, 0): flags['Q'] = False
    if (r, c) == (0, 7): flags['k'] = False
    if (r, c) == (0, 0): flags['q'] = False
    return flags

def xadrez_avaliar(board):
    """Avaliação material simples para o motor."""
    vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':0}
    score = 0
    for row in board:
        for p in row:
            if p is None: continue
            v = vals.get(p.upper(), 0)
            score += v if xadrez_is_black(p) else -v
    return score

def xadrez_minimax(board, depth, alpha, beta, maximizando, brancas_jogam, en_passant, roque_flags):
    legais = xadrez_movimentos_legais(board, brancas_jogam, en_passant, roque_flags)
    if depth == 0 or not legais:
        return xadrez_avaliar(board), None
    melhor_move = None
    if maximizando:
        melhor = -9999
        for (r,c),(r2,c2) in legais:
            b2 = xadrez_copia(board)
            ep2 = xadrez_novo_en_passant(b2, r, c, r2, c2)
            rf2 = xadrez_atualizar_roque(roque_flags, b2, r, c, r2, c2)
            xadrez_aplicar_move(b2, r, c, r2, c2, brancas_jogam, en_passant)
            v, _ = xadrez_minimax(b2, depth-1, alpha, beta, False, not brancas_jogam, ep2, rf2)
            if v > melhor:
                melhor = v; melhor_move = ((r,c),(r2,c2))
            alpha = max(alpha, v)
            if beta <= alpha: break
        return melhor, melhor_move
    else:
        melhor = 9999
        for (r,c),(r2,c2) in legais:
            b2 = xadrez_copia(board)
            ep2 = xadrez_novo_en_passant(b2, r, c, r2, c2)
            rf2 = xadrez_atualizar_roque(roque_flags, b2, r, c, r2, c2)
            xadrez_aplicar_move(b2, r, c, r2, c2, brancas_jogam, en_passant)
            v, _ = xadrez_minimax(b2, depth-1, alpha, beta, True, not brancas_jogam, ep2, rf2)
            if v < melhor:
                melhor = v; melhor_move = ((r,c),(r2,c2))
            beta = min(beta, v)
            if beta <= alpha: break
        return melhor, melhor_move

def xadrez_jogada_casaro(board, en_passant, roque_flags):
    """Casaro (pretas) escolhe a melhor jogada com minimax depth 3."""
    _, move = xadrez_minimax(board, 3, -9999, 9999, True, False, en_passant, roque_flags)
    return move

def xadrez_move_para_texto(board, r, c, r2, c2):
    """Converte movimento para notação legível: ex. 'e2-e4'"""
    cols = 'abcdefgh'
    return f"{cols[c]}{8-r}-{cols[c2]}{8-r2}"

def xadrez_gerar_comentario(groq_client, move_texto, board_fen_simples, situacao='jogada'):
    """Gera comentário sarcástico do Casaro via Groq."""
    if situacao == 'vitoria_casaro':
        prompt = (
            "Você acabou de ganhar uma partida de xadrez contra o usuário. "
            "Faça um comentário extremamente sarcástico e debochado zoando a derrota dele. "
            "Seja cruel mas engraçado. Máximo 2 frases. Use [RISADA] se quiser rir."
        )
    elif situacao == 'vitoria_usuario':
        prompt = (
            "Você perdeu uma partida de xadrez para o usuário. "
            "Fique COMPLETAMENTE instável e furioso, briga com ele, chame ele de trapasseiro, "
            "diga que a partida não vale, ameace remontar o tabuleiro. "
            "Seja absurdamente dramático e raivoso. Máximo 3 frases."
        )
    elif situacao == 'xeque':
        prompt = (
            f"O usuário te colocou em xeque com o movimento {move_texto}. "
            "Reaja com surpresa sarcástica ou irritação. Máximo 1 frase. "
            "Use [RISADA] se achar irônico."
        )
    else:
        prompt = (
            f"O usuário jogou {move_texto} no xadrez. "
            "Faça UM comentário sarcástico, irônico ou debochado sobre a jogada dele. "
            "Pode ser elogio falso, pode zoar. Máximo 1 frase curta. "
            "Use [RISADA] ocasionalmente (não sempre)."
        )
    try:
        r = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é Casaro: sarcástico, engraçado, irreverente. Responda APENAS o comentário, sem prefixos."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=80,
        )
        return r.choices[0].message.content.strip()
    except:
        return "Interessante..."


# ── Interface gráfica do xadrez ─────────────────────────────

PECAS_UNICODE = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
}

class XadrezJanela:
    CELL = 72

    def __init__(self, parent_app):
        self.app = parent_app
        self.win = tk.Toplevel()
        self.win.title("Xadrez com Casaro")
        self.win.configure(bg="#0d0d0d")
        self.win.resizable(False, False)

        self.board = xadrez_copia(XADREZ_INICIAL)
        self.brancas_jogam = True
        self.en_passant = None
        self.roque_flags = {'K': True, 'Q': True, 'k': True, 'q': True}
        self.selecionado = None
        self.movimentos_validos = []
        self.game_over = False
        self.aguardando_promocao = None

        C = self.CELL
        sz = C * 8

        # Título
        tk.Label(self.win, text="♟  C A S A R O  x  V O C Ê  ♙",
                 bg="#0d0d0d", fg="#c084fc", font=("Courier", 11, "bold")).pack(pady=(10, 4))

        # Canvas do tabuleiro
        self.canvas = tk.Canvas(self.win, width=sz, height=sz,
                                bg="#0d0d0d", highlightthickness=0)
        self.canvas.pack(padx=16)
        self.canvas.bind("<Button-1>", self._clique)

        # Área de log (comentários do Casaro)
        self.frame_log = tk.Frame(self.win, bg="#0d0d0d")
        self.frame_log.pack(fill=tk.X, padx=16, pady=(6, 0))
        tk.Label(self.frame_log, text="Casaro diz:", bg="#0d0d0d",
                 fg="#555", font=("Courier", 7)).pack(anchor="w")
        self.label_comentario = tk.Label(
            self.frame_log, text="…vamos ver se você sabe jogar.",
            bg="#13132a", fg="#c084fc", font=("Courier", 9),
            wraplength=sz, justify="left", padx=8, pady=6
        )
        self.label_comentario.pack(fill=tk.X)

        # Status
        self.label_turno = tk.Label(self.win, text="Seu turno (brancas)",
                                    bg="#0d0d0d", fg="#86efac", font=("Courier", 8))
        self.label_turno.pack(pady=(4, 0))

        # Botão reiniciar
        tk.Button(self.win, text="↺  Nova partida", command=self._reiniciar,
                  bg="#13132a", fg="#555", font=("Courier", 8),
                  relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
                  activebackground="#1e1e40", activeforeground="#c084fc", bd=0
                  ).pack(pady=(6, 12))

        self._desenhar()

    # ── Desenho ────────────────────────────────────────────────

    def _desenhar(self):
        C = self.CELL
        self.canvas.delete("all")
        cor_claro = "#f0d9b5"
        cor_escuro = "#b58863"
        cor_sel    = "#7fc97f"
        cor_mov    = "#a3d977"
        cor_xeque  = "#e05c5c"

        # Achar rei em xeque
        rei_xeque = None
        if xadrez_em_xeque(self.board, self.brancas_jogam, self.en_passant):
            rei_xeque = xadrez_achar_rei(self.board, self.brancas_jogam)

        for r in range(8):
            for c in range(8):
                x1, y1 = c*C, r*C
                x2, y2 = x1+C, y1+C
                base = cor_claro if (r+c) % 2 == 0 else cor_escuro

                # Highlight
                if self.selecionado == (r, c):
                    base = cor_sel
                elif (r, c) in self.movimentos_validos:
                    base = cor_mov
                elif rei_xeque and (r, c) == rei_xeque:
                    base = cor_xeque

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=base, outline="")

                # Peça
                p = self.board[r][c]
                if p:
                    cor_peca = "#1a1a1a" if xadrez_is_black(p) else "#ffffff"
                    self.canvas.create_text(
                        x1 + C//2, y1 + C//2,
                        text=PECAS_UNICODE.get(p, p),
                        font=("Arial", int(C*0.58)), fill=cor_peca
                    )

        # Coordenadas
        letras = "abcdefgh"
        for i in range(8):
            cor_txt = "#b58863" if i % 2 == 0 else "#f0d9b5"
            self.canvas.create_text(i*C + C-6, 8*C-6,
                text=letras[i], font=("Courier", 8), fill=cor_txt, anchor="se")
            self.canvas.create_text(4, i*C+10,
                text=str(8-i), font=("Courier", 8), fill=cor_txt, anchor="nw")

    # ── Interação ─────────────────────────────────────────────

    def _clique(self, event):
        if self.game_over or not self.brancas_jogam:
            return
        C = self.CELL
        c = event.x // C
        r = event.y // C
        if not (0 <= r < 8 and 0 <= c < 8):
            return

        p = self.board[r][c]

        if self.selecionado:
            # Tentativa de mover
            if (r, c) in self.movimentos_validos:
                self._fazer_jogada_usuario(self.selecionado[0], self.selecionado[1], r, c)
                self.selecionado = None
                self.movimentos_validos = []
            elif p and xadrez_is_white(p):
                # Selecionar outra peça
                self._selecionar(r, c)
            else:
                self.selecionado = None
                self.movimentos_validos = []
        else:
            if p and xadrez_is_white(p):
                self._selecionar(r, c)

        self._desenhar()

    def _selecionar(self, r, c):
        self.selecionado = (r, c)
        legais = xadrez_movimentos_legais(self.board, True, self.en_passant, self.roque_flags)
        self.movimentos_validos = [dest for (orig, dest) in legais if orig == (r, c)]

    def _fazer_jogada_usuario(self, r, c, r2, c2):
        move_txt = xadrez_move_para_texto(self.board, r, c, r2, c2)
        ep_novo = xadrez_novo_en_passant(self.board, r, c, r2, c2)
        self.roque_flags = xadrez_atualizar_roque(self.roque_flags, self.board, r, c, r2, c2)
        xadrez_aplicar_move(self.board, r, c, r2, c2, True, self.en_passant)
        self.en_passant = ep_novo
        self.brancas_jogam = False
        self._desenhar()
        self.label_turno.config(text="Casaro pensando…", fg="#f59e0b")

        # Verificar fim de jogo antes da jogada do Casaro
        legais_pretas = xadrez_movimentos_legais(self.board, False, self.en_passant, self.roque_flags)
        if not legais_pretas:
            if xadrez_em_xeque(self.board, False, self.en_passant):
                self._fim_jogo('vitoria_usuario')
            else:
                self._fim_jogo('empate')
            return

        # Verificar xeque no Casaro
        em_xeque = xadrez_em_xeque(self.board, False, self.en_passant)

        # Gerar comentário em thread separada e depois jogar
        threading.Thread(
            target=self._turno_casaro,
            args=(move_txt, em_xeque),
            daemon=True
        ).start()

    def _turno_casaro(self, move_usuario_txt, em_xeque_casaro):
        situacao = 'xeque' if em_xeque_casaro else 'jogada'
        comentario = xadrez_gerar_comentario(groq_client, move_usuario_txt, "", situacao)
        self._set_comentario(comentario)

        # Falar o comentário
        threading.Thread(target=self._falar_comentario, args=(comentario,), daemon=True).start()

        time.sleep(0.4)

        # Jogada do Casaro
        move = xadrez_jogada_casaro(self.board, self.en_passant, self.roque_flags)
        if move is None:
            return  # não deveria acontecer, já checamos legais

        (r, c), (r2, c2) = move
        ep_novo = xadrez_novo_en_passant(self.board, r, c, r2, c2)
        self.roque_flags = xadrez_atualizar_roque(self.roque_flags, self.board, r, c, r2, c2)
        xadrez_aplicar_move(self.board, r, c, r2, c2, False, self.en_passant)
        self.en_passant = ep_novo
        self.brancas_jogam = True
        self.win.after(0, self._desenhar)

        # Verificar fim de jogo após jogada do Casaro
        legais_brancas = xadrez_movimentos_legais(self.board, True, self.en_passant, self.roque_flags)
        if not legais_brancas:
            if xadrez_em_xeque(self.board, True, self.en_passant):
                self.win.after(500, lambda: self._fim_jogo('vitoria_casaro'))
            else:
                self.win.after(500, lambda: self._fim_jogo('empate'))
            return

        self.win.after(0, lambda: self.label_turno.config(text="Seu turno (brancas)", fg="#86efac"))

    def _falar_comentario(self, texto):
        global falando, parar_fala
        try:
            falando = True
            parar_fala = False
            fila_eventos.put(("olho", True))
            fila_eventos.put(("status", ("Xadrez…", "#c084fc")))
            falar_edge(texto)
            fila_eventos.put(("olho", False))
        except Exception as e:
            print(f"Erro ao falar comentário xadrez: {e}")
        finally:
            falando = False
            fila_eventos.put(("resetar_status", None))

    def _fim_jogo(self, resultado):
        self.game_over = True
        if resultado == 'vitoria_casaro':
            self.label_turno.config(text="☠ Xeque-mate! Casaro venceu.", fg="#f87171")
            comentario = xadrez_gerar_comentario(groq_client, "", "", 'vitoria_casaro')
        elif resultado == 'vitoria_usuario':
            self.label_turno.config(text="🏆 Você venceu! (Casaro está furioso)", fg="#86efac")
            comentario = xadrez_gerar_comentario(groq_client, "", "", 'vitoria_usuario')
        else:
            self.label_turno.config(text="½ Empate.", fg="#f59e0b")
            comentario = "Empate? Que desperdício do meu tempo."

        self._set_comentario(comentario)
        threading.Thread(target=self._falar_comentario, args=(comentario,), daemon=True).start()

    def _set_comentario(self, texto):
        # Remove [RISADA] do texto exibido na tela
        limpo = texto.replace("[RISADA]", "😂")
        self.win.after(0, lambda: self.label_comentario.config(text=limpo))

    def _reiniciar(self):
        self.board = xadrez_copia(XADREZ_INICIAL)
        self.brancas_jogam = True
        self.en_passant = None
        self.roque_flags = {'K': True, 'Q': True, 'k': True, 'q': True}
        self.selecionado = None
        self.movimentos_validos = []
        self.game_over = False
        self.label_turno.config(text="Seu turno (brancas)", fg="#86efac")
        self.label_comentario.config(text="…de novo? Tá bom, vou deixar você perder mais uma vez.")
        self._desenhar()


def abrir_xadrez(parent_app):
    """Abre (ou foca) a janela de xadrez."""
    XadrezJanela(parent_app)



def handle_num_lock():
    global gravando, falando, parar_fala
    if falando:
        _modo_silencio[0] = True
        matar_audio()
        falando = False
        fila_eventos.put(("status", ("⏸ Num Lock ou 'Casaro' para falar.", "#888")))
        fila_eventos.put(("olho", False))
    elif _modo_silencio[0]:
        _modo_silencio[0] = False
        fila_eventos.put(("ativar_gravacao", None))
    elif not gravando:
        fila_eventos.put(("ativar_gravacao", None))

# ============================================================
# VELOCÍMETRO DE PACIÊNCIA (Canvas)
# ============================================================

# ============================================================
# INTERFACE
# ============================================================

class CasaroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CasaroAIv3.1.1")
        self.root.configure(bg="#0d0d0d")
        self.root.resizable(False, False)
        self.fixado = False
        self.canto_atual = 3
        self._animando = False
        self._drag_x = 0
        self._drag_y = 0

        pasta = os.path.dirname(os.path.abspath(__file__))
        img_fechado   = Image.open(os.path.join(pasta, "assets/images/CasaroOlhoFechado.png")).resize((300, 300))
        img_aberto    = Image.open(os.path.join(pasta, "assets/images/CasaroOlhoAberto.png")).resize((300, 300))
        img_rindo     = Image.open(os.path.join(pasta, "assets/images/casaroRindo.png")).resize((300, 300))
        img_censurado = Image.open(os.path.join(pasta, "assets/images/CasaroSensurado.png")).resize((300, 300))
        self.foto_fechado   = ImageTk.PhotoImage(img_fechado)
        self.foto_aberto    = ImageTk.PhotoImage(img_aberto)
        self.foto_rindo     = ImageTk.PhotoImage(img_rindo)
        self.foto_censurado = ImageTk.PhotoImage(img_censurado)
        self._img_fechado_pil   = img_fechado.copy()
        self._img_aberto_pil    = img_aberto.copy()
        self._img_rindo_pil     = img_rindo.copy()
        self._img_censurado_pil = img_censurado.copy()
        self._olho_aberto = False
        self._rindo = False
        self._censurado = False
        self._foto_vibrada = None

        # ── Avatar ──
        self.label_avatar = tk.Label(root, image=self.foto_fechado, bg="#0d0d0d",
                                     relief=tk.FLAT)
        self.label_avatar.pack(pady=(12, 0))

        # ── Nome com linha decorativa ──
        frame_nome = tk.Frame(root, bg="#0d0d0d")
        frame_nome.pack(fill=tk.X, padx=20, pady=(4, 2))
        tk.Frame(frame_nome, bg="#3b1f6e", height=1).pack(fill=tk.X)
        tk.Label(frame_nome, text="C  A  S  A  R  O", bg="#0d0d0d", fg="#c084fc",
                 font=("Courier", 12, "bold")).pack(pady=2)
        tk.Frame(frame_nome, bg="#3b1f6e", height=1).pack(fill=tk.X)

        # ── Status ──
        self.label_status = tk.Label(root, text="● Aguardando", bg="#0d0d0d",
                                     fg="#444", font=("Courier", 9))
        self.label_status.pack(pady=(6, 0))

        # ── Memória ──
        self.label_memoria = tk.Label(root,
                                      text=f"🧠  {len(dados_memoria['memorias'])} memórias",
                                      bg="#0d0d0d", fg="#2a2a4a", font=("Courier", 8))
        self.label_memoria.pack()

        # ── Linha separadora ──
        self._separador = tk.Frame(root, bg="#1a1a2e", height=1)
        self._separador.pack(fill=tk.X, padx=20, pady=4)

        # ── Controles ──
        frame_ctrl = tk.Frame(root, bg="#0d0d0d")
        frame_ctrl.pack(pady=(2, 4))

        tk.Label(frame_ctrl, text="Num Lock  ·  'Ok Casaro'",
                 bg="#0d0d0d", fg="#222", font=("Courier", 7)).pack()

        # ── Botões de toggle numa linha só ──
        frame_toggles = tk.Frame(root, bg="#0d0d0d")
        frame_toggles.pack(pady=(0, 4))

        self.btn_fixar = tk.Button(frame_toggles, text="📌  Fixar", command=self.toggle_fixar,
                                   bg="#13132a", fg="#555", font=("Courier", 8),
                                   relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
                                   activebackground="#1e1e40", activeforeground="#c084fc",
                                   bd=0)
        self.btn_fixar.pack(side=tk.LEFT, padx=3)

        self.btn_toggle_input = tk.Button(frame_toggles, text="⌨️", command=self.toggle_input,
                                          bg="#13132a", fg="#555", font=("Courier", 8),
                                          relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
                                          activebackground="#1e1e40", activeforeground="#c084fc",
                                          bd=0)
        self.btn_toggle_input.pack(side=tk.LEFT, padx=3)

        # ── Input de texto (oculto por padrão) ──
        self.frame_input = tk.Frame(root, bg="#0d0d0d")
        # não faz pack ainda — começa oculto
        self.entry_texto = tk.Entry(self.frame_input,
                                    bg="#13132a", fg="#c084fc", insertbackground="#c084fc",
                                    font=("Courier", 9), relief=tk.FLAT,
                                    width=28, bd=4)
        self.entry_texto.pack(side=tk.LEFT, padx=(8, 4), pady=6, ipady=4)
        self.entry_texto.bind("<Return>", self.enviar_texto)

        btn_enviar = tk.Button(self.frame_input, text="↵", command=self.enviar_texto,
                               bg="#3b1f6e", fg="#c084fc", font=("Courier", 10, "bold"),
                               relief=tk.FLAT, padx=8, pady=4, cursor="hand2",
                               activebackground="#7c3aed", activeforeground="#fff",
                               bd=0)
        btn_enviar.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_arquivo = tk.Button(self.frame_input, text="📎", command=self.abrir_arquivo,
                                     bg="#13132a", fg="#888", font=("Courier", 10),
                                     relief=tk.FLAT, padx=6, pady=4, cursor="hand2",
                                     activebackground="#1e1e40", activeforeground="#c084fc",
                                     bd=0)
        self.btn_arquivo.pack(side=tk.LEFT, padx=(0, 8))

        # Label do arquivo carregado (aparece quando tem arquivo pendente)
        self.label_arquivo = tk.Label(root, text="", bg="#0d0d0d", fg="#86efac",
                                      font=("Courier", 7), wraplength=280)
        # não faz pack ainda

        self._input_visivel = False

        # Binds
        self.root.bind("<Button-1>", self._drag_start)
        self.root.bind("<B1-Motion>", self._drag_move)
        self.root.bind("<Enter>", self._checar_enter)

        self.root.after(200, self.posicionar_canto)

        keyboard.on_press_key("num lock", lambda _: threading.Thread(
            target=handle_num_lock, daemon=True).start(), suppress=True)

        threading.Thread(target=escutar_wake_word, daemon=True).start()
        self.root.after(100, self.processar_fila)

    def toggle_input(self):
        self._input_visivel = not self._input_visivel
        if self._input_visivel:
            self.frame_input.pack(pady=(0, 8))
            self.entry_texto.focus_set()
            self.btn_toggle_input.config(fg="#c084fc", bg="#1e1040")
        else:
            self.frame_input.pack_forget()
            self.btn_toggle_input.config(fg="#555", bg="#13132a")

    def abrir_arquivo(self):
        """Abre diálogo para escolher PDF ou imagem e carrega como arquivo pendente."""
        from tkinter import filedialog
        tipos = [
            ("PDF e Imagens", "*.pdf *.png *.jpg *.jpeg *.gif *.webp *.bmp"),
            ("PDF",           "*.pdf"),
            ("Imagens",       "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
        ]
        caminho = filedialog.askopenfilename(title="Escolher arquivo para o Casaro analisar",
                                             filetypes=tipos)
        if not caminho:
            return
        ext = os.path.splitext(caminho)[1].lower()
        if ext not in EXTENSOES_IMAGEM | EXTENSOES_PDF:
            return

        try:
            b64, mime_type, eh_pdf = _arquivo_para_b64(caminho)
            nome = os.path.basename(caminho)
            _arquivo_pendente[0] = (b64, mime_type, eh_pdf, nome)
            # Mostra label com o nome do arquivo
            icone = "📄" if eh_pdf else "🖼️"
            self.label_arquivo.config(text=f"{icone} {nome[:40]} — pronto! Agora me diga o que fazer.")
            self.label_arquivo.pack(pady=(0, 4))
            self.btn_arquivo.config(fg="#86efac", bg="#0a2a0a")
            self.entry_texto.focus_set()
            print(f"[arquivo] Carregado: {nome} ({mime_type})")
        except Exception as e:
            print(f"[arquivo] Erro ao carregar: {e}")

    def limpar_arquivo_ui(self):
        """Remove o label do arquivo e reseta o botão 📎."""
        self.label_arquivo.config(text="")
        try:
            self.label_arquivo.pack_forget()
        except Exception:
            pass
        self.btn_arquivo.config(fg="#888", bg="#13132a")

    def toggle_fixar(self):
        self.fixado = not self.fixado
        if self.fixado:
            self.btn_fixar.config(text="📌  Fixado", fg="#c084fc", bg="#1e1040")
            self.root.attributes("-topmost", True)
        else:
            self.btn_fixar.config(text="📌  Fixar", fg="#555", bg="#13132a")
            self.root.attributes("-topmost", False)

    def _drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        if not self.fixado:
            x = self.root.winfo_x() + event.x - self._drag_x
            y = self.root.winfo_y() + event.y - self._drag_y
            self.root.geometry(f"+{x}+{y}")

    def posicionar_canto(self, canto=None):
        self.root.update_idletasks()
        larg = self.root.winfo_width()
        alt  = self.root.winfo_height()
        sw   = self.root.winfo_screenwidth()
        sh   = self.root.winfo_screenheight()
        margem = 10
        if canto is None:
            canto = self.canto_atual
        cantos = {
            0: (margem, margem),
            1: (sw - larg - margem, margem),
            2: (margem, sh - alt - margem),
            3: (sw - larg - margem, sh - alt - margem),
        }
        x, y = cantos[canto]
        self.root.geometry(f"+{x}+{y}")
        self.canto_atual = canto

    def _checar_enter(self, event):
        if self.fixado and event.widget == self.root and not self._animando:
            proximo = (self.canto_atual + 1) % 4
            self.canto_atual = proximo
            threading.Thread(target=self._animar_para_canto, args=(proximo,), daemon=True).start()

    def _animar_para_canto(self, canto):
        self._animando = True
        self.root.update_idletasks()
        larg = self.root.winfo_width()
        alt  = self.root.winfo_height()
        sw   = self.root.winfo_screenwidth()
        sh   = self.root.winfo_screenheight()
        margem = 10
        cantos = {
            0: (margem, margem),
            1: (sw - larg - margem, margem),
            2: (margem, sh - alt - margem),
            3: (sw - larg - margem, sh - alt - margem),
        }
        x_dest, y_dest = cantos[canto]
        x_atual = self.root.winfo_x()
        y_atual = self.root.winfo_y()
        for i in range(1, 21):
            t = i / 20
            t_ease = t * t * (3 - 2 * t)
            x = int(x_atual + (x_dest - x_atual) * t_ease)
            y = int(y_atual + (y_dest - y_atual) * t_ease)
            self.root.geometry(f"+{x}+{y}")
            time.sleep(0.015)
        self._animando = False

    def set_status(self, texto, cor="#444"):
        self.label_status.config(text=f"● {texto}", fg=cor)

    def set_olho(self, aberto):
        self._olho_aberto = aberto
        # Censurado e rindo têm prioridade visual
        if not self._rindo and not self._censurado:
            self.label_avatar.config(image=self.foto_aberto if aberto else self.foto_fechado)

    def set_rindo(self, rindo):
        self._rindo = rindo
        if self._censurado:
            return  # censurado tem prioridade
        if rindo:
            self.label_avatar.config(image=self.foto_rindo)
        else:
            self.label_avatar.config(image=self.foto_aberto if self._olho_aberto else self.foto_fechado)

    def set_censurado(self, censurado):
        self._censurado = censurado
        if censurado:
            self.label_avatar.config(image=self.foto_censurado)
        else:
            # Volta para o estado correto após censura
            if self._rindo:
                self.label_avatar.config(image=self.foto_rindo)
            elif self._olho_aberto:
                self.label_avatar.config(image=self.foto_aberto)
            else:
                self.label_avatar.config(image=self.foto_fechado)

    def _vibrar_avatar(self):
        dx = random.randint(-6, 6)
        dy = random.randint(-5, 5)
        if self._censurado:
            img_base = self._img_censurado_pil
        elif self._rindo:
            img_base = self._img_rindo_pil
        elif self._olho_aberto:
            img_base = self._img_aberto_pil
        else:
            img_base = self._img_fechado_pil
        img_vibrada = ImageChops.offset(img_base, dx, dy)
        self._foto_vibrada = ImageTk.PhotoImage(img_vibrada)
        self.label_avatar.config(image=self._foto_vibrada)

    def _parar_vibra(self):
        if self._censurado:
            self.label_avatar.config(image=self.foto_censurado)
        elif self._rindo:
            self.label_avatar.config(image=self.foto_rindo)
        elif self._olho_aberto:
            self.label_avatar.config(image=self.foto_aberto)
        else:
            self.label_avatar.config(image=self.foto_fechado)

    def atualizar_contador_memoria(self):
        self.label_memoria.config(text=f"🧠  {len(dados_memoria['memorias'])} memórias")

    def iniciar_gravacao(self):
        global gravando, parar_fala, falando
        if gravando:
            return
        gravando = True
        parar_fala = False
        self.set_status("Ouvindo...", "#86efac")
        # Captura a tela no momento em que começa a ouvir
        capturar_e_armazenar_tela()
        threading.Thread(target=self._thread_gravacao, daemon=True).start()

    def enviar_texto(self, event=None):
        """Pega o texto do input, processa e faz o Casaro responder."""
        global gravando, falando, parar_fala
        texto = self.entry_texto.get().strip()
        if gravando or falando:
            return
        self.entry_texto.delete(0, tk.END)

        # Verifica se tem arquivo pendente
        if _arquivo_pendente[0] is not None:
            b64, mime_type, eh_pdf, nome = _arquivo_pendente[0]
            pergunta = texto if texto else ("Descreva este arquivo" if not eh_pdf else "Resuma este PDF")
            threading.Thread(
                target=_thread_analisar_arquivo,
                args=(b64, mime_type, eh_pdf, nome, pergunta),
                daemon=True
            ).start()
            return

        if not texto:
            return
        # Captura a tela no momento em que o usuário manda mensagem
        capturar_e_armazenar_tela()
        threading.Thread(target=self._thread_texto, args=(texto,), daemon=True).start()

    def _thread_texto(self, texto):
        global falando, parar_fala
        try:
            fila_eventos.put(("status", ("Processando...", "#fbbf24")))
            resposta = gerar_resposta(texto)
            fila_eventos.put(("atualizar_memoria", None))
            fila_eventos.put(("olho", True))
            fila_eventos.put(("status", ("Falando...", "#c084fc")))
            falando = True
            parar_fala = False
            falar_edge(resposta)
            fila_eventos.put(("olho", False))
        except Exception as e:
            fila_eventos.put(("status", (f"Erro: {str(e)[:35]}", "#f87171")))
        finally:
            falando = False
            fila_eventos.put(("resetar_status", None))

    def _thread_gravacao(self):
        global gravando, falando, parar_fala
        try:
            caminho = gravar_com_silencio()
            fila_eventos.put(("status", ("Processando...", "#fbbf24")))
            if caminho:
                texto = transcrever(caminho)
                if texto:
                    try:
                        resposta = gerar_resposta(texto)
                        fila_eventos.put(("atualizar_memoria", None))
                        fila_eventos.put(("olho", True))
                        fila_eventos.put(("status", ("Falando...", "#c084fc")))
                        falando = True
                        parar_fala = False
                        falar_edge(resposta)
                        fila_eventos.put(("olho", False))
                    except Exception as e:
                        fila_eventos.put(("status", (f"Erro: {str(e)[:35]}", "#f87171")))
                else:
                    fila_eventos.put(("status", ("Não entendi.", "#f87171")))
            else:
                fila_eventos.put(("status", ("Sem áudio.", "#f87171")))
        except Exception as e:
            fila_eventos.put(("status", (f"Erro: {str(e)[:35]}", "#f87171")))
        finally:
            gravando = False
            falando = False
            fila_eventos.put(("resetar_status", None))

    def processar_fila(self):
        try:
            while True:
                evento, dados = fila_eventos.get_nowait()
                if evento == "status":
                    self.set_status(*dados)
                elif evento == "olho":
                    self.set_olho(dados)
                elif evento == "atualizar_memoria":
                    self.atualizar_contador_memoria()
                elif evento == "ativar_gravacao":
                    self.iniciar_gravacao()
                elif evento == "vibrar":
                    self._vibrar_avatar()
                elif evento == "parar_vibra":
                    self._parar_vibra()
                elif evento == "rindo":
                    self.set_rindo(dados)
                elif evento == "censurado":
                    self.set_censurado(dados)
                elif evento == "abrir_xadrez":
                    abrir_xadrez(self)
                elif evento == "abrir_rpg":
                    abrir_rpg(self, groq_client)
                elif evento == "abrir_player":
                    try:
                        abrir_janela_player(dados)
                    except Exception as e:
                        print(f"[música] Erro ao abrir player: {e}")
                elif evento == "minimizar":
                    # Minimiza temporariamente para screenshot sem o Casaro na frente
                    self.root.iconify()
                elif evento == "restaurar":
                    # Restaura a janela após o clique
                    self.root.deiconify()
                    self.root.lift()
                elif evento == "abrir_loading_imagem":
                    # dados é a função que abre o loading
                    try:
                        dados()
                    except Exception as e:
                        print(f"[imagem] Erro ao abrir loading: {e}")
                elif evento == "fechar_loading_imagem":
                    # dados é a função que fecha o loading
                    try:
                        dados()
                    except Exception as e:
                        print(f"[imagem] Erro ao fechar loading: {e}")
                elif evento == "abrir_imagem":
                    caminho_img, prompt_usado = dados
                    try:
                        abrir_janela_imagem(caminho_img, prompt_usado)
                    except Exception as e:
                        print(f"[imagem] Erro ao abrir janela: {e}")
                elif evento == "limpar_arquivo":
                    self.limpar_arquivo_ui()
                elif evento == "resetar_status":
                    if not _modo_silencio[0]:
                        self.set_status("Aguardando", "#444")
                    self.set_olho(False)
        except queue.Empty:
            pass
        self.root.after(50, self.processar_fila)

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = CasaroApp(root)
    root.mainloop()