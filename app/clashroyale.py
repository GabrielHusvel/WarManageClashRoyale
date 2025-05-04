# -*- coding: utf-8 -*-
import streamlit as st
import requests
import os
import pandas as pd
from urllib.parse import quote
from datetime import datetime
import re # Para sanitizar nomes de arquivos

# --- Configuração e Constantes ---
BASE_API_URL = "https://api.clashroyale.com/v1"
PLAYER_DATA_DIR = "dados_clas" # Diretório para salvar os CSVs dos clãs

# --- Funções Auxiliares ---

def sanitize_filename(tag):
    """Remove caracteres inválidos para nomes de arquivo da tag."""
    sanitized = re.sub(r'^#', '', tag)
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', sanitized)
    return sanitized

def get_clan_csv_filename(clan_tag):
    """Gera o caminho completo para o arquivo CSV do clã."""
    if not os.path.exists(PLAYER_DATA_DIR):
        try:
            os.makedirs(PLAYER_DATA_DIR) # Cria o diretório se não existir
        except OSError as e:
            st.error(f"Erro ao criar diretório {PLAYER_DATA_DIR}: {e}")
            return None # Retorna None se não puder criar o diretório
    return os.path.join(PLAYER_DATA_DIR, f"dados_jogadores_{sanitize_filename(clan_tag)}.csv")

# --- Funções de Interação com a API ---

def get_api_headers(user_api_token=None):
    """Retorna os headers da API, priorizando o token do usuário."""
    api_token = user_api_token or os.getenv("CLASH_ROYALE_API_TOKEN")

    if not api_token:
        # Este erro será tratado antes da chamada da API principal
        return None
    return {"Authorization": f"Bearer {api_token}"}

def fetch_api_data(endpoint, user_api_token=None):
    """Função genérica para buscar dados da API."""
    headers = get_api_headers(user_api_token)
    if not headers:
        # Erro já tratado no get_api_headers ou antes da chamada
        return None

    url = f"{BASE_API_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao conectar à API Clash Royale ({url}): {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                reason = error_detail.get('reason', '')
                message = error_detail.get('message', e.response.text)
                # Mensagens específicas para erros comuns
                if e.response.status_code == 403:
                    st.error("Erro 403: Acesso Negado. Verifique se o Token da API é válido e se o IP de acesso está autorizado na sua conta de desenvolvedor Supercell.")
                elif e.response.status_code == 404:
                     st.error(f"Erro 404: Recurso não encontrado (Tag do Clã '{endpoint.split('/')[1]}' existe?).")
                else:
                    st.error(f"Detalhes do erro da API ({e.response.status_code}): {reason} - {message}")

            except requests.exceptions.JSONDecodeError:
                st.error(f"Resposta da API (não JSON): {e.response.text}")
        return None

def get_clan_members(clan_tag, user_api_token=None):
    """Busca a lista de membros do clã."""
    encoded_tag = quote(clan_tag)
    endpoint = f"clans/{encoded_tag}/members"
    data = fetch_api_data(endpoint, user_api_token)
    # Retorna a lista de membros ou uma lista vazia em caso de erro/não encontrado
    return data.get("items", []) if data else []

def get_current_river_race(clan_tag, user_api_token=None):
    """Busca dados da corrida de rio (River Race) atual do clã."""
    encoded_tag = quote(clan_tag)
    endpoint = f"clans/{encoded_tag}/currentriverrace"
    # Retorna os dados da corrida ou um dicionário vazio em caso de erro/não encontrado
    return fetch_api_data(endpoint, user_api_token) or {}

# --- Funções de Manipulação do CSV ---

def load_player_data(clan_tag):
    """Carrega os dados dos jogadores (tag, nome, telefone) do CSV específico do clã."""
    filepath = get_clan_csv_filename(clan_tag)
    if not filepath: return pd.DataFrame(columns=['tag', 'name', 'phone']) # Se não pôde criar diretório

    try:
        df = pd.read_csv(filepath, dtype={'tag': str, 'name': str, 'phone': str})
        # Garante que as colunas essenciais existam
        for col in ['tag', 'name', 'phone']:
            if col not in df.columns:
                df[col] = ''
        df = df.fillna('') # Preenche quaisquer NaNs restantes
        return df[['tag', 'name', 'phone']] # Retorna apenas as colunas esperadas
    except FileNotFoundError:
        return pd.DataFrame(columns=['tag', 'name', 'phone'])
    except pd.errors.EmptyDataError: # Trata caso de arquivo CSV vazio
         return pd.DataFrame(columns=['tag', 'name', 'phone'])
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo CSV ({filepath}): {e}")
        return pd.DataFrame(columns=['tag', 'name', 'phone'])

def save_player_data(df, clan_tag):
    """Salva o DataFrame com dados dos jogadores no CSV específico do clã."""
    filepath = get_clan_csv_filename(clan_tag)
    if not filepath: return # Não tenta salvar se o caminho não pôde ser gerado

    try:
        # Garante que as colunas existam antes de tentar salvar
        df_to_save = pd.DataFrame(columns=['tag', 'name', 'phone'])
        # Copia dados das colunas existentes no df original
        for col in ['tag', 'name', 'phone']:
             if col in df.columns:
                 df_to_save[col] = df[col]
             else:
                 df_to_save[col] = '' # Cria coluna vazia se não existir

        df_to_save = df_to_save[['tag', 'name', 'phone']].fillna('')
        df_to_save.to_csv(filepath, index=False, encoding='utf-8')
    except Exception as e:
        st.error(f"Erro ao salvar o arquivo CSV ({filepath}): {e}")

# --- Funções para Download ---

@st.cache_data # Cacheia o resultado para evitar reprocessamento
def convert_df_to_csv(df):
    """Converte um DataFrame para CSV em formato de bytes para download."""
    return df.to_csv(index=False, encoding='utf-8').encode('utf-8')

# --- Interface Streamlit ---

st.set_page_config(layout="wide", page_title="Painel Clash Royale")
st.title("📊 Painel do Clã - Clash Royale v3")

# --- Barra Lateral (Sidebar) para Configurações ---
st.sidebar.header("⚙️ Configurações")

# Input para a Chave da API (visível e claro)
st.sidebar.subheader("🔑 Chave da API")
if 'api_token' not in st.session_state:
    st.session_state.api_token = os.getenv("CLASH_ROYALE_API_TOKEN", "")

# Usamos st.text_input normal, mas dentro da sidebar
api_token_input = st.sidebar.text_input(
    "Chave da API Clash Royale",
    type="password", # Mascara a entrada
    value=st.session_state.api_token,
    help="Insira sua chave da API oficial do Clash Royale. Pode também ser definida pela variável de ambiente CLASH_ROYALE_API_TOKEN."
)
# Atualiza o session_state sempre que o input mudar
st.session_state.api_token = api_token_input

# Feedback visual sobre o token
if st.session_state.api_token:
    st.sidebar.success("Token da API carregado.")
else:
    st.sidebar.warning("Token da API não definido.")

# Input para a Tag do Clã
st.sidebar.subheader("🏷️ Clã")
if 'clan_tag' not in st.session_state:
    st.session_state.clan_tag = "" # Começa vazio para forçar input

clan_tag_input = st.sidebar.text_input(
    "Tag do Clã",
    value=st.session_state.clan_tag,
    placeholder="#QPYL8YCV",
    help="Insira a tag do clã começando com '#'."
).strip().upper()
st.session_state.clan_tag = clan_tag_input

# Botão principal para buscar dados
if st.sidebar.button("🔍 Buscar Dados do Clã", use_container_width=True):
    # Validações ANTES de chamar a API
    if not st.session_state.api_token:
        st.sidebar.error("Erro: Chave da API não fornecida.")
        st.stop() # Interrompe se não há token

    if not st.session_state.clan_tag or not st.session_state.clan_tag.startswith("#"):
        st.sidebar.warning("Erro: Tag de Clã inválida. Deve começar com '#'.")
        st.stop() # Interrompe se a tag é inválida

    # Se passou nas validações, busca os dados
    clan_tag = st.session_state.clan_tag
    user_api_token = st.session_state.api_token

    with st.spinner(f"Buscando dados para o clã {clan_tag}..."):
        members_data = get_clan_members(clan_tag, user_api_token)
        river_race_data = get_current_river_race(clan_tag, user_api_token)

    # Verifica se a busca de membros foi bem-sucedida (essencial)
    if members_data is None: # A função retorna None em caso de erro de API
        st.error(f"Falha ao buscar dados do clã {clan_tag}. Verifique o log de erros acima.")
        # Limpa dados antigos para evitar confusão
        st.session_state.pop('members_data', None)
        st.session_state.pop('river_race_data', None)
        st.session_state.pop('data_loaded_for_tag', None)
        st.stop()
    elif not members_data: # Retornou lista vazia (pode ser clã vazio ou erro não capturado)
         st.warning(f"Nenhum membro encontrado para o clã {clan_tag}. A tag está correta?")
         # Permite continuar, mas pode não haver muito o que mostrar
         st.session_state.members_data = []
         st.session_state.river_race_data = river_race_data or {} # Usa dados da guerra se houver
         st.session_state.data_loaded_for_tag = clan_tag
    else:
        # Sucesso! Armazena os dados no session_state
        st.session_state.members_data = members_data
        st.session_state.river_race_data = river_race_data or {} # Garante que seja um dict
        st.session_state.data_loaded_for_tag = clan_tag
        st.success(f"Dados do clã {clan_tag} carregados!")
        # Limpa o estado do editor de dados para forçar recarga com novos dados/clã
        editor_key = f"data_editor_phones_{sanitize_filename(clan_tag)}"
        if editor_key in st.session_state:
            del st.session_state[editor_key]
        st.rerun() # Força o rerun para atualizar a interface principal


# --- Exibição dos Dados (se carregados para uma tag específica) ---
if 'data_loaded_for_tag' in st.session_state and st.session_state.data_loaded_for_tag:
    current_tag = st.session_state.data_loaded_for_tag
    st.header(f"Dados do Clã: {current_tag}")

    # Recupera dados do session_state (já validados na busca)
    members_data = st.session_state.get('members_data', [])
    river_race_data = st.session_state.get('river_race_data', {})

    # Cria DataFrame de membros (se houver dados)
    members_df = pd.DataFrame(members_data) if members_data else pd.DataFrame()
    current_member_tags = set(members_df['tag']) if not members_df.empty else set()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"👥 Membros ({len(members_data)})")
        if not members_df.empty:
            members_df_display = members_df[[
                'tag', 'name', 'expLevel', 'trophies', 'clanRank',
                'role', 'donations', 'lastSeen'
            ]].rename(columns={
                'tag': 'Tag', 'name': 'Nome', 'expLevel': 'Nível XP', 'trophies': 'Troféus',
                'clanRank': 'Rank Clã', 'role': 'Cargo', 'donations': 'Doações', 'lastSeen': 'Visto por Último'
            })
            st.dataframe(members_df_display, hide_index=True, use_container_width=True)
        else:
            st.info("Nenhum membro para exibir.")

        # --- Gerenciamento de Telefones ---
        st.subheader("📞 Gerenciar Telefones")
        if not members_df.empty:
            current_members_info = members_df[['tag', 'name']].copy()
            player_phone_data_loaded = load_player_data(current_tag)

            # Mescla para exibir todos os membros atuais e seus telefones salvos
            combined_data = pd.merge(
                current_members_info,
                player_phone_data_loaded[['tag', 'phone']],
                on='tag',
                how='left'
            ).fillna({'phone': '', 'name': ''}) # Garante preenchimento

            editor_key = f"data_editor_phones_{sanitize_filename(current_tag)}"
            edited_data = st.data_editor(
                combined_data[['tag', 'name', 'phone']],
                column_config={
                    "tag": st.column_config.TextColumn("Tag", disabled=True, width="medium"),
                    "name": st.column_config.TextColumn("Nome", disabled=True, width="large"),
                    "phone": st.column_config.TextColumn("Telefone (Editável)", width="medium"),
                },
                hide_index=True,
                key=editor_key,
                use_container_width=True,
                num_rows="dynamic"
            )

            # Salva se houver alteração nos telefones
            original_phones = combined_data[['tag', 'phone']].fillna('')
            edited_phones = edited_data[['tag', 'phone']].fillna('')
            if not original_phones.equals(edited_phones):
                save_player_data(edited_data, current_tag)
                st.success(f"Telefones atualizados para o clã {current_tag}!")
                # Não precisa de rerun aqui, o editor já reflete a mudança visualmente
                # Mas atualizamos os dados carregados em memória se necessário em outro lugar
                st.session_state[f'player_phone_data_{current_tag}'] = edited_data
        else:
            st.info("Carregue os dados de um clã para gerenciar telefones.")


    with col2:
        # --- Dados da River Race ---
        st.subheader("⚔️ Corrida de Rio Atual")
        if river_race_data and river_race_data.get("state") != "notInWar":
            state = river_race_data.get("state", "N/A")
            st.write(f"**Estado:** {state.replace('_', ' ').title()}") # Formata o estado

            clan_info = river_race_data.get("clan")
            if clan_info:
                st.metric("Fama do Clã", clan_info.get('fame', 0))
                participants = clan_info.get('participants', [])
                st.metric("Participantes na Guerra", len(participants))
                st.metric("Pontos de Reparo", clan_info.get('repairPoints', 0))

                if participants:
                    participants_df = pd.DataFrame(participants)
                    # Garante que a coluna exista, mesmo que vazia na API
                    if 'decksUsedToday' not in participants_df.columns:
                        participants_df['decksUsedToday'] = 0 # Assume 0 se não vier da API

                    participants_df_display = participants_df[[
                        'tag', 'name', 'fame', 'repairPoints', 'boatAttacks', 'decksUsedToday'
                    ]].rename(columns={
                        'tag': 'Tag', 'name': 'Nome', 'fame': 'Fama', 'repairPoints': 'Reparos',
                        'boatAttacks': 'Ataques Barco', 'decksUsedToday': 'Decks Usados Hoje'
                    })
                    st.dataframe(participants_df_display, hide_index=True, use_container_width=True)

                    # --- Verificação de Ataques Pendentes (com validação de membro) ---
                    st.subheader("🚨 Verificar Ataques Pendentes")
                    st.info("Verifica jogadores com 0 'Decks Usados Hoje' que **ainda estão no clã**.")

                    if st.button("Gerar Lista de Pendentes", use_container_width=True):
                        # Filtra participantes com 0 decks usados HOJE
                        missing_attack_today = participants_df[participants_df['decksUsedToday'] == 0]

                        if not missing_attack_today.empty:
                            missing_tags_today = set(missing_attack_today['tag'])

                            # *** NOVA VERIFICAÇÃO: Filtra apenas os que ainda são membros ***
                            verified_missing_tags = missing_tags_today.intersection(current_member_tags)
                            unverified_tags = missing_tags_today.difference(current_member_tags)

                            if unverified_tags:
                                # Pega nomes dos não verificados se possível
                                names_unverified = missing_attack_today[missing_attack_today['tag'].isin(unverified_tags)]['name'].tolist()
                                st.warning(f"⚠️ Jogadores com 0 decks usados hoje, mas que **não estão mais na lista de membros** (podem ter saído): {', '.join(names_unverified)}")

                            if not verified_missing_tags:
                                st.success("✅ Nenhum jogador *atual do clã* está com ataques pendentes hoje!")
                            else:
                                # Filtra o DataFrame original para incluir apenas os verificados
                                verified_missing_players_info = missing_attack_today[missing_attack_today['tag'].isin(verified_missing_tags)][['tag', 'name']].copy()

                                # Carrega os dados de telefone do CSV deste clã
                                player_phone_data = load_player_data(current_tag)

                                # Junta os faltantes (verificados) com os dados de telefone
                                missing_players_with_phones = pd.merge(
                                    verified_missing_players_info,
                                    player_phone_data[['tag', 'phone']],
                                    on='tag',
                                    how='left'
                                ).fillna({'phone': 'N/A'}) # Preenche telefone não encontrado com 'N/A'

                                # Seleciona apenas nome e telefone para o arquivo final
                                final_missing_list = missing_players_with_phones[['name', 'phone']].rename(columns={'name': 'Nome', 'phone': 'Telefone'})

                                st.write(f"Jogadores **atuais do clã** com ataques pendentes hoje ({len(final_missing_list)}):")
                                st.dataframe(final_missing_list, hide_index=True, use_container_width=True)

                                # Gera o CSV para download
                                csv_data = convert_df_to_csv(final_missing_list)
                                now = datetime.now().strftime("%Y%m%d_%H%M")
                                download_filename = f"pendentes_{sanitize_filename(current_tag)}_{now}.csv"

                                st.download_button(
                                    label="📥 Baixar Lista de Pendentes (.csv)",
                                    data=csv_data,
                                    file_name=download_filename,
                                    mime='text/csv',
                                    use_container_width=True
                                )
                        else:
                            st.success("✅ Todos os participantes da corrida utilizaram seus decks hoje!")
                else:
                    st.write("Nenhum participante encontrado na corrida atual.")
            else:
                st.write("Informações detalhadas do clã na corrida não disponíveis.")

            # Mais detalhes da corrida...
            st.markdown("---")
            st.write(f"**Índice da Semana:** {river_race_data.get('sectionIndex', 'N/A')}")
            st.write(f"**Índice do Período:** {river_race_data.get('periodIndex', 'N/A')}")
            st.write(f"**Tipo do Período:** {river_race_data.get('periodType', 'N/A')}")
            st.write(f"**Fim da Guerra/Coleta:** {river_race_data.get('warEndTime', 'N/A')}")

        else:
            st.info("O clã não está participando de uma Corrida de Rio no momento ou os dados não puderam ser carregados.")

# Mensagem inicial se nenhum clã foi carregado ainda
elif not st.session_state.get('clan_tag'):
     st.info("⬅️ Por favor, insira a Tag do Clã e a Chave da API na barra lateral e clique em 'Buscar Dados do Clã'.")
elif not st.session_state.get('api_token'):
     st.warning("⬅️ Por favor, insira a Chave da API na barra lateral para continuar.")