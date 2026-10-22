#define _POSIX_C_SOURCE 200809L
#include "../loopback_connect.h"
#include <assert.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <unistd.h>

int main(void) {
    int listener=socket(AF_INET,SOCK_STREAM,0);
    assert(listener>=0);
    struct sockaddr_in address={0};
    address.sin_family=AF_INET;
    address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    address.sin_port=0;
    assert(bind(listener,(struct sockaddr *)&address,sizeof(address))==0);
    assert(listen(listener,1)==0);
    socklen_t size=sizeof(address);
    assert(getsockname(listener,(struct sockaddr *)&address,&size)==0);
    int client=socket(AF_INET,SOCK_STREAM,0);
    assert(client>=0);
    assert(niak_connect_bounded(client,
           (const struct sockaddr *)&address,sizeof(address),100)==0);
    assert((fcntl(client,F_GETFL,0)&O_NONBLOCK)==0);
    int accepted=accept(listener,NULL,NULL);
    assert(accepted>=0);
    close(accepted);close(client);close(listener);
    // Closed listener: fail promptly and restore descriptor flags.
    client=socket(AF_INET,SOCK_STREAM,0);
    assert(client>=0);
    assert(niak_connect_bounded(client,
           (const struct sockaddr *)&address,sizeof(address),100)==-1);
    assert((fcntl(client,F_GETFL,0)&O_NONBLOCK)==0);
    close(client);
    return 0;
}
