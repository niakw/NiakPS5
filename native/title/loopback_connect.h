/* SPDX-License-Identifier: GPL-3.0-or-later
 * Bounded TCP connection to the already known loopback service.
 * Native UI/catalogue initialization must not wait for OS TCP retries.
 */
#ifndef NIAK_LOOPBACK_CONNECT_H
#define NIAK_LOOPBACK_CONNECT_H
#include <stddef.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/time.h>

/* Returns 0 on a connected descriptor, -1 otherwise.
 * Restores original blocking mode in ALL paths after F_SETFL succeeds. */
static inline int niak_connect_bounded(int fd,
                                        const struct sockaddr *address,
                                        socklen_t address_size,
                                        unsigned timeout_ms) {
    const int original=fcntl(fd,F_GETFL,0);
    if(original<0 || fcntl(fd,F_SETFL,original|O_NONBLOCK)<0)return -1;
    int result=connect(fd,address,address_size);
    if(result!=0 && (errno==EINPROGRESS || errno==EWOULDBLOCK)) {
        fd_set writable;
        FD_ZERO(&writable);FD_SET(fd,&writable);
        struct timeval deadline={ (long)(timeout_ms/1000u),
                                  (long)((timeout_ms%1000u)*1000u) };
        const int ready=select(fd+1,NULL,&writable,NULL,&deadline);
        int so_error=0;
        socklen_t error_len=sizeof(so_error);
        result=(ready>0 && FD_ISSET(fd,&writable) &&
                getsockopt(fd,SOL_SOCKET,SO_ERROR,
                           &so_error,&error_len)==0 && so_error==0)?0:-1;
    }
    const int restore=fcntl(fd,F_SETFL,original);
    return result==0 && restore==0?0:-1;
}
#endif
