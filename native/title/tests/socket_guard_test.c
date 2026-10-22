#include "../socket_guard.h"
#include <assert.h>
#include <errno.h>
#include <unistd.h>
int main(void) {
    int fds[2]={-1,-1};
    assert(socketpair(AF_UNIX,SOCK_STREAM,0,fds)==0);
    niak_socket_guard(fds[0]);
    close(fds[1]);
    // If SIGPIPE is not suppressed, the child process dies here instead of
    // reaching the assertion (SIGPIPE default disposition is termination).
    assert(niak_socket_send(fds[0],"PING\n",5)==-1);
    assert(errno==EPIPE || errno==ECONNRESET);
    close(fds[0]);
    return 0;
}
