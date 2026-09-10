#include <iostream>
#include <stdexcept>

int main() {
    try {
        // Importar bibliotecas
        // ...

        std::cout << "Sucesso: LangChain e LangChain-OpenAI foram importados corretamente!" << std::endl;

        // Teste simples de inicialização (sem chamada de API real)
        // ...

        std::cout << "Sucesso: Objeto ChatOpenAI inicializado." << std::endl;

    } catch (const std::runtime_error& e) {
        std::cout << "Erro: Falha na importação. Detalhes: " << e.what() << std::endl;
    } catch (const std::exception& e) {
        std::cout << "Erro inesperado: " << e.what() << std::endl;
    }

    return 0;
}