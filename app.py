import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import urllib.parse

# ==========================================
# 1. CONFIGURAÇÕES E MEMÓRIA
# ==========================================
st.set_page_config(page_title="Sweet Home Pro", page_icon="🏠", layout="wide")

if 'historico_sessao' not in st.session_state:
    st.session_state['historico_sessao'] = []

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

# ==========================================
# 2. CARREGAMENTO DE DADOS (7 ITENS)
# ==========================================
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
            return df[df.iloc[:, 0].str.strip() != ""]
        except: return pd.DataFrame()

    df_inv = ler_aba_seguro("INVENTÁRIO")
    df_cli = ler_aba_seguro("CARTEIRA DE CLIENTES")
    df_fin = ler_aba_seguro("FINANCEIRO")
    df_vendas = ler_aba_seguro("VENDAS")
    df_painel = ler_aba_seguro("PAINEL")

    # Bancos de dados para Selectbox
    banco_prod = {str(r.iloc[0]): {"nome": r.iloc[1], "estoque": r.iloc[2], "venda": r.iloc[8]} for _, r in df_inv.iterrows()} if not df_inv.empty else {}
    banco_cli = {str(r.iloc[0]): {"nome": str(r.iloc[1]), "fone": str(r.iloc[2])} for _, r in df_cli.iterrows()} if not df_cli.empty else {}

    return banco_prod, banco_cli, df_inv, df_fin, df_vendas, df_painel, df_cli

# RECEBIMENTO DOS DADOS
banco_de_produtos, banco_de_clientes, df_full_inv, df_financeiro, df_vendas_hist, df_painel_resumo, df_clientes_full = carregar_dados()

# ==========================================
# 3. BARRA LATERAL (SIDEBAR)
# ==========================================
st.sidebar.title("🛠️ Painel Sweet Home")
modo_teste = st.sidebar.toggle("🔬 Modo de Teste (Simulação)", value=False)
if modo_teste: st.sidebar.warning("⚠️ MODO TESTE ATIVO")

if st.sidebar.button("🔄 Sincronizar Planilha"):
    st.cache_resource.clear()
    st.rerun()

# ==========================================
# 4. CRIAÇÃO DAS ABAS (DEFINIÇÃO DAS VARIÁVEIS)
# ==========================================
aba_venda, aba_financeiro, aba_estoque, aba_clientes = st.tabs(["🛒 Vendas", "💰 Financeiro", "📦 Estoque", "👥 Clientes"])

# ==========================================
# --- ABA 1: VENDAS (MOTOR REVISADO) ---
# ==========================================
with aba_venda:
    st.subheader("🛒 Registro de Venda")
    metodo = st.selectbox("Forma de Pagamento", ["Pix", "Dinheiro", "Cartão", "Sweet Flex"])
    
    detalhes_p = []
    n_p = 1 
    if metodo == "Sweet Flex":
        st.info("📅 Planejamento de Parcelas")
        n_p = st.number_input("Número de Parcelas", 1, 12, 1)
        cols_p = st.columns(n_p)
        for i in range(n_p):
            with cols_p[i]:
                dt = st.date_input(f"{i+1}ª Parc.", datetime.now(), key=f"vd_{i}")
                detalhes_p.append(dt.strftime("%d/%m/%Y"))

    with st.form("form_pdv_final", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            st.write("👤 **Dados da Cliente**")
            c_sel = st.selectbox("Selecionar Cliente", ["*** NOVO CLIENTE ***"] + [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
            c_nome_novo = st.text_input("Nome Completo (se novo)")
            c_zap = st.text_input("WhatsApp (DDD + Número)")
        with c2:
            st.write("📦 **Produto**")
            p_sel = st.selectbox("Item do Estoque", [f"{k} - {v['nome']}" for k, v in banco_de_produtos.items()])
            cc1, cc2, cc3 = st.columns(3)
            qtd_v = cc1.number_input("Qtd", 1, 100, 1)
            val_v = cc2.number_input("Preço Un.", 0.0)
            desc_v = cc3.number_input("Desconto (R$)", 0.0)
            vendedor = st.text_input("Vendedor(a)", value="Bia")

        if st.form_submit_button("Finalizar Venda 🚀"):
            # --- PONTE DE CADASTRO ---
            if c_sel == "*** NOVO CLIENTE ***":
                if not c_nome_novo or not c_zap:
                    st.error("⚠️ Para novos clientes, Nome e WhatsApp são obrigatórios!"); st.stop()
                nome_cli = c_nome_novo.strip()
                if not modo_teste:
                    try:
                        aba_cli_sheet = planilha_mestre.worksheet("CARTEIRA DE CLIENTES")
                        dados_atuais = aba_cli_sheet.get_all_values()
                        nomes_upper = [l[1].strip().upper() for l in dados_atuais[1:]]
                        if nome_cli.upper() in nomes_upper:
                            idx = nomes_upper.index(nome_cli.upper())
                            cod_cli = dados_atuais[idx+1][0]
                        else:
                            prox_c = len(dados_atuais); cod_cli = f"CLI-{prox_c:03d}"
                            aba_cli_sheet.append_row([cod_cli, nome_cli, c_zap.strip(), "", datetime.now().strftime("%d/%m/%Y"), 0, "", "Incompleto"], value_input_option='USER_ENTERED')
                            st.toast(f"👤 {nome_cli} cadastrada!")
                    except Exception as e: st.error(f"Erro Cadastro: {e}"); st.stop()
                else: cod_cli = "CLI-TESTE"
            else:
                cod_cli = c_sel.split(" - ")[0]
                nome_cli = banco_de_clientes[cod_cli]['nome']

            # --- PROCESSAMENTO E GRAVAÇÃO (EMPURA TOTAIS) ---
            valor_bruto = qtd_v * val_v
            t_liq = valor_bruto - desc_v
            desc_decimal = desc_v / valor_bruto if valor_bruto > 0 else 0
            
            if not modo_teste:
                try:
                    aba_v = planilha_mestre.worksheet("VENDAS")
                    try:
                        idx_ins = aba_v.find("TOTAIS").row
                    except:
                        idx_ins = len(aba_v.col_values(2)) + 1
                    
                    # Lógica Financeira Original
                    eh_parc = "Sim" if metodo == "Sweet Flex" else "Não"
                    l_venda = ["", datetime.now().strftime("%d/%m/%Y"), cod_cli, nome_cli, p_sel.split(" - ")[0], p_sel.split(" - ")[1].strip(), "", qtd_v, val_v, desc_decimal, "", t_liq, "", "", metodo, eh_parc, n_p, t_liq if eh_parc == "Não" else 0, t_liq/n_p if eh_parc == "Sim" else 0, t_liq if eh_parc == "Não" else 0, t_liq if eh_parc == "Sim" else 0, detalhes_p[0] if (eh_parc == "Sim" and detalhes_p) else "", "Pendente" if eh_parc == "Sim" else "Pago", '=SE(OU(INDIRETO("W"&LIN())="Pago"; INDIRETO("W"&LIN())="Em dia"); 0; MÁXIMO(0; HOJE() - INDIRETO("V"&LIN())))']
                    aba_v.insert_row(l_venda, index=idx_ins, value_input_option='USER_ENTERED')
                    st.cache_resource.clear()
                    st.success("✅ Venda Processada!")
                except Exception as e: st.error(f"Erro: {e}")

            # LOG E RECIBO
            st.session_state['historico_sessao'].insert(0, {"Data": datetime.now().strftime("%d/%m/%Y"), "Cliente": nome_cli, "Produto": p_sel.split(" - ")[1], "Total": f"R$ {t_liq:.2f}"})
            recibo = f"*RECIBO SWEET HOME*\nCliente: {nome_cli}\nTotal: R$ {t_liq:.2f}"
            st.link_button("📲 WhatsApp", f"https://wa.me/55{c_zap}?text={urllib.parse.quote(recibo)}", use_container_width=True)

# ==========================================
# --- ABA 2: FINANCEIRO (REVISADO) ---
# ==========================================
with aba_financeiro:
    def limpar_v(v):
        if pd.isna(v) or v == "": return 0.0
        return pd.to_numeric(str(v).replace('R$', '').replace('.', '').replace(',', '.').strip(), errors='coerce') or 0.0

    st.markdown("### 📈 Resumo Geral")
    if not df_vendas_hist.empty:
        try:
            divida = df_vendas_hist['SALDO DEVEDOR'].apply(limpar_v).sum()
            pago = df_financeiro['VALOR_PAGO'].apply(limpar_v).sum() if not df_financeiro.empty else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Dívida", f"R$ {divida:,.2f}"); c2.metric("Pago", f"R$ {pago:,.2f}"); c3.metric("Rua", f"R$ {divida-pago:,.2f}")
        except: st.info("Calculando...")

    st.divider()
    st.markdown("### 🔍 Ficha da Cliente")
    if not df_vendas_hist.empty:
        opcoes = sorted([f"{c} - {banco_de_clientes.get(str(c), {}).get('nome', '???')}" for c in df_vendas_hist['CÓD. CLIENTE'].unique() if str(c).strip()])
        sel = st.selectbox("Escolha a cliente:", ["---"] + opcoes)
        if sel != "---":
            id_c = sel.split(" - ")[0]
            st.dataframe(df_vendas_hist[df_vendas_hist['CÓD. CLIENTE'].astype(str) == id_c][['DATA DA VENDA', 'PRODUTO', 'TOTAL R$', 'STATUS']], hide_index=True)

# ==========================================
# --- ABA 3: ESTOQUE (BUSCA POR CÓDIGO) ---
# ==========================================
with aba_estoque:
    st.subheader("📦 Estoque")
    busca = st.text_input("🔍 Localize pelo NOME, CÓDIGO ou DATA...")
    df_est = df_full_inv.copy()
    if busca and not df_est.empty:
        df_est = df_est[df_est.apply(lambda r: busca.lower() in str(r).lower(), axis=1)]
    st.dataframe(df_est, use_container_width=True, hide_index=True)

# ==========================================
# --- ABA 4: CLIENTES (RADAR + CARTEIRA TOTAL) ---
# ==========================================
with aba_clientes:
    st.subheader("👥 Clientes")
    if not df_clientes_full.empty:
        # RADAR
        try:
            inc = df_clientes_full[df_clientes_full.iloc[:, 7].str.strip() == "Incompleto"]
            if not inc.empty: st.warning(f"🚨 {len(inc)} cadastros incompletos!"); st.dataframe(inc, hide_index=True)
            else: st.success("✨ Tudo completo!")
        except: pass
        
        st.divider()
        st.markdown("### 🗂️ Carteira Total") # AQUI VOCÊ VÊ TODOS OS CLIENTES
        st.dataframe(df_clientes_full, use_container_width=True, hide_index=True)
