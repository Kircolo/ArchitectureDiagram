#include "encoder.h"
#include "bitwriter.h"
#include "file_storage.h"

int encode_file(void) {
    return bitwriter_put() + storage_read();
}
