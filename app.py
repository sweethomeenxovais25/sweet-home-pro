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

    st.title("🛠️ Painel Sweet Home")
    menu_selecionado = st.radio(
        "Navegação",
        ["🛒 Vendas", "💰 Financeiro", "📦 Estoque", "👥 Clientes"],
        key="navegacao_principal_sweet"
    )
    
    st.divider()
    modo_teste = st.toggle("🔬 Modo de Teste", value=False, key="toggle_teste")
    
    if st.button("🔄 Sincronizar Planilha", key="btn_sincronizar"):
        st.cache_resource.clear()
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

# ==========================================
# 4. LÓGICA DE DISTRIBUIÇÃO DAS TELAS
# ==========================================

if menu_selecionado == "🛒 Vendas":
    st.subheader("🛒 Registro de Venda")
    with st.form("form_venda_final", clear_on_submit=True):
        metodo = st.selectbox("Forma de Pagamento", ["Pix", "Dinheiro", "Cartão", "Sweet Flex"], key="venda_metodo_pg")
        
        detalhes_p = []; n_p = 1 
        if metodo == "Sweet Flex":
            n_p = st.number_input("Número de Parcelas", 1, 12, 1, key="venda_n_parcelas")
            cols_parc = st.columns(n_p)
            for i in range(n_p):
                with cols_parc[i]:
                    dt = st.date_input(f"{i+1}ª Parc.", datetime.now(), key=f"vd_data_parc_{i}")
                    detalhes_p.append(dt.strftime("%d/%m/%Y"))

        col_esq, col_dir = st.columns(2)
        with col_esq:
            st.write("👤 **Dados da Cliente**")
            c_sel = st.selectbox("Selecionar Cliente", ["*** NOVO CLIENTE ***"] + [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()], key="venda_cliente_sel")
            telefone_sugerido = banco_de_clientes[c_sel.split(" - ")[0]].get('fone', "") if c_sel != "*** NOVO CLIENTE ***" else ""
            c_nome_novo = st.text_input("Nome Completo (se novo)", key="venda_nome_novo")
            c_zap = st.text_input("WhatsApp", value=telefone_sugerido, key=f"zap_venda_{c_sel}")

        with col_dir:
            st.write("📦 **Produto**")
            p_sel = st.selectbox("Item do Estoque", [f"{k} - {v['nome']}" for k, v in banco_de_produtos.items()], key="venda_produto_sel")
            cc1, cc2, cc3 = st.columns(3)
            qtd_v = cc1.number_input("Qtd", 1, key="venda_qtd_input")
            val_v = cc2.number_input("Preço Un.", 0.0, key="venda_val_input")
            desc_v = cc3.number_input("Desconto (R$)", 0.0, key="venda_desc_input")
            vendedor = st.text_input("Vendedor(a)", value="Bia", key="venda_vendedor_input")

        enviar = st.form_submit_button("Finalizar Venda 🚀")

        if enviar:
            if c_sel == "*** NOVO CLIENTE ***":
                if not c_nome_novo or not c_zap: st.error("⚠️ Preencha Nome e Zap!"); st.stop()
                nome_cli = c_nome_novo.strip()
                if not modo_teste:
                    try:
                        aba_cli = planilha_mestre.worksheet("CARTEIRA DE CLIENTES")
                        cod_cli = f"CLI-{len(aba_cli.get_all_values()):03d}"
                        aba_cli.append_row([cod_cli, nome_cli, c_zap.strip(), "", datetime.now().strftime("%d/%m/%Y"), 0, "", "Incompleto"], value_input_option='USER_ENTERED')
                    except Exception as e: st.error(f"Erro: {e}"); st.stop()
                else: cod_cli = "CLI-TESTE"
            else:
                cod_cli = c_sel.split(" - ")[0]
                nome_cli = banco_de_clientes[cod_cli]['nome']

            v_bruto = qtd_v * val_v
            t_liq = v_bruto - desc_v
            cod_p = p_sel.split(" - ")[0]
            nome_p = p_sel.split(" - ")[1].strip()
            custo_un = banco_de_produtos[cod_p].get('custo', 0) if cod_p in banco_de_produtos else 0
            
            st.session_state['historico_sessao'].insert(0, {"Data": datetime.now().strftime("%d/%m/%Y"), "Cliente": nome_cli, "Produto": nome_p, "Total": f"R$ {t_liq:.2f}"})

            if not modo_teste:
                try:
                    aba_v = planilha_mestre.worksheet("VENDAS")
                    idx_ins = aba_v.find("TOTAIS").row 
                    eh_parc = "Sim" if metodo == "Sweet Flex" else "Não"
                    linha = ["", datetime.now().strftime("%d/%m/%Y"), cod_cli, nome_cli, cod_p, nome_p, custo_un, qtd_v, val_v, (desc_v/v_bruto if v_bruto>0 else 0), "", "", "", "", metodo, eh_parc, n_p, "", t_liq/n_p if eh_parc=="Sim" else 0, t_liq if eh_parc=="Não" else 0, t_liq if eh_parc=="Sim" else 0, detalhes_p[0] if (eh_parc=="Sim" and detalhes_p) else "", "Pendente" if eh_parc=="Sim" else "Pago"]
                    aba_v.insert_row(linha, index=idx_ins, value_input_option='USER_ENTERED')
                    st.success("✅ Venda registrada!")
                    st.cache_resource.clear()
                except Exception as e: st.error(f"Erro: {e}")

            recibo = f"🌸 *RECIBO SWEET HOME*\n💰 *Total:* R$ {t_liq:.2f}\n💳 *Pagto:* {metodo}"
            st.code(recibo)
            zap_limpo = c_zap.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            st.link_button("📲 Enviar WhatsApp", f"https://wa.me/55{zap_limpo}?text={urllib.parse.quote(recibo)}", type="primary")

    st.subheader("📝 Histórico")
    st.dataframe(st.session_state['historico_sessao'], use_container_width=True)

elif menu_selecionado == "💰 Financeiro":
    st.subheader("💰 Financeiro")
    if not df_vendas_hist.empty:
        vendas_brutas = df_vendas_hist.iloc[:, 19].apply(limpar_v).sum()
        saldo_devedor = df_vendas_hist.iloc[:, 20].apply(limpar_v).sum()
        c1, c2 = st.columns(2)
        c1.metric("Vendas Totais", f"R$ {vendas_brutas:,.2f}")
        c2.metric("A Receber", f"R$ {saldo_devedor:,.2f}", delta_color="inverse")

    with st.expander("➕ Abatimento FIFO"):
        with st.form("f_fifo"):
            c_pg = st.selectbox("Cliente", [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
            v_pg = st.number_input("Valor", 0.0)
            if st.form_submit_button("Confirmar"):
                st.info("Processando FIFO...") # Adicionar lógica de update aqui

elif menu_selecionado == "📦 Estoque":
    st.subheader("📦 Estoque")
    st.dataframe(df_full_inv, use_container_width=True)

elif menu_selecionado == "👥 Clientes":
    st.subheader("👥 Clientes")
    st.dataframe(df_clientes_full, use_container_width=True)
