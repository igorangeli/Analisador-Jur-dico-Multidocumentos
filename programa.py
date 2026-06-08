import streamlit as st
import json
import google.generativeai as genai

st.set_page_config(page_title="Analisador Jurídico v1.1", layout="wide")

# PROMPT MODIFICADO PARA RETORNAR RESPOSTA E FOLHA PARA CADA CAMPO
PROMPT_BASE = """
Você é um analista jurídico especializado e extremamente meticuloso.
Analise o PDF enviado na íntegra e preencha o relatório solicitado.

CRITÉRIOS DE DISTINÇÃO CRÍTICOS (NÃO CONFUNDA OS CAMPOS):
1. valor_garantia: É o valor TOTAL e atual da garantia do juízo (seja por depósito judicial, penhora ou o somatório de seguros).
2. valor_primeira_apolice: Deve conter EXCLUSIVAMENTE o valor da primeira apólice emitida/anexada no processo. Se houver apenas uma apólice, o valor pode coincidir, mas se houver renovações, substituições ou aditamentos com valores novos, diferencie-os e pegue apenas o valor histórico da PRIMEIRA apólice.

CRITÉRIO DE INDICAÇÃO DE FOLHAS:
Para cada campo solicitado, você deve extrair o dado ("resposta") e indicar EXTREMAMENTE DE FORMA PRECISA o número da folha/página do PDF onde esse dado foi encontrado ("folha"). Se não encontrar a informação, preencha a resposta com "[Não localizado nos documentos anexos]" e a folha com "N/A".

Retorne SOMENTE JSON válido, sem markdown e sem caixas de código seguindo estritamente a estrutura abaixo:
{{
  "numero_cumprimento_sentenca": {{ "resposta": "", "folha": "" }},
  "fase_cumprimento": {{ "resposta": "", "folha": "" }},
  "juiz": {{ "resposta": "", "folha": "" }},
  "camara_preventa": {{ "resposta": "", "folha": "" }},
  "relator_prevento": {{ "resposta": "", "folha": "" }},
  "autores": {{ "resposta": "", "folha": "" }},
  "manifestacao_caixa": {{ "resposta": "", "folha": "" }},
  "conteudo_manifestacao_caixa": {{ "resposta": "", "folha": "" }},
  "forma_garantia": {{ "resposta": "", "folha": "" }},
  "valor_garantia": {{ "resposta": "[Valor total garantido. Se for apólice, cite o valor total atualizado]", "folha": "" }},
  "valor_primeira_apolice": {{ "resposta": "[Busque no histórico e isole estritamente o valor da 1ª apólice apresentada]", "folha": "" }},
  "rejeicao_apolice_garantia": {{ "resposta": "[SIM ou NÃO se há decisão rejeitando expressamente a apólice]", "folha": "" }},
  "folha_rejeicao_apolice": {{ "resposta": "[Se a resposta anterior for SIM, indique o número da folha da decisão. Se for NÃO, preencha com N/A]", "folha": "" }},
  "data_sentenca_conhecimento": {{ "resposta": "[Data da sentença do processo de conhecimento]", "folha": "" }},
  "alvaras": {{ "resposta": "[Informações sobre alvarás]", "folha": "" }},
  "materia_impugnada": {{ "resposta": "", "folha": "" }}
}}

REGRAS ADICIONAIS:
* Seja rígido na linha do tempo das apólices: olhe as datas dos documentos para garantir que o "valor_primeira_apolice" refira-se ao documento mais antigo de garantia.
* Seja extremamente preciso ao indicar os números das folhas de onde cada informação foi extraída.
"""

def criar_campo_com_folha(label, chave_dado, dados, sufixo_chave, height=100):
    """Função utilitária para renderizar o campo de resposta e o campo da folha lado a lado"""
    objeto_campo = dados.get(chave_dado, {})
    # Tratamento caso o modelo traga string em vez de dicionário por falha de formato
    if isinstance(objeto_campo, str):
        val_resposta = objeto_campo
        val_folha = "N/A"
    else:
        val_resposta = str(objeto_campo.get("resposta", ""))
        val_folha = str(objeto_campo.get("folha", ""))

    c_resp, c_fl = st.columns([3, 1])
    with c_resp:
        st.text_area(label, value=val_resposta, height=height, key=f"resp_{chave_dado}_{sufixo_chave}")
    with c_fl:
        st.text_area("Folha", value=val_folha, height=height, key=f"fl_{chave_dado}_{sufixo_chave}")

def exibir_campos_processo(dados, sufixo_chave):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📋 Informações Estruturais")
        criar_campo_com_folha("Nº Cumprimento de Sentença", "numero_cumprimento_sentenca", dados, sufixo_chave)
        criar_campo_com_folha("Fase de Cumprimento", "fase_cumprimento", dados, sufixo_chave)
        criar_campo_com_folha("Juiz", "juiz", dados, sufixo_chave)
        criar_campo_com_folha("Câmara Preventa", "camara_preventa", dados, sufixo_chave)
        criar_campo_com_folha("Relator Prevento", "relator_prevento", dados, sufixo_chave)
        criar_campo_com_folha("Autores", "autores", dados, sufixo_chave)
        criar_campo_com_folha("Data da Sentença (Conhecimento)", "data_sentenca_conhecimento", dados, sufixo_chave)

    with col2:
        st.markdown("### 💰 Informações Financeiras e de Mérito")
        criar_campo_com_folha("Manifestação da Caixa", "manifestacao_caixa", dados, sufixo_chave)
        criar_campo_com_folha("Conteúdo Manifestação Caixa", "conteudo_manifestacao_caixa", dados, sufixo_chave)
        criar_campo_com_folha("Forma de Garantia", "forma_garantia", dados, sufixo_chave)
        criar_campo_com_folha("Valor da Garantia", "valor_garantia", dados, sufixo_chave)
        criar_campo_com_folha("Valor da Primeira Apólice", "valor_primeira_apolice", dados, sufixo_chave)
        
        st.markdown("---")
        criar_campo_com_folha("Decisão Rejeita Apólice?", "rejeicao_apolice_garantia", dados, sufixo_chave, height=70)
        criar_campo_com_folha("Folha da Rejeição da Apólice (Obs)", "folha_rejeicao_apolice", dados, sufixo_chave, height=70)
        st.markdown("---")
        
        criar_campo_com_folha("Alvarás", "alvaras", dados, sufixo_chave)
        criar_campo_com_folha("Matéria Impugnada", "materia_impugnada", dados, sufixo_chave)

st.title("📄 Analisador de Documento SFH - RAMO 66")

api_key = st.text_input("Chave Gemini", type="password")

if "resultados_analise" not in st.session_state:
    st.session_state.resultados_analise = {}

if "id_uploader" not in st.session_state:
    st.session_state.id_uploader = 0

arquivos = st.file_uploader(
    "Selecione os PDFs dos Processos",
    type=["pdf"],
    accept_multiple_files=True,
    key=f"upload_pdfs_{st.session_state.id_uploader}"
)

btn_col1, btn_col2 = st.columns([1, 5])

with btn_col1:
    botao_analisar = st.button("Analisar Processos", type="primary")

with btn_col2:
    botao_limpar = st.button("🧹 Limpar Tudo")

if botao_limpar:
    st.session_state.resultados_analise = {}
    st.session_state.id_uploader += 1
    st.rerun()

if botao_analisar:

    if not api_key:
        st.error("Informe a chave Gemini.")
        st.stop()

    if not arquivos:
        st.error("Envie ao menos um PDF.")
        st.stop()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-pro")
    
    st.session_state.resultados_analise = {}
    
    progresso = st.progress(0)
    status_texto = st.empty()
    
    for idx, arq in enumerate(arquivos):
        status_texto.info(f"Analisando PDF completo {idx+1} de {len(arquivos)}: {arq.name}")
        
        try:
            arq.seek(0)
            pdf_bytes = arq.read()
            
            documento_pdf = {
                "mime_type": "application/pdf",
                "data": pdf_bytes
            }
            
            resposta = model.generate_content(
                [PROMPT_BASE, documento_pdf],
                generation_config={"temperature": 0, "response_mime_type": "application/json"}
            )
            
            conteudo = resposta.text.strip()
            dados_json = json.loads(conteudo)
            st.session_state.resultados_analise[arq.name] = dados_json
            
        except Exception as e:
            st.session_state.resultados_analise[arq.name] = {"erro": f"Erro no processamento direto do PDF: {str(e)}"}
            
        progresso.progress((idx + 1) / len(arquivos))
        
    status_texto.success("Todos os processos foram analisados com sucesso!")

if st.session_state.resultados_analise:
    st.write("---")
    st.subheader("📌 Resultados da Análise por Arquivo")
    
    nomes_abas = list(st.session_state.resultados_analise.keys())
    abas = st.tabs(nomes_abas)
    
    for i, nome_da_aba in enumerate(nomes_abas):
        with abas[i]:
            dados_do_arquivo = st.session_state.resultados_analise[nome_da_aba]
            
            if "erro" in dados_do_arquivo:
                st.error(dados_do_arquivo["erro"])
            else:
                st.caption(f"Arquivo origem: {nome_da_aba}")
                exibir_campos_processo(dados_do_arquivo, sufixo_chave=str(i))
                
                st.download_button(
                    label=f"📥 Baixar JSON deste processo",
                    data=json.dumps(dados_do_arquivo, ensure_ascii=False, indent=2),
                    file_name=f"analise_{nome_da_aba}.json",
                    mime="application/json",
                    key=f"dl_{i}"
                )
