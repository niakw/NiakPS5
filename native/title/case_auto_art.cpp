// SPDX-License-Identifier: GPL-3.0-or-later
// Automatic, bounded, private cover hydration. App is usable offline.
// The rendering thread enqueues only; HTTPS, JPEG decoding and PNG cache
// writes all happen on one background worker. PNG appears on next launch.
#include "niak/case_auto_art.hpp"
#if defined(__PROSPERO__)
#include "niak/daily_runtime.hpp"
#include "niak/case_texture_scale.hpp"
#include "niak/lodepng.h"
#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_JPEG
#define STBI_NO_STDIO
#define STBI_NO_HDR
#define STBI_NO_LINEAR
#include "niak/stb_image.h"
#include <algorithm>
#include <atomic>
#include <array>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <unistd.h>
#include <unordered_map>
#include <vector>

namespace {
constexpr const char *ROOT="/download0/niak-case-";
constexpr std::size_t kMaxQueued=512;
using ArtSlots=std::array<std::vector<std::string>,7>;
struct Task { std::string id,side; };
struct State {
 std::mutex mutex;
 std::condition_variable cv;
 std::deque<Task> tasks;
 std::set<std::string> seen;
 bool started=false;
 std::atomic<unsigned> indexed{0},queued{0},completed{0},
     network_failed{0},decode_failed{0},write_failed{0},unmatched{0};
 std::atomic<int> last_network_error{0};
 std::atomic<unsigned> requests{0}, exhausted{0};
};
State& state(){static State *instance=new State;return *instance;}
int side_index(const std::string& side){
 const char *names[]={"front","back","spine","logo","hero","shot1","shot2"};
 for(int i=0;i<7;++i)if(side==names[i])return i;
 return -1;
}
bool valid_id(const char *id){
 if(!id || std::strlen(id)!=9)return false;
 const bool prefix=std::strncmp(id,"PPSA",4)==0 ||
                   std::strncmp(id,"CUSA",4)==0;
 if(!prefix)return false;
 for(int i=4;i<9;++i)if(id[i]<'0'||id[i]>'9')return false;
 return true;
}
bool valid_filename(const std::string& name){
 const std::size_t offset=name.rfind("r2_",0)==0?3u:0u;
 if(name.size()<offset+40 || name.size()>offset+41)return false;
 for(std::size_t i=offset;i<offset+36;++i){
   const char c=name[i];
   if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')||
        (c>='A'&&c<='F')||c=='-'))return false;
 }
 const std::string ext=name.substr(offset+36);
 return ext==".jpg" || ext==".png" || ext==".jpeg";
}
std::string cache_path(const Task& task){
 return std::string(ROOT)+task.id+"-"+task.side+".png";
}
bool existing(const std::string& path,const std::string& source){
 const std::string marker=path+".source";
 FILE *f=std::fopen(marker.c_str(),"rb");
 if(!f)return false;
 char value[90]{};
 const std::size_t size=std::fread(value,1,sizeof(value)-1,f);
 std::fclose(f);
 if(std::string(value,size)!=source)return false;
 f=std::fopen(path.c_str(),"rb");
 if(!f)return false;
 if(std::fseek(f,0,SEEK_END)!=0){std::fclose(f);return false;}
 const long length=std::ftell(f);
 if(length<33 || length>3*1024*1024 ||
    std::fseek(f,0,SEEK_SET)!=0){std::fclose(f);return false;}
 std::vector<unsigned char> raw(static_cast<std::size_t>(length));
 const bool complete=std::fread(raw.data(),1,raw.size(),f)==raw.size();
 std::fclose(f);
 if(!complete ||
    std::memcmp(raw.data(),"\x89PNG\r\n\x1a\n",8)!=0)return false;
 const unsigned iw=(unsigned(raw[16])<<24)|(unsigned(raw[17])<<16)|
                   (unsigned(raw[18])<<8)|raw[19];
 const unsigned ih=(unsigned(raw[20])<<24)|(unsigned(raw[21])<<16)|
                   (unsigned(raw[22])<<8)|raw[23];
 if(iw<16||ih<20||iw>2048||ih>1536||
    std::uint64_t(iw)*ih>2500000u)return false;
 std::vector<unsigned char> pixels;unsigned w=0,h=0;
 return lodepng::decode(pixels,w,h,raw)==0 && w==iw && h==ih &&
        pixels.size()==std::size_t(w)*h*4u;
}
std::unordered_map<std::string,ArtSlots> read_index(){
 std::unordered_map<std::string,ArtSlots> index;
 // Installed-title-specific metadata takes precedence over the generic
 // bundled catalogue (exactly like the native overview reader).
 FILE *f=std::fopen(
    "/data/homebrew/PPSA99386/assets/niak-launchbox-cases.tsv","rb");
 if(!f)f=std::fopen("/app0/assets/niak-launchbox-cases.tsv","rb");
 if(!f)return index;
 char line[8192];
 while(index.size()<50000 && std::fgets(line,sizeof(line),f)){
   if(!std::strchr(line,'\n') && !std::feof(f)){
     int ch;while((ch=std::fgetc(f))!=EOF&&ch!='\n'){}
     continue;
   }
   std::vector<std::string> columns;
   char *begin=line;
   for(char *p=line;*p && columns.size()<10;++p){
     if(*p=='\t'||*p=='\n'){
       columns.emplace_back(begin,std::size_t(p-begin));
       if(*p=='\n')break;
       begin=p+1;
     }
   }
   if(columns.size()<9 || !valid_id(columns[0].c_str()))continue;
   ArtSlots parts{};
   for(int i=0;i<7;++i) {
     const auto& col=columns[std::size_t(i+2)];
     std::size_t begin=0;
     while(begin<col.size() && parts[std::size_t(i)].size()<8) {
       const auto end=col.find(';',begin);
       const std::string candidate=col.substr(
           begin,end==std::string::npos?end:end-begin);
       const auto colon=candidate.find(':');
       if(colon!=std::string::npos) {
         const std::string filename=candidate.substr(colon+1);
         auto &sources=parts[std::size_t(i)];
         if(valid_filename(filename) &&
            std::find(sources.begin(),sources.end(),filename)==sources.end())
            sources.push_back(filename);
       }
       if(end==std::string::npos)break;
       begin=end+1;
     }
   }
   index.emplace(columns[0],std::move(parts));
 }
 std::fclose(f);
 return index;
}
bool convert_png(const std::vector<std::uint8_t>& bytes,
                 const std::string& source,const std::string& side,
                 std::vector<unsigned char>& output){
 if(bytes.size()<33 || bytes.size()>5u*1024u*1024u)return false;
 unsigned w=0,h=0;
 std::vector<unsigned char> pixels;
 const bool jpeg=source.size()>4 &&
   (source.compare(source.size()-4,4,".jpg")==0 ||
    source.compare(source.size()-5,5,".jpeg")==0);
 if(jpeg){
   int jw=0,jh=0,ch=0;
   if(!stbi_info_from_memory(bytes.data(),int(bytes.size()),&jw,&jh,&ch) ||
      jw<16 || jh<20 || jw>4096 || jh>4096 ||
      std::uint64_t(jw)*std::uint64_t(jh)>4500000u)return false;
   stbi_uc *raw=stbi_load_from_memory(bytes.data(),int(bytes.size()),
                                      &jw,&jh,&ch,4);
   if(!raw)return false;
   w=unsigned(jw);h=unsigned(jh);
   pixels.assign(raw,raw+std::size_t(w)*h*4u);
   stbi_image_free(raw);
 } else {
   if(bytes[0]!=137 || bytes[1]!=80 || bytes[2]!=78 || bytes[3]!=71)
     return false;
   const unsigned iw=(unsigned(bytes[16])<<24)|(unsigned(bytes[17])<<16)|
                      (unsigned(bytes[18])<<8)|bytes[19];
   const unsigned ih=(unsigned(bytes[20])<<24)|(unsigned(bytes[21])<<16)|
                      (unsigned(bytes[22])<<8)|bytes[23];
   if(iw<16||ih<20||iw>4096||ih>4096||
      std::uint64_t(iw)*ih>4500000u)return false;
   if(lodepng::decode(pixels,w,h,bytes)!=0||w!=iw||h!=ih)
     return false;
 }
 const float aspect=float(w)/float(h);
 const bool spine=side=="spine",logo=side=="logo";
 const bool landscape=side=="hero"||side=="shot1"||side=="shot2";
 if(spine?(h<100||aspect>0.25f):
    logo?(w<32||h<20):
    landscape?(w<320||h<180||aspect<1.15f||aspect>3.1f):
              (h<200||aspect<0.55f||aspect>0.90f))return false;
 if(!niak_scale_case_rgba(pixels,w,h,
       spine?96u:logo?768u:landscape?768u:512u,
       landscape?512u:768u))return false;
 if(lodepng::encode(output,pixels,w,h)!=0 || output.size()>3u*1024u*1024u)
    return false;
 return true;
}
bool write_atomic(const std::string &path,
                  const unsigned char *data,std::size_t size) {
 if(!data || size==0 || path.size()>180)return false;
 char temp[256];
 const int n=std::snprintf(temp,sizeof(temp),"%s.XXXXXX",path.c_str());
 if(n<=0||std::size_t(n)>=sizeof(temp))return false;
 const int fd=mkstemp(temp);
 if(fd<0)return false;
 FILE *f=fdopen(fd,"wb");
 if(!f){close(fd);std::remove(temp);return false;}
 bool ok=std::fwrite(data,1,size,f)==size;
 if(std::fflush(f)!=0)ok=false;
 if(ok && fsync(fd)!=0)ok=false;
 if(std::fclose(f)!=0)ok=false;
 if(!ok || std::rename(temp,path.c_str())!=0){
   std::remove(temp);return false;
 }
 return true;
}
bool save(const Task& task,const std::string& name,
          const std::vector<unsigned char>& png){
 const std::string path=cache_path(task);
 if(!write_atomic(path,png.data(),png.size()))return false;
 // The provenance marker is installed only AFTER its validated image.
 (void)write_atomic(path+".source",
             reinterpret_cast<const unsigned char*>(name.data()),name.size());
 return true;
}
void work(){
 const auto index=read_index();
 State &s=state();
 s.indexed.store(static_cast<unsigned>(index.size()));
 unsigned requested=0;
 for(;;){
   Task task;
   {
     std::unique_lock<std::mutex> lock(s.mutex);
     s.cv.wait(lock,[&]{return !s.tasks.empty();});
     task=std::move(s.tasks.front());s.tasks.pop_front();
   }
   const auto found=index.find(task.id);
   if(found==index.end()){++s.unmatched;continue;}
   const int field=side_index(task.side);
   if(field<0)continue;
   const auto &candidates=found->second[std::size_t(field)];
   if(candidates.empty()){++s.unmatched;continue;}
   const std::string target=cache_path(task);
   bool reusable=false;
   for(const std::string &source:candidates)
     if(existing(target,source)){reusable=true;break;}
   if(reusable)continue;
   // Region/server variation: a missing FR image can fall back to EU or
   // another validated image, without ever trusting an arbitrary URL.
   const unsigned candidate_limit=
       (task.side=="front"||task.side=="back")?3u:1u;
   unsigned examined=0;
   for(const std::string &source:candidates) {
     if(examined++>=candidate_limit)break;
     if(requested>=512u) { ++s.exhausted;break; }
     ++requested;++s.requests;
     std::vector<std::uint8_t> bytes;
     int error=0;
     if(!niak_fetch_launchbox_asset_ex(source.c_str(),bytes,&error)){
       s.last_network_error.store(error);
       ++s.network_failed;continue;
     }
     std::vector<unsigned char> png;
     if(!convert_png(bytes,source,task.side,png)){
       ++s.decode_failed;continue;
     }
     if(save(task,source,png)){++s.completed;break;}
     ++s.write_failed;
     std::this_thread::sleep_for(std::chrono::milliseconds(150));
   }
 }
}
} // namespace
#endif
void niak_queue_auto_case_art(const char *title_id,const char *side){
#if defined(__PROSPERO__)
 if(!valid_id(title_id) || !side || side_index(side)<0)return;
 State &s=state();
 const std::string name=std::string(title_id)+"-"+side;
 {
   std::lock_guard<std::mutex> lock(s.mutex);
   if(s.seen.size()>=kMaxQueued || !s.seen.insert(name).second)return;
   // Scan the entire library without starving all remaining box fronts:
   // missing official front/back scans outrank extra logo/screenshots. New
   // titles also get a chance when the user navigates a long game shelf.
   if(std::strcmp(side,"front")==0||std::strcmp(side,"back")==0)
     s.tasks.push_front({title_id,side});
   else s.tasks.push_back({title_id,side});
   ++s.queued;
   if(!s.started){
     s.started=true;
     std::thread(work).detach();
   }
 }
 s.cv.notify_one();
#else
 (void)title_id;(void)side;
#endif
}

NiakArtDownloadStatus niak_case_art_download_status(){
#if defined(__PROSPERO__)
 const State &s=state();
 return {s.indexed.load(),s.queued.load(),s.completed.load(),
         s.network_failed.load(),s.decode_failed.load(),
         s.write_failed.load(),s.unmatched.load(),
         s.last_network_error.load(),s.requests.load(),s.exhausted.load()};
#else
 return {};
#endif
}
