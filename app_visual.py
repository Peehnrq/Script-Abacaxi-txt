import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import os
import time
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin
from unidecode import unidecode

# =================================================================
# CLASSE COM A LÓGICA DE PROCESSAMENTO (APENAS DOWNLOAD)
# =================================================================
class ProcessadorDeImagens:
    def __init__(self, app_gui):
        """Inicializa o processador com uma referência à interface gráfica."""
        self.gui = app_gui

        # Caminho de destino definido para a sua pasta específica
        self.PASTA_IMAGENS_BAIXADAS = r"C:\Users\User\Desktop\scripts-Pineapple Co\script-sku\imagens-sku"

    def log(self, message):
        """Envia uma mensagem de log para a caixa de texto da interface."""
        if self.gui:
            self.gui.log_message(message)

    def limpar_nome(self, nome):
        """Remove caracteres inválidos para nomes de pasta."""
        nome = unidecode(nome)
        nome = re.sub(r'[\\/*?:"<>|]', "", nome)
        return nome.strip()

    def baixar_imagem(self, url, pasta, nome_arquivo):
        """Baixa uma única imagem da URL fornecida."""
        try:
            response = requests.get(url, stream=True, timeout=15)
            if response.status_code == 200:
                caminho = os.path.join(pasta, nome_arquivo)
                with open(caminho, 'wb') as f:
                    f.write(response.content)
                return True
            self.log(f"   -> Falha no download (Status: {response.status_code}): {url}")
            return False
        except Exception as e:
            self.log(f"   -> Erro ao baixar imagem: {e}")
            return False

    def iniciar_processo_completo(self, lista_skus):
        self.log("--- INICIANDO DOWNLOAD DAS IMAGENS ---")
        self.log(f"Destino dos downloads: {self.PASTA_IMAGENS_BAIXADAS}")
        os.makedirs(self.PASTA_IMAGENS_BAIXADAS, exist_ok=True)

        options = Options()
        options.add_argument("--headless"); options.add_argument("--disable-gpu"); options.add_argument("--log-level=3"); options.add_argument("--no-sandbox"); options.add_argument("--disable-dev-shm-usage")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        navegador, skus_com_erro = None, []
        try:
            navegador = webdriver.Chrome(options=options)
            total_skus = len(lista_skus)
            for i, sku in enumerate(lista_skus, 1):
                self.log(f"\n[{i}/{total_skus}] Processando SKU: {sku}")
                try:
                    url_busca = f"https://www.shop-pineapple.co/buscar?q={sku}"
                    navegador.get(url_busca); time.sleep(2)
                    soup = BeautifulSoup(navegador.page_source, "html.parser")
                    a = soup.select_one("div#listagemProdutos ul[data-produtos-linha] li.span3 a")
                    if not a:
                        self.log(f"❌ Produto não encontrado para o SKU: {sku}"); skus_com_erro.append(sku); continue
                    titulo = self.limpar_nome(a["title"])
                    link_produto = urljoin(url_busca, a["href"])
                    self.log(f"➡️  Encontrado: {titulo}")
                    navegador.get(link_produto); time.sleep(2)
                    soup_produto = BeautifulSoup(navegador.page_source, "html.parser")
                    pasta_produto = os.path.join(self.PASTA_IMAGENS_BAIXADAS, f"{sku}_{titulo}")
                    os.makedirs(pasta_produto, exist_ok=True)
                    imagens_urls = []
                    img_principal = soup_produto.select_one("img#imagemProduto")
                    if img_principal and img_principal.get("src"): imagens_urls.append(img_principal["src"])
                    for thumb in soup_produto.select("ul.miniaturas li a[data-imagem-grande]"):
                        url_img = thumb.get("data-imagem-grande")
                        if url_img and url_img not in imagens_urls: imagens_urls.append(url_img)
                    if not imagens_urls: self.log("- Nenhuma imagem encontrada na página do produto."); continue
                    self.log(f"- Baixando {len(imagens_urls)} imagem(ns)...")
                    for idx, url_img in enumerate(imagens_urls, 1): self.baixar_imagem(url_img, pasta_produto, f"img_{idx}.jpg")
                except Exception as e:
                    self.log(f"❌ Erro inesperado no SKU {sku}: {e}"); skus_com_erro.append(sku)
        finally:
            if navegador: navegador.quit()
            # A etapa de redimensionamento foi removida.
            if skus_com_erro:
                with open("skus_com_erro.txt", "w", encoding='utf-8') as f: f.write("\n".join(skus_com_erro))
            sucessos = len(lista_skus) - len(skus_com_erro)
            self.log("\n================= RESUMO FINAL =================")
            self.log("🎉 Processo concluído!")
            self.log(f"✅ {sucessos} SKUs processados com sucesso.")
            if skus_com_erro: self.log(f"❌ {len(skus_com_erro)} SKUs falharam. Verifique o arquivo 'skus_com_erro.txt'.")
            self.log("==============================================")
            if self.gui: self.gui.finalizar_processo()

# =================================================================
# CLASSE DA INTERFACE GRÁFICA (Tkinter)
# =================================================================
class AppGUI:
    def __init__(self, root):
        self.root = root
        root.title("Downloader de Imagens Pineapple")
        root.geometry("750x600")

        frame = tk.Frame(root, padx=15, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Novo campo para inserir SKUs
        self.lbl_skus = tk.Label(frame, text="1. Cole os SKUs abaixo (um por linha):", font=("Helvetica", 10))
        self.lbl_skus.pack(fill=tk.X, pady=(0, 5))

        self.sku_input_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=10, font=("Courier New", 9))
        self.sku_input_area.pack(fill=tk.BOTH, expand=True)
        self.sku_input_area.focus() # Foco inicial no campo de texto

        self.btn_iniciar = tk.Button(frame, text="2. Iniciar Download", command=self.iniciar_thread_processo, font=("Helvetica", 10, "bold"), bg="#4CAF50", fg="white")
        self.btn_iniciar.pack(fill=tk.X, pady=10, ipady=5)

        self.log_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=15, font=("Courier New", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True)

        self.processor = ProcessadorDeImagens(self)
        self.log_message("Bem-vindo! Cole os SKUs no campo acima e inicie o download.")

    def log_message(self, message):
        """Adiciona uma mensagem à área de log de forma segura."""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def iniciar_thread_processo(self):
        """Inicia a tarefa pesada em uma thread separada para não travar a GUI."""
        # Pega os SKUs do novo campo de texto
        skus_raw = self.sku_input_area.get("1.0", tk.END)
        skus = [linha.strip() for linha in skus_raw.splitlines() if linha.strip()]

        if not skus:
            messagebox.showwarning("Aviso", "O campo de SKUs está vazio. Nenhum processo será iniciado.")
            return

        self.btn_iniciar.config(state=tk.DISABLED, text="Processando...")
        self.sku_input_area.config(state=tk.DISABLED)
        self.log_area.delete(1.0, tk.END)

        thread = threading.Thread(target=self.processor.iniciar_processo_completo, args=(skus,))
        thread.daemon = True
        thread.start()

    def finalizar_processo(self):
        """É chamado pela classe processadora para reativar a GUI."""
        self.btn_iniciar.config(state=tk.NORMAL, text="2. Iniciar Download")
        self.sku_input_area.config(state=tk.NORMAL)
        messagebox.showinfo("Concluído", "O processo foi finalizado! Verifique o log para mais detalhes.")

# --- PONTO DE ENTRADA PRINCIPAL PARA EXECUTAR A APLICAÇÃO ---
if __name__ == "__main__":
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()