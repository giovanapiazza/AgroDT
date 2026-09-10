import os
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class TradutorDeCodigo:
    def __init__(self, modelo="llama3"):
        self.llm = ChatOllama(model=modelo, temperature=0)
        self.prompt = ChatPromptTemplate.from_template("""
            Você é um engenheiro de software especialista em migração de sistemas.
            Traduza o código de {lingua_origem} para {lingua_destino}.
            Regras estritas: Retorne APENAS o código. Sem explicações ou Markdown.
            Código: {codigo}
        """)
        self.cadeia = self.prompt | self.llm | StrOutputParser()

    def traduzir(self, codigo, l_origem, l_destino):
        saida = self.cadeia.invoke({
            "codigo": codigo, 
            "lingua_origem": l_origem, 
            "lingua_destino": l_destino
        })
        # Limpeza de formatação
        return saida.replace("```python", "").replace("```cpp", "").replace("```", "").strip()
