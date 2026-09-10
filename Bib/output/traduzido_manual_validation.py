#include <iostream>
#include <vector>
#include <string>
#include <fstream>
#include <algorithm>

using namespace std;

vector<pair<int, int>> entradas = {{10, 5}, {0, 0}};

void validar() {
    for (auto a : entradas) {
        cout << "Entrada (" << a.first << "," << a.second << ") -> Orig: " << funcao_teste(a.first, a.second) << " | Trad: " << funcao_traduzida(a.first, a.second) << endl;
    }
}

int main() {
    validar();
    return 0;
}