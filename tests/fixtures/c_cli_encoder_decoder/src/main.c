#include "encoder.h"
#include "decoder.h"

int main(int argc, char **argv) {
    return argc > 1 && argv[0] != 0 ? encode_file() + decode_file() : 0;
}
