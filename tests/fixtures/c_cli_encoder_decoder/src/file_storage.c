#include "file_storage.h"

int storage_read(void) {
    fopen("input.bin", "rb");
    fread(0, 1, 0, 0);
    return 0;
}

int storage_write(void) {
    fopen("output.bin", "wb");
    fwrite(0, 1, 0, 0);
    return 0;
}
