import math
import re

def extrair_pous_do_xml(xml_path):
    """
    Função principal de entrada. Lê o arquivo e delega o parsing 
    conforme o formato detectado, retornando a lista de dados estruturados.
    """
    try:
        with open(xml_path, "r", encoding="utf-8", errors="ignore") as f:
            conteudo_xml = f.read()
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir o arquivo: {e}")

    # --- IDENTIFICAÇÃO DO FORMATO ---
    if "<addObject" in conteudo_xml:
        return extrair_formato_codesys_v3(conteudo_xml)
    else:
        return extrair_formato_plcopen_classico(conteudo_xml)

def extrair_formato_codesys_v3(conteudo_xml):
    lista_pous_processadas = []
    objetos = re.findall(r'<addObject[^>]*name="([^"]+)"[^>]*>(.*?)</addObject>', conteudo_xml, flags=re.DOTALL)
    
    for nome_objeto, conteudo_objeto in objetos:
        if "<ST>" in conteudo_objeto:
            st_match = re.search(r"<ST>(.*?)</ST>", conteudo_objeto, flags=re.DOTALL)
            if st_match:
                codigo_st = st_match.group(1).replace("<![CDATA[", "").replace("]]>", "")
                dados_metricas = processar_metricas_pou(nome_objeto, codigo_st)
                lista_pous_processadas.append(dados_metricas)
    return lista_pous_processadas

def extrair_formato_plcopen_classico(conteudo_xml):
    lista_pous_processadas = []
    pou_blocos = re.findall(r'<pou[^>]*name="([^"]+)"[^>]*>(.*?)</pou>', conteudo_xml, flags=re.DOTALL)
    
    for pou_name, pou_conteudo in pou_blocos:
        st_match = re.search(r"<xhtml[^>]*>(.*?)</xhtml>", pou_conteudo, flags=re.DOTALL)
        if st_match:
            codigo_st = st_match.group(1)
            dados_metricas = processar_metricas_pou(pou_name, codigo_st)
            lista_pous_processadas.append(dados_metricas)
        else:
            # Caso não seja Texto Estruturado, criamos um registro vazio/alerta
            lista_pous_processadas.append({
                "nome": pou_name, "loc": 0, "mccabe": 0, "cognitiva": 0,
                "vol": 0.0, "dif": 0.0, "esf": 0.0, "status": "Não é ST/Vazia"
            })
    return lista_pous_processadas

def processar_metricas_pou(pou_name, codigo_st):
    loc_total, _ = calcular_linhas_codigo(codigo_st)
    complexidade = calcular_complexidade_ciclomatica(codigo_st)
    cognitiva = calcular_complexidade_cognitiva(codigo_st)
    halstead = calcular_metricas_halstead(codigo_st)

    return {
        "nome": pou_name,
        "loc": loc_total,
        "mccabe": complexidade,
        "cognitiva": cognitiva,
        "vol": halstead['volume'],
        "dif": halstead['dificuldade'],
        "esf": halstead['esforco'],
        "status": "OK"
    }

def calcular_linhas_codigo(codigo):
    linhas = codigo.split("\n")
    total_linhas = len(linhas)
    linhas_comentarios = 0
    dentro_bloco_comentario = False

    for linha in map(str.strip, linhas):
        if not linha: continue
        if "(*" in linha: dentro_bloco_comentario = True
        if "*)" in linha:
            dentro_bloco_comentario = False
            linhas_comentarios += 1
            continue
        if dentro_bloco_comentario:
            linhas_comentarios += 1
            continue
        if linha.startswith("//"):
            linhas_comentarios += 1

    return total_linhas, linhas_comentarios

def limpar_comentarios(codigo):
    codigo_limpo = re.sub(r"\(\*.*?\*\)", " ", codigo, flags=re.DOTALL)
    if "(*" in codigo_limpo:
        codigo_limpo = codigo_limpo.split("(*")[0]
    codigo_limpo = re.sub(r"//.*", "", codigo_limpo)
    return codigo_limpo

def calcular_complexidade_ciclomatica(codigo):
    codigo_limpo = limpar_comentarios(codigo)
    padroes_decisao = [
        r"\bIF\b", r"\bELSIF\b", r"\bWHILE\b", r"\bFOR\b", r"\bREPEAT\b", r"\bAND\b", r"\bOR\b"
    ]
    pontos_de_decisao = 0
    for padrao in padroes_decisao:
        matches = re.findall(padrao, codigo_limpo, flags=re.IGNORECASE)
        pontos_de_decisao += len(matches)
    return pontos_de_decisao + 1

def calcular_complexidade_cognitiva(codigo):
    codigo_limpo = limpar_comentarios(codigo)
    tokens = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b|:=|<=|>=|<>|&&|\|\|', codigo_limpo, flags=re.IGNORECASE)

    complexidade_cognitiva = 0
    nivel_aninhamento = 0
    ultimo_op_logico = None

    for token in tokens:
        token_upper = token.upper()

        if token_upper in ['IF', 'WHILE', 'FOR', 'REPEAT']:
            complexidade_cognitiva += 1 + nivel_aninhamento
            nivel_aninhamento += 1
            ultimo_op_logico = None
        elif token_upper in ['ELSIF', 'ELSE']:
            complexidade_cognitiva += 1
            ultimo_op_logico = None
        elif token_upper == 'CASE':
            complexidade_cognitiva += 1 + nivel_aninhamento
            nivel_aninhamento += 1
            ultimo_op_logico = None
        elif token_upper in ['END_IF', 'END_WHILE', 'END_FOR', 'END_REPEAT', 'END_CASE']:
            nivel_aninhamento = max(0, nivel_aninhamento - 1)
            ultimo_op_logico = None
        elif token_upper in ['AND', 'OR', 'XOR', 'NOT']:
            if ultimo_op_logico is None:
                complexidade_cognitiva += 1
            elif ultimo_op_logico != token_upper:
                complexidade_cognitiva += 1
            ultimo_op_logico = token_upper

    return complexidade_cognitiva

def calcular_metricas_halstead(codigo):
    codigo_limpo = limpar_comentarios(codigo)
    operadores_patterns = [
        r":=", r"\+", r"-", r"\*", r"/", r"<>", r"<=", r">=", r"=", r"<", r">", r";",
        r"\bIF\b", r"\bTHEN\b", r"\bELSE\b", r"\bELSIF\b", r"\bEND_IF\b",
        r"\bCASE\b", r"\bOF\b", r"\bEND_CASE\b", r"\bFOR\b", r"\bTO\b", r"\bDO\b", r"\bEND_FOR\b",
        r"\bWHILE\b", r"\bEND_WHILE\b", r"\bREPEAT\b", r"\bUNTIL\b", r"\bEND_REPEAT\b",
        r"\bAND\b", r"\bOR\b", r"\bXOR\b", r"\bNOT\b"
    ]

    total_operadores = 0
    operadores_unicos = set()
    codigo_sem_operadores = codigo_limpo

    for pat in operadores_patterns:
        matches = re.findall(pat, codigo_sem_operadores, flags=re.IGNORECASE)
        if matches:
            total_operadores += len(matches)
            operadores_unicos.add(pat)
            codigo_sem_operadores = re.sub(pat, " ", codigo_sem_operadores, flags=re.IGNORECASE)

    operandos_encontrados = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b|\b\d+\b", codigo_sem_operadores)
    total_operandos = len(operandos_encontrados)
    operandos_unicos = set(operandos_encontrados)

    n1, n2 = len(operadores_unicos), len(operandos_unicos)
    N1, N2 = total_operadores, total_operandos

    if n1 == 0 or n2 == 0:
        return {"volume": 0.0, "dificuldade": 0.0, "esforco": 0.0}

    vocabulario = n1 + n2
    comprimento = N1 + N2
    volume = comprimento * math.log2(vocabulario)
    dificuldade = (n1 / 2.0) * (N2 / n2)
    esforco = dificuldade * volume

    return {"volume": volume, "dificuldade": dificuldade, "esforco": esforco}