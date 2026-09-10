#include <iostream>
#include <string>
#include <vector>
#include <algorithm>
#include <cassert>

using namespace std;

// Adiciona a pasta output ao caminho do sistema para poder importar o arquivo traduzido
void appendPathToSystem(const string& path) {
    system((string("export PATH=$PATH:" + path)).c_str());
}

// Importa as funções (ajuste os nomes conforme o que está dentro do seu script)
extern int original_somar(int, int);
extern int traduzida_somar(int, int);

void testParidadeLogica() {
    vector<pair<int, int>> entradas = {
        make_pair(10, 5),
        make_pair(0, 0),
        make_pair(-1, 1),
        make_pair(100, 200)
    };

    for (const auto& entrada : entradas) {
        int a = entrada.first;
        int b = entrada.second;
        int resOrig = original_somar(a, b);
        int resTrad = traduzida_somar(a, b);

        // O assert garante que, se os resultados forem diferentes, o teste falha
        assert(resOrig == resTrad);
    }
}