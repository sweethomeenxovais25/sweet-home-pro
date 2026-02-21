import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import urllib.parse
import streamlit as st
# ... (seus outros imports como pandas, gspread, datetime, etc) ...

# ==========================================
# 🔒 FASE 1: TELA DE LOGIN & SEGURANÇA
# ==========================================

# 1. Cria a "memória" para saber se a Bia já fez o login
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

# 2. Se ela NÃO estiver autenticada, mostra a tela de login e TRAVA o resto
if not st.session_state['autenticado']:
    st.markdown("<h2 style='text-align: center;'>🔒 Acesso Restrito - Sweet Home</h2>", unsafe_allow_html=True)
    
    # Criando colunas só para o formulário ficar centralizado e bonito
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("form_login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password") # Esconde a senha com asteriscos
            submit = st.form_submit_button("Entrar no Sistema", use_container_width=True)
            
            if submit:
                # 1. Puxa a lista de usuários do cofre
                usuarios_permitidos = st.secrets["usuarios"]
                
                # 2. Verifica se o usuário digitado existe no cofre
                if usuario in usuarios_permitidos:
                    # 3. Verifica se a senha bate com a do cofre
                    if usuarios_permitidos[usuario] == senha:
                        st.session_state['autenticado'] = True
                        st.session_state['usuario_logado'] = usuario # Guarda quem logou
                        st.rerun()
                    else:
                        st.error("❌ Senha incorreta.")
                else:
                    st.error("❌ Usuário não encontrado.")
    
    # 🛑 O COMANDO MÁGICO: st.stop() mata o código aqui se não logar. 
    st.stop()

# ==========================================
# 🚀 SEU APLICATIVO COMEÇA REALMENTE AQUI
# ==========================================

# 🚪 O Botão de Sair (Colocado na barra lateral para quem já entrou)
with st.sidebar:
    st.divider()
    if st.button("Sair do Sistema 🚪", use_container_width=True):
        st.session_state['autenticado'] = False
        st.rerun()

# (Aqui embaixo continua o resto do seu código original: Título, carregar dados, etc...)

# ==========================================
# 1. INICIALIZAÇÃO E MEMÓRIA
# ==========================================
st.set_page_config(page_title="Sweet Home Pro", page_icon="🏠", layout="wide")

# Registros Recentes (A memória da sessão que você pediu)
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

# --- AUXILIARES TÉCNICOS ---
def limpar_v(v):
    if pd.isna(v) or v == "": return 0.0
    return pd.to_numeric(str(v).replace('R$', '').replace('.', '').replace(',', '.').strip(), errors='coerce') or 0.0

# ==========================================
# 2. MOTOR DE DADOS REFINADO (7 ITENS)
# ==========================================
@st.cache_resource(ttl=600)
@st.cache_resource(ttl=600)
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
            
            # --- 🛡️ FILTRO TÉCNICO: REMOVE LINHAS DE RESUMO ---
            if not df.empty:
                # Remove linhas onde a palavra "TOTAIS" aparece nas colunas A ou B
                # Usamos case=False para pegar "Totais", "TOTAIS" ou "totais"
                df = df[~df.iloc[:, 0].str.contains("TOTAIS", case=False, na=False)]
                df = df[~df.iloc[:, 1].str.contains("TOTAIS", case=False, na=False)]
                # Limpeza extra de linhas totalmente vazias
                df = df[df.iloc[:, 1].str.strip() != ""]
            
            return df
        except: return pd.DataFrame()

    df_inv = ler_aba_seguro("INVENTÁRIO")
    df_cli = ler_aba_seguro("CARTEIRA DE CLIENTES")
    df_fin = ler_aba_seguro("FINANCEIRO")
    df_vendas = ler_aba_seguro("VENDAS")
    df_painel = ler_aba_seguro("PAINEL")

    # Mapeamento para os seletores (mantendo a integridade)
    banco_prod = {str(r.iloc[0]): {"nome": r.iloc[1], "estoque": r.iloc[7], "venda": r.iloc[8]} for _, r in df_inv.iterrows()} if not df_inv.empty else {}
    banco_cli = {str(r.iloc[0]): {"nome": str(r.iloc[1]), "fone": str(r.iloc[2])} for _, r in df_cli.iterrows()} if not df_cli.empty else {}

    return banco_prod, banco_cli, df_inv, df_fin, df_vendas, df_painel, df_cli

banco_de_produtos, banco_de_clientes, df_full_inv, df_financeiro, df_vendas_hist, df_painel_resumo, df_clientes_full = carregar_dados()

# ==========================================
# 3. INTERFACE E BARRA LATERAL
# ==========================================
st.sidebar.title("🛠️ Painel Sweet Home")
modo_teste = st.sidebar.toggle("🔬 Modo de Teste", value=False)
if st.sidebar.button("🔄 Sincronizar Planilha"):
    st.cache_resource.clear()
    st.rerun()

# Criação das abas (Variáveis definidas antes de usar)
aba_venda, aba_financeiro, aba_estoque, aba_clientes = st.tabs(["🛒 Vendas", "💰 Financeiro", "📦 Estoque", "👥 Clientes"])

# ==========================================
# --- ABA 1: VENDAS (SISTEMA INTEGRAL) ---
# ==========================================
with aba_venda:
    st.subheader("🛒 Registro de Venda")
    metodo = st.selectbox("Forma de Pagamento", ["Pix", "Dinheiro", "Cartão", "Sweet Flex"])
    
    detalhes_p = []; n_p = 1 
    if metodo == "Sweet Flex":
        n_p = st.number_input("Número de Parcelas", 1, 12, 1)
        cols = st.columns(n_p)
        for i in range(n_p):
            with cols[i]:
                dt = st.date_input(f"{i+1}ª Parc.", datetime.now(), key=f"vd_{i}")
                detalhes_p.append(dt.strftime("%d/%m/%Y"))

    with st.form("form_venda_final", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            st.write("👤 **Dados da Cliente**")
            c_sel = st.selectbox("Selecionar Cliente", ["*** NOVO CLIENTE ***"] + [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
            c_nome_novo = st.text_input("Nome Completo (se novo)"); c_zap = st.text_input("WhatsApp")
        with c2:
            st.write("📦 **Produto**")
            p_sel = st.selectbox("Item do Estoque", [f"{k} - {v['nome']}" for k, v in banco_de_produtos.items()])
            cc1, cc2, cc3 = st.columns(3)
            qtd_v = cc1.number_input("Qtd", 1); val_v = cc2.number_input("Preço Un.", 0.0); desc_v = cc3.number_input("Desconto (R$)", 0.0)
            vendedor = st.text_input("Vendedor(a)", value="Bia")

        if st.form_submit_button("Finalizar Venda 🚀"):
            # --- PONTE DE CADASTRO AUTOMÁTICO ---
            if c_sel == "*** NOVO CLIENTE ***":
                if not c_nome_novo or not c_zap: st.error("⚠️ Preencha Nome e Zap!"); st.stop()
                nome_cli = c_nome_novo.strip()
                if not modo_teste:
                    try:
                        aba_cli = planilha_mestre.worksheet("CARTEIRA DE CLIENTES")
                        dados_c = aba_cli.get_all_values()
                        nomes_up = [l[1].strip().upper() for l in dados_c[1:]]
                        if nome_cli.upper() in nomes_up:
                            cod_cli = dados_c[nomes_up.index(nome_cli.upper())+1][0]
                        else:
                            cod_cli = f"CLI-{len(dados_c):03d}"
                            aba_cli.append_row([cod_cli, nome_cli, c_zap.strip(), "", datetime.now().strftime("%d/%m/%Y"), 0, "", "Incompleto"], value_input_option='USER_ENTERED')
                            st.toast(f"👤 {nome_cli} cadastrada!")
                    except Exception as e: st.error(f"Erro: {e}"); st.stop()
            else:
                cod_cli = c_sel.split(" - ")[0]; nome_cli = banco_de_clientes[cod_cli]['nome']

            # --- PROCESSAMENTO (DESCONTO DECIMAL + TOTAIS) ---
            v_bruto = qtd_v * val_v
            t_liq = v_bruto - desc_v
            desc_percentual = desc_v / v_bruto if v_bruto > 0 else 0
            
            # BUSCANDO O CUSTO (Para a fórmula de Lucro do Sheets funcionar)
            cod_p = p_sel.split(" - ")[0]
            # Usa o custo se existir no banco, senão manda 0
            custo_un = banco_de_produtos[cod_p].get('custo', 0) if cod_p in banco_de_produtos else 0
            
            if not modo_teste:
                try:
                    aba_v = planilha_mestre.worksheet("VENDAS")
                    idx_ins = aba_v.find("TOTAIS").row # BUSCA DINÂMICA DO RODAPÉ
                    eh_parc = "Sim" if metodo == "Sweet Flex" else "Não"
                    f_atraso = '=SE(OU(INDIRETO("W"&LIN())="Pago"; INDIRETO("W"&LIN())="Em dia"); 0; MÁXIMO(0; HOJE() - INDIRETO("V"&LIN())))'
                    
                    linha = [
                        "",                                          # A: Vazio
                        datetime.now().strftime("%d/%m/%Y"),         # B: Data
                        cod_cli,                                     # C: Cód Cliente
                        nome_cli,                                    # D: Nome Cliente
                        cod_p,                                       # E: Cód Prod
                        p_sel.split(" - ")[1].strip(),               # F: Nome Prod
                        custo_un,                                    # G: CUSTO UNITÁRIO (Adicionado!)
                        qtd_v,                                       # H: Qtd
                        val_v,                                       # I: Preço Un
                        desc_percentual,                             # J: Desc %
                        "",                                          # K: Valor com Desc (FÓRMULA)
                        "",                                          # L: TOTAL (FÓRMULA)
                        "",                                          # M: LUCRO (FÓRMULA)
                        "",                                          # N: MARGEM (FÓRMULA)
                        metodo,                                      # O: Forma Pagto
                        eh_parc,                                     # P: Parcelado? (Sim/Não)
                        n_p,                                         # Q: Nº Parcelas
                        "",                                          # R: PAG À VISTA (FÓRMULA)
                        t_liq/n_p if eh_parc == "Sim" else 0,        # S: Valor da Parcela
                        t_liq if eh_parc == "Não" else 0,            # T: Valor Pago
                        "",                                          # U: SALDO DEVEDOR (FÓRMULA)
                        detalhes_p[0] if (eh_parc == "Sim" and detalhes_p) else "", # V: Vencimento 1
                        "Pendente" if eh_parc == "Sim" else "Pago",  # W: Status
                        f_atraso                                     # X: Fórmula Atraso
                    ]
                    
                    aba_v.insert_row(linha, index=idx_ins, value_input_option='USER_ENTERED')
                    st.cache_resource.clear()
                except Exception as e: 
                    st.error(f"Erro ao registrar: {e}")

            # --- REGISTROS RECENTES (MEMÓRIA DA SESSÃO) ---
            st.session_state['historico_sessao'].insert(0, {
                "Data": datetime.now().strftime("%d/%m/%Y"),
                "Hora": datetime.now().strftime("%H:%M:%S"),
                "Cliente": nome_cli, "Produto": p_sel.split(" - ")[1], "Total": f"R$ {t_liq:.2f}"
            })
            
            # --- RECIBO COMPLETO ---
            recibo = f"*RECIBO SWEET HOME*\nCliente: {nome_cli}\nData: {datetime.now().strftime('%d/%m/%Y')}\nVendedor(a): {vendedor}\nItem: {qtd_v}x {p_sel.split(' - ')[1]}\nTotal: R$ {t_liq:.2f}"
            if metodo == "Sweet Flex":
                recibo += "\n\n*Parcelas:*"
                for d_p in detalhes_p: recibo += f"\n{d_p} --- R$ {t_liq/n_p:.2f}"
            st.link_button("📲 Enviar WhatsApp", f"https://wa.me/55{c_zap}?text={urllib.parse.quote(recibo)}", use_container_width=True)

    # --- SEÇÃO REGISTROS RECENTES VISÍVEL ---
    st.divider()
    st.subheader("📝 Registros Realizados Agora")
    if st.session_state['historico_sessao']:
        st.dataframe(st.session_state['historico_sessao'], use_container_width=True, hide_index=True)
        if st.button("Limpar Histórico Local 🗑️"):
            st.session_state['historico_sessao'] = []; st.rerun()
    else: st.info("Aguardando vendas...")

# ==========================================
# --- ABA 2: FINANCEIRO (RESUMO + FIFO + COBRANÇA) ---
# ==========================================
with aba_financeiro:
    st.markdown("### 📈 Resumo Geral Sweet Home")
    
    if not df_vendas_hist.empty:
        try:
            # L=11, M=12, U=20
            vendas_brutas = df_vendas_hist.iloc[:, 11].apply(limpar_v).sum()
            lucro_bruto = df_vendas_hist.iloc[:, 12].apply(limpar_v).sum()
            saldo_devedor = df_vendas_hist.iloc[:, 20].apply(limpar_v).sum()
            total_recebido = vendas_brutas - saldo_devedor

            # --- LÓGICA DE RISCO (O Termômetro) ---
            percentual_pendente = (saldo_devedor / vendas_brutas) * 100 if vendas_brutas > 0 else 0
            
            if percentual_pendente <= 20:
                status_cor = "green"
                status_texto = "✨ Saúde Financeira: EXCELENTE"
            elif percentual_pendente <= 40:
                status_cor = "orange"
                status_texto = "⚠️ Saúde Financeira: ATENÇÃO (Cobrar mais)"
            else:
                status_cor = "red"
                status_texto = "🚨 Saúde Financeira: CRÍTICA (Risco de Caixa)"

            # --- EXIBIÇÃO DAS MÉTRICAS ---
            c1, c2, c3, c4 = st.columns(4)
            
            c1.metric("Vendas Totais", f"R$ {vendas_brutas:,.2f}")
            c2.metric("Lucro Bruto", f"R$ {lucro_bruto:,.2f}", delta="Margem Real")
            c3.metric("Total Recebido", f"R$ {total_recebido:,.2f}", delta="Dinheiro no Bolso")
            
            # Delta inverse: Se subir fica vermelho, se descer fica verde
            c4.metric("Saldo Devedor", f"R$ {saldo_devedor:,.2f}", 
                      delta=f"{percentual_pendente:.1f}% do total", 
                      delta_color="inverse")

            # Barra de Status Visual
            st.markdown(f"### <span style='color:{status_cor}'>{status_texto}</span>", unsafe_allow_html=True)
            st.progress(min(percentual_pendente/100, 1.0)) # Uma barrinha visual de 0 a 100%

        except Exception as e:
            st.warning(f"Aguardando dados para processar o painel. (Erro: {e})")

    st.divider()

    # 2. LANÇAMENTO FIFO (ABATIMENTO)
    with st.expander("➕ Lançar Novo Abatimento (Sistema FIFO)", expanded=False):
        with st.form("f_fifo_novo", clear_on_submit=True):
            # LISTA UNIFORME: Agora usa o banco_de_clientes completo, igual às outras abas!
            lista_todas_clientes = sorted([f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
            c_pg = st.selectbox("Quem está pagando?", ["Selecione..."] + lista_todas_clientes)
            
            f1, f2, f3 = st.columns(3)
            v_pg = f1.number_input("Valor Pago (R$)", min_value=0.0)
            meio = f2.selectbox("Meio", ["Pix", "Dinheiro", "Cartão", "Sweet Flex"])
            obs = f3.text_input("Obs", "Abatimento")
            
            if st.form_submit_button("Confirmar Pagamento ✅"):
                if v_pg > 0 and c_pg != "Selecione...":
                    try:
                        aba_v = planilha_mestre.worksheet("VENDAS")
                        # Lemos os dados "vivos" para garantir que o FIFO não erre a linha
                        df_v_viva = pd.DataFrame(aba_v.get_all_records())
                        df_v_viva['S_NUM'] = df_v_viva['SALDO DEVEDOR'].apply(limpar_v)
                        
                        nome_c_alvo = " - ".join(c_pg.split(" - ")[1:])
                        # Filtra apenas vendas com saldo > 0 daquela cliente
                        pendentes = df_v_viva[(df_v_viva['CLIENTE'] == nome_c_alvo) & (df_v_viva['S_NUM'] > 0)].copy()
                        
                        sobra = v_pg
                        for idx, row in pendentes.iterrows():
                            if sobra <= 0: break
                            lin_planilha = idx + 2 # +2 porque o pandas ignora o cabeçalho e começa no 0
                            div_linha = row['S_NUM']
                            
                            if sobra >= div_linha:
                                aba_v.update_acell(f"U{lin_planilha}", 0) # Zera a dívida
                                aba_v.update_acell(f"W{lin_planilha}", "Pago") # Muda status
                                sobra -= div_linha
                            else:
                                aba_v.update_acell(f"U{lin_planilha}", div_linha - sobra) # Abate parcial
                                sobra = 0
                        
                        # Registra no histórico do Financeiro
                        aba_f = planilha_mestre.worksheet("FINANCEIRO")
                        aba_f.append_row([
                            datetime.now().strftime("%d/%m/%Y"), 
                            datetime.now().strftime("%H:%M"), 
                            c_pg.split(" - ")[0], 
                            nome_c_alvo, 0, v_pg, "PAGO", f"{meio}: {obs}"
                        ], value_input_option='USER_ENTERED')
                        
                        st.success(f"✅ Recebido de {nome_c_alvo} processado!")
                        st.cache_resource.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Erro no FIFO: {e}")

    st.divider()

    # 3. FICHA DA CLIENTE (LISTA CORRIGIDA + CÁLCULO REAL)
    st.markdown("### 🔍 Ficha de Cliente (Extrato Dinâmico)")
    
    # LISTA UNIFORME: Agora igual à de Vendas e Abatimento
    opcoes_ficha = sorted([f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
    sel_ficha = st.selectbox("Selecione para ver o que ela deve:", ["---"] + opcoes_ficha)
    
    if sel_ficha != "---":
        id_c = sel_ficha.split(" - ")[0]
        nome_c_ficha = " - ".join(sel_ficha.split(" - ")[1:])
        
        # Filtra o histórico de vendas dessa cliente
        v_hist = df_vendas_hist[df_vendas_hist['CÓD. CLIENTE'].astype(str) == id_c]
        
        # CORREÇÃO DA MATEMÁTICA: 
        # Como o FIFO já abate na coluna U, o saldo real é APENAS a soma da coluna U.
        saldo_devedor_real = v_hist['SALDO DEVEDOR'].apply(limpar_v).sum()
        
        c_f1, c_f2 = st.columns(2)
        c_f1.metric("Saldo Devedor Atual", f"R$ {saldo_devedor_real:,.2f}")
        
        if saldo_devedor_real > 0.01:
            tel_c = banco_de_clientes.get(id_c, {}).get('fone', "")
            msg_zap = f"Olá {nome_c_ficha}! 🏠 Segue seu extrato na *Sweet Home Enxovais*. Atualmente consta um saldo pendente de *R$ {saldo_devedor_real:.2f}*. Qualquer dúvida estou à disposição! 😊"
            st.link_button("📲 Cobrar no WhatsApp", f"https://wa.me/55{tel_c}?text={urllib.parse.quote(msg_zap)}", use_container_width=True)
        else:
            st.success("✅ Esta cliente não possui débitos pendentes.")

        st.write("#### ⏳ Histórico de Vendas Localizado")
        if not v_hist.empty:
            st.dataframe(v_hist[['DATA DA VENDA', 'PRODUTO', 'TOTAL R$', 'SALDO DEVEDOR', 'STATUS']], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma compra registrada para esta cliente ainda.")

# ==========================================
# --- ABA 3: ESTOQUE (CADASTRO + BUSCA + ALERTA) ---
# ==========================================
with aba_estoque:
    st.subheader("📦 Gestão de Itens")
    with st.expander("➕ Cadastrar Novo Produto"):
        with st.form("f_est"):
            c1, c2 = st.columns([1, 2]); n_c = c1.text_input("Cód."); n_n = c2.text_input("Nome")
            c3, c4 = st.columns(2); n_q = c3.number_input("Qtd", 0); n_v = c4.number_input("Venda", 0.0)
            if st.form_submit_button("Salvar"):
                aba_inv = planilha_mestre.worksheet("INVENTÁRIO")
                aba_inv.append_row([n_c, n_n, n_q, 0, "", 3, 0, "", n_v, datetime.now().strftime("%d/%m/%Y"), ""], value_input_option='USER_ENTERED')
                st.success("✅ Cadastrado!"); st.cache_resource.clear()
    
    st.divider()
    busca = st.text_input("🔍 Buscar (Nome, Código ou Data)")
    df_e = df_full_inv.copy()
    if not df_e.empty:
        df_e['QUANTIDADE'] = pd.to_numeric(df_e['QUANTIDADE'], errors='coerce')
        baixos = df_e[df_e['QUANTIDADE'] <= 3]
        if not baixos.empty: st.warning(f"🚨 {len(baixos)} itens com estoque baixo!")
    if busca: df_e = df_e[df_e.apply(lambda r: busca.lower() in str(r).lower(), axis=1)]
    st.dataframe(df_e, use_container_width=True, hide_index=True)

# ==========================================
# --- ABA 4: CLIENTES (RADAR + CADASTRO DO ZERO) ---
# ==========================================
with aba_clientes:
    st.subheader("👥 Gestão de Clientes")

    # ÁREA 2: CADASTRO DO ZERO (RECUPERADO)
    with st.expander("➕ Cadastrar Nova Cliente (Sem compra atual)", expanded=False):
        with st.form("form_novo_manual", clear_on_submit=True):
            st.markdown("Código gerado automaticamente.")
            c1, c2 = st.columns([2, 1])
            n_nome = c1.text_input("Nome Completo *"); n_zap = c2.text_input("WhatsApp *")
            c3, c4 = st.columns([3, 1])
            n_end = c3.text_input("Endereço"); n_vale = c4.number_input("Vale Desconto", 0.0)
            if st.form_submit_button("Salvar Cadastro 💾"):
                if n_nome and n_zap:
                    try:
                        aba_cli_sheet = planilha_mestre.worksheet("CARTEIRA DE CLIENTES")
                        codigo = f"CLI-{len(aba_cli_sheet.get_all_values()):03d}"
                        aba_cli_sheet.append_row([codigo, n_nome.strip(), n_zap.strip(), n_end.strip(), datetime.now().strftime("%d/%m/%Y"), n_vale, "", "Completo" if n_end else "Incompleto"], value_input_option='USER_ENTERED')
                        st.success(f"✅ {n_nome} cadastrada!"); st.cache_resource.clear()
                    except Exception as e: st.error(f"Erro: {e}")

    st.divider()
    if not df_clientes_full.empty:
        try:
            inc = df_clientes_full[df_clientes_full.iloc[:, 7].str.strip() == "Incompleto"]
            if not inc.empty:
                st.warning(f"🚨 Radar: {len(inc)} cadastros pendentes!")
                st.dataframe(inc, hide_index=True)
        except: pass
        st.markdown("### 🗂️ Carteira Total")
        st.dataframe(df_clientes_full, use_container_width=True, hide_index=True)











