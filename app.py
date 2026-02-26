import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import urllib.parse
import unicodedata
import cloudinary
import cloudinary.uploader
import io
import google.generativeai as genai
from PIL import Image
import requests
import time
import pytz

def verificar_status_odoo(codigo_produto):
    cod_limpo = str(codigo_produto).strip()
    url_busca = f"https://sweethomecomfort.odoo.com/shop?&search={cod_limpo}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resposta = requests.get(url_busca, headers=headers, timeout=10)
        conteudo = resposta.text.lower()
        
        # Validação rigorosa: se o código pesquisado não retorna produto
        if f'nenhum resultado para "{cod_limpo.lower()}"' in conteudo or "nenhum resultado encontrado" in conteudo:
            return False, ""
        
        if "oe_product" in conteudo or "o_wsale_products_item" in conteudo:
            return True, url_busca
        return False, ""
    except:
        return False, ""

# ==========================================
# 1. CONFIGURAÇÃO ÚNICA DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Sweet Home", 
    page_icon="logo_sweet.png", 
    layout="wide"
)

# Inicialização das Memórias de Sessão
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False
if 'historico_sessao' not in st.session_state:
    st.session_state['historico_sessao'] = []
if 'historico_estoque' not in st.session_state:
    st.session_state['historico_estoque'] = []
if 'carrinho' not in st.session_state:
    st.session_state['carrinho'] = []    
    
# --- AUXILIARES TÉCNICOS ---
def limpar_v(v):
    if pd.isna(v) or v == "": return 0.0
    numero = pd.to_numeric(str(v).replace('R$', '').replace('.', '').replace(',', '.').strip(), errors='coerce') or 0.0
    return round(numero, 2)

def limpar_texto(texto):
    if not isinstance(texto, str):
        return ""
    texto_sem_acento = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    return texto_sem_acento.lower().strip()

# ==========================================
# 🎨 1.5. IDENTIDADE VISUAL (SWEET CLEAN)
# ==========================================
estilo_sweet_clean = """
<style>
    /* 1. Tela Principal Branca com a Listra Café na Extrema Direita */
    [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
        border-right: 12px solid #31241b !important;
    }
    
    /* 2. Barra Lateral (Tom Areia Muito Claro) */
    [data-testid="stSidebar"] {
        background-color: #FCF8F2 !important;
        border-right: 1px solid #f6debc !important;
    }

    /* ✨ O EXORCISMO DA SETA FANTASMA ✨ */
    /* Pega a seta de abrir e a de fechar diretamente pelo código do Streamlit */
    [data-testid="collapsedControl"] svg, 
    [data-testid="collapsedControl"] path,
    [data-testid="stSidebar"] button svg,
    [data-testid="stSidebar"] button path {
        color: #31241b !important;
        fill: #31241b !important;
        stroke: #31241b !important;
    }

    /* Força os textos comuns a ficarem escuros (caso o navegador esteja no modo escuro) */
    .stMarkdown, p, span, label, div[data-testid="stMetricValue"] {
        color: #31241b !important;
    }

    /* 3. Títulos na cor Café Intenso */
    h1, h2, h3, h4 {
        color: #31241b !important;
    }

    /* 4. Botões Principais no tom Caramelo */
    .stButton>button {
        background-color: #A67B5B !important; 
        color: #ffffff !important;
        font-weight: bold !important;
        border-radius: 6px !important;
        border: none !important;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.1) !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    .stButton>button:hover {
        background-color: #8B5A2B !important;
        color: #ffffff !important;
        transform: scale(1.02);
    }
    
    /* Protege a letra do botão para continuar branca */
    .stButton>button p, .stButton>button span {
        color: #ffffff !important;
    }

    /* Limpeza do cabeçalho e rodapé */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background-color: transparent !important;}
</style>
"""
st.markdown(estilo_sweet_clean, unsafe_allow_html=True)

# ==========================================
# 🔒 2. FASE DE LOGIN & SEGURANÇA
# ==========================================
if not st.session_state['autenticado']:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        try:
            st.image("logo_sweet.png", use_container_width=True)
        except:
            st.warning("🌸 Sweet Home Enxovais")
        
        st.markdown("<h2 style='text-align: center;'>Gestão Sweet</h2>", unsafe_allow_html=True)

        with st.form("form_login"):
            usuario_input = st.text_input("Usuário").strip()
            senha_input = st.text_input("Senha", type="password").strip()
            entrar = st.form_submit_button("Entrar no Sistema 🚀", use_container_width=True)
            
            if entrar:
                try:
                    usuarios_permitidos = st.secrets["usuarios"]
                    if usuario_input in usuarios_permitidos:
                        if str(usuarios_permitidos[usuario_input]) == senha_input:
                            st.session_state['autenticado'] = True
                            st.session_state['usuario_logado'] = usuario_input
                            
                            # 💡 LINHA ESSENCIAL ADICIONADA: Ativa o registro na Fase 3
                            st.session_state['precisa_registrar_acesso'] = True
                            
                            st.rerun()
                        else:
                            st.error("❌ Senha incorreta.")
                    else:
                        st.error("❌ Usuário não encontrado.")
                except Exception as e:
                    st.error("Erro ao acessar cofre de senhas. Verifique os Secrets.")
    st.stop()

# ==========================================
# 🚀 3. SISTEMA LIBERADO (CONEXÕES E DADOS)
# ==========================================

# ID da Planilha Cobaia
ID_PLANILHA = "1E2NwI5WBE1iCjTWxpUxy3TYpiwKU6e4s4-C1Rp1AJX8"
ESPECIFICACOES = [
    "https://spreadsheets.google.com/feeds", 
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file"
]

# 👇 1. PRIMEIRO: O SISTEMA SE CONECTA AO GOOGLE E ABRE A PLANILHA (AGORA COM ESCUDO!)
@st.cache_resource
def conectar_google():
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, ESPECIFICACOES)
            return gspread.authorize(creds).open_by_key(ID_PLANILHA)
        return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        st.stop()

planilha_mestre = conectar_google()

# 👇 2. DEPOIS: O GATILHO RODA (Agora que a planilha_mestre já existe!)
# ====================================================
# 🤖 GATILHO DE REGISTRO (VERSÃO COM HORÁRIO DE RECIFE)
# ====================================================
if st.session_state.get('precisa_registrar_acesso'):
    try:
        aba_usuario = planilha_mestre.worksheet("USUARIO") 
        
        # --- CONFIGURAÇÃO DE FUSO HORÁRIO (RECIFE/BRASÍLIA) ---
        fuso_br = pytz.timezone('America/Sao_Paulo') 
        agora = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
        
        usuario_logado = st.session_state.get('usuario_logado')
        celula_nome = aba_usuario.find(usuario_logado)
        
        if celula_nome:
            cabecalhos = aba_usuario.row_values(1)
            if "ULTIMO_ACESSO" in cabecalhos:
                col_acesso = cabecalhos.index("ULTIMO_ACESSO") + 1
                aba_usuario.update_cell(celula_nome.row, col_acesso, agora)
                st.toast(f"Logado como {usuario_logado}. Ponto registrado! 🕒", icon="✅")
            
            # Desliga o sinalizador para não repetir o registro no próximo clique
            st.session_state['precisa_registrar_acesso'] = False 
            
    except Exception as e:
        # Erro discreto no log do servidor
        print(f"Erro ao registrar: {e}") 
        st.session_state['precisa_registrar_acesso'] = False
        
# ☁️ Função de Upload Rápido para Cloudinary (Nova Engine de Arquivos)
def upload_para_cloudinary(file_bytes, file_name, pasta_destino):
    try:
        # Puxa as senhas dos secrets
        cloudinary.config(
            cloud_name = st.secrets["cloudinary"]["cloud_name"],
            api_key = st.secrets["cloudinary"]["api_key"],
            api_secret = st.secrets["cloudinary"]["api_secret"],
            secure = True
        )
        
        # Cria as pastas virtuais automaticamente no CDN
        caminho_pasta = f"SweetHome/{pasta_destino}"
        
        resposta = cloudinary.uploader.upload(
            file_bytes,
            folder=caminho_pasta,
            public_id=file_name,
            resource_type="auto"
        )
        # Retorna o ID único e o link direto
        return resposta.get('public_id'), resposta.get('secure_url')
    except Exception as e:
        st.error(f"Erro no servidor de arquivos: {e}")
        return None, None

@st.cache_data(ttl=60) # Reduzir para 60 ajuda a manter o estoque mais fresco
def carregar_dados():
    if not planilha_mestre: 
        return {}, {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    def ler_aba_seguro(nome):
        try:
            aba = planilha_mestre.worksheet(nome)
            dados = aba.get_all_values()
            if len(dados) <= 1: return pd.DataFrame()
            df = pd.DataFrame(dados[1:], columns=dados[0])
            if not df.empty:
                df = df[~df.iloc[:, 0].astype(str).str.contains("TOTAIS", case=False, na=False)]
                df = df[df.iloc[:, 1].astype(str).str.strip() != ""]
            return df
        except: return pd.DataFrame()

    df_inv = ler_aba_seguro("INVENTÁRIO")
    df_cli = ler_aba_seguro("CARTEIRA DE CLIENTES")
    df_fin = ler_aba_seguro("FINANCEIRO")
    df_vendas = ler_aba_seguro("VENDAS")
    df_painel = ler_aba_seguro("PAINEL")
    
    # 💡 AQUI ESTÁ O SEGREDO: Puxando as novas abas
    df_socios = ler_aba_seguro("SOCIOS")
    df_aportes = ler_aba_seguro("APORTES")

    banco_prod = {str(r.iloc[0]): {"nome": r.iloc[1], "custo": float(limpar_v(r.iloc[3])), "estoque": r.iloc[7], "venda": r.iloc[8]} for _, r in df_inv.iterrows()} if not df_inv.empty else {}
    banco_cli = {str(r.iloc[0]): {"nome": str(r.iloc[1]), "fone": str(r.iloc[2])} for _, r in df_cli.iterrows()} if not df_cli.empty else {}

    # 💡 AJUSTE 1: O return TEM que devolver as duas abas novas no final
    return banco_prod, banco_cli, df_inv, df_fin, df_vendas, df_painel, df_cli, df_socios, df_aportes

# 💡 AJUSTE 2: A variável que recebe os dados TEM que ter os nomes das duas abas novas no final
banco_de_produtos, banco_de_clientes, df_full_inv, df_financeiro, df_vendas_hist, df_painel_resumo, df_clientes_full, df_socios, df_aportes = carregar_dados()

with st.sidebar:
    try:
        st.image("logo_sweet.png", use_container_width=True)
    except:
        st.write("🌸 **Sweet Home**")
    
    st.write(f"👋 Olá, **{st.session_state.get('usuario_logado', 'Usuária')}**!")
    st.divider()
    
    if st.button("Sair do Sistema 🚪", use_container_width=True):
        st.session_state['autenticado'] = False
        st.rerun()

    st.title("🛠️ Painel Sweet Home")
    
    menu_selecionado = st.radio(
        "Navegação",
        ["🛒 Vendas", "💰 Financeiro", "📦 Estoque", "👥 Clientes", "📂 Documentos"], 
        key="navegacao_principal_sweet"
    )
    
    st.divider()
    modo_teste = st.toggle("🔬 Modo de Teste", value=False, key="toggle_teste")
    
    if st.button("🔄 Sincronizar Planilha", key="btn_sincronizar"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

    st.divider()
    with st.expander("🛡️ Backup do Sistema"):
        st.markdown("<small>Faça o download seguro dos seus dados para o computador.</small>", unsafe_allow_html=True)
        try:
            if not df_vendas_hist.empty:
                st.download_button("📥 Baixar Vendas", df_vendas_hist.to_csv(index=False).encode('utf-8'), f"Vendas_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
            if not df_full_inv.empty:
                st.download_button("📥 Baixar Estoque", df_full_inv.to_csv(index=False).encode('utf-8'), f"Estoque_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
            if not df_clientes_full.empty:
                st.download_button("📥 Baixar Clientes", df_clientes_full.to_csv(index=False).encode('utf-8'), f"Clientes_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
            if not df_financeiro.empty:
                st.download_button("📥 Baixar Financeiro", df_financeiro.to_csv(index=False).encode('utf-8'), f"Financeiro_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
        except Exception as e:
            st.error("Sincronize a planilha para gerar o backup.")

# --- 👤 CONTROLE DE FLUXO (Visualização) ---
    with st.expander("👤 Controle de Fluxo", expanded=False):
        st.write("Monitoramento de acesso dos usuários ao sistema.")

        try:
            # Carrega a aba USUARIO fresca da planilha
            aba_usuario = planilha_mestre.worksheet("USUARIO")
            dados_usuarios = aba_usuario.get_all_values()

            if len(dados_usuarios) > 1:
                # Transforma os dados em uma tabela (DataFrame)
                df_usuarios = pd.DataFrame(dados_usuarios[1:], columns=dados_usuarios[0])

                # Deixa o quadro elegante e fácil de ler
                st.markdown("### 📋 Últimos Acessos Registrados")
                
                st.dataframe(
                    df_usuarios,
                    column_config={
                        "USUARIO": st.column_config.TextColumn("👤 Nome do Usuário", width="medium"),
                        "ULTIMO_ACESSO": st.column_config.TextColumn("🕒 Último Acesso (Data e Hora)")
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption("O registro de horário é feito automaticamente toda vez que o login é efetuado com sucesso.")
            else:
                st.info("A aba 'USUARIO' não possui registros válidos.")

        except Exception as e:
            st.error(f"Erro ao carregar o relatório de acessos: {e}")
            
# ==========================================
# --- SEÇÃO 1: VENDAS (SISTEMA DE CARRINHO MULTI-ITENS) ---
# ==========================================
if menu_selecionado == "🛒 Vendas":
    # --- FILTRO INTELIGENTE DE VERSÕES (LATEST VERSION) ---
    produtos_filtrados_venda = {}
    for cod_completo, info in banco_de_produtos.items():
        # Separa o código da versão (ex: "101.2" vira base="101" e versao=2)
        if "." in str(cod_completo):
            base, versao = str(cod_completo).split(".")
            versao = int(versao)
        else:
            base, versao = str(cod_completo), 0
        
        # Se o produto base ainda não está no filtro OU se esta versão é mais recente
        if base not in produtos_filtrados_venda or versao > produtos_filtrados_venda[base]['v']:
            produtos_filtrados_venda[base] = {
                'v': versao, 
                'full_cod': cod_completo, 
                'nome': info['nome']
            }
    
    # Criamos a lista final apenas com os códigos mais recentes
    lista_selecao_limpa = [f"{v['full_cod']} - {v['nome']}" for v in produtos_filtrados_venda.values()]
    # -----------------------------------------------------
    
    # ==========================================
    # --- 1. CONFIGURAÇÃO GERAL DA VENDA (CABEÇALHO) ---
    # ==========================================
    with st.container(border=True):
        # 1. Título centralizado e DENTRO do quadro para ditar a largura total
        st.markdown("<h3 style='text-align: center;'>🛒 Registro de Venda</h3>", unsafe_allow_html=True)
        st.divider()

        # 2. Mantendo EXATAMENTE a sua estrutura original: um embaixo do outro
        col_v1, col_v2 = st.columns(2)
        
        with col_v1:
            metodo = st.selectbox("Forma de Pagamento", ["Pix", "Dinheiro", "Cartão", "Sweet Flex"], key="venda_metodo_pg")
            c_sel = st.selectbox("Selecionar Cliente", ["*** NOVO CLIENTE ***"] + [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()], key="venda_cliente_sel")
            
            telefone_sugerido = ""
            if c_sel != "*** NOVO CLIENTE ***":
                id_cliente = c_sel.split(" - ")[0].strip()
                if id_cliente in banco_de_clientes:
                    telefone_sugerido = banco_de_clientes[id_cliente].get('fone', "")
            
            c_nome_novo = st.text_input("Nome Completo (se novo)", key="venda_nome_novo")
            c_zap = st.text_input("WhatsApp", value=telefone_sugerido, key=f"zap_venda_input_{c_sel}")
            vendedor = st.text_input("Vendedor(a)", value="Bia", key="venda_vendedor_input")

        with col_v2:
            # 3. O "espaço vazio" à direita é protegido aqui para as parcelas do Sweet Flex
            detalhes_p = []
            n_p = 1
            if metodo == "Sweet Flex":
                n_p = st.number_input("Número de Parcelas", 1, 12, 1, key="venda_n_parcelas")
                cols_parc = st.columns(n_p)
                for i in range(n_p):
                    with cols_parc[i]:
                        dt = st.date_input(f"{i+1}ª Parc.", datetime.now(), format="DD/MM/YYYY", key=f"vd_data_parc_{i}")
                        detalhes_p.append(dt.strftime("%d/%m/%Y"))
            else:
                detalhes_p = [datetime.now().strftime("%d/%m/%Y")]

    st.divider()

    # --- 2. ADIÇÃO DE PRODUTOS AO CARRINHO ---
    with st.container(border=True):
        st.markdown("### 🛍️ Adicionar Produtos")
        
        # Ajustamos as proporções para a caixa preencher melhor a tela e sumir com a lacuna
        c_p1, c_p2, c_p3, c_p4 = st.columns([3.5, 1, 1, 1])
        
        # 1. Seleção do Produto
        p_sel = c_p1.selectbox(
            "Item do Estoque", 
            sorted(lista_selecao_limpa), # Deixa em ordem alfabética/numérica
            key="venda_produto_sel"
        )
        
        # 2. Recuperação do preço direto da planilha (usando o ID do produto selecionado)
        cod_p_temp = p_sel.split(" - ")[0]
        preco_da_planilha = limpar_v(banco_de_produtos.get(cod_p_temp, {}).get('venda', 0.0))
        
        # 3. Campos de entrada
        qtd_v = c_p2.number_input("Qtd", value=1, min_value=1, key="venda_qtd_input")
        
        # O segredo está aqui: o value recebe o preco_da_planilha e a KEY muda conforme o produto
        # Isso força o Streamlit a atualizar o valor na tela instantaneamente
        val_v = c_p3.number_input("Preço Un. (R$)", value=preco_da_planilha, min_value=0.0, step=0.01, key=f"preco_dinamico_{cod_p_temp}")

        with c_p4:
            # Solução definitiva de alinhamento: empurra o botão exatamente a altura do texto "Preço Un. (R$)"
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            
            if st.button("➕ Adicionar", use_container_width=True):
                id_p = p_sel.split(" - ")[0]
                nome_p = p_sel.split(" - ")[1].strip()
                custo_un = float(banco_de_produtos.get(id_p, {}).get('custo', 0.0))
                
                item_carrinho = {
                    "cod": id_p,
                    "nome": nome_p,
                    "qtd": qtd_v,
                    "preco": val_v,
                    "custo": custo_un,
                    "subtotal": qtd_v * val_v
                }
                
                # --- A MÁGICA ENTRA AQUI ---
                cesta_temporaria = st.session_state['carrinho']
                cesta_temporaria.append(item_carrinho)
                st.session_state['carrinho'] = cesta_temporaria
                
                st.toast(f"✅ {nome_p} no carrinho!")
                st.rerun()

    # --- 3. EXIBIÇÃO DO CARRINHO E FINALIZAÇÃO ---
    if st.session_state['carrinho']:
        st.write("") # Espaço em branco para não colar as caixas
        with st.container(border=True):
            st.markdown("#### 🛒 Itens Selecionados")
            df_car = pd.DataFrame(st.session_state['carrinho'])
            st.dataframe(df_car[['nome', 'qtd', 'preco', 'subtotal']], use_container_width=True, hide_index=True)
            
            subtotal_venda = df_car['subtotal'].sum()
            
            col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
            desc_v = col_f1.number_input("Desconto Total na Compra (R$)", 0.0, key="venda_desc_total")
            
            total_com_desconto = subtotal_venda - desc_v
            col_f2.metric("Subtotal", f"R$ {subtotal_venda:,.2f}")
            col_f3.metric("Total a Pagar", f"R$ {total_com_desconto:,.2f}", delta=f"- R$ {desc_v:,.2f}" if desc_v > 0 else None)

            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("🗑️ Limpar Tudo", use_container_width=True):
                st.session_state['carrinho'] = []
                st.cache_data.clear()
                st.rerun()

            if c_btn2.button("Finalizar Venda 🚀", type="primary", use_container_width=True):
                # Validação
                if c_sel == "*** NOVO CLIENTE ***" and (not c_nome_novo or not c_zap):
                    st.error("⚠️ Preencha Nome e Zap para novo cliente!"); st.stop()

                # 👇 Tudo daqui para baixo agora pertence SOMENTE ao clique do botão!
                with st.spinner("Salvando venda e gerando recibo..."):
                    try:
                        # 1. Identificação/Cadastro do Cliente
                        if c_sel == "*** NOVO CLIENTE ***":
                            nome_cli = c_nome_novo.strip()
                            if not modo_teste:
                                aba_cli = planilha_mestre.worksheet("CARTEIRA DE CLIENTES")
                                dados_c = aba_cli.get_all_values()
                                nomes_up = [l[1].strip().upper() for l in dados_c[1:]]
                                if nome_cli.upper() in nomes_up:
                                    cod_cli = dados_c[nomes_up.index(nome_cli.upper())+1][0]
                                else:
                                    cod_cli = f"CLI-{len(dados_c):03d}"
                                    aba_cli.append_row([cod_cli, nome_cli, c_zap.strip(), "", datetime.now().strftime("%d/%m/%Y"), 0, "", "Incompleto"], value_input_option='RAW')
                            else: cod_cli = "CLI-TESTE"
                        else:
                            cod_cli = c_sel.split(" - ")[0]
                            nome_cli = banco_de_clientes[cod_cli]['nome']

                        # 2. Gravação de Itens (Loop na Planilha)
                        if not modo_teste:
                            aba_v = planilha_mestre.worksheet("VENDAS")
                            for item in st.session_state['carrinho']:
                                # Distribuição proporcional do desconto por item para manter lucro exato
                                proporcao_desc = (item['subtotal'] / subtotal_venda) if subtotal_venda > 0 else 0
                                desconto_proporcional = desc_v * proporcao_desc
                                desc_percentual = desconto_proporcional / item['subtotal'] if item['subtotal'] > 0 else 0
                                
                                t_liq_item = item['subtotal'] - desconto_proporcional
                                eh_parc = "Sim" if metodo == "Sweet Flex" else "Não"
                                
                                # Fórmulas Inteligentes
                                f_atraso = '=SE(OU(INDIRETO("W"&LIN())="Pago"; INDIRETO("W"&LIN())="Em dia"); 0; MÁXIMO(0; HOJE() - INDIRETO("V"&LIN())))'
                                f_k = '=SE(INDIRETO("I"&LIN())=""; ""; ARRED(INDIRETO("I"&LIN()) * (1 - INDIRETO("J"&LIN())); 2))'
                                f_l = '=SE(INDIRETO("H"&LIN())=""; ""; ARRED(INDIRETO("H"&LIN()) * INDIRETO("K"&LIN()); 2))'
                                f_m = '=SE(INDIRETO("L"&LIN())=""; ""; ARRED(INDIRETO("L"&LIN()) - (INDIRETO("H"&LIN()) * INDIRETO("G"&LIN())); 2))'
                                f_n = '=SE(INDIRETO("L"&LIN())=""; ""; SEERRO(INDIRETO("M"&LIN()) / INDIRETO("L"&LIN()); ""))'
                                f_r = '=SE(INDIRETO("L"&LIN())=""; ""; SE(INDIRETO("P"&LIN())="Não"; INDIRETO("L"&LIN()); 0))'
                                
                                linha = [
                                    "", datetime.now().strftime("%d/%m/%Y"), cod_cli, nome_cli, 
                                    item['cod'], item['nome'], item['custo'], item['qtd'], item['preco'], 
                                    desc_percentual, f_k, f_l, f_m, f_n, metodo, eh_parc, n_p, f_r, 
                                    t_liq_item/n_p if eh_parc=="Sim" else 0, 
                                    t_liq_item if eh_parc=="Não" else 0, 
                                    t_liq_item if eh_parc=="Sim" else 0, 
                                    detalhes_p[0] if (eh_parc=="Sim" and detalhes_p) else "", 
                                    "Pendente" if eh_parc=="Sim" else "Pago", f_atraso
                                ]
                                idx_ins = aba_v.find("TOTAIS").row
                                aba_v.insert_row(linha, index=idx_ins, value_input_option='USER_ENTERED')

                        # 3. Geração do Recibo Único e Elegante
                        recibo_texto = (
                            f"🌸 *DOCE LAR - RECIBO DE COMPRA* 🌸\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"Olá, eu sou a Bia! ✨ É um prazer atender você, *{nome_cli.split(' ')[0]}*.\n"
                            f"Aqui está o resumo detalhado da sua felicidade:\n\n"
                        )
                        for item in st.session_state['carrinho']:
                            recibo_texto += f"🛍️ {item['qtd']}x {item['nome']} - R$ {item['subtotal']:,.2f}\n"
                        
                        recibo_texto += f"━━━━━━━━━━━━━━━━━━━\n"
                        recibo_texto += f"💰 *Subtotal:* R$ {subtotal_venda:,.2f}\n"
                        if desc_v > 0:
                            recibo_texto += f"📉 *Desconto:* - R$ {desc_v:,.2f}\n"
                        recibo_texto += f"✅ *TOTAL FINAL:* *R$ {total_com_desconto:,.2f}*\n\n"
                        recibo_texto += f"💳 *Forma de Pagto:* {metodo}\n"
                        recibo_texto += f"🗓️ *Data:* {datetime.now().strftime('%d/%m/%Y')}\n"
                        
                        if metodo == "Sweet Flex":
                            recibo_texto += f"\n📝 *Plano de Pagamento ({n_p}x):*\n"
                            for i, data_p in enumerate(detalhes_p):
                                recibo_texto += f"🔹 {i+1}ª Parcela: {data_p} - R$ {total_com_desconto/n_p:,.2f}\n"
                        
                        recibo_texto += f"\n━━━━━━━━━━━━━━━━━━━\n"
                        recibo_texto += f"👤 *Vendedor(a):* {vendedor}\n"
                        recibo_texto += f"✨ *Obrigada pela preferência!*"

                        st.success("✅ Venda registrada com sucesso!")
                        st.code(recibo_texto, language="text")
                        
                        # 1. Inteligência: Puxa do Banco de Dados se for cliente antigo, ou da tela se for novo
                        if c_sel == "*** NOVO CLIENTE ***":
                            telefone_final = c_zap
                        else:
                            id_cli_final = c_sel.split(" - ")[0]
                            telefone_final = banco_de_clientes[id_cli_final].get('fone', "")

                        # 2. Limpeza pesada igual ao CRM
                        zap_limpo = str(telefone_final).replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

                        # 3. Proteção extra (Se já tiver 55 no banco de dados, ele não duplica)
                        if zap_limpo.startswith("55") and len(zap_limpo) > 11:
                            zap_limpo = zap_limpo[2:]

                        st.link_button("📲 Enviar Recibo Único para o WhatsApp", f"https://wa.me/55{zap_limpo}?text={urllib.parse.quote(recibo_texto)}", use_container_width=True, type="primary")

                        # Limpeza Final (AGORA SIM, BEM GUARDADA NO LUGAR CERTO)
                        st.session_state['carrinho'] = []
                        st.cache_data.clear()
                        st.cache_resource.clear()
                        
                    except Exception as e:
                        st.error(f"Erro ao processar venda: {e}")

    # --- MANTENDO HISTÓRICO E BORRACHA MÁGICA ---
    st.divider()
    with st.expander("📝 Ver Histórico de Vendas Recentes (Últimas 10)", expanded=False):
        try:
            dados_v = planilha_mestre.worksheet("VENDAS").get_all_values()
            if len(dados_v) > 1:
                df_v_real = pd.DataFrame(dados_v[1:], columns=dados_v[0])
                df_v_real = df_v_real[~df_v_real['CLIENTE'].astype(str).str.contains("TOTAIS", case=False, na=False)]
                df_v_real = df_v_real[df_v_real['CLIENTE'] != ""]
                historico_display = df_v_real[['DATA DA VENDA', 'CLIENTE', 'PRODUTO', 'TOTAL R$', 'STATUS']].tail(10).iloc[::-1]
                st.dataframe(historico_display, use_container_width=True, hide_index=True)
            else: st.info("Nenhuma venda registrada ainda.")
        except Exception as e: st.warning("Sincronize a planilha para ver o histórico.")

    # [O código da Borracha Mágica (Edição de Vendas) continua exatamente como você já tinha abaixo deste ponto]

# ==========================================
    # ✏️ BORRACHA MÁGICA: EDIÇÃO E EXCLUSÃO
    # ==========================================
    with st.expander("✏️ Corrigir ou Excluir Venda Recente", expanded=False):
        st.write("Escolha uma venda recente abaixo para corrigir cliente, produto ou valores.")
        
        try:
            aba_vendas = planilha_mestre.worksheet("VENDAS")
            dados_v = aba_vendas.get_all_values()
            
            if len(dados_v) > 1:
                vendas_recentes = []
                for i in range(len(dados_v)-1, max(0, len(dados_v)-21), -1):
                    linha = dados_v[i]
                    if len(linha) > 5 and "TOTAIS" not in str(linha[3]).upper() and linha[3] != "":
                        vendas_recentes.append(f"Linha {i+1} | Data: {linha[1]} | Cliente: {linha[3]} | Item: {linha[5]}")
                
                venda_selecionada = st.selectbox("Selecione a venda com erro:", ["---"] + vendas_recentes)
                
                if venda_selecionada != "---":
                    linha_real = int(venda_selecionada.split(" | ")[0].replace("Linha ", ""))
                    linha_dados = dados_v[linha_real - 1]
                    
                    # Dados atuais para preenchimento do form
                    cod_cli_atual = linha_dados[2]
                    nome_cli_atual = linha_dados[3]
                    cod_prod_atual = linha_dados[4]
                    nome_prod_atual = linha_dados[5]
                    metodo_atual = linha_dados[14]

                    def limpar_para_editar(val_str, is_perc=False):
                        try:
                            v = str(val_str).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
                            if is_perc and "%" in str(val_str):
                                return float(v.replace("%", "")) / 100.0
                            return float(v)
                        except: return 0.0

                    qtd_atual = limpar_para_editar(linha_dados[7])
                    val_atual = limpar_para_editar(linha_dados[8])
                    desc_perc_raw = limpar_para_editar(linha_dados[9], is_perc=True)
                    desc_reais_atual = round((qtd_atual * val_atual) * desc_perc_raw, 2) if 0 <= desc_perc_raw <= 1 else 0.0

                    # Listas para os Selectboxes
                    lista_clientes = [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()]
                    cliente_str_atual = f"{cod_cli_atual} - {nome_cli_atual}"
                    idx_cliente = lista_clientes.index(cliente_str_atual) if cliente_str_atual in lista_clientes else 0

                    lista_produtos = [f"{k} - {v['nome']}" for k, v in banco_de_produtos.items()]
                    produto_str_atual = f"{cod_prod_atual} - {nome_prod_atual}"
                    idx_produto = lista_produtos.index(produto_str_atual) if produto_str_atual in lista_produtos else 0

                    lista_metodos = ["Pix", "Dinheiro", "Cartão", "Sweet Flex"]
                    idx_metodo = lista_metodos.index(metodo_atual) if metodo_atual in lista_metodos else 0

                    with st.form(f"form_edicao_{linha_real}"):
                        st.markdown(f"#### 🔄 Atualizar Dados (Linha {linha_real})")
                        e_c1, e_c2 = st.columns(2)
                        novo_cliente = e_c1.selectbox("Cliente Oficial", lista_clientes, index=idx_cliente)
                        novo_produto = e_c2.selectbox("Produto Correto", lista_produtos, index=idx_produto)
                        
                        e_c3, e_c4, e_c5 = st.columns(3)
                        nova_qtd = e_c3.number_input("Quantidade", value=float(qtd_atual), min_value=0.1)
                        novo_val = e_c4.number_input("Preço Un. (R$)", value=float(val_atual))
                        novo_desc = e_c5.number_input("Desconto (R$)", value=float(desc_reais_atual))
                        
                        novo_metodo = st.selectbox("Forma de Pagto", lista_metodos, index=idx_metodo)
                        
                        st.divider()
                        col_btn1, col_btn2 = st.columns([2, 1])
                        
                        salvar = col_btn1.form_submit_button("💾 Salvar Alteração", type="primary", use_container_width=True)
                        
                        st.write("---")
                        confirma_exclusao = st.checkbox("Confirmar que desejo EXCLUIR esta venda permanentemente")
                        excluir = col_btn2.form_submit_button("🗑️ Excluir", type="secondary", use_container_width=True)

                        if salvar:
                            try:
                                n_cod_cli = novo_cliente.split(" - ")[0]
                                n_nome_cli = " - ".join(novo_cliente.split(" - ")[1:])
                                n_cod_prod = novo_produto.split(" - ")[0]
                                n_nome_prod = " - ".join(novo_produto.split(" - ")[1:])
                                n_custo = float(banco_de_produtos.get(n_cod_prod, {}).get('custo', 0.0))
                                n_v_bruto = nova_qtd * novo_val
                                n_desc_perc = novo_desc / n_v_bruto if n_v_bruto > 0 else 0
                                n_t_liq = n_v_bruto - novo_desc
                                eh_parc = "Sim" if novo_metodo == "Sweet Flex" else "Não"
                                
                                try: num_parc = int(linha_dados[16]) if linha_dados[16] else 1
                                except: num_parc = 1
                                
                                val_parc = n_t_liq / num_parc if eh_parc == "Sim" else 0
                                val_vista = n_t_liq if eh_parc == "Não" else 0
                                val_total_flex = n_t_liq if eh_parc == "Sim" else 0

                                atualizacoes = [
                                    {'range': f'C{linha_real}', 'values': [[n_cod_cli]]},
                                    {'range': f'D{linha_real}', 'values': [[n_nome_cli]]},
                                    {'range': f'E{linha_real}', 'values': [[n_cod_prod]]},
                                    {'range': f'F{linha_real}', 'values': [[n_nome_prod]]},
                                    {'range': f'G{linha_real}', 'values': [[n_custo]]},
                                    {'range': f'H{linha_real}', 'values': [[nova_qtd]]},
                                    {'range': f'I{linha_real}', 'values': [[novo_val]]},
                                    {'range': f'J{linha_real}', 'values': [[n_desc_perc]]},
                                    {'range': f'O{linha_real}', 'values': [[novo_metodo]]},
                                    {'range': f'P{linha_real}', 'values': [[eh_parc]]},
                                    {'range': f'S{linha_real}', 'values': [[val_parc]]},
                                    {'range': f'T{linha_real}', 'values': [[val_vista]]},
                                    {'range': f'U{linha_real}', 'values': [[val_total_flex]]}
                                ]
                                aba_vendas.batch_update(atualizacoes, value_input_option='USER_ENTERED')
                                
                                st.session_state['recibo_correcao'] = {
                                    "tipo": "editado",
                                    "cliente": n_nome_cli,
                                    "produto": f"{nova_qtd}x {n_nome_prod}",
                                    "total": n_t_liq,
                                    "metodo": novo_metodo
                                }
                                st.cache_data.clear()
                                st.cache_resource.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")

                        if excluir:
                            if confirma_exclusao:
                                try:
                                    aba_vendas.delete_rows(linha_real)
                                    st.session_state['recibo_correcao'] = {"tipo": "excluido", "linha": linha_real}
                                    st.cache_data.clear()
                                    st.cache_resource.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir: {e}")
                            else:
                                st.warning("⚠️ Você precisa marcar a caixa de confirmação para excluir.")

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")

    # ==========================================
    # 🧾 RECIBO DE ATUALIZAÇÃO / EXCLUSÃO
    # ==========================================
    if 'recibo_correcao' in st.session_state:
        recibo = st.session_state['recibo_correcao']
        
        if recibo['tipo'] == "editado":
            st.success("✅ Venda atualizada na planilha com sucesso!")
            st.markdown("#### 📋 Resumo do Ajuste")
            tabela_resumo = f"""
| Informação | Registro Corrigido |
| :--- | :--- |
| 👤 **Cliente** | {recibo['cliente']} |
| 📦 **Produto** | {recibo['produto']} |
| 💰 **Valor Total** | R$ {recibo['total']:.2f} |
| 💳 **Pagamento** | {recibo['metodo']} |
"""
            st.markdown(tabela_resumo)
        
        elif recibo['tipo'] == "excluido":
            st.warning(f"🗑️ A venda da Linha {recibo['linha']} foi excluída permanentemente.")
            st.info("A planilha financeira já foi reajustada automaticamente.")

        if st.button("✖️ Fechar Aviso", key="fechar_aviso_correcao"):
            del st.session_state['recibo_correcao']
            st.rerun()
            
# ==========================================
# --- SEÇÃO 2: FINANCEIRO (INTELIGÊNCIA 360) ---
# ==========================================
elif menu_selecionado == "💰 Financeiro":
    st.markdown("### 📈 Resumo Geral Sweet Home")
    if not df_vendas_hist.empty:
        try:
            # 1. PROCESSAMENTO SEGURO POR POSIÇÃO (ILOC)
            df_fin_total = df_vendas_hist.copy()
            
            # ========================================================
            # 🛑 O FILTRO DE GOVERNANÇA DINÂMICO (SEM NOMES FIXOS)
            # ========================================================
            try:
                # 1. Puxa todos os nomes da aba SOCIOS, convertendo para minúsculo e sem espaços
                if not df_socios.empty:
                    nomes_socios_limpos = df_socios['NOME'].astype(str).str.strip().str.lower().tolist()
                else:
                    nomes_socios_limpos = []
            except:
                nomes_socios_limpos = []

            # 2. Puxa do Banco de Clientes (CRM) os Códigos (CLI-XXX) que pertencem a esses sócios
            codigos_dos_socios = []
            if nomes_socios_limpos:
                for cod, dados in banco_de_clientes.items():
                    if str(dados['nome']).strip().lower() in nomes_socios_limpos:
                        codigos_dos_socios.append(str(cod).strip().lower())

            # 3. Limpa as colunas de Vendas pelo NOME DA COLUNA (Tirando a venda dos olhos do robô)
            nomes_vendas = df_fin_total['CLIENTE'].astype(str).str.strip().str.lower()
            
            # Prevenção: Busca a coluna de código pelo nome, para não errar a posição
            if 'CÓD. CLIENTE' in df_fin_total.columns:
                codigos_vendas = df_fin_total['CÓD. CLIENTE'].astype(str).str.split('.').str[0].str.strip().str.lower()
            else:
                codigos_vendas = df_fin_total.iloc[:, 2].astype(str).str.split('.').str[0].str.strip().str.lower()

            # 4. A MÁSCARA: É sócio se o NOME bater OU se o CÓDIGO bater. Totalmente automático!
            mascara_socios = nomes_vendas.isin(nomes_socios_limpos) | codigos_vendas.isin(codigos_dos_socios)

            # df_fin = VENDAS REAIS (Exclui os sócios para os Gráficos e Saldo Geral)
            df_fin = df_fin_total[~mascara_socios].copy()

            # df_retiradas = PRODUTOS RETIRADOS (Vai direto para o Banco Sweet)
            df_retiradas = df_fin_total[mascara_socios].copy()
            # ========================================================
            
            if not df_fin.empty:
                # 💡 A MÁGICA: Busca pelo NOME do cabeçalho que você me passou, não pela posição!
                df_fin['VALOR_NUM'] = df_fin['TOTAL R$'].apply(limpar_v)
                df_fin['FORMA_PG'] = df_fin['FORMA DE PAGAMENTO']
                df_fin['SALDO_NUM'] = df_fin['SALDO DEVEDOR'].apply(limpar_v)
                
                # Para o lucro, vamos garantir que ele ache a coluna certa também
                if 'LUCRO' in df_fin.columns:
                    df_fin['LUCRO_NUM'] = df_fin['LUCRO'].apply(limpar_v)
                elif 'LUCRO R$' in df_fin.columns:
                    df_fin['LUCRO_NUM'] = df_fin['LUCRO R$'].apply(limpar_v)
                else:
                    df_fin['LUCRO_NUM'] = df_fin.iloc[:, 12].apply(limpar_v) # Fallback
                
                vendas_brutas = df_fin['VALOR_NUM'].sum()
                lucro_bruto = df_fin['LUCRO_NUM'].sum()
                saldo_devedor = df_fin['SALDO_NUM'].sum()
                total_recebido = vendas_brutas - saldo_devedor
                
                # 🛡️ PENTE FINO NA LIQUIDEZ: Garante que "Sweet flex", "FLEX" ou "Sweet Flex" fiquem de fora da receita à vista
                receita_imediata = df_fin[~df_fin['FORMA_PG'].astype(str).str.upper().str.contains('FLEX')]['VALOR_NUM'].sum()
                indice_liquidez = (receita_imediata / vendas_brutas * 100) if vendas_brutas > 0 else 0
                
                # 🔍 CÁLCULO DA PROVA REAL (Para mostrar a separação)
                df_retiradas['SALDO_SOCIA'] = df_retiradas['SALDO DEVEDOR'].apply(limpar_v)
                saldo_socia = df_retiradas['SALDO_SOCIA'].sum()
                saldo_total_planilha = saldo_devedor + saldo_socia
            else:
                vendas_brutas = lucro_bruto = saldo_devedor = total_recebido = indice_liquidez = saldo_socia = saldo_total_planilha = 0.0
            
            # 2. MÉTRICAS PRINCIPAIS (AGORA SÓ COM VENDAS REAIS)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Vendas Totais", f"R$ {vendas_brutas:,.2f}", help="Soma de todas as vendas reais registradas para clientes (já excluindo as retiradas dos sócios).")
            c2.metric("Lucro Bruto", f"R$ {lucro_bruto:,.2f}", help="Lucro projetado dessas vendas (Valor Total de Venda cobrado menos o Custo de Fábrica dos produtos).")
            c3.metric("Total Recebido", f"R$ {total_recebido:,.2f}", delta="Dinheiro em Caixa", help="Capital que já entrou de fato no caixa da loja (Pix, Dinheiro, Cartão ou parcelas do Flex que já foram pagas).")
            c4.metric("Saldo Devedor", f"R$ {saldo_devedor:,.2f}", delta=f"{(saldo_devedor/vendas_brutas*100):.1f}% pendente" if vendas_brutas > 0 else "0%", delta_color="inverse", help="Montante que está 'na rua', aguardando o pagamento das faturas em aberto pelas clientes.")
            
            # 💡 LINHA DO "PENTE FINO" NA TELA (Isso vai tranquilizar você e a Bia)
            st.caption(f"🕵️‍♂️ **Raio-X do Filtro:** A planilha bruta possui **R$ {saldo_total_planilha:,.2f}** de dívida total. O sistema isolou **R$ {saldo_socia:,.2f}** (retiradas da sócia) para o *Banco Sweet* e exibe nas métricas acima apenas a dívida real de clientes (**R$ {saldo_devedor:,.2f}**).") help="Montante que está 'na rua', aguardando o pagamento das faturas em aberto pelas clientes.")

            # 3. TERMÔMETRO DE SAÚDE FINANCEIRA
            st.markdown("---")
            col_t1, col_t2 = st.columns([2, 1])
            with col_t1:
                # Define a cor e a mensagem baseada no índice
                if indice_liquidez >= 70:
                    cor_barra = "#28a745" # Verde
                    st.success(f"🟢 **Saúde de Caixa: EXCELENTE** ({indice_liquidez:.1f}% recebido à vista)")
                elif indice_liquidez >= 40:
                    cor_barra = "#ffa500" # Amarelo/Laranja
                    st.warning(f"🟡 **Saúde de Caixa: ATENÇÃO** ({indice_liquidez:.1f}% à vista)")
                else:
                    cor_barra = "#ff4b4b" # Vermelho
                    st.error(f"🔴 **Saúde de Caixa: CRÍTICA** (Apenas {indice_liquidez:.1f}% à vista)")
                
                # --- Barra de Progresso Customizada (Acompanha a cor e ganhou Tooltip HTML) ---
                progresso = min(indice_liquidez/100, 1.0)
                st.markdown(
                    f"""
                    <div style="width: 100%; background-color: #f0f2f6; border-radius: 10px; height: 10px;" title="Porcentagem do Faturamento que já é dinheiro vivo no caixa.">
                        <div style="width: {progresso*100}%; background-color: {cor_barra}; height: 10px; border-radius: 10px;">
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            with col_t2:
                st.metric("Recebíveis (Futuro)", f"R$ {saldo_devedor:,.2f}", help="Dinheiro que entrará via faturas do Sweet Flex no futuro. É o reflexo do Saldo Devedor visto como promessa de recebimento.")

            # 4. DASHBOARD DE ANÁLISE (VERSÃO PREMIUM COM CORES DA MARCA)
            with st.expander("📊 Análise de Desempenho e Tendências", expanded=False):
                if not df_fin.empty:
                    t_faturamento, t_pagamentos, t_ticket = st.tabs(["📈 Faturamento", "💳 Meios de Pagamento", "🎟️ Ticket Médio"])
                    
                    import plotly.express as px
                    paleta_sweet = ['#31241b', '#8d5524', '#d4a373', '#f6debc'] # Marrons e Beges da marca

                    with t_faturamento:
                        st.write("#### Evolução de Vendas no Tempo")
                        df_fin['DATA_DT'] = pd.to_datetime(df_fin['DATA DA VENDA'], format='%d/%m/%Y', errors='coerce')
                        vendas_dia = df_fin.groupby('DATA_DT')['VALOR_NUM'].sum().reset_index()
                        
                        # Gráfico de Área com Formatação de R$ no hover
                        fig_fat = px.area(vendas_dia, x='DATA_DT', y='VALOR_NUM',
                                         labels={'VALOR_NUM': 'Total Vendido', 'DATA_DT': 'Data'},
                                         color_discrete_sequence=[paleta_sweet[0]])
                        fig_fat.update_traces(hovertemplate='<b>Data:</b> %{x}<br><b>Vendido:</b> R$ %{y:,.2f}')
                        fig_fat.update_layout(xaxis_title=None, yaxis_title="Total (R$)", margin=dict(t=10, b=10, l=0, r=0))
                        st.plotly_chart(fig_fat, use_container_width=True)
                    
                    with t_pagamentos:
                        st.write("#### Composição dos Recebimentos")
                        vendas_meio = df_fin.groupby('FORMA_PG')['VALOR_NUM'].sum().reset_index()
                        fig_pie = px.pie(vendas_meio, values='VALOR_NUM', names='FORMA_PG', 
                                        color_discrete_sequence=paleta_sweet,
                                        hole=.4)
                        fig_pie.update_traces(textposition='inside', textinfo='percent+label', 
                                             hovertemplate='<b>%{label}</b><br>Total: R$ %{value:,.2f}')
                        fig_pie.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
                        st.plotly_chart(fig_pie, use_container_width=True)

                    with t_ticket:
                        st.write("#### Valor Médio por Venda (Ticket Médio)")
                        # Arredondando para 2 casas decimais para evitar o erro visual
                        ticket_meio = df_fin.groupby('FORMA_PG')['VALOR_NUM'].mean().round(2).reset_index()
                        
                        fig_ticket = px.bar(ticket_meio, x='FORMA_PG', y='VALOR_NUM',
                                           text='VALOR_NUM',
                                           labels={'VALOR_NUM': 'Ticket Médio (R$)', 'FORMA_PG': 'Meio de Pagto'},
                                           color='FORMA_PG',
                                           color_discrete_sequence=paleta_sweet)
                        
                        fig_ticket.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside',
                                                hovertemplate='<b>%{x}</b><br>Média: R$ %{y:,.2f}')
                        fig_ticket.update_layout(showlegend=False, yaxis_title="Valor (R$)", xaxis_title=None)
                        st.plotly_chart(fig_ticket, use_container_width=True)
                        st.caption("💡 O Ticket Médio ajuda a entender qual cliente gasta mais em cada modalidade.")
                else:
                    st.info("Aguardando vendas de clientes reais para gerar os gráficos.")

        except Exception as e:
            st.error(f"⚠️ Erro ao processar o painel: {e}")

    st.divider()

    with st.expander("➕ Lançar Novo Abatimento (Sistema FIFO)", expanded=False):
        with st.form("f_fifo_novo", clear_on_submit=True):
            lista_todas_clientes = sorted([f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
            c_pg = st.selectbox("Quem está pagando?", ["Selecione..."] + lista_todas_clientes, key="fifo_cliente")
            f1, f2, f3 = st.columns(3)
            v_pg = f1.number_input("Valor Pago (R$)", min_value=0.0, key="fifo_valor", help="Digite o valor exato que a cliente pagou agora.")
            meio = f2.selectbox("Meio", ["Pix", "Dinheiro", "Cartão", "Sweet Flex"], key="fifo_meio")
            obs = f3.text_input("Obs", "Abatimento", key="fifo_obs")
            
            if st.form_submit_button("Confirmar Pagamento ✅"):
                if v_pg > 0 and c_pg != "Selecione...":
                    try:
                        aba_v = planilha_mestre.worksheet("VENDAS")
                        df_v_viva = pd.DataFrame(aba_v.get_all_records())
                        df_v_viva['S_NUM'] = df_v_viva['SALDO DEVEDOR'].apply(limpar_v)
                        nome_c_alvo = " - ".join(c_pg.split(" - ")[1:])
                        pendentes = df_v_viva[(df_v_viva['CLIENTE'] == nome_c_alvo) & (df_v_viva['S_NUM'] > 0)].copy()
                        sobra = v_pg
                        for idx, row in pendentes.iterrows():
                            if sobra <= 0: break
                            lin_planilha = idx + 2
                            div_linha = row['S_NUM']
                            if sobra >= div_linha:
                                aba_v.update_acell(f"U{lin_planilha}", 0) 
                                aba_v.update_acell(f"W{lin_planilha}", "Pago") 
                                sobra -= div_linha
                            else:
                                aba_v.update_acell(f"U{lin_planilha}", div_linha - sobra) 
                                sobra = 0
                        
                        aba_f = planilha_mestre.worksheet("FINANCEIRO")
                        aba_f.append_row([datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), c_pg.split(" - ")[0], nome_c_alvo, 0, v_pg, "PAGO", f"{meio}: {obs}"], value_input_option='RAW')
                        st.success(f"✅ Recebido de {nome_c_alvo} processado!")
                        st.cache_data.clear()
                        st.cache_resource.clear(); st.rerun()
                    except Exception as e: st.error(f"Erro no FIFO: {e}")

        # --- 🕒 HISTÓRICO DE ABATIMENTOS (LÊ A ABA FINANCEIRO) ---
        st.markdown("---")
        st.subheader("🕒 Últimos Abatimentos Registrados")
        
        try:
            aba_f_hist = planilha_mestre.worksheet("FINANCEIRO")
            dados_f = aba_f_hist.get_all_values()

            if len(dados_f) > 1:
                # Cria o DataFrame com as colunas reais da sua planilha
                df_f_hist = pd.DataFrame(dados_f[1:], columns=dados_f[0])

                # Limpeza de segurança nos nomes das colunas
                df_f_hist.columns = [c.strip() for c in df_f_hist.columns]
                
                # Filtro pelo STATUS que você definiu na Coluna G
                if 'STATUS' in df_f_hist.columns:
                    df_f_hist['STATUS'] = df_f_hist['STATUS'].str.strip().str.upper()
                    # Filtra apenas o que está PAGO e pega os últimos 5
                    abatimentos = df_f_hist[df_f_hist['STATUS'] == "PAGO"].tail(5).iloc[::-1]
                else:
                    abatimentos = pd.DataFrame()

                if not abatimentos.empty:
                    # Exibição organizada com os nomes de colunas que você passou
                    st.dataframe(
                        abatimentos[['DATA', 'NOME', 'VALOR_PAGO', 'OBS']],
                        column_config={
                            "DATA": st.column_config.TextColumn("📅 Data"),
                            "NOME": st.column_config.TextColumn("👤 Cliente"),
                            "VALOR_PAGO": st.column_config.TextColumn("💰 Valor Pago"),
                            "OBS": st.column_config.TextColumn("📝 Observação")
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("ℹ️ Nenhum abatimento com status 'PAGO' foi localizado.")
            else:
                st.info("ℹ️ A planilha financeira ainda está vazia.")

        except Exception as e:
            if st.session_state.get('usuario_logado') == 'Admin':
                st.error(f"Erro técnico: {e}")
            else:
                st.info("🕒 O histórico aparecerá após o primeiro recebimento ser registrado.")

    # ====================================================
    # ⚖️ PAINEL GERENCIAL DE INADIMPLÊNCIA E ACORDOS
    # ====================================================
    st.markdown("---")
            
    with st.expander("⚖️ Painel Estratégico de Inadimplência (Visão Gerencial)", expanded=False):
        
        # 💡 Botão para forçar a atualização da planilha em tempo real
        col_tit, col_ref = st.columns([3, 1])
        col_tit.write("Análise de carteira, cálculo de juros (CDC) e simulador de acordos com IA.")
        if col_ref.button("🔄 Recarregar Dados", use_container_width=True):
            st.cache_data.clear() # Limpa a memória do Streamlit
            st.rerun() # Força a tela a piscar e buscar os dados novos do Google Sheets
        
        try:
            import pytz
            from datetime import datetime
            import pandas as pd
            
            if not df_vendas_hist.empty:
                fuso_br = pytz.timezone('America/Sao_Paulo') 
                hoje_pd = pd.to_datetime(datetime.now(fuso_br).strftime("%Y-%m-%d"))
                
                # 📅 REGRA DE NEGÓCIO: Dívidas antes de Fev/2026 são "Legado" (Sem Juros automáticos)
                DATA_CORTE_LEGADO = pd.to_datetime("2026-02-01")
                
                # --- 1. HIGIENIZAÇÃO DE DADOS ---
                # A MÁGICA AQUI: Puxa o df_fin (sem sócios) no lugar do histórico bruto
                df_cobranca = df_fin.copy()
                df_cobranca['SALDO_NUM'] = df_cobranca['SALDO DEVEDOR'].apply(limpar_v)
                
                # 🛑 Trava de Status para não cobrar quem já pagou
                if 'STATUS' in df_cobranca.columns:
                    df_cobranca['STATUS_LIMPO'] = df_cobranca['STATUS'].astype(str).str.strip().str.lower()
                    df_dev_real = df_cobranca[
                        (df_cobranca['SALDO_NUM'] > 0.01) & 
                        (~df_cobranca['STATUS_LIMPO'].isin(['pago', 'quitado', 'ok', 'paga']))
                    ].copy()
                else:
                    df_dev_real = df_cobranca[df_cobranca['SALDO_NUM'] > 0.01].copy()
                
                df_dev_real['CÓD. CLIENTE'] = df_dev_real['CÓD. CLIENTE'].astype(str).str.split('.').str[0].str.strip()
                df_dev_real['VENCIMENTO'] = pd.to_datetime(df_dev_real['PRÓXIMA PARCELA'], format="%d/%m/%Y", errors='coerce')
                df_dev_real = df_dev_real.dropna(subset=['VENCIMENTO'])
                df_dev_real['DIAS_ATRASO'] = (hoje_pd - df_dev_real['VENCIMENTO']).dt.days

                # --- 2. MOTOR FINANCEIRO (POR FATURA) ---
                def calc_compliance(row):
                    multa = 0
                    juros = 0
                    is_legado = row['VENCIMENTO'] < DATA_CORTE_LEGADO
                    
                    if row['DIAS_ATRASO'] > 0:
                        if not is_legado:
                            multa = row['SALDO_NUM'] * 0.02 # 2% de multa (CDC)
                            juros = row['SALDO_NUM'] * (0.01 / 30) * row['DIAS_ATRASO'] # 1% ao mês pro rata
                        status = "🕰️ Legado" if is_legado else ("🔴 Crítico" if row['DIAS_ATRASO'] > 30 else "🟡 Recente")
                    elif row['DIAS_ATRASO'] == 0:
                        status = "🟢 Vence Hoje"
                    else:
                        status = f"📅 Vence em {abs(row['DIAS_ATRASO'])}d"
                    
                    valor_total = row['SALDO_NUM'] + multa + juros
                    return pd.Series([multa, juros, valor_total, status, is_legado])

                df_dev_real[['MULTA', 'JUROS', 'VALOR_ATUALIZADO', 'FASE', 'IS_LEGADO']] = df_dev_real.apply(calc_compliance, axis=1)

                # --- 3. CONSOLIDAÇÃO POR CLIENTE ---
                df_agrupado = df_dev_real.groupby(['CÓD. CLIENTE', 'CLIENTE']).agg(
                    TOTAL_ORIGINAL=pd.NamedAgg(column='SALDO_NUM', aggfunc='sum'),
                    TOTAL_ATUALIZADO=pd.NamedAgg(column='VALOR_ATUALIZADO', aggfunc='sum'),
                    TOTAL_ENCARGOS=pd.NamedAgg(column='MULTA', aggfunc=lambda x: x.sum() + df_dev_real.loc[x.index, 'JUROS'].sum()),
                    MAIOR_ATRASO=pd.NamedAgg(column='DIAS_ATRASO', aggfunc='max'),
                    STATUS_PREDOMINANTE=pd.NamedAgg(column='FASE', aggfunc=lambda x: x.iloc[0])
                ).reset_index()

                # 💡 Regras de Score e Sweet Flex
                LIMITE_DIAS_FLEX = 15
                df_agrupado['SWEET_FLEX'] = df_agrupado['MAIOR_ATRASO'].apply(
                    lambda dias: "🔒 Suspenso" if dias > LIMITE_DIAS_FLEX else "🔑 Liberado"
                )
                
                def calcular_score(dias):
                    if dias <= 0: return "⭐ 10/10 (Excelente)"
                    elif dias <= 7: return "🟢 8/10 (Bom)"
                    elif dias <= 20: return "🟡 5/10 (Atenção)"
                    else: return "🔴 3/10 (Risco)"
                df_agrupado['SWEET_SCORE'] = df_agrupado['MAIOR_ATRASO'].apply(calcular_score)

                # 💡 NOVA INJEÇÃO: Leitor Raiz baseado na lógica do seu CRM (Puxa do df_clientes_full)
                try:
                    # Mapeia a Tabela Mãe na hora
                    df_carteira_temp = df_clientes_full.copy()
                    
                    # Coluna 0 é o COD. CLIENTE
                    df_carteira_temp['COD_LIMPO'] = df_carteira_temp[df_carteira_temp.columns[0]].astype(str).str.split('.').str[0].str.strip()
                    
                    # Coluna 5 é a F (VALE DESCONTO). Se a planilha tiver a Coluna F, ele puxa ela.
                    if len(df_carteira_temp.columns) > 5:
                        coluna_vale_real = df_carteira_temp.columns[5] 
                    else:
                        # Fallback: Se por acaso a ordem mudar, procura a palavra "vale"
                        coluna_vale_real = None
                        for c in df_carteira_temp.columns:
                            if 'vale' in str(c).lower() or 'desconto' in str(c).lower():
                                coluna_vale_real = c
                                break
                    
                    if coluna_vale_real:
                        dicionario_vales_vivos = dict(zip(df_carteira_temp['COD_LIMPO'], df_carteira_temp[coluna_vale_real]))
                    else:
                        dicionario_vales_vivos = {}
                except:
                    dicionario_vales_vivos = {}

                def resgatar_vale_vivo(cod_cliente):
                    cod_str = str(cod_cliente).strip()
                    vale = str(dicionario_vales_vivos.get(cod_str, '')).strip()
                    
                    if not vale or vale.lower() in ['nan', 'none', '0', '0.0', '0,00', 'r$ 0,00', 'r$ 0', 'null']:
                        return "R$ 0,00"
                    
                    if vale.upper().startswith('R$'):
                        return vale
                        
                    try:
                        v_float = float(vale.replace('.', '').replace(',', '.'))
                        if v_float > 0.01:
                            return f"R$ {v_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    except:
                        pass
                    return f"R$ {vale}"
                
                df_agrupado['VALE_DESCONTO'] = df_agrupado['CÓD. CLIENTE'].apply(resgatar_vale_vivo)

                atrasados = df_agrupado[df_agrupado['MAIOR_ATRASO'] > 0].sort_values('MAIOR_ATRASO', ascending=False)
                prevencao = df_agrupado[(df_agrupado['MAIOR_ATRASO'] <= 0) & (df_agrupado['MAIOR_ATRASO'] >= -5)].sort_values('MAIOR_ATRASO', ascending=False)

                # --- 4. INTERFACE DE GESTÃO ---
                t1, t2 = st.tabs(["🚨 Mapa de Risco (Atrasados)", "📅 Fluxo de Caixa (Próximos 5 dias)"])
                
                with t1:
                    if not atrasados.empty:
                        c_m1, c_m2, c_m3 = st.columns(3)
                        c_m1.metric("💰 Capital Retido (Original)", f"R$ {atrasados['TOTAL_ORIGINAL'].sum():,.2f}")
                        c_m2.metric("📈 Expectativa c/ Encargos", f"R$ {atrasados['TOTAL_ATUALIZADO'].sum():,.2f}")
                        c_m3.metric("👥 Clientes Inadimplentes", f"{len(atrasados)}")
                        
                        # A Coluna VALE_DESCONTO agora aparece aqui na tela principal!
                        st.dataframe(
                            atrasados[['CLIENTE', 'SWEET_SCORE', 'SWEET_FLEX', 'VALE_DESCONTO', 'MAIOR_ATRASO', 'TOTAL_ORIGINAL', 'TOTAL_ENCARGOS', 'TOTAL_ATUALIZADO', 'STATUS_PREDOMINANTE']], 
                            column_config={
                                "TOTAL_ORIGINAL": st.column_config.NumberColumn("Original (R$)", format="R$ %.2f"),
                                "TOTAL_ENCARGOS": st.column_config.NumberColumn("Juros/Multa (R$)", format="R$ %.2f"),
                                "TOTAL_ATUALIZADO": st.column_config.NumberColumn("Atualizado (R$)", format="R$ %.2f"),
                                "MAIOR_ATRASO": "Dias Atraso",
                                "VALE_DESCONTO": "Vale (R$)"
                            },
                            use_container_width=True, hide_index=True
                        )
                    else:
                        st.success("🎉 Excelência! Nenhum cliente em atraso na base.")

                with t2:
                    if not prevencao.empty:
                        st.dataframe(
                            prevencao[['CLIENTE', 'SWEET_SCORE', 'VALE_DESCONTO', 'MAIOR_ATRASO', 'TOTAL_ORIGINAL', 'STATUS_PREDOMINANTE']], 
                            column_config={
                                "TOTAL_ORIGINAL": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                                "VALE_DESCONTO": "Vale (R$)"
                            },
                            use_container_width=True, hide_index=True
                        )
                    else:
                        st.write("Nenhum vencimento previsto para os próximos 5 dias.")

                # --- 5. SIMULADOR DE ACORDOS COM IA ---
                if not atrasados.empty:
                    st.markdown("---")
                    st.markdown("#### 🤖 Simulador de Cenários de Negociação")
                    st.write("Escolha uma cliente para a IA gerar opções de parcelamento e descontos matematicamente viáveis.")
                    
                    opcoes_acordo = atrasados['CLIENTE'].tolist()
                    cliente_alvo = st.selectbox("Selecionar Cliente:", ["---"] + opcoes_acordo)
                    
                    if cliente_alvo != "---":
                        dados_cli = atrasados[atrasados['CLIENTE'] == cliente_alvo].iloc[0]
                        
                        # 💡 A IA agora puxa a informação oficial da nova coluna
                        vale_atual = dados_cli['VALE_DESCONTO']
                        tem_vale_valido = vale_atual != "R$ 0,00"
                        
                        st.write("##### 🛡️ Preparação Adicional (Opcional)")
                        desculpa_cliente = st.text_input("A cliente deu alguma desculpa para o atraso?", placeholder="Ex: Fiquei doente, achei o juros alto...")
                        
                        # O Checkbox se adapta se a cliente tiver dinheiro na casa
                        texto_check = f"🎁 Usar Saldo de {vale_atual} (Carteira) na negociação" if tem_vale_valido else "🎁 Ativar 'Sweet Rewards' (Oferecer NOVO Vale-Desconto como negociação)"
                        usar_rewards = st.checkbox(texto_check)
                        
                        if st.button("✨ Gerar Propostas de Acordo", type="primary"):
                            with st.spinner("Analisando perfil da dívida e calculando cenários..."):
                                try:
                                    import google.generativeai as genai
                                    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                                    
                                    # Lógica Dinâmica do Vale
                                    if usar_rewards:
                                        if tem_vale_valido:
                                            instrucao_rewards = f"ESTRATÉGIA SWEET REWARDS ATIVADA: A cliente JÁ POSSUI um saldo de 'Vale-Desconto' de {vale_atual} cadastrado no nosso sistema. Use esse argumento OBRIGATORIAMENTE na proposta: proponha que ela use esse saldo acumulado agora mesmo para abater a dívida/encargos, desde que faça o pagamento à vista hoje."
                                        else:
                                            instrucao_rewards = "ESTRATÉGIA SWEET REWARDS ATIVADA: Oriente a vendedora a gerar um NOVO 'Vale-Fidelidade' (entre R$ 20 e R$ 50) ou um 'Cupom de 10%' para a PRÓXIMA compra, condicionando isso à quitação da dívida hoje."
                                    else:
                                        instrucao_rewards = ""
                                        
                                    instrucao_objecao = f"A cliente deu esta desculpa: '{desculpa_cliente}'. Escreva um parágrafo amigável (pronto para copiar e colar no WhatsApp) desarmando essa desculpa com empatia e focando na solução." if desculpa_cliente else ""
                                    
                                    # 💡 O PROMPT DE AÇO: A IA agora enxerga a matemática completa
                                    prompt_estrategia = f"""
                                    Você é o Diretor Financeiro da 'Sweet Home Enxovais'. Analise a dívida abaixo e crie opções de negociação matemática e persuasiva.
                                    
                                    DADOS DO DÉBITO (BASE PARA ANÁLISE):
                                    - Cliente: {dados_cli['CLIENTE']}
                                    - Score Interno: {dados_cli['SWEET_SCORE']}
                                    - Status do Crédito: {dados_cli['SWEET_FLEX']}
                                    - Saldo de Vale-Desconto Disponível na Ficha: {vale_atual}
                                    - Dias de Atraso: {dados_cli['MAIOR_ATRASO']}
                                    - Valor Original (Sem Juros): R$ {dados_cli['TOTAL_ORIGINAL']:.2f}
                                    - Juros/Multas Legais: R$ {dados_cli['TOTAL_ENCARGOS']:.2f}
                                    - Valor Total Atualizado: R$ {dados_cli['TOTAL_ATUALIZADO']:.2f}
                                    - Possui dívida antiga (Legado)? {'Sim' if 'Legado' in dados_cli['STATUS_PREDOMINANTE'] else 'Não'}
                                    
                                    ⚠️ REGRAS CRÍTICAS DE FORMATAÇÃO E ANÁLISE:
                                    1. NÃO use Markdown de cabeçalhos (como #, ## ou ###). Use apenas texto normal e negrito.
                                    2. Seja extremamente organizado, use emojis para listar os tópicos.
                                    3. Analise o "Saldo de Vale-Desconto Disponível". Se for maior que zero e a estratégia Sweet Rewards estiver ativada, faça a conta abatendo esse valor da dívida atualizada na opção à vista.
                                    4. Entregue a resposta EXATAMENTE nesta estrutura:
                                    
                                    🎯 **CENÁRIOS DE ACORDO (Para a Loja)**
                                    (Liste 3 opções: Quitação com desconto / Parcelamento Curto / Parcelamento Longo)
                                    
                                    💬 **MENSAGEM PARA A CLIENTE (Copie e Cole)**
                                    (Escreva um texto empático oferecendo essas opções para a vendedora copiar e mandar)
                                    
                                    🔑 **ESTRATÉGIA SWEET FLEX**
                                    (Se o Status do Crédito for '🔒 Suspenso', escreva um texto amigável ensinando a vendedora a dizer que quitar a dívida destravará o limite)
                                    
                                    🛡️ **CONTORNO DE OBJEÇÃO & SWEET REWARDS**
                                    {instrucao_objecao}
                                    {instrucao_rewards}
                                    """
                                    
                                    modelos = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]
                                    for m in modelos:
                                        try:
                                            modelo = genai.GenerativeModel(m)
                                            resposta = modelo.generate_content(prompt_estrategia)
                                            if resposta:
                                                st.info("💡 **Relatório Gerencial de Negociação:**")
                                                st.write(resposta.text)
                                                break
                                        except: continue
                                        
                                except Exception as e:
                                    st.error(f"Erro ao gerar estratégia: {e}")

            else:
                st.info("Aguardando dados de vendas na planilha para iniciar as análises.")
                
        except Exception as e:
            st.error(f"⚠️ Erro no núcleo de processamento gerencial: {e}")

    # ====================================================
    # 🏦 BANCO SWEET & GOVERNANÇA CORPORATIVA (NOVO)
    # ====================================================
    st.markdown("---")
    with st.expander("🏦 Banco Sweet (Equity, Aportes e Retiradas)", expanded=False):
        st.write("Módulo de gestão de sócios, injeção de capital e monitoramento de retiradas (Marketing/Uso Pessoal).")
        
        # --- 0. MINI DASHBOARD DO BANCO (RESUMO RÁPIDO) ---
        try:
            # Processa Aportes (Entradas)
            if not df_aportes.empty:
                df_aportes['VALOR_NUM'] = df_aportes['VALOR_R$'].apply(limpar_v)
                aporte_total_empresa = df_aportes['VALOR_NUM'].sum()
            else:
                aporte_total_empresa = 0.0

            # Processa Retiradas (Saídas) focando na Coluna L = TOTAL R$ e Coluna H = QUANTIDADE
            if not df_retiradas.empty:
                # Puxa a Coluna L (Índice 11) para somar os valores financeiros
                df_retiradas['RETIRADA_NUM'] = df_retiradas.iloc[:, 11].apply(limpar_v)
                
                # Puxa a Coluna H (Índice 7) para somar as peças físicas reais
                df_retiradas['QTD_PECAS'] = pd.to_numeric(df_retiradas.iloc[:, 7], errors='coerce').fillna(0)
                
                total_retirado_global = df_retiradas['RETIRADA_NUM'].sum()
                qtd_total_pecas = int(df_retiradas['QTD_PECAS'].sum())
            else:
                total_retirado_global = 0.0
                qtd_total_pecas = 0

            # Saldo do Banco (Injeções - Retiradas)
            saldo_banco_sweet = aporte_total_empresa - total_retirado_global
            
            b1, b2, b3 = st.columns(3)
            b1.metric("📥 Capital Injetado", f"R$ {aporte_total_empresa:,.2f}", help="Soma de todo o dinheiro vivo (aportes) colocado na empresa pelos sócios.")
            
            # 💡 AQUI ESTÁ A MÁGICA: O delta agora mostra a quantidade exata de itens retirados
            b2.metric("📤 Estoque Retirado", f"R$ {total_retirado_global:,.2f}", delta=f"{qtd_total_pecas} itens físicos", delta_color="inverse", help="Valor financeiro total consumido em produtos (respeitando descontos) e a quantidade exata de peças físicas retiradas da loja.")
            
            if saldo_banco_sweet >= 0:
                b3.metric("💼 Balanço Corporativo", f"R$ {saldo_banco_sweet:,.2f}", delta="Superávit", help="Calculado: Capital Injetado menos Estoque Retirado. Se verde, a empresa tem caixa positivo frente às retiradas.")
            else:
                b3.metric("💼 Balanço Corporativo", f"R$ {saldo_banco_sweet:,.2f}", delta="Déficit", delta_color="inverse", help="Atenção: O valor dos produtos retirados do estoque já superou o dinheiro injetado pelos sócios.")
        except Exception as e:
            st.error(f"Erro ao carregar o resumo corporativo: {e}")
            
        st.divider()

        # --- 1. CADASTRO DE NOVOS SÓCIOS ---
        with st.form("form_novo_socio", clear_on_submit=True):
            st.markdown("##### 🤝 Cadastrar Novo Sócio / Investidor")
            st.caption("O código único (Ex: SOC-001) será gerado e vinculado automaticamente ao salvar.")
            
            c_s1, c_s2 = st.columns(2)
            nome_s = c_s1.text_input("Nome Completo", help="Digite exatamente como a pessoa sairá nas vendas, caso ela faça retiradas de estoque.")
            tel_s = c_s2.text_input("WhatsApp")
            
            if st.form_submit_button("Adicionar ao Quadro Societário", type="secondary"):
                if nome_s:
                    try:
                        aba_soc = planilha_mestre.worksheet("SOCIOS")
                        dados_soc = aba_soc.get_all_values()
                        
                        # 💡 Geração Inteligente de Código (À prova de falhas/exclusões)
                        if len(dados_soc) > 1:
                            ultimo_cod = str(dados_soc[-1][0]) # Pega o ID da última linha da planilha
                            try:
                                prox_num = int(ultimo_cod.replace("SOC-", "")) + 1
                            except:
                                prox_num = len(dados_soc)
                        else:
                            prox_num = 1 # Se a planilha só tiver o cabeçalho, ele será o número 1
                            
                        novo_cod = f"SOC-{prox_num:03d}" # Monta no formato SOC-001, SOC-002...
                        
                        # Salvando no Google Sheets
                        aba_soc.append_row([
                            novo_cod, 
                            nome_s.strip(), 
                            tel_s.strip(), 
                            datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%d/%m/%Y")
                        ], value_input_option='RAW')
                        
                        st.success(f"✅ {nome_s} cadastrado com sucesso! Código gerado: **{novo_cod}**")
                        st.cache_data.clear()
                        st.cache_resource.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar na aba SOCIOS: {e}")
                else:
                    st.warning("⚠️ O Nome Completo é obrigatório para gerar o cadastro.")

        st.divider()

        # --- 2. APORTES DE CAPITAL (INJEÇÃO DE DINHEIRO) ---
        st.markdown("##### 💰 Injeção de Capital (Aportes)")
        
        try:
            lista_socios_select = ["---"]
            if not df_socios.empty:
                lista_socios_select += [f"{row['COD_SOCIO']} - {row['NOME']}" for _, row in df_socios.iterrows()]
                
            with st.form("form_aporte_capital", clear_on_submit=True):
                c_a1, c_a2, c_a3 = st.columns([1.5, 1, 1.5])
                socio_aporte = c_a1.selectbox("Quem está investindo?", lista_socios_select, help="Selecione o sócio que está transferindo o dinheiro para o caixa da loja.")
                
                # 💡 AJUSTE AQUI: Começa em 0.00 limpo e formata com duas casas decimais
                valor_aporte = c_a2.number_input("Valor (R$)", min_value=0.00, value=0.00, step=0.01, format="%.2f")
                
                tipo_aporte = c_a3.selectbox("Destinação", ["Caixa Geral", "Marketing", "Infraestrutura", "Reinvestimento de Lucro"])
                obs_aporte = st.text_input("Observações do Aporte")
                
                if st.form_submit_button("Registrar Aporte 🚀", type="primary"):
                    # 🛡️ Travas de segurança antes de salvar
                    if socio_aporte == "---":
                        st.warning("⚠️ Selecione um sócio.")
                    elif valor_aporte <= 0:
                        st.warning("⚠️ O valor do aporte deve ser maior que zero.")
                    else:
                        try:
                            aba_ap = planilha_mestre.worksheet("APORTES")
                            cod_soc, nome_soc = socio_aporte.split(" - ")[0], socio_aporte.split(" - ")[1]
                            aba_ap.append_row([
                                datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%d/%m/%Y %H:%M"),
                                cod_soc, nome_soc, valor_aporte, tipo_aporte, obs_aporte
                            ], value_input_option='RAW')
                            st.success("✅ Capital injetado com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar na aba APORTES: {e}")
        except Exception as e:
            st.error(f"Aba SOCIOS não configurada. {e}")

        st.divider()

        # --- 3. CAP TABLE (QUADRO SOCIETÁRIO E MÉTRICAS) ---
        st.markdown("##### 📊 Cap Table e Balanço dos Sócios")
        st.caption("Distribuição de Equity calculada automaticamente pelo volume financeiro aportado por cada sócio.")
        
        try:
            if not df_socios.empty:
                # O processamento numérico já foi feito lá em cima no Mini Dashboard
                if not df_aportes.empty:
                    aportes_por_socio = df_aportes.groupby('NOME_SOCIO')['VALOR_NUM'].sum().to_dict()
                else:
                    aportes_por_socio = {}

                if not df_retiradas.empty:
                    retiradas_por_socio = df_retiradas.groupby('CLIENTE')['RETIRADA_NUM'].sum().to_dict()
                else:
                    retiradas_por_socio = {}

                # Montando a Tabela de Sócios
                dados_cap_table = []
                for _, row in df_socios.iterrows():
                    n_socio = str(row['NOME']).strip()
                    t_aporte = aportes_por_socio.get(n_socio, 0.0)
                    t_retirada = retiradas_por_socio.get(n_socio, 0.0)
                    balanco = t_aporte - t_retirada
                    
                    # Participação baseada no montante injetado
                    participacao = (t_aporte / aporte_total_empresa * 100) if aporte_total_empresa > 0 else 0.0
                    
                    dados_cap_table.append({
                        "Sócio": n_socio,
                        "Equity (%)": f"{participacao:.1f}%",
                        "Capital Injetado": t_aporte,
                        "Produtos Retirados": t_retirada,
                        "Balanço Liquido": balanco
                    })
                
                df_cap = pd.DataFrame(dados_cap_table)
                
                st.dataframe(
                    df_cap,
                    column_config={
                        "Capital Injetado": st.column_config.NumberColumn(help="Total em dinheiro que este sócio investiu.", format="R$ %.2f"),
                        "Produtos Retirados": st.column_config.NumberColumn("Retirado (Col L)", help="Valor consumido da loja em produtos.", format="R$ %.2f"),
                        "Balanço Liquido": st.column_config.NumberColumn(help="Capital Injetado - Produtos Retirados.", format="R$ %.2f")
                    },
                    use_container_width=True, hide_index=True
                )
                
                # --- 4. HISTÓRICO RÁPIDO DO BANCO SWEET (INJEÇÕES E RETIRADAS) ---
                st.divider()
                st.markdown("#### 📜 Extrato do Banco Sweet")
                t_inv, t_ret = st.tabs(["Injeções de Dinheiro", "Peças Retiradas"])
                
                with t_inv:
                    if not df_aportes.empty:
                        # Exibe as injeções com as colunas relevantes
                        st.dataframe(df_aportes[['DATA', 'NOME_SOCIO', 'VALOR_R$', 'TIPO', 'OBSERVACOES']], use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhum aporte financeiro registrado ainda na aba APORTES.")
                
                with t_ret:
                    if not df_retiradas.empty:
                        # Exibe as peças tiradas com base na aba VENDAS
                        st.dataframe(df_retiradas[['DATA DA VENDA', 'CLIENTE', 'PRODUTO', 'TOTAL R$', 'FORMA DE PAGAMENTO']], use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhuma retirada de produto registrada pelos sócios.")

            else:
                st.warning("Cadastre o primeiro sócio acima para gerar o Cap Table.")
        except Exception as e:
            st.error(f"Erro ao calcular Cap Table. Certifique-se que as abas SOCIOS e APORTES existem. {e}")
            
    st.markdown("### 🔍 Ficha de Cliente (Extrato Dinâmico)")
    opcoes_ficha = sorted([f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
    sel_ficha = st.selectbox("Selecione para ver o que ela deve:", ["---"] + opcoes_ficha, key="ficha_sel_cliente")
    
    if sel_ficha != "---":
        id_c = sel_ficha.split(" - ")[0]
        nome_c_ficha = " - ".join(sel_ficha.split(" - ")[1:])
        v_hist = df_vendas_hist[df_vendas_hist['CÓD. CLIENTE'].astype(str) == id_c]
        
        # Cria uma coluna numérica temporária para facilitar a soma e o filtro
        v_hist['SALDO_NUM'] = v_hist['SALDO DEVEDOR'].apply(limpar_v)
        saldo_devedor_real = v_hist['SALDO_NUM'].sum()
        
        c_f1, c_f2 = st.columns(2)
        c_f1.metric("Saldo Devedor Atual", f"R$ {saldo_devedor_real:,.2f}")
        
        if saldo_devedor_real > 0.01:
            # ---------------------------------------------------------
            # 1. BUSCA INTELIGENTE DO NÚMERO NA CARTEIRA DE CLIENTES
            # ---------------------------------------------------------
            dados_cliente = banco_de_clientes.get(id_c, {})
            telefone_cru = str(dados_cliente.get('TELEFONE', dados_cliente.get('telefone', dados_cliente.get('fone', ''))))
            
            # Limpa tudo que não for número e garante o 55 do Brasil
            tel_c = "".join(filter(str.isdigit, telefone_cru))
            if tel_c and not tel_c.startswith("55"): 
                tel_c = "55" + tel_c

            # ---------------------------------------------------------
            # 2. CONSTRUÇÃO DO RECIBO FINANCEIRO (VERSÃO PREMIUM MOBILE)
            # ---------------------------------------------------------
            lista_extrato = ""
            
            # Varre TODO o histórico com visual de Ticket e Emojis
            for _, row in v_hist.iterrows():
                status_atual = str(row['STATUS']).strip()
                
                if status_atual.lower() in ['pago', 'quitado', 'ok']:
                    icone = "✅ *PAGO*"
                else:
                    icone = "⏳ *PENDENTE*"
                
                lista_extrato += f"🛍️ *{row['PRODUTO']}*\n ├ 📅 Data: {row['DATA DA VENDA']}\n └ 🏷️ Status: {icone}\n\n"
            
            saldo_formatado = f"R$ {saldo_devedor_real:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            # MENSAGEM 1: COBRANÇA (Design Sweet Home)
            msg_cobranca = (
                f"Olá, *{nome_c_ficha}*! Tudo bem? 🌸\n\n"
                f"Aqui é do *Setor Financeiro da Sweet Home Enxovais*.\n"
                f"Criamos esse departamento recentemente para melhorar a nossa organização e estarmos ainda mais próximos de você! ✨\n\n"
                f"Passando para deixar o resumo atualizado da sua ficha conosco:\n\n"
                f"📑 *SEU HISTÓRICO DE COMPRAS:*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"{lista_extrato}"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💰 *Total Pendente Atual: {saldo_formatado}*\n\n"
                f"Qualquer dúvida sobre os itens ou se precisar da nossa chave PIX para regularizar, estou à disposição! 🥰"
            )

            # MENSAGEM 2: LEMBRETE PREVENTIVO (Design Sweet Home)
            msg_lembrete = (
                f"Olá, *{nome_c_ficha}*! Tudo bem? 🌸\n\n"
                f"Aqui é do *Setor Financeiro da Sweet Home Enxovais*.\n\n"
                f"Passando apenas para te enviar um lembrete super amigável de que você tem itens com vencimento se aproximando. ✨\n\n"
                f"📑 *RESUMO DA SUA FICHA:*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"{lista_extrato}"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💰 *Valor programado para acerto: {saldo_formatado}*\n\n"
                f"Se precisar da nossa chave PIX para já deixar agendado, é só me avisar. Tenha um excelente dia! 🥰"
            )
            
            # ---------------------------------------------------------
            # 3. EXIBIÇÃO DOS BOTÕES LADO A LADO (Bypass com HTML Puro)
            # ---------------------------------------------------------
            if tel_c:
                st.write("#### 🎯 Escolha a abordagem:")
                col_btn1, col_btn2 = st.columns(2)
                
                # Voltamos para o quote normal, o HTML vai cuidar do resto
                url_cob = f"https://wa.me/{tel_c}?text={urllib.parse.quote(msg_cobranca)}"
                url_prev = f"https://wa.me/{tel_c}?text={urllib.parse.quote(msg_lembrete)}"
                
                # Criando botões com HTML/CSS para driblar o bloqueio do Streamlit
                btn_cob_html = f"""<a href="{url_cob}" target="_blank" style="display: block; width: 100%; text-align: center; background-color: #ff4b4b; color: white; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold;">🚨 Enviar Cobrança (Atrasados)</a>"""
                
                btn_prev_html = f"""<a href="{url_prev}" target="_blank" style="display: block; width: 100%; text-align: center; background-color: #262730; color: white; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold;">📅 Enviar Lembrete (Preventivo)</a>"""
                
                with col_btn1:
                    st.markdown(btn_cob_html, unsafe_allow_html=True)
                
                with col_btn2:
                    st.markdown(btn_prev_html, unsafe_allow_html=True)
                
                # ---------------------------------------------------------
                # 4. MÓDULO DE IA SOB DEMANDA
                # ---------------------------------------------------------
                st.markdown("---")
                st.write("✨ **Precisa de uma abordagem diferente?**")
                
                if st.button("🤖 Personalizar mensagem com IA", use_container_width=True):
                    st.session_state['ia_ficha_ativa'] = True
                    
                if st.session_state.get('ia_ficha_ativa', False):
                    tipo_ia = st.radio("Qual mensagem você quer que a IA reescreva?", ["Cobrança", "Lembrete Preventivo"])
                    msg_base_ia = msg_cobranca if tipo_ia == "Cobrança" else msg_lembrete
                    
                    with st.spinner("🤖 Consultando a IA (Modo Seguro)..."):
                        try:
                            import google.generativeai as genai
                            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                            
                            prompt = f"""
                            Você atua no Setor Financeiro da 'Sweet Home Enxovais'. 
                            Reescreva a mensagem abaixo para deixá-la incrivelmente empática e persuasiva, mas sem perder a educação. 
                            MANTENHA INTACTA a lista de produtos (o histórico com as datas) e o valor final.
                            
                            ⚠️ REGRA CRÍTICA: Retorne EXATAMENTE APENAS o texto da mensagem final. 
                            NÃO inclua introduções como "Com certeza!", "Aqui está..." ou tracejados iniciais. 
                            NÃO explique o que você fez. O texto deve estar pronto para eu copiar e colar diretamente no WhatsApp.
                            Você PODE e DEVE utilizar emojis estratégicos para deixar a mensagem amigável e simpática.
                            
                            Mensagem:
                            {msg_base_ia}
                            """
                            
                            # 💡 AJUSTE DA IA: Removido o modelo velho (pro) e inserido o tradutor de limites (429)
                            modelos = ["gemini-2.0-flash"]
                            resultado_ia = None
                            erro_google = ""
                            
                            for m in modelos:
                                try:
                                    modelo_gen = genai.GenerativeModel(m)
                                    resultado_ia = modelo_gen.generate_content(prompt)
                                    if resultado_ia:
                                        break
                                except Exception as e:
                                    erro_str = str(e)
                                    if "429" in erro_str or "quota" in erro_str.lower():
                                        erro_google = "⏳ Limite de consultas rápidas atingido. Por favor, aguarde 30 segundos e clique novamente."
                                    else:
                                        erro_google = erro_str
                                    continue
                                
                            if resultado_ia:
                                st.success("✨ Mensagem Otimizada com Sucesso!")
                                texto_final_ia = st.text_area("Revise a mensagem da IA:", value=resultado_ia.text.strip(), height=250)
                                
                                # Botão Nativo (st.link_button) para garantir que os Emojis gerados pela IA não quebrem
                                url_ia = f"https://wa.me/{tel_c}?text={urllib.parse.quote(texto_final_ia)}"
                                st.link_button("📲 Enviar Mensagem da IA", url_ia, use_container_width=True, type="primary")
                                
                                st.write("") # Espaçinho visual
                                if st.button("❌ Dispensar IA"):
                                    st.session_state['ia_ficha_ativa'] = False
                                    st.rerun()
                            else:
                                st.error(f"⚠️ {erro_google}" if erro_google else "⚠️ Nenhum modelo de IA suportou a requisição no momento.")
                        except Exception as e_ia:
                            st.error(f"⚠️ Erro de comunicação com o Google: {e_ia}")

            else:
                st.error("⚠️ Telefone não localizado na base desta cliente.")
                
        else: 
            st.success("✅ Esta cliente não possui débitos pendentes.")

        st.write("#### ⏳ Histórico de Vendas Localizado")
        if not v_hist.empty:
            st.dataframe(v_hist[['DATA DA VENDA', 'PRODUTO', 'TOTAL R$', 'SALDO DEVEDOR', 'STATUS']], use_container_width=True, hide_index=True)
        else: 
            st.info("Nenhuma compra registrada para esta cliente ainda.")

# ==========================================
# --- SEÇÃO 3: ESTOQUE (MEMÓRIA ETERNA + IA) ---
# ==========================================
elif menu_selecionado == "📦 Estoque":
    st.subheader("📦 Gestão Inteligente de Estoque")
    df_estoque = df_full_inv.copy()

    if not df_estoque.empty:
        df_estoque['EST_NUM'] = pd.to_numeric(df_estoque['ESTOQUE ATUAL'], errors='coerce').fillna(0)
        df_estoque['VENDAS_NUM'] = pd.to_numeric(df_estoque['QTD VENDIDA'], errors='coerce').fillna(0)
        df_estoque['CUSTO_NUM'] = df_estoque['CUSTO UNITÁRIO R$'].apply(limpar_v)
        
        total_skus = len(df_estoque)
        capital_parado = (df_estoque['EST_NUM'] * df_estoque['CUSTO_NUM']).sum()
        qtd_furos = len(df_estoque[df_estoque['EST_NUM'] <= 0])
        qtd_baixos = len(df_estoque[(df_estoque['EST_NUM'] > 0) & (df_estoque['EST_NUM'] <= 3)])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 Itens no Catálogo", total_skus)
        c2.metric("💰 Capital na Prateleira", f"R$ {capital_parado:,.2f}")
        c3.metric("🚨 Esgotados / Furos", qtd_furos)
        c4.metric("⚠️ Estoque Baixo (≤3)", qtd_baixos)

        with st.expander("📊 Central de Reposição e Tendências", expanded=False):
            tab1, tab2 = st.tabs(["🚨 Malha Fina", "🏆 Campeões de Venda"])
            with tab1:
                criticos_df = df_estoque[df_estoque['EST_NUM'] <= 3].copy()
                if not criticos_df.empty:
                    criticos_df['Status'] = criticos_df['EST_NUM'].apply(lambda x: "🔴 Esgotado" if x <= 0 else "🟡 Acabando")
                    st.dataframe(criticos_df[['CÓD. PRÓDUTO', 'NOME DO PRODUTO', 'ESTOQUE ATUAL', 'Status']].sort_values('ESTOQUE ATUAL'), use_container_width=True, hide_index=True)
                else: st.success("✨ Tudo em ordem!")
            with tab2:
                campeoes_df = df_estoque[df_estoque['VENDAS_NUM'] > 0].sort_values(by='VENDAS_NUM', ascending=False).head(10)
                if not campeoes_df.empty:
                    st.dataframe(campeoes_df[['CÓD. PRÓDUTO', 'NOME DO PRODUTO', 'QTD VENDIDA', 'ESTOQUE ATUAL']], use_container_width=True, hide_index=True)
                else: st.info("Aguardando volume de vendas.")

    # ==========================================
    # 🤖 ENTRADA INTELIGENTE (IA GEMINI)
    # ==========================================
    st.divider()
    with st.expander("🤖 Entrada Inteligente (Ler Nota Fiscal com IA)", expanded=False):
        st.write("Tire uma foto da Nota Fiscal ou Recibo do fornecedor e deixe a IA ler os itens para você!")
        foto_nf = st.file_uploader("Envie a foto da Nota", type=['png', 'jpg', 'jpeg'], key="uploader_ia_estoque")
        
        if foto_nf is not None:
            if st.button("🧠 Ler Documento", use_container_width=True, key="btn_ler_ia"):
                with st.spinner("A IA está analisando a imagem. Isso leva alguns segundos... ⏳"):
                    try:
                        # Conecta com a sua chave
                        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                        modelo_ia = genai.GenerativeModel('gemini-2.5-flash')
                        
                        # Prepara a imagem
                        img = Image.open(foto_nf)
                        
                        # A "ordem" que damos para a IA
                        prompt = """
                        Você é o assistente de estoque da 'Sweet Home Enxovais'. 
                        Sua tarefa é ler esta nota fiscal ou recibo e extrair os produtos.
                        
                        Aja como um sistema. Retorne o resultado EXATAMENTE no formato de uma tabela Markdown com as seguintes colunas:
                        | Qtd | Descrição do Produto | Custo Unitário (R$) | Valor Total (R$) |
                        
                        REGRAS RÍGIDAS:
                        1. Retorne APENAS a tabela. Não escreva nenhum texto de saudação, explicação ou formatação fora da tabela.
                        2. Extraia os valores com precisão.
                        3. Se a imagem não for uma nota fiscal ou estiver ilegível, retorne APENAS a frase: "⚠️ Documento ilegível ou não reconhecido. Tente enviar uma foto mais nítida."
                        """
                        
                        # A mágica acontece aqui
                        resposta = modelo_ia.generate_content([prompt, img])
                        
                        st.success("✅ Leitura Concluída!")
                        st.markdown("#### 📋 Produtos Identificados na Nota:")
                        
                        # Exibe a resposta da IA nativamente
                        st.markdown(resposta.text)
                        st.warning("💡 Dica: Use a lista acima para copiar os nomes e dar a entrada rápida no 'Radar de Entrada' logo abaixo.")
                        
                    except Exception as e:
                        st.error(f"⚠️ Ocorreu um erro na IA: {e}")
                        st.caption("Verifique se a chave do Google está correta nos Secrets.")

    st.divider()
    st.write("### 🔍 Radar de Entrada")
    
    # 🎯 CORREÇÃO AQUI: Atribuindo o valor do input à variável 'busca_radar'
    busca_radar = st.text_input("Pesquisar produto para atualizar", placeholder="Ex: lencol casal ou 800", key="txt_busca_radar")
    
    if busca_radar and not df_estoque.empty:
        t_limpo = limpar_texto(busca_radar)
        df_estoque['Nome_L'] = df_estoque['NOME DO PRODUTO'].apply(limpar_texto)
        df_estoque['Cod_L'] = df_estoque['CÓD. PRÓDUTO'].astype(str).str.lower().str.strip()
        res = df_estoque[df_estoque['Nome_L'].str.contains(t_limpo, na=False) | df_estoque['Cod_L'].str.contains(t_limpo, na=False)]
        
        if not res.empty:
            opcs = ["Nenhum. É um produto 100% NOVO."] + [f"{r['CÓD. PRÓDUTO']} - {r['NOME DO PRODUTO']}" for _, r in res.iterrows()]
            p_alvo = st.radio("Produto encontrado:", opcs, key="res_radar_radio")
            
            if p_alvo != "Nenhum. É um produto 100% NOVO.":
                cod_e = p_alvo.split(" - ")[0]
                idx = df_estoque[df_estoque['CÓD. PRÓDUTO'] == cod_e].index[0]
                lin_p = int(idx) + 2
                nome_e = df_estoque.loc[idx, 'NOME DO PRODUTO']
                est_h = int(pd.to_numeric(df_estoque.loc[idx, 'ESTOQUE ATUAL'], errors='coerce') or 0)
                vend_g = int(pd.to_numeric(df_estoque.loc[idx, 'QTD VENDIDA'], errors='coerce') or 0)
                comp_c = int(pd.to_numeric(df_estoque.loc[idx, 'QUANTIDADE'], errors='coerce') or 0)
                custo_at = limpar_v(df_estoque.loc[idx, 'CUSTO UNITÁRIO R$'])
                preco_at = limpar_v(df_estoque.loc[idx, 'VALOR DE VENDA'])

                acao = st.selectbox("Ação:", ["Selecione...", "1. Reposição", "2. Novo Lote (Preço Novo)", "3. Correção"], key="acao_radar_select")

                if acao == "1. Reposição":
                    with st.form("f_rep"):
                        q_nova = st.number_input("Quantidade recebida", 1)
                        if st.form_submit_button("Confirmar Entrada"):
                            with st.spinner("Atualizando..."):
                                aba = planilha_mestre.worksheet("INVENTÁRIO")
                                aba.update_acell(f"C{lin_p}", comp_c + q_nova)
                                aba.update_acell(f"J{lin_p}", datetime.now().strftime("%d/%m/%Y"))
                                planilha_mestre.worksheet("LOG_ESTOQUE").append_row([datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), "REPOSIÇÃO", nome_e, f"+{q_nova} un.", st.session_state.get('usuario_logado', 'Bia')], value_input_option='RAW')
                                st.success("Estoque Atualizado!"); st.cache_data.clear(); st.cache_resource.clear(); st.rerun()

                elif acao == "2. Novo Lote (Preço Novo)":
                    with st.form("f_lote"):
                        c1, c2, c3 = st.columns(3)
                        q_l = c1.number_input("Qtd nova", 0)
                        cu_l = c2.number_input("Novo Custo", value=float(custo_at))
                        pr_l = c3.number_input("Novo Preço", value=float(preco_at))
                        puxar = st.checkbox(f"Puxar {est_h} itens antigos?", value=True)
                        if st.form_submit_button("Gerar Lote"):
                            with st.spinner("Criando lote..."):
                                aba = planilha_mestre.worksheet("INVENTÁRIO")
                                f_total_e = '=SE(INDIRETO("C"&LIN())=""; ""; ARRED(INDIRETO("C"&LIN()) * INDIRETO("D"&LIN()); 2))'
                                f_estoque_h = '=SE(INDIRETO("C"&LIN())=""; ""; INDIRETO("C"&LIN()) - INDIRETO("G"&LIN()))'
                                base = str(cod_e).split(".")[0]; ext = str(cod_e).split(".")[1] if "." in str(cod_e) else "0"
                                n_cod = f"{base}.{int(ext)+1}"
                                if puxar: aba.update_acell(f"C{lin_p}", vend_g)
                                nova_linha = [n_cod, f"{nome_e} (Lote {int(ext)+1})", q_l + (est_h if puxar else 0), cu_l, f_total_e, 3, 0, f_estoque_h, pr_l, datetime.now().strftime("%d/%m/%Y"), ""]
                                cel_tot = aba.find("TOTAIS")
                                if cel_tot: aba.insert_row(nova_linha, index=cel_tot.row, value_input_option='RAW')
                                else: aba.append_row(nova_linha, value_input_option='RAW')
                                planilha_mestre.worksheet("LOG_ESTOQUE").append_row([datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), "NOVO LOTE", nome_e, f"Lote {n_cod}", st.session_state.get('usuario_logado', 'Bia')], value_input_option='RAW')
                                st.success(f"Lote {n_cod} criado!"); st.cache_data.clear(); st.cache_resource.clear(); st.rerun()

                elif acao == "3. Correção":
                    with st.form("f_cor"):
                        real = st.number_input("Qtd real física", value=est_h)
                        if st.form_submit_button("Corrigir"):
                            with st.spinner("Sincronizando..."):
                                aba = planilha_mestre.worksheet("INVENTÁRIO")
                                aba.update_acell(f"C{lin_p}", real + vend_g)
                                planilha_mestre.worksheet("LOG_ESTOQUE").append_row([datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), "CORREÇÃO", nome_e, f"Ajustado para {real}", st.session_state.get('usuario_logado', 'Bia')], value_input_option='RAW')
                                st.success("Corrigido!"); st.cache_data.clear(); st.cache_resource.clear(); st.rerun()

    st.divider()
    with st.expander("➕ Cadastrar Novo Produto"):
        with st.form("f_est_original", clear_on_submit=True):
            c1, c2 = st.columns([1, 2]); n_c = c1.text_input("Cód."); n_n = c2.text_input("Nome")
            c3, c4, c5 = st.columns(3); n_q = c3.number_input("Qtd", 0); n_custo = c4.number_input("Custo (R$)", 0.0); n_v = c5.number_input("Venda (R$)", 0.0)
            if st.form_submit_button("Salvar Novo Produto") and n_c and n_n:
                with st.spinner("Cadastrando..."):
                    aba = planilha_mestre.worksheet("INVENTÁRIO")
                    f_total_e = '=SE(INDIRETO("C"&LIN())=""; ""; ARRED(INDIRETO("C"&LIN()) * INDIRETO("D"&LIN()); 2))'
                    f_estoque_h = '=SE(INDIRETO("C"&LIN())=""; ""; INDIRETO("C"&LIN()) - INDIRETO("G"&LIN()))'
                    linha_manual = [n_c, n_n, n_q, n_custo, f_total_e, 3, 0, f_estoque_h, n_v, datetime.now().strftime("%d/%m/%Y"), ""]
                    cel_tot = aba.find("TOTAIS")
                    if cel_tot: aba.insert_row(linha_manual, index=cel_tot.row, value_input_option='RAW')
                    else: aba.append_row(linha_manual, value_input_option='RAW')
                    planilha_mestre.worksheet("LOG_ESTOQUE").append_row([datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), "CADASTRO", n_n, f"Cód: {n_c}", st.session_state.get('usuario_logado', 'Bia')], value_input_option='RAW')
                    st.success("✅ Cadastrado!"); st.cache_data.clear(); st.cache_resource.clear(); st.rerun()

    st.divider()
    st.write("### 📜 Histórico de Movimentações (Banco de Dados)")
    try:
        df_log_db = pd.DataFrame(planilha_mestre.worksheet("LOG_ESTOQUE").get_all_records())
        if not df_log_db.empty:
            st.dataframe(df_log_db.sort_index(ascending=False).head(20), use_container_width=True, hide_index=True)
        else: st.info("Nenhuma movimentação registrada.")
    except: st.warning("Aba 'LOG_ESTOQUE' não encontrada.")
    
    st.divider()
    busca_lista = st.text_input("🔍 Buscar na Lista Abaixo", key="txt_busca_lista_estoque")
    df_ver = df_full_inv.copy()
    if busca_lista: df_ver = df_ver[df_ver.apply(lambda r: busca_lista.lower() in str(r).lower(), axis=1)]
    st.dataframe(df_ver, use_container_width=True, hide_index=True)
    
# ==========================================
# --- SEÇÃO 4: CLIENTES ---
# ==========================================
elif menu_selecionado == "👥 Clientes":
    st.subheader("👥 Gestão de Clientes e CRM")

    if not df_vendas_hist.empty and not df_clientes_full.empty:
        df_v_crm = df_vendas_hist.copy()
        df_v_crm['DATA_DATETIME'] = pd.to_datetime(df_v_crm['DATA DA VENDA'], format='%d/%m/%Y', errors='coerce')
        
        ultima_compra = df_v_crm.groupby('CÓD. CLIENTE')['DATA_DATETIME'].max().reset_index()
        hoje = pd.to_datetime(datetime.now().date())
        ultima_compra['DIAS_AUSENTE'] = (hoje - ultima_compra['DATA_DATETIME']).dt.days
        
        sumidas = ultima_compra[ultima_compra['DIAS_AUSENTE'] >= 60].copy()
        
        with st.expander(f"🎯 CRM: Radar de Retenção ({len(sumidas)} clientes ausentes há +60 dias)", expanded=False):
            if not sumidas.empty:
                st.write("Estas clientes não compram há mais de 2 meses. Que tal enviar uma promoção?")
                df_c_crm = df_clientes_full.rename(columns={df_clientes_full.columns[0]: 'CÓD. CLIENTE', df_clientes_full.columns[1]: 'NOME', df_clientes_full.columns[2]: 'ZAP'})
                sumidas_full = sumidas.merge(df_c_crm[['CÓD. CLIENTE', 'NOME', 'ZAP']], on='CÓD. CLIENTE', how='left')
                
                for _, cliente in sumidas_full.iterrows():
                    dias = int(cliente['DIAS_AUSENTE'])
                    nome = str(cliente['NOME'])
                    zap = str(cliente['ZAP']).replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                    
                    c_crm1, c_crm2 = st.columns([3, 1])
                    c_crm1.write(f"👤 **{nome}** (Última compra há {dias} dias)")
                    
                    if zap and zap != "nan":
                        msg_recuperacao = f"Olá {nome.split(' ')[0]}! Que saudade de você aqui na Sweet Home Enxovais 🌸. Preparamos novidades lindas e um mimo especial para você. Como você está?"
                        c_crm2.link_button("📲 Enviar Mensagem", f"https://wa.me/55{zap}?text={urllib.parse.quote(msg_recuperacao)}", use_container_width=True)
                    else:
                        c_crm2.write("❌ Sem Zap")
                    st.divider()
            else:
                st.success("Parabéns! Suas clientes estão ativas e comprando recentemente. 🚀")

    st.divider()

    with st.expander("➕ Cadastrar Nova Cliente (Sem compra atual)", expanded=False):
        with st.form("form_novo_manual", clear_on_submit=True):
            st.markdown("Código gerado automaticamente.")
            c1, c2 = st.columns([2, 1])
            n_nome = c1.text_input("Nome Completo *")
            n_zap = c2.text_input("WhatsApp *")
            c3, c4 = st.columns([3, 1])
            n_end = c3.text_input("Endereço")
            n_vale = c4.number_input("Vale Desconto", 0.0)
            if st.form_submit_button("Salvar Cadastro 💾"):
                if n_nome and n_zap:
                    try:
                        aba_cli_sheet = planilha_mestre.worksheet("CARTEIRA DE CLIENTES")
                        codigo = f"CLI-{len(aba_cli_sheet.get_all_values()):03d}"
                        aba_cli_sheet.append_row([codigo, n_nome.strip(), n_zap.strip(), n_end.strip(), datetime.now().strftime("%d/%m/%Y"), n_vale, "", "Completo" if n_end else "Incompleto"], value_input_option='USER_ENTERED')
                        st.success(f"✅ {n_nome} cadastrada!")
                        st.cache_data.clear()
                        st.cache_resource.clear()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    st.divider()
    
    if not df_clientes_full.empty:
        try:
            inc = df_clientes_full[df_clientes_full.iloc[:, 7].str.strip() == "Incompleto"]
            if not inc.empty:
                st.warning(f"🚨 Radar: {len(inc)} cadastros pendentes!")
                st.dataframe(inc, hide_index=True)
        except:
            pass
        st.markdown("### 🗂️ Carteira Total")
        st.dataframe(df_clientes_full, use_container_width=True, hide_index=True)
        
    with st.expander("🔄 Atualizar Dados de Cliente Existente", expanded=False):
        lista_clientes_edit = [f"{row[0]} - {row[1]}" for row in df_clientes_full.values]
        escolha = st.selectbox("Selecione a Cliente para editar", ["---"] + lista_clientes_edit, key="sel_edit_cli_manual")

        if escolha != "---":
            id_edit = escolha.split(" - ")[0]
            dados_atuais = df_clientes_full[df_clientes_full.iloc[:, 0] == id_edit].iloc[0]

            with st.form("form_atualizar_cli_v1"):
                st.info(f"Editando: {id_edit} - {dados_atuais[1]}")
                
                col1, col2 = st.columns(2)
                novo_nome = col1.text_input("Nome Completo", value=str(dados_atuais[1]))
                novo_zap = col2.text_input("WhatsApp", value=str(dados_atuais[2]))
                
                val_original = dados_atuais[5]
                try:
                    valor_limpo = float(val_original) if (pd.notna(val_original) and str(val_original).strip() != "") else 0.0
                except:
                    valor_limpo = 0.0

                novo_end = st.text_input("Endereço", value=str(dados_atuais[3]) if pd.notna(dados_atuais[3]) else "")
                novo_vale = st.number_input("Vale Desconto", value=valor_limpo)

                botao_salvar = st.form_submit_button("Salvar Alterações 💾", use_container_width=True)

                if botao_salvar:
                    try:
                        aba_cli_sheet = planilha_mestre.worksheet("CARTEIRA DE CLIENTES")
                        celula = aba_cli_sheet.find(id_edit)
                        num_linha = celula.row

                        aba_cli_sheet.update_cell(num_linha, 2, novo_nome.strip())
                        aba_cli_sheet.update_cell(num_linha, 3, novo_zap.strip())
                        aba_cli_sheet.update_cell(num_linha, 4, novo_end.strip())
                        aba_cli_sheet.update_cell(num_linha, 6, novo_vale)
                        
                        novo_status = "Completo" if novo_end.strip() else "Incompleto"
                        aba_cli_sheet.update_cell(num_linha, 8, novo_status)

                        st.success(f"✅ Dados de {novo_nome} atualizados!")
                        st.cache_data.clear()
                        st.cache_resource.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")

# ==========================================
# 🌟 SEÇÃO 5: DOCUMENTOS & FILA ODOO (NOVA ENGINE CLOUDINARY) 🌟
# ==========================================
elif menu_selecionado == "📂 Documentos":
    st.subheader("📂 Cofre Digital & Fila Odoo")

    try:
        dados_doc = planilha_mestre.worksheet("DOCUMENTOS").get_all_values()
        df_docs = pd.DataFrame(dados_doc[1:], columns=dados_doc[0]) if len(dados_doc) > 1 else pd.DataFrame()
    except: 
        df_docs = pd.DataFrame()

    with st.expander("🚀 Linha de Montagem Odoo (Site)", expanded=True):
        t_falta, t_pronto = st.tabs(["🔴 1. Falta Foto (Bia)", "🟢 2. Pronto p/ Site (Você)"])
        
        # --- ABA 1: O QUE A BIA PRECISA FOTOGRAFAR ---
        with t_falta:
            st.write("**Produtos no inventário aguardando foto para o site:**")
            if not df_full_inv.empty:
                prods_com_foto = []
                # Verifica na aba DOCUMENTOS quem já tem foto
                if not df_docs.empty and 'VINCULO' in df_docs.columns:
                    fotos = df_docs[df_docs['TIPO'] == "Foto de Produto"]
                    prods_com_foto = [str(p).split(" - ")[0].strip() for p in fotos['VINCULO'].dropna() if " - " in str(p)]
                
                # Filtra o inventário tirando quem já tem foto
                df_falta = df_full_inv[~df_full_inv['CÓD. PRÓDUTO'].astype(str).str.strip().isin(prods_com_foto)].copy()
                
                # Limpeza de segurança: Remove linhas vazias e a linha de 'TOTAIS'
                df_falta = df_falta[
                    (df_falta['CÓD. PRÓDUTO'].str.strip() != "") & 
                    (~df_falta['CÓD. PRÓDUTO'].str.upper().str.contains("TOTAIS", na=False))
                ]

                if not df_falta.empty:
                    # 💡 AQUI ESTÁ A MUDANÇA: Substituímos ESTOQUE ATUAL por STATUS ODOO
                    st.dataframe(
                        df_falta[['CÓD. PRÓDUTO', 'NOME DO PRODUTO', 'STATUS ODOO']], 
                        hide_index=True,
                        use_container_width=True
                    )
                else: 
                    st.success("🎉 Nenhuma pendência! O inventário inteiro tem foto.")

        # --- ABA 2: O QUE VOCÊ PRECISA PUBLICAR ---
        with t_pronto:
            st.write("**Fotos tiradas! Coloque no site e marque como publicado:**")
            if not df_docs.empty and 'STATUS_ODOO' in df_docs.columns:
                # Puxa apenas o que a Bia fotografou e ainda não foi pro site
                prontos = df_docs[(df_docs['TIPO'] == "Foto de Produto") & (df_docs['STATUS_ODOO'] == "Pronto para Site")]
                
                if not prontos.empty:
                    for idx, r in prontos.iterrows():
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.write(f"📦 **{r['VINCULO']}**")
                        c2.link_button("🖼️ Ver Foto", r['LINK_DRIVE'], use_container_width=True)
                        
                        # Botão manual (caso você não queira usar o robô e queira dar baixa na mão)
                        if c3.button("✅ Publicado", key=f"btn_odoo_{idx}"):
                            try:
                                aba_doc = planilha_mestre.worksheet("DOCUMENTOS")
                                cell = aba_doc.find(r['ID_ARQUIVO'])
                                aba_doc.update_cell(cell.row, 7, "Publicado no Odoo")
                                st.success("Atualizado!")
                                st.cache_data.clear()
                                st.cache_resource.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar: {e}")
                        st.divider()
                else: 
                    st.info("Sua fila de trabalho está limpa. 🚀")

    # --- 🤖 SEÇÃO: SINCRONIZADOR INTELIGENTE ODOO (V14) ---
    with st.expander("🤖 Sincronizador Inteligente (Análise de Versões)", expanded=True):
        st.write("Diagnóstico de versões e limpeza automática da vitrine.")

        # 1. INICIALIZAÇÃO DO COFRE DE MEMÓRIA (Fundamental para o relatório não sumir)
        if 'relatorio_fixo' not in st.session_state:
            st.session_state.relatorio_fixo = None

        # Botão de ação principal
        if st.button("🚀 Iniciar Nova Varredura Completa", use_container_width=True):
            try:
                # --- CARREGAMENTO E FILTRO DE TOTAIS ---
                aba_inv = planilha_mestre.worksheet("INVENTÁRIO")
                dados_inv = aba_inv.get_all_values()
                df_inv = pd.DataFrame(dados_inv[1:], columns=dados_inv[0])
                
                # Localiza a linha de TOTAIS para o robô parar
                idx_limite = df_inv[df_inv['CÓD. PRÓDUTO'].str.upper().str.contains("TOTAIS", na=False)].index.min()
                df_proc = df_inv.iloc[:idx_limite].copy() if not pd.isna(idx_limite) else df_inv.copy()
                df_proc = df_proc[df_proc['CÓD. PRÓDUTO'].str.strip() != ""]

                if not df_proc.empty:
                    # Mapeamento de versões (famílias .1, .2, etc)
                    df_proc['BASE'] = df_proc['CÓD. PRÓDUTO'].apply(lambda x: str(x).split('.')[0].strip())
                    mapa_mais_recente = df_proc.groupby('BASE')['CÓD. PRÓDUTO'].last().to_dict()

                    st.info(f"🔍 Varrendo {len(df_proc)} linhas do inventário...")
                    barra = st.progress(0)
                    status_txt = st.empty()
                    dados_acumulados = []
                    
                    # Acessa a aba DOCUMENTOS para a integração
                    aba_doc = planilha_mestre.worksheet("DOCUMENTOS")

                    for i, (idx, row) in enumerate(df_proc.iterrows()):
                        cod_atual = str(row['CÓD. PRÓDUTO']).strip()
                        base_cod = row['BASE']
                        versao_topo = mapa_mais_recente[base_cod]
                        linha_p = idx + 2
                        
                        status_txt.markdown(f"⏳ **Analisando:** `{cod_atual}`")
                        
                        # Chamada ao robô de busca
                        achou, link_ref = verificar_status_odoo(cod_atual)
                        time.sleep(1.3) # Respeito ao limite do Google

                        if achou:
                            # Lógica de diagnóstico de versão
                            if cod_atual == versao_topo:
                                status_inv, res_obs = "Publicado", "✅ Publicado (Atualizado)"
                            else:
                                status_inv, res_obs = "Publicado (Site Desatualizado)", "⚠️ Site com Versão Antiga"
                            
                            # Atualiza ABA INVENTÁRIO
                            aba_inv.update_cell(linha_p, 11, link_ref) # Link
                            aba_inv.update_cell(linha_p, 12, status_inv) # Status
                            
                            # 🔗 INTEGRAÇÃO COM DOCUMENTOS (Limpeza da Linha de Montagem)
                            if not df_docs.empty:
                                # Busca se o código atual está no vínculo das fotos
                                matches = df_docs[df_docs['VINCULO'].str.contains(cod_atual, na=False)].index
                                for m_idx in matches:
                                    aba_doc.update_cell(int(m_idx) + 2, 7, "Publicado no Odoo")
                        else:
                            # Caso não encontre no site
                            aba_inv.update_cell(linha_p, 12, "Não Publicado")
                            res_obs = "❌ Não Encontrado"

                        dados_acumulados.append({
                            "Linha": linha_p,
                            "Cód. SKU": cod_atual,
                            "Status Site": res_obs,
                            "Ação": "OK" if "✅" in res_obs else ("⚠️ Atualizar Odoo" if "⚠️" in res_obs else "❌ Publicar")
                        })
                        barra.progress((i + 1) / len(df_proc))

                    # 💾 SALVANDO RESULTADO NO COFRE
                    st.session_state.relatorio_fixo = pd.DataFrame(dados_acumulados)
                    status_txt.empty()
                    st.success("Varredura Finalizada!")
                    
                    # Limpa o cache e força o app a ler as planilhas novas
                    st.cache_data.clear()
                    st.rerun()

            except Exception as e:
                st.error(f"Erro na varredura: {e}")

        # --- 📋 EXIBIÇÃO DO RELATÓRIO FIXO ---
        # Esta parte fica fora do botão para não sumir após o rerun
        if st.session_state.relatorio_fixo is not None:
            st.divider()
            with st.expander("📊 Relatório da Última Verificação (Fixo)", expanded=True):
                
                # Estilização de cores (Verde, Amarelo, Vermelho)
                def style_status_cores(val):
                    if "✅" in val: return 'background-color: #d4edda; color: #155724'
                    if "⚠️" in val: return 'background-color: #fff3cd; color: #856404'
                    if "❌" in val: return 'background-color: #f8d7da; color: #721c24'
                    return ''

                st.dataframe(
                    st.session_state.relatorio_fixo.style.applymap(style_status_cores, subset=['Status Site']),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption("ℹ️ Este relatório é mantido até você iniciar uma nova varredura.")
                
                if st.button("🔄 Atualizar Vitrine Odoo Agora", key="btn_manual_refresh"):
                    st.cache_data.clear()
                    st.rerun()

    st.divider()
    st.write("### 📤 Enviar Arquivo")
    
    lista_categorias = ["Foto de Produto", "Nota Fiscal", "Comprovante", "Recibo / Pgto", "Contrato", "Outros"]
    cat_escolhida = st.selectbox("1️⃣ Categoria do Documento", lista_categorias)
    
    with st.form("form_upload_cloudinary", clear_on_submit=True):
        st.write("2️⃣ **Detalhes e Arquivo**")
        vinc_cli = "Nenhum"
        vinc_prod = "Nenhum"
        nome_livre = ""
        
        if cat_escolhida in ["Foto de Produto", "Nota Fiscal"]:
            st.info("📦 O sistema dará o nome do arquivo automaticamente com base no produto.")
            opcoes_prod = ["Nenhum"] + [f"{k} - {v['nome']}" for k, v in banco_de_produtos.items()]
            vinc_prod = st.selectbox("Selecione o Produto:", opcoes_prod)
        
        elif cat_escolhida in ["Comprovante", "Recibo / Pgto"]:
            st.info("👤 O sistema dará o nome do arquivo automaticamente com base na cliente.")
            opcoes_cli = ["Nenhum"] + [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()]
            vinc_cli = st.selectbox("Selecione a Cliente:", opcoes_cli)
        
        else:
            nome_livre = st.text_input("Nome ou Descrição Breve", help="Exemplo: Conta de Luz Janeiro")

        arquivo_subido = st.file_uploader("3️⃣ Escolha o arquivo (Imagem/PDF)", type=['png', 'jpg', 'jpeg', 'pdf'])
        
        if st.form_submit_button("Salvar no Cofre 🔒"):
            erro = False
            if not arquivo_subido:
                st.error("⚠️ Você esqueceu de anexar o arquivo!"); erro = True
            elif cat_escolhida in ["Foto de Produto", "Nota Fiscal"] and vinc_prod == "Nenhum":
                st.error("⚠️ Selecione um produto."); erro = True
            elif cat_escolhida in ["Comprovante", "Recibo / Pgto"] and vinc_cli == "Nenhum":
                st.error("⚠️ Selecione uma cliente."); erro = True
            elif cat_escolhida in ["Contrato", "Outros"] and not nome_livre:
                st.error("⚠️ Digite um nome para o documento."); erro = True

            if not erro:
                if vinc_prod != "Nenhum":
                    nome_gerado = f"[{cat_escolhida.upper()}] {vinc_prod}"
                    vinculo_final = vinc_prod
                elif vinc_cli != "Nenhum":
                    nome_gerado = f"[{cat_escolhida.upper()}] {vinc_cli}"
                    vinculo_final = vinc_cli
                else:
                    nome_gerado = f"[{cat_escolhida.upper()}] {nome_livre}"
                    vinculo_final = "-"
                
                nome_limpo = nome_gerado.replace("/", "-").replace(":", "")

                with st.spinner(f"Subindo para o servidor seguro... ⏳"):
                    f_id, f_link = upload_para_cloudinary(arquivo_subido.getvalue(), nome_limpo, cat_escolhida)
                    
                    if f_id:
                        try:
                            aba_doc = planilha_mestre.worksheet("DOCUMENTOS")
                            if len(aba_doc.get_all_values()) == 0:
                                aba_doc.append_row(["DATA", "TIPO", "NOME", "ID_ARQUIVO", "LINK_DRIVE", "VINCULO", "STATUS_ODOO"])
                            
                            status_odoo = "Pronto para Site" if cat_escolhida == "Foto de Produto" else "-"
                            
                            aba_doc.append_row([
                                datetime.now().strftime("%d/%m/%Y %H:%M"),
                                cat_escolhida, nome_limpo, f_id, f_link, vinculo_final, status_odoo
                            ], value_input_option='USER_ENTERED')
                            st.success(f"✅ Arquivado com sucesso!"); st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
                        except Exception as e: 
                            st.error(f"Erro na planilha: {e}")

    st.divider()
    st.write("### 🗂️ Histórico Geral de Documentos")
    
    if not df_docs.empty:
        categorias_existentes = ["Tudo"] + sorted(df_docs['TIPO'].unique().tolist())
        filtro_cat = st.selectbox("Filtrar por Categoria:", categorias_existentes)
        
        df_filtrado = df_docs.copy()
        if filtro_cat != "Tudo":
            df_filtrado = df_filtrado[df_filtrado['TIPO'] == filtro_cat]
            
        busca_doc = st.text_input("🔍 Pesquisar por Nome ou Código...")
        if busca_doc:
            df_filtrado = df_filtrado[df_filtrado.apply(lambda r: busca_doc.lower() in str(r).lower(), axis=1)]

        for _, r in df_filtrado.sort_index(ascending=False).head(10).iterrows():
            with st.container():
                col_a, col_b, col_c = st.columns([1, 3, 1])
                col_a.write(f"📅 {str(r['DATA']).split(' ')[0]}")
                col_b.write(f"**{r['TIPO']}**\n\n<small>{r['NOME']}</small>", unsafe_allow_html=True)
                col_c.link_button("👁️ Abrir", r['LINK_DRIVE'], use_container_width=True)
                st.divider()
    else:
        st.info("O cofre geral está vazio.")





























