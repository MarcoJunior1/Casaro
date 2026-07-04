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


# ============================================================
# MÓDULO RPG — CASARO RPG (integrado)
# ============================================================
# ============================================================
# CASARO RPG — O MUNDO DO CASARO
# Fantasy Medieval 2D com pixel art, exploração, combate e quests
# O Casaro é o criador do mundo (estilo Caim de Digital Circus)
# ============================================================

import tkinter as tk
from tkinter import font as tkfont
import math, random, time, threading, json, os

# ── Paleta de cores pixel art ────────────────────────────────
RPG_CORES = {
    "bg":           "#0a0a12",
    "painel":       "#13132a",
    "borda":        "#3b1f6e",
    "roxo_brilho":  "#c084fc",
    "roxo_escuro":  "#7c3aed",
    "ouro":         "#fbbf24",
    "verde":        "#86efac",
    "verde_escuro": "#14532d",
    "vermelho":     "#ef4444",
    "azul":         "#60a5fa",
    "cinza":        "#374151",
    "branco":       "#f3f4f6",
    "terra":        "#92400e",
    "pedra":        "#4b5563",
    "agua":         "#1e3a5f",
    "grama":        "#166534",
    "caminho":      "#78350f",
    "masmorra":     "#1c1917",
    "fogo":         "#f97316",
    "neve":         "#e0e7ff",
    "areia":        "#d97706",
}

# ── Tamanho do tile ─────────────────────────────────────────
TILE  = 40
COLS  = 25   # largura do mapa em tiles
ROWS  = 20   # altura do mapa em tiles
VIEW_COLS = 18  # tiles visíveis horizontalmente
VIEW_ROWS = 16  # tiles visíveis verticalmente
MAP_W = VIEW_COLS * TILE
MAP_H = VIEW_ROWS * TILE

# ── Tipos de tile ────────────────────────────────────────────
T_GRAMA    = 0
T_CAMINHO  = 1
T_AGUA     = 2
T_PEDRA    = 3
T_MURO     = 4
T_ARVORE   = 5
T_PORTA    = 6
T_ALTAR    = 7
T_TESOURO  = 8
T_ESPINHO  = 9
T_FOGUEIRA = 10
T_ERVA     = 11
T_RUNA     = 12
T_BOSS     = 13

# ── Mapa do mundo (25x20) ────────────────────────────────────
# Legenda: G=grama, P=caminho, W=água, R=pedra, M=muro, A=árvore
#          D=porta (dungeon), L=altar, T=tesouro, S=espinho
#          F=fogueira, E=erva, U=runa, B=boss

_MAPA_ASCII = [
    "AAAAAAAAAAAAAAAAAAAAAAAGGA",  # row 0
    "AGGGGGGGGGGGGGGGGGGAAAAGGA",  # row 1
    "AGGGGGGGGGWWWGGGGGGGAAAGGA",  # row 2
    "AGGGGGPPPWWWWWPPPGGGGAAGGA",  # row 3
    "AGGGGGPGGWWWWWGPGGGGGAAGGA",  # row 4
    "AGGGGGPGGGGGGGGPGGGGGAAGGA",  # row 5
    "AGGGGGPPPPPPPPPPPGGGGAAGGA",  # row 6
    "AGGGGGGGGGGGGGGGGGGGGAAGGA",  # row 7
    "AGGGGGGEEEGGGGGGGGGGAAAGGA",  # row 8
    "AGGGGGGEEEGPPPPPPPGGAAAGGA",  # row 9
    "AGGRRRRRRRGPGGGGGPGGAAAGGA",  # row 10
    "AGGRDDRRRGGGGGGGGGGGAAAGGA",  # row 11 — porta da masmorra
    "AGGRRRRRRGGGGGSGGGGGAAAGGA",  # row 12
    "AGGGGGGGGGPPPPPPPGGAAAAGGA",  # row 13
    "AGGGGFFGGGPGLGGGPGGGAAAGGA",  # row 14 — fogueira e altar
    "AGGGGGGGGGPGGGGUPGGGAAAGGA",  # row 15 — runa
    "AGGGGGGGGGPGGGGUPGGGAAAGGA",  # row 16
    "AGGGGGGGGGGPPPPPPGGGAAAGGA",  # row 17
    "AGGGGGGGGGGGGGGGGGGAAAAGGA",  # row 18
    "AAAAAAAAABAAAAAAAAAAAAAAAA",  # row 19 — boss
]

_CHAR_TO_TILE = {
    'G': T_GRAMA, 'P': T_CAMINHO, 'W': T_AGUA, 'R': T_PEDRA,
    'M': T_MURO,  'A': T_ARVORE,  'D': T_PORTA,'L': T_ALTAR,
    'T': T_TESOURO,'S': T_ESPINHO,'F': T_FOGUEIRA,'E': T_ERVA,
    'U': T_RUNA,  'B': T_BOSS,
}

# Tiles bloqueantes (não se pode andar em cima)
BLOQUEANTES = {T_AGUA, T_PEDRA, T_MURO, T_ARVORE, T_ESPINHO}

def _construir_mapa():
    m = []
    for row in _MAPA_ASCII:
        linha = [_CHAR_TO_TILE.get(c, T_GRAMA) for c in row]
        m.append(linha)
    return m

# ── Cores por tile ───────────────────────────────────────────
TILE_COR = {
    T_GRAMA:    ("#166534", "#15803d", "░"),
    T_CAMINHO:  ("#78350f", "#92400e", "·"),
    T_AGUA:     ("#1e3a5f", "#1d4ed8", "≈"),
    T_PEDRA:    ("#374151", "#4b5563", "▓"),
    T_MURO:     ("#1f2937", "#374151", "█"),
    T_ARVORE:   ("#14532d", "#166534", "♣"),
    T_PORTA:    ("#3b1f6e", "#7c3aed", "▬"),
    T_ALTAR:    ("#78350f", "#b45309", "✦"),
    T_TESOURO:  ("#78350f", "#d97706", "◈"),
    T_ESPINHO:  ("#166534", "#ef4444", "✕"),
    T_FOGUEIRA: ("#166534", "#f97316", "♨"),
    T_ERVA:     ("#166534", "#4ade80", "♠"),
    T_RUNA:     ("#1e1b4b", "#c084fc", "⊗"),
    T_BOSS:     ("#7f1d1d", "#ef4444", "☠"),
}

# ── Classes de personagem ────────────────────────────────────
CLASSES = {
    "Guerreiro": {
        "emoji": "⚔️", "cor": "#ef4444",
        "hp": 120, "mp": 30, "atk": 18, "def_": 12, "spd": 5,
        "skills": ["Golpe Brutal", "Escudo Divino", "Frenesi"],
        "desc": "Força bruta e resistência. Tanque do grupo."
    },
    "Mago": {
        "emoji": "🔮", "cor": "#c084fc",
        "hp": 70, "mp": 120, "atk": 25, "def_": 5, "spd": 6,
        "skills": ["Bola de Fogo", "Gelo Eterno", "Relâmpago Arcano"],
        "desc": "Domina a magia. Alto dano, baixa defesa."
    },
    "Arqueiro": {
        "emoji": "🏹", "cor": "#86efac",
        "hp": 90, "mp": 60, "atk": 20, "def_": 8, "spd": 9,
        "skills": ["Flecha Certeira", "Chuva de Flechas", "Invisível"],
        "desc": "Agilidade e precisão. Ataca de longe."
    },
    "Ladino": {
        "emoji": "🗡️", "cor": "#fbbf24",
        "hp": 80, "mp": 50, "atk": 22, "def_": 7, "spd": 10,
        "skills": ["Ataque Furtivo", "Veneno", "Roubar"],
        "desc": "Sorrateiro e veloz. Critico alto."
    },
}

# ── Inimigos ─────────────────────────────────────────────────
INIMIGOS_BASE = [
    {"nome": "Goblin Sarnento",    "emoji": "👺", "hp": 30,  "atk": 8,  "def_": 3,  "xp": 15, "ouro": 8,  "cor": "#86efac"},
    {"nome": "Esqueleto Guerreiro","emoji": "💀", "hp": 45,  "atk": 12, "def_": 6,  "xp": 25, "ouro": 12, "cor": "#9ca3af"},
    {"nome": "Bruxa da Floresta",  "emoji": "🧙", "hp": 35,  "atk": 18, "def_": 2,  "xp": 30, "ouro": 18, "cor": "#c084fc"},
    {"nome": "Lobo Sombrio",       "emoji": "🐺", "hp": 40,  "atk": 14, "def_": 4,  "xp": 20, "ouro": 10, "cor": "#6b7280"},
    {"nome": "Treant Corrompido",  "emoji": "🌲", "hp": 70,  "atk": 10, "def_": 12, "xp": 40, "ouro": 20, "cor": "#166534"},
    {"nome": "Mago das Trevas",    "emoji": "🧟", "hp": 55,  "atk": 22, "def_": 5,  "xp": 50, "ouro": 30, "cor": "#7c3aed"},
]
BOSS_INIMIGO = {
    "nome": "Dracomante das Ruínas","emoji": "🐉", "hp": 200, "atk": 30, "def_": 15,
    "xp": 300, "ouro": 150, "cor": "#ef4444", "boss": True,
}

# ── Quests fixas (história principal) ────────────────────────
QUESTS_PRINCIPAIS = [
    {
        "id": "q1",
        "titulo": "Despertar no Cubo",
        "desc": "Casaro te convocou para este mundo estranho. Explore o mapa e encontre o Altar Mágico.",
        "objetivo": "altar",
        "recompensa_xp": 50, "recompensa_ouro": 30,
        "casaro_fala": "Ah, finalmente acorda! Bem-vindo ao meu mundo. Tente não morrer rápido demais, fica chato.",
    },
    {
        "id": "q2",
        "titulo": "A Runa Proibida",
        "desc": "Uma energia estranha emana das Runas. Investigue as 2 runas no mapa.",
        "objetivo": "runas",
        "count_alvo": 2, "count_atual": 0,
        "recompensa_xp": 80, "recompensa_ouro": 50,
        "casaro_fala": "Essas runas... eu coloquei ali por algum motivo que não vou te contar ainda. Vai lá.",
    },
    {
        "id": "q3",
        "titulo": "Limpar o Caminho",
        "desc": "Derrote 5 inimigos que bloqueiam a estrada.",
        "objetivo": "matar",
        "count_alvo": 5, "count_atual": 0,
        "recompensa_xp": 100, "recompensa_ouro": 60,
        "casaro_fala": "Matar coisas. Simples assim. Até você consegue.",
    },
    {
        "id": "q4",
        "titulo": "O Dragão Final",
        "desc": "Enfrente o Dracomante das Ruínas no sul do mapa. O clímax do meu mundinho.",
        "objetivo": "boss",
        "recompensa_xp": 500, "recompensa_ouro": 200,
        "casaro_fala": "Eu criei esse dragão numa tarde chateado. Boa sorte. [RISADA]",
    },
]

# ── Diálogos do Casaro no mundo ──────────────────────────────
CASARO_WORLD_DIALOGOS = {
    "inicio": [
        "Bem-vindo ao meu mundo. Sim, fui EU que criei tudo isso.",
        "Não quebre os móveis. Levei semanas fazendo esse mapa.",
        "Explore à vontade. Só não me culpe se morrer.",
    ],
    "altar": [
        "Ah, achou o altar. Criei esse com carinho. Quase.",
        "Esse altar canaliza magia do cubo. Não pergunte como.",
    ],
    "runa": [
        "Essa runa... guarda um segredo que [CENSURA]",
        "Bonita né? Pintei na mão. Quer dizer, na pata de cubo.",
    ],
    "porta_masmorra": [
        "Atrás dessa porta tem horrores que eu mesmo me assustei ao criar.",
        "Sério que vai entrar? Tá bom, mas não diz que não avisei.",
    ],
    "boss_area": [
        "O Dracomante... criei ele numa quinta-feira às 3 da manhã. Está claramente com raiva.",
        "Você tem certeza? Porque eu NÃO tenho.",
    ],
    "morte": [
        "Morre rapidinho, hein? Esperava mais de você.",
        "Quer dizer que vou ter que te ressuscitar de novo? Que saco.",
        "Tá bem, tá bem. Levanta aí. Mas dessa vez tenta não ser idiota.",
    ],
    "vitoria_boss": [
        "Parabéns. Genuinamente. Não achei que ia conseguir.",
        "Matou o meu dragão favorito. Estou emocionado. Não.",
        "Tá bom, ganhou o jogo. Agora vai fazer algo útil com sua vida.",
    ],
    "nivel": [
        "Subiu de nível! Fica feliz, mas não muito.",
        "Level up. Como se isso fosse impressionante.",
        "Crescendo! Tipo, literalmente, sua ficha ficou mais forte.",
    ],
    "tesouro": [
        "Ouro! Que surpresa. Coloquei aí sabendo que você ia achar.",
        "Pegue o tesouro. Não vou dizer que esse era armadilha. Ou vou?",
    ],
}

# ── Itens ────────────────────────────────────────────────────
ITENS = {
    "Poção de Vida":    {"tipo": "consumivel", "efeito": "hp",  "valor": 40,  "emoji": "🧪", "preco": 20},
    "Poção de Mana":    {"tipo": "consumivel", "efeito": "mp",  "valor": 40,  "emoji": "💧", "preco": 20},
    "Espada Sombria":   {"tipo": "arma",       "efeito": "atk", "valor": 8,   "emoji": "🗡️", "preco": 80},
    "Cajado Arcano":    {"tipo": "arma",       "efeito": "atk", "valor": 10,  "emoji": "🪄", "preco": 90},
    "Escudo Rúnico":    {"tipo": "armadura",   "efeito": "def_","valor": 7,   "emoji": "🛡️", "preco": 70},
    "Botas Velozes":    {"tipo": "armadura",   "efeito": "spd", "valor": 3,   "emoji": "👟", "preco": 60},
    "Amuleto do Cubo":  {"tipo": "especial",   "efeito": "all", "valor": 5,   "emoji": "🎲", "preco": 150},
}

# ============================================================
# ESTADO DO JOGO
# ============================================================

def _novo_estado_jogo(nome, classe):
    c = CLASSES[classe]
    return {
        "nome": nome,
        "classe": classe,
        "emoji_classe": c["emoji"],
        "nivel": 1,
        "xp": 0,
        "xp_proximo": 100,
        "hp": c["hp"],
        "hp_max": c["hp"],
        "mp": c["mp"],
        "mp_max": c["mp"],
        "atk": c["atk"],
        "def_": c["def_"],
        "spd": c["spd"],
        "ouro": 50,
        "inventario": {"Poção de Vida": 2, "Poção de Mana": 1},
        "equipamentos": {},
        "habilidades": c["skills"],
        "pos_x": 12,  # posição inicial no mapa
        "pos_y": 7,
        "quests_ativas": [QUESTS_PRINCIPAIS[0].copy()],
        "quests_concluidas": [],
        "npcs_falados": [],
        "tiles_visitados": set(),
        "inimigos_mortos": 0,
        "runas_ativadas": 0,
        "altar_visitado": False,
        "boss_derrotado": False,
        "casaro_comentou": set(),
    }

def _xp_para_nivel(nivel):
    return 100 * (nivel ** 2)

def _ganhar_xp(estado, xp):
    estado["xp"] += xp
    subiu = False
    while estado["xp"] >= estado["xp_proximo"]:
        estado["xp"] -= estado["xp_proximo"]
        estado["nivel"] += 1
        estado["xp_proximo"] = _xp_para_nivel(estado["nivel"])
        # Sobe stats
        c = CLASSES[estado["classe"]]
        estado["hp_max"]  += 10
        estado["mp_max"]  += 5
        estado["atk"]     += 2
        estado["def_"]    += 1
        estado["hp"] = estado["hp_max"]  # cura ao subir nível
        estado["mp"] = estado["mp_max"]
        subiu = True
    return subiu

# ============================================================
# CLASSE PRINCIPAL DO JOGO
# ============================================================

class CasaroRPGJanela:
    def __init__(self, parent_app, groq_client_ref):
        self.app       = parent_app
        self.groq      = groq_client_ref
        self.mapa      = _construir_mapa()
        self.estado    = None
        self.fase      = "menu"   # menu | customizacao | jogo | combate | dialogo | gameover | vitoria
        self._efeitos  = []       # lista de animações ativas
        self._combate  = {}       # estado do combate atual
        self._dialogo  = {}       # estado do diálogo atual
        self._side_quests_geradas = []
        self._npcs     = self._gerar_npcs()
        self._inimigos_mapa = self._gerar_inimigos_mapa()
        self._particulas = []
        self._tick     = 0

        self.win = tk.Toplevel()
        self.win.title("🎮 Casaro RPG — O Mundo do Cubo")
        self.win.configure(bg=RPG_CORES["bg"])
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self._fechar)

        # Centraliza
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        w, h = 1010, 760
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self._construir_ui()
        self.win.update_idletasks()   # garante que o canvas está pronto antes de desenhar
        self.win.update()
        self._mostrar_intro()
        self._loop_animacao()

        # Garante foco e captura de teclado para a janela do RPG
        self.win.after(200, self._garantir_foco)

    # ── NPCs e inimigos no mapa ──────────────────────────────

    def _gerar_npcs(self):
        return [
            {"x": 12, "y": 6,  "nome": "Ferreiro Drak",  "emoji": "🔨", "fala": ["Vendo armas e armaduras.", "O Casaro me contratou. Paga mal, mas o trabalho é interessante."], "loja": ["Espada Sombria", "Escudo Rúnico", "Cajado Arcano", "Botas Velozes"]},
            {"x": 8,  "y": 5,  "nome": "Curandeira Lyra", "emoji": "🌿", "fala": ["Poções para venda.", "Cuidado com os espinhos ao sul."], "loja": ["Poção de Vida", "Poção de Mana"]},
            {"x": 16, "y": 9,  "nome": "Viajante Misterioso", "emoji": "🧭", "fala": ["Dizem que o boss ao sul foi criado em uma noite.", "Runas guardam poder antigo..."], "loja": ["Amuleto do Cubo"]},
        ]

    def _gerar_inimigos_mapa(self):
        inimigos = []
        posicoes_possiveis = [
            (6, 8), (9, 10), (14, 8), (17, 5), (5, 14), (18, 12),
            (7, 15), (15, 13), (10, 3), (19, 7), (4, 10), (20, 15),
        ]
        for i, (x, y) in enumerate(posicoes_possiveis):
            base = INIMIGOS_BASE[i % len(INIMIGOS_BASE)].copy()
            base["x"]  = x
            base["y"]  = y
            base["hp_atual"] = base["hp"]
            base["vivo"] = True
            inimigos.append(base)
        return inimigos

    # ── UI ───────────────────────────────────────────────────

    def _construir_ui(self):
        # Frame principal esquerda (jogo) + direita (painel)
        self.frame_main = tk.Frame(self.win, bg=RPG_CORES["bg"])
        self.frame_main.pack(fill="both", expand=True)

        # Canvas do mapa
        self.canvas = tk.Canvas(
            self.frame_main,
            width=MAP_W, height=MAP_H,
            bg=RPG_CORES["bg"], highlightthickness=2,
            highlightbackground=RPG_CORES["borda"]
        )
        self.canvas.pack(side="left", padx=8, pady=8)

        # Painel lateral direito
        self.painel = tk.Frame(self.frame_main, bg=RPG_CORES["painel"], width=240)
        self.painel.pack(side="left", fill="y", padx=(0, 8), pady=8)
        self.painel.pack_propagate(False)

        # Título do painel
        tk.Label(self.painel, text="⬡ C A S A R O", bg=RPG_CORES["painel"],
                 fg=RPG_CORES["roxo_brilho"], font=("Courier", 11, "bold")).pack(pady=(10,2))
        tk.Label(self.painel, text="R  P  G", bg=RPG_CORES["painel"],
                 fg=RPG_CORES["borda"], font=("Courier", 9)).pack()
        tk.Frame(self.painel, bg=RPG_CORES["borda"], height=1).pack(fill="x", padx=8, pady=6)

        # Status do personagem
        self.lbl_nome_classe = tk.Label(self.painel, text="", bg=RPG_CORES["painel"],
                                        fg=RPG_CORES["ouro"], font=("Courier", 10, "bold"))
        self.lbl_nome_classe.pack()
        self.lbl_nivel = tk.Label(self.painel, text="", bg=RPG_CORES["painel"],
                                  fg=RPG_CORES["branco"], font=("Courier", 8))
        self.lbl_nivel.pack()

        # Barras HP/MP
        self.frame_barras = tk.Frame(self.painel, bg=RPG_CORES["painel"])
        self.frame_barras.pack(fill="x", padx=10, pady=4)

        tk.Label(self.frame_barras, text="HP", bg=RPG_CORES["painel"],
                 fg=RPG_CORES["vermelho"], font=("Courier", 8, "bold"), width=4, anchor="w").grid(row=0, column=0)
        self.canvas_hp = tk.Canvas(self.frame_barras, width=140, height=12,
                                   bg="#1f1f35", highlightthickness=1,
                                   highlightbackground=RPG_CORES["borda"])
        self.canvas_hp.grid(row=0, column=1, padx=2)
        self.lbl_hp_val = tk.Label(self.frame_barras, text="", bg=RPG_CORES["painel"],
                                   fg=RPG_CORES["branco"], font=("Courier", 7), width=9)
        self.lbl_hp_val.grid(row=0, column=2)

        tk.Label(self.frame_barras, text="MP", bg=RPG_CORES["painel"],
                 fg=RPG_CORES["azul"], font=("Courier", 8, "bold"), width=4, anchor="w").grid(row=1, column=0, pady=(3,0))
        self.canvas_mp = tk.Canvas(self.frame_barras, width=140, height=12,
                                   bg="#1f1f35", highlightthickness=1,
                                   highlightbackground=RPG_CORES["borda"])
        self.canvas_mp.grid(row=1, column=1, padx=2, pady=(3,0))
        self.lbl_mp_val = tk.Label(self.frame_barras, text="", bg=RPG_CORES["painel"],
                                   fg=RPG_CORES["branco"], font=("Courier", 7), width=9)
        self.lbl_mp_val.grid(row=1, column=2, pady=(3,0))

        tk.Label(self.frame_barras, text="XP", bg=RPG_CORES["painel"],
                 fg=RPG_CORES["ouro"], font=("Courier", 8, "bold"), width=4, anchor="w").grid(row=2, column=0, pady=(3,0))
        self.canvas_xp = tk.Canvas(self.frame_barras, width=140, height=8,
                                   bg="#1f1f35", highlightthickness=1,
                                   highlightbackground=RPG_CORES["borda"])
        self.canvas_xp.grid(row=2, column=1, padx=2, pady=(3,0))

        tk.Frame(self.painel, bg=RPG_CORES["borda"], height=1).pack(fill="x", padx=8, pady=6)

        # Stats resumidos
        self.lbl_stats = tk.Label(self.painel, text="", bg=RPG_CORES["painel"],
                                  fg=RPG_CORES["branco"], font=("Courier", 8), justify="left")
        self.lbl_stats.pack(padx=10, anchor="w")

        tk.Frame(self.painel, bg=RPG_CORES["borda"], height=1).pack(fill="x", padx=8, pady=4)

        # Quest ativa
        tk.Label(self.painel, text="📜 QUEST", bg=RPG_CORES["painel"],
                 fg=RPG_CORES["roxo_brilho"], font=("Courier", 9, "bold")).pack(anchor="w", padx=10)
        self.lbl_quest = tk.Label(self.painel, text="", bg=RPG_CORES["painel"],
                                  fg=RPG_CORES["ouro"], font=("Courier", 8), wraplength=210,
                                  justify="left")
        self.lbl_quest.pack(padx=10, anchor="w")

        tk.Frame(self.painel, bg=RPG_CORES["borda"], height=1).pack(fill="x", padx=8, pady=4)

        # Log de mensagens
        tk.Label(self.painel, text="💬 LOG", bg=RPG_CORES["painel"],
                 fg=RPG_CORES["roxo_brilho"], font=("Courier", 9, "bold")).pack(anchor="w", padx=10)
        self.frame_log = tk.Frame(self.painel, bg=RPG_CORES["painel"])
        self.frame_log.pack(fill="x", padx=10)
        self._log_labels = []
        for _ in range(5):
            lbl = tk.Label(self.frame_log, text="", bg=RPG_CORES["painel"],
                           fg=RPG_CORES["cinza"], font=("Courier", 7), wraplength=210,
                           justify="left", anchor="w")
            lbl.pack(fill="x")
            self._log_labels.append(lbl)
        self._log_msgs = []

        tk.Frame(self.painel, bg=RPG_CORES["borda"], height=1).pack(fill="x", padx=8, pady=4)

        # Botões de controle
        frame_btns = tk.Frame(self.painel, bg=RPG_CORES["painel"])
        frame_btns.pack(pady=4)

        btn_style = {
            "bg": "#1e1040", "fg": RPG_CORES["roxo_brilho"],
            "font": ("Courier", 8), "relief": "flat",
            "padx": 6, "pady": 3, "cursor": "hand2",
            "activebackground": RPG_CORES["roxo_escuro"],
            "activeforeground": "#fff", "bd": 0
        }
        tk.Button(frame_btns, text="🎒 Inventário", command=self._abrir_inventario, **btn_style).pack(side="left", padx=3)
        tk.Button(frame_btns, text="📜 Quests",     command=self._abrir_quests,     **btn_style).pack(side="left", padx=3)

        frame_btns2 = tk.Frame(self.painel, bg=RPG_CORES["painel"])
        frame_btns2.pack(pady=2)
        tk.Button(frame_btns2, text="💤 Descansar", command=self._descansar, **btn_style).pack(side="left", padx=3)
        tk.Button(frame_btns2, text="✕ Sair",       command=self._fechar,    **btn_style).pack(side="left", padx=3)

        # Área de diálogo do Casaro (embaixo de tudo)
        self.frame_dialogo_casaro = tk.Frame(self.win, bg="#0d0d20", height=60)
        self.frame_dialogo_casaro.pack(fill="x", padx=8, pady=(0, 8))
        self.frame_dialogo_casaro.pack_propagate(False)

        self.lbl_casaro_fala = tk.Label(
            self.frame_dialogo_casaro,
            text="",
            bg="#0d0d20", fg=RPG_CORES["roxo_brilho"],
            font=("Courier", 9, "italic"),
            wraplength=900, justify="left"
        )
        self.lbl_casaro_fala.pack(side="left", padx=12, pady=8)

        # Controles de teclado
        self.win.bind("<Left>",  lambda e: self._mover(-1, 0))
        self.win.bind("<Right>", lambda e: self._mover(1, 0))
        self.win.bind("<Up>",    lambda e: self._mover(0, -1))
        self.win.bind("<Down>",  lambda e: self._mover(0, 1))
        self.win.bind("<a>",     lambda e: self._mover(-1, 0))
        self.win.bind("<d>",     lambda e: self._mover(1, 0))
        self.win.bind("<w>",     lambda e: self._mover(0, -1))
        self.win.bind("<s>",     lambda e: self._mover(0, 1))
        self.win.bind("<space>", lambda e: self._interagir())
        self.win.bind("<i>",     lambda e: self._abrir_inventario())
        self.win.bind("<q>",     lambda e: self._abrir_quests())
        self.win.bind("<r>",     lambda e: self._descansar())
        self.win.focus_set()
        # Re-foca ao clicar no canvas (caso o foco seja perdido)
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<FocusIn>",  lambda e: None)
        self.win.bind("<FocusIn>", lambda e: self.canvas.focus_set())

    # ── Intro / Menu ─────────────────────────────────────────

    def _mostrar_intro(self):
        self.fase = "menu"
        self.canvas.delete("all")
        c = self.canvas

        # Fundo estrelado
        for _ in range(60):
            x = random.randint(0, MAP_W)
            y = random.randint(0, MAP_H)
            c.create_text(x, y, text="·", fill="#ffffff22", font=("Courier", 8))

        # Título
        c.create_text(MAP_W//2, 80, text="⬡ CASARO RPG ⬡",
                      fill=RPG_CORES["roxo_brilho"], font=("Courier", 28, "bold"))
        c.create_text(MAP_W//2, 120, text="O   M U N D O   D O   C U B O",
                      fill=RPG_CORES["borda"], font=("Courier", 12))

        # Avatar do Casaro (desenhado)
        cx, cy = MAP_W//2, 240
        # Cubo
        c.create_rectangle(cx-50, cy-60, cx+50, cy+40, fill="#3b1f6e", outline="#c084fc", width=3)
        # Olhos
        c.create_rectangle(cx-30, cy-35, cx-8,  cy-15, fill="#c084fc", outline="#fff", width=1)
        c.create_rectangle(cx+8,  cy-35, cx+30, cy-15, fill="#c084fc", outline="#fff", width=1)
        # Sorriso
        c.create_arc(cx-25, cy-10, cx+25, cy+20, start=200, extent=140,
                     outline="#fbbf24", width=2, style="arc")
        # Cartola
        c.create_rectangle(cx-40, cy-80, cx+40, cy-60, fill="#1f0a3e", outline="#c084fc", width=2)
        c.create_rectangle(cx-28, cy-120, cx+28, cy-80, fill="#2d1060", outline="#c084fc", width=2)
        # Terno listrado
        c.create_rectangle(cx-40, cy+40, cx+40, cy+120,
                           fill="#1f0a3e", outline="#c084fc", width=2)
        for lx in range(cx-35, cx+40, 12):
            c.create_line(lx, cy+40, lx, cy+120, fill="#3b1f6e", width=1)

        # Texto de intro
        c.create_text(MAP_W//2, 380,
                      text='"Bem-vindo ao meu mundo. Tente não fazer feio."',
                      fill=RPG_CORES["ouro"], font=("Courier", 11, "italic"))
        c.create_text(MAP_W//2, 410,
                      text="— Casaro, Criador do Mundo (e de problemas)",
                      fill=RPG_CORES["cinza"], font=("Courier", 9))

        # Botão iniciar
        btn_iniciar = tk.Button(
            self.canvas, text="⚔  INICIAR JORNADA  ⚔",
            bg=RPG_CORES["roxo_escuro"], fg="#fff",
            font=("Courier", 12, "bold"), relief="flat", padx=20, pady=10,
            cursor="hand2", activebackground=RPG_CORES["borda"],
            command=self._tela_customizacao, bd=0
        )
        self.canvas.create_window(MAP_W//2, 500, window=btn_iniciar)

        c.create_text(MAP_W//2, MAP_H - 20,
                      text="WASD / Setas: mover  |  SPACE: interagir  |  I: inventário  |  Q: quests",
                      fill=RPG_CORES["cinza"], font=("Courier", 7))
        self.win.update_idletasks()

    # ── Customização ─────────────────────────────────────────

    def _tela_customizacao(self):
        self.fase = "customizacao"
        self.canvas.delete("all")
        c = self.canvas
        self._custom_nome = tk.StringVar(value="Herói")
        self._custom_classe = tk.StringVar(value="Guerreiro")

        c.create_text(MAP_W//2, 40, text="✦  CRIAR PERSONAGEM  ✦",
                      fill=RPG_CORES["roxo_brilho"], font=("Courier", 18, "bold"))

        # Nome
        c.create_text(MAP_W//2 - 150, 100, text="Nome:", fill=RPG_CORES["branco"],
                      font=("Courier", 11), anchor="e")
        entry_nome = tk.Entry(c, textvariable=self._custom_nome,
                              bg="#1e1040", fg=RPG_CORES["ouro"],
                              insertbackground=RPG_CORES["ouro"],
                              font=("Courier", 12), relief="flat", width=20,
                              highlightthickness=1, highlightbackground=RPG_CORES["borda"])
        c.create_window(MAP_W//2 + 40, 100, window=entry_nome)

        # Classes
        c.create_text(MAP_W//2, 145, text="Escolha sua classe:",
                      fill=RPG_CORES["branco"], font=("Courier", 11))

        self._classe_frames = {}
        for i, (nome_classe, dados) in enumerate(CLASSES.items()):
            col = i % 2
            row = i // 2
            cx2 = 160 + col * 360
            cy2 = 210 + row * 200

            frame_cls = tk.Frame(c, bg=RPG_CORES["painel"],
                                 highlightthickness=2,
                                 highlightbackground=RPG_CORES["borda"])
            self._classe_frames[nome_classe] = frame_cls

            tk.Label(frame_cls, text=dados["emoji"],
                     bg=RPG_CORES["painel"], font=("Courier", 24)).pack(pady=(8,2))
            tk.Label(frame_cls, text=nome_classe,
                     bg=RPG_CORES["painel"], fg=dados["cor"],
                     font=("Courier", 11, "bold")).pack()
            tk.Label(frame_cls, text=dados["desc"],
                     bg=RPG_CORES["painel"], fg=RPG_CORES["cinza"],
                     font=("Courier", 8), wraplength=150).pack(pady=2)
            stats_txt = (f"HP:{dados['hp']}  MP:{dados['mp']}\n"
                         f"ATK:{dados['atk']}  DEF:{dados['def_']}  SPD:{dados['spd']}")
            tk.Label(frame_cls, text=stats_txt,
                     bg=RPG_CORES["painel"], fg=RPG_CORES["branco"],
                     font=("Courier", 7)).pack()
            tk.Button(frame_cls, text="Selecionar",
                      bg=RPG_CORES["roxo_escuro"], fg="#fff",
                      font=("Courier", 9), relief="flat", cursor="hand2",
                      command=lambda n=nome_classe: self._selecionar_classe(n),
                      activebackground=RPG_CORES["borda"], bd=0, padx=8, pady=4
                      ).pack(pady=(4, 8))

            c.create_window(cx2, cy2, window=frame_cls, width=170, height=170)

        # Botão confirmar
        btn_conf = tk.Button(c, text="⚔  ENTRAR NO MUNDO  ⚔",
                             bg=RPG_CORES["roxo_escuro"], fg="#fff",
                             font=("Courier", 12, "bold"), relief="flat", padx=20, pady=10,
                             cursor="hand2", activebackground=RPG_CORES["borda"],
                             command=self._iniciar_jogo, bd=0)
        c.create_window(MAP_W//2, 620, window=btn_conf)

        self._selecionar_classe("Guerreiro")

    def _selecionar_classe(self, nome):
        self._custom_classe.set(nome)
        for n, frame in self._classe_frames.items():
            cor = RPG_CORES["roxo_brilho"] if n == nome else RPG_CORES["borda"]
            frame.config(highlightbackground=cor)

    def _iniciar_jogo(self):
        nome  = self._custom_nome.get().strip() or "Herói"
        classe = self._custom_classe.get()
        self.estado = _novo_estado_jogo(nome, classe)
        self.fase   = "jogo"
        self._log("Bem-vindo ao Mundo do Casaro!", RPG_CORES["roxo_brilho"])
        self._log("Use WASD ou setas para andar.", RPG_CORES["cinza"])
        self._log("SPACE para interagir.", RPG_CORES["cinza"])
        self._casaro_falar(random.choice(CASARO_WORLD_DIALOGOS["inicio"]))
        self._atualizar_painel()
        self._desenhar_mapa()

    # ── Loop de animação ─────────────────────────────────────

    def _loop_animacao(self):
        if not self.win.winfo_exists():
            return
        self._tick += 1
        if self.fase == "jogo" and self.estado:
            if self._tick % 30 == 0:
                self._redesenhar_tiles_animados()
            self._atualizar_particulas()
        elif self.fase == "menu":
            if self._tick % 60 == 0:
                self._animar_menu_estrelas()
        self.win.after(50, self._loop_animacao)

    def _animar_menu_estrelas(self):
        pass  # estrelas estáticas por enquanto

    def _redesenhar_tiles_animados(self):
        if not self.estado:
            return
        # Redesenha tiles animados (água, fogueiras)
        ox = self.estado["pos_x"] - VIEW_COLS // 2
        oy = self.estado["pos_y"] - VIEW_ROWS // 2
        for vy in range(VIEW_ROWS):
            for vx in range(VIEW_COLS):
                mx = ox + vx
                my = oy + vy
                if 0 <= mx < COLS and 0 <= my < ROWS:
                    t = self.mapa[my][mx]
                    if t in (T_AGUA, T_FOGUEIRA):
                        self._desenhar_tile(vx, vy, mx, my)

    def _atualizar_particulas(self):
        self._particulas = [(x, y, vx, vy, cor, vida-1) for x, y, vx, vy, cor, vida in self._particulas if vida > 0]

    # ── Desenho do mapa ──────────────────────────────────────

    def _desenhar_mapa(self):
        if self.fase != "jogo" or not self.estado:
            return
        self.canvas.delete("all")
        e = self.estado
        ox = e["pos_x"] - VIEW_COLS // 2
        oy = e["pos_y"] - VIEW_ROWS // 2

        for vy in range(VIEW_ROWS):
            for vx in range(VIEW_COLS):
                mx = ox + vx
                my = oy + vy
                self._desenhar_tile(vx, vy, mx, my)

        # Desenha NPCs
        for npc in self._npcs:
            vx = npc["x"] - ox
            vy = npc["y"] - oy
            if 0 <= vx < VIEW_COLS and 0 <= vy < VIEW_ROWS:
                px = vx * TILE + TILE // 2
                py = vy * TILE + TILE // 2
                self.canvas.create_oval(px-14, py-14, px+14, py+14,
                                        fill="#1e1040", outline=RPG_CORES["ouro"], width=2)
                self.canvas.create_text(px, py, text=npc["emoji"],
                                        font=("Segoe UI Emoji", 14))

        # Desenha inimigos
        for inimigo in self._inimigos_mapa:
            if not inimigo["vivo"]:
                continue
            vx = inimigo["x"] - ox
            vy = inimigo["y"] - oy
            if 0 <= vx < VIEW_COLS and 0 <= vy < VIEW_ROWS:
                px = vx * TILE + TILE // 2
                py = vy * TILE + TILE // 2
                self.canvas.create_oval(px-14, py-14, px+14, py+14,
                                        fill="#3b0000", outline=RPG_CORES["vermelho"], width=2)
                self.canvas.create_text(px, py, text=inimigo["emoji"],
                                        font=("Segoe UI Emoji", 12))

        # Desenha boss (posição fixa row=19)
        bvx = 9 - ox
        bvy = 19 - oy
        if 0 <= bvx < VIEW_COLS and 0 <= bvy < VIEW_ROWS and not e["boss_derrotado"]:
            px = bvx * TILE + TILE // 2
            py = bvy * TILE + TILE // 2
            self.canvas.create_oval(px-18, py-18, px+18, py+18,
                                    fill="#3b0000", outline="#ef4444", width=3)
            self.canvas.create_text(px, py, text="🐉", font=("Segoe UI Emoji", 18))

        # Desenha jogador
        pvx = VIEW_COLS // 2
        pvy = VIEW_ROWS // 2
        px = pvx * TILE + TILE // 2
        py = pvy * TILE + TILE // 2
        cor_classe = CLASSES[e["classe"]]["cor"]
        self.canvas.create_oval(px-15, py-15, px+15, py+15,
                                fill="#0d0d20", outline=cor_classe, width=3)
        self.canvas.create_text(px, py, text=e["emoji_classe"],
                                font=("Segoe UI Emoji", 14))

        # Mini HUD no canvas
        self._desenhar_mini_hud()

    def _desenhar_tile(self, vx, vy, mx, my):
        c = self.canvas
        px = vx * TILE
        py = vy * TILE

        if not (0 <= mx < COLS and 0 <= my < ROWS):
            c.create_rectangle(px, py, px+TILE, py+TILE, fill="#050508", outline="")
            return

        t = self.mapa[my][mx]
        cor_base, cor_detalhe, char = TILE_COR.get(t, ("#0a0a12", "#1a1a2e", "?"))

        # Animação de água
        if t == T_AGUA:
            fase_agua = (self._tick // 10) % 2
            cor_base = "#1d4ed8" if fase_agua == 0 else "#1e3a5f"
            char = "≈" if fase_agua == 0 else "~"
        elif t == T_FOGUEIRA:
            fase_fogo = (self._tick // 5) % 3
            chars_fogo = ["♨", "🔥", "♨"]
            cor_detalhe = ["#f97316", "#ef4444", "#fbbf24"][fase_fogo]
            char = chars_fogo[fase_fogo]

        c.create_rectangle(px, py, px+TILE, py+TILE, fill=cor_base, outline="#0a0a12", width=1)

        # Caractere decorativo
        if char and t not in (T_GRAMA,):
            c.create_text(px + TILE//2, py + TILE//2, text=char,
                          fill=cor_detalhe, font=("Courier", 9))

        # Sombra nas bordas da tela
        dist_cx = abs(vx - VIEW_COLS//2)
        dist_cy = abs(vy - VIEW_ROWS//2)
        dist = max(dist_cx, dist_cy)
        if dist >= VIEW_COLS//2 - 1 or dist >= VIEW_ROWS//2 - 1:
            alpha_hex = "44"
            c.create_rectangle(px, py, px+TILE, py+TILE,
                               fill="#000000", outline="", stipple="gray50")

    def _desenhar_mini_hud(self):
        e = self.estado
        if not e:
            return
        c = self.canvas
        # Posição no canto superior esquerdo do canvas
        c.create_rectangle(4, 4, 160, 42, fill="#000000aa", outline=RPG_CORES["borda"])
        c.create_text(8, 8, text=f"{e['emoji_classe']} {e['nome']}  Lv.{e['nivel']}",
                      fill=RPG_CORES["ouro"], font=("Courier", 8), anchor="nw")
        hp_pct = e["hp"] / max(e["hp_max"], 1)
        c.create_rectangle(8, 22, 8 + int(148 * hp_pct), 30,
                           fill=RPG_CORES["vermelho"], outline="")
        c.create_text(8, 32, text=f"HP {e['hp']}/{e['hp_max']}  💰{e['ouro']}",
                      fill=RPG_CORES["branco"], font=("Courier", 7), anchor="nw")

    # ── Movimentação ─────────────────────────────────────────

    def _mover(self, dx, dy):
        if self.fase != "jogo" or not self.estado:
            return
        e = self.estado
        nx = e["pos_x"] + dx
        ny = e["pos_y"] + dy

        if not (0 <= nx < COLS and 0 <= ny < ROWS):
            return

        tile_dest = self.mapa[ny][nx]
        if tile_dest in BLOQUEANTES:
            self._log("Caminho bloqueado.", RPG_CORES["cinza"])
            return

        # Verifica inimigo na posição destino
        for inimigo in self._inimigos_mapa:
            if inimigo["vivo"] and inimigo["x"] == nx and inimigo["y"] == ny:
                self._iniciar_combate(inimigo)
                return

        # Verifica boss
        if nx == 9 and ny == 19 and not e["boss_derrotado"]:
            self._casaro_falar(random.choice(CASARO_WORLD_DIALOGOS["boss_area"]))
            self._iniciar_combate(BOSS_INIMIGO.copy())
            return

        e["pos_x"] = nx
        e["pos_y"] = ny
        e["tiles_visitados"].add((nx, ny))

        # Verifica tile especial na nova posição
        self._verificar_tile_especial(nx, ny, tile_dest)

        # Verifica NPC próximo
        self._verificar_npc_proximo(nx, ny)

        # Encontro aleatório (20% de chance nas ervas)
        if tile_dest == T_ERVA and random.random() < 0.25:
            inimigo = random.choice(INIMIGOS_BASE).copy()
            inimigo["hp_atual"] = inimigo["hp"]
            inimigo["vivo"] = True
            self._casaro_falar("Opa, inimigo nas ervas! Clássico.")
            self._iniciar_combate(inimigo)
            return

        self._atualizar_painel()
        self._desenhar_mapa()

    def _verificar_tile_especial(self, x, y, tile):
        e = self.estado
        chave = f"tile_{x}_{y}"

        if tile == T_ALTAR and not e["altar_visitado"]:
            e["altar_visitado"] = True
            e["hp"] = min(e["hp"] + 30, e["hp_max"])
            e["mp"] = min(e["mp"] + 20, e["mp_max"])
            self._log("✦ Altar! +30HP +20MP", RPG_CORES["ouro"])
            self._casaro_falar(random.choice(CASARO_WORLD_DIALOGOS["altar"]))
            self._verificar_quest_objetivo("altar")

        elif tile == T_RUNA and chave not in e["casaro_comentou"]:
            e["casaro_comentou"].add(chave)
            e["runas_ativadas"] += 1
            e["mp"] = min(e["mp"] + 15, e["mp_max"])
            self._log("⊗ Runa ativada! +15MP", RPG_CORES["roxo_brilho"])
            self._casaro_falar(random.choice(CASARO_WORLD_DIALOGOS["runa"]))
            self._verificar_quest_objetivo("runas")

        elif tile == T_TESOURO and chave not in e["casaro_comentou"]:
            e["casaro_comentou"].add(chave)
            ouro = random.randint(15, 40)
            e["ouro"] += ouro
            self._log(f"💰 Tesouro! +{ouro} ouro", RPG_CORES["ouro"])
            self._casaro_falar(random.choice(CASARO_WORLD_DIALOGOS["tesouro"]))

        elif tile == T_PORTA and chave not in e["casaro_comentou"]:
            e["casaro_comentou"].add(chave)
            self._casaro_falar(random.choice(CASARO_WORLD_DIALOGOS["porta_masmorra"]))

        elif tile == T_FOGUEIRA and chave not in e["casaro_comentou"]:
            e["casaro_comentou"].add(chave)
            e["hp"] = min(e["hp"] + 15, e["hp_max"])
            self._log("♨ Fogueira! +15HP", RPG_CORES["verde"])

    def _verificar_npc_proximo(self, x, y):
        e = self.estado
        for npc in self._npcs:
            dist = abs(npc["x"] - x) + abs(npc["y"] - y)
            if dist == 1:
                nome_chave = f"npc_{npc['nome']}"
                if nome_chave not in e["casaro_comentou"]:
                    self._log(f"[SPACE] Falar com {npc['nome']}", RPG_CORES["ouro"])
                    break

    # ── Interação ────────────────────────────────────────────

    def _interagir(self):
        if self.fase != "jogo" or not self.estado:
            return
        e = self.estado
        x, y = e["pos_x"], e["pos_y"]

        # Verifica NPC adjacente
        for npc in self._npcs:
            dist = abs(npc["x"] - x) + abs(npc["y"] - y)
            if dist <= 1:
                self._abrir_dialogo_npc(npc)
                return

        self._log("Nada por aqui...", RPG_CORES["cinza"])

    # ── Diálogo com NPC ──────────────────────────────────────

    def _abrir_dialogo_npc(self, npc):
        self.fase = "dialogo_npc"
        self._dialogo = {"npc": npc, "fase": "fala"}
        self.canvas.delete("all")
        c = self.canvas
        e = self.estado

        # Fundo
        c.create_rectangle(0, 0, MAP_W, MAP_H, fill="#000000aa")
        c.create_rectangle(50, MAP_H//4, MAP_W-50, MAP_H*3//4,
                           fill=RPG_CORES["painel"], outline=RPG_CORES["borda"], width=3)

        c.create_text(MAP_W//2, MAP_H//4 + 25,
                      text=f"{npc['emoji']}  {npc['nome']}",
                      fill=RPG_CORES["ouro"], font=("Courier", 14, "bold"))

        # Fala do NPC
        fala = random.choice(npc["fala"])
        c.create_text(MAP_W//2, MAP_H//2 - 20, text=f'"{fala}"',
                      fill=RPG_CORES["branco"], font=("Courier", 10), wraplength=500)

        # Botões
        if "loja" in npc:
            btn_loja = tk.Button(c, text="🛒 Ver loja",
                                 bg=RPG_CORES["roxo_escuro"], fg="#fff",
                                 font=("Courier", 10), relief="flat", cursor="hand2",
                                 command=lambda: self._abrir_loja(npc), bd=0, padx=12, pady=6)
            c.create_window(MAP_W//2 - 80, MAP_H*3//4 - 30, window=btn_loja)

        btn_fechar_dialogo = tk.Button(c, text="✕ Fechar",
                                       bg=RPG_CORES["cinza"], fg="#fff",
                                       font=("Courier", 10), relief="flat", cursor="hand2",
                                       command=self._fechar_dialogo, bd=0, padx=12, pady=6)
        c.create_window(MAP_W//2 + 60 if "loja" in npc else MAP_W//2,
                        MAP_H*3//4 - 30, window=btn_fechar_dialogo)

        # Quest do NPC (se houver side quest disponível)
        self._verificar_side_quest_npc(npc)

    def _fechar_dialogo(self):
        self.fase = "jogo"
        self._desenhar_mapa()

    # ── Loja ─────────────────────────────────────────────────

    def _abrir_loja(self, npc):
        self.canvas.delete("all")
        c = self.canvas
        e = self.estado

        c.create_rectangle(0, 0, MAP_W, MAP_H, fill=RPG_CORES["bg"])
        c.create_text(MAP_W//2, 30, text=f"🛒 LOJA DE {npc['nome'].upper()}",
                      fill=RPG_CORES["ouro"], font=("Courier", 14, "bold"))
        c.create_text(MAP_W//2, 55, text=f"💰 Seu ouro: {e['ouro']}",
                      fill=RPG_CORES["branco"], font=("Courier", 10))

        for i, nome_item in enumerate(npc["loja"]):
            item = ITENS.get(nome_item)
            if not item:
                continue
            row = i // 2
            col = i % 2
            ix = 160 + col * 360
            iy = 110 + row * 110

            frame_item = tk.Frame(c, bg=RPG_CORES["painel"],
                                  highlightthickness=1, highlightbackground=RPG_CORES["borda"])
            tk.Label(frame_item, text=f"{item['emoji']} {nome_item}",
                     bg=RPG_CORES["painel"], fg=RPG_CORES["branco"],
                     font=("Courier", 9, "bold")).pack(pady=(6,2), padx=8)
            efeito_txt = f"+{item['valor']} {item['efeito'].upper().replace('_','')}"
            tk.Label(frame_item, text=efeito_txt,
                     bg=RPG_CORES["painel"], fg=RPG_CORES["verde"],
                     font=("Courier", 8)).pack()
            pode_comprar = e["ouro"] >= item["preco"]
            tk.Button(frame_item,
                      text=f"💰 {item['preco']} ouro",
                      bg=RPG_CORES["roxo_escuro"] if pode_comprar else RPG_CORES["cinza"],
                      fg="#fff", font=("Courier", 8), relief="flat", cursor="hand2",
                      command=(lambda n=nome_item, p=item["preco"]: self._comprar_item(n, p)) if pode_comprar else lambda: None,
                      bd=0, padx=6, pady=3).pack(pady=(4,6))
            c.create_window(ix, iy, window=frame_item, width=180, height=90)

        btn_voltar = tk.Button(c, text="← Voltar",
                               bg=RPG_CORES["cinza"], fg="#fff",
                               font=("Courier", 10), relief="flat", cursor="hand2",
                               command=self._fechar_dialogo, bd=0, padx=12, pady=6)
        c.create_window(MAP_W//2, MAP_H - 40, window=btn_voltar)

    def _comprar_item(self, nome_item, preco):
        e = self.estado
        item = ITENS.get(nome_item)
        if not item or e["ouro"] < preco:
            return
        e["ouro"] -= preco
        inv = e["inventario"]
        inv[nome_item] = inv.get(nome_item, 0) + 1
        self._log(f"Comprou {item['emoji']} {nome_item}!", RPG_CORES["ouro"])
        self._fechar_dialogo()

    # ── Combate ──────────────────────────────────────────────

    def _iniciar_combate(self, inimigo_dados):
        self.fase = "combate"
        e = self.estado
        self._combate = {
            "inimigo":     inimigo_dados.copy(),
            "turno":       "jogador",
            "log":         [],
            "habilidade_idx": 0,
            "animando":    False,
            "vitoria":     False,
            "derrota":     False,
        }
        if "hp_atual" not in self._combate["inimigo"]:
            self._combate["inimigo"]["hp_atual"] = self._combate["inimigo"]["hp"]

        self._desenhar_combate()

    def _desenhar_combate(self):
        self.canvas.delete("all")
        c = self.canvas
        e = self.estado
        comb = self._combate
        inimigo = comb["inimigo"]

        # Fundo da batalha
        c.create_rectangle(0, 0, MAP_W, MAP_H, fill="#0a0014")
        # Grade de batalha
        for i in range(0, MAP_W, 60):
            c.create_line(i, 0, i, MAP_H, fill="#1a0030", width=1)
        for i in range(0, MAP_H, 60):
            c.create_line(0, i, MAP_W, i, fill="#1a0030", width=1)

        # Título
        boss_txt = " ☠ BOSS ☠" if inimigo.get("boss") else ""
        c.create_text(MAP_W//2, 25, text=f"⚔  COMBATE{boss_txt}  ⚔",
                      fill=RPG_CORES["roxo_brilho"] if not inimigo.get("boss") else RPG_CORES["vermelho"],
                      font=("Courier", 14, "bold"))

        # Painel do jogador (esquerda)
        c.create_rectangle(30, 60, 330, 220, fill=RPG_CORES["painel"],
                           outline=RPG_CORES["borda"], width=2)
        c.create_text(180, 80, text=f"{e['emoji_classe']} {e['nome']}",
                      fill=RPG_CORES["ouro"], font=("Courier", 11, "bold"))
        c.create_text(180, 100, text=f"Lv.{e['nivel']} {e['classe']}",
                      fill=RPG_CORES["cinza"], font=("Courier", 8))

        # Barras jogador
        self._barra_combate(c, 50, 115, 260, 14, e["hp"], e["hp_max"],
                           RPG_CORES["vermelho"], f"HP {e['hp']}/{e['hp_max']}")
        self._barra_combate(c, 50, 138, 260, 14, e["mp"], e["mp_max"],
                           RPG_CORES["azul"], f"MP {e['mp']}/{e['mp_max']}")

        c.create_text(180, 165, text=f"ATK:{e['atk']}  DEF:{e['def_']}  SPD:{e['spd']}",
                      fill=RPG_CORES["branco"], font=("Courier", 8))

        # Avatar do jogador (placeholder pixel)
        cor_cls = CLASSES[e["classe"]]["cor"]
        c.create_oval(120, 175, 240, 215, fill="#0d0d20", outline=cor_cls, width=3)
        c.create_text(180, 195, text=e["emoji_classe"], font=("Segoe UI Emoji", 22))

        # Painel do inimigo (direita)
        cor_borda_inimigo = RPG_CORES["vermelho"] if inimigo.get("boss") else RPG_CORES["borda"]
        c.create_rectangle(MAP_W-330, 60, MAP_W-30, 220, fill=RPG_CORES["painel"],
                           outline=cor_borda_inimigo, width=2)
        c.create_text(MAP_W-180, 80, text=inimigo["nome"],
                      fill=inimigo.get("cor", RPG_CORES["vermelho"]), font=("Courier", 11, "bold"))
        c.create_text(MAP_W-180, 100, text="Inimigo",
                      fill=RPG_CORES["cinza"], font=("Courier", 8))
        self._barra_combate(c, MAP_W-310, 115, 260, 14,
                           inimigo["hp_atual"], inimigo["hp"],
                           inimigo.get("cor", RPG_CORES["vermelho"]),
                           f"HP {inimigo['hp_atual']}/{inimigo['hp']}")
        c.create_text(MAP_W-180, 165,
                      text=f"ATK:{inimigo['atk']}  DEF:{inimigo['def_']}",
                      fill=RPG_CORES["branco"], font=("Courier", 8))

        # Avatar do inimigo
        c.create_oval(MAP_W-240, 175, MAP_W-120, 215,
                     fill="#200000", outline=cor_borda_inimigo, width=3)
        c.create_text(MAP_W-180, 195, text=inimigo["emoji"],
                     font=("Segoe UI Emoji", 22))

        # VS
        c.create_text(MAP_W//2, 140, text="VS", fill=RPG_CORES["roxo_brilho"],
                     font=("Courier", 20, "bold"))

        # Log de combate
        c.create_rectangle(30, 230, MAP_W-30, 350, fill="#0d0d1a",
                          outline=RPG_CORES["borda"])
        for i, (txt, cor) in enumerate(comb["log"][-5:]):
            c.create_text(40, 243 + i*22, text=f"▸ {txt}",
                         fill=cor, font=("Courier", 8), anchor="nw")

        # Botões de ação (turno do jogador)
        if comb["turno"] == "jogador" and not comb["animando"]:
            btn_style = {
                "bg": "#1e1040", "fg": RPG_CORES["roxo_brilho"],
                "font": ("Courier", 9, "bold"), "relief": "flat",
                "cursor": "hand2", "activebackground": RPG_CORES["roxo_escuro"],
                "activeforeground": "#fff", "bd": 0, "padx": 10, "pady": 6
            }

            # Habilidades
            for i, hab in enumerate(e["habilidades"]):
                col = i % 3
                row_h = i // 3
                bx = 130 + col * 220
                by = 390 + row_h * 50
                btn = tk.Button(self.canvas, text=f"⚡ {hab}", **btn_style,
                               command=lambda h=hab: self._acao_combate("habilidade", h))
                self.canvas.create_window(bx, by, window=btn)

            # Ações básicas
            btn_style2 = btn_style.copy()
            btn_style2["bg"] = "#1a1a2e"
            bx_base = 180
            btn_atkb = tk.Button(self.canvas, text="⚔ Atacar", **btn_style2,
                                command=lambda: self._acao_combate("atacar"))
            self.canvas.create_window(bx_base, 450, window=btn_atkb)

            btn_item = tk.Button(self.canvas, text="🧪 Item", **btn_style2,
                                command=self._combate_usar_item)
            self.canvas.create_window(bx_base + 180, 450, window=btn_item)

            btn_fugir = tk.Button(self.canvas, text="💨 Fugir", **btn_style2,
                                 command=lambda: self._acao_combate("fugir"))
            self.canvas.create_window(bx_base + 360, 450, window=btn_fugir)

        elif comb["turno"] == "inimigo" and not comb["animando"]:
            self.win.after(1000, self._turno_inimigo)

        # Resultado
        if comb.get("vitoria"):
            c.create_rectangle(MAP_W//2 - 200, MAP_H//2 - 60,
                               MAP_W//2 + 200, MAP_H//2 + 60,
                               fill="#0a200a", outline=RPG_CORES["verde"], width=3)
            c.create_text(MAP_W//2, MAP_H//2 - 20,
                         text="⚔  VITÓRIA!  ⚔",
                         fill=RPG_CORES["verde"], font=("Courier", 18, "bold"))
            c.create_text(MAP_W//2, MAP_H//2 + 15,
                         text=f"+{comb['inimigo'].get('xp',0)} XP  +{comb['inimigo'].get('ouro',0)} 💰",
                         fill=RPG_CORES["ouro"], font=("Courier", 12))
            btn_cont = tk.Button(self.canvas, text="Continuar →",
                                bg=RPG_CORES["verde_escuro"], fg="#fff",
                                font=("Courier", 10, "bold"), relief="flat",
                                cursor="hand2", bd=0, padx=14, pady=6,
                                command=self._fim_combate_vitoria)
            self.canvas.create_window(MAP_W//2, MAP_H//2 + 45, window=btn_cont)

        elif comb.get("derrota"):
            c.create_rectangle(MAP_W//2 - 200, MAP_H//2 - 60,
                               MAP_W//2 + 200, MAP_H//2 + 60,
                               fill="#200000", outline=RPG_CORES["vermelho"], width=3)
            c.create_text(MAP_W//2, MAP_H//2 - 20,
                         text="☠  DERROTA  ☠",
                         fill=RPG_CORES["vermelho"], font=("Courier", 18, "bold"))
            self._casaro_falar(random.choice(CASARO_WORLD_DIALOGOS["morte"]))
            btn_revive = tk.Button(self.canvas, text="↩ Ressuscitar (perde 30% do ouro)",
                                  bg="#3b0000", fg="#fff",
                                  font=("Courier", 9), relief="flat",
                                  cursor="hand2", bd=0, padx=10, pady=6,
                                  command=self._ressuscitar)
            self.canvas.create_window(MAP_W//2, MAP_H//2 + 30, window=btn_revive)

    def _barra_combate(self, c, x, y, largura, altura, valor, maximo, cor, label):
        c.create_rectangle(x, y, x+largura, y+altura,
                          fill="#1f1f35", outline=RPG_CORES["borda"])
        pct = max(0, min(1, valor / max(maximo, 1)))
        if pct > 0:
            c.create_rectangle(x+1, y+1, x+1+int((largura-2)*pct), y+altura-1,
                              fill=cor, outline="")
        c.create_text(x + largura//2, y + altura//2,
                     text=label, fill="#fff", font=("Courier", 7))

    def _acao_combate(self, tipo, habilidade=None):
        e = self.estado
        comb = self._combate
        inimigo = comb["inimigo"]
        comb["animando"] = True

        dano_base = e["atk"]
        critico = random.random() < 0.15

        if tipo == "atacar":
            dano = max(1, dano_base - inimigo["def_"] + random.randint(-3, 5))
            if critico:
                dano = int(dano * 1.8)
            inimigo["hp_atual"] -= dano
            txt = f"Você atacou! -{dano} HP" + (" (CRÍTICO!)" if critico else "")
            comb["log"].append((txt, RPG_CORES["vermelho"] if not critico else RPG_CORES["ouro"]))

        elif tipo == "habilidade":
            # Cada habilidade tem efeito diferente
            if "Fogo" in habilidade or "Frenesi" in habilidade or "Brutal" in habilidade:
                custo_mp = 15
                if e["mp"] >= custo_mp:
                    e["mp"] -= custo_mp
                    dano = max(1, int(dano_base * 1.6) - inimigo["def_"] + random.randint(0, 8))
                    inimigo["hp_atual"] -= dano
                    comb["log"].append((f"⚡ {habilidade}: -{dano} HP!", RPG_CORES["fogo"]))
                else:
                    comb["log"].append(("MP insuficiente!", RPG_CORES["cinza"]))
                    comb["animando"] = False
                    return
            elif "Gelo" in habilidade or "Chuva" in habilidade or "Veneno" in habilidade:
                custo_mp = 20
                if e["mp"] >= custo_mp:
                    e["mp"] -= custo_mp
                    dano = max(1, int(dano_base * 1.4) - inimigo["def_"] + random.randint(5, 15))
                    inimigo["hp_atual"] -= dano
                    comb["log"].append((f"⚡ {habilidade}: -{dano} HP!", RPG_CORES["azul"]))
                else:
                    comb["log"].append(("MP insuficiente!", RPG_CORES["cinza"]))
                    comb["animando"] = False
                    return
            elif "Escudo" in habilidade or "Invisível" in habilidade:
                custo_mp = 12
                if e["mp"] >= custo_mp:
                    e["mp"] -= custo_mp
                    cura = random.randint(15, 30)
                    e["hp"] = min(e["hp"] + cura, e["hp_max"])
                    comb["log"].append((f"✦ {habilidade}: +{cura} HP!", RPG_CORES["verde"]))
                else:
                    comb["log"].append(("MP insuficiente!", RPG_CORES["cinza"]))
                    comb["animando"] = False
                    return
            elif "Furtivo" in habilidade or "Roubar" in habilidade or "Certeiro" in habilidade:
                custo_mp = 10
                if e["mp"] >= custo_mp:
                    e["mp"] -= custo_mp
                    dano = max(1, int(dano_base * 2.0) - inimigo["def_"])
                    inimigo["hp_atual"] -= dano
                    ouro_roubado = random.randint(0, 5)
                    e["ouro"] += ouro_roubado
                    txt_extra = f" +{ouro_roubado}💰" if ouro_roubado > 0 else ""
                    comb["log"].append((f"⚡ {habilidade}: -{dano} HP!{txt_extra}", RPG_CORES["ouro"]))
                else:
                    comb["log"].append(("MP insuficiente!", RPG_CORES["cinza"]))
                    comb["animando"] = False
                    return
            else:
                dano = max(1, int(dano_base * 1.3) - inimigo["def_"])
                inimigo["hp_atual"] -= dano
                comb["log"].append((f"⚡ {habilidade}: -{dano} HP!", RPG_CORES["roxo_brilho"]))

        elif tipo == "fugir":
            if random.random() < 0.5:
                comb["log"].append(("Fugiu do combate!", RPG_CORES["verde"]))
                self.win.after(800, self._fechar_combate_fuga)
                return
            else:
                comb["log"].append(("Tentativa de fuga falhou!", RPG_CORES["vermelho"]))

        # Checa morte do inimigo
        if inimigo["hp_atual"] <= 0:
            inimigo["hp_atual"] = 0
            comb["vitoria"] = True
            comb["animando"] = False
            self._desenhar_combate()
            return

        # Turno do inimigo
        comb["turno"] = "inimigo"
        comb["animando"] = False
        self._desenhar_combate()

    def _turno_inimigo(self):
        e = self.estado
        comb = self._combate
        if self.fase != "combate" or comb.get("vitoria") or comb.get("derrota"):
            return

        inimigo = comb["inimigo"]
        dano = max(1, inimigo["atk"] - e["def_"] + random.randint(-2, 5))
        critico = random.random() < 0.1
        if critico:
            dano = int(dano * 1.5)

        e["hp"] -= dano
        txt = f"{inimigo['nome']}: -{dano} HP" + (" (CRÍTICO!)" if critico else "")
        comb["log"].append((txt, inimigo.get("cor", RPG_CORES["vermelho"])))

        if e["hp"] <= 0:
            e["hp"] = 0
            comb["derrota"] = True

        comb["turno"] = "jogador"
        comb["animando"] = False
        self._desenhar_combate()

    def _combate_usar_item(self):
        e = self.estado
        comb = self._combate
        # Usa primeira poção disponível
        for nome_item, qtd in list(e["inventario"].items()):
            if qtd <= 0:
                continue
            item = ITENS.get(nome_item)
            if not item or item["tipo"] != "consumivel":
                continue
            e["inventario"][nome_item] -= 1
            if e["inventario"][nome_item] == 0:
                del e["inventario"][nome_item]
            if item["efeito"] == "hp":
                ganho = min(item["valor"], e["hp_max"] - e["hp"])
                e["hp"] += ganho
                comb["log"].append((f"🧪 {nome_item}: +{ganho} HP", RPG_CORES["verde"]))
            elif item["efeito"] == "mp":
                ganho = min(item["valor"], e["mp_max"] - e["mp"])
                e["mp"] += ganho
                comb["log"].append((f"💧 {nome_item}: +{ganho} MP", RPG_CORES["azul"]))
            comb["turno"] = "inimigo"
            self._desenhar_combate()
            return
        comb["log"].append(("Sem itens de consumo!", RPG_CORES["cinza"]))
        self._desenhar_combate()

    def _fim_combate_vitoria(self):
        e = self.estado
        comb = self._combate
        inimigo = comb["inimigo"]

        # Recompensas
        xp_ganho  = inimigo.get("xp", 10)
        ouro_ganho = inimigo.get("ouro", 5)
        e["ouro"] += ouro_ganho
        subiu_nivel = _ganhar_xp(e, xp_ganho)

        # Conta inimigo morto para quests
        e["inimigos_mortos"] += 1
        self._verificar_quest_objetivo("matar")

        # Marca como morto no mapa (se for inimigo fixo)
        for inimigo_mapa in self._inimigos_mapa:
            if (inimigo_mapa["nome"] == inimigo["nome"] and inimigo_mapa["vivo"]):
                inimigo_mapa["vivo"] = False
                break

        # Boss?
        if inimigo.get("boss"):
            e["boss_derrotado"] = True
            self._verificar_quest_objetivo("boss")
            self._casaro_falar(random.choice(CASARO_WORLD_DIALOGOS["vitoria_boss"]))
        else:
            if subiu_nivel:
                self._casaro_falar(random.choice(CASARO_WORLD_DIALOGOS["nivel"]))
            self._log(f"+{xp_ganho} XP | +{ouro_ganho} 💰", RPG_CORES["ouro"])

        self._fechar_combate()

    def _fechar_combate(self):
        self.fase = "jogo"
        self._atualizar_painel()
        self._desenhar_mapa()

    def _fechar_combate_fuga(self):
        self._log("Fugiu do combate.", RPG_CORES["cinza"])
        self._fechar_combate()

    def _ressuscitar(self):
        e = self.estado
        e["ouro"] = int(e["ouro"] * 0.7)
        e["hp"] = e["hp_max"] // 2
        e["mp"] = e["mp_max"] // 2
        self._fechar_combate()

    # ── Painel lateral ───────────────────────────────────────

    def _atualizar_painel(self):
        e = self.estado
        if not e:
            return

        self.lbl_nome_classe.config(
            text=f"{e['emoji_classe']} {e['nome']}"
        )
        self.lbl_nivel.config(text=f"Lv.{e['nivel']} {e['classe']}")

        # Barra HP
        self.canvas_hp.delete("all")
        pct_hp = e["hp"] / max(e["hp_max"], 1)
        w = 140
        self.canvas_hp.create_rectangle(1, 1, int((w-2)*pct_hp)+1, 11,
                                        fill=RPG_CORES["vermelho"], outline="")
        self.canvas_hp.create_text(w//2, 6, text=f"{e['hp']}/{e['hp_max']}",
                                   fill="#fff", font=("Courier", 6))
        self.lbl_hp_val.config(text=f"{e['hp']}/{e['hp_max']}")

        # Barra MP
        self.canvas_mp.delete("all")
        pct_mp = e["mp"] / max(e["mp_max"], 1)
        self.canvas_mp.create_rectangle(1, 1, int((w-2)*pct_mp)+1, 11,
                                        fill=RPG_CORES["azul"], outline="")
        self.canvas_mp.create_text(w//2, 6, text=f"{e['mp']}/{e['mp_max']}",
                                   fill="#fff", font=("Courier", 6))
        self.lbl_mp_val.config(text=f"{e['mp']}/{e['mp_max']}")

        # Barra XP
        self.canvas_xp.delete("all")
        pct_xp = e["xp"] / max(e["xp_proximo"], 1)
        self.canvas_xp.create_rectangle(1, 1, int((w-2)*pct_xp)+1, 7,
                                        fill=RPG_CORES["ouro"], outline="")

        # Stats
        inv_total = sum(e["inventario"].values())
        self.lbl_stats.config(
            text=f"⚔ ATK:{e['atk']}  🛡 DEF:{e['def_']}  💨 SPD:{e['spd']}\n"
                 f"💰 {e['ouro']} ouro  🎒 {inv_total} itens\n"
                 f"☠ {e['inimigos_mortos']} mortes  XP:{e['xp']}/{e['xp_proximo']}"
        )

        # Quest ativa
        quests_txt = ""
        for q in e["quests_ativas"][:2]:
            if q.get("count_alvo"):
                progresso = f" ({q['count_atual']}/{q['count_alvo']})"
            else:
                progresso = ""
            quests_txt += f"• {q['titulo']}{progresso}\n"
        if not quests_txt:
            quests_txt = "Nenhuma quest ativa."
        self.lbl_quest.config(text=quests_txt.strip())

    def _log(self, msg, cor=None):
        if cor is None:
            cor = RPG_CORES["branco"]
        self._log_msgs.append((msg, cor))
        if len(self._log_msgs) > 5:
            self._log_msgs = self._log_msgs[-5:]
        for i, lbl in enumerate(self._log_labels):
            if i < len(self._log_msgs):
                m, c = self._log_msgs[i]
                lbl.config(text=m, fg=c)
            else:
                lbl.config(text="")

    # ── Quests ───────────────────────────────────────────────

    def _verificar_quest_objetivo(self, tipo):
        e = self.estado
        concluidas_agora = []

        for q in e["quests_ativas"]:
            objetivo = q.get("objetivo")
            if objetivo == "altar" and tipo == "altar":
                if not q.get("concluida"):
                    q["concluida"] = True
                    concluidas_agora.append(q)
            elif objetivo == "boss" and tipo == "boss":
                if not q.get("concluida"):
                    q["concluida"] = True
                    concluidas_agora.append(q)
            elif objetivo == "matar" and tipo == "matar":
                q["count_atual"] = q.get("count_atual", 0) + 1
                if q["count_atual"] >= q.get("count_alvo", 999):
                    if not q.get("concluida"):
                        q["concluida"] = True
                        concluidas_agora.append(q)
            elif objetivo == "runas" and tipo == "runas":
                q["count_atual"] = e["runas_ativadas"]
                if q["count_atual"] >= q.get("count_alvo", 999):
                    if not q.get("concluida"):
                        q["concluida"] = True
                        concluidas_agora.append(q)

        for q in concluidas_agora:
            e["quests_ativas"].remove(q)
            e["quests_concluidas"].append(q)
            xp_r = q.get("recompensa_xp", 0)
            ouro_r = q.get("recompensa_ouro", 0)
            _ganhar_xp(e, xp_r)
            e["ouro"] += ouro_r
            self._log(f"✦ Quest completa: {q['titulo']}!", RPG_CORES["ouro"])
            self._log(f"  +{xp_r} XP  +{ouro_r} 💰", RPG_CORES["ouro"])

            # Próxima quest principal
            qid = q.get("id")
            for i, qp in enumerate(QUESTS_PRINCIPAIS):
                if qp["id"] == qid and i + 1 < len(QUESTS_PRINCIPAIS):
                    prox = QUESTS_PRINCIPAIS[i+1].copy()
                    # Verifica se não está já ativa nem concluída
                    ids_ativas = [x.get("id") for x in e["quests_ativas"]]
                    ids_concluidas = [x.get("id") for x in e["quests_concluidas"]]
                    if prox["id"] not in ids_ativas and prox["id"] not in ids_concluidas:
                        e["quests_ativas"].append(prox)
                        self._log(f"📜 Nova quest: {prox['titulo']}!", RPG_CORES["roxo_brilho"])
                        self._casaro_falar(prox.get("casaro_fala", "Nova missão."))
                    break

            # Vitória final?
            if q.get("id") == "q4":
                self.win.after(2000, self._tela_vitoria_final)

        self._atualizar_painel()

    def _verificar_side_quest_npc(self, npc):
        """Gera side quest via Groq se disponível."""
        if len(self._side_quests_geradas) < 3:
            threading.Thread(target=self._gerar_side_quest_ia,
                            args=(npc,), daemon=True).start()

    def _gerar_side_quest_ia(self, npc):
        if not self.groq:
            return
        try:
            prompt = (
                f"Você é Casaro, criador de um mundo RPG fantasy medieval. "
                f"O NPC '{npc['nome']}' vai dar uma side quest ao herói. "
                f"Crie uma side quest curta e engraçada no estilo sarcástico do Casaro. "
                f"Responda SOMENTE com JSON: {{\"titulo\": \"...\", \"desc\": \"...\", \"casaro_fala\": \"...\"}}"
            )
            resp = self.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            raw = resp.choices[0].message.content.strip()
            raw = raw.replace("```json","").replace("```","").strip()
            import re as _re
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            if m:
                dados = json.loads(m.group(0))
                self._side_quests_geradas.append(dados)
        except Exception as ex:
            print(f"[rpg-ia] Side quest: {ex}")

    def _abrir_quests(self):
        if self.fase not in ("jogo", "combate"):
            return
        fase_anterior = self.fase
        self.fase = "quests_ui"
        self.canvas.delete("all")
        c = self.canvas
        e = self.estado

        c.create_rectangle(0, 0, MAP_W, MAP_H, fill=RPG_CORES["bg"])
        c.create_text(MAP_W//2, 30, text="📜  DIÁRIO DE QUESTS",
                     fill=RPG_CORES["roxo_brilho"], font=("Courier", 14, "bold"))
        tk.Frame(self.canvas, bg=RPG_CORES["borda"], height=1)

        y = 65
        c.create_text(40, y, text="ATIVAS:", fill=RPG_CORES["ouro"],
                     font=("Courier", 10, "bold"), anchor="w")
        y += 25
        for q in e["quests_ativas"]:
            progresso = ""
            if q.get("count_alvo"):
                progresso = f"  [{q.get('count_atual',0)}/{q['count_alvo']}]"
            c.create_text(60, y, text=f"▸ {q['titulo']}{progresso}",
                         fill=RPG_CORES["ouro"], font=("Courier", 9), anchor="w")
            y += 18
            c.create_text(80, y, text=q["desc"],
                         fill=RPG_CORES["cinza"], font=("Courier", 8), anchor="w",
                         width=600)
            y += 30

        # Side quests geradas por IA
        if self._side_quests_geradas:
            y += 10
            c.create_text(40, y, text="MISSÕES ESPECIAIS (por IA):",
                         fill=RPG_CORES["roxo_brilho"], font=("Courier", 9, "bold"), anchor="w")
            y += 20
            for sq in self._side_quests_geradas:
                c.create_text(60, y, text=f"★ {sq.get('titulo','')}",
                             fill=RPG_CORES["roxo_brilho"], font=("Courier", 9), anchor="w")
                y += 18
                c.create_text(80, y, text=sq.get("desc",""),
                             fill=RPG_CORES["cinza"], font=("Courier", 8), anchor="w",
                             width=580)
                y += 25

        y += 10
        c.create_text(40, y, text="CONCLUÍDAS:", fill=RPG_CORES["verde"],
                     font=("Courier", 10, "bold"), anchor="w")
        y += 25
        for q in e["quests_concluidas"]:
            c.create_text(60, y, text=f"✔ {q['titulo']}",
                         fill=RPG_CORES["verde"], font=("Courier", 9), anchor="w")
            y += 22

        btn_voltar = tk.Button(c, text="← Voltar ao jogo",
                              bg=RPG_CORES["cinza"], fg="#fff",
                              font=("Courier", 10), relief="flat", cursor="hand2",
                              command=lambda: (setattr(self, "fase", fase_anterior),
                                             self._desenhar_mapa() if fase_anterior == "jogo" else None),
                              bd=0, padx=12, pady=6)
        c.create_window(MAP_W//2, MAP_H - 30, window=btn_voltar)

    # ── Inventário ───────────────────────────────────────────

    def _abrir_inventario(self):
        if self.fase not in ("jogo", "combate"):
            return
        fase_anterior = self.fase
        self.fase = "inventario_ui"
        self.canvas.delete("all")
        c = self.canvas
        e = self.estado

        c.create_rectangle(0, 0, MAP_W, MAP_H, fill=RPG_CORES["bg"])
        c.create_text(MAP_W//2, 30, text="🎒  INVENTÁRIO",
                     fill=RPG_CORES["roxo_brilho"], font=("Courier", 14, "bold"))
        c.create_text(MAP_W//2, 55, text=f"💰 Ouro: {e['ouro']}",
                     fill=RPG_CORES["ouro"], font=("Courier", 10))

        y = 85
        c.create_text(40, y, text="ITENS:", fill=RPG_CORES["branco"],
                     font=("Courier", 10, "bold"), anchor="w")
        y += 25
        if not e["inventario"]:
            c.create_text(60, y, text="Inventário vazio.",
                         fill=RPG_CORES["cinza"], font=("Courier", 9), anchor="w")
        else:
            for nome_item, qtd in e["inventario"].items():
                item = ITENS.get(nome_item, {})
                emoji = item.get("emoji", "•")
                c.create_text(60, y, text=f"{emoji} {nome_item}  x{qtd}",
                             fill=RPG_CORES["branco"], font=("Courier", 9), anchor="w")
                if fase_anterior == "jogo" and item.get("tipo") == "consumivel":
                    btn_usar = tk.Button(c, text="Usar",
                                        bg=RPG_CORES["verde_escuro"], fg="#fff",
                                        font=("Courier", 8), relief="flat", cursor="hand2",
                                        command=lambda n=nome_item: self._usar_item(n),
                                        bd=0, padx=6, pady=2)
                    c.create_window(550, y, window=btn_usar)
                y += 24

        y += 20
        c.create_text(40, y, text="EQUIPAMENTOS:", fill=RPG_CORES["branco"],
                     font=("Courier", 10, "bold"), anchor="w")
        y += 25
        for slot, nome_item in e["equipamentos"].items():
            item = ITENS.get(nome_item, {})
            c.create_text(60, y, text=f"[{slot.upper()}] {item.get('emoji','')} {nome_item}",
                         fill=RPG_CORES["ouro"], font=("Courier", 9), anchor="w")
            y += 22
        if not e["equipamentos"]:
            c.create_text(60, y, text="Nenhum item equipado.",
                         fill=RPG_CORES["cinza"], font=("Courier", 9), anchor="w")

        btn_voltar = tk.Button(c, text="← Voltar ao jogo",
                              bg=RPG_CORES["cinza"], fg="#fff",
                              font=("Courier", 10), relief="flat", cursor="hand2",
                              command=lambda: (setattr(self, "fase", fase_anterior),
                                             self._desenhar_mapa() if fase_anterior == "jogo" else self._desenhar_combate()),
                              bd=0, padx=12, pady=6)
        c.create_window(MAP_W//2, MAP_H - 30, window=btn_voltar)

    def _usar_item(self, nome_item):
        e = self.estado
        item = ITENS.get(nome_item)
        if not item or e["inventario"].get(nome_item, 0) <= 0:
            return
        e["inventario"][nome_item] -= 1
        if e["inventario"][nome_item] == 0:
            del e["inventario"][nome_item]
        if item["efeito"] == "hp":
            ganho = min(item["valor"], e["hp_max"] - e["hp"])
            e["hp"] += ganho
            self._log(f"🧪 {nome_item}: +{ganho} HP", RPG_CORES["verde"])
        elif item["efeito"] == "mp":
            ganho = min(item["valor"], e["mp_max"] - e["mp"])
            e["mp"] += ganho
            self._log(f"💧 {nome_item}: +{ganho} MP", RPG_CORES["azul"])
        self._abrir_inventario()

    def _descansar(self):
        if self.fase != "jogo" or not self.estado:
            return
        e = self.estado
        cura_hp = int(e["hp_max"] * 0.4)
        cura_mp = int(e["mp_max"] * 0.4)
        e["hp"] = min(e["hp"] + cura_hp, e["hp_max"])
        e["mp"] = min(e["mp"] + cura_mp, e["mp_max"])
        custo = 10
        e["ouro"] = max(0, e["ouro"] - custo)
        self._log(f"💤 Descansou! +{cura_hp} HP +{cura_mp} MP (-{custo} 💰)", RPG_CORES["verde"])
        self._atualizar_painel()
        self._desenhar_mapa()

    # ── Fala do Casaro no rodapé ─────────────────────────────

    def _casaro_falar(self, texto):
        if not hasattr(self, "lbl_casaro_fala"):
            return
        clean = texto.replace("[RISADA]", "haha").replace("[CENSURA]", "***")
        self.lbl_casaro_fala.config(text=f'⬡ Casaro: "{clean}"')
        # Limpa após 8 segundos
        self.win.after(8000, lambda: self.lbl_casaro_fala.config(text=""))

    # ── Vitória final ────────────────────────────────────────

    def _tela_vitoria_final(self):
        self.fase = "vitoria"
        self.canvas.delete("all")
        c = self.canvas

        c.create_rectangle(0, 0, MAP_W, MAP_H, fill="#020208")
        for _ in range(100):
            x = random.randint(0, MAP_W)
            y = random.randint(0, MAP_H)
            cor = random.choice(["#c084fc", "#fbbf24", "#86efac", "#60a5fa"])
            c.create_text(x, y, text="✦", fill=cor, font=("Courier", random.randint(8,16)))

        c.create_text(MAP_W//2, 150, text="⬡  VOCÊ VENCEU!  ⬡",
                     fill=RPG_CORES["roxo_brilho"], font=("Courier", 28, "bold"))

        e = self.estado
        c.create_text(MAP_W//2, 220,
                     text=f"{e['emoji_classe']} {e['nome']} derrotou o Dracomante!",
                     fill=RPG_CORES["ouro"], font=("Courier", 14))

        c.create_text(MAP_W//2, 270,
                     text=f"Nível {e['nivel']}  •  {e['inimigos_mortos']} inimigos abatidos  •  💰{e['ouro']} ouro",
                     fill=RPG_CORES["branco"], font=("Courier", 10))

        # Fala final do Casaro
        c.create_rectangle(100, 320, MAP_W-100, 420,
                          fill=RPG_CORES["painel"], outline=RPG_CORES["borda"], width=2)
        c.create_text(MAP_W//2, 370,
                     text='"Parabéns. Genuinamente. Não esperava que um humano sobrevivesse\n'
                          'ao meu mundo. Tá bom, você ganhou o cubo de ouro imaginário.\n'
                          'Agora vai fazer algo útil com sua vida."  — Casaro',
                     fill=RPG_CORES["roxo_brilho"], font=("Courier", 9, "italic"),
                     wraplength=600, justify="center")

        btn_menu = tk.Button(c, text="↩ Voltar ao Menu",
                            bg=RPG_CORES["roxo_escuro"], fg="#fff",
                            font=("Courier", 11, "bold"), relief="flat",
                            cursor="hand2", bd=0, padx=16, pady=8,
                            command=self._mostrar_intro)
        c.create_window(MAP_W//2, 480, window=btn_menu)

    # ── Foco ─────────────────────────────────────────────────

    def _garantir_foco(self):
        """Força o foco para a janela do RPG para capturar teclado corretamente."""
        try:
            if self.win.winfo_exists():
                self.win.lift()
                self.win.focus_force()
                self.canvas.focus_set()
                # Rebind teclado direto no canvas também
                self.canvas.bind("<Left>",  lambda e: self._mover(-1, 0))
                self.canvas.bind("<Right>", lambda e: self._mover(1, 0))
                self.canvas.bind("<Up>",    lambda e: self._mover(0, -1))
                self.canvas.bind("<Down>",  lambda e: self._mover(0, 1))
                self.canvas.bind("<a>",     lambda e: self._mover(-1, 0))
                self.canvas.bind("<d>",     lambda e: self._mover(1, 0))
                self.canvas.bind("<w>",     lambda e: self._mover(0, -1))
                self.canvas.bind("<s>",     lambda e: self._mover(0, 1))
                self.canvas.bind("<space>", lambda e: self._interagir())
                self.canvas.bind("<i>",     lambda e: self._abrir_inventario())
                self.canvas.bind("<q>",     lambda e: self._abrir_quests())
                self.canvas.bind("<r>",     lambda e: self._descansar())
        except Exception as ex:
            print(f"[rpg] _garantir_foco: {ex}")

    # ── Fechar ───────────────────────────────────────────────

    def _fechar(self):
        try:
            self.win.grab_release()
        except:
            pass
        try:
            self.win.destroy()
        except:
            pass


# ============================================================
# DETECÇÃO DE GATILHOS DE JOGO
