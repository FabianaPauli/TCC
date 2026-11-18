# Projetos CODESYS

Esta pasta contém os nove projetos CODESYS montados com o código em Texto Estruturado (ST) gerado pelos assistentes de IA. Cada projeto foi compilado e simulado no CODESYS e, em seguida, exportado em PLCopen XML (TC6) para a pasta `xml/`, que é a entrada do analisador.

## Arquivos

| Especificação | Máquina | Claude | ChatGPT (OpenAI) | DeepSeek |
|---|---|---|---|---|
| 1 | Tanque de mistura | `Claude1.project` | `OpenAI1.project` | `DeepSeek1.project` |
| 2 | Linha de montagem de placas eletrônicas (SMT) | `Claude2.project` | `OpenAI2.project` | `DeepSeek2.project` |
| 3 | Envasadora de líquidos | `Claude3.project` | `OpenAI3.project` | `DeepSeek3.project` |

Cada `.project` corresponde ao XML de mesmo nome em `xml/` (por exemplo, `Claude2.project` → `xml/2_linha_smt/Claude2.xml`).

## Como abrir

- **Software:** CODESYS V3.5 SP20.
- **Dispositivo:** CODESYS Control Win V3 (controlador de simulação, sem hardware).
- **Bibliotecas:** apenas a biblioteca Standard do CODESYS (temporizadores TON, detecção de borda R_TRIG e similares); os prompts proibiam bibliotecas proprietárias.

Para executar: abra o projeto, compile (**Compilar > Gerar código**), entre no modo de simulação (**Online > Simulação**), faça login e inicie a aplicação.

Se o CODESYS informar que falta alguma biblioteca ou a descrição do dispositivo, use o **Gerenciador de bibliotecas** ou o **Repositório de dispositivos** para instalar a versão indicada.

## Ajustes feitos no código gerado

O código dos assistentes foi mantido como gerado, sem alterar a lógica:

## Como exportar o PLCopen XML

No CODESYS, selecione a aplicação na árvore do projeto e use **Projeto > Exportar PLCopenXML…**.
