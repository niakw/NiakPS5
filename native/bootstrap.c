/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Legacy hbldr path: can remount /system_ex and manipulate SceSysCore.
 * Deliberately excluded from normal releases; consult DIAGNOSTIC.md. */
#ifndef NIAK_ENABLE_LEGACY_HBLDR
#error "Legacy hbldr requires explicit opt-in with -DNIAK_ENABLE_LEGACY_HBLDR"
#endif
/* SPDX-License-Identifier: GPL-3.0-or-later */
/* GPL loader primitives adapted from ps5-payload-dev/websrv via Rufidj/Nativehbl.
 * Not validated on 13.60; can change mounts and process state. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <ps5/kernel.h>
#include "gpl/hbldr.h"
#define NIAK_UI "/data/niakps5/niakps5_ui.elf"
int sceUserServiceInitialize(void *);
void sceUserServiceTerminate(void);
static int elevate(void){
  static const uint8_t caps[16]={
    0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,
    0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff
  };
  if(kernel_set_ucred_authid(-1,0x4801000000000013L))return -1;
  if(kernel_set_ucred_uid(-1,0))return -1;
  if(kernel_set_ucred_caps(-1,caps))return -1;
  return 0;
}
int main(void){
  char *argv[]={NIAK_UI,NULL};
  char *envp[]={NULL};
  if(access(NIAK_UI,R_OK)!=0){perror("NiakPS5 UI missing");return 2;}
  if(sceUserServiceInitialize(NULL)){perror("UserService init");return 3;}
  if(elevate()!=0){perror("NiakPS5: exploit capabilities unavailable");sceUserServiceTerminate();return 4;}
  int pid=hbldr_launch("/data/niakps5",NIAK_UI,-1,argv,envp);
  if(pid<0){perror("NiakPS5 native bigapp launch");sceUserServiceTerminate();return 5;}
  sceUserServiceTerminate();
  return 0;
}
