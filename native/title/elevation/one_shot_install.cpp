// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded one-shot self-install of NiakPS5's OWN bundled PLDmgr ELF.
// The GUI remains sandboxed if the existing local elfldr cannot elevate it.
#include "one_shot_install.hpp"
#include "elevation.hpp"
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

#if defined(__PROSPERO__)
namespace {
constexpr const char *kSlot="/data/pldmgr/payloads/niakps5";
constexpr const char *kSource="/app0/tools/niakps5/niakps5.elf";
constexpr const char *kSourceJson="/app0/tools/niakps5/niakps5.elf.json";
constexpr const char *kDestination="/data/pldmgr/payloads/niakps5/niakps5.elf";
constexpr const char *kDestinationJson="/data/pldmgr/payloads/niakps5/niakps5.elf.json";
constexpr const char *kAutoload="/data/pldmgr/autoload.txt";

bool regular(const char *path,std::size_t cap,std::size_t *size=nullptr) {
    struct stat st{};
    if(lstat(path,&st)!=0 || !S_ISREG(st.st_mode) ||
       st.st_size<=0 || std::uint64_t(st.st_size)>cap)return false;
    if(size)*size=static_cast<std::size_t>(st.st_size);
    return true;
}
bool same_file(const char *source,const char *target) {
    std::size_t a=0,b=0;
    if(!regular(source,20u*1024u*1024u,&a) ||
       !regular(target,20u*1024u*1024u,&b) || a!=b)return false;
    FILE *left=std::fopen(source,"rb"),*right=std::fopen(target,"rb");
    if(!left||!right) {
        if(left)std::fclose(left);
        if(right)std::fclose(right);
        return false;
    }
    char x[8192],y[8192];bool equal=true;
    std::size_t remaining=a;
    while(remaining) {
        const std::size_t n=remaining<sizeof(x)?remaining:sizeof(x);
        if(std::fread(x,1,n,left)!=n || std::fread(y,1,n,right)!=n ||
           std::memcmp(x,y,n)!=0){equal=false;break;}
        remaining-=n;
    }
    std::fclose(left);std::fclose(right);
    return equal;
}
bool atomic_copy(const char *source,const char *target,int mode) {
    std::size_t size=0;
    if(!regular(source,20u*1024u*1024u,&size))return false;
    FILE *in=std::fopen(source,"rb");
    if(!in)return false;
    char temp[192];
    const int n=std::snprintf(temp,sizeof(temp),"%s/.niak-install-XXXXXX",kSlot);
    if(n<1 || n>=int(sizeof(temp))){std::fclose(in);return false;}
    const int fd=mkstemp(temp);
    if(fd<0){std::fclose(in);return false;}
    bool ok=true;char buffer[8192];std::size_t left=size;
    while(ok&&left) {
        const std::size_t bytes=left<sizeof(buffer)?left:sizeof(buffer);
        if(std::fread(buffer,1,bytes,in)!=bytes){ok=false;break;}
        std::size_t offset=0;
        while(offset<bytes) {
            const ssize_t wrote=write(fd,buffer+offset,bytes-offset);
            if(wrote<0&&errno==EINTR)continue;
            if(wrote<=0){ok=false;break;}
            offset+=static_cast<std::size_t>(wrote);
        }
        left-=bytes;
    }
    if(std::fclose(in)!=0)ok=false;
    if(ok && (fchmod(fd,mode)!=0 || fsync(fd)!=0))ok=false;
    if(close(fd)!=0)ok=false;
    if(ok)ok=rename(temp,target)==0;
    if(!ok)unlink(temp);
    return ok;
}
bool validate_bundle() {
    std::size_t size=0;
    if(!regular(kSource,20u*1024u*1024u,&size) || size<1024 ||
       !regular(kSourceJson,32768))return false;
    FILE *elf=std::fopen(kSource,"rb");
    if(!elf)return false;
    unsigned char magic[5]={};
    const bool correct=std::fread(magic,1,sizeof(magic),elf)==sizeof(magic) &&
        magic[0]==0x7f && magic[1]=='E' && magic[2]=='L' &&
        magic[3]=='F' && magic[4]==2;
    std::fclose(elf);
    return correct;
}
bool has_autoload_entry(const std::string &text) {
    std::size_t start=0;
    while(start<text.size()) {
        const auto end=text.find('\n',start);
        const auto size=(end==std::string::npos?text.size():end)-start;
        std::string line=text.substr(start,size);
        while(!line.empty()&&(line.back()=='\r'||line.back()==' '))line.pop_back();
        const auto first=line.find_first_not_of(" \t");
        if(first!=std::string::npos)line.erase(0,first);
        if(line=="niakps5.elf" || line==kDestination)return true;
        if(end==std::string::npos)break;
        start=end+1;
    }
    return false;
}
// Strict read-only check: the FTP installer owns PLDmgr configuration.
// A GUI launch, including one with temporary filesystem privilege, must
// NEVER rewrite the user's existing autoload list or silently append itself.
bool configure_autoload() {
    struct stat st{};
    if(lstat(kAutoload,&st)!=0 || !S_ISREG(st.st_mode) ||
       st.st_size<0 || st.st_size>3500)return false;
    FILE *in=std::fopen(kAutoload,"rb");
    if(!in)return false;
    std::string config;
    char buffer[1024];std::size_t n=0;
    while((n=std::fread(buffer,1,sizeof(buffer),in))>0)
        config.append(buffer,n);
    const int read_error=std::ferror(in);
    std::fclose(in);
    // No fallback creation: report pending PLDmgr setup and keep UI alive.
    return !read_error && config.find('\\0')==std::string::npos &&
           has_autoload_entry(config);
}

} // namespace
#endif

int niak::bootstrap_own_payload() noexcept {
#if defined(__PROSPERO__)
    if(!validate_bundle())return -2;
    // Mirror Encore's one-shot safety contract: a failed helper must never
    // leave this long-lived graphical process with partly changed credentials.
    // On an ambiguous rollback, terminating is safer than continuing in UI.
    const uid_t uid_before=getuid(),euid_before=geteuid();
    const gid_t gid_before=getgid(),egid_before=getegid();
    const elevation::Status granted=
        elevation::request(elevation::Capability::filesystem);
    const bool changed_on_failure=granted!=elevation::Status::ok &&
        (getuid()!=uid_before || geteuid()!=euid_before ||
         getgid()!=gid_before || getegid()!=egid_before);
    if(granted==elevation::Status::rollback_failed || changed_on_failure)
        std::_Exit(125);
    if(granted!=elevation::Status::ok)return -1;
    // Grant is not enough: prove that the specific managed destination exists
    // and perform only fixed-path own-slot atomic writes. No arbitrary paths.
    struct stat st{};
    if(lstat("/data/pldmgr/payloads",&st)!=0 || !S_ISDIR(st.st_mode))
        return -2;
    if(mkdir(kSlot,0755)!=0 && errno!=EEXIST)return -2;
    if(lstat(kSlot,&st)!=0 || !S_ISDIR(st.st_mode))return -2;
    const bool elf_current=same_file(kSource,kDestination);
    const bool json_current=same_file(kSourceJson,kDestinationJson);
    if(!elf_current && !atomic_copy(kSource,kDestination,0755))return -2;
    if(!json_current && !atomic_copy(kSourceJson,kDestinationJson,0644))return -2;
    if(!configure_autoload())return -2;
    return (elf_current && json_current)?0:1;
#else
    return -1;  // Host preview cannot elevate or modify host folders.
#endif
}
