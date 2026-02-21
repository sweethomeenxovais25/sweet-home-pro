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
@st.cache_resource(ttl=600)
def carregar_dados():
    if not planilha_mestre: 
        return {}, {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    def ler_aba_seguro(nome):
        try:
            aba = planilha_mestre.worksheet(nome)
            dados = aba.get_all_values()
            if len(dados) <= 1: return pd.DataFrame() # Se só tiver cabeçalho ou estiver vazia
            df = pd.DataFrame(dados[1:], columns=dados[0])
            # Limpa linhas onde a primeira coluna (Código) está vazia
            return df[df.iloc[:, 0].str.strip() != ""]
        except: return pd.DataFrame()

    df_inv = ler_aba_seguro("INVENTÁRIO")
    df_cli = ler_aba_seguro("CARTEIRA DE CLIENTES")
    df_fin = ler_aba_seguro("FINANCEIRO")
    df_vendas = ler_aba_seguro("VENDAS")
    df_painel = ler_aba_seguro("PAINEL")

    # Dicionários de busca rápida (Segurança por posição para evitar KeyError)
    banco_prod = {}
    if not df_inv.empty:
        for _, r in df_inv.iterrows():
            banco_prod[str(r.iloc[0])] = {"nome": r.iloc[1], "estoque": r.iloc[2], "venda": r.iloc[8]}

    banco_cli = {}
    if not df_cli.empty:
        for _, r in df_cli.iterrows():
            # Pegamos: Col 0 (Código), Col 1 (Nome), Col 2 (Fone)
            banco_cli[str(r.iloc[0])] = {"nome": str(r.iloc[1]), "fone": str(r.iloc[2])}

    return banco_prod, banco_cli, df_inv, df_fin, df_vendas, df_painel, df_cli

# Recebimento dos dados (7 itens agora)
banco_de_produtos, banco_de_clientes, df_full_inv, df_financeiro, df_vendas_hist, df_painel_resumo, df_clientes_full = carregar_dados()

# ==========================================
# --- ABA 1: VENDAS ---
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
            # --- [AJUSTE 1: PONTE DE CADASTRO AUTOMÁTICO] ---
            if c_sel == "*** NOVO CLIENTE ***":
                if not c_nome_novo or not c_zap:
                    st.error("⚠️ Para novos clientes, Nome e WhatsApp são obrigatórios!")
                    st.stop()
                
                nome_cli = c_nome_novo.strip()
                if not modo_teste:
                    try:
                        aba_cli_sheet = planilha_mestre.worksheet("CARTEIRA DE CLIENTES")
                        dados_cli_atuais = aba_cli_sheet.get_all_values()
                        nomes_no_banco = [linha[1].strip().upper() for linha in dados_cli_atuais[1:]]
                        
                        if nome_cli.upper() in nomes_no_banco:
                            idx = nomes_no_banco.index(nome_cli.upper())
                            cod_cli = dados_cli_atuais[idx + 1][0]
                        else:
                            prox_num_c = len(dados_cli_atuais)
                            cod_cli = f"CLI-{prox_num_c:03d}"
                            linha_novo_cliente = [cod_cli, nome_cli, c_zap.strip(), "", datetime.now().strftime("%d/%m/%Y"), 0, "", "Incompleto"]
                            aba_cli_sheet.append_row(linha_novo_cliente, value_input_option='USER_ENTERED')
                            st.toast(f"👤 {nome_cli} cadastrada automaticamente!")
                    except Exception as e:
                        st.error(f"Erro no cadastro: {e}"); st.stop()
                else:
                    cod_cli = "CLI-TESTE"
            else:
                cod_cli = c_sel.split(" - ")[0]
                nome_cli = banco_de_clientes[cod_cli]['nome']

            # --- 1. PROCESSAMENTO DE VALORES (Cálculos mantidos 100%) ---
            valor_bruto_total = qtd_v * val_v
            t_liq = valor_bruto_total - desc_v
            nome_prod = p_sel.split(" - ")[1].strip()

            # --- ✨ A MÁGICA DO DESCONTO (MANUTENÇÃO DO FORMATO %) ---
            if valor_bruto_total > 0:
                desc_percentual_decimal = desc_v / valor_bruto_total
            else:
                desc_percentual_decimal = 0
            
            # --- 2. LÓGICA DE MEMÓRIA DINÂMICA (Histórico mantido 100%) ---
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

            # --- 3. MOTOR DE GRAVAÇÃO COM BUSCA POR 'TOTAIS' (AJUSTE 2) ---
            if not modo_teste:
                try:
                    aba_v_sheet = planilha_mestre.worksheet("VENDAS")
                    
                    # 🔍 Localiza a linha "TOTAIS" para empurrar ela para baixo
                    try:
                        celula_totais = aba_v_sheet.find("TOTAIS")
                        indice_insercao = celula_totais.row
                    except:
                        indice_insercao = len(aba_v_sheet.col_values(2)) + 1
                    
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
                        cod_prod, nome_prod, "", qtd_v, val_v, desc_percentual_decimal, 
                        "", t_liq, "", "", metodo, 
                        eh_parc, n_p, val_a_vista, val_parc, entrada, 
                        saldo_dev, dt_prox, status, f_atraso
                    ]
                    
                    # 🚀 INSERÇÃO QUE EMPURRA O TOTAIS
                    aba_v_sheet.insert_row(linha_nova, index=indice_insercao, value_input_option='USER_ENTERED')
                    
                    st.cache_resource.clear()
                    st.success(f"✅ Venda gravada! A linha TOTAIS agora está na {indice_insercao + 1}")
                except Exception as erro:
                    st.error(f"❌ Erro Planilha: {erro}")
            
            # --- 4. RECIBO (SEU CÓDIGO ORIGINAL COMPLETO) ---
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

# ==========================================
# --- ABA 2: FINANCEIRO ---
# ==========================================
with aba_financeiro:
    def limpar_v(v):
        if pd.isna(v) or v == "": return 0.0
        return pd.to_numeric(str(v).replace('R$', '').replace('.', '').replace(',', '.').strip(), errors='coerce') or 0.0

    st.markdown("### 📈 Resumo Geral Sweet Home Enxovais")
    try:
        divida_total_vendas = df_vendas_hist['SALDO DEVEDOR'].apply(limpar_v).sum()
        total_recebido_fin = df_financeiro['VALOR_PAGO'].apply(limpar_v).sum()
        saldo_rua = divida_total_vendas - total_recebido_fin

        c1, c2, c3 = st.columns(3)
        c1.metric("Dívida Total (Vendas)", f"R$ {divida_total_vendas:,.2f}")
        c2.metric("Total Recebido (Abatimentos)", f"R$ {total_recebido_fin:,.2f}")
        c3.metric("Saldo Líquido na Rua", f"R$ {saldo_rua:,.2f}", delta="- Pendente", delta_color="inverse")
    except: st.warning("Aguardando dados para calcular o resumo.")

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
                if valor_pgto > 0 and c_escolhida != "Selecione...":
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
                                div_l = row['S_NUM']
                                if saldo_disponivel >= div_l:
                                    aba_v_sheet.update_acell(f"U{linha_excel}", 0)
                                    aba_v_sheet.update_acell(f"W{linha_excel}", "Pago")
                                    aba_v_sheet.update_acell(f"V{linha_excel}", "")
                                    saldo_disponivel -= div_l
                                else:
                                    aba_v_sheet.update_acell(f"U{linha_excel}", div_l - saldo_disponivel)
                                    saldo_disponivel = 0
                            
                            aba_f = planilha_mestre.worksheet("FINANCEIRO")
                            prox_f = len(aba_f.col_values(1)) + 1
                            linha_nova_f = [datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), cod_c, nome_c, 0, valor_pgto, "PAGO", f"{meio_pgto}: {obs_pgto}"]
                            aba_f.update(f"A{prox_f}", [linha_nova_f], value_input_option='USER_ENTERED')
                            st.success(f"✅ R$ {valor_pgto:.2f} abatido da conta de {nome_c}!")
                            st.cache_resource.clear() 
                        except Exception as e: st.error(f"Erro: {e}")

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
            pagos_f = df_financeiro[df_financeiro['CÓD. CLIENTE'].astype(str) == id_cliente]['VALOR_PAGO'].apply(limpar_v).sum() if not df_financeiro.empty else 0
            saldo_final_c = div_u - pagos_f

            st.info(f"📋 Ficha de: **{selecao_c}**")
            m1, m2, m3 = st.columns(3)
            m1.metric("Dívida Histórica", f"R$ {div_u:,.2f}"); m2.metric("Total Pago Recente", f"R$ {pagos_f:,.2f}")
            if saldo_final_c > 0.01:
                m3.metric("Saldo Real a Pagar", f"R$ {saldo_final_c:,.2f}", delta="- Pendente", delta_color="inverse")
                tel = banco_de_clientes.get(id_cliente, {}).get('fone', "")
                texto_zap = f"Olá {nome_cliente}! 🏠 Passando da *Sweet Home Enxovais* para atualizar seu extrato: saldo de *R$ {saldo_final_c:.2f}*. 😊"
                st.link_button("📲 Lembrar via WhatsApp", f"https://wa.me/55{tel}?text={urllib.parse.quote(texto_zap)}", use_container_width=True)
            else: m3.success("✅ CLIENTE EM DIA")
            st.divider()
            st.write("#### ⏳ Histórico Localizado na Aba Vendas")
            st.dataframe(v_hist[['DATA DA VENDA', 'PRODUTO', 'TOTAL R$', 'SALDO DEVEDOR', 'STATUS']], use_container_width=True, hide_index=True)

# ==========================================
# --- ABA 3: ESTOQUE ---
# ==========================================
with aba_estoque:
    st.subheader("📦 Inventário e Controle de Entradas")
    
    # --- 1. CADASTRAR NOVO PRODUTO ---
    with st.expander("➕ Cadastrar Novo Produto", expanded=False):
        with st.form("form_novo_produto", clear_on_submit=True):
            st.markdown("Preencha os dados básicos. Fórmulas da planilha farão o resto!")
            c1, c2 = st.columns([1, 2])
            n_cod = c1.text_input("Cód. Produto (Ex: TOA-01)")
            n_nome = c2.text_input("Nome do Produto")
            
            c3, c4, c5 = st.columns(3)
            n_qtd = c3.number_input("Qtd Inicial", 0)
            n_custo = c4.number_input("Custo Unit (R$)", 0.0)
            n_venda = c5.number_input("Valor Venda (R$)", 0.0)
            
            n_min = st.number_input("Quantidade Mínima", value=3)
            
            if st.form_submit_button("Salvar Produto 📦"):
                if n_cod and n_nome and not modo_teste:
                    try:
                        aba_inv = planilha_mestre.worksheet("INVENTÁRIO")
                        prox_inv = len(aba_inv.col_values(1)) + 1
                        linha_p = [n_cod.strip(), n_nome.strip(), n_qtd, n_custo, "", n_min, 0, "", n_venda, datetime.now().strftime("%d/%m/%Y"), ""]
                        aba_inv.update(f"A{prox_inv}", [linha_p], value_input_option='USER_ENTERED')
                        st.success(f"✅ Produto '{n_nome}' cadastrado!")
                        st.cache_resource.clear()
                    except Exception as e: 
                        st.error(f"Erro: {e}")

    st.divider()

    # --- 2. EXIBIÇÃO E BUSCA INTELIGENTE ---
    if not df_full_inv.empty:
        df_est = df_full_inv.copy()
        
        # Alerta de Estoque Baixo (Mantido)
        df_est['QUANTIDADE'] = pd.to_numeric(df_est['QUANTIDADE'], errors='coerce')
        baixo = df_est[df_est['QUANTIDADE'] <= 3]
        if not baixo.empty:
            st.warning(f"🚨 Atenção: {len(baixo)} produto(s) com estoque baixo!")
            with st.expander("👀 Ver produtos"): 
                st.dataframe(baixo[['NOME DO PRODUTO', 'QUANTIDADE']], hide_index=True)
        
        st.markdown("### 🔍 Buscar Produtos")
        # Texto atualizado para a Bia saber que pode usar o código agora
        busca = st.text_input("Localize pelo NOME, CÓDIGO ou DATA...")
        
        if busca:
            # A mágica do "OU" (|): Procuramos o termo nas 3 colunas principais
            filtro = (
                df_est['NOME DO PRODUTO'].astype(str).str.contains(busca, case=False, na=False) | 
                df_est['CÓD. PRÓDUTO'].astype(str).str.contains(busca, case=False, na=False) | 
                df_est['ÚLTIMA ENTRADA'].astype(str).str.contains(busca, case=False, na=False)
            )
            df_est = df_est[filtro]
            
        st.markdown("### 📋 Tabela de Estoque Atualizada")
        st.dataframe(df_est, use_container_width=True, hide_index=True)

# ==========================================
# --- ABA 4: CLIENTES ---
# ==========================================
with aba_clientes:
    st.subheader("👥 Gestão de Clientes")
    
    if not df_clientes_full.empty:
        # --- 🚨 PARTE 1: RADAR DE INCOMPLETOS ---
        # Olhamos para a Coluna 7 (oitava coluna) onde fica o 'Incompleto'
        try:
            # Filtramos quem é "Incompleto" na 8ª coluna (índice 7)
            mask_incompletos = df_clientes_full.iloc[:, 7].str.strip() == "Incompleto"
            incompletos = df_clientes_full[mask_incompletos]
            
            if not incompletos.empty:
                st.warning(f"🚨 Radar: {len(incompletos)} cadastro(s) aguardando conclusão!")
                with st.expander("📝 Detalhes dos Pendentes"):
                    st.dataframe(incompletos, use_container_width=True, hide_index=True)
            else:
                st.success("✨ Tudo em dia! Todos os clientes estão com cadastro completo.")
        except:
            st.info("Status de cadastro não identificado nesta planilha.")

        st.divider()

        # --- 📋 PARTE 2: CARTEIRA TOTAL (AQUI APARECE TODO MUNDO!) ---
        st.markdown("### 🗂️ Carteira Total de Clientes")
        
        # Campo de busca para não precisar rolar a lista toda
        busca_cli = st.text_input("🔍 Buscar cliente na lista total (por nome ou código):")
        
        df_mostrar = df_clientes_full.copy()
        if busca_cli:
            # Busca no Nome (Col 1) ou Código (Col 0)
            filtro = (df_mostrar.iloc[:, 1].str.contains(busca_cli, case=False, na=False) | 
                      df_mostrar.iloc[:, 0].str.contains(busca_cli, case=False, na=False))
            df_mostrar = df_mostrar[filtro]
        
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
        
    else:
        st.info("Nenhum cliente encontrado na planilha.")







