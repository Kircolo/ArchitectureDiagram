#include "storage.h"

int storage_write(void) {
    fopen("audit.log", "ab");
    fread(0, 1, 0, 0);
    fwrite(0, 1, 0, 0);
    return 0;
}
