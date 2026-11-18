"""
Analisador de métricas de manutenibilidade para Texto Estruturado (IEC 61131-3).

Lê projetos de CLP exportados em PLCopen XML e calcula, para cada unidade de
código (programa, bloco funcional, função, método ou ação):

    - LOC, SLOC e CLOC (linhas totais, linhas com código e linhas com comentário);
    - Complexidade Ciclomática de McCabe (forma clássica; a estendida vai para o CSV);
    - Complexidade Cognitiva, adaptada para ST;
    - métricas de Halstead (volume, dificuldade e esforço).

Cada unidade é classificada nas cinco subcaracterísticas de manutenibilidade
da ISO/IEC 25010, segundo o mapeamento de Verdugo et al. (2024):

    testabilidade     -> Complexidade Ciclomática
    analisabilidade   -> Complexidade Cognitiva e duplicação (projeto)
    modificabilidade  -> Halstead e duplicação (projeto)
    modularidade      -> SLOC por unidade, métodos por FB e acoplamento por
                         variáveis globais (relativo)
    reusabilidade     -> densidade de comentários, % de FBs e funções e
                         unidades sem variáveis globais (relativos)

Uma unidade é gargalo quando é desfavorável em McCabe ou na Cognitiva, e
gargalo crítico quando é desfavorável nas duas.

Formatos de entrada:
    - PLCopen XML (TC6): <pou> ... <body><ST><xhtml> ... </xhtml></ST></body>
    - exportação do CODESYS V3 com elementos <addObject>

Uso:
    python analisador_metricas_st.py
        analisa as pastas da lista ARQUIVOS_XML (no fim do arquivo)
    python analisador_metricas_st.py XML/1_tanque_mistura/OpenAI1.xml
        analisa um único arquivo
    python analisador_metricas_st.py XML/2_linha_smt
        analisa todos os .xml da pasta
    python analisador_metricas_st.py XML/1_tanque_mistura XML/2_linha_smt XML/3_envasadora --csv resultados/CSV/resultados.csv
        analisa a amostra completa e gera os CSVs
"""

import argparse  # argumentos da linha de comando
import csv  # exportação dos resultados
import html  # decodificação de entidades (&lt; &gt; &amp;)
import math  # log2 do volume de Halstead
import os  # caminhos de arquivos e pastas
import re  # tokenização e leitura de contingência
import sys  # saída de avisos e código de retorno
import xml.etree.ElementTree as ET  # leitura do XML


# =============================================================================
# CONFIGURAÇÃO DAS MÉTRICAS
# =============================================================================

# McCabe: na forma clássica (False), contam apenas os desvios do fluxo de
# controle (IF, ELSIF, laços e rótulos de CASE). Em ST, "x := a AND b;" não
# cria desvio, pois AND e OR avaliam sempre os dois operandos no CODESYS.
# A forma estendida, que soma cada AND e OR, é gravada no CSV para comparação.
MCCABE_CONTAR_OPERADORES_LOGICOS = False

# McCabe: cada rótulo de CASE é um ramo (McCabe, 1976).
MCCABE_CONTAR_ROTULOS_CASE = True

# Halstead: True conta IF...THEN...END_IF como um único operador;
# False conta cada palavra-chave como um operador (opção adotada).
HALSTEAD_AGRUPAR_ESTRUTURAS = False

# Halstead: o nome de uma função ou FB seguido de "(" é contado como operador.
HALSTEAD_CHAMADAS_COMO_OPERADOR = True

# Comentários (* ... *) podem ser aninhados, como no CODESYS e no TwinCAT.
COMENTARIOS_ANINHADOS = True


# =============================================================================
# LIMIARES DE CLASSIFICAÇÃO (Quadro 2 do artigo)
# =============================================================================

# Testabilidade: Complexidade Ciclomática (Verdugo et al., 2024)
MCCABE_ADEQUADO_ATE = 10      # 1 a 10 -> Adequada
MCCABE_ATENCAO_ATE = 15       # 11 a 15 -> Atenção; acima de 15 -> Gargalo

# Analisabilidade: Complexidade Cognitiva (limiar do SonarQube; Barón, Wyrich e Wagner, 2020)
COGNITIVA_ADEQUADO_ATE = 15   # até 15 -> Adequada; acima de 15 -> Gargalo

# Modularidade: tamanho da unidade em SLOC (Verdugo et al., 2024)
SLOC_ADEQUADO_ATE = 15        # 1 a 15 -> Adequada
SLOC_ATENCAO_ATE = 30         # 16 a 30 -> Atenção; acima de 30 -> Desfavorável

# Modularidade: métodos por FB (Verdugo et al., 2024)
METODOS_ADEQUADO_ATE = 12     # 0 a 12 -> Adequada
METODOS_ATENCAO_ATE = 18      # 13 a 18 -> Atenção; acima de 18 -> Desfavorável

# Analisabilidade e modificabilidade: % de linhas duplicadas no projeto (Verdugo et al., 2024)
DUPLICACAO_ADEQUADO_ABAIXO = 4.0   # [0, 4) -> Adequada
DUPLICACAO_ATENCAO_ABAIXO = 7.0    # [4, 7) -> Atenção; a partir de 7 -> Desfavorável

# Tamanho mínimo, em linhas consecutivas, de um trecho considerado duplicado.
DUPLICACAO_MIN_LINHAS = 10

# Reusabilidade: densidade de comentários, CLOC/LOC em % (Verdugo et al., 2024)
COMENTARIOS_ADEQUADO = (22.0, 50.0)                 # (22, 50) -> Adequada
COMENTARIOS_ATENCAO = ((10.0, 22.0), (50.0, 60.0))  # (10, 22] ou [50, 60) -> Atenção
                                                     # demais valores -> Desfavorável


# =============================================================================
# VOCABULÁRIO DO ST
# =============================================================================

# Estruturas de controle que abrem e fecham um nível de aninhamento.
ABERTURAS = {"IF", "CASE", "FOR", "WHILE", "REPEAT"}

FECHAMENTOS = {"END_IF", "END_CASE", "END_FOR", "END_WHILE", "END_REPEAT"}

# Palavras reservadas contadas como operadores no Halstead.
PALAVRAS_RESERVADAS = {
    "IF", "THEN", "ELSE", "ELSIF", "END_IF",
    "CASE", "OF", "END_CASE",
    "FOR", "TO", "BY", "DO", "END_FOR",
    "WHILE", "END_WHILE",
    "REPEAT", "UNTIL", "END_REPEAT",
    "AND", "OR", "XOR", "NOT", "MOD", "AND_THEN", "OR_ELSE",
    "EXIT", "CONTINUE", "RETURN", "JMP",
}

# Palavras que apenas delimitam uma estrutura (usadas quando HALSTEAD_AGRUPAR_ESTRUTURAS = True).
PALAVRAS_AUXILIARES = {"THEN", "OF", "DO"} | FECHAMENTOS

# Operadores lógicos binários ("&" equivale a AND em ST).
OPERADORES_LOGICOS = {"AND", "OR", "XOR", "AND_THEN", "OR_ELSE", "&"}

# Tokens que encerram uma expressão e reiniciam a sequência de operadores lógicos.
FIM_DE_EXPRESSAO = {";", ":=", "=>", ",", "THEN", "DO", "UNTIL", "OF"}


# =============================================================================
# COMENTÁRIOS E TOKENIZAÇÃO
# =============================================================================

def separar_comentarios(codigo):
    """
    Substitui comentários e pragmas por espaços, mantendo as quebras de linha
    para que a contagem de linhas não mude.

    Considera:
      - strings '...' e "..." (um "(*" dentro de uma string não abre comentário);
      - comentários (* *) e /* */, inclusive aninhados;
      - comentários de linha //;
      - pragmas {...} do CODESYS.

    Retorna (código sem comentários, linhas que têm comentário,
    True se algum comentário ficou sem fechamento).
    """
    saida = []
    linhas_comentario = set()
    i, n, linha = 0, len(codigo), 0
    modo = None  # None, "bloco", "linha", "pragma" ou "string"
    abre = fecha = aspas = ""
    profundidade = 0

    while i < n:
        c = codigo[i]
        par = codigo[i:i + 2]

        if c == "\n":
            if modo == "linha":
                modo = None
            saida.append("\n")
            linha += 1
            i += 1
            continue

        if modo is None:
            if par in ("(*", "/*"):
                modo, abre, profundidade = "bloco", par, 1
                fecha = "*)" if par == "(*" else "*/"
                linhas_comentario.add(linha)
                saida.append("  ")
                i += 2
            elif par == "//":
                modo = "linha"
                linhas_comentario.add(linha)
                saida.append("  ")
                i += 2
            elif c == "{":
                modo = "pragma"
                saida.append(" ")
                i += 1
            else:
                if c in ("'", '"'):
                    modo, aspas = "string", c
                saida.append(c)
                i += 1

        elif modo == "string":
            saida.append(c)
            if c == "$" and i + 1 < n and codigo[i + 1] != "\n":
                saida.append(codigo[i + 1])  # caractere de escape do ST ($' $$ $N)
                i += 2
                continue
            if c == aspas:
                modo = None
            i += 1

        elif modo == "linha":
            saida.append(" ")
            i += 1

        elif modo == "pragma":
            if c == "}":
                modo = None
            saida.append(" ")
            i += 1

        else:  # comentário de bloco
            linhas_comentario.add(linha)
            if COMENTARIOS_ANINHADOS and par == abre:
                profundidade += 1
                saida.append("  ")
                i += 2
            elif par == fecha:
                profundidade -= 1
                saida.append("  ")
                i += 2
                if profundidade == 0:
                    modo = None
            else:
                saida.append(" ")
                i += 1

    return "".join(saida), linhas_comentario, modo == "bloco"


def limpar_comentarios(codigo):
    """Retorna apenas o código sem comentários."""
    return separar_comentarios(codigo)[0]


# Padrão de tokens do ST, na ordem em que são testados.
_PADRAO_TOKEN = re.compile(
    r"""
      (?P<str>'(?:\$.|[^'$])*'|"(?:\$.|[^"$])*")          # strings
    | (?P<lit>\b(?:\w+\#)+[-+]?[\w.]+(?::\d[\w.]*)*         # literais tipados:
              (?:-\d[\w.]*)*)                               # T#5s, 16#FF, INT#3, D#2024-01-01
    | (?P<num>\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][-+]?\d+)?)     # números inteiros e reais
    | (?P<id>[A-Za-z_]\w*)                                  # identificadores e palavras-chave
    | (?P<op>:=|=>|<>|<=|>=|\*\*|\.\.|[-+*/=<>;,.:()\[\]^&])  # operadores e separadores
    | (?P<ws>\s+)                                           # espaços (descartados)
    | (?P<outro>.)                                          # qualquer outro caractere (descartado)
    """,
    re.VERBOSE,
)


def tokenizar(codigo_limpo):
    """
    Converte o código, já sem comentários, em uma lista de tokens (tipo, valor).
    Identificadores e literais ficam em maiúsculas, porque o ST não diferencia
    maiúsculas de minúsculas; strings mantêm o texto original.
    """
    tokens = []
    for m in _PADRAO_TOKEN.finditer(codigo_limpo):
        tipo = m.lastgroup
        if tipo in ("ws", "outro"):
            continue
        valor = m.group()
        if tipo in ("id", "lit"):
            valor = valor.upper()
        tokens.append((tipo, valor))
    return tokens


def _eh(token, *valores):
    """Indica se o token é uma palavra-chave ou um operador com um dos valores informados."""
    tipo, valor = token
    return tipo in ("id", "op") and valor in valores


# =============================================================================
# MÉTRICAS POR UNIDADE
# =============================================================================

def calcular_linhas_codigo(codigo):
    """Retorna LOC, SLOC e CLOC de um bloco de código."""
    sem_comentarios, linhas_comentario, _ = separar_comentarios(codigo)
    original = codigo.split("\n")
    limpo = sem_comentarios.split("\n")

    # ignora as linhas vazias que o XML deixa no início e no fim do bloco
    ini, fim = 0, len(original)
    while ini < fim and not original[ini].strip():
        ini += 1
    while fim > ini and not original[fim - 1].strip():
        fim -= 1

    loc = fim - ini
    sloc = sum(1 for k in range(ini, fim) if limpo[k].strip())
    cloc = sum(1 for k in linhas_comentario if ini <= k < fim)
    return {"loc": loc, "sloc": sloc, "cloc": cloc}


def _indice_rotulo_case(tokens, i):
    """
    Verifica se a instrução que começa na posição i, dentro de um CASE, é um
    rótulo (por exemplo, '1:', '2, 3:', '10..20:' ou 'E_ESTADO.PARADO:').
    Retorna a posição do ':' do rótulo ou None se for uma instrução comum.
    """
    for j in range(i, len(tokens)):
        tipo, valor = tokens[j]
        if tipo == "op" and valor == ":":
            return j
        if tipo == "op" and valor in (":=", ";", "=>"):
            return None
        if tipo == "id" and valor in PALAVRAS_RESERVADAS and valor not in ("NOT", "MOD"):
            return None
    return None


def contar_rotulos_case(tokens):
    """Conta os rótulos de todas as estruturas CASE; o ELSE do CASE não conta."""
    pilha = []
    rotulos = 0
    inicio_instrucao = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok[0] == "id" and tok[1] in ABERTURAS:
            pilha.append(tok[1])
            inicio_instrucao = False
        elif tok[0] == "id" and tok[1] in FECHAMENTOS:
            if pilha:
                pilha.pop()
            inicio_instrucao = False
        elif pilha and pilha[-1] == "CASE":
            if _eh(tok, "OF", "ELSE", ";"):
                inicio_instrucao = True
            elif inicio_instrucao:
                inicio_instrucao = False
                j = _indice_rotulo_case(tokens, i)
                if j is not None:
                    rotulos += 1
                    i = j  # avança até o ':' do rótulo
                    inicio_instrucao = True  # depois do rótulo começa uma instrução
        i += 1
    return rotulos


def calcular_complexidade_ciclomatica(tokens, contar_logicos=None):
    """
    Complexidade Ciclomática de McCabe: pontos de decisão + 1.
    Com contar_logicos=None, segue MCCABE_CONTAR_OPERADORES_LOGICOS;
    com True, calcula a forma estendida (soma também AND e OR).
    """
    if contar_logicos is None:
        contar_logicos = MCCABE_CONTAR_OPERADORES_LOGICOS
    decisoes = 0
    for tipo, valor in tokens:
        if tipo == "id" and valor in ("IF", "ELSIF", "WHILE", "FOR", "REPEAT"):
            decisoes += 1
        elif contar_logicos and tipo in ("id", "op") and valor in (
            "AND", "OR", "AND_THEN", "OR_ELSE", "&"
        ):
            decisoes += 1
    if MCCABE_CONTAR_ROTULOS_CASE:
        decisoes += contar_rotulos_case(tokens)
    return decisoes + 1


def calcular_complexidade_cognitiva(tokens):
    """
    Complexidade Cognitiva (Campbell, 2018), adaptada para ST:
      +1 + nível de aninhamento : IF, CASE, FOR, WHILE, REPEAT
      +1                        : ELSIF e ELSE de IF (o ELSE de CASE não conta)
      +1                        : cada sequência de operadores lógicos iguais
                                  (trocar de operador inicia nova sequência;
                                  NOT não interrompe a sequência)
      +1                        : JMP (desvio incondicional)
    """
    total = 0
    pilha = []  # estruturas abertas; o tamanho da pilha é o nível de aninhamento
    ultimo_logico = None

    for tok in tokens:
        tipo, valor = tok
        if tipo == "id" and valor in ABERTURAS:
            total += 1 + len(pilha)
            pilha.append(valor)
            ultimo_logico = None
        elif tipo == "id" and valor == "ELSIF":
            total += 1
            ultimo_logico = None
        elif tipo == "id" and valor == "ELSE":
            if pilha and pilha[-1] == "IF":
                total += 1
            ultimo_logico = None
        elif tipo == "id" and valor in FECHAMENTOS:
            if pilha:
                pilha.pop()
            ultimo_logico = None
        elif tipo == "id" and valor == "JMP":
            total += 1
            ultimo_logico = None
        elif tipo in ("id", "op") and valor in OPERADORES_LOGICOS:
            if valor != ultimo_logico:
                total += 1
            ultimo_logico = valor
        elif _eh(tok, *FIM_DE_EXPRESSAO):
            ultimo_logico = None

    return total


def calcular_aninhamento_maximo(tokens):
    """Retorna a maior profundidade de estruturas de controle aninhadas."""
    nivel = maximo = 0
    for tipo, valor in tokens:
        if tipo == "id" and valor in ABERTURAS:
            nivel += 1
            maximo = max(maximo, nivel)
        elif tipo == "id" and valor in FECHAMENTOS:
            nivel = max(0, nivel - 1)
    return maximo


def calcular_metricas_halstead(tokens):
    """
    Métricas de Halstead (Equações 1, 2 e 3 do artigo).
      Operadores: símbolos (:=, +, <, ;, ., :), palavras reservadas, parênteses
                  e colchetes (um por par) e chamadas de funções e FBs.
      Operandos : variáveis, constantes, números, literais tipados (T#5s, 16#FF),
                  strings, TRUE e FALSE.
    """
    operadores = []
    operandos = []
    pular_parentese = False

    for k, (tipo, valor) in enumerate(tokens):
        proximo = tokens[k + 1] if k + 1 < len(tokens) else None

        if tipo == "op":
            if valor in (")", "]"):
                continue  # o par já foi contado na abertura
            if valor == "(":
                if pular_parentese:
                    pular_parentese = False  # os parênteses fazem parte da chamada
                    continue
                operadores.append("()")
            elif valor == "[":
                operadores.append("[]")
            else:
                operadores.append(valor)

        elif tipo == "id" and valor in PALAVRAS_RESERVADAS:
            if HALSTEAD_AGRUPAR_ESTRUTURAS and valor in PALAVRAS_AUXILIARES:
                continue
            operadores.append(valor)

        elif tipo == "id" and HALSTEAD_CHAMADAS_COMO_OPERADOR and proximo == ("op", "("):
            operadores.append(valor + "()")
            pular_parentese = True

        else:
            operandos.append(valor)

    n1, n2 = len(set(operadores)), len(set(operandos))
    N1, N2 = len(operadores), len(operandos)

    resultado = {"n1": n1, "n2": n2, "N1": N1, "N2": N2,
                 "volume": 0.0, "dificuldade": 0.0, "esforco": 0.0}
    if n1 == 0 or n2 == 0:
        return resultado  # unidade sem operadores ou operandos: evita divisão por zero

    vocabulario = n1 + n2
    comprimento = N1 + N2
    volume = comprimento * math.log2(vocabulario)
    dificuldade = (n1 / 2.0) * (N2 / n2)
    resultado.update(volume=volume, dificuldade=dificuldade, esforco=dificuldade * volume)
    return resultado


# =============================================================================
# CLASSIFICAÇÃO POR LIMIARES
# =============================================================================

def classificar_testabilidade(mccabe):
    """Classifica a testabilidade da unidade pela Complexidade Ciclomática."""
    if mccabe <= MCCABE_ADEQUADO_ATE:
        return "Adequada"
    if mccabe <= MCCABE_ATENCAO_ATE:
        return "Atenção"
    return "Gargalo"


def classificar_analisabilidade(cognitiva):
    """Classifica a analisabilidade da unidade pela Complexidade Cognitiva."""
    return "Adequada" if cognitiva <= COGNITIVA_ADEQUADO_ATE else "Gargalo"


def classificar_modularidade(sloc):
    """Classifica a modularidade da unidade pelo tamanho em SLOC."""
    if sloc <= SLOC_ADEQUADO_ATE:
        return "Adequada"
    if sloc <= SLOC_ATENCAO_ATE:
        return "Atenção"
    return "Desfavorável"


def classificar_reusabilidade(densidade):
    """Classifica a reusabilidade da unidade pela densidade de comentários (%)."""
    lo, hi = COMENTARIOS_ADEQUADO
    if lo < densidade < hi:
        return "Adequada"
    (a_lo, a_hi), (b_lo, b_hi) = COMENTARIOS_ATENCAO
    if a_lo < densidade <= a_hi or b_lo <= densidade < b_hi:
        return "Atenção"
    return "Desfavorável"


def classificar_gargalo(testabilidade, analisabilidade):
    """
    Classifica a unidade como gargalo de manutenibilidade:
      Crítico : desfavorável em testabilidade e em analisabilidade;
      Sim     : desfavorável em apenas uma delas;
      Atenção : nenhuma desfavorável, mas alguma na faixa de atenção;
      Não     : as duas adequadas.
    """
    gargalos = [testabilidade, analisabilidade].count("Gargalo")
    if gargalos == 2:
        return "Crítico"
    if gargalos == 1:
        return "Sim"
    if "Atenção" in (testabilidade, analisabilidade):
        return "Atenção"
    return "Não"


def calcular_todas_metricas(nome, codigo_st, tipo=""):
    """Calcula as métricas e as classificações de uma unidade de código."""
    codigo_limpo, _, nao_fechado = separar_comentarios(codigo_st)
    if nao_fechado:
        print(f"[AVISO] {nome}: comentário '(*' sem fechamento; "
              f"o restante do bloco foi tratado como comentário.", file=sys.stderr)
    tokens = tokenizar(codigo_limpo)
    linhas = calcular_linhas_codigo(codigo_st)
    halstead = calcular_metricas_halstead(tokens)
    mccabe = calcular_complexidade_ciclomatica(tokens)
    cognitiva = calcular_complexidade_cognitiva(tokens)
    densidade = 100.0 * linhas["cloc"] / linhas["loc"] if linhas["loc"] else 0.0
    testabilidade = classificar_testabilidade(mccabe)
    analisabilidade = classificar_analisabilidade(cognitiva)
    return {
        "pou": nome,
        "tipo": tipo,
        "loc": linhas["loc"],
        "sloc": linhas["sloc"],
        "cloc": linhas["cloc"],
        "densidade_comentarios": densidade,
        "mccabe": mccabe,
        "mccabe_estendido": calcular_complexidade_ciclomatica(tokens, contar_logicos=True),
        "cognitiva": cognitiva,
        "aninhamento_max": calcular_aninhamento_maximo(tokens),
        **halstead,
        "testabilidade": testabilidade,
        "analisabilidade": analisabilidade,
        "modularidade": classificar_modularidade(linhas["sloc"]),
        "reusabilidade": classificar_reusabilidade(densidade),
        "gargalo": classificar_gargalo(testabilidade, analisabilidade),
    }


# =============================================================================
# LEITURA DO XML
# =============================================================================

def _local(tag):
    """Retorna o nome do elemento sem o namespace ('{http://...}pou' -> 'pou')."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _filho(elem, nome):
    """Retorna o primeiro filho direto com o nome informado, ou None."""
    if elem is None:
        return None
    for f in elem:
        if _local(f.tag) == nome:
            return f
    return None


def _texto(elem):
    """Retorna todo o texto do elemento (o parser já decodifica &lt; e CDATA)."""
    return "".join(elem.itertext())


# Tipo atribuído a cada elemento interno de uma POU (ações, métodos, propriedades e transições).
TIPOS_ELEMENTO = {
    "action": "action",
    "transition": "transition",
    "Method": "method",
    "GetAccessor": "property_get",
    "SetAccessor": "property_set",
    "Get": "property_get",
    "Set": "property_set",
}


def extrair_plcopen_classico(raiz):
    """
    Extrai o código ST de cada <pou> no formato PLCopen TC6, incluindo ações,
    transições, métodos e propriedades que tenham o próprio <body><ST>.
    Retorna uma lista de (nome, código ST ou None, tipo), em que o tipo é o
    pouType (program, functionBlock, function) ou o tipo do elemento interno.
    """
    resultados = []
    for pou in raiz.iter():
        if _local(pou.tag) != "pou":
            continue
        nome_pou = pou.get("name", "?")
        pais = {f: p for p in pou.iter() for f in p}

        for elem in pou.iter():
            corpo = _filho(elem, "body")
            if corpo is None:
                continue
            if elem is pou:
                nome = nome_pou
                tipo = pou.get("pouType", "")
            else:
                tipo = TIPOS_ELEMENTO.get(_local(elem.tag), _local(elem.tag))
                rotulo = elem.get("name")
                if not rotulo:  # <Get> e <Set> de propriedade não têm nome próprio
                    pai = pais.get(elem)
                    rotulo = f"{pai.get('name', _local(pai.tag))}.{_local(elem.tag)}" if pai is not None else _local(elem.tag)
                nome = f"{nome_pou}.{rotulo}"
            st = _filho(corpo, "ST")
            resultados.append((nome, _texto(st) if st is not None else None, tipo))
    return resultados


def _buscar_st_sem_aninhados(elem):
    """Procura o <ST> do elemento sem entrar em <addObject> aninhados."""
    for f in elem:
        if _local(f.tag) == "addObject":
            continue
        if _local(f.tag) == "ST":
            return f
        achado = _buscar_st_sem_aninhados(f)
        if achado is not None:
            return achado
    return None


def extrair_codesys_v3(raiz):
    """Extrai o código ST de cada <addObject> da exportação do CODESYS V3."""
    resultados = []
    for obj in raiz.iter():
        if _local(obj.tag) != "addObject":
            continue
        st = _buscar_st_sem_aninhados(obj)
        if st is not None:
            resultados.append((obj.get("name", "?"), _texto(st), ""))
    return resultados


def _extrair_por_regex(conteudo):
    """
    Leitura de contingência, por expressões regulares, para XML malformado.
    É menos precisa: não trata objetos aninhados.
    """
    def limpar(txt):
        return html.unescape(txt.replace("<![CDATA[", "").replace("]]>", ""))

    resultados = []
    if "<addObject" in conteudo:
        for nome, corpo in re.findall(
            r'<addObject[^>]*name="([^"]+)"[^>]*>(.*?)</addObject>', conteudo, flags=re.DOTALL
        ):
            m = re.search(r"<ST>(.*?)</ST>", corpo, flags=re.DOTALL)
            if m:
                resultados.append((nome, limpar(m.group(1)), ""))
    else:
        for cabecalho, nome, corpo in re.findall(
            r'(<pou[^>]*name="([^"]+)"[^>]*>)(.*?)</pou>', conteudo, flags=re.DOTALL
        ):
            m = re.search(r"<body>\s*<ST>\s*<xhtml[^>]*>(.*?)</xhtml>", corpo, flags=re.DOTALL)
            t = re.search(r'pouType="([^"]+)"', cabecalho)
            resultados.append((nome, limpar(m.group(1)) if m else None, t.group(1) if t else ""))
    return resultados


def extrair_blocos_st(xml_path):
    """Lê o arquivo XML e retorna uma lista de (nome, código ST ou None, tipo)."""
    with open(xml_path, "r", encoding="utf-8", errors="ignore") as f:
        conteudo = f.read()
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as e:
        print(f"[AVISO] XML malformado ({e}); usando leitura por expressões regulares.",
              file=sys.stderr)
        return _extrair_por_regex(conteudo)

    if any(_local(el.tag) == "addObject" for el in raiz.iter()):
        return extrair_codesys_v3(raiz)
    return extrair_plcopen_classico(raiz)


# =============================================================================
# MODULARIDADE E REUSABILIDADE (NÍVEL DE PROJETO)
# =============================================================================

def _avaliar_limite(texto, constantes):
    """Calcula o limite de um ARRAY (por exemplo, '4', 'GVL_Main.C_NUM_LINES' ou '(N - 1)')."""
    expr = texto.strip()
    for nome in sorted(constantes, key=len, reverse=True):
        expr = re.sub(r"\b" + re.escape(nome) + r"\b", str(constantes[nome]), expr,
                      flags=re.IGNORECASE)
    if not re.fullmatch(r"[0-9+\-*/() ]+", expr):
        return None
    try:
        return int(eval(expr, {"__builtins__": {}}, {}))  # a expressão só tem dígitos e operadores
    except Exception:
        return None


def _tamanho_array(array, constantes):
    """Retorna o número de elementos de um <array> (produto das dimensões) ou None."""
    total = 1
    for d in array:
        if _local(d.tag) != "dimension":
            continue
        lo = _avaliar_limite(d.get("lower", ""), constantes)
        hi = _avaliar_limite(d.get("upper", ""), constantes)
        if lo is None or hi is None:
            return None
        total *= max(hi - lo + 1, 0)
    return total


def extrair_info_projeto(xml_path):
    """
    Lê do XML as informações de nível de projeto:
      - nomes das listas de variáveis globais (GVL) e das variáveis globais;
      - nomes dos FBs e das funções do projeto;
      - número de instâncias de cada FB (um ARRAY [1..4] OF FB conta como
        quatro instâncias; limites simbólicos são resolvidos pelas constantes
        das listas globais).
    Listas cujo nome começa por "GVL" são reconhecidas no acesso qualificado
    (por exemplo, GVL_IO.xSensor) mesmo que não estejam no arquivo.
    """
    info = {"gvls": set(), "globais": set(), "fbs": set(), "funcoes": set(),
            "instancias": {}}
    try:
        raiz = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError):
        return info

    # 1ª passagem: listas globais, constantes numéricas, FBs e funções
    constantes = {}
    for e in raiz.iter():
        tag = _local(e.tag)
        if tag == "globalVars":
            gvl = (e.get("name") or "").upper()
            if gvl:
                info["gvls"].add(gvl)
            for v in e:
                if _local(v.tag) != "variable" or not v.get("name"):
                    continue
                nome = v.get("name").upper()
                info["globais"].add(nome)
                for sv in v.iter():
                    if _local(sv.tag) == "simpleValue" and re.fullmatch(
                            r"-?\d+", (sv.get("value") or "").strip()):
                        valor = int(sv.get("value"))
                        constantes[nome] = valor
                        if gvl:
                            constantes[f"{gvl}.{nome}"] = valor
                        break
        elif tag == "pou" and e.get("pouType") == "functionBlock":
            info["fbs"].add(e.get("name", "").upper())
        elif tag == "pou" and e.get("pouType") == "function":
            info["funcoes"].add(e.get("name", "").upper())

    # 2ª passagem: instâncias de cada FB, considerando vetores de FB
    pais = {f: p for p in raiz.iter() for f in p}
    for e in raiz.iter():
        if _local(e.tag) != "derived" or not e.get("name"):
            continue
        tipo = e.get("name").upper()
        if tipo not in info["fbs"]:
            continue
        n, p = 1, pais.get(e)
        while p is not None and _local(p.tag) != "variable":
            if _local(p.tag) == "array":
                tam = _tamanho_array(p, constantes)
                n *= tam if tam is not None else 2   # limite não resolvido: considera ao menos 2
            p = pais.get(p)
        info["instancias"][tipo] = info["instancias"].get(tipo, 0) + n
    return info


def referencias_globais(tokens, info):
    """
    Retorna o conjunto de variáveis globais usadas por uma unidade:
      - acesso qualificado LISTA.VARIAVEL, em que LISTA é uma GVL declarada
        ou um nome iniciado por "GVL";
      - acesso direto a uma variável global declarada.
    """
    refs = set()
    for k, (tipo, valor) in enumerate(tokens):
        if tipo != "id":
            continue
        anterior = tokens[k - 1] if k > 0 else None
        if anterior == ("op", "."):
            continue  # é membro de outro elemento (por exemplo, fb.Q), não o início de um acesso
        prox = tokens[k + 1] if k + 1 < len(tokens) else None
        prox2 = tokens[k + 2] if k + 2 < len(tokens) else None
        eh_gvl = valor in info["gvls"] or valor.startswith("GVL")
        if eh_gvl and prox == ("op", ".") and prox2 and prox2[0] == "id":
            refs.add(f"{valor}.{prox2[1]}")
        elif valor in info["globais"]:
            refs.add(valor)
    return refs


def linhas_normalizadas(codigo_st):
    """Retorna as linhas de código sem comentários, sem espaços extras e em maiúsculas."""
    limpo = separar_comentarios(codigo_st)[0]
    return [" ".join(l.split()).upper() for l in limpo.split("\n") if l.strip()]


def marcar_duplicacao(unidades, minimo=None):
    """
    Detecta trechos de pelo menos `minimo` linhas consecutivas iguais, dentro
    de uma unidade ou entre unidades, comparando as linhas normalizadas.
    `unidades` é uma lista com as linhas normalizadas de cada unidade.
    Retorna, para cada unidade, quantas linhas pertencem a algum trecho duplicado.
    """
    minimo = minimo or DUPLICACAO_MIN_LINHAS
    janelas = {}
    for u, linhas in enumerate(unidades):
        for i in range(len(linhas) - minimo + 1):
            chave = tuple(linhas[i:i + minimo])
            janelas.setdefault(chave, []).append((u, i))

    marcadas = [set() for _ in unidades]
    for ocorrencias in janelas.values():
        if len(ocorrencias) < 2:
            continue
        for u, i in ocorrencias:
            marcadas[u].update(range(i, i + minimo))
    return [len(m) for m in marcadas]


def classificar_estrutura_fb(metodos):
    """Classifica a estrutura do FB pelo número de métodos."""
    if metodos <= METODOS_ADEQUADO_ATE:
        return "Adequada"
    if metodos <= METODOS_ATENCAO_ATE:
        return "Atenção"
    return "Desfavorável"


def classificar_duplicacao(percentual):
    """Classifica o projeto pelo percentual de linhas duplicadas."""
    if percentual < DUPLICACAO_ADEQUADO_ABAIXO:
        return "Adequada"
    if percentual < DUPLICACAO_ATENCAO_ABAIXO:
        return "Atenção"
    return "Desfavorável"


def calcular_modularidade_reusabilidade(linhas, codigos, info):
    """
    Acrescenta a cada unidade os indicadores de modularidade e reusabilidade
    e retorna o resumo do projeto.
    `codigos` traz o código ST de cada unidade, na mesma ordem de `linhas`.
    """
    # acoplamento: variáveis globais usadas por unidade
    uso_global = {}
    for r, codigo in zip(linhas, codigos):
        refs = referencias_globais(tokenizar(limpar_comentarios(codigo)), info)
        r["globais_referenciadas"] = len(refs)
        for g in refs:
            uso_global.setdefault(g, set()).add(r["pou"].split(".")[0])

    # duplicação de código, por unidade e no projeto
    normalizadas = [linhas_normalizadas(c) for c in codigos]
    duplicadas = marcar_duplicacao(normalizadas)
    for r, d in zip(linhas, duplicadas):
        r["linhas_duplicadas"] = d

    # métodos por FB
    metodos_por_fb = {}
    for r in linhas:
        if r["tipo"].startswith("method"):
            fb = r["pou"].split(".")[0]
            metodos_por_fb[fb] = metodos_por_fb.get(fb, 0) + 1
    for r in linhas:
        if r["tipo"].startswith("functionBlock"):
            n = metodos_por_fb.get(r["pou"], 0)
            r["metodos"] = n
            r["estrutura_fb"] = classificar_estrutura_fb(n)
        else:
            r["metodos"] = ""
            r["estrutura_fb"] = ""

    # resumo do projeto (os percentuais consideram apenas as POUs, sem métodos e ações)
    unidades_pou = [r for r in linhas if r["tipo"].split(" ")[0] in
                    ("program", "functionBlock", "function")]
    parametrizaveis = [r for r in unidades_pou if r["tipo"].split(" ")[0] in
                       ("functionBlock", "function")]
    autocontidas = [r for r in unidades_pou if r["globais_referenciadas"] == 0]
    sloc_total = sum(r["sloc"] for r in linhas)
    dup_total = sum(duplicadas)
    perc_dup = 100.0 * dup_total / sloc_total if sloc_total else 0.0
    fbs_com_instancias = {fb: n for fb, n in info["instancias"].items() if n > 0}
    fbs_reutilizados = [fb for fb, n in fbs_com_instancias.items() if n >= 2]

    # funções do projeto: número de chamadas (nome seguido de "(")
    chamadas = {fn: 0 for fn in info.get("funcoes", set())}
    for codigo in codigos:
        toks = tokenizar(limpar_comentarios(codigo))
        for k in range(len(toks) - 1):
            t, v = toks[k]
            if t == "id" and v.upper() in chamadas and toks[k + 1] == ("op", "("):
                chamadas[v.upper()] += 1
    funcoes_reutilizadas = [fn for fn, n in chamadas.items() if n >= 2]

    acopl = [r["globais_referenciadas"] for r in unidades_pou] or [0]
    fbs = [r for r in linhas if r["tipo"].startswith("functionBlock")]
    niveis = ("Adequada", "Atenção", "Desfavorável")
    mod = {n: sum(1 for r in linhas if r["modularidade"] == n) for n in niveis}
    reu = {n: sum(1 for r in linhas if r["reusabilidade"] == n) for n in niveis}
    met = {n: sum(1 for r in fbs if r["estrutura_fb"] == n) for n in niveis}
    densidade_media = (sum(r["densidade_comentarios"] for r in linhas) / len(linhas)
                       if linhas else 0.0)

    return {
        "unidades": len(linhas),
        "pous": len(unidades_pou),
        "sloc_total": sloc_total,
        # modularidade
        "sloc_medio_por_pou": sloc_total / len(unidades_pou) if unidades_pou else 0.0,
        "globais_distintas_usadas": len(uso_global),
        "globais_compartilhadas": sum(1 for p in uso_global.values() if len(p) >= 2),
        "acoplamento_medio": sum(acopl) / len(acopl),
        "acoplamento_maximo": max(acopl),
        "fbs": len(fbs),
        "fbs_metodos_desfavoravel": met["Desfavorável"],
        "mod_adequada": mod["Adequada"],
        "mod_atencao": mod["Atenção"],
        "mod_desfavoravel": mod["Desfavorável"],
        "metodos_adequada": met["Adequada"],
        "metodos_atencao": met["Atenção"],
        # reusabilidade
        "densidade_media": densidade_media,
        "reu_adequada": reu["Adequada"],
        "reu_atencao": reu["Atenção"],
        "reu_desfavoravel": reu["Desfavorável"],
        "perc_parametrizaveis": 100.0 * len(parametrizaveis) / len(unidades_pou) if unidades_pou else 0.0,
        "perc_autocontidas": 100.0 * len(autocontidas) / len(unidades_pou) if unidades_pou else 0.0,
        "fbs_instanciados": len(fbs_com_instancias),
        "fbs_reutilizados": len(fbs_reutilizados),
        "funcoes": len(chamadas),
        "funcoes_reutilizadas": len(funcoes_reutilizadas),
        # analisabilidade e modificabilidade
        "linhas_duplicadas": dup_total,
        "perc_duplicacao": perc_dup,
        "duplicacao": classificar_duplicacao(perc_dup),
    }


# =============================================================================
# SAÍDA NO TERMINAL E EM CSV
# =============================================================================

# Colunas da tabela no terminal: (campo, título, largura, formato).
# LOC, volume, dificuldade e as demais métricas ficam apenas no CSV.
COLUNAS = [
    ("pou", "POU", 28, ""),
    ("sloc", "SLOC", 5, ""),
    ("mccabe", "McCabe", 6, ""),
    ("testabilidade", "Testabilidade", 13, ""),
    ("cognitiva", "Cognitiva", 9, ""),
    ("analisabilidade", "Analisabilidade", 15, ""),
    ("esforco", "Esforço (E)", 11, ".0f"),
    ("modularidade", "Modularidade", 12, ""),
    ("densidade_comentarios", "Coment.%", 8, ".1f"),
    ("reusabilidade", "Reusabilidade", 13, ""),
    ("gargalo", "Gargalo", 8, ""),
]


def imprimir_tabela(linhas, sem_st, titulo=None):
    """Imprime a tabela de métricas de um arquivo e a contagem de gargalos."""
    cabecalho = " | ".join(f"{t:<{larg}}" for _, t, larg, _ in COLUNAS)
    if titulo:
        print("\n" + "=" * len(cabecalho))
        print(f"ARQUIVO: {titulo}")
        print("=" * len(cabecalho))
    else:
        print()
    print(cabecalho)
    print("-" * len(cabecalho))
    for r in linhas:
        print(" | ".join(f"{r[ch]:<{larg}{fmt}}" for ch, _, larg, fmt in COLUNAS))
    for nome in sem_st:
        print(f"{nome:<30} | Lógica não está em Texto Estruturado (ST) ou está vazia.")
    if linhas:
        resumo = {c: sum(1 for r in linhas if r["gargalo"] == c)
                  for c in ("Crítico", "Sim", "Atenção", "Não")}
        print("Gargalos: " + " | ".join(f"{c}: {q}" for c, q in resumo.items()))


def imprimir_resumo_projeto(proj):
    """Imprime os indicadores do projeto em uma linha abaixo da tabela."""
    texto = (f"Projeto: duplicação {proj['perc_duplicacao']:.1f}% ({proj['duplicacao']}) "
             f"[analisab./modificab.] | acoplamento global médio {proj['acoplamento_medio']:.1f} "
             f"(máx {proj['acoplamento_maximo']}) | FBs/funções {proj['perc_parametrizaveis']:.0f}% | "
             f"unidades sem globais {proj['perc_autocontidas']:.0f}% [relativos]")
    if proj["fbs"]:
        texto += (f" | métodos por FB desfavoráveis: {proj['fbs_metodos_desfavoravel']} "
                  f"de {proj['fbs']} | FBs reutilizados (2+ instâncias) {proj['fbs_reutilizados']} "
                  f"de {proj['fbs']}")
    if proj["funcoes"]:
        texto += (f" | funções reutilizadas (2+ chamadas) {proj['funcoes_reutilizadas']} "
                  f"de {proj['funcoes']}")
    print(texto)


def salvar_csv_projeto(projetos, caminho):
    """Grava o CSV com uma linha por projeto (separador ';' e vírgula decimal)."""
    campos = ["arquivo", "unidades", "pous", "sloc_total",
              # modularidade
              "sloc_medio_por_pou", "mod_adequada", "mod_atencao", "mod_desfavoravel",
              "fbs", "metodos_adequada", "metodos_atencao", "fbs_metodos_desfavoravel",
              "globais_distintas_usadas", "globais_compartilhadas",
              "acoplamento_medio", "acoplamento_maximo",
              # reusabilidade
              "densidade_media", "reu_adequada", "reu_atencao", "reu_desfavoravel",
              "perc_parametrizaveis", "perc_autocontidas", "fbs_instanciados",
              "fbs_reutilizados", "funcoes", "funcoes_reutilizadas",
              # analisabilidade e modificabilidade
              "linhas_duplicadas", "perc_duplicacao", "duplicacao"]
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:  # o BOM mantém os acentos no Excel
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        for p in projetos:
            w.writerow({k: (f"{p[k]:.2f}".replace(".", ",") if isinstance(p[k], float) else p[k])
                        for k in campos})
    print(f"Resumo por projeto salvo em: {os.path.abspath(caminho)}")


def salvar_csv(linhas, caminho):
    """Grava o CSV com uma linha por unidade de código (separador ';' e vírgula decimal)."""
    campos = ["arquivo", "pou", "tipo",
              "loc", "sloc", "cloc", "densidade_comentarios",
              "mccabe", "mccabe_estendido", "cognitiva", "aninhamento_max",
              "n1", "n2", "N1", "N2", "volume", "dificuldade", "esforco",
              "globais_referenciadas", "linhas_duplicadas", "metodos",
              "testabilidade", "analisabilidade", "modularidade", "reusabilidade",
              "estrutura_fb", "gargalo"]
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:  # o BOM mantém os acentos no Excel
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        for r in linhas:
            w.writerow({k: (f"{r[k]:.2f}".replace(".", ",") if isinstance(r[k], float) else r[k])
                        for k in campos})
    print(f"\nResultados salvos em: {os.path.abspath(caminho)}")


# =============================================================================
# EXECUÇÃO
# =============================================================================

def analisar_projeto_universal(xml_path):
    """
    Analisa um arquivo XML e retorna (métricas de cada unidade, unidades sem
    código ST, resumo do projeto).
    """
    arquivo = os.path.basename(xml_path)
    try:
        blocos = extrair_blocos_st(xml_path)
    except OSError as e:
        print(f"Erro ao abrir o arquivo '{arquivo}': {e}")
        return [], [], None

    linhas, sem_st, codigos = [], [], []
    for nome, codigo, tipo in blocos:
        if codigo is None or not codigo.strip():
            sem_st.append(nome)
        else:
            linha = calcular_todas_metricas(nome, codigo, tipo)
            linha["arquivo"] = arquivo
            linhas.append(linha)
            codigos.append(codigo)

    projeto = calcular_modularidade_reusabilidade(linhas, codigos, extrair_info_projeto(xml_path))
    projeto["arquivo"] = arquivo
    return linhas, sem_st, projeto


def listar_arquivos_xml(caminhos):
    """Expande as pastas em seus arquivos .xml, em ordem alfabética."""
    arquivos = []
    for c in caminhos:
        if os.path.isdir(c):
            arquivos.extend(sorted(
                os.path.join(c, f) for f in os.listdir(c) if f.lower().endswith(".xml")
            ))
        elif os.path.isfile(c):
            arquivos.append(c)
        else:
            print(f"[ERRO] '{c}' não foi encontrado (caminho tentado: {os.path.abspath(c)})")
    return arquivos


def analisar_varios(caminhos, csv_path=None):
    """Analisa os arquivos XML, imprime uma tabela por arquivo e grava os CSVs."""
    arquivos = listar_arquivos_xml(caminhos)
    if not arquivos:
        print("Nenhum arquivo XML para analisar.")
        return []

    todas, projetos = [], []
    for xml_path in arquivos:
        linhas, sem_st, projeto = analisar_projeto_universal(xml_path)
        imprimir_tabela(linhas, sem_st, titulo=os.path.basename(xml_path))
        if projeto and linhas:
            imprimir_resumo_projeto(projeto)
            projetos.append(projeto)
        todas.extend(linhas)

    print(f"\nTotal: {len(arquivos)} arquivo(s), {len(todas)} POU(s) analisada(s).")
    if csv_path:
        pasta = os.path.dirname(csv_path)
        if pasta:
            os.makedirs(pasta, exist_ok=True)  # cria a pasta de saída, se ainda não existir
        salvar_csv(todas, csv_path)
        base, ext = os.path.splitext(csv_path)
        salvar_csv_projeto(projetos, f"{base}_projeto{ext or '.csv'}")
    return todas


# Pastas analisadas quando o script é executado sem argumentos.
ARQUIVOS_XML = [
    "XML/1_tanque_mistura",
    "XML/2_linha_smt",
    "XML/3_envasadora",
]

# CSV gerado quando o script é executado sem argumentos (None para não gerar).
ARQUIVO_CSV = "resultados/CSV/resultados.csv"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Métricas de manutenibilidade para código ST (IEC 61131-3).")
    parser.add_argument("caminhos", nargs="*",
                        help="arquivos XML e/ou pastas (sem argumentos, usa a lista ARQUIVOS_XML)")
    parser.add_argument("--csv", help="grava os resultados em CSV (separador ';')")
    args = parser.parse_args()

    caminhos = args.caminhos or ARQUIVOS_XML
    csv_saida = args.csv if args.caminhos else (args.csv or ARQUIVO_CSV)

    if not analisar_varios(caminhos, csv_saida):
        sys.exit(1)
