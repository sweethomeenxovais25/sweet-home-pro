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

# Barra Lateral (Sidebar) com Logout, Logo e NAVEGAÇÃO
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
    
    # ⚓ A ÂNCORA MASTER: Isso impede a página de pular
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

    banco_prod = {str(r.iloc[0]): {"nome": r.iloc[1], "custo": float(limpar_v(r.iloc[6])), "estoque": r.iloc[7], "venda": r.iloc[8]} for _, r in df_inv.iterrows()} if not df_inv.empty else {}
    banco_cli = {str(r.iloc[0]): {"nome": str(r.iloc[1]), "fone": str(r.iloc[2])} for _, r in df_cli.iterrows()} if not df_cli.empty else {}

    return banco_prod, banco_cli, df_inv, df_fin, df_vendas, df_painel, df_cli

banco_de_produtos, banco_de_clientes, df_full_inv, df_financeiro, df_vendas_hist, df_painel_resumo, df_clientes_full = carregar_dados()

# ==========================================
# --- SEÇÃO 1: VENDAS (SISTEMA INTEGRAL) ---
# ==========================================
if menu_selecionado == "🛒 Vendas":
    st.subheader("🛒 Registro de Venda")
    
    # 🔑 O SEGREDO DA CORREÇÃO: Seleção de pagamento ANTES do formulário
    # Isso destrava a tela e faz os calendários do Sweet Flex aparecerem na hora!
    metodo = st.selectbox("Forma de Pagamento", ["Pix", "Dinheiro", "Cartão", "Sweet Flex"], key="venda_metodo_pg")
    
    # O formulário agora agrupa o resto, mantendo a limpeza automática (clear_on_submit)
    with st.form("form_venda_final", clear_on_submit=True):
        
        detalhes_p = []; n_p = 1 
        if metodo == "Sweet Flex":
            n_p = st.number_input("Número de Parcelas", 1, 12, 1, key="venda_n_parcelas")
            cols_parc = st.columns(n_p)
            for i in range(n_p):
                with cols_parc[i]:
                    # 🇧🇷 O PARÂMETRO format="DD/MM/YYYY" DEIXA O CALENDÁRIO NO PADRÃO BRASIL
                    dt = st.date_input(f"{i+1}ª Parc.", datetime.now(), format="DD/MM/YYYY", key=f"vd_data_parc_{i}")
                    detalhes_p.append(dt.strftime("%d/%m/%Y"))

        col_esq, col_dir = st.columns(2)

        with col_esq:
            st.write("👤 **Dados da Cliente**")
            c_sel = st.selectbox(
                "Selecionar Cliente", 
                ["*** NOVO CLIENTE ***"] + [f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()],
                key="venda_cliente_sel"
            )
            
            telefone_sugerido = ""
            if c_sel != "*** NOVO CLIENTE ***":
                id_cliente = c_sel.split(" - ")[0].strip()
                if id_cliente in banco_de_clientes:
                    telefone_sugerido = banco_de_clientes[id_cliente].get('fone', "")

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
            # --- 1. PONTE DE CADASTRO AUTOMÁTICO ---
            if c_sel == "*** NOVO CLIENTE ***":
                if not c_nome_novo or not c_zap: 
                    st.error("⚠️ Preencha Nome e Zap!"); st.stop()
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
                    except Exception as e: 
                        st.error(f"Erro no cadastro: {e}"); st.stop()
                else: cod_cli = "CLI-TESTE"
            else:
                cod_cli = c_sel.split(" - ")[0]
                nome_cli = banco_de_clientes[cod_cli]['nome']

            # --- 2. PROCESSAMENTO FINANCEIRO (CÁLCULOS) ---
            v_bruto = qtd_v * val_v
            t_liq = v_bruto - desc_v
            desc_percentual = desc_v / v_bruto if v_bruto > 0 else 0
            cod_p = p_sel.split(" - ")[0]
            nome_p = p_sel.split(" - ")[1].strip()
            custo_un = float(banco_de_produtos[cod_p].get('custo', 0.0)) if cod_p in banco_de_produtos else 0.0
            
            # --- 3. ALIMENTAR HISTÓRICO DE SESSÃO ---
            st.session_state['historico_sessao'].insert(0, {
                "Data": datetime.now().strftime("%d/%m/%Y"),
                "Hora": datetime.now().strftime("%H:%M:%S"),
                "Cliente": nome_cli, 
                "Produto": nome_p, 
                "Pagto": metodo, 
                "Total": f"R$ {t_liq:.2f}"
            })

            # --- 4. ENVIO PARA PLANILHA (SÓ SE NÃO FOR TESTE) ---
            if not modo_teste:
                try:
                    aba_v = planilha_mestre.worksheet("VENDAS")
                    idx_ins = aba_v.find("TOTAIS").row 
                    eh_parc = "Sim" if metodo == "Sweet Flex" else "Não"
                    f_atraso = '=SE(OU(INDIRETO("W"&LIN())="Pago"; INDIRETO("W"&LIN())="Em dia"); 0; MÁXIMO(0; HOJE() - INDIRETO("V"&LIN())))'
                    
                    # LINHA EXATAMENTE IGUAL AO SEU ORIGINAL
                    linha = ["", datetime.now().strftime("%d/%m/%Y"), cod_cli, nome_cli, cod_p, nome_p, custo_un, qtd_v, val_v, desc_percentual, "", "", "", "", metodo, eh_parc, n_p, "", t_liq/n_p if eh_parc=="Sim" else 0, t_liq if eh_parc=="Não" else 0, "", detalhes_p[0] if (eh_parc=="Sim" and detalhes_p) else "", "Pendente" if eh_parc=="Sim" else "Pago", f_atraso]
                    
                    aba_v.insert_row(linha, index=idx_ins, value_input_option='USER_ENTERED')
                    st.success("✅ Venda registrada com sucesso!")
                    st.cache_data.clear() 
                except Exception as e:
                    st.error(f"Erro ao registrar: {e}")
            else:
                st.info("🧪 Modo Teste: Simulação realizada com sucesso!")

            # --- 5. RECIBO PADRÃO SWEET HOME 🌸 ---
            st.divider()
            recibo_texto = (
                f"🌸 *RECIBO SWEET HOME ENXOVAIS*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"Olá, *{nome_cli.split(' ')[0]}*! Segue o resumo da sua compra:\n\n"
                f"📦 *Produto:* {qtd_v}x {nome_p}\n"
                f"💰 *Valor Total:* R$ {t_liq:.2f}\n"
                f"💳 *Forma de Pagto:* {metodo}\n"
                f"🗓️ *Data:* {datetime.now().strftime('%d/%m/%Y')}\n"
                f"👤 *Vendedor(a):* {vendedor}\n"
            )
            if metodo == "Sweet Flex":
                recibo_texto += f"\n📝 *Plano de Pagamento:* {n_p}x de R$ {t_liq/n_p:.2f}\n"
                for i, data_p in enumerate(detalhes_p):
                    recibo_texto += f"🔹 {i+1}ª Parcela: {data_p}\n"
            recibo_texto += f"\n━━━━━━━━━━━━━━━━━━━\n✨ *Obrigada pela preferência!*"

            st.code(recibo_texto, language="text")
            
            zap_limpo = c_zap.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            st.link_button("📲 Enviar Recibo para o WhatsApp", f"https://wa.me/55{zap_limpo}?text={urllib.parse.quote(recibo_texto)}", use_container_width=True, type="primary")

    # --- SEÇÃO REGISTROS RECENTES ---
    st.divider()
    st.subheader("📝 Histórico de Registros")
    if st.session_state['historico_sessao']:
        st.dataframe(st.session_state['historico_sessao'], use_container_width=True, hide_index=True)
        if st.button("Limpar Histórico Local 🗑️", key="btn_limpar_hist"):
            st.session_state['historico_sessao'] = []; st.rerun()

# ==========================================
# --- SEÇÃO 2: FINANCEIRO (RESUMO + FIFO + COBRANÇA) ---
# ==========================================
elif menu_selecionado == "💰 Financeiro":
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
            st.progress(min(percentual_pendente/100, 1.0)) 

        except Exception as e:
            st.warning(f"Aguardando dados para processar o painel. (Erro: {e})")

    st.divider()

    # 2. LANÇAMENTO FIFO (ABATIMENTO)
    with st.expander("➕ Lançar Novo Abatimento (Sistema FIFO)", expanded=False):
        with st.form("f_fifo_novo", clear_on_submit=True):
            lista_todas_clientes = sorted([f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
            c_pg = st.selectbox("Quem está pagando?", ["Selecione..."] + lista_todas_clientes, key="fifo_cliente")
            
            f1, f2, f3 = st.columns(3)
            v_pg = f1.number_input("Valor Pago (R$)", min_value=0.0, key="fifo_valor")
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

    # 3. FICHA DA CLIENTE
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
        else:
            st.success("✅ Esta cliente não possui débitos pendentes.")

        st.write("#### ⏳ Histórico de Vendas Localizado")
        if not v_hist.empty:
            st.dataframe(v_hist[['DATA DA VENDA', 'PRODUTO', 'TOTAL R$', 'SALDO DEVEDOR', 'STATUS']], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma compra registrada para esta cliente ainda.")

# ==========================================
# --- SEÇÃO 3: ESTOQUE ---
# ==========================================
elif menu_selecionado == "📦 Estoque":
    st.subheader("📦 Gestão de Itens")
    with st.expander("➕ Cadastrar Novo Produto"):
        with st.form("f_est", clear_on_submit=True):
            c1, c2 = st.columns([1, 2]); n_c = c1.text_input("Cód."); n_n = c2.text_input("Nome")
            c3, c4 = st.columns(2); n_q = c3.number_input("Qtd", 0); n_v = c4.number_input("Venda", 0.0)
            if st.form_submit_button("Salvar"):
                aba_inv = planilha_mestre.worksheet("INVENTÁRIO")
                aba_inv.append_row([n_c, n_n, n_q, 0, "", 3, 0, "", n_v, datetime.now().strftime("%d/%m/%Y"), ""], value_input_option='USER_ENTERED')
                st.success("✅ Cadastrado!"); st.cache_resource.clear()
    
    st.divider()
    busca = st.text_input("🔍 Buscar (Nome, Código ou Data)", key="busca_estoque_input")
    df_e = df_full_inv.copy()
    if not df_e.empty:
        df_e['QUANTIDADE'] = pd.to_numeric(df_e['QUANTIDADE'], errors='coerce')
        baixos = df_e[df_e['QUANTIDADE'] <= 3]
        if not baixos.empty: st.warning(f"🚨 {len(baixos)} itens com estoque baixo!")
    if busca: df_e = df_e[df_e.apply(lambda r: busca.lower() in str(r).lower(), axis=1)]
    st.dataframe(df_e, use_container_width=True, hide_index=True)

# ==========================================
# --- SEÇÃO 4: CLIENTES ---
# ==========================================
elif menu_selecionado == "👥 Clientes":
    st.subheader("👥 Gestão de Clientes")

    # ÁREA 2: CADASTRO DO ZERO
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
        
    # ÁREA 3: ATUALIZAÇÃO DE DADOS 
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




