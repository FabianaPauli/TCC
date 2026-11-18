"""
Testes do analisador (execute com:  python -m pytest -v test_analisador_metricas_st.py).
Os valores esperados foram calculados manualmente e servem como validação
da ferramenta no capítulo de metodologia.
"""
import math
import os
import tempfile

import analisador_metricas_st as a


def metricas(codigo):
    return a.calcular_todas_metricas("teste", codigo)


def tokens(codigo):
    return a.tokenizar(a.limpar_comentarios(codigo))


# ---------------- Comentários ----------------

def test_comentario_dentro_de_string_nao_trunca_codigo():
    cod = "s := '(* texto'; IF a THEN b := 1; END_IF;"
    assert metricas(cod)["mccabe"] == 2


def test_comentario_aninhado():
    cod = "(* externo (* interno *) IF x THEN *)\nIF a THEN b := 1; END_IF;"
    assert metricas(cod)["mccabe"] == 2


def test_palavra_chave_em_string_nao_conta():
    assert metricas("msg := 'IF AND OR';")["mccabe"] == 1


# ---------------- LOC ----------------

def test_linhas():
    cod = "\n\n(* cabeçalho *)\nx := 1; // inicializa\n\ny := 2;\n\n"
    r = metricas(cod)
    assert r["loc"] == 4    # do comentário até 'y := 2;'
    assert r["sloc"] == 2   # x := 1; e y := 2;
    assert r["cloc"] == 2   # linha do (* *) e linha com //


# ---------------- McCabe ----------------

def test_mccabe_case_conta_rotulos_e_nao_else():
    cod = """
    CASE estado OF
        1: a := 1;
        2, 3: a := 2;
        10..20: a := 3;
    ELSE
        a := 0;
    END_CASE;
    """
    assert metricas(cod)["mccabe"] == 4  # 3 rótulos + 1


def test_mccabe_case_com_if_aninhado():
    cod = """
    CASE e OF
        1: IF x THEN y := 1; END_IF;
           z := 2;
        2: z := 3;
    END_CASE;
    """
    assert metricas(cod)["mccabe"] == 4  # 2 rótulos + IF + 1


def test_mccabe_operadores_logicos():
    r = metricas("IF a AND b OR c THEN x := 1; END_IF;")
    assert r["mccabe"] == 2 and r["mccabe_estendido"] == 4


# ---------------- Cognitiva ----------------

def test_cognitiva_operadores_reiniciam_entre_instrucoes():
    assert metricas("a := x AND y; b := z AND w;")["cognitiva"] == 2


def test_cognitiva_not_nao_quebra_sequencia():
    assert metricas("IF x AND NOT y AND z THEN a := 1; END_IF;")["cognitiva"] == 2


def test_cognitiva_troca_de_operador():
    assert metricas("IF a AND b OR c THEN x := 1; END_IF;")["cognitiva"] == 3


def test_cognitiva_aninhamento_e_else():
    cod = """
    IF a THEN                 (* +1 *)
        FOR i := 1 TO 10 DO   (* +2 *)
            IF b THEN         (* +3 *)
                x := 1;
            END_IF;
        END_FOR;
    ELSIF c THEN              (* +1 *)
        x := 2;
    ELSE                      (* +1 *)
        x := 3;
    END_IF;
    """
    assert metricas(cod)["cognitiva"] == 8


def test_cognitiva_else_de_case_nao_conta():
    cod = "CASE e OF 1: x := 1; ELSE x := 0; END_CASE;"
    assert metricas(cod)["cognitiva"] == 1


# ---------------- Halstead ----------------

def test_halstead_exemplo_manual():
    # operadores: :=  +  ;      -> n1 = 3, N1 = 3
    # operandos : X  A  B       -> n2 = 3, N2 = 3
    r = metricas("x := a + b;")
    assert (r["n1"], r["n2"], r["N1"], r["N2"]) == (3, 3, 3, 3)
    assert math.isclose(r["volume"], 6 * math.log2(6))
    assert math.isclose(r["dificuldade"], 1.5)


def test_halstead_nao_diferencia_maiusculas():
    r = metricas("Motor := motor;")
    assert r["n2"] == 1 and r["N2"] == 2


def test_halstead_literais_tipados():
    toks = tokens("t := T#1.5s; h := 16#FF; d := D#2024-01-31; r := 3.14;")
    literais = [v for tp, v in toks if tp in ("lit", "num")]
    assert literais == ["T#1.5S", "16#FF", "D#2024-01-31", "3.14"]


def test_halstead_chamada_de_funcao_e_operador():
    r = metricas("y := LIMIT(0, x, 100);")
    # operadores: := LIMIT() , , ;  -> n1 = 4 ; operandos: Y 0 X 100 -> n2 = 4
    assert (r["n1"], r["N1"], r["n2"], r["N2"]) == (4, 5, 4, 4)


# ---------------- XML ----------------

PLCOPEN = """<?xml version="1.0" encoding="utf-8"?>
<project xmlns="http://www.plcopen.org/xml/tc6_0200">
  <types><pous>
    <pou name="Controle" pouType="program">
      <documentation><xhtml xmlns="http://www.w3.org/1999/xhtml">Documentação IF AND OR</xhtml></documentation>
      <body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">IF nivel &lt; 10 AND bomba THEN
  valvula := TRUE;
END_IF;</xhtml></ST></body>
      <actions>
        <action name="Reset"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">x := 0;</xhtml></ST></body></action>
      </actions>
    </pou>
    <pou name="Ladder" pouType="program"><body><LD/></body></pou>
  </pous></types>
</project>"""


def _arquivo_temp(conteudo):
    fd, caminho = tempfile.mkstemp(suffix=".xml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(conteudo)
    return caminho


def test_plcopen_entidades_documentacao_e_acoes():
    blocos = {n: c for n, c, _ in a.extrair_blocos_st(_arquivo_temp(PLCOPEN))}
    assert set(blocos) == {"Controle", "Controle.Reset", "Ladder"}
    assert blocos["Ladder"] is None
    assert "nivel < 10" in blocos["Controle"]          # &lt; decodificado
    assert "Documentação" not in blocos["Controle"]    # não pegou <documentation>
    r = metricas(blocos["Controle"])
    assert r["mccabe"] == 2 and r["mccabe_estendido"] == 3   # IF (+ AND na estendida)
    assert "LT" not in [v for _, v in tokens(blocos["Controle"])]


CODESYS = """<?xml version="1.0"?>
<root>
  <addObject name="Pasta">
    <addObject name="FB_Motor"><ST><![CDATA[IF a < b THEN c := 1; END_IF;]]></ST></addObject>
    <addObject name="PRG_Main"><ST>x := 1;</ST></addObject>
  </addObject>
</root>"""


def test_codesys_objetos_aninhados():
    blocos = {n: c for n, c, _ in a.extrair_blocos_st(_arquivo_temp(CODESYS))}
    assert set(blocos) == {"FB_Motor", "PRG_Main"}
    assert blocos["FB_Motor"] == "IF a < b THEN c := 1; END_IF;"


def test_programa_fb_funcao_metodo_propriedade():
    xml = """<?xml version="1.0"?>
<project xmlns="http://www.plcopen.org/xml/tc6_0200"><types><pous>
 <pou name="FB_Cil" pouType="functionBlock"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">IF a THEN b := 1; END_IF;</xhtml></ST></body>
  <actions><action name="Reset"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">b := 0;</xhtml></ST></body></action></actions>
  <addData><data name="m"><Method name="Recuar"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">Recuar := TRUE;</xhtml></ST></body></Method></data>
  <data name="p"><Property name="Estado"><GetAccessor><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">Estado := s;</xhtml></ST></body></GetAccessor></Property></data></addData>
 </pou>
 <pou name="FUN_Escala" pouType="function"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">FUN_Escala := x * 2;</xhtml></ST></body></pou>
</pous></types>
<instances><configurations><configuration name="D"><resource name="A"><addData><data name="pou">
 <pou name="PRG_Main" pouType="program"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">fbCil();</xhtml></ST></body></pou>
</data></addData></resource></configuration></configurations></instances></project>"""
    tipos = {n: t for n, _, t in a.extrair_blocos_st(_arquivo_temp(xml))}
    assert tipos == {
        "FB_Cil": "functionBlock",
        "FB_Cil.Reset": "action",
        "FB_Cil.Recuar": "method",
        "FB_Cil.Estado.GetAccessor": "property_get",
        "FUN_Escala": "function",
        "PRG_Main": "program",
    }


# ---------------- Classificação por limiares ----------------

def test_classificacao_testabilidade():
    assert [a.classificar_testabilidade(v) for v in (1, 10, 11, 15, 16)] == \
        ["Adequada", "Adequada", "Atenção", "Atenção", "Gargalo"]


def test_classificacao_analisabilidade():
    assert a.classificar_analisabilidade(15) == "Adequada"
    assert a.classificar_analisabilidade(16) == "Gargalo"


def test_classificacao_complementar():
    assert [a.classificar_modularidade(v) for v in (15, 16, 30, 31)] == \
        ["Adequada", "Atenção", "Atenção", "Desfavorável"]
    assert [a.classificar_reusabilidade(v) for v in (0, 14.1, 30, 55, 70)] == \
        ["Desfavorável", "Atenção", "Adequada", "Atenção", "Desfavorável"]


def test_classificacao_gargalo():
    assert a.classificar_gargalo("Gargalo", "Gargalo") == "Crítico"
    assert a.classificar_gargalo("Adequada", "Gargalo") == "Sim"
    assert a.classificar_gargalo("Atenção", "Adequada") == "Atenção"
    assert a.classificar_gargalo("Adequada", "Adequada") == "Não"


def test_mccabe_classico_ignora_operadores_logicos_em_atribuicao():
    r = metricas("x := a AND b OR c;")
    assert r["mccabe"] == 1 and r["mccabe_estendido"] == 3 and r["aninhamento_max"] == 0


# ---------------- Modularidade e reusabilidade ----------------

def test_referencias_globais_qualificadas_e_diretas():
    info = {"gvls": {"GVL_MAIN"}, "globais": {"XSTART"}, "fbs": set(), "instancias": {}}
    toks = tokens("GVL_Main.xMotor := xStart AND GVL_IO.xSensor; fb.xStart := TRUE;")
    assert a.referencias_globais(toks, info) == {"GVL_MAIN.XMOTOR", "XSTART", "GVL_IO.XSENSOR"}


def test_duplicacao_entre_unidades():
    bloco = ["A := 1;", "B := 2;", "C := 3;", "D := 4;", "E := 5;", "F := 6;"]
    u1 = bloco + ["X := 0;"]
    u2 = ["Y := 9;"] + bloco
    u3 = ["Z := 1;"] * 3
    assert a.marcar_duplicacao([u1, u2, u3], minimo=6) == [6, 6, 0]


def test_classificacao_modularidade_reusabilidade():
    assert [a.classificar_estrutura_fb(n) for n in (12, 13, 18, 19)] == \
        ["Adequada", "Atenção", "Atenção", "Desfavorável"]
    assert [a.classificar_duplicacao(p) for p in (3.9, 4.0, 6.9, 7.0)] == \
        ["Adequada", "Atenção", "Atenção", "Desfavorável"]


def test_resumo_de_projeto_com_fb_metodos_e_instancias():
    xml = """<?xml version="1.0"?>
<project xmlns="http://www.plcopen.org/xml/tc6_0200"><types><pous>
 <pou name="FB_Cil" pouType="functionBlock"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">IF xAv THEN xOut := TRUE; END_IF;</xhtml></ST></body>
  <addData><data name="m"><Method name="Recuar"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">xOut := FALSE;</xhtml></ST></body></Method></data></addData>
 </pou>
 <pou name="PRG_Main" pouType="program">
  <interface><localVars>
   <variable name="cil1"><type><derived name="FB_Cil"/></type></variable>
   <variable name="cil2"><type><derived name="FB_Cil"/></type></variable>
  </localVars></interface>
  <body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">cil1(xAv := GVL.xStart); cil2(xAv := GVL.xStart);</xhtml></ST></body></pou>
</pous></types>
<instances><configurations><configuration name="D"><resource name="A">
 <globalVars name="GVL"><variable name="xStart"><type><BOOL/></type></variable></globalVars>
</resource></configuration></configurations></instances></project>"""
    linhas, _, proj = a.analisar_projeto_universal(_arquivo_temp(xml))
    por_nome = {r["pou"]: r for r in linhas}
    assert por_nome["FB_Cil"]["metodos"] == 1
    assert por_nome["PRG_Main"]["globais_referenciadas"] == 1
    assert por_nome["FB_Cil"]["globais_referenciadas"] == 0
    assert proj["fbs_instanciados"] == 1 and proj["fbs_reutilizados"] == 1
    assert proj["perc_parametrizaveis"] == 50.0 and proj["perc_autocontidas"] == 50.0
    # contagem das classificações (3 unidades de 1 SLOC, sem comentários, 1 FB com 1 método)
    assert (proj["mod_adequada"], proj["mod_atencao"], proj["mod_desfavoravel"]) == (3, 0, 0)
    assert (proj["reu_adequada"], proj["reu_atencao"], proj["reu_desfavoravel"]) == (0, 0, 3)
    assert (proj["metodos_adequada"], proj["metodos_atencao"], proj["fbs_metodos_desfavoravel"]) == (1, 0, 0)


def test_array_de_fb_e_chamadas_de_funcao_contam_como_reuso():
    xml = """<?xml version="1.0"?>
<project xmlns="http://www.plcopen.org/xml/tc6_0200"><types><pous>
 <pou name="FB_Linha" pouType="functionBlock"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">x := 1;</xhtml></ST></body></pou>
 <pou name="FB_Tanque" pouType="functionBlock"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">y := 1;</xhtml></ST></body></pou>
 <pou name="FC_Escala" pouType="function"><body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">FC_Escala := 0.0;</xhtml></ST></body></pou>
 <pou name="PRG_Main" pouType="program">
  <interface><localVars>
   <variable name="aLinhas"><type><array><dimension lower="1" upper="GVL_Main.C_N"/><baseType><derived name="FB_Linha"/></baseType></array></type></variable>
   <variable name="fbTanque"><type><derived name="FB_Tanque"/></type></variable>
  </localVars></interface>
  <body><ST><xhtml xmlns="http://www.w3.org/1999/xhtml">a := FC_Escala(1); b := FC_Escala(2);</xhtml></ST></body></pou>
</pous></types>
<instances><configurations><configuration name="D"><resource name="A">
 <globalVars name="GVL_Main" constant="true"><variable name="C_N"><type><INT/></type><initialValue><simpleValue value="4"/></initialValue></variable></globalVars>
</resource></configuration></configurations></instances></project>"""
    _, _, proj = a.analisar_projeto_universal(_arquivo_temp(xml))
    info = a.extrair_info_projeto(_arquivo_temp(xml))
    assert info["instancias"] == {"FB_LINHA": 4, "FB_TANQUE": 1}   # ARRAY [1..C_N] com C_N = 4
    assert proj["fbs_reutilizados"] == 1
    assert proj["funcoes"] == 1 and proj["funcoes_reutilizadas"] == 1   # 2 chamadas
