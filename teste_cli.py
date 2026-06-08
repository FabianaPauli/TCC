import os
from core.xml_engine import extrair_pous_do_xml

def testar_analisador_completo():
    # Atualizado para o caminho do arquivo que você está testando
        # Adicione o "XML/" antes do nome do arquivo para o Python entrar na pasta correta
    #caminho_do_arquivo = "XML/8_S500B_V2.1.xml"  # caminho padrão para o XML de entrada
    caminho_do_arquivo = "XML/Untitled2.xml"  # outro arquivo XML possível
    #caminho_do_arquivo = "XML/OSC_MQTT.xml"  # outro arquivo XML possível
    #caminho_do_arquivo = "XML/addition.xml"  # outro arquivo XML possível
    #caminho_do_arquivo = "XML/StructuredText.xml"  # outro arquivo XML possível

    if not os.path.exists(caminho_do_arquivo):
        print(f"\n[ERRO] O arquivo '{caminho_do_arquivo}' NÃO foi encontrado!")
        return

    print(f"🔄 Analisando e Processando Métricas Complexas: {caminho_do_arquivo}")
    print("-" * 106)
    print(f"{'POU Name':<25} | {'LOC':<5} | {'McCabe':<6} | {'Cognitive':<9} | {'Halstead Vol':<13} | {'Dificuldade':<11} | {'Esforço (E)':<12}")
    print("-" * 106)

    try:
        pous_processadas = extrair_pous_do_xml(caminho_do_arquivo)
        
        for pou in pous_processadas:
            if pou["status"] == "OK":
                print(
                    f"{pou['nome']:<25} | {pou['loc']:<5} | {pou['mccabe']:<6} | {pou['cognitiva']:<9} | "
                    f"{pou['vol']:<13.1f} | {pou['dif']:<11.1f} | {pou['esf']:<12.1f}"
                )
            else:
                print(f"{pou['nome']:<25} | {pou['status']}")
                
        print("-" * 106)
        print(f"✅ Varredura concluída. Total de POUs analisadas: {len(pous_processadas)}")

    except Exception as e:
        print(f"\n[ERRO CRÍTICO NO PROCESSAMENTO]: {e}")

if __name__ == "__main__":
    testar_analisador_completo()