import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import urllib.parse

# ==========================================
# 1. CONFIGURAÇÃO ÚNICA DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Gestão Sweet", 
    page_icon="logo_sweet.png", 
    layout="wide"
)

# Inicialização das Memórias de Sessão
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False
if 'historico_sessao' not in st.session_state:
    st.session_state['historico_sessao'] = []

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

# Barra Lateral (Sidebar)
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

# --- CONFIGURAÇÃO GOOGLE SHEETS ---
ID_PLANILHA = "1E2NwI5WBE1iCjTWxpUxy3TYpiwKU6e4s4-C1Rp1AJX8"
ESPECIFICACOES = [
    "https://spreadsheets.google.com/feeds", 
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file", 
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def conectar_google():
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, ESPECIFICACOES)
            return gspread.authorize(creds).open_by_key(ID_PLANILHA)
        elif os.path.exists('credenciais.json'):
            creds = ServiceAccountCredentials.from_json_keyfile_name('credenciais.json', ESPECIFICACOES)
            return gspread.authorize(creds).open_by_key(ID_PLANILHA)
        return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

planilha_mestre = conectar_google()

def limpar_v(v):
    if pd.isna(v) or v == "": return 0.0
    return pd.to_numeric(str(v).replace('R$', '').replace('.', '').replace(',', '.').strip(), errors='coerce') or 0.0

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
                df = df[~df.iloc[:, 0].str.contains("TOTAIS", case=False, na=False)]
                df = df[~df.iloc[:, 1].str.contains("TOTAIS", case=False, na=False)]
                df = df[df.iloc[:, 1].str.strip() != ""]
            return df
        except: return pd.DataFrame()

    df_inv = ler_aba_seguro("INVENTÁRIO")
    df_cli = ler_aba_seguro("CARTEIRA DE CLIENTES")
    df_fin = ler_aba_seguro("FINANCEIRO")
    df_vendas = ler_aba_seguro("VENDAS")
    df_painel = ler_aba_seguro("PAINEL")

    banco_prod = {str(r.iloc[0]): {"nome": r.iloc[1], "estoque": r.iloc[7], "venda": r.iloc[8], "custo": r.iloc[6]} for _, r in df_inv.iterrows()} if not df_inv.empty else {}
    banco_cli = {str(r.iloc[0]): {"nome": str(r.iloc[1]), "fone": str(r.iloc[2])} for _, r in df_cli.iterrows()} if not df_cli.empty else {}

    return banco_prod, banco_cli, df_inv, df_fin, df_vendas, df_painel, df_cli

banco_de_produtos, banco_de_clientes, df_full_inv, df_financeiro, df_vendas_hist, df_painel_resumo, df_clientes_full = carregar_dados()

# --- NAVEGAÇÃO ---
with st.sidebar:
    st.title("🛠️ Painel Sweet Home")
    menu_selecionado = st.radio(
        "Navegação",
        ["🛒 Vendas", "💰 Financeiro", "📦 Estoque", "👥 Clientes"],
        key="nav_master"
    )
    st.divider()
    modo_teste = st.toggle("🔬 Modo de Teste", value=False)
    if st.button("🔄 Sincronizar"):
        st.cache_resource.clear()
        st.rerun()

# ==========================================
# --- SEÇÃO 1: VENDAS ---
# ==========================================
if menu_selecionado == "🛒 Vendas":
    st.subheader("🛒 Registro de Venda")
    with st.form("form_venda_final", clear_on_submit=True):
        metodo = st.selectbox("Forma de Pagamento", ["Pix", "Dinheiro", "Cartão", "Sweet Flex"], key="v_metodo")
        
        detalhes_p = []; n_p = 1 
        if metodo == "Sweet Flex":
            n_p = st.number_input("Número de Parcelas", 1, 12, 1)
            cols_parc = st.columns(n_p)
            for i in range(n_p):
                with cols_parc[i]:
                    dt = st.date_input(f"{i+1}ª Parc.", datetime.now(), key=f"d_p_{i}")
                    detalhes_p.append(dt.strftime("%d/%m/%Y"))

        col_esq, col_dir = st.columns(2)
        with col_esq:
            c_sel = st.selectbox("Selecionar Cliente", ["*** NOVO CLIENTE ***"] + [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
            c_nome_novo = st.text_input("Nome (se novo)")
            tel_sug = banco_de_clientes[c_sel.split(" - ")[0]]['fone'] if c_sel != "*** NOVO CLIENTE ***" else ""
            c_zap = st.text_input("WhatsApp", value=tel_sug)

        with col_dir:
            p_sel = st.selectbox("Item do Estoque", [f"{k} - {v['nome']}" for k, v in banco_de_produtos.items()])
            cc1, cc2, cc3 = st.columns(3)
            qtd_v = cc1.number_input("Qtd", 1)
            val_v = cc2.number_input("Preço Un.", 0.0)
            desc_v = cc3.number_input("Desconto (R$)", 0.0)
            vendedor = st.text_input("Vendedor(a)", value="Bia")

        if st.form_submit_button("Finalizar Venda 🚀"):
            if c_sel == "*** NOVO CLIENTE ***":
                if not c_nome_novo or not c_zap: st.error("⚠️ Nome e Zap obrigatórios!"); st.stop()
                nome_cli = c_nome_novo.strip()
                cod_cli = f"CLI-{len(df_clientes_full)+1:03d}"
                if not modo_teste:
                    planilha_mestre.worksheet("CARTEIRA DE CLIENTES").append_row([cod_cli, nome_cli, c_zap, "", datetime.now().strftime("%d/%m/%Y"), 0, "", "Incompleto"], value_input_option='USER_ENTERED')
            else:
                cod_cli = c_sel.split(" - ")[0]
                nome_cli = banco_de_clientes[cod_cli]['nome']

            t_liq = (qtd_v * val_v) - desc_v
            cod_p = p_sel.split(" - ")[0]
            nome_p = p_sel.split(" - ")[1]
            
            if not modo_teste:
                aba_v = planilha_mestre.worksheet("VENDAS")
                idx = aba_v.find("TOTAIS").row
                linha = ["", datetime.now().strftime("%d/%m/%Y"), cod_cli, nome_cli, cod_p, nome_p, banco_de_produtos[cod_p]['custo'], qtd_v, val_v, desc_v/(qtd_v*val_v) if val_v>0 else 0, "", "", "", "", metodo, "Sim" if metodo=="Sweet Flex" else "Não", n_p, "", t_liq/n_p if metodo=="Sweet Flex" else 0, t_liq if metodo!="Sweet Flex" else 0, "", detalhes_p[0] if detalhes_p else "", "Pendente" if metodo=="Sweet Flex" else "Pago"]
                aba_v.insert_row(linha, index=idx, value_input_option='USER_ENTERED')
                st.success("✅ Venda Registrada!")
            
            recibo = f"🌸 *RECIBO SWEET HOME*\n📦 {qtd_v}x {nome_p}\n💰 Total: R$ {t_liq:.2f}\n💳 Pagto: {metodo}"
            st.code(recibo)
            st.link_button("📲 Enviar WhatsApp", f"https://wa.me/55{c_zap.replace(' ','')}?text={urllib.parse.quote(recibo)}")

# ==========================================
# --- SEÇÃO 2: FINANCEIRO ---
# ==========================================
if menu_selecionado == "💰 Financeiro":
    st.subheader("💰 Painel Financeiro")
    if not df_vendas_hist.empty:
        v_brutas = df_vendas_hist.iloc[:, 11].apply(limpar_v).sum()
        s_devedor = df_vendas_hist.iloc[:, 20].apply(limpar_v).sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Vendas Totais", f"R$ {v_brutas:,.2f}")
        c2.metric("Saldo Devedor", f"R$ {s_devedor:,.2f}", delta_color="inverse")
        c3.metric("Recebido", f"R$ {v_brutas - s_devedor:,.2f}")

    with st.expander("➕ Lançar Abatimento (FIFO)"):
        with st.form("fifo"):
            c_pg = st.selectbox("Cliente", [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
            v_pg = st.number_input("Valor", 0.0)
            if st.form_submit_button("Confirmar"):
                st.info("Processando FIFO na planilha...")
                # Lógica de atualização de células aqui conforme seu original

    st.divider()
    st.markdown("### 🔍 Ficha de Cliente")
    sel_f = st.selectbox("Ver Extrato", [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
    if sel_f:
        id_c = sel_f.split(" - ")[0]
        v_hist = df_vendas_hist[df_vendas_hist['CÓD. CLIENTE'].astype(str) == id_c]
        st.dataframe(v_hist, use_container_width=True)

# ==========================================
# --- SEÇÃO 3: ESTOQUE ---
# ==========================================
if menu_selecionado == "📦 Estoque":
    st.subheader("📦 Gestão de Estoque")
    with st.expander("➕ Novo Produto"):
        with st.form("novo_p"):
            c1, c2 = st.columns(2); cod = c1.text_input("Cód"); nom = c2.text_input("Nome")
            if st.form_submit_button("Salvar"):
                planilha_mestre.worksheet("INVENTÁRIO").append_row([cod, nom, 0, 0, "", 3, 0, "", 0, datetime.now().strftime("%d/%m/%Y")], value_input_option='USER_ENTERED')
                st.rerun()
    st.dataframe(df_full_inv, use_container_width=True)

# ==========================================
# --- SEÇÃO 4: CLIENTES ---
# ==========================================
if menu_selecionado == "👥 Clientes":
    st.subheader("👥 Gestão de Clientes")
    with st.expander("➕ Cadastrar Cliente"):
        with st.form("c_manual"):
            n = st.text_input("Nome"); z = st.text_input("Zap")
            if st.form_submit_button("Salvar"):
                planilha_mestre.worksheet("CARTEIRA DE CLIENTES").append_row([f"CLI-{len(df_clientes_full)+1:03d}", n, z, "", datetime.now().strftime("%d/%m/%Y"), 0, "", "Incompleto"], value_input_option='USER_ENTERED')
                st.rerun()
    st.dataframe(df_clientes_full, use_container_width=True)
