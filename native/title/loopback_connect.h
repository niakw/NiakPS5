/* SPDX-License-Identifier: GPL-3.0-or-later
 * Bounded connection from a fresh blocking loopback TCP socket.
 * PS5 sandbox may reject fcntl(F_GETFL/F_SETFL) with EACCES (errno 13).
 * ioctl(FIONBIO) is the socket-specific alternative. Some native retail
 * sandboxes reject BOTH fcntl and ioctl with EACCES, even though local
 * socket connect is permitted. In that case try a socket-send-timeout-
 * limited blocking connect, ONLY for the exact IPv4 loopback address.
 * No remote destination, background thread, or privilege change.
 */
#ifndef NIAK_LOOPBACK_CONNECT_H
#define NIAK_LOOPBACK_CONNECT_H
#include <stddef.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>

/* stage=2: FIONBIO denied; stage=3: connect/select/socket error.
 * All callers pass a NEW, initially blocking socket. FIONBIO(0) restores
 * this state even if connect or select fails. errno is preserved on failure.
 */
static inline int niak_connect_bounded_ex(int fd,
    const struct sockaddr *address,socklen_t address_size,
    unsigned timeout_ms,int *stage) {
    if(stage)*stage=2;
    int enabled=1;
    if(ioctl(fd,FIONBIO,&enabled)!=0) {
        const int reason=errno;
        if(reason!=EACCES && reason!=EPERM && reason!=ENOTTY)
            return -1;
        if(!address || address_size<sizeof(struct sockaddr_in) ||
           address->sa_family!=AF_INET ||
           ((const struct sockaddr_in *)address)->sin_addr.s_addr!=
               htonl(INADDR_LOOPBACK)) {
            errno=EACCES;return -1;
        }
        /* The socket is freshly created and still blocking. SO_SNDTIMEO
         * is supported by the FreeBSD socket stack and also controls the
         * blocking loopback connect. Do not connect without a timeout.
         */
        struct timeval deadline={
            (time_t)(timeout_ms/1000u),
            (suseconds_t)((timeout_ms%1000u)*1000u)};
        if(setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,
                      &deadline,sizeof(deadline))!=0)return -1;
        if(stage)*stage=3;
        return connect(fd,address,address_size);
    }
    if(stage)*stage=3;
    int result=connect(fd,address,address_size);
    int error=result!=0?errno:0;
    if(result!=0 && (error==EINPROGRESS || error==EWOULDBLOCK)) {
        fd_set writable;
        FD_ZERO(&writable);FD_SET(fd,&writable);
        struct timeval deadline={ (long)(timeout_ms/1000u),
                                  (long)((timeout_ms%1000u)*1000u) };
        const int ready=select(fd+1,NULL,&writable,NULL,&deadline);
        if(ready>0 && FD_ISSET(fd,&writable)) {
            int socket_error=0;
            socklen_t error_len=sizeof(socket_error);
            if(getsockopt(fd,SOL_SOCKET,SO_ERROR,
                          &socket_error,&error_len)==0) {
                error=socket_error;
                result=socket_error==0?0:-1;
            } else {
                error=errno;result=-1;
            }
        } else {
            error=ready==0?ETIMEDOUT:errno;
            result=-1;
        }
    }
    int disabled=0;
    if(ioctl(fd,FIONBIO,&disabled)!=0) {
        if(stage)*stage=2;
        return -1; /* errno of ioctl, fail closed */
    }
    if(result!=0) {
        errno=error;
        return -1;
    }
    return 0;
}
static inline int niak_connect_bounded(int fd,
    const struct sockaddr *address,socklen_t address_size,
    unsigned timeout_ms) {
    return niak_connect_bounded_ex(fd,address,address_size,timeout_ms,NULL);
}
#endif
