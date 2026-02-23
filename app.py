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

# ==========================================
# 1. CONFIGURAÇÃO ÚNICA DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="🧪 TESTE - Sweet Home", 
    page_icon="logo_sweet_teste.png", 
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
            st.image("logo_sweet_teste.png", use_container_width=True)
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
        return None

planilha_mestre = conectar_google()

@st.cache_resource(ttl=600)
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

    banco_prod = {str(r.iloc[0]): {"nome": r.iloc[1], "custo": float(limpar_v(r.iloc[3])), "estoque": r.iloc[7], "venda": r.iloc[8]} for _, r in df_inv.iterrows()} if not df_inv.empty else {}
    banco_cli = {str(r.iloc[0]): {"nome": str(r.iloc[1]), "fone": str(r.iloc[2])} for _, r in df_cli.iterrows()} if not df_cli.empty else {}

    return banco_prod, banco_cli, df_inv, df_fin, df_vendas, df_painel, df_cli

banco_de_produtos, banco_de_clientes, df_full_inv, df_financeiro, df_vendas_hist, df_painel_resumo, df_clientes_full = carregar_dados()

with st.sidebar:
    try:
        st.image("logo_sweet_teste.png", use_container_width=True)
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
            c_zap = st.text_input("WhatsApp", value=telefone_sugerido, key="zap_venda_input")
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
                st.session_state['carrinho'].append(item_carrinho)
                st.toast(f"✅ {nome_p} no carrinho!")

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
                st.rerun()

            if c_btn2.button("Finalizar Venda 🚀", type="primary", use_container_width=True):
                # Validação de Cliente Novo
                if c_sel == "*** NOVO CLIENTE ***" and (not c_nome_novo or not c_zap):
                    st.error("⚠️ Preencha Nome e Zap para novo cliente!"); st.stop()

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
                            aba_v.insert_row(linha, index=idx_ins, value_input_option='RAW')

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
                    
                    zap_limpo = c_zap.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                    st.link_button("📲 Enviar Recibo Único para o WhatsApp", f"https://wa.me/55{zap_limpo}?text={urllib.parse.quote(recibo_texto)}", use_container_width=True, type="primary")

                    # Limpeza Final
                    st.session_state['carrinho'] = []
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
    # ✏️ BORRACHA MÁGICA: EDIÇÃO SEGURA DE VENDAS
    # ==========================================
    with st.expander("✏️ Corrigir Venda Recente", expanded=False):
        st.write("Escolha uma venda recente abaixo para corrigir cliente, produto ou valores.")
        
        try:
            aba_vendas = planilha_mestre.worksheet("VENDAS")
            dados_v = aba_vendas.get_all_values()
            
            if len(dados_v) > 1:
                vendas_recentes = []
                for i in range(len(dados_v)-1, max(0, len(dados_v)-21), -1):
                    linha = dados_v[i]
                    if "TOTAIS" not in str(linha[3]).upper() and linha[3] != "":
                        vendas_recentes.append(f"Linha {i+1} | Data: {linha[1]} | Cliente: {linha[3]} | Item: {linha[5]}")
                
                venda_selecionada = st.selectbox("Selecione a venda com erro:", ["---"] + vendas_recentes, help="Mostra apenas as últimas 20 vendas.")
                
                if venda_selecionada != "---":
                    linha_real = int(venda_selecionada.split(" | ")[0].replace("Linha ", ""))
                    linha_dados = dados_v[linha_real - 1]
                    
                    cod_cli_atual = linha_dados[2]
                    nome_cli_atual = linha_dados[3]
                    cod_prod_atual = linha_dados[4]
                    nome_prod_atual = linha_dados[5]
                    
                    def limpar_para_editar(val_str, is_perc=False):
                        try:
                            v = str(val_str).replace("R$", "").strip()
                            if is_perc and "%" in v:
                                v = v.replace("%", "").strip()
                                if "," in v and "." in v: v = v.replace(".", "").replace(",", ".")
                                elif "," in v: v = v.replace(",", ".")
                                return float(v) / 100.0
                            
                            if "," in v and "." in v: v = v.replace(".", "").replace(",", ".")
                            elif "," in v: v = v.replace(",", ".")
                            return float(v)
                        except:
                            return 0.0

                    qtd_atual = limpar_para_editar(linha_dados[7])
                    val_atual = limpar_para_editar(linha_dados[8])
                    desc_perc_atual = limpar_para_editar(linha_dados[9], is_perc=True)
                    
                    # ✨ TRAVA DE SEGURANÇA CONTRA BUGS ANTIGOS ✨
                    # Se o percentual na planilha estiver absurdo (maior que 100%) ou negativo, zera para não confundir.
                    if desc_perc_atual > 1.0 or desc_perc_atual < 0:
                        desc_reais_atual = 0.0
                    else:
                        desc_reais_atual = round((qtd_atual * val_atual) * desc_perc_atual, 2)
                        
                    metodo_atual = linha_dados[14]

                    lista_clientes = [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()]
                    cliente_str_atual = f"{cod_cli_atual} - {nome_cli_atual}"
                    idx_cliente = lista_clientes.index(cliente_str_atual) if cliente_str_atual in lista_clientes else 0

                    lista_produtos = [f"{k} - {v['nome']}" for k, v in banco_de_produtos.items()]
                    produto_str_atual = f"{cod_prod_atual} - {nome_prod_atual}"
                    idx_produto = lista_produtos.index(produto_str_atual) if produto_str_atual in lista_produtos else 0

                    lista_metodos = ["Pix", "Dinheiro", "Cartão", "Sweet Flex"]
                    idx_metodo = lista_metodos.index(metodo_atual) if metodo_atual in lista_metodos else 0

                    with st.form(f"form_edicao_{linha_real}"):
                        st.write("#### 🔄 Atualizar Dados", help="📝 COMO USAR:\nAltere apenas os campos que estavam errados na venda original.\n\n🎯 QUANDO USAR:\nPara corrigir erros de digitação rápidos (ex: selecionou a cliente errada, trocou o produto ou errou o valor).\n\n⚠️ AVISO IMPORTANTE:\nUse apenas para arrumar erros do dia a dia. Não use essa ferramenta para bagunçar vendas antigas, pois ela altera a planilha financeira oficial!")
                        e_c1, e_c2 = st.columns(2)
                        novo_cliente = e_c1.selectbox("Cliente Oficial", lista_clientes, index=idx_cliente)
                        novo_produto = e_c2.selectbox("Produto Correto", lista_produtos, index=idx_produto)
                        
                        e_c3, e_c4, e_c5 = st.columns(3)
                        nova_qtd = e_c3.number_input("Quantidade", value=int(qtd_atual) if qtd_atual.is_integer() else qtd_atual, min_value=1)
                        novo_val = e_c4.number_input("Preço Un. (R$)", value=float(val_atual))
                        novo_desc = e_c5.number_input("Desconto (R$)", value=float(desc_reais_atual))
                        
                        novo_metodo = st.selectbox("Forma de Pagto", lista_metodos, index=idx_metodo)
                        
                        if st.form_submit_button("💾 Salvar Correção", type="primary"):
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
                                
                                try: num_parc = int(linha_dados[16])
                                except: num_parc = 1
                                if num_parc <= 0: num_parc = 1
                                
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
                                aba_vendas.batch_update(atualizacoes, value_input_option='RAW')
                                
                                st.session_state['recibo_correcao'] = {
                                    "cliente": n_nome_cli,
                                    "produto": f"{nova_qtd}x {n_nome_prod}",
                                    "total": n_t_liq,
                                    "metodo": novo_metodo
                                }
                                
                                st.cache_resource.clear()
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"⚠️ Erro ao salvar: {e}")
        except Exception as e:
            st.info("Aguardando carregamento dos dados para edição.")

    # ==========================================
    # 🧾 AVISO DE CORREÇÃO BEM-SUCEDIDA
    # ==========================================
    if 'recibo_correcao' in st.session_state:
        st.success("✅ Venda atualizada na planilha com sucesso!")
        recibo = st.session_state['recibo_correcao']
        
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
            df_fin = df_vendas_hist.copy()
            
            # Mapeamento: Coluna L (11)=Total | M (12)=Lucro | O (14)=Pagto | U (20)=Saldo
            df_fin['VALOR_NUM'] = df_fin.iloc[:, 11].apply(limpar_v)
            df_fin['LUCRO_NUM'] = df_fin.iloc[:, 12].apply(limpar_v)
            df_fin['FORMA_PG'] = df_fin.iloc[:, 14]
            df_fin['SALDO_NUM'] = df_fin.iloc[:, 20].apply(limpar_v)
            
            vendas_brutas = df_fin['VALOR_NUM'].sum()
            lucro_bruto = df_fin['LUCRO_NUM'].sum()
            saldo_devedor = df_fin['SALDO_NUM'].sum()
            total_recebido = vendas_brutas - saldo_devedor
            
            # Cálculo de Liquidez (O que já é dinheiro vivo vs. o que é Flex)
            receita_imediata = df_fin[df_fin['FORMA_PG'] != 'Sweet Flex']['VALOR_NUM'].sum()
            indice_liquidez = (receita_imediata / vendas_brutas * 100) if vendas_brutas > 0 else 0
            
            # 2. MÉTRICAS PRINCIPAIS
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Vendas Totais", f"R$ {vendas_brutas:,.2f}")
            c2.metric("Lucro Bruto", f"R$ {lucro_bruto:,.2f}")
            c3.metric("Total Recebido", f"R$ {total_recebido:,.2f}", delta="Dinheiro em Caixa")
            c4.metric("Saldo Devedor", f"R$ {saldo_devedor:,.2f}", delta=f"{(saldo_devedor/vendas_brutas*100):.1f}% pendente", delta_color="inverse")

            # 3. TERMÔMETRO DE SAÚDE FINANCEIRA
            st.markdown("---")
            col_t1, col_t2 = st.columns([2, 1])
            with col_t1:
                if indice_liquidez >= 70:
                    st.success(f"🟢 **Saúde de Caixa: EXCELENTE** ({indice_liquidez:.1f}% recebido à vista)")
                elif indice_liquidez >= 40:
                    st.warning(f"🟡 **Saúde de Caixa: ATENÇÃO** ({indice_liquidez:.1f}% à vista)")
                else:
                    st.error(f"🔴 **Saúde de Caixa: CRÍTICA** (Apenas {indice_liquidez:.1f}% à vista)")
                st.progress(min(indice_liquidez/100, 1.0))
            
            with col_t2:
                st.metric("Recebíveis (Futuro)", f"R$ {saldo_devedor:,.2f}", help="Dinheiro que entrará via Sweet Flex.")

            # 4. DASHBOARD DE ANÁLISE (VERSÃO PREMIUM COM CORES DA MARCA)
            with st.expander("📊 Análise de Desempenho e Tendências", expanded=False):
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
                        st.cache_resource.clear(); st.rerun()
                    except Exception as e: st.error(f"Erro no FIFO: {e}")

        # --- 🕒 HISTÓRICO DE ABATIMENTOS (LÊ A ABA FINANCEIRO) ---
        st.markdown("---")
        st.write("#### 🕒 Últimos Abatimentos Registrados (Banco de Dados)")
        try:
            aba_f_hist = planilha_mestre.worksheet("FINANCEIRO")
            df_f_hist = pd.DataFrame(aba_f_hist.get_all_records())
            # Filtra apenas registros de entrada real (Abatimentos PAGO)
            abatimentos = df_f_hist[df_f_hist['STATUS'] == "PAGO"].tail(5).iloc[::-1]
            if not abatimentos.empty:
                st.dataframe(abatimentos[['DATA', 'CLIENTE', 'ENTRADA R$', 'OBS']], use_container_width=True, hide_index=True)
            else: st.info("Nenhum abatimento localizado na planilha.")
        except: st.info("O histórico aparecerá após o primeiro recebimento.")

    st.divider()

    st.markdown("### 🔍 Ficha de Cliente (Extrato Dinâmico)")
    opcoes_ficha = sorted([f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
    sel_ficha = st.selectbox("Selecione para ver o que ela deve:", ["---"] + opcoes_ficha, key="ficha_sel_cliente")
    
    if sel_ficha != "---":
        id_c = sel_ficha.split(" - ")[0]
        nome_c_ficha = " - ".join(sel_ficha.split(" - ")[1:])
        v_hist = df_vendas_hist[df_vendas_hist['CÓD. CLIENTE'].astype(str) == id_c]
        saldo_devedor_real = v_hist['SALDO DEVEDOR'].apply(limpar_v).sum()
        c_f1, c_f2 = st.columns(2)
        c_f1.metric("Saldo Devedor Atual", f"R$ {saldo_devedor_real:,.2f}")
        if saldo_devedor_real > 0.01:
            tel_c = banco_de_clientes.get(id_c, {}).get('fone', "")
            msg_zap = f"Olá {nome_c_ficha}! 🏠 Segue seu extrato na *Sweet Home Enxovais*. Atualmente consta um saldo pendente de *R$ {saldo_devedor_real:.2f}*. Qualquer dúvida estou à disposição! 😊"
            st.link_button("📲 Cobrar no WhatsApp", f"https://wa.me/55{tel_c}?text={urllib.parse.quote(msg_zap)}", use_container_width=True)
        else: st.success("✅ Esta cliente não possui débitos pendentes.")

        st.write("#### ⏳ Histórico de Vendas Localizado")
        if not v_hist.empty:
            st.dataframe(v_hist[['DATA DA VENDA', 'PRODUTO', 'TOTAL R$', 'SALDO DEVEDOR', 'STATUS']], use_container_width=True, hide_index=True)
        else: st.info("Nenhuma compra registrada para esta cliente ainda.")

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
                                st.success("Estoque Atualizado!"); st.cache_resource.clear(); st.rerun()

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
                                st.success(f"Lote {n_cod} criado!"); st.cache_resource.clear(); st.rerun()

                elif acao == "3. Correção":
                    with st.form("f_cor"):
                        real = st.number_input("Qtd real física", value=est_h)
                        if st.form_submit_button("Corrigir"):
                            with st.spinner("Sincronizando..."):
                                aba = planilha_mestre.worksheet("INVENTÁRIO")
                                aba.update_acell(f"C{lin_p}", real + vend_g)
                                planilha_mestre.worksheet("LOG_ESTOQUE").append_row([datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), "CORREÇÃO", nome_e, f"Ajustado para {real}", st.session_state.get('usuario_logado', 'Bia')], value_input_option='RAW')
                                st.success("Corrigido!"); st.cache_resource.clear(); st.rerun()

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
                    st.success("✅ Cadastrado!"); st.cache_resource.clear(); st.rerun()

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
        
        with t_falta:
            st.write("**Produtos no estoque aguardando foto para o site:**")
            if not df_full_inv.empty:
                prods_com_foto = []
                if not df_docs.empty and 'VINCULO' in df_docs.columns:
                    fotos = df_docs[df_docs['TIPO'] == "Foto de Produto"]
                    prods_com_foto = [str(p).split(" - ")[0].strip() for p in fotos['VINCULO'].dropna() if " - " in str(p)]
                
                df_falta = df_full_inv[~df_full_inv['CÓD. PRÓDUTO'].astype(str).str.strip().isin(prods_com_foto)]
                if not df_falta.empty:
                    st.dataframe(df_falta[['CÓD. PRÓDUTO', 'NOME DO PRODUTO', 'ESTOQUE ATUAL']], hide_index=True)
                else: 
                    st.success("🎉 Nenhuma pendência! O estoque inteiro tem foto.")

        with t_pronto:
            st.write("**Fotos tiradas! Coloque no site e marque como publicado:**")
            if not df_docs.empty and 'STATUS_ODOO' in df_docs.columns:
                prontos = df_docs[(df_docs['TIPO'] == "Foto de Produto") & (df_docs['STATUS_ODOO'] == "Pronto para Site")]
                if not prontos.empty:
                    for idx, r in prontos.iterrows():
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.write(f"📦 **{r['VINCULO']}**")
                        c2.link_button("🖼️ Ver Foto", r['LINK_DRIVE'], use_container_width=True)
                        if c3.button("✅ Publicado", key=f"btn_odoo_{idx}"):
                            aba_doc = planilha_mestre.worksheet("DOCUMENTOS")
                            cell = aba_doc.find(r['ID_ARQUIVO'])
                            aba_doc.update_cell(cell.row, 7, "Publicado no Odoo")
                            st.success("Atualizado!"); st.cache_resource.clear(); st.rerun()
                        st.divider()
                else: 
                    st.info("Sua fila de trabalho está limpa.")

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
                            st.success(f"✅ Arquivado com sucesso!"); st.cache_resource.clear(); st.rerun()
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

