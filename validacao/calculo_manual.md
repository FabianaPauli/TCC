# Cálculo manual da especificação 1 (validação do analisador)

Este documento valida o analisador comparando, para os três programas da especificação 1 (tanque de mistura), os valores calculados à mão com os valores exportados pela ferramenta. A especificação 1 foi escolhida por ter uma única POU por assistente, o que permite contar cada métrica linha a linha.

**Resultado: os 30 valores calculados manualmente (10 métricas × 3 programas) são idênticos aos da ferramenta.**

## Como o cálculo foi feito

- **Código analisado:** o corpo em ST do `PLC_PRG` de cada XML em `xml/1_tanque_mistura/` (DeepSeek1, Claude1 e OpenAI1), sem as declarações de variáveis. A linha 1 é a primeira linha do corpo; os números de linha citados abaixo seguem essa numeração.
- **Linhas:** LOC conta da primeira à última linha do corpo; SLOC exclui linhas em branco e linhas só de comentário; CLOC conta as linhas que têm comentário (inclusive as que também têm código).
- **McCabe (forma clássica):** cada IF, ELSIF, FOR, WHILE, REPEAT e rótulo de CASE é uma decisão; V(G) = decisões + 1. AND e OR não contam (no CODESYS não criam desvio); ELSE não conta.
- **Cognitiva:** IF, CASE, FOR, WHILE e REPEAT valem 1 + nível de aninhamento; ELSIF e ELSE de IF valem 1; ELSE de CASE e NOT valem 0; cada sequência de operadores lógicos iguais vale 1.
- **Halstead:** operadores são símbolos (`;`, `:=`, `+`…), palavras reservadas e chamadas de funções e FBs (parênteses e colchetes contam uma vez por par); operandos são variáveis, constantes e literais. V = N · log₂(n), D = (n1/2) · (N2/n2) e E = D · V.

## Resultado final: manual = ferramenta

| Métrica | DeepSeek1 | Claude1 | OpenAI1 |
| --- | --- | --- | --- |
| LOC | 56 | 71 | 60 |
| SLOC | 49 | 55 | 45 |
| CLOC | 0 | 10 | 0 |
| McCabe | 10 | 12 | 10 |
| Cognitiva | 17 | 17 | 15 |
| n1 / n2 | 27 / 28 | 29 / 28 | 28 / 27 |
| N1 / N2 | 128 / 96 | 133 / 100 | 113 / 83 |
| Volume | 1295,02 | 1359,06 | 1133,15 |
| Dificuldade | 46,29 | 51,79 | 43,04 |
| Esforço | 59 941,14 | 70 380,07 | 48 767,27 |

---

## Códigos analisados

Os três programas estão nos arquivos `xml/1_tanque_mistura/DeepSeek1.xml`, `Claude1.xml` e `OpenAI1.xml`. No Claude1, as entidades `-&gt;`, `&lt;` e `&gt;` do XML foram decodificadas para `->`, `<` e `>` antes da contagem, como faz o analisador.

---

## 1. Linhas de código

| Medida | DeepSeek1 | Claude1 | OpenAI1 |
| --- | --- | --- | --- |
| LOC (1ª a última linha) | 56 | 71 | 60 |
| Linhas em branco | 7 (2, 10, 15, 21, 30, 40, 50) | 9 (3, 9, 15, 21, 33, 41, 51, 60, 68) | 15 (2, 6, 8, 10, 14, 16, 24, 26, 30, 34, 38, 44, 48, 53, 58) |
| Só comentário | 0 | 7 (1, 10, 22, 24, 31, 62, 69) | 0 |
| Código + comentário | 0 | 3 (34, 42, 52) | 0 |
| **CLOC** = só comentário + misto | **0** | **10** | **0** |
| **SLOC** = LOC − brancas − só comentário | 56 − 7 = **49** | 71 − 9 − 7 = **55** | 60 − 15 = **45** |

No Claude1, as linhas 34, 42 e 52 (`0: (* IDLE *)`) têm código e comentário na mesma linha. Por isso contam ao mesmo tempo em SLOC e em CLOC.

---

## 2. Complexidade Ciclomática de McCabe

**Fórmula:** V(G) = pontos de decisão + 1

| Ponto de decisão | DeepSeek1 | Claude1 | OpenAI1 |
| --- | --- | --- | --- |
| IF | 4 (3, 27, 34, 45) | 5 (4, 23, 38, 45, 55) | 4 (17, 31, 39, 49) |
| ELSIF | 0 | 1 (6) | 0 |
| FOR | 2 (11, 17) | 2 (11, 17) | 2 (3, 11) |
| Rótulos do CASE | 3 (23, 31, 41) | 3 (34, 42, 52) | 3 (27, 35, 45) |
| AND / OR | 0 | 0 | 0 |
| ELSE (IF e CASE) | não conta | não conta | não conta |
| **Decisões** | 9 | 11 | 9 |
| **V(G)** | **10** | **12** | **10** |

O Claude1 fica 2 pontos acima porque tem o IF/ELSIF das linhas 4–8, que limita a temperatura entre 0 e 150. No OpenAI1, o `(i_State = 2)` da linha 23 é uma comparação usada como valor e não desvia o fluxo, então não conta como decisão.

---

## 3. Complexidade Cognitiva

**Regras:**

- IF, FOR e CASE valem +1 mais o nível de aninhamento.
- ELSIF e ELSE de IF valem +1.
- ELSE de CASE e NOT valem 0.

| Construção | DeepSeek1 | Claude1 | OpenAI1 |
| --- | --- | --- | --- |
| IF de limitação da faixa | — | L4: +1 (nível 0) | — |
| ELSIF | — | L6: +1 | — |
| 1º FOR (deslocamento) | L11: **+2** (nível 1) | L11: +1 (nível 0) | L3: +1 (nível 0) |
| 2º FOR (soma) | L17: **+2** (nível 1) | L17: +1 (nível 0) | L11: +1 (nível 0) |
| IF de emergência | L3: +1 | L23: +1 | L17: +1 |
| ELSE desse IF | L8: +1 | L30: +1 | L22: +1 |
| CASE (dentro do ELSE) | L22: +2 (nível 1) | L32: +2 | L25: +2 |
| IF do estado 0 | L27: +3 (nível 2) | L38: +3 | L31: +3 |
| IF do estado 1 | L34: +3 | L45: +3 | L39: +3 |
| IF do estado 2 | L45: +3 | L55: +3 | L49: +3 |
| ELSE do CASE / NOT | 0 | 0 | 0 |
| **Total** | **17** | **17** | **15** |

O DeepSeek1 e o Claude1 chegam a 17 por caminhos diferentes:

- **DeepSeek1:** colocou os dois FOR dentro do ELSE. O aninhamento faz cada um valer 2 em vez de 1.
- **Claude1:** deixou os FOR no nível 0, mas acrescentou o IF/ELSIF de limitação, que soma 2.
- **OpenAI1:** tem a mesma estrutura do Claude1 sem essa limitação, por isso fica em 15.

---

## 4. Halstead

### 4.1 Operadores

| Operador | DeepSeek1 | Claude1 | OpenAI1 |
| --- | --- | --- | --- |
| `;` | 37 | 41 | 33 |
| `:=` (atribuições + parâmetros `IN :=`/`PT :=`) | 37 (27 + 10) | 37 (33 + 4) | 30 (26 + 4) |
| `IF` | 4 | 5 | 4 |
| `THEN` | 4 | 6 | 4 |
| `END_IF` | 4 | 5 | 4 |
| `ELSIF` | — | 1 | — |
| `ELSE` | 2 | 2 | 2 |
| `CASE` · `OF` · `END_CASE` | 1 · 1 · 1 | 1 · 1 · 1 | 1 · 1 · 1 |
| `:` (rótulo) | 3 | 3 | 3 |
| `FOR` · `TO` · `DO` · `END_FOR` | 2 · 2 · 2 · 2 | 2 · 2 · 2 · 2 | 2 · 2 · 2 · 2 |
| `BY` | 1 | 1 | 1 |
| `NOT` | 1 | 1 | 1 |
| `[]` | 4 | 4 | 4 |
| `()` (agrupamento) | 1 | 1 | 2 (L1, L23) |
| `.` (acesso `.Q`) | 1 | 1 | 1 |
| `,` | 5 | 2 | 2 |
| `+` · `*` | 1 · 1 | 1 · 1 | 1 · 1 |
| `-` (`BY -1` e `idx - 1`) | 2 | 2 | 2 |
| `/` | 2 | 2 | 2 |
| `<` | — | 1 | — |
| `>` | 1 | 2 | 1 |
| `=` | — | — | 1 (L23) |
| `INT_TO_REAL()` | 1 | 1 | 1 |
| Chamada do TON (`fbMixTimer()`/`tmrMix()`) | 5 | 2 | 2 |
| **n1 (distintos)** | **27** | **29** | **28** |
| **N1 (total)** | **128** | **133** | **113** |

As linhas com `;` são estas:

- **Claude1:** 2, 5, 7–8, 12–14, 16, 18–20, 25–29, 35–37, 39–40, 43–44, 46–50, 53–54, 56–59, 63–67, 70–71.
- **OpenAI1:** 1, 4–5, 7, 9, 12–13, 15, 18–21, 23, 28–29, 32–33, 36–37, 40–43, 46–47, 50–52, 55–57, 59–60.

### 4.2 Operandos

Os nomes das variáveis mudam entre os códigos, então a tabela agrupa pelo papel de cada uma.

| Operando (papel) | DeepSeek1 | Claude1 | OpenAI1 |
| --- | --- | --- | --- |
| FALSE | 13 | 15 | 11 |
| TRUE | 5 | 4 | 3 |
| Saída do aquecedor `o_bHeater` | 6 | 6 | 6 |
| Saída do misturador `o_bMixer` | 7 | 7 | 7 |
| Estado (`i_State` / `iState`) | 6 | 6 | 7 |
| Índice (`i_Index` / `iIdx`) | 5 | 5 | 5 |
| Histórico (`a_rTempHistory` / `aTempHist`) | 4 | 4 | 4 |
| Soma (`r_SumTemp` / `rSum` / `r_Sum`) | 4 | 4 | 4 |
| Temperatura convertida (`r_TempConverted` / `rTempScaled` / `r_Temp`) | 2 | 6 | 2 |
| `o_rAvgTemp` | 2 | 2 | 2 |
| `b_EmergencyStop` | 2 | — | — |
| `bTmrEnable` | — | 6 | — |
| `i_bStop` · `i_bStart` · `i_wTempSensor` | 1 · 1 · 1 | 1 · 1 · 1 | 1 · 1 · 1 |
| Instância do TON (em `.Q`) · `Q` | 1 · 1 | 1 · 1 | 1 · 1 |
| `IN` · `PT` · `T#10S` | 5 · 5 · 5 | 2 · 2 · 2 | 2 · 2 · 2 |
| `0` | 4 | 6 | 6 |
| `1` | 6 | 5 | 5 |
| `2` | 3 | 2 | 3 |
| `4` | — | 2 | 2 |
| `5` | 2 | — | — |
| `0.0` | 1 | 3 | 1 |
| `150.0` | 1 | 3 | 1 |
| `5.0` · `80.0` · `27648.0` | 1 · 1 · 1 | 1 · 1 · 1 | 1 · 1 · 1 |
| **n2 (distintos)** | **28** | **28** | **27** |
| **N2 (total)** | **96** | **100** | **83** |

Para conferir as contagens maiores, estas são as linhas de cada ocorrência:

- **FALSE no Claude1:** 26, 27, 28, 29, 35, 36, 37, 44, 46, 53, 56, 57, 63, 64, 65.
- **FALSE no OpenAI1:** 19, 20, 21, 28, 29, 37, 40, 46, 50, 56, 57.
- **Literal `1` no Claude1:** L11 duas vezes (`TO 1` e `1`), L12, L39 e L42 (rótulo).
- **Literal `1` no OpenAI1:** L3 duas vezes, L4, L32 e L35.

### 4.3 Cálculo final

| Medida | Fórmula | DeepSeek1 | Claude1 | OpenAI1 |
| --- | --- | --- | --- | --- |
| Vocabulário | n = n1 + n2 | 55 | 57 | 55 |
| Comprimento | N = N1 + N2 | 224 | 233 | 196 |
| log₂ n |  | 5,7814 | 5,8329 | 5,7814 |
| **Volume** | V = N · log₂ n | **1295,02** | **1359,06** | **1133,15** |
| n1 / 2 |  | 13,5 | 14,5 | 14,0 |
| N2 / n2 |  | 3,4286 | 3,5714 | 3,0741 |
| **Dificuldade** | D = (n1/2) · (N2/n2) | **46,29** | **51,79** | **43,04** |
| **Esforço** | E = D · V | **59 941,14** | **70 380,07** | **48 767,27** |

---

## Como conferir com a ferramenta

Na pasta do repositório:

```bash
python analisador_metricas_st.py xml/1_tanque_mistura --csv resultados/especificacao1.csv
```

As colunas `loc`, `sloc`, `cloc`, `mccabe`, `cognitiva`, `n1`, `n2`, `N1`, `N2`, `volume`, `dificuldade` e `esforco` do CSV devem coincidir com a tabela "Resultado final".
