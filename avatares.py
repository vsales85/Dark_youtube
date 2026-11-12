"""Bonequinhos do canal "Bravura Esquecida" - estilo PROPRIO desenhado por codigo (Skia), sem imagens de terceiros.

Cabecao, olhos grandes com palpebra expressiva, contorno marrom-escuro, sombra suave, corpo que pode vestir a
BANDEIRA de um pais/estado (personificacao), braco comprido com dedo apontando, acessorios militares do tema.

personagem = {"tipo": "pracinha", "pose": "aponta", "expressao": "bravo", "lado": "esq", "nome": "Geraldo",
              "pele": "clara|morena|parda|negra", "roupa": "bandeira:Brasil" (opcional), "olha": "esq|dir"}
Tipos: pracinha, alemao, soldado, imperador, politico, padre, marinheiro, povo, mulher, crianca, nacao
Poses: parado, aponta, bracos_cima, comemora, triste, anda, assustado
Expressoes: normal, preocupado, bravo, feliz, assustado
"""
import math
import skia

TINTA = skia.ColorSetRGB(38, 26, 20)          # contorno marrom-escuro (assinatura do canal)
PELES = {"clara": (244, 206, 172), "morena": (226, 178, 134), "parda": (184, 126, 86), "negra": (120, 78, 50)}
ORDEM_PELE = ["clara", "morena", "parda", "negra"]
CABELOS = [(46, 32, 24), (92, 60, 32), (24, 22, 22), (160, 156, 150)]

FIGURINOS = {
    "pracinha":   {"roupa": (104, 112, 66), "calca": (86, 92, 56), "chapeu": "capacete_rede", "cor_chapeu": (92, 100, 58), "acessorio": "fuzil", "distintivo": True},
    "alemao":     {"roupa": (112, 118, 112), "calca": (90, 94, 90), "chapeu": "capacete_aba", "cor_chapeu": (96, 100, 96), "acessorio": "fuzil"},
    "soldado":    {"roupa": (54, 78, 132), "calca": (236, 232, 220), "chapeu": "quepe", "cor_chapeu": (40, 52, 92), "acessorio": "lanca", "cruz": True},
    "imperador":  {"roupa": (30, 62, 140), "calca": (238, 234, 222), "chapeu": "coroa", "cor_chapeu": (236, 192, 62), "faixa": (24, 140, 70), "dragona": True},
    "politico":   {"roupa": (44, 44, 50), "calca": (38, 38, 42), "chapeu": "cartola", "cor_chapeu": (30, 30, 32), "gravata": True},
    "padre":      {"roupa": (32, 30, 32), "calca": (32, 30, 32), "chapeu": "", "colarinho": True, "comprido": True},
    "marinheiro": {"roupa": (238, 238, 242), "calca": (40, 60, 112), "chapeu": "marinheiro", "cor_chapeu": (240, 240, 244), "lenco": True},
    "povo":       {"roupa": (182, 96, 62), "calca": (96, 84, 70), "chapeu": "palha", "cor_chapeu": (222, 190, 116)},
    "mulher":     {"roupa": (156, 62, 96), "calca": (156, 62, 96), "chapeu": "", "cabelo": "longo", "comprido": True},
    "crianca":    {"roupa": (232, 182, 52), "calca": (62, 92, 152), "chapeu": "", "escala": 0.76},
    "nacao":      {"roupa": (200, 200, 200), "calca": (60, 60, 64), "chapeu": ""},
    # --- Brasil
    "cangaceiro": {"roupa": (128, 96, 62), "calca": (94, 72, 50), "chapeu": "cangaceiro", "cor_chapeu": (146, 100, 54), "acessorio": "fuzil", "cartucheira": True, "lenco_cor": (186, 36, 40)},
    "vaqueiro":   {"roupa": (152, 102, 60), "calca": (110, 76, 46), "chapeu": "aba_larga", "cor_chapeu": (132, 88, 48)},
    "bandeirante": {"roupa": (112, 92, 70), "calca": (82, 68, 54), "chapeu": "aba_larga", "cor_chapeu": (62, 52, 42), "acessorio": "fuzil"},
    "gaucho":     {"roupa": (236, 230, 214), "calca": (44, 42, 48), "chapeu": "aba_larga", "cor_chapeu": (42, 38, 36), "lenco_cor": (180, 30, 40)},
    "coronel":    {"roupa": (232, 228, 214), "calca": (226, 222, 208), "chapeu": "aba_larga", "cor_chapeu": (228, 222, 204), "gravata": True},
    "baiana":     {"roupa": (246, 244, 238), "calca": (246, 244, 238), "chapeu": "turbante", "cor_chapeu": (248, 248, 244), "comprido": True, "colar": True, "pele_padrao": "negra"},
    "indigena":   {"roupa": (150, 104, 66), "calca": (150, 104, 66), "chapeu": "cocar", "pele_padrao": "parda", "colar": True},
    # --- mundo
    "cowboy":     {"roupa": (160, 62, 52), "calca": (62, 84, 126), "chapeu": "cowboy", "cor_chapeu": (156, 108, 62), "lenco_cor": (40, 60, 120)},
    "americano":  {"roupa": (112, 108, 76), "calca": (98, 94, 66), "chapeu": "capacete", "cor_chapeu": (96, 98, 64), "acessorio": "fuzil", "insignia": "Estados Unidos"},
    "sovietico":  {"roupa": (128, 116, 78), "calca": (92, 84, 60), "chapeu": "pilotka", "cor_chapeu": (120, 108, 72), "acessorio": "fuzil", "insignia": "arquivo:Flag of the Soviet Union"},
    "romano":     {"roupa": (176, 40, 40), "calca": None, "chapeu": "elmo_romano", "cor_chapeu": (196, 196, 204), "acessorio": "lanca", "escudo": (176, 40, 40)},
    "viking":     {"roupa": (112, 92, 70), "calca": (86, 70, 54), "chapeu": "elmo_viking", "cor_chapeu": (150, 152, 158), "acessorio": "machado", "barba": True, "escudo": (60, 90, 140)},
    "farao":      {"roupa": (242, 234, 206), "calca": None, "chapeu": "nemes", "cor_chapeu": (226, 186, 70), "comprido": True, "colar": True, "pele_padrao": "morena"},
    "samurai":    {"roupa": (150, 32, 40), "calca": (40, 36, 40), "chapeu": "kabuto", "cor_chapeu": (40, 36, 40), "acessorio": "espada"},
    "cavaleiro":  {"roupa": (172, 176, 184), "calca": (150, 154, 162), "chapeu": "elmo_cavaleiro", "cor_chapeu": (176, 180, 188), "acessorio": "espada", "escudo": (236, 236, 236), "pele_padrao": "clara"},
    "pirata":     {"roupa": (204, 194, 172), "calca": (60, 50, 44), "chapeu": "tricornio", "cor_chapeu": (32, 30, 32), "acessorio": "espada", "tapa_olho": True, "faixa": (170, 30, 40)},
    "mongol":     {"roupa": (60, 112, 142), "calca": (70, 56, 44), "chapeu": "mongol", "cor_chapeu": (150, 40, 40), "acessorio": "lanca", "faixa": (226, 186, 70)},
    "princesa":   {"roupa": (226, 120, 170), "calca": (226, 120, 170), "chapeu": "tiara", "cor_chapeu": (236, 196, 70), "comprido": True, "cabelo": "longo", "colar": True},
    "rainha":     {"roupa": (120, 30, 60), "calca": (120, 30, 60), "chapeu": "coroa", "cor_chapeu": (236, 192, 62), "comprido": True, "cabelo": "longo", "colar": True},
    "rei":        {"roupa": (150, 30, 40), "calca": (236, 232, 220), "chapeu": "coroa", "cor_chapeu": (236, 192, 62), "faixa": (236, 192, 62), "barba": True},
    "medico_guerra": {"roupa": (112, 112, 80), "calca": (98, 96, 70), "chapeu": "capacete_medico", "cor_chapeu": (236, 236, 230), "braçadeira": True},
    "enfermeira": {"roupa": (236, 236, 240), "calca": (236, 236, 240), "chapeu": "touca_enfermeira", "cor_chapeu": (248, 248, 248), "comprido": True, "braçadeira": True},
    "freira":     {"roupa": (30, 30, 34), "calca": (30, 30, 34), "chapeu": "veu", "cor_chapeu": (30, 30, 34), "comprido": True, "colarinho": True},
    "monge":      {"roupa": (126, 92, 60), "calca": (126, 92, 60), "chapeu": "capuz", "cor_chapeu": (116, 84, 54), "comprido": True},
    "nativo_americano": {"roupa": (176, 132, 86), "calca": (150, 110, 70), "chapeu": "faixa_pena", "cor_chapeu": (176, 50, 40), "colar": True, "pele_padrao": "parda"},
    "explorador": {"roupa": (196, 178, 132), "calca": (150, 132, 96), "chapeu": "safari", "cor_chapeu": (214, 198, 150)},
    "aviador":    {"roupa": (110, 76, 50), "calca": (90, 80, 66), "chapeu": "gorro_aviador", "cor_chapeu": (100, 70, 46), "lenco_cor": (240, 240, 236)},
    "cientista":  {"roupa": (244, 244, 246), "calca": (70, 70, 80), "chapeu": "", "oculos": True, "gravata": True},
    "astronauta": {"roupa": (236, 236, 236), "calca": (226, 226, 226), "chapeu": "astronauta", "cor_chapeu": (236, 236, 236)},
    "operario":   {"roupa": (60, 90, 140), "calca": (54, 62, 90), "chapeu": "capacete_obra", "cor_chapeu": (240, 196, 40)},
    "campones":   {"roupa": (150, 126, 90), "calca": (110, 92, 68), "chapeu": "touca", "cor_chapeu": (140, 60, 50)},
    "mago":       {"roupa": (60, 50, 140), "calca": (60, 50, 140), "chapeu": "mago", "cor_chapeu": (60, 50, 140), "comprido": True, "barba": True},
    # --- Brasil (mais)
    "jesuita":    {"roupa": (30, 28, 30), "calca": (30, 28, 30), "chapeu": "aba_larga", "cor_chapeu": (30, 28, 30), "comprido": True, "colarinho": True},
    "seringueiro": {"roupa": (170, 150, 110), "calca": (110, 96, 72), "chapeu": "aba_larga", "cor_chapeu": (150, 120, 80)},
    "garimpeiro": {"roupa": (160, 120, 80), "calca": (100, 84, 64), "chapeu": "palha", "cor_chapeu": (200, 170, 100)},
    "jangadeiro": {"roupa": (236, 230, 214), "calca": (180, 160, 120), "chapeu": "palha", "cor_chapeu": (226, 196, 120), "pele_padrao": "parda"},
    "pescador":   {"roupa": (60, 110, 150), "calca": (200, 180, 140), "chapeu": "palha", "cor_chapeu": (214, 182, 110)},
    "imigrante_italiano": {"roupa": (236, 232, 220), "calca": (80, 70, 60), "chapeu": "boina", "cor_chapeu": (70, 60, 52), "lenco_cor": (180, 30, 40), "pele_padrao": "clara"},
    "imigrante_japones": {"roupa": (50, 70, 120), "calca": (60, 60, 64), "chapeu": "conico", "cor_chapeu": (214, 190, 130), "pele_padrao": "clara"},
    "presidente": {"roupa": (40, 40, 46), "calca": (38, 38, 42), "chapeu": "", "gravata": True, "faixa": (40, 150, 70)},
    "revolucionario": {"roupa": (96, 104, 70), "calca": (80, 86, 58), "chapeu": "boina", "cor_chapeu": (40, 40, 40), "barba": True, "acessorio": "fuzil"},
    "capoeirista": {"roupa": (236, 236, 236), "calca": (246, 246, 246), "chapeu": "", "pele_padrao": "negra", "faixa": (226, 186, 70)},
    # --- mundo (mais)
    "napoleao":   {"roupa": (30, 50, 120), "calca": (236, 232, 220), "chapeu": "bicorne", "cor_chapeu": (24, 24, 28), "dragona": True, "pele_padrao": "clara"},
    "soldado_britanico": {"roupa": (180, 30, 36), "calca": (40, 40, 60), "chapeu": "quepe", "cor_chapeu": (30, 30, 40), "acessorio": "fuzil", "cruz": True, "pele_padrao": "clara"},
    "soldado_frances": {"roupa": (90, 110, 160), "calca": (150, 40, 40), "chapeu": "capacete_aba", "cor_chapeu": (100, 116, 150), "acessorio": "fuzil", "pele_padrao": "clara"},
    "gladiador":  {"roupa": (140, 110, 70), "calca": None, "chapeu": "elmo_romano", "cor_chapeu": (180, 150, 70), "acessorio": "espada", "escudo": (150, 40, 40)},
    "espartano":  {"roupa": (170, 40, 36), "calca": None, "chapeu": "elmo_grego", "cor_chapeu": (196, 150, 60), "acessorio": "lanca", "escudo": (196, 150, 60)},
    "cruzado":    {"roupa": (236, 236, 236), "calca": (150, 154, 162), "chapeu": "elmo_cavaleiro", "cor_chapeu": (176, 180, 188), "acessorio": "espada", "escudo": (236, 236, 236), "cruz_peito": True, "pele_padrao": "clara"},
    "beduino":    {"roupa": (236, 228, 206), "calca": (236, 228, 206), "chapeu": "turbante", "cor_chapeu": (200, 60, 50), "comprido": True, "pele_padrao": "morena"},
    "chines_imperial": {"roupa": (200, 40, 40), "calca": (200, 40, 40), "chapeu": "chapeu_chines", "cor_chapeu": (30, 30, 34), "comprido": True, "faixa": (236, 192, 62), "pele_padrao": "clara"},
    "campones_asiatico": {"roupa": (80, 110, 150), "calca": (60, 70, 90), "chapeu": "conico", "cor_chapeu": (214, 190, 130), "pele_padrao": "clara"},
    "maharaja":   {"roupa": (236, 192, 62), "calca": (236, 236, 236), "chapeu": "turbante", "cor_chapeu": (190, 40, 80), "colar": True, "pele_padrao": "morena"},
    "rei_africano": {"roupa": (226, 150, 40), "calca": (40, 120, 70), "chapeu": "coroa", "cor_chapeu": (236, 192, 62), "colar": True, "faixa": (180, 40, 40), "pele_padrao": "negra"},
    "rainha_egipcia": {"roupa": (242, 234, 206), "calca": None, "chapeu": "nemes", "cor_chapeu": (226, 186, 70), "comprido": True, "colar": True, "cabelo": "longo", "pele_padrao": "morena"},
    "filosofo":   {"roupa": (240, 238, 228), "calca": None, "chapeu": "", "comprido": True, "barba": True, "faixa": (60, 90, 150), "pele_padrao": "clara"},
    "inventor":   {"roupa": (110, 76, 50), "calca": (60, 60, 64), "chapeu": "", "oculos": True, "gravata": True},
    "detetive":   {"roupa": (150, 120, 84), "calca": (90, 80, 70), "chapeu": "fedora", "cor_chapeu": (120, 96, 66)},
    "gangster":   {"roupa": (40, 40, 46), "calca": (40, 40, 46), "chapeu": "fedora", "cor_chapeu": (36, 36, 40), "gravata": True},
    "policial":   {"roupa": (40, 60, 120), "calca": (30, 40, 80), "chapeu": "quepe", "cor_chapeu": (30, 40, 80)},
    "bombeiro":   {"roupa": (60, 60, 64), "calca": (60, 60, 64), "chapeu": "capacete_bombeiro", "cor_chapeu": (200, 40, 40)},
    "mineiro_carvao": {"roupa": (70, 70, 74), "calca": (60, 56, 52), "chapeu": "capacete_obra", "cor_chapeu": (230, 200, 60)},
    "lenhador":   {"roupa": (180, 40, 40), "calca": (60, 80, 120), "chapeu": "touca", "cor_chapeu": (60, 60, 64), "barba": True, "acessorio": "machado"},
    # --- Forcas Armadas do Brasil (com distintivo da bandeira no braco)
    "exercito_br": {"roupa": (96, 108, 66), "calca": (90, 100, 60), "chapeu": "capacete", "cor_chapeu": (86, 98, 58), "acessorio": "fuzil", "camuflado": True, "insignia": "Brasil"},
    "marinha_br":  {"roupa": (244, 244, 246), "calca": (244, 244, 246), "chapeu": "quepe", "cor_chapeu": (246, 246, 248), "dragona": True, "insignia": "Brasil"},
    "fuzileiro_naval": {"roupa": (70, 90, 120), "calca": (60, 78, 104), "chapeu": "boina", "cor_chapeu": (180, 30, 40), "acessorio": "fuzil", "camuflado": True, "insignia": "Brasil"},
    "aeronautica_br": {"roupa": (70, 100, 150), "calca": (60, 86, 130), "chapeu": "quepe", "cor_chapeu": (60, 86, 130), "gravata": True, "insignia": "Brasil"},
    "piloto_fab":  {"roupa": (100, 110, 80), "calca": (100, 110, 80), "chapeu": "gorro_aviador", "cor_chapeu": (90, 96, 70), "insignia": "Brasil"},
    "general":     {"roupa": (86, 100, 64), "calca": (80, 92, 60), "chapeu": "quepe", "cor_chapeu": (80, 92, 60), "medalhas": True, "dragona": True, "insignia": "Brasil"},
    "policia_militar": {"roupa": (110, 116, 126), "calca": (60, 64, 72), "chapeu": "quepe", "cor_chapeu": (40, 50, 80), "insignia": "Brasil"},
    "soldado_paraguai": {"roupa": (40, 60, 120), "calca": (236, 232, 220), "chapeu": "quepe", "cor_chapeu": (40, 50, 90), "acessorio": "fuzil", "cruz": True},
    "soldado_1932": {"roupa": (120, 104, 72), "calca": (110, 96, 66), "chapeu": "capacete_aba", "cor_chapeu": (100, 96, 76), "acessorio": "fuzil", "insignia": "São Paulo"},
    "soldado_portugues": {"roupa": (40, 60, 130), "calca": (236, 232, 220), "chapeu": "tricornio", "cor_chapeu": (30, 30, 34), "acessorio": "fuzil", "cruz": True, "pele_padrao": "clara"},
    # --- Forcas estrangeiras (bandeira do pais no braco; historicas usam "arquivo:")
    "soldado_argentino": {"roupa": (60, 100, 170), "calca": (236, 232, 220), "chapeu": "quepe", "cor_chapeu": (40, 60, 110), "acessorio": "fuzil", "insignia": "Argentina"},
    "soldado_paraguaio": {"roupa": (180, 40, 40), "calca": (236, 232, 220), "chapeu": "quepe", "cor_chapeu": (40, 40, 60), "acessorio": "fuzil", "insignia": "Paraguai"},
    "soldado_uruguaio": {"roupa": (50, 70, 130), "calca": (236, 232, 220), "chapeu": "quepe", "cor_chapeu": (40, 50, 90), "acessorio": "fuzil", "insignia": "Uruguai"},
    "marine_eua":  {"roupa": (150, 130, 96), "calca": (130, 112, 82), "chapeu": "capacete", "cor_chapeu": (120, 104, 76), "acessorio": "fuzil", "camuflado": True, "insignia": "Estados Unidos"},
    "marinha_eua": {"roupa": (240, 240, 244), "calca": (30, 40, 80), "chapeu": "marinheiro", "cor_chapeu": (244, 244, 248), "lenco": True, "insignia": "Estados Unidos"},
    "soldado_uniao": {"roupa": (40, 56, 110), "calca": (100, 130, 170), "chapeu": "quepe", "cor_chapeu": (36, 48, 96), "acessorio": "fuzil", "insignia": "arquivo:Flag of the United States (1863-1865)"},
    "soldado_confederado": {"roupa": (150, 150, 150), "calca": (130, 130, 130), "chapeu": "quepe", "cor_chapeu": (120, 120, 120), "acessorio": "fuzil"},
    "alemao_ww1":  {"roupa": (110, 116, 100), "calca": (90, 96, 84), "chapeu": "pickelhaube", "cor_chapeu": (40, 40, 40), "acessorio": "fuzil", "insignia": "arquivo:Flag of the German Empire"},
    "japones_ww2": {"roupa": (150, 140, 90), "calca": (130, 120, 78), "chapeu": "quepe", "cor_chapeu": (130, 120, 78), "acessorio": "fuzil", "insignia": "Japão", "pele_padrao": "clara"},
    "italiano_ww2": {"roupa": (140, 130, 100), "calca": (120, 112, 86), "chapeu": "capacete_aba", "cor_chapeu": (120, 112, 86), "acessorio": "fuzil", "insignia": "arquivo:Flag of Italy (1861-1946)", "pele_padrao": "clara"},
    "britanico_ww2": {"roupa": (130, 116, 80), "calca": (116, 104, 72), "chapeu": "capacete_aba", "cor_chapeu": (110, 104, 74), "acessorio": "fuzil", "insignia": "Reino Unido", "pele_padrao": "clara"},
    "frances_ww2": {"roupa": (126, 120, 86), "calca": (110, 104, 76), "chapeu": "capacete_aba", "cor_chapeu": (100, 106, 96), "acessorio": "fuzil", "insignia": "França", "pele_padrao": "clara"},
    "chines_soldado": {"roupa": (96, 116, 70), "calca": (86, 104, 62), "chapeu": "quepe", "cor_chapeu": (86, 104, 62), "acessorio": "fuzil", "insignia": "China", "pele_padrao": "clara"},
    "conquistador": {"roupa": (170, 172, 180), "calca": (130, 40, 40), "chapeu": "morion", "cor_chapeu": (186, 188, 196), "acessorio": "espada", "barba": True, "insignia": "arquivo:Flag of Cross of Burgundy", "pele_padrao": "clara"},
    "holandes_1630": {"roupa": (40, 40, 44), "calca": (40, 40, 44), "chapeu": "aba_larga", "cor_chapeu": (30, 30, 32), "acessorio": "espada", "colarinho": True, "insignia": "arquivo:Flag of the Dutch East India Company", "pele_padrao": "clara"},
    "otomano":     {"roupa": (40, 80, 140), "calca": (200, 40, 40), "chapeu": "fez", "cor_chapeu": (190, 30, 40), "acessorio": "espada", "insignia": "arquivo:Flag of the Ottoman Empire (1844-1922)"},
    "revolucionario_mexicano": {"roupa": (236, 230, 214), "calca": (120, 96, 66), "chapeu": "sombrero", "cor_chapeu": (210, 180, 110), "acessorio": "fuzil", "cartucheira": True, "insignia": "México", "pele_padrao": "morena"},
    "soldado_russo": {"roupa": (100, 110, 80), "calca": (90, 100, 70), "chapeu": "capacete", "cor_chapeu": (90, 100, 70), "acessorio": "fuzil", "camuflado": True, "insignia": "Rússia", "pele_padrao": "clara"},
    # --- Lideres da 2a Guerra (reconheciveis pelo visual da epoca; SEM simbolos nazistas)
    "lider_alemao": {"roupa": (150, 120, 80), "calca": (40, 40, 44), "chapeu": "", "bigode": "escovinha", "cabelo_tipo": "lado", "pele_padrao": "clara"},
    "lider_sovietico": {"roupa": (170, 160, 130), "calca": (150, 140, 110), "chapeu": "", "bigode": "grosso", "cabelo_tipo": "tras", "pele_padrao": "clara"},
    "lider_britanico": {"roupa": (40, 40, 46), "calca": (40, 40, 46), "chapeu": "", "careca": True, "charuto": True, "gravata_borboleta": True, "pele_padrao": "clara"},
    "lider_italiano": {"roupa": (24, 24, 26), "calca": (24, 24, 26), "chapeu": "", "careca": True, "dragona": True, "pele_padrao": "clara"},
    "lider_americano": {"roupa": (60, 60, 70), "calca": (60, 60, 70), "chapeu": "", "oculos": True, "gravata": True, "pele_padrao": "clara"},
    "lider_japones": {"roupa": (110, 104, 70), "calca": (100, 96, 64), "chapeu": "quepe", "cor_chapeu": (100, 96, 64), "oculos": True, "bigode": "fino", "pele_padrao": "clara"},
    # --- povos originarios e outras culturas (com respeito, sem caricatura)
    "guerreiro_africano": {"roupa": (190, 120, 50), "calca": (120, 70, 40), "chapeu": "", "acessorio": "lanca", "escudo": (236, 230, 214), "colar": True, "pele_padrao": "negra"},
    "rainha_africana": {"roupa": (200, 120, 30), "calca": (40, 110, 70), "chapeu": "turbante", "cor_chapeu": (40, 110, 70), "comprido": True, "colar": True, "pele_padrao": "negra"},
    "inca":        {"roupa": (200, 60, 50), "calca": (230, 190, 70), "chapeu": "llauto", "cor_chapeu": (226, 186, 70), "colar": True, "pele_padrao": "parda"},
    "asteca":      {"roupa": (60, 140, 120), "calca": (226, 186, 70), "chapeu": "cocar", "acessorio": "lanca", "escudo": (226, 186, 70), "pele_padrao": "parda"},
    "chefe_nativo": {"roupa": (176, 132, 86), "calca": (150, 110, 70), "chapeu": "cocar", "colar": True, "pele_padrao": "parda"},
    "inuit":       {"roupa": (200, 186, 160), "calca": (150, 130, 100), "chapeu": "capuz_pele", "cor_chapeu": (200, 186, 160), "pele_padrao": "morena"},
    "sultao":     {"roupa": (110, 40, 120), "calca": (110, 40, 120), "chapeu": "turbante", "cor_chapeu": (246, 244, 236), "comprido": True, "faixa": (226, 186, 70), "pele_padrao": "morena"},
}


def _cor(rgb, a=255):
    return skia.ColorSetARGB(a, *rgb)


def _fill(rgb, a=255):
    return skia.Paint(Color=_cor(rgb, a), AntiAlias=True)


def _linha(lw, cor=None):
    return skia.Paint(Color=cor if cor is not None else TINTA, AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=lw,
                      StrokeJoin=skia.Paint.kRound_Join, StrokeCap=skia.Paint.kRound_Cap)


def _forma(c, path, rgb, lw, flag=None, sombra=True):
    """Preenche (cor ou bandeira recortada), sombra interna suave e contorno."""
    if flag is not None:
        c.save(); c.clipPath(path, doAntiAlias=True)
        b = path.getBounds()
        esc = max(b.width() / flag.width(), b.height() / flag.height())
        w, h = flag.width() * esc, flag.height() * esc
        c.drawImageRect(flag, skia.Rect.MakeXYWH(b.centerX() - w / 2, b.centerY() - h / 2, w, h), skia.SamplingOptions(skia.FilterMode.kLinear))
        c.restore()
    else:
        c.drawPath(path, _fill(rgb))
    if sombra:  # sombra do lado direito (luz vem da esquerda)
        c.save(); c.clipPath(path, doAntiAlias=True)
        b = path.getBounds()
        c.drawRect(skia.Rect.MakeLTRB(b.centerX() + b.width() * 0.18, b.top(), b.right(), b.bottom()), _fill((0, 0, 0), 34))
        c.restore()
    c.drawPath(path, _linha(lw))


def _rrect_path(x, y, w, h, r):
    p = skia.Path(); p.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r)); return p


def _braco(c, ox, oy, ang, comp, larg, roupa, pele, lw, aponta=False):
    x2, y2 = ox + math.cos(ang) * comp, oy + math.sin(ang) * comp
    p = skia.Path(); p.moveTo(ox, oy); p.lineTo(x2, y2)
    c.drawPath(p, skia.Paint(Color=TINTA, AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=larg + lw * 2, StrokeCap=skia.Paint.kRound_Cap))
    c.drawPath(p, skia.Paint(Color=_cor(roupa), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=larg, StrokeCap=skia.Paint.kRound_Cap))
    m = larg * 0.62
    if aponta:
        # mao apontando SEM ambiguidade: punho grande + polegar por cima + indicador curto e grosso,
        # sempre na horizontal ou levemente para baixo (nunca para cima)
        a_dedo = min(max(ang, 0.0), 0.35)
        dx, dy = math.cos(a_dedo), math.sin(a_dedo)
        punho = m * 1.15
        dedo = skia.Path(); dedo.moveTo(x2, y2); dedo.lineTo(x2 + dx * punho * 1.55, y2 + dy * punho * 1.55)
        c.drawPath(dedo, skia.Paint(Color=TINTA, AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=punho * 0.95 + lw * 2, StrokeCap=skia.Paint.kRound_Cap))
        c.drawPath(dedo, skia.Paint(Color=_cor(pele), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=punho * 0.95, StrokeCap=skia.Paint.kRound_Cap))
        c.drawCircle(x2, y2, punho, _fill(pele)); c.drawCircle(x2, y2, punho, _linha(lw))
        # polegar: bolinha encostada em cima do punho
        px_, py_ = x2 + dx * punho * 0.35 - dy * punho * 0.75, y2 + dy * punho * 0.35 - dx * punho * 0.75
        c.drawCircle(px_, py_, punho * 0.42, _fill(pele)); c.drawCircle(px_, py_, punho * 0.42, _linha(lw * 0.8))
        # dobras dos outros dedos (deixa claro que estao fechados)
        for k in (-0.35, 0.05):
            c.drawLine(x2 - dy * punho * k - dx * punho * 0.2, y2 + dx * punho * k - dy * punho * 0.2,
                       x2 - dy * punho * k + dx * punho * 0.25, y2 + dx * punho * k + dy * punho * 0.25, _linha(lw * 0.6))
        return x2, y2
    c.drawCircle(x2, y2, m, _fill(pele)); c.drawCircle(x2, y2, m, _linha(lw))
    return x2, y2

def tipo_valido(nome):
    """Aceita nomes parecidos da IA ('portugues' -> 'soldado_portugues', 'holandes' -> 'holandes_1630')."""
    try:
        from unidecode import unidecode
        nome = unidecode(str(nome or ""))
    except Exception:
        pass
    n = str(nome or "").strip().lower().replace(" ", "_").replace("-", "_")
    n = "_".join(w for w in n.split("_") if w and w not in ("de", "da", "do", "das", "dos", "e", "o", "a"))
    if n in FIGURINOS:
        return n
    candidatos = [k for k in FIGURINOS if n and (n in k or k in n)]
    if candidatos:
        return max(candidatos, key=len)  # o mais especifico ("soldado_portugues" antes de "soldado")
    return "povo"


def desenhar(c, pers, x, y, altura, t, semente=0, flag_fn=None):
    """Desenha o bonequinho com os PES em (x, y). t = segundos desde a entrada. flag_fn(nome) -> skia.Image da bandeira."""
    tipo = tipo_valido(pers.get("tipo"))
    fig = FIGURINOS[tipo]
    h = altura * fig.get("escala", 1.0)
    r = h * 0.30                                  # cabecao
    lw = max(2.2, h * 0.026)
    nome_pele = pers.get("pele") if pers.get("pele") in PELES else (fig.get("pele_padrao") or ("clara" if tipo in ("alemao", "imperador") else ORDEM_PELE[semente % 4]))
    pele = PELES[nome_pele]
    cabelo = CABELOS[(semente // 3) % len(CABELOS)] if tipo != "politico" else (150, 146, 140)
    pose, expr = pers.get("pose", "parado"), pers.get("expressao", "normal")
    if pose == "assustado":
        expr = "assustado"
    flag = None
    roupa_cfg = str(pers.get("roupa") or "")
    if roupa_cfg.startswith("bandeira:") and flag_fn:
        flag = flag_fn(roupa_cfg.split(":", 1)[1])
    olha = -1 if pers.get("olha") == "esq" else 1

    resp = math.sin(t * 3.0 + semente) * h * 0.012
    pulo = abs(math.sin(t * 6.5)) * h * 0.07 if pose == "comemora" else 0
    tremor = math.sin(t * 40) * h * 0.006 if pose == "assustado" else 0
    passo = math.sin(t * 9.0) if pose == "anda" else 0
    c.save(); c.translate(x + tremor, y - pulo); c.scale(olha, 1)

    c.drawOval(skia.Rect.MakeXYWH(-h * 0.24, -h * 0.03, h * 0.48, h * 0.065), _fill((0, 0, 0), 80))   # sombra no chao
    # pernas e botas
    perna_h, perna_w = h * 0.16, h * 0.1
    for lado, fase in ((-1, passo), (1, -passo)):
        rx = lado * h * 0.085 + fase * h * 0.05
        if not fig.get("comprido"):
            _forma(c, _rrect_path(rx - perna_w / 2, -perna_h, perna_w, perna_h, perna_w * 0.3), fig["calca"] or pele, lw, sombra=False)
        _forma(c, _rrect_path(rx - perna_w * 0.72, -h * 0.05, perna_w * 1.5, h * 0.055, h * 0.022), (54, 40, 32), lw, sombra=False)
    # tronco: "tunica" levemente trapezoidal (ou vestido/batina comprida)
    topo = -perna_h - h * 0.3 + resp
    base = -h * 0.04 if fig.get("comprido") else -perna_h + h * 0.02
    meia_t, meia_b = h * 0.17, h * (0.23 if fig.get("comprido") else 0.2)
    tron = skia.Path()
    tron.moveTo(-meia_t, topo + h * 0.03); tron.quadTo(-meia_t, topo, -meia_t + h * 0.04, topo)
    tron.lineTo(meia_t - h * 0.04, topo); tron.quadTo(meia_t, topo, meia_t, topo + h * 0.03)
    tron.lineTo(meia_b, base); tron.lineTo(-meia_b, base); tron.close()
    _forma(c, tron, fig["roupa"], lw, flag=flag)
    if flag is None:
        if fig.get("faixa"):
            f = skia.Path(); f.moveTo(-meia_t + h * 0.02, topo + h * 0.02); f.lineTo(meia_b - h * 0.03, base - h * 0.02)
            c.drawPath(f, skia.Paint(Color=_cor(fig["faixa"]), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=h * 0.04))
        if fig.get("cruz"):  # correias cruzadas do soldado
            for a, b_ in ((-1, 1), (1, -1)):
                q = skia.Path(); q.moveTo(a * meia_t * 0.8, topo + h * 0.02); q.lineTo(b_ * meia_b * 0.75, base - h * 0.03)
                c.drawPath(q, skia.Paint(Color=_cor((240, 236, 226)), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=h * 0.03))
        if fig.get("gravata"):
            g = skia.Path(); g.moveTo(0, topo + h * 0.01); g.lineTo(h * 0.028, topo + h * 0.15); g.lineTo(0, topo + h * 0.19); g.lineTo(-h * 0.028, topo + h * 0.15); g.close()
            _forma(c, g, (176, 30, 40), lw * 0.6, sombra=False)
        if fig.get("colarinho"):
            c.drawRect(skia.Rect.MakeXYWH(-h * 0.035, topo, h * 0.07, h * 0.03), _fill((246, 246, 246)))
        if fig.get("lenco"):
            l = skia.Path(); l.moveTo(-h * 0.1, topo); l.lineTo(h * 0.1, topo); l.lineTo(0, topo + h * 0.12); l.close()
            _forma(c, l, (40, 60, 112), lw * 0.6, sombra=False)
        if fig.get("distintivo"):  # distintivo PROPRIO do canal: escudo dourado com estrela
            e = skia.Path(); cx_, cy_, s = -h * 0.09, topo + h * 0.09, h * 0.05
            e.moveTo(cx_ - s, cy_ - s); e.lineTo(cx_ + s, cy_ - s); e.lineTo(cx_ + s, cy_ + s * 0.3); e.lineTo(cx_, cy_ + s * 1.2); e.lineTo(cx_ - s, cy_ + s * 0.3); e.close()
            _forma(c, e, (226, 186, 70), lw * 0.6, sombra=False)
            c.drawCircle(cx_, cy_, s * 0.32, _fill((170, 40, 40)))
    if fig.get("dragona"):
        for lado in (-1, 1):
            _forma(c, _rrect_path(lado * meia_t - h * 0.055, topo - h * 0.015, h * 0.11, h * 0.045, h * 0.02), (236, 192, 62), lw * 0.7, sombra=False)
    if fig.get("acessorio") == "fuzil" and pose not in ("bracos_cima", "comemora", "assustado"):
        fz = skia.Path(); fz.moveTo(-meia_t - h * 0.02, base - h * 0.02); fz.lineTo(-meia_t + h * 0.06, topo - h * 0.22)
        c.drawPath(fz, skia.Paint(Color=TINTA, AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=h * 0.04, StrokeCap=skia.Paint.kRound_Cap))
        c.drawPath(fz, skia.Paint(Color=_cor((112, 78, 46)), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=h * 0.022, StrokeCap=skia.Paint.kRound_Cap))
    if fig.get("cartucheira") and flag is None:  # cartucheiras cruzadas do cangaceiro
        for a_, b_ in ((-1, 1), (1, -1)):
            q = skia.Path(); q.moveTo(a_ * meia_t * 0.85, topo + h * 0.02); q.lineTo(b_ * meia_b * 0.8, base - h * 0.02)
            c.drawPath(q, skia.Paint(Color=_cor((88, 58, 34)), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=h * 0.045))
            med = skia.PathMeasure(q, False); L = med.getLength()
            for k in range(1, 7):
                pt_ = med.getPosTan(L * k / 7)
                if pt_:
                    c.drawCircle(pt_[0].x(), pt_[0].y(), h * 0.011, _fill((226, 190, 80)))
    if fig.get("camuflado") and flag is None:  # manchas de camuflagem dentro da tunica
        c.save(); c.clipPath(tron, doAntiAlias=True)
        base_c = fig["roupa"]
        for k in range(14):
            mx = -meia_b + ((k * 37) % 100) / 100 * meia_b * 2
            my = topo + ((k * 53) % 100) / 100 * (base - topo)
            tom = tuple(max(0, min(255, v + (-34 if k % 2 else 26))) for v in base_c)
            c.drawOval(skia.Rect.MakeXYWH(mx - h * 0.05, my - h * 0.03, h * 0.1 + (k % 3) * h * 0.03, h * 0.06), _fill(tom))
        c.restore(); c.drawPath(tron, _linha(lw))
    if fig.get("medalhas") and flag is None:
        for k in range(4):
            mx = -h * 0.12 + k * h * 0.045
            c.drawRect(skia.Rect.MakeXYWH(mx - h * 0.015, topo + h * 0.05, h * 0.03, h * 0.025), _fill(((200, 40, 40), (40, 120, 70), (40, 80, 160), (236, 192, 62))[k]))
            c.drawCircle(mx, topo + h * 0.095, h * 0.014, _fill((236, 192, 62)))
    if fig.get("cruz_peito") and flag is None:
        c.drawRect(skia.Rect.MakeXYWH(-h * 0.025, topo + h * 0.04, h * 0.05, h * 0.2), _fill((200, 30, 40)))
        c.drawRect(skia.Rect.MakeXYWH(-h * 0.09, topo + h * 0.09, h * 0.18, h * 0.05), _fill((200, 30, 40)))
    if fig.get("braçadeira") and flag is None:  # cruz vermelha no braco/peito
        bx, by = h * 0.06, topo + h * 0.1
        c.drawCircle(bx, by, h * 0.045, _fill((250, 250, 250))); c.drawCircle(bx, by, h * 0.045, _linha(lw * 0.6))
        c.drawRect(skia.Rect.MakeXYWH(bx - h * 0.01, by - h * 0.03, h * 0.02, h * 0.06), _fill((210, 30, 40)))
        c.drawRect(skia.Rect.MakeXYWH(bx - h * 0.03, by - h * 0.01, h * 0.06, h * 0.02), _fill((210, 30, 40)))
    if fig.get("lenco_cor"):
        l = skia.Path(); l.moveTo(-h * 0.11, topo); l.lineTo(h * 0.11, topo); l.lineTo(0, topo + h * 0.1); l.close()
        _forma(c, l, fig["lenco_cor"], lw * 0.6, sombra=False)
    if fig.get("colar"):
        for k in range(7):
            ang = math.pi * (0.15 + 0.7 * k / 6)
            c.drawCircle(math.cos(ang) * h * 0.1, topo + math.sin(ang) * h * 0.06, h * 0.014, _fill((214, 60, 50) if k % 2 else (236, 196, 70)))
    if fig.get("escudo") and pose not in ("bracos_cima", "comemora", "assustado"):
        e = skia.Path(); e.addOval(skia.Rect.MakeXYWH(-meia_t - h * 0.17, topo + h * 0.02, h * 0.2, h * 0.26))
        _forma(c, e, fig["escudo"], lw)
        c.drawCircle(-meia_t - h * 0.07, topo + h * 0.15, h * 0.03, _fill((226, 186, 70)))
    if fig.get("acessorio") in ("espada", "machado") and pose not in ("bracos_cima", "comemora", "assustado"):
        cab_ = skia.Path(); cab_.moveTo(meia_b * 0.9, base); cab_.lineTo(meia_b * 0.9 + h * 0.05, topo - h * 0.12)
        c.drawPath(cab_, _linha(h * 0.022, _cor((210, 212, 218) if fig["acessorio"] == "espada" else (120, 88, 52))))
        if fig["acessorio"] == "machado":
            mx, my = meia_b * 0.9 + h * 0.05, topo - h * 0.12
            lam = skia.Path(); lam.moveTo(mx, my); lam.lineTo(mx + h * 0.09, my - h * 0.04); lam.lineTo(mx + h * 0.09, my + h * 0.08); lam.close()
            _forma(c, lam, (200, 202, 208), lw * 0.6, sombra=False)
    if fig.get("acessorio") == "lanca":
        ln = skia.Path(); ln.moveTo(-meia_t - h * 0.05, -h * 0.02); ln.lineTo(-meia_t - h * 0.05, topo - h * 0.4)
        c.drawPath(ln, _linha(h * 0.02, _cor((120, 88, 52))))
        pt = skia.Path(); px_, py_ = -meia_t - h * 0.05, topo - h * 0.4
        pt.moveTo(px_, py_ - h * 0.07); pt.lineTo(px_ + h * 0.025, py_); pt.lineTo(px_ - h * 0.025, py_); pt.close()
        _forma(c, pt, (200, 200, 205), lw * 0.5, sombra=False)

    # bracos (angulo 0 = para frente/direita, pi/2 = para baixo)
    ombro = topo + h * 0.06
    onda = math.sin(t * 5 + semente) * 0.16
    angs = {"parado": (math.pi * 0.64, math.pi * 0.36), "triste": (math.pi * 0.6, math.pi * 0.42),
            "aponta": (math.pi * 0.64, 0.08 + abs(onda) * 0.12), "bracos_cima": (-math.pi * 0.64 + onda, -math.pi * 0.36 - onda),
            "comemora": (-math.pi * 0.72 + onda, -math.pi * 0.28 - onda), "anda": (math.pi * 0.5 + passo * 0.45, math.pi * 0.5 - passo * 0.45),
            "assustado": (-math.pi * 0.78, -math.pi * 0.22)}
    a1, a2 = angs.get(pose, angs["parado"])
    comp, larg = h * (0.27 if pose == "aponta" else 0.22), h * 0.085
    roupa_braco = fig["roupa"] if flag is None else (230, 230, 230)
    _braco(c, -meia_t + h * 0.01, ombro, a1, h * 0.22, larg, roupa_braco, pele, lw)
    _braco(c, meia_t - h * 0.01, ombro, a2, comp, larg, roupa_braco, pele, lw, aponta=(pose == "aponta"))

    # distintivo com a bandeira (do figurino ou pedido: "insignia": "Japão")
    ins = pers.get("insignia") or fig.get("insignia")
    if ins and flag_fn and flag is None:
        fi = flag_fn(ins)
        if fi is not None:
            iw, ih_ = h * 0.11, h * 0.075
            ix, iy = -meia_t - h * 0.035, ombro + h * 0.02
            c.drawImageRect(fi, skia.Rect.MakeXYWH(ix, iy, iw, ih_), skia.SamplingOptions(skia.FilterMode.kLinear))
            c.drawRect(skia.Rect.MakeXYWH(ix, iy, iw, ih_), _linha(lw * 0.6))

    # cabeca
    cy = topo - r * 0.86 + resp * 0.5 + (h * 0.025 if pose == "triste" else 0)
    chapeu = fig.get("chapeu", "")
    if fig.get("cabelo") == "longo":
        cab_l = _rrect_path(-r * 1.08, cy - r * 0.6, r * 2.16, r * 1.75, r * 0.6)
        _forma(c, cab_l, cabelo, lw, sombra=False)
    cab = skia.Path(); cab.addCircle(0, cy, r)
    _forma(c, cab, pele, lw)
    # orelhas
    for lado in (-1, 1):
        o = skia.Path(); o.addCircle(lado * r * 0.98, cy + r * 0.08, r * 0.17)
        _forma(c, o, pele, lw * 0.8, sombra=False)
    c.drawCircle(0, cy, r, _fill(pele))  # cobre o encaixe das orelhas
    c.save(); c.clipPath(cab, doAntiAlias=True)
    c.drawRect(skia.Rect.MakeLTRB(r * 0.35, cy - r, r, cy + r), _fill((0, 0, 0), 26)); c.restore()
    c.drawCircle(0, cy, r, _linha(lw))
    # cabelo (quando a cabeca aparece)
    if fig.get("careca"):
        chapeu = "_careca"
        c.drawArc(skia.Rect.MakeXYWH(-r * 0.98, cy - r * 0.3, r * 1.96, r * 1.0), 160, 60, False, _linha(r * 0.16, _cor(cabelo)))
        c.drawArc(skia.Rect.MakeXYWH(-r * 0.98, cy - r * 0.3, r * 1.96, r * 1.0), -40, 60, False, _linha(r * 0.16, _cor(cabelo)))
    if fig.get("cabelo_tipo") == "lado" and chapeu == "":  # repartido de lado, franja caida
        cb = skia.Path(); cb.addArc(skia.Rect.MakeXYWH(-r, cy - r, 2 * r, 2 * r), 180, 180)
        cb.lineTo(r * 0.8, cy - r * 0.45); cb.lineTo(-r * 0.1, cy - r * 0.6); cb.lineTo(-r * 0.75, cy - r * 0.15); cb.close()
        _forma(c, cb, (40, 30, 26), lw, sombra=False); chapeu = "_feito"
    if fig.get("cabelo_tipo") == "tras" and chapeu == "":  # penteado para tras
        cb = skia.Path(); cb.addArc(skia.Rect.MakeXYWH(-r, cy - r * 1.05, 2 * r, 2 * r), 185, 170)
        cb.quadTo(0, cy - r * 0.55, -r * 0.95, cy - r * 0.25); cb.close()
        _forma(c, cb, (70, 60, 56), lw, sombra=False); chapeu = "_feito"
    if chapeu in ("", "palha", "cartola", "coroa", "marinheiro", "tiara", "sombrero", "fez", "boina", "conico", "fedora", "bicorne", "chapeu_chines", "touca_enfermeira", "faixa_pena", "safari", "capacete_obra", "touca", "mago", "cangaceiro", "aba_larga", "cowboy", "tricornio", "pilotka", "cocar", "mongol"):
        if semente % 3 == 0 and tipo not in ("politico", "imperador", "mulher"):  # cacheado
            for k in range(7):
                ang = math.pi + k * math.pi / 6
                cx_, cy_ = math.cos(ang) * r * 0.82, cy + math.sin(ang) * r * 0.82
                b = skia.Path(); b.addCircle(cx_, cy_, r * 0.26); _forma(c, b, cabelo, lw * 0.8, sombra=False)
        else:
            cb = skia.Path(); cb.addArc(skia.Rect.MakeXYWH(-r, cy - r, 2 * r, 2 * r), 180, 180)
            cb.lineTo(r * 0.78, cy - r * 0.3); cb.quadTo(r * 0.1, cy - r * 0.62, -r * 0.78, cy - r * 0.3); cb.close()
            _forma(c, cb, cabelo, lw, sombra=False)
    # olhos grandes com palpebra expressiva (assinatura do canal)
    piscando = (t + semente * 0.73) % 3.6 < 0.12
    olho_w, olho_h = r * 0.34, r * (0.46 if expr == "assustado" else 0.4)
    pup_dx = r * 0.07  # pupila olha para frente (lado da acao)
    for lado in (-1, 1):
        ex, ey = lado * r * 0.33, cy - r * 0.02
        ret = skia.Rect.MakeXYWH(ex - olho_w / 2, ey - olho_h / 2, olho_w, olho_h)
        if piscando:
            c.drawLine(ex - olho_w / 2, ey, ex + olho_w / 2, ey, _linha(lw))
            continue
        c.drawOval(ret, _fill((255, 255, 255))); c.drawOval(ret, _linha(lw * 0.9))
        pr = r * (0.09 if expr == "assustado" else 0.12)
        c.drawCircle(ex + pup_dx, ey + r * 0.04, pr, _fill((28, 22, 18)))
        c.drawCircle(ex + pup_dx - pr * 0.35, ey + r * 0.04 - pr * 0.4, pr * 0.32, _fill((255, 255, 255)))
        # palpebra: bravo = corta de cima em diagonal; triste/preocupado = cai para fora; feliz = sorriso nos olhos
        if expr in ("bravo", "preocupado", "triste") or pose == "triste":
            pal = skia.Path()
            inc = 0.5 if expr == "bravo" else -0.45
            y_in, y_out = ey - olho_h / 2 + olho_h * (0.45 if inc > 0 else 0.1), ey - olho_h / 2 + olho_h * (0.1 if inc > 0 else 0.45)
            xi, xo = ex - lado * olho_w / 2, ex + lado * olho_w / 2
            pal.moveTo(xi - lado * 2, ey - olho_h); pal.lineTo(xo + lado * 2, ey - olho_h)
            pal.lineTo(xo + lado * 2, y_out); pal.lineTo(xi - lado * 2, y_in); pal.close()
            c.save(); c.clipRRect(skia.RRect.MakeOval(ret), doAntiAlias=True); c.drawPath(pal, _fill(pele)); c.restore()
            c.drawLine(xi, y_in, xo, y_out, _linha(lw * 1.1))
        if expr == "feliz":
            c.save(); c.clipRRect(skia.RRect.MakeOval(ret), doAntiAlias=True)
            c.drawRect(skia.Rect.MakeXYWH(ex - olho_w, ey + olho_h * 0.12, olho_w * 2, olho_h), _fill(pele)); c.restore()
    # nariz
    n = skia.Path(); n.moveTo(r * 0.05, cy + r * 0.12); n.quadTo(r * 0.2, cy + r * 0.3, r * 0.02, cy + r * 0.33)
    c.drawPath(n, _linha(lw * 0.9))
    # bigodes especiais (lideres) e charuto
    bg_tipo = fig.get("bigode")
    if bg_tipo == "escovinha":
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.1, cy + r * 0.38, r * 0.2, r * 0.13), _fill((40, 30, 26)))
    elif bg_tipo == "grosso":
        bgp = skia.Path(); bgp.moveTo(-r * 0.4, cy + r * 0.52); bgp.quadTo(0, cy + r * 0.25, r * 0.4, cy + r * 0.52)
        c.drawPath(bgp, skia.Paint(Color=_cor((60, 46, 40)), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=r * 0.2, StrokeCap=skia.Paint.kRound_Cap))
    elif bg_tipo == "fino":
        c.drawLine(-r * 0.2, cy + r * 0.45, r * 0.2, cy + r * 0.45, _linha(lw * 0.9, _cor((40, 30, 26))))
    if fig.get("charuto"):
        _forma(c, _rrect_path(r * 0.12, cy + r * 0.5, r * 0.5, r * 0.1, r * 0.04), (120, 80, 50), lw * 0.6, sombra=False)
        c.drawCircle(r * 0.62, cy + r * 0.55, r * 0.05, _fill((255, 140, 40)))
        for k in range(3):
            f_ = (t * 0.7 + k / 3) % 1.0
            c.drawCircle(r * 0.65 + f_ * r * 0.2, cy + r * 0.45 - f_ * r * 0.6, r * (0.05 + 0.08 * f_), _fill((220, 220, 220), int(160 * (1 - f_))))
    if fig.get("gravata_borboleta"):
        gb = skia.Path(); gb.moveTo(0, topo + h * 0.02); gb.lineTo(-h * 0.05, topo - h * 0.005); gb.lineTo(-h * 0.05, topo + h * 0.045); gb.close()
        gb.moveTo(0, topo + h * 0.02); gb.lineTo(h * 0.05, topo - h * 0.005); gb.lineTo(h * 0.05, topo + h * 0.045); gb.close()
        c.drawPath(gb, _fill((40, 60, 120)))
    # bigode / barba
    if bg_tipo:
        pass
    elif tipo in ("politico", "imperador", "povo") or (tipo == "soldado" and semente % 2 == 0):
        bg = skia.Path(); bg.moveTo(-r * 0.26, cy + r * 0.47); bg.quadTo(0, cy + r * 0.32, r * 0.26, cy + r * 0.47)
        c.drawPath(bg, skia.Paint(Color=_cor(cabelo), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=r * 0.13, StrokeCap=skia.Paint.kRound_Cap))
    elif tipo in ("pracinha", "nacao") and semente % 2 == 1:  # barba por fazer
        for k in range(9):
            c.drawCircle(-r * 0.32 + (k % 5) * r * 0.16, cy + r * (0.66 + (k // 5) * 0.1), r * 0.022, _fill((60, 44, 36), 160))
    if fig.get("barba"):
        bb = skia.Path(); bb.moveTo(-r * 0.62, cy + r * 0.3); bb.quadTo(-r * 0.5, cy + r * 1.25, 0, cy + r * 1.3)
        bb.quadTo(r * 0.5, cy + r * 1.25, r * 0.62, cy + r * 0.3); bb.quadTo(0, cy + r * 0.62, -r * 0.62, cy + r * 0.3)
        _forma(c, bb, (176, 110, 50), lw, sombra=False)
    if fig.get("oculos"):
        for lado in (-1, 1):
            c.drawCircle(lado * r * 0.33, cy - r * 0.02, r * 0.24, _linha(lw * 0.9))
        c.drawLine(-r * 0.09, cy - r * 0.04, r * 0.09, cy - r * 0.04, _linha(lw * 0.8))
    if fig.get("tapa_olho"):
        c.drawLine(-r * 0.9, cy - r * 0.45, r * 0.75, cy + r * 0.2, _linha(lw))
        c.drawOval(skia.Rect.MakeXYWH(r * 0.33 - r * 0.2, cy - r * 0.2, r * 0.4, r * 0.34), _fill((20, 18, 18)))
    # boca
    b = skia.Path()
    if expr == "feliz" or pose == "comemora":
        b.addArc(skia.Rect.MakeXYWH(-r * 0.26, cy + r * 0.38, r * 0.52, r * 0.34), 10, 160)
    elif expr == "assustado":
        b.addOval(skia.Rect.MakeXYWH(-r * 0.1, cy + r * 0.52, r * 0.2, r * 0.24)); c.drawPath(b, _fill((70, 30, 30)))
    elif expr in ("bravo", "preocupado") or pose == "triste":
        b.addArc(skia.Rect.MakeXYWH(-r * 0.2, cy + r * 0.6, r * 0.4, r * 0.24), 200, 140)
    else:
        b.moveTo(-r * 0.14, cy + r * 0.64); b.lineTo(r * 0.14, cy + r * 0.64)
    c.drawPath(b, _linha(lw))

    # chapeus
    cc = fig.get("cor_chapeu")
    if chapeu in ("capacete_rede", "capacete_aba"):
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 1.06, cy - r * 1.16, r * 2.12, r * 1.95), 180, 180); cap.close()
        _forma(c, cap, cc, lw)
        if chapeu == "capacete_rede":  # rede de camuflagem (detalhe do tema)
            c.save(); c.clipPath(cap, doAntiAlias=True)
            for k in range(-6, 7):
                c.drawLine(k * r * 0.22 - r, cy - r * 1.2, k * r * 0.22 + r, cy, _linha(lw * 0.45, _cor((60, 70, 40))))
                c.drawLine(k * r * 0.22 + r, cy - r * 1.2, k * r * 0.22 - r, cy, _linha(lw * 0.45, _cor((60, 70, 40))))
            c.restore(); c.drawPath(cap, _linha(lw))
        aba = r * (1.38 if chapeu == "capacete_aba" else 1.16)
        _forma(c, _rrect_path(-aba, cy - r * 0.24, aba * 2, r * 0.2, r * 0.1), cc, lw, sombra=False)
    elif chapeu == "quepe":
        _forma(c, _rrect_path(-r * 0.78, cy - r * 1.42, r * 1.56, r * 0.66, r * 0.12), cc, lw)
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.78, cy - r * 0.95, r * 1.56, r * 0.12), _fill((224, 184, 62)))
        _forma(c, _rrect_path(-r * 0.2, cy - r * 0.86, r * 1.1, r * 0.14, r * 0.07), (24, 24, 26), lw * 0.7, sombra=False)
    elif chapeu == "coroa":
        cr = skia.Path(); bse = cy - r * 0.8
        cr.moveTo(-r * 0.64, bse); cr.lineTo(-r * 0.64, bse - r * 0.58); cr.lineTo(-r * 0.32, bse - r * 0.26); cr.lineTo(0, bse - r * 0.7)
        cr.lineTo(r * 0.32, bse - r * 0.26); cr.lineTo(r * 0.64, bse - r * 0.58); cr.lineTo(r * 0.64, bse); cr.close()
        _forma(c, cr, cc, lw); c.drawCircle(0, bse - r * 0.16, r * 0.08, _fill((204, 30, 50)))
    elif chapeu == "cartola":
        _forma(c, _rrect_path(-r * 0.56, cy - r * 1.82, r * 1.12, r * 1.0, r * 0.08), cc, lw)
        _forma(c, _rrect_path(-r * 0.98, cy - r * 0.9, r * 1.96, r * 0.17, r * 0.08), cc, lw, sombra=False)
    elif chapeu == "palha":
        topo_p = skia.Path(); topo_p.addArc(skia.Rect.MakeXYWH(-r * 0.72, cy - r * 1.5, r * 1.44, r * 1.16), 180, 180); topo_p.close()
        _forma(c, topo_p, cc, lw)
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.7, cy - r * 1.0, r * 1.4, r * 0.12), _fill((40, 110, 60)))
        aba = skia.Path(); aba.addOval(skia.Rect.MakeXYWH(-r * 1.5, cy - r * 1.0, r * 3.0, r * 0.4)); _forma(c, aba, cc, lw, sombra=False)
    elif chapeu == "cangaceiro":  # couro em meia-lua com estrelas
        aba_ = skia.Path(); aba_.moveTo(-r * 1.45, cy - r * 0.55); aba_.quadTo(0, cy - r * 2.35, r * 1.45, cy - r * 0.55)
        aba_.quadTo(0, cy - r * 1.05, -r * 1.45, cy - r * 0.55); aba_.close()
        _forma(c, aba_, cc, lw)
        for k, dx in enumerate((-0.55, 0, 0.55)):
            sx, sy = dx * r, cy - r * (1.25 if k == 1 else 1.05)
            est = skia.Path()
            for j in range(10):
                rr_ = r * (0.13 if j % 2 == 0 else 0.055); an = -math.pi / 2 + j * math.pi / 5
                if j == 0:
                    est.moveTo(sx + math.cos(an) * rr_, sy + math.sin(an) * rr_)
                else:
                    est.lineTo(sx + math.cos(an) * rr_, sy + math.sin(an) * rr_)
            est.close(); c.drawPath(est, _fill((236, 196, 70)))
    elif chapeu in ("aba_larga", "cowboy"):
        copa = _rrect_path(-r * 0.62, cy - r * 1.45, r * 1.24, r * 0.7, r * 0.25)
        _forma(c, copa, cc, lw)
        aba_ = skia.Path()
        if chapeu == "cowboy":
            aba_.moveTo(-r * 1.4, cy - r * 1.05); aba_.quadTo(0, cy - r * 0.55, r * 1.4, cy - r * 1.05); aba_.quadTo(0, cy - r * 0.78, -r * 1.4, cy - r * 1.05)
        else:
            aba_.addOval(skia.Rect.MakeXYWH(-r * 1.45, cy - r * 0.98, r * 2.9, r * 0.32))
        _forma(c, aba_, cc, lw, sombra=False)
    elif chapeu == "turbante":
        t_ = skia.Path(); t_.addOval(skia.Rect.MakeXYWH(-r * 0.95, cy - r * 1.55, r * 1.9, r * 1.0)); _forma(c, t_, cc, lw)
        for k in range(3):
            c.drawLine(-r * 0.8, cy - r * (1.2 - k * 0.2), r * 0.8, cy - r * (1.35 - k * 0.2), _linha(lw * 0.5))
        c.drawCircle(0, cy - r * 1.05, r * 0.11, _fill((200, 40, 60)))
    elif chapeu == "cocar":
        for k in range(9):
            an = math.pi + (k + 0.5) * math.pi / 9
            fx, fy = math.cos(an) * r * 0.95, cy + math.sin(an) * r * 0.95
            pena = skia.Path(); pena.addOval(skia.Rect.MakeXYWH(-r * 0.09, -r * 0.42, r * 0.18, r * 0.5))
            c.save(); c.translate(fx, fy); c.rotate(math.degrees(an) + 90)
            _forma(c, pena, ((214, 60, 40), (240, 196, 60), (40, 120, 70))[k % 3], lw * 0.6, sombra=False); c.restore()
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.95, cy - r * 0.62, r * 1.9, r * 0.14), _fill((180, 50, 40)))
    elif chapeu == "pilotka":
        pk = skia.Path(); pk.moveTo(-r * 0.75, cy - r * 0.8); pk.lineTo(r * 0.75, cy - r * 0.8); pk.lineTo(r * 0.55, cy - r * 1.25); pk.lineTo(-r * 0.55, cy - r * 1.18); pk.close()
        _forma(c, pk, cc, lw); c.drawCircle(0, cy - r * 1.0, r * 0.1, _fill((200, 30, 40)))
    elif chapeu == "elmo_romano":
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 1.05, cy - r * 1.14, r * 2.1, r * 1.9), 180, 180); cap.close(); _forma(c, cap, cc, lw)
        crista = skia.Path(); crista.addArc(skia.Rect.MakeXYWH(-r * 0.75, cy - r * 1.75, r * 1.5, r * 1.3), 180, 180); crista.close()
        _forma(c, crista, (196, 36, 40), lw)
        for lado in (-1, 1):
            _forma(c, _rrect_path(lado * r * 0.98 - r * 0.14, cy - r * 0.25, r * 0.28, r * 0.75, r * 0.1), cc, lw * 0.8, sombra=False)
    elif chapeu == "elmo_viking":  # capacete arredondado com protetor de nariz (vikings nao usavam chifres)
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 1.05, cy - r * 1.16, r * 2.1, r * 1.95), 180, 180); cap.close(); _forma(c, cap, cc, lw)
        _forma(c, _rrect_path(-r * 0.07, cy - r * 0.25, r * 0.14, r * 0.45, r * 0.05), cc, lw * 0.7, sombra=False)
    elif chapeu == "nemes":  # toucado listrado do farao
        nm = skia.Path(); nm.moveTo(-r * 0.95, cy - r * 0.5); nm.quadTo(0, cy - r * 1.55, r * 0.95, cy - r * 0.5)
        nm.lineTo(r * 1.15, cy + r * 0.9); nm.lineTo(r * 0.75, cy + r * 0.9); nm.lineTo(r * 0.7, cy - r * 0.2)
        nm.lineTo(-r * 0.7, cy - r * 0.2); nm.lineTo(-r * 0.75, cy + r * 0.9); nm.lineTo(-r * 1.15, cy + r * 0.9); nm.close()
        _forma(c, nm, cc, lw)
        c.save(); c.clipPath(nm, doAntiAlias=True)
        for k in range(-8, 9):
            c.drawRect(skia.Rect.MakeXYWH(-r * 1.3, cy + k * r * 0.2, r * 2.6, r * 0.08), _fill((40, 70, 150)))
        c.restore(); c.drawPath(nm, _linha(lw))
    elif chapeu == "kabuto":
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 1.05, cy - r * 1.16, r * 2.1, r * 1.95), 180, 180); cap.close(); _forma(c, cap, cc, lw)
        lua = skia.Path(); lua.moveTo(-r * 0.8, cy - r * 1.6); lua.quadTo(0, cy - r * 0.9, r * 0.8, cy - r * 1.6); lua.quadTo(0, cy - r * 1.15, -r * 0.8, cy - r * 1.6)
        _forma(c, lua, (226, 186, 70), lw * 0.7, sombra=False)
        for lado in (-1, 1):
            ab = skia.Path(); ab.moveTo(lado * r * 1.0, cy - r * 0.3); ab.lineTo(lado * r * 1.45, cy + r * 0.1); ab.lineTo(lado * r * 1.1, cy + r * 0.2); ab.close()
            _forma(c, ab, cc, lw * 0.7, sombra=False)
    elif chapeu == "elmo_cavaleiro":
        e_ = _rrect_path(-r * 1.0, cy - r * 1.1, r * 2.0, r * 1.75, r * 0.45); _forma(c, e_, cc, lw)
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.75, cy - r * 0.12, r * 1.5, r * 0.12), _fill((30, 28, 30)))
        c.drawLine(0, cy - r * 1.05, 0, cy + r * 0.6, _linha(lw * 0.6))
    elif chapeu == "tricornio":
        tc = skia.Path(); tc.moveTo(-r * 1.3, cy - r * 0.75); tc.quadTo(0, cy - r * 1.95, r * 1.3, cy - r * 0.75); tc.quadTo(0, cy - r * 1.05, -r * 1.3, cy - r * 0.75)
        _forma(c, tc, cc, lw)
        c.drawCircle(0, cy - r * 1.22, r * 0.14, _fill((240, 240, 236)))
    elif chapeu == "mongol":
        mg = skia.Path(); mg.moveTo(-r * 0.75, cy - r * 0.8); mg.quadTo(0, cy - r * 2.0, r * 0.75, cy - r * 0.8); mg.close(); _forma(c, mg, cc, lw)
        _forma(c, _rrect_path(-r * 0.95, cy - r * 0.95, r * 1.9, r * 0.3, r * 0.14), (120, 90, 60), lw, sombra=False)
    elif chapeu == "capacete":
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 1.06, cy - r * 1.16, r * 2.12, r * 1.95), 180, 180); cap.close(); _forma(c, cap, cc, lw)
        _forma(c, _rrect_path(-r * 1.16, cy - r * 0.24, r * 2.32, r * 0.2, r * 0.1), cc, lw, sombra=False)
    elif chapeu == "tiara":
        tr = skia.Path(); bse = cy - r * 0.78
        tr.moveTo(-r * 0.5, bse); tr.lineTo(-r * 0.25, bse - r * 0.25); tr.lineTo(0, bse - r * 0.42); tr.lineTo(r * 0.25, bse - r * 0.25); tr.lineTo(r * 0.5, bse); tr.close()
        _forma(c, tr, cc, lw * 0.8, sombra=False); c.drawCircle(0, bse - r * 0.2, r * 0.07, _fill((80, 160, 220)))
    elif chapeu == "capacete_medico":
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 1.06, cy - r * 1.16, r * 2.12, r * 1.95), 180, 180); cap.close(); _forma(c, cap, cc, lw)
        _forma(c, _rrect_path(-r * 1.16, cy - r * 0.24, r * 2.32, r * 0.2, r * 0.1), cc, lw, sombra=False)
        c.drawCircle(0, cy - r * 0.72, r * 0.26, _fill((250, 250, 250)))
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.06, cy - r * 0.92, r * 0.12, r * 0.4), _fill((210, 30, 40)))
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.2, cy - r * 0.78, r * 0.4, r * 0.12), _fill((210, 30, 40)))
    elif chapeu == "touca_enfermeira":
        tc = _rrect_path(-r * 0.55, cy - r * 1.22, r * 1.1, r * 0.4, r * 0.08); _forma(c, tc, cc, lw)
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.05, cy - r * 1.17, r * 0.1, r * 0.3), _fill((210, 30, 40)))
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.15, cy - r * 1.07, r * 0.3, r * 0.1), _fill((210, 30, 40)))
    elif chapeu in ("veu", "capuz"):
        v = skia.Path(); v.moveTo(-r * 1.15, cy + r * 0.9); v.quadTo(-r * 1.2, cy - r * 1.35, 0, cy - r * 1.25)
        v.quadTo(r * 1.2, cy - r * 1.35, r * 1.15, cy + r * 0.9); v.lineTo(r * 0.85, cy + r * 0.9); v.quadTo(r * 0.9, cy - r * 0.8, 0, cy - r * 0.85)
        v.quadTo(-r * 0.9, cy - r * 0.8, -r * 0.85, cy + r * 0.9); v.close()
        _forma(c, v, cc, lw)
        if chapeu == "veu":
            c.drawRect(skia.Rect.MakeXYWH(-r * 0.85, cy - r * 0.85, r * 1.7, r * 0.12), _fill((246, 246, 246)))
    elif chapeu == "faixa_pena":  # faixa com uma pena (respeitoso, sem caricatura)
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.97, cy - r * 0.6, r * 1.94, r * 0.16), _fill(cc))
        for k in range(5):
            c.drawRect(skia.Rect.MakeXYWH(-r * 0.8 + k * r * 0.35, cy - r * 0.58, r * 0.12, r * 0.12), _fill((236, 196, 70)))
        pena = skia.Path(); pena.addOval(skia.Rect.MakeXYWH(r * 0.45, cy - r * 1.35, r * 0.22, r * 0.8))
        c.save(); c.rotate(12, r * 0.56, cy - r * 0.95); _forma(c, pena, (246, 244, 236), lw * 0.7, sombra=False)
        c.drawLine(r * 0.56, cy - r * 1.3, r * 0.56, cy - r * 0.6, _linha(lw * 0.5)); c.restore()
    elif chapeu == "safari":
        cp = skia.Path(); cp.addArc(skia.Rect.MakeXYWH(-r * 0.85, cy - r * 1.42, r * 1.7, r * 1.15), 180, 180); cp.close(); _forma(c, cp, cc, lw)
        aba_ = skia.Path(); aba_.addOval(skia.Rect.MakeXYWH(-r * 1.25, cy - r * 0.98, r * 2.5, r * 0.3)); _forma(c, aba_, cc, lw, sombra=False)
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.83, cy - r * 1.0, r * 1.66, r * 0.1), _fill((110, 80, 50)))
    elif chapeu == "gorro_aviador":
        g_ = skia.Path(); g_.addArc(skia.Rect.MakeXYWH(-r * 1.04, cy - r * 1.1, r * 2.08, r * 1.9), 180, 180); g_.close(); _forma(c, g_, cc, lw)
        for lado in (-1, 1):
            _forma(c, _rrect_path(lado * r * 0.92 - r * 0.15, cy - r * 0.2, r * 0.3, r * 0.6, r * 0.12), cc, lw * 0.8, sombra=False)
            c.drawCircle(lado * r * 0.32, cy - r * 0.62, r * 0.2, _fill((150, 200, 220))); c.drawCircle(lado * r * 0.32, cy - r * 0.62, r * 0.2, _linha(lw))
        c.drawLine(-r * 0.12, cy - r * 0.62, r * 0.12, cy - r * 0.62, _linha(lw))
    elif chapeu == "astronauta":
        c.drawCircle(0, cy, r * 1.22, _fill((200, 230, 245), 90)); c.drawCircle(0, cy, r * 1.22, _linha(lw))
        c.drawCircle(-r * 0.6, cy - r * 0.6, r * 0.14, _fill((255, 255, 255), 200))
    elif chapeu == "capacete_obra":
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 0.95, cy - r * 1.2, r * 1.9, r * 1.6), 180, 180); cap.close(); _forma(c, cap, cc, lw)
        _forma(c, _rrect_path(-r * 1.2, cy - r * 0.48, r * 2.4, r * 0.16, r * 0.08), cc, lw, sombra=False)
    elif chapeu == "touca":
        tc = skia.Path(); tc.addArc(skia.Rect.MakeXYWH(-r * 0.95, cy - r * 1.2, r * 1.9, r * 1.2), 180, 180); tc.close(); _forma(c, tc, cc, lw)
    elif chapeu == "mago":
        mg = skia.Path(); mg.moveTo(-r * 1.1, cy - r * 0.62); mg.lineTo(r * 0.25, cy - r * 2.3); mg.lineTo(r * 1.1, cy - r * 0.62); mg.close()
        _forma(c, mg, cc, lw)
        for (sx, sy) in ((-r * 0.3, cy - r * 1.0), (r * 0.25, cy - r * 1.45), (r * 0.5, cy - r * 0.85)):
            c.drawCircle(sx, sy, r * 0.07, _fill((236, 196, 70)))
        _forma(c, _rrect_path(-r * 1.3, cy - r * 0.75, r * 2.6, r * 0.2, r * 0.1), cc, lw, sombra=False)
    elif chapeu == "boina":
        b_ = skia.Path(); b_.addOval(skia.Rect.MakeXYWH(-r * 1.0, cy - r * 1.25, r * 1.9, r * 0.6)); _forma(c, b_, cc, lw)
        c.drawCircle(r * 0.3, cy - r * 1.05, r * 0.1, _fill((200, 40, 40)))
    elif chapeu == "conico":
        cn = skia.Path(); cn.moveTo(-r * 1.4, cy - r * 0.62); cn.lineTo(0, cy - r * 1.55); cn.lineTo(r * 1.4, cy - r * 0.62); cn.close(); _forma(c, cn, cc, lw)
        for k in range(1, 4):
            c.drawLine(0, cy - r * 1.55, -r * 1.4 + k * r * 0.7, cy - r * 0.62, _linha(lw * 0.4, _cor((170, 146, 96))))
    elif chapeu == "fedora":
        _forma(c, _rrect_path(-r * 0.65, cy - r * 1.42, r * 1.3, r * 0.62, r * 0.2), cc, lw)
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.65, cy - r * 0.98, r * 1.3, r * 0.12), _fill((30, 30, 32)))
        ab = skia.Path(); ab.addOval(skia.Rect.MakeXYWH(-r * 1.2, cy - r * 0.95, r * 2.4, r * 0.26)); _forma(c, ab, cc, lw, sombra=False)
    elif chapeu == "bicorne":
        bc = skia.Path(); bc.moveTo(-r * 1.55, cy - r * 0.75); bc.quadTo(0, cy - r * 1.85, r * 1.55, cy - r * 0.75); bc.quadTo(0, cy - r * 1.0, -r * 1.55, cy - r * 0.75)
        _forma(c, bc, cc, lw)
        c.drawCircle(r * 0.35, cy - r * 1.15, r * 0.13, _fill((40, 60, 150))); c.drawCircle(r * 0.35, cy - r * 1.15, r * 0.07, _fill((240, 240, 240)))
    elif chapeu == "elmo_grego":
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 1.05, cy - r * 1.16, r * 2.1, r * 2.1), 180, 180); cap.close(); _forma(c, cap, cc, lw)
        for lado in (-1, 1):
            _forma(c, _rrect_path(lado * r * 0.75 - r * 0.2, cy - r * 0.25, r * 0.4, r * 0.95, r * 0.12), cc, lw * 0.8, sombra=False)
        cr = skia.Path(); cr.moveTo(-r * 1.1, cy - r * 1.05); cr.quadTo(0, cy - r * 2.1, r * 1.1, cy - r * 1.05); cr.quadTo(0, cy - r * 1.45, -r * 1.1, cy - r * 1.05)
        _forma(c, cr, (196, 36, 40), lw)
    elif chapeu == "chapeu_chines":
        _forma(c, _rrect_path(-r * 0.7, cy - r * 1.3, r * 1.4, r * 0.5, r * 0.15), cc, lw)
        ab = skia.Path(); ab.addOval(skia.Rect.MakeXYWH(-r * 1.1, cy - r * 0.95, r * 2.2, r * 0.26)); _forma(c, ab, cc, lw, sombra=False)
        c.drawCircle(0, cy - r * 1.38, r * 0.12, _fill((200, 40, 40)))
    elif chapeu == "capacete_bombeiro":
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 1.0, cy - r * 1.2, r * 2.0, r * 1.7), 180, 180); cap.close(); _forma(c, cap, cc, lw)
        ab = skia.Path(); ab.moveTo(-r * 1.15, cy - r * 0.4); ab.lineTo(r * 1.5, cy - r * 0.4); ab.lineTo(r * 1.2, cy - r * 0.25); ab.lineTo(-r * 1.15, cy - r * 0.25); ab.close()
        _forma(c, ab, cc, lw, sombra=False)
        c.drawCircle(0, cy - r * 0.85, r * 0.2, _fill((236, 192, 62))); c.drawCircle(0, cy - r * 0.85, r * 0.2, _linha(lw * 0.7))
    elif chapeu == "pickelhaube":  # capacete de couro com ponta (Alemanha, 1a Guerra)
        cap = skia.Path(); cap.addArc(skia.Rect.MakeXYWH(-r * 1.0, cy - r * 1.15, r * 2.0, r * 1.85), 180, 180); cap.close(); _forma(c, cap, cc, lw)
        _forma(c, _rrect_path(-r * 1.15, cy - r * 0.26, r * 2.3, r * 0.18, r * 0.09), cc, lw, sombra=False)
        pt = skia.Path(); pt.moveTo(-r * 0.12, cy - r * 1.12); pt.lineTo(0, cy - r * 1.6); pt.lineTo(r * 0.12, cy - r * 1.12); pt.close()
        _forma(c, pt, (210, 190, 120), lw * 0.7, sombra=False)
        c.drawCircle(0, cy - r * 0.7, r * 0.16, _fill((210, 190, 120)))
    elif chapeu == "morion":  # elmo do conquistador espanhol
        cp = skia.Path(); cp.addArc(skia.Rect.MakeXYWH(-r * 0.8, cy - r * 1.4, r * 1.6, r * 1.3), 180, 180); cp.close(); _forma(c, cp, cc, lw)
        cr = skia.Path(); cr.moveTo(-r * 0.55, cy - r * 1.2); cr.quadTo(0, cy - r * 1.95, r * 0.55, cy - r * 1.2); cr.close(); _forma(c, cr, cc, lw * 0.8, sombra=False)
        ab = skia.Path(); ab.moveTo(-r * 1.45, cy - r * 0.95); ab.quadTo(0, cy - r * 0.55, r * 1.45, cy - r * 0.95); ab.quadTo(0, cy - r * 0.8, -r * 1.45, cy - r * 0.95)
        _forma(c, ab, cc, lw, sombra=False)
    elif chapeu == "sombrero":
        cp = _rrect_path(-r * 0.55, cy - r * 1.75, r * 1.1, r * 0.95, r * 0.4); _forma(c, cp, cc, lw)
        ab = skia.Path(); ab.addOval(skia.Rect.MakeXYWH(-r * 1.85, cy - r * 1.05, r * 3.7, r * 0.45)); _forma(c, ab, cc, lw, sombra=False)
        for k in range(6):
            c.drawCircle(-r * 0.4 + k * r * 0.16, cy - r * 0.95, r * 0.05, _fill((200, 40, 40) if k % 2 else (40, 120, 70)))
    elif chapeu == "fez":
        fz = skia.Path(); fz.moveTo(-r * 0.55, cy - r * 0.8); fz.lineTo(-r * 0.45, cy - r * 1.45); fz.lineTo(r * 0.45, cy - r * 1.45); fz.lineTo(r * 0.55, cy - r * 0.8); fz.close()
        _forma(c, fz, cc, lw)
        c.drawLine(0, cy - r * 1.45, r * 0.5, cy - r * 1.0, _linha(lw * 0.8, _cor((30, 30, 30))))
    elif chapeu == "llauto":  # faixa real inca com franja vermelha e plumas
        c.drawRect(skia.Rect.MakeXYWH(-r * 0.97, cy - r * 0.62, r * 1.94, r * 0.18), _fill(cc))
        for k in range(9):
            c.drawRect(skia.Rect.MakeXYWH(-r * 0.4 + k * r * 0.1, cy - r * 0.44, r * 0.06, r * 0.18), _fill((200, 30, 40)))
        for dx in (-0.12, 0.12):
            pl = skia.Path(); pl.addOval(skia.Rect.MakeXYWH(dx * r - r * 0.08, cy - r * 1.2, r * 0.16, r * 0.6)); _forma(c, pl, (240, 240, 236), lw * 0.6, sombra=False)
    elif chapeu == "capuz_pele":
        v = skia.Path(); v.addCircle(0, cy - r * 0.05, r * 1.25); v.addCircle(0, cy + r * 0.05, r * 0.88); v.setFillType(skia.PathFillType.kEvenOdd)
        _forma(c, v, cc, lw)
        c.drawCircle(0, cy - r * 0.05, r * 1.25, _linha(r * 0.12, _cor((240, 236, 226))))
    elif chapeu == "marinheiro":
        m_ = skia.Path(); m_.addOval(skia.Rect.MakeXYWH(-r * 0.78, cy - r * 1.22, r * 1.56, r * 0.52)); _forma(c, m_, cc, lw)
    c.restore()


def entrada(lado, t, W):
    """Deslocamento horizontal da entrada (desliza da lateral com freio suave)."""
    if t >= 0.45:
        return 0.0
    k = (1 - t / 0.45) ** 3
    return (-1 if lado == "esq" else 1 if lado == "dir" else 0) * W * 0.6 * k


# ------------------------------------------------------------------ elementos de cena do tema
def tropa(c, tipo, qtd, x, y, altura, t, semente=0, flag_fn=None):
    """Grupo de soldados em formacao (2 fileiras), balancando levemente."""
    qtd = max(2, min(12, int(qtd or 5)))
    por_fila = math.ceil(qtd / 2)
    for k in range(qtd):
        fila, col = divmod(k, por_fila)
        dx = (col - (por_fila - 1) / 2) * altura * 0.42 + (fila * altura * 0.2)
        dy = -fila * altura * 0.22
        desenhar(c, {"tipo": tipo, "pose": "anda" if k % 3 == 0 else "parado", "expressao": "bravo"},
                 x + dx, y + dy, altura * (0.92 if fila else 1.0), t + k * 0.37, semente=semente + k * 7, flag_fn=flag_fn)


def fumaca(c, x, y, tam, t):
    """Nuvem de batalha: bolas brancas que crescem e somem + faiscas."""
    for k in range(7):
        fase = (t * 0.9 + k * 0.143) % 1.0
        ang = k * 0.9
        rr = tam * (0.18 + 0.22 * fase)
        cx_, cy_ = x + math.cos(ang) * tam * 0.35 * (0.5 + fase), y + math.sin(ang) * tam * 0.2 - fase * tam * 0.25
        a = int(235 * (1 - fase))
        c.drawCircle(cx_, cy_, rr, _fill((246, 244, 236), a))
        c.drawCircle(cx_, cy_, rr, skia.Paint(Color=skia.ColorSetARGB(int(a * 0.7), 38, 26, 20), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=max(1.5, tam * 0.012)))
    for k in range(4):
        if (t * 7 + k) % 2 < 1:
            fx, fy = x + math.sin(k * 2.1 + t) * tam * 0.3, y + math.cos(k * 1.7) * tam * 0.15
            c.drawCircle(fx, fy, tam * 0.03, _fill((255, 214, 60)))


def bandeira_mastro(c, flag, x, y, altura, t):
    """Bandeira tremulando num mastro fincado em (x, y)."""
    c.drawLine(x, y, x, y - altura, _linha(max(3, altura * 0.035), _cor((96, 70, 44))))
    c.drawCircle(x, y - altura, altura * 0.035, _fill((226, 186, 70)))
    if flag is None:
        return
    fw, fh = altura * 0.62, altura * 0.42
    # onda: desenha em fatias verticais com deslocamento senoidal
    fatias = 14
    for k in range(fatias):
        sx = flag.width() * k / fatias
        sw = flag.width() / fatias
        dx = fw * k / fatias
        off = math.sin(t * 5 - k * 0.55) * fh * 0.06 * (k / fatias)
        dst = skia.Rect.MakeXYWH(x + dx, y - altura + fh * 0.02 + off, fw / fatias + 1, fh)
        c.drawImageRect(flag, skia.Rect.MakeXYWH(sx, 0, sw, flag.height()), dst, skia.SamplingOptions(skia.FilterMode.kLinear))
    c.drawRect(skia.Rect.MakeXYWH(x, y - altura + fh * 0.02, fw, fh), _linha(max(2, altura * 0.012)))
