#include <iostream>
#include <vector>
#include <string>
#include <assert.h>

using namespace std;

int main() {
    vector<pair<int, int>> dadosDeTeste = {{10, 5}, {0, 0}, {-1, 1}};

    for (auto a : dadosDeTeste) {
        int resultadoOrig = original(a.first, a.second);
        int resultadoTrad = traduzido(a.first, a.second);

        assert(resultadoOrig == resultadoTrad);
    }

    return 0;
}