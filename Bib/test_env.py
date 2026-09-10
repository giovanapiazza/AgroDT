try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    
    print("Sucesso: LangChain e LangChain-OpenAI foram importados corretamente!")
    
    # Teste simples de inicialização (sem chamada de API real)
    llm = ChatOpenAI(model="gpt-4o", api_key="test_key")
    print("Sucesso: Objeto ChatOpenAI inicializado.")

except ImportError as e:
    print(f"Erro: Falha na importação. Detalhes: {e}")
except Exception as e:
    print(f"Erro inesperado: {e}")
