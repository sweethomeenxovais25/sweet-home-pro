import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import random
from datetime import datetime
import urllib.parse

# --- INICIALIZAÇÃO DA MEMÓRIA DA SESSÃO ---
if 'historico_sessao' not in st.session_state:
    st.session_state['historico_sessao'] = []

# ==========================================
# 1. CONEXÃO E CONFIGURAÇÃO
# ==========================================
st.set_page_config(page_title="Sweet Home Pro", page_icon="🏠", layout="wide")

# ID da sua planilha
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
        else:
            if os.path.exists('credenciais.json'):
                creds = ServiceAccountCredentials.from_json_keyfile_name('credenciais.json', ESPECIFICACOES)
                return gspread.authorize(creds).open_by_key(ID_PLANILHA)
            return None
    except Exception as e:
        st.error(f"Erro detalhado de conexão: {e}")
        return None

planilha_mestre = conectar_google()

# ==========================================
# 2. CARREGAMENTO REFINADO (Fiel à Planilha)
# ==========================================
def carregar_dados():
    if not planilha_mestre: 
        return {}, {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    def ler_aba_seguro(nome):
        try:
            aba = planilha_mestre.worksheet(nome)
            dados = aba.get_all_values()
            if not dados: return pd.DataFrame()
            df = pd.DataFrame(dados[1:], columns=dados[0])
            return df[df.iloc[:, 0].str.strip() != ""]
        except: return pd.DataFrame()

    df_inv = ler_aba_seguro("INVENTÁRIO")
    df_cli = ler_aba_seguro("CARTEIRA DE CLIENTES")
    df_fin = ler_aba_seguro("FINANCEIRO")
    df_vendas = ler_aba_seguro("VENDAS")
    df_painel = ler_aba_seguro("PAINEL")

    banco_prod = {str(r['CÓD. PRÓDUTO']): {"nome": r['NOME DO PRODUTO'], "estoque": r['ESTOQUE ATUAL'], "venda": r['VALOR DE VENDA']} for _, r in df_inv.iterrows()}
    banco_cli = {str(r['CÓD. CLIENTE']): {"nome": str(r['NOME DO CLIENTE']), "fone": str(r.get('TELEFONE', ''))} for _, r in df_cli.iterrows()}

    return banco_prod, banco_cli, df_full_inv, df_financeiro, df_vendas_hist, df_painel_resumo

banco_de_produtos, banco_de_clientes, df_full_inv, df_financeiro, df_vendas_hist, df_painel_resumo = carregar_dados()

def tratar_numeros(df, colunas):
    for col in colunas:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# ==========================================
# 3. BARRA LATERAL (MODO TESTE E ATUALIZAÇÃO)
# ==========================================
st.sidebar.title("🛠️ Painel Sweet Home")
modo_teste = st.sidebar.toggle("🔬 Modo de Teste (Simulação)", value=False)
if modo_teste: st.sidebar.warning("⚠️ MODO TESTE ATIVO")

if st.sidebar.button("🔄 Sincronizar Planilha"):
    st.cache_resource.clear()
    st.rerun()

aba_venda, aba_financeiro, aba_estoque, aba_clientes = st.tabs(["🛒 Vendas", "💰 Financeiro", "📦 Estoque", "👥 Clientes"])

# --- ABA 1: VENDAS ---
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
            nome_cli = c_nome_novo if c_sel == "*** NOVO CLIENTE ***" else banco_de_clientes[c_sel.split(" - ")[0]]['nome']
            t_liq = (qtd_v * val_v) - desc_v
            nome_prod = p_sel.split(" - ")[1].strip()
            
            novo_log = {
                "Data": datetime.now().strftime("%d/%m/%Y"),
                "Hora": datetime.now().strftime("%H:%M:%S"),
                "Cliente": nome_cli,
                "Produto": nome_prod,
                "QT": qtd_v,
                "Pagamento": metodo,
                "Total": f"R$ {t_liq:.2f}"
            }
            st.session_state['historico_sessao'].insert(0, novo_log)

            if not modo_teste:
                try:
                    aba_v_sheet = planilha_mestre.worksheet("VENDAS")
                    
                    # CORREÇÃO: Localizar próxima linha pela Coluna B (Data)
                    proxima_linha = len(aba_v_sheet.col_values(2)) + 1
                    
                    cod_cli = "NOVO" if c_sel == "*** NOVO CLIENTE ***" else c_sel.split(" - ")[0]
                    cod_prod = p_sel.split(" - ")[0]
                    
                    eh_parc = "Sim" if metodo == "Sweet Flex" else "Não"
                    val_a_vista = t_liq if eh_parc == "Não" else 0
                    val_parc = t_liq / n_p if eh_parc == "Sim" else 0
                    entrada = t_liq if eh_parc == "Não" else 0
                    saldo_dev = t_liq if eh_parc == "Sim" else 0
                    status = "Pendente" if eh_parc == "Sim" else "Pago"
                    dt_prox = detalhes_p[0] if (eh_parc == "Sim" and detalhes_p) else ""
                    f_atraso = '=SE(OU(INDIRETO("W"&LIN())="Pago"; INDIRETO("W"&LIN())="Em dia"); 0; MÁXIMO(0; HOJE() - INDIRETO("V"&LIN())))'
                    
                    linha_nova = [
                        "", datetime.now().strftime("%d/%m/%Y"), cod_cli, nome_cli, 
                        cod_prod, nome_prod, "", qtd_v, val_v, desc_v, 
                        "", t_liq, "", "", metodo, 
                        eh_parc, n_p, val_a_vista, val_parc, entrada, 
                        saldo_dev, dt_prox, status, f_atraso
                    ]
                    
                    # GRAVAÇÃO PRECISA: Evita pular linhas
                    aba_v_sheet.update(f"A{proxima_linha}", [linha_nova], value_input_option='USER_ENTERED')
                    
                    st.cache_resource.clear()
                    st.success("✅ Venda Gravada na Planilha!")
                except Exception as erro:
                    st.error(f"❌ Erro ao comunicar com a Planilha: {erro}")
            else:
                st.warning("🔬 Simulação: Venda processada apenas localmente (Modo Teste).")
            
            recibo = f"*RECIBO DE COMPRA*\n\n*Nome da cliente:* {nome_cli}\n*Data:* {datetime.now().strftime('%d/%m/%Y')}\n*Vendedor(a):* {vendedor}\n\n*Itens adquiridos:*\n- {qtd_v}x {nome_prod} = R$ {qtd_v*val_v:.2f}"
            if desc_v > 0: recibo += f"\n-- R$ {desc_v:.2f} de desconto = R$ {t_liq:.2f}"
            if metodo == "Sweet Flex":
                recibo += "\n\n*Cronograma de Pagamento:*"
                for d_p in detalhes_p: recibo += f"\n{d_p} -------- R$ {t_liq/n_p:.2f}"
            recibo += f"\n\n*Obs:* Recibo válido como comprovação de compra. Dúvidas, chame a {vendedor}."
            
            link = f"https://wa.me/55{c_zap}?text={urllib.parse.quote(recibo)}"
            st.link_button("Enviar no WhatsApp 📲", link, use_container_width=True)
            st.code(recibo)

    st.divider()
    st.subheader("📝 Registros Realizados Agora")
    if st.session_state['historico_sessao']:
        st.dataframe(st.session_state['historico_sessao'], use_container_width=True, hide_index=True)
        if st.button("Limpar Histórico Local 🗑️"):
            st.session_state['historico_sessao'] = []
            st.rerun()
    else:
        st.info("Aguardando a primeira venda desta sessão...")

# --- ABA 2: FINANCEIRO ---
with aba_financeiro:
    from datetime import datetime
    st.markdown("### 📈 Resumo Geral Sweet Home Enxovais")
    
    def limpar_v(v):
        if pd.isna(v) or v == "": return 0.0
        return pd.to_numeric(str(v).replace('R$', '').replace('.', '').replace(',', '.').strip(), errors='coerce') or 0.0

    try:
        divida_total_vendas = df_vendas_hist['SALDO DEVEDOR'].apply(limpar_v).sum()
        total_recebido_fin = df_financeiro['VALOR_PAGO'].apply(limpar_v).sum()
        saldo_rua = divida_total_vendas - total_recebido_fin

        c1, c2, c3 = st.columns(3)
        c1.metric("Dívida Total (Vendas)", f"R$ {divida_total_vendas:,.2f}")
        c2.metric("Total Recebido (Abatimentos)", f"R$ {total_recebido_fin:,.2f}")
        c3.metric("Saldo Líquido na Rua", f"R$ {saldo_rua:,.2f}", delta="- Pendente", delta_color="inverse")
    except Exception as e:
        st.warning("Aguardando dados para calcular o resumo geral.")

    st.divider()

    with st.expander("➕ Lançar Novo Recebimento / Abatimento", expanded=False):
        with st.form("form_registro_pagamento", clear_on_submit=True):
            lista_clientes_base = sorted([f"{k} - {v['nome']}" for k, v in banco_de_clientes.items()])
            c_escolhida = st.selectbox("Quem está pagando?", ["Selecione..."] + lista_clientes_base)
            f1, f2, f3 = st.columns([1, 1, 1])
            valor_pgto = f1.number_input("Valor Pago (R$)", min_value=0.0, format="%.2f")
            meio_pgto = f2.selectbox("Meio de Pagamento", ["Pix", "Dinheiro", "Cartão", "Sweet Flex"])
            obs_pgto = f3.text_input("Obs", value="Abatimento")
            
            if st.form_submit_button("Confirmar Recebimento ✅"):
                if valor_pgto <= 0:
                    st.error("⚠️ O valor do pagamento deve ser maior que zero!")
                elif c_escolhida == "Selecione...":
                    st.error("⚠️ Por favor, selecione a cliente que está pagando.")
                else:
                    cod_c = c_escolhida.split(" - ")[0]
                    nome_c = " - ".join(c_escolhida.split(" - ")[1:])
                    
                    if not modo_teste:
                        try:
                            aba_v_sheet = planilha_mestre.worksheet("VENDAS")
                            df_v_viva = pd.DataFrame(aba_v_sheet.get_all_records())
                            df_v_viva['S_NUM'] = df_v_viva['SALDO DEVEDOR'].apply(limpar_v)
                            pendencias = df_v_viva[(df_v_viva['CLIENTE'] == nome_c) & (df_v_viva['S_NUM'] > 0)].copy()
                            
                            saldo_disponivel = valor_pgto
                            for idx, row in pendencias.iterrows():
                                if saldo_disponivel <= 0: break
                                linha_excel = idx + 2 
                                divida_da_linha = row['S_NUM']
                                
                                if saldo_disponivel >= divida_da_linha:
                                    aba_v_sheet.update_acell(f"U{linha_excel}", 0)
                                    aba_v_sheet.update_acell(f"W{linha_excel}", "Pago")
                                    aba_v_sheet.update_acell(f"V{linha_excel}", "")
                                    saldo_disponivel -= divida_da_linha
                                else:
                                    aba_v_sheet.update_acell(f"U{linha_excel}", divida_da_linha - saldo_disponivel)
                                    saldo_disponivel = 0
                            
                            aba_f = planilha_mestre.worksheet("FINANCEIRO")
                            
                            # CORREÇÃO: Localizar próxima linha pela Coluna A (Data)
                            proxima_linha_f = len(aba_f.col_values(1)) + 1
                            
                            linha_nova = [
                                datetime.now().strftime("%d/%m/%Y"),
                                datetime.now().strftime("%H:%M"),
                                cod_c, nome_c, 0, valor_pgto, "PAGO", f"{meio_pgto}: {obs_pgto}"
                            ]
                            
                            aba_f.update(f"A{proxima_linha_f}", [linha_nova], value_input_option='USER_ENTERED')
                            
                            st.success(f"✅ R$ {valor_pgto:.2f} via {meio_pgto} abatido da conta de {nome_c}!")
                            st.cache_resource.clear() 
                        except Exception as e:
                            st.error(f"Erro de conexão com o Google Sheets: {e}")
                    else:
                        st.warning(f"🔬 Simulação: R$ {valor_pgto:.2f} seriam abatidos via {meio_pgto}.")

    st.divider()
    st.markdown("### 🔍 Consultar Ficha da Cliente")
    if not df_vendas_hist.empty:
        codigos_vendas = df_vendas_hist['CÓD. CLIENTE'].unique().tolist()
        opcoes_busca = sorted([f"{c} - {banco_de_clientes.get(str(c), {}).get('nome', 'Desconhecido')}" for c in codigos_vendas if str(c).strip()])
        selecao_c = st.selectbox("Selecione para ver detalhes e cobrar:", ["--- Selecionar ---"] + opcoes_busca)

        if selecao_c != "--- Selecionar ---":
            id_cliente = selecao_c.split(" - ")[0]
            nome_cliente = " - ".join(selecao_c.split(" - ")[1:])
            v_hist = df_vendas_hist[df_vendas_hist['CÓD. CLIENTE'].astype(str) == id_cliente]
            div_u = v_hist['SALDO DEVEDOR'].apply(limpar_v).sum()
            pagos_f = 0.0
            if not df_financeiro.empty:
                f_hist = df_financeiro[df_financeiro['CÓD. CLIENTE'].astype(str) == id_cliente]
                pagos_f = f_hist['VALOR_PAGO'].apply(limpar_v).sum()
            saldo_final_c = div_u - pagos_f
            st.info(f"📋 Ficha de: **{selecao_c}**")
            m1, m2, m3 = st.columns(3)
            m1.metric("Dívida Histórica", f"R$ {div_u:,.2f}")
            m2.metric("Total Pago Recente", f"R$ {pagos_f:,.2f}")
            if saldo_final_c > 0.01:
                m3.metric("Saldo Real a Pagar", f"R$ {saldo_final_c:,.2f}", delta="- Pendente", delta_color="inverse")
                tel = banco_de_clientes.get(id_cliente, {}).get('fone', "")
                texto_zap = f"Olá {nome_cliente}! 🏠 Passando da *Sweet Home Enxovais* para atualizar seu extrato: saldo de *R$ {saldo_final_c:.2f}*. 😊"
                st.link_button(f"📲 Lembrar via WhatsApp", f"https://wa.me/55{tel}?text={urllib.parse.quote(texto_zap)}", use_container_width=True)
            else:
                m3.success("✅ CLIENTE EM DIA")
            st.divider()
            st.write("#### ⏳ Histórico Localizado na Aba Vendas")
            st.dataframe(v_hist[['DATA DA VENDA', 'PRODUTO', 'TOTAL R$', 'SALDO DEVEDOR', 'STATUS']], use_container_width=True, hide_index=True)

# --- ABA 3: CONTROLE DE ESTOQUE ---
with aba_estoque:
    st.subheader("📦 Inventário e Controle de Entradas")
    with st.expander("➕ Cadastrar Novo Produto", expanded=False):
        with st.form("form_novo_produto", clear_on_submit=True):
            st.markdown("Preencha os dados básicos. Fórmulas da planilha farão o resto!")
            c1, c2 = st.columns([1, 2])
            novo_cod = c1.text_input("Cód. Produto (Ex: TOA-01)")
            novo_nome = c2.text_input("Nome do Produto")
            c3, c4, c5 = st.columns(3)
            nova_qtd = c3.number_input("Qtd Inicial", min_value=0, step=1)
            novo_custo = c4.number_input("Custo Unit (R$)", min_value=0.0, format="%.2f")
            novo_venda = c5.number_input("Valor Venda (R$)", min_value=0.0, format="%.2f")
            nova_qtd_min = st.number_input("Quantidade Mínima (Alerta de Estoque)", min_value=1, step=1, value=3)
            
            if st.form_submit_button("Salvar Produto no Estoque 📦"):
                if novo_cod and novo_nome:
                    if not modo_teste:
                        try:
                            aba_inv = planilha_mestre.worksheet("INVENTÁRIO")
                            
                            # CORREÇÃO: Localizar próxima linha pela Coluna A (Cód)
                            proxima_linha_inv = len(aba_inv.col_values(1)) + 1
                            
                            linha_produto = [
                                novo_cod.strip(), novo_nome.strip(), nova_qtd, novo_custo, 
                                "", nova_qtd_min, 0, "", novo_venda, 
                                datetime.now().strftime("%d/%m/%Y"), ""
                            ]
                            
                            aba_inv.update(f"A{proxima_linha_inv}", [linha_produto], value_input_option='USER_ENTERED')
                            st.success(f"✅ Produto '{novo_nome}' cadastrado!")
                            st.cache_resource.clear()
                        except Exception as e:
                            st.error(f"Erro de conexão com a planilha: {e}")
                    else:
                        st.warning("🔬 Simulação ativa.")
                else:
                    st.error("⚠️ Código e Nome são obrigatórios.")

    st.divider()
    if not df_full_inv.empty:
        df_estoque_vis = df_full_inv.copy()
        col_entrada = 'ÚLTIMA ENTRADA'
        col_qtd = 'QUANTIDADE' 
        if col_qtd in df_estoque_vis.columns:
            df_estoque_vis[col_qtd] = pd.to_numeric(df_estoque_vis[col_qtd], errors='coerce')
            estoque_baixo = df_estoque_vis[df_estoque_vis[col_qtd] <= 3]
            if not estoque_baixo.empty:
                st.warning(f"🚨 Atenção: {len(estoque_baixo)} produto(s) com estoque baixo!")
                with st.expander("👀 Ver produtos que precisam de reposição"):
                    st.dataframe(estoque_baixo[['NOME DO PRODUTO', col_qtd]], hide_index=True)
        st.markdown("### 🔍 Buscar Produtos")
        termo_busca = st.text_input("Localize pelo nome ou data...")
        if termo_busca:
            filtro = (df_estoque_vis['NOME DO PRODUTO'].astype(str).str.contains(termo_busca, case=False, na=False))
            df_estoque_vis = df_estoque_vis[filtro]
        st.markdown("### 📋 Tabela de Estoque Atualizada")
        st.dataframe(df_estoque_vis, use_container_width=True, hide_index=True)
    else:
        st.info("Aguardando carregamento de Inventário...")

# --- ABA 4: CLIENTES ---
with aba_clientes:
    st.subheader("👥 Gestão de Clientes e Fidelização")
    try:
        aba_cli_sheet = planilha_mestre.worksheet("CARTEIRA DE CLIENTES")
        dados_clientes = aba_cli_sheet.get_all_values()
        incompletos = []
        for i, linha in enumerate(dados_clientes):
            if i == 0: continue 
            if len(linha) > 7 and linha[7] == "Incompleto":
                incompletos.append({"linha_excel": i + 1, "cod": linha[0], "nome": linha[1], "zap": linha[2]})
        
        if incompletos:
            st.warning(f"🚨 Radar: Temos {len(incompletos)} cliente(s) incompletos!")
            with st.form("form_atualizar_cliente", clear_on_submit=True):
                opcoes_inc = {f"{c['cod']} - {c['nome']}": c for c in incompletos}
                sel_inc = st.selectbox("Selecione para completar:", ["Selecione..."] + list(opcoes_inc.keys()))
                c_edit1, c_edit2 = st.columns([2, 1])
                end_novo = c_edit1.text_input("Bairro / Endereço *")
                vale_novo = c_edit2.number_input("Vale Desconto (R$)", min_value=0.0)
                obs_nova = st.text_input("Observações")
                if st.form_submit_button("Atualizar Cadastro ✅"):
                    if sel_inc != "Selecione..." and end_novo:
                        c_alvo = opcoes_inc[sel_inc]
                        l_a = c_alvo['linha_excel']
                        if not modo_teste:
                            aba_cli_sheet.update_acell(f"D{l_a}", end_novo.strip())
                            aba_cli_sheet.update_acell(f"F{l_a}", vale_novo)
                            aba_cli_sheet.update_acell(f"G{l_a}", obs_nova.strip())
                            aba_cli_sheet.update_acell(f"H{l_a}", "Completo")
                            st.success("🎉 Finalizado!")
                            st.cache_resource.clear()
        else:
            st.success("✨ Tudo em dia!")
    except Exception as e:
        st.info(f"Conectando... {e}")

    st.divider()
    with st.expander("➕ Cadastrar Nova Cliente", expanded=False):
        with st.form("form_novo_cliente", clear_on_submit=True):
            c1, c2 = st.columns([2, 1])
            novo_nome_cli = c1.text_input("Nome Completo *")
            novo_zap_cli = c2.text_input("WhatsApp *")
            novo_endereco = st.text_input("Bairro / Endereço")
            novo_vale = st.number_input("Vale Desconto Inicial (R$)", min_value=0.0)
            
            if st.form_submit_button("Salvar Novo Cadastro 💾"):
                if novo_nome_cli and novo_zap_cli:
                    try:
                        prox_num = len(aba_cli_sheet.col_values(1))
                        codigo_gerado = f"CLI-{prox_num:03d}" 
                        if not modo_teste:
                            proxima_linha_cli = prox_num + 1
                            linha_cliente = [
                                codigo_gerado, novo_nome_cli.strip(), novo_zap_cli.strip(),
                                novo_endereco.strip(), datetime.now().strftime("%d/%m/%Y"),
                                novo_vale, "", "Completo" if novo_endereco else "Incompleto"
                            ]
                            # GRAVAÇÃO PRECISA
                            aba_cli_sheet.update(f"A{proxima_linha_cli}", [linha_cliente], value_input_option='USER_ENTERED')
                            st.success(f"✅ {novo_nome_cli} cadastrada!")
                            st.cache_resource.clear()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
