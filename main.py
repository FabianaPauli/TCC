import tkinter as tk
from app_gui import XMLParserApp

def main():
    # Inicializa a janela do Tkinter
    janela_principal = tk.Tk()
    
    # Instancia a nossa aplicação visual
    app = XMLParserApp(janela_principal)
    
    # Inicia o loop da interface gráfica
    janela_principal.mainloop()

if __name__ == "__main__":
    main()