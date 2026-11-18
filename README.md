# Analisador de métricas de manutenibilidade para Texto Estruturado (IEC 61131-3)

Repositório do Trabalho de Conclusão de Curso **"Análise Estática em Lógicas de Controladores Lógicos Programáveis Baseada em Python e PLCopen XML"**, do Bacharelado em Engenharia de Software da Universidade da Região de Joinville (Univille).

- **Autora:** Fabiana Detroz Pauli
- **Orientadora:** Chaiene Mercedes da Silva Minella

A ferramenta lê projetos de CLP exportados em **PLCopen XML (TC6)**, extrai métricas de complexidade do código em **Texto Estruturado (ST)** e classifica cada unidade de código pelas cinco subcaracterísticas de manutenibilidade da **ISO/IEC 25010**: testabilidade, analisabilidade, modificabilidade, modularidade e reusabilidade.

## Métricas calculadas

| Subcaracterística | Métrica | Critério |
|---|---|---|
| Testabilidade | Complexidade Ciclomática de McCabe (forma clássica) | Adequada ≤ 10; Atenção 11–15; Desfavorável > 15 (Verdugo et al., 2024) |
| Analisabilidade | Complexidade Cognitiva; duplicação | Cognitiva ≤ 15 / > 15 (SonarQube; Barón, Wyrich e Wagner, 2020); duplicação < 4% / 4–7% / ≥ 7% (Verdugo et al., 2024) |
| Modificabilidade | Halstead (Volume, Dificuldade, Esforço); duplicação | Halstead: comparação relativa |
| Modularidade | SLOC por unidade; métodos por FB; acoplamento por variáveis globais | SLOC 1–15 / 16–30 / > 30; métodos ≤ 12 / 13–18 / > 18 (Verdugo et al., 2024); acoplamento: relativo |
| Reusabilidade | Densidade de comentários; % de FBs e funções; unidades sem globais; FBs e funções reutilizados | Comentários 22–50% / 10–22% ou 50–60% / demais (Verdugo et al., 2024); demais: relativos |

Uma unidade é **gargalo** quando é desfavorável em McCabe **ou** na Cognitiva, e **gargalo crítico** quando é desfavorável nas duas. A forma estendida de McCabe (que soma também cada AND e OR) é exportada no CSV apenas para comparação.

## Requisitos

- Python **3.10** ou superior.
- O analisador usa apenas a biblioteca padrão do Python; não é preciso instalar nada para executá-lo.
- Para rodar os testes, é preciso o `pytest` (listado em `requirements.txt`).

## Como executar

Na pasta do repositório:

```bash
# todos os projetos da amostra, gerando os CSVs na pasta resultados/
python analisador_metricas_st.py xml/1_tanque_mistura xml/2_linha_smt xml/3_envasadora --csv resultados/resultados.csv

# um único arquivo
python analisador_metricas_st.py xml/1_tanque_mistura/OpenAI1.xml

# tabela compacta (usada nas figuras do artigo)
python analisador_metricas_st.py xml/3_envasadora --compacto
```

Sem argumentos, o script analisa as três pastas da amostra e grava `resultados/resultados.csv`.

São gerados dois arquivos (separador `;` e vírgula decimal, prontos para abrir no Excel em português):

- `resultados.csv`: uma linha por unidade de código, com todas as métricas e classificações;
- `resultados_projeto.csv`: uma linha por projeto, com duplicação, acoplamento médio e máximo, percentual de FBs e funções (`perc_parametrizaveis`), percentual de unidades sem variáveis globais (`perc_autocontidas`) e FBs e funções reutilizados.

## Como rodar os testes

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python -m pytest -v
```

Os 29 testes unitários verificam regras como comentários aninhados, rótulos de CASE, operadores lógicos, literais tipados, variáveis globais, instâncias de FBs (inclusive em vetores) e duplicação.

## Estrutura do repositório

```
analisador_metricas_st.py        ferramenta de análise
test_analisador_metricas_st.py   testes unitários (pytest)
requirements.txt                 dependência dos testes
xml/
  1_tanque_mistura/              especificação 1 (Claude1, DeepSeek1, OpenAI1)
  2_linha_smt/                   especificação 2 (Claude2, DeepSeek2, OpenAI2)
  3_envasadora/                  especificação 3 (Claude3, DeepSeek3, OpenAI3)
prompts/                         especificações funcionais e prompts enviados aos assistentes
projetos_codesys/                projetos CODESYS V3.5 SP20 gerados a partir do código dos assistentes
resultados/                      CSVs exportados pelo analisador
validacao/                       cálculo manual da especificação 1, usado para validar a ferramenta
```

## Amostra

Nove projetos: três especificações de máquinas (tanque de mistura, linha de montagem de placas eletrônicas SMT e envasadora de líquidos), cada uma gerada uma única vez por três assistentes de IA em planos gratuitos (Claude, ChatGPT e DeepSeek), a partir de prompts idênticos. Os projetos foram compilados e simulados no CODESYS V3.5 SP20 e exportados em PLCopen XML (TC6).

## Validação

Os 30 valores calculados manualmente para a especificação 1 (10 métricas × 3 programas) coincidem com a saída do analisador. O passo a passo está em `validacao/`.

## Limitações

- Lê apenas código em ST; LD, FBD e SFC não são analisados.
- Os limiares vêm de linguagens de propósito geral e não foram calibrados para ST.
- As métricas não verificam a correção funcional do programa.
