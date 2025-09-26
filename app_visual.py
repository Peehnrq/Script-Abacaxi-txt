import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
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
from PIL import Image

# =================================================================
# CLASSE COM A LÓGICA DE PROCESSAMENTO (DOWNLOAD E REDIMENSIONAMENTO)
# =================================================================
class ProcessadorDeImagens:
    def __init__(self, app_gui):
        """Inicializa o processador com uma referência à interface gráfica."""
        self.gui = app_gui

        # MODIFICAÇÃO: Caminhos de destino fixos conforme solicitado.
        # Usa os.path.expanduser('~') para encontrar a pasta do usuário dinamicamente
        # e garantir que funcione para qualquer usuário.
        base_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'script-txt')
        self.PASTA_IMAGENS_BAIXADAS = os.path.join(base_path, "imagens_pineapple")
        self.PASTA_IMAGENS_REDIMENSIONADAS = os.path.join(base_path, "imagens_redimensionadas")
        
        # Configurações do redimensionador (lógica original mantida)
        self.FUNDO_TAMANHO = (1080, 1080)
        self.LIMITE_TOPO = 272
        self.LIMITE_BASE = 808
        self.LIMITE_ESQUERDA = 204
        self.LIMITE_DIREITA = 877
    
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

    def crop_por_cor_de_fundo(self, imagem, tolerancia=245):
        """Sua função original para detectar margens brancas e cortar."""
        imagem = imagem.convert("RGB")
        pixels = imagem.load()
        largura, altura = imagem.size
        topo, base, esquerda, direita = 0, altura, 0, largura

        def eh_fundo(rgb):
            return all(v >= tolerancia for v in rgb)

        for y in range(altura):
            if any(not eh_fundo(pixels[x, y]) for x in range(largura)):
                topo = y; break
        for y in range(altura - 1, -1, -1):
            if any(not eh_fundo(pixels[x, y]) for x in range(largura)):
                base = y; break
        for x in range(largura):
            if any(not eh_fundo(pixels[x, y]) for y in range(altura)):
                esquerda = x; break
        for x in range(largura - 1, -1, -1):
            if any(not eh_fundo(pixels[x, y]) for y in range(altura)):
                direita = x; break
        return imagem.crop((esquerda, topo, direita + 1, base + 1))

    def redimensionar_imagens(self):
        """Sua lógica de redimensionamento original, integrada ao app."""
        self.log("\n--- INICIANDO ETAPA 2: REDIMENSIONAMENTO ---")
        if not os.path.exists(self.PASTA_IMAGENS_BAIXADAS):
            self.log(f"⚠️ Pasta de imagens baixadas não encontrada em '{self.PASTA_IMAGENS_BAIXADAS}'. Pulando esta etapa.")
            return

        largura_util = self.LIMITE_DIREITA - self.LIMITE_ESQUERDA
        altura_util = self.LIMITE_BASE - self.LIMITE_TOPO
        encontrou_imagem = False

        for root, _, arquivos in os.walk(self.PASTA_IMAGENS_BAIXADAS):
            for nome_arquivo in arquivos:
                if nome_arquivo.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    encontrou_imagem = True
                    self.log(f"   -> Processando: {nome_arquivo}")
                    try:
                        caminho_imagem = os.path.join(root, nome_arquivo)
                        imagem = Image.open(caminho_imagem)
                        imagem_crop = self.crop_por_cor_de_fundo(imagem, tolerancia=245)
                        proporcao = min(largura_util / imagem_crop.width, altura_util / imagem_crop.height)
                        nova_largura = int(imagem_crop.width * proporcao)
                        nova_altura = int(imagem_crop.height * proporcao)
                        imagem_redimensionada = imagem_crop.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
                        fundo = Image.new("RGB", self.FUNDO_TAMANHO, (255, 255, 255))
                        offset_x = self.LIMITE_ESQUERDA + (largura_util - nova_largura) // 2
                        offset_y = self.LIMITE_TOPO + (altura_util - nova_altura) // 2
                        fundo.paste(imagem_redimensionada, (offset_x, offset_y))
                        caminho_relativo = os.path.relpath(caminho_imagem, self.PASTA_IMAGENS_BAIXADAS)
                        caminho_destino = os.path.join(self.PASTA_IMAGENS_REDIMENSIONADAS, caminho_relativo)
                        os.makedirs(os.path.dirname(caminho_destino), exist_ok=True)
                        novo_nome = os.path.splitext(caminho_destino)[0] + ".jpg"
                        fundo.save(novo_nome, format="JPEG", quality=95)
                    except Exception as e:
                        self.log(f"   ❌ Erro com {nome_arquivo}: {e}")
        if not encontrou_imagem:
            self.log("⚠️ Nenhuma imagem válida foi encontrada para redimensionar.")
        else:
            self.log("🎉 Todas as imagens foram processadas com sucesso!")

    def iniciar_processo_completo(self, lista_skus):
        self.log("--- INICIANDO ETAPA 1: DOWNLOAD DAS IMAGENS ---")
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
            self.redimensionar_imagens()
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
        root.title("Processador de Imagens Pineapple")
        root.geometry("750x550")

        frame = tk.Frame(root, padx=15, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)

        self.btn_selecionar = tk.Button(frame, text="1. Selecionar Arquivo de SKUs (.txt)", command=self.selecionar_arquivo, font=("Helvetica", 10))
        self.btn_selecionar.pack(fill=tk.X, pady=5)

        self.lbl_arquivo = tk.Label(frame, text="Nenhum arquivo selecionado.", fg="blue", pady=5)
        self.lbl_arquivo.pack(fill=tk.X)

        self.btn_iniciar = tk.Button(frame, text="2. Iniciar Processamento", state=tk.DISABLED, command=self.iniciar_thread_processo, font=("Helvetica", 10, "bold"), bg="#4CAF50", fg="white")
        self.btn_iniciar.pack(fill=tk.X, pady=10, ipady=5)

        self.log_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20, font=("Courier New", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True)

        self.caminho_arquivo_sku = None
        self.processor = ProcessadorDeImagens(self)
        self.log_message("Bem-vindo! Por favor, selecione o arquivo 'skus.txt' para começar.")

    def selecionar_arquivo(self):
        caminho = filedialog.askopenfilename(title="Selecione o arquivo skus.txt", filetypes=[("Arquivos de Texto", "*.txt")])
        if caminho:
            self.caminho_arquivo_sku = caminho
            self.lbl_arquivo.config(text=f"Arquivo selecionado: {os.path.basename(caminho)}")
            self.btn_iniciar.config(state=tk.NORMAL)
            self.log_message(f"Arquivo '{os.path.basename(caminho)}' carregado com sucesso.")
            self.log_message("Clique em 'Iniciar Processamento' para continuar.")
    
    def log_message(self, message):
        """Adiciona uma mensagem à área de log de forma segura."""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def iniciar_thread_processo(self):
        """Inicia a tarefa pesada em uma thread separada para não travar a GUI."""
        if not self.caminho_arquivo_sku:
            messagebox.showerror("Erro", "Por favor, selecione um arquivo de SKUs primeiro.")
            return

        try:
            with open(self.caminho_arquivo_sku, 'r', encoding='utf-8') as f:
                skus = [linha.strip() for linha in f if linha.strip()]
            if not skus:
                messagebox.showwarning("Aviso", "O arquivo de SKUs está vazio. Nenhum processo será iniciado.")
                return
        except Exception as e:
            messagebox.showerror("Erro de Leitura", f"Não foi possível ler o arquivo de SKUs:\n{e}")
            return

        self.btn_iniciar.config(state=tk.DISABLED, text="Processando...")
        self.btn_selecionar.config(state=tk.DISABLED)
        self.log_area.delete(1.0, tk.END)

        thread = threading.Thread(target=self.processor.iniciar_processo_completo, args=(skus,))
        thread.daemon = True
        thread.start()

    def finalizar_processo(self):
        """É chamado pela classe processadora para reativar a GUI."""
        self.btn_iniciar.config(state=tk.NORMAL, text="2. Iniciar Processamento")
        self.btn_selecionar.config(state=tk.NORMAL)
        messagebox.showinfo("Concluído", "O processo foi finalizado! Verifique o log para mais detalhes.")

# --- PONTO DE ENTRADA PRINCIPAL PARA EXECUTAR A APLICAÇÃO ---
if __name__ == "__main__":
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()