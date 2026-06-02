#include "threadpool.h"
#include "queue.h"

int threadpool_start(void) {
    pthread_create(0, 0, 0, 0);
    pthread_join(0, 0);
    return queue_push();
}
