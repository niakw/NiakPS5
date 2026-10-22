/* SPDX-License-Identifier: GPL-3.0-or-later
 * Protect the local title/payload TCP protocol against SIGPIPE when the
 * peer disconnects while a request or response is being sent.
 * PS5's FreeBSD socket stack supports SO_NOSIGPIPE; Linux uses MSG_NOSIGNAL.
 */
#ifndef NIAK_SOCKET_GUARD_H
#define NIAK_SOCKET_GUARD_H
#include <sys/types.h>
#include <sys/socket.h>

static inline void niak_socket_guard(int fd) {
#ifdef SO_NOSIGPIPE
    const int yes=1;
    (void)setsockopt(fd,SOL_SOCKET,SO_NOSIGPIPE,&yes,sizeof(yes));
#else
    (void)fd;
#endif
}
static inline ssize_t niak_socket_send(int fd,const void *data,size_t size) {
#ifdef MSG_NOSIGNAL
    return send(fd,data,size,MSG_NOSIGNAL);
#else
    return send(fd,data,size,0);
#endif
}
#endif
