#include "server.h"
#include "http.h"
#include "queue.h"
#include "threadpool.h"
#include "storage.h"

int server_run(void) {
    int listener = socket(0, 0, 0);
    bind(listener, 0, 0);
    listen(listener, 16);
    accept(listener, 0, 0);
    return http_parse_request() + queue_push() + threadpool_start() + storage_write();
}
