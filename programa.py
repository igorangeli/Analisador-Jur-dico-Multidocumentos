import streamlit as st
import fitz
import json
import google.generativeai as genai

st.set_page_config(page_title="Analisador Jurídico", layout="wide")

# PROMPT OTIMIZADO PARA ISOLAR OS VALORES FINANCEIROS DE FORMA RÍGIDA
PROMPT_BASE = """
Você é um analista jurídico especializado e extremamente meticuloso.
Analise os dados extraídos do PDF enviado e preencha o relatório solicitado.

CRITÉRIOS DE DISTINÇÃO CRÍTICOS (NÃO CONFUNDA OS CAMPOS):
1. valor_garantia: É o valor TOTAL e atual da garantia do juízo (seja por depósito judicial, penhora ou o somatório de seguros).
2. valor_primeira_apolice: Deve conter EXCLUSIVAMENTE o valor da primeira apólice emitida/anexada no processo. Se houver apenas uma apólice, o valor pode coincidir, mas se houver renovações, substituições ou aditamentos com valores novos, diferencie-os e pegue apenas o valor histórico da PRIMEIRA apólice.

Nunca invente informações. Caso não encontre um dado, preencha: [Não localizado nos documentos anexos]

Retorne SOMENTE JSON válido, sem markdown e sem caixas de código:
{{
  "numero_cumprimento_sentenca":"",
  "fase_cumprimento":"",
  "juiz":"",
  "camara_preventa":"",
  "relator_prevento":"",
  "autores":"",
  "manifestacao_caixa":"",
  "conteudo_manifestacao_caixa":"",
  "forma_garantia":"",
  "valor_garantia":"[Identifique o valor total garantido. Se for apólice, cite o valor total atualizado]",
  "valor_primeira_apolice":"[Busque no histórico e isole estritamente o valor da 1ª apólice apresentada. Não repita o valor atual se ele mudou nas renovações]",
  "alvaras":"",
  "materia_impugnada":""
}}

REGRAS ADICIONAIS:
* Seja rígido na linha do tempo das apólices: olhe as datas dos documentos para garantir que o "valor_primeira_apolice" refira-se ao documento mais antigo de garantia.
"""

PALAVRAS_CHAVE = [
    "cumprimento", "sentença", "cumprimento de sentença", "apólice",
    "seguro garantia", "depósito judicial", "manifestação", "caixa econômica",
    "caixa", "impugnação", "impugnada", "alvará", "levantamento",
    "garantia", "autor", "relator", "juiz"
]

def extrair_pdf_otimizado(pdf_file):
    texto = ""
    pdf_bytes = pdf_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for i, pagina in enumerate(doc):
        conteudo_pagina = pagina.get_text()
        if not conteudo_pagina:
            continue
            
        texto_lower = conteudo_pagina.lower()

        if i < 3 or any(p in texto_lower for p in PALAVRAS_CHAVE):
            texto += f"\n\n=== PÁGINA {i+1} ===\n"
            texto += conteudo_pagina

    doc.close()
    return texto

def exibir_campos_processo(dados, sufixo_chave):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📋 Informações Estruturais")
        st.text_area("Nº Cumprimento de Sentença", value=str(dados.get("numero_cumprimento_sentenca", "")), height=100, key=f"num_{sufixo_chave}")
        st.text_area("Fase de Cumprimento", value=str(dados.get("fase_cumprimento", "")), height=100, key=f"fase_{sufixo_chave}")
        st.text_area("Juiz", value=str(dados.get("juiz", "")), height=100, key=f"juiz_{sufixo_chave}")
        st.text_area("Câmara Preventa", value=str(dados.get("camara_preventa", "")), height=100, key=f"camara_{sufixo_chave}")
        st.text_area("Relator Prevento", value=str(dados.get("relator_prevento", "")), height=100, key=f"relator_{sufixo_chave}")
        st.text_area("Autores", value=str(dados.get("autores", "")), height=100, key=f"autores_{sufixo_chave}")

    with col2:
        st.markdown("### 💰 Informações Financeiras e de Mérito")
        st.text_area("Manifestação da Caixa", value=str(dados.get("manifestacao_caixa", "")), height=100, key=f"caixa_{sufixo_chave}")
        st.text_area("Conteúdo Manifestação Caixa", value=str(dados.get("conteudo_manifestacao_caixa", "")), height=100, key=f"cont_caixa_{sufixo_chave}")
        st.text_area("Forma de Garantia", value=str(dados.get("forma_garantia", "")), height=100, key=f"forma_{sufixo_chave}")
        st.text_area("Valor da Garantia", value=str(dados.get("valor_garantia", "")), height=100, key=f"val_gar_{sufixo_chave}")
        st.text_area("Valor da Primeira Apólice", value=str(dados.get("valor_primeira_apolice", "")), height=100, key=f"val_apol_{sufixo_chave}")
        st.text_area("Alvarás", value=str(dados.get("alvaras", "")), height=100, key=f"alvaras_{sufixo_chave}")
        st.text_area("Matéria Impugnada", value=str(dados.get("materia_impugnada", "")), height=100, key=f"materia_{sufixo_chave}")

st.title("📄 Analisador Jurídico Multidocumentos")

api_key = st.text_input("Chave Gemini", type="password")

# Inicialização de variáveis de controle de estado
if "resultados_analise" not in st.session_state:
    st.session_state.resultados_analise = {}

if "id_uploader" not in st.session_state:
    st.session_state.id_uploader = 0

# Mecanismo de chave dinâmica para limpar a seleção de PDFs quando necessário
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

# LÓGICA DE LIMPEZA COMPLETA (ZERA RESULTADOS E LIMPA O SELETOR DE ARQUIVOS)
if botao_limpar:
    st.session_state.resultados_analise = {}
    st.session_state.id_uploader += 1
    st.rerun()

# LÓGICA DA ANÁLISE DOS DOCUMENTOS
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
        status_texto.info(f"Processando arquivo {idx+1} de {len(arquivos)}: {arq.name}")
        
        texto_processo = extrair_pdf_otimizado(arq)
        
        if not texto_processo.strip():
            st.session_state.resultados_analise[arq.name] = {"erro": "Nenhum texto relevante encontrado."}
            continue
            
        try:
            resposta = model.generate_content(
                [PROMPT_BASE, texto_processo],
                generation_config={"temperature": 0, "response_mime_type": "application/json"}
            )
            
            conteudo = resposta.text.strip()
            dados_json = json.loads(conteudo)
            st.session_state.resultados_analise[arq.name] = dados_json
            
        except Exception as e:
            st.session_state.resultados_analise[arq.name] = {"erro": f"Erro na análise: {str(e)}"}
            
        progresso.progress((idx + 1) / len(arquivos))
        
    status_texto.success("Todos os processos foram analisados com sucesso!")

# APRESENTAÇÃO DOS RESULTADOS NAS ABAS
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