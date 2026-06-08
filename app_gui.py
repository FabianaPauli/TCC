import tkinter as tk
from tkinter import filedialog, messagebox
# Importa a função lógica do nosso pacote core
from core.xml_engine import extrair_pous_do_xml

class XMLParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Parser PLCopen XML - Arquitetura Separada")
        self.root.geometry("650x450")
        
        # Elementos visuais
        self.label_instrucao = tk.Label(root, text="Selecione o arquivo PLCopen XML:", font=("Arial", 11))
        self.label_instrucao.pack(pady=15)
        
        self.btn_carregar = tk.Button(root, text="Selecionar Arquivo XML", command=self.selecionar_arquivo, bg="#1976D2", fg="white", font=("Arial", 10, "bold"))
        self.btn_carregar.pack(pady=5)
        
        self.txt_log = tk.Text(root, height=15, width=75, font=("Consolas", 10))
        self.txt_log.pack(pady=15)
        
    def selecionar_arquivo(self):
        caminho_arquivo = filedialog.askopenfilename(
            title="Abrir arquivo PLCopen XML",
            filetypes=[("Arquivos XML", "*.xml")]
        )
        
        if caminho_arquivo:
            self.txt_log.delete("1.0", tk.END)
            self.txt_log.insert(tk.END, f"Arquivo: {caminho_arquivo}\n\n")
            
            try:
                # CHAMADA DA LÓGICA EXTERNA
                pous = extrair_pous_do_xml(caminho_arquivo)
                
                # Atualiza a tela com o resultado que a lógica devolveu
                for pou in pous:
                    self.txt_log.insert(tk.END, f" POU: {pou['nome']:<25} | Tipo: {pou['tipo']}\n")
                    
                messagebox.showinfo("Sucesso", f"{len(pous)} POUs processadas com sucesso!")
                
            except Exception as e:
                messagebox.showerror("Erro de Processamento", str(e))