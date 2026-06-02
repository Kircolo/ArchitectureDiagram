#include "decoder.h"
#include "bitreader.h"
#include "file_storage.h"

int decode_file(void) {
    return bitreader_get() + storage_write();
}
