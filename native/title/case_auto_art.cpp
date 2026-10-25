// SPDX-License-Identifier: GPL-3.0-or-later
// Automatic, bounded, private cover hydration. App is usable offline.
// The rendering thread enqueues only; HTTPS, JPEG decoding and PNG cache
// writes all happen on one background worker. PNG appears on next launch.
#include "niak/case_auto_art.hpp"
#if defined(__PROSPERO__)
#include "niak/daily_runtime.hpp"
#include "niak/case_texture_scale.hpp"
#include "niak/lodepng.h"
#include <webp/encode.h>
#include <webp/decode.h>
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
#include <sys/stat.h>
#include <unistd.h>
#include <unordered_map>
#include <vector>

namespace {
constexpr const char *ROOT="/download0/niak-case-";
constexpr const char *INDEX_SOURCES[]={
    "/app0/assets/niak-launchbox-cases.tsv",
    "/data/homebrew/PPSA99386/assets/niak-launchbox-cases.tsv"};
constexpr std::size_t kMaxQueued=512;
struct SourceStamp {
 std::uint64_t size=0,mtime=0,ctime=0,inode=0;
 bool present=false;
 bool operator==(const SourceStamp &x)const{
   return size==x.size && mtime==x.mtime && ctime==x.ctime &&
          inode==x.inode && present==x.present;
 }
};
std::array<SourceStamp,2> index_stamps(){
 std::array<SourceStamp,2> result{};
 for(std::size_t i=0;i<result.size();++i){
   struct stat st{};
   if(::stat(INDEX_SOURCES[i],&st)!=0 || !S_ISREG(st.st_mode))
     continue;
   result[i]={static_cast<std::uint64_t>(st.st_size),
      static_cast<std::uint64_t>(st.st_mtime),
      static_cast<std::uint64_t>(st.st_ctime),
      static_cast<std::uint64_t>(st.st_ino),true};
 }
 return result;
}
using ArtSlots=std::array<std::vector<std::string>,7>;
struct Task {
 std::string id,side;
 unsigned generation=0,attempt=0,index_attempt=0;
 std::chrono::steady_clock::time_point retry_at{};
};
bool transient_network_failure(int error){
 return (error<0 && error!=-100 && error!=-103 && error!=-200) ||
        error==408 || error==429 || (error>=500 && error<=599);
}
struct State {
 std::mutex mutex;
 std::condition_variable cv;
 std::deque<Task> tasks;
 std::deque<Task> retries;
 std::set<std::string> seen;
 bool started=false;
 std::atomic<unsigned> generation{0};
 std::string selected;
 std::atomic<unsigned> indexed{0},queued{0},completed{0},
     network_failed{0},decode_failed{0},write_failed{0},unmatched{0};
 std::atomic<int> last_network_error{0},last_network_stage{0};
 std::atomic<unsigned> requests{0}, exhausted{0};
 std::array<std::atomic<unsigned>,7> side_completed{};
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
 return std::string(ROOT)+task.id+"-"+task.side+".webp";
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
 if(!complete || raw.size()<20 ||
    std::memcmp(raw.data(),"RIFF",4)!=0 ||
    std::memcmp(raw.data()+8,"WEBP",4)!=0)return false;
 int iw=0,ih=0;
 if(!WebPGetInfo(raw.data(),raw.size(),&iw,&ih) ||
    iw<16||ih<20||iw>2048||ih>1536||
    std::uint64_t(iw)*std::uint64_t(ih)>2500000u)return false;
 // A complete decode prevents corrupt or truncated WebP from acquiring
 // authoritative cache status and hiding an otherwise valid fallback.
 std::vector<unsigned char> pixels(std::size_t(iw)*ih*4u);
 return WebPDecodeRGBAInto(raw.data(),raw.size(),pixels.data(),
                          pixels.size(),iw*4)!=nullptr;
}
std::unordered_map<std::string,ArtSlots> read_index(){
 std::unordered_map<std::string,ArtSlots> index;
 // The packaged LaunchBox index must remain authoritative after a PS5
 // update. An old private FTP overlay may add/replace valid media per side,
 // but missing fields must NEVER hide a newer packaged entry.
 for(const char *source:INDEX_SOURCES) {
 FILE *f=std::fopen(source,"rb");
 if(!f)continue;
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
   bool usable=false;
   for(const auto &part:parts)usable|=!part.empty();
   if(!usable)continue;
   auto &current=index[columns[0]];
   for(std::size_t i=0;i<current.size();++i) {
     // Keep newly shipped official metadata first; a private FTP re-index
     // contributes missing candidates instead of replacing better ones.
     for(const auto &candidate:parts[i]) {
       if(current[i].size()>=12)break;
       if(std::find(current[i].begin(),current[i].end(),candidate)
          ==current[i].end())current[i].push_back(candidate);
     }
   }
 }
 std::fclose(f);
 }
 return index;
}
bool convert_webp(const std::vector<std::uint8_t>& bytes,
                 const std::string& source,const std::string& side,
                 std::vector<unsigned char>& output){
 // Eden accepts full retail scans before resizing them for its cache.
 if(bytes.size()<33 || bytes.size()>16u*1024u*1024u)return false;
 unsigned w=0,h=0;
 std::vector<unsigned char> pixels;
 // Trust the verified image signature, not only LaunchBox's filename
 // extension. Regional entries can point to a differently encoded CDN blob.
 const bool jpeg=bytes[0]==0xff && bytes[1]==0xd8 && bytes[2]==0xff;
 const bool png=std::memcmp(bytes.data(),"\x89PNG\r\n\x1a\n",8)==0;
 if(!jpeg && !png)return false;
 if(jpeg){
   int jw=0,jh=0,ch=0;
   if(!stbi_info_from_memory(bytes.data(),int(bytes.size()),&jw,&jh,&ch) ||
      jw<16 || jh<20 || jw>4096 || jh>4096 ||
      std::uint64_t(jw)*std::uint64_t(jh)>3840u*2160u)return false;
   stbi_uc *raw=stbi_load_from_memory(bytes.data(),int(bytes.size()),
                                      &jw,&jh,&ch,4);
   if(!raw)return false;
   w=unsigned(jw);h=unsigned(jh);
   pixels.assign(raw,raw+std::size_t(w)*h*4u);
   stbi_image_free(raw);
 } else {
   const unsigned iw=(unsigned(bytes[16])<<24)|(unsigned(bytes[17])<<16)|
                      (unsigned(bytes[18])<<8)|bytes[19];
   const unsigned ih=(unsigned(bytes[20])<<24)|(unsigned(bytes[21])<<16)|
                      (unsigned(bytes[22])<<8)|bytes[23];
   if(iw<16||ih<20||iw>4096||ih>4096||
      std::uint64_t(iw)*ih>3840u*2160u)return false;
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
 // WebP quality 80; it does not imply an 80% saving for every picture.
 // RGBA preserves transparency in spine and other eligible artwork.
 std::uint8_t *encoded=nullptr;
 const std::size_t size=WebPEncodeRGBA(pixels.data(),int(w),int(h),
                                       int(w*4u),80.f,&encoded);
 if(!encoded||size==0)return false;
 if(size>3u*1024u*1024u){WebPFree(encoded);return false;}
 output.assign(encoded,encoded+size);
 WebPFree(encoded);
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
          const std::vector<unsigned char>& webp){
 const std::string path=cache_path(task);
 const std::string marker=path+".source";
 // Stage both files BEFORE invalidating the current cache entry.
 // A new PNG must never be advertised by an obsolete .source marker.
 const std::string staged_png=path+".pending";
 const std::string staged_source=marker+".pending";
 if(!write_atomic(staged_png,webp.data(),webp.size()))return false;
 if(!write_atomic(staged_source,
       reinterpret_cast<const unsigned char*>(name.data()),name.size())){
   (void)std::remove(staged_png.c_str());
   return false;
 }
 (void)std::remove(marker.c_str());
 if(std::rename(staged_png.c_str(),path.c_str())!=0){
   (void)std::remove(staged_png.c_str());
   (void)std::remove(staged_source.c_str());
   return false;
 }
 if(std::rename(staged_source.c_str(),marker.c_str())!=0){
   // A PNG without committed provenance is never reusable.
   (void)std::remove(path.c_str());
   (void)std::remove(staged_source.c_str());
   return false;
 }
 return true;
}
void queue_retry(State &s,Task task,bool waiting_for_index=false){
 // Keep HTTPS failures tightly bounded. Delayed /app0 or FTP metadata may
 // appear several minutes after boot; that path needs a separate, bounded
 // LOCAL retry budget without issuing a single additional network request.
 unsigned &attempt=waiting_for_index?task.index_attempt:task.attempt;
 const unsigned max_attempts=waiting_for_index?5u:2u;
 if(attempt>=max_attempts){++s.exhausted;return;}
 ++attempt;
 const unsigned seconds=waiting_for_index?
     (attempt==1?20u:attempt==2?60u:attempt==3?120u:
      attempt==4?240u:360u):
     (attempt==1?20u:60u);
 task.retry_at=std::chrono::steady_clock::now()+
     std::chrono::seconds(seconds);
 std::lock_guard<std::mutex> guard(s.mutex);
 if(task.generation!=s.generation)return;
 s.retries.push_back(std::move(task));
 s.queued.store(static_cast<unsigned>(s.tasks.size()+s.retries.size()));
}
void work(){
 std::unordered_map<std::string,ArtSlots> index;
 std::array<SourceStamp,2> loaded_stamps{};
 bool index_loaded=false;
 unsigned indexed_attempt=0,media_generation=~0u;
 bool official_front_ready=false,official_back_ready=false;
 State &s=state();
 for(;;){
   Task task;
   {
     std::unique_lock<std::mutex> lock(s.mutex);
     // Selected-game downloads have priority over due retries.
     for(;;){
       if(!s.tasks.empty()){
         task=std::move(s.tasks.front());s.tasks.pop_front();
         s.queued.store(static_cast<unsigned>(s.tasks.size()+s.retries.size()));
         break;
       }
       if(s.retries.empty()){
         if(s.selected.empty()){s.cv.wait(lock);continue;}
         // All attempts can expire before FTP mounts a new metadata index.
         // Check ONLY two local file stamps every 30 s while a title stays
         // focused. No HTTPS request is made unless the index truly changes.
         const std::string watched_title=s.selected;
         const unsigned watched_epoch=s.generation.load();
         const auto wake=s.cv.wait_for(lock,std::chrono::seconds(30));
         if(wake==std::cv_status::timeout &&
            s.tasks.empty() && s.retries.empty() &&
            s.selected==watched_title &&
            s.generation.load()==watched_epoch) {
           lock.unlock();
           const auto current=index_stamps();
           lock.lock();
           if(s.tasks.empty() && s.retries.empty() &&
              s.selected==watched_title &&
              s.generation.load()==watched_epoch &&
              current!=loaded_stamps) {
             // A new or replaced LaunchBox index can add missing faces.
             // Revisit just this game; existing provenance-checked WebP
             // caches prevent redundant transfers and image decoding.
             s.seen.clear();
             for(const char *side:{"spine","hero","shot1","shot2",
                                   "back","front"}) {
               s.seen.insert(watched_title+"-"+side);
               Task pending{};
               pending.id=watched_title;
               pending.side=side;
               pending.generation=watched_epoch;
               if(pending.side=="front"||pending.side=="back")
                 s.tasks.push_front(std::move(pending));
               else s.tasks.push_back(std::move(pending));
             }
             s.queued.store(static_cast<unsigned>(s.tasks.size()));
           }
         }
         continue;
       }
       const auto next=std::min_element(s.retries.begin(),s.retries.end(),
           [](const Task &a,const Task &b){return a.retry_at<b.retry_at;});
       const auto due=next->retry_at;
       if(std::chrono::steady_clock::now()>=due){
         task=std::move(*next);s.retries.erase(next);
         s.queued.store(static_cast<unsigned>(s.tasks.size()+s.retries.size()));
         break;
       }
       s.cv.wait_until(lock,due);
     }
   }
   {
     std::lock_guard<std::mutex> guard(s.mutex);
     if(task.generation!=s.generation || task.id!=s.selected)
       continue; // navigation cancelled old work
   }
   if(media_generation!=task.generation){
     media_generation=task.generation;
     official_front_ready=false;
     official_back_ready=false;
   }
   // The screenshots are unused with an official BACK. A missing FRONT
   // can still use the hero artwork even when the BACK is already present.
   // Skip hero only once both official faces are ready.
   if(((task.side=="shot1"||task.side=="shot2") &&
        official_back_ready) ||
      (task.side=="hero" && official_front_ready &&
        official_back_ready) ||
      (task.side=="logo" && official_front_ready))
     continue;
   // Compare two cheap local file stamps. Avoid parsing thousands of
   // LaunchBox rows during rapid navigation. Reparse when FTP replaces the
   // metadata, when a sandbox mount appears, or on empty-index retries.
   const auto current_stamps=index_stamps();
   if(!index_loaded || current_stamps!=loaded_stamps ||
      (index.empty() && task.index_attempt>indexed_attempt)){
     index=read_index();
     loaded_stamps=current_stamps;
     index_loaded=true;
     indexed_attempt=task.index_attempt;
     s.indexed.store(static_cast<unsigned>(index.size()));
   }
   if(index.empty()){queue_retry(s,std::move(task),true);continue;}
   const auto found=index.find(task.id);
   if(found==index.end()){
     if(task.index_attempt==0)++s.unmatched;
     queue_retry(s,std::move(task),true);
     continue;
   }
   const int field=side_index(task.side);
   if(field<0)continue;
   const auto &candidates=found->second[std::size_t(field)];
   if(candidates.empty()){
     if(task.index_attempt==0)++s.unmatched;
     queue_retry(s,std::move(task),true);
     continue;
   }
   const std::string target=cache_path(task);
   // The fallback image can remain usable offline, but must not permanently
   // mask a newly available higher-priority PS5/PS4 Box - Back. Upgrade it
   // when possible, only trying entries BEFORE its cached source.
   std::size_t reusable_rank=candidates.size();
   for(std::size_t i=0;i<candidates.size();++i)
     if(existing(target,candidates[i])){reusable_rank=i;break;}
   if(reusable_rank==0){
     if(task.side=="front")official_front_ready=true;
     if(task.side=="back")official_back_ready=true;
     continue;
   }
   // Region/server variation: a missing FR image can fall back to EU or
   // another validated image, without ever trusting an arbitrary URL.
   // Up to three CDN candidates per side, ordered by the LaunchBox index:
   // PS5 -> PS4 -> PC for backs, hero, gameplay, game title and logos.
   // Fronts remain native console retail scans only.
   const unsigned candidate_limit=3u;
   unsigned examined=0;
   bool transient_failure=false,downloaded=false;
   for(const std::string &source:candidates) {
     {
       std::lock_guard<std::mutex> guard(s.mutex);
       if(task.generation!=s.generation || task.id!=s.selected)break;
     }
     if(examined>=candidate_limit || examined>=reusable_rank)break;
     ++examined;
     // No lifetime cap: seven sides with at most three passes each.
     ++s.requests;
     std::vector<std::uint8_t> bytes;
     int error=0,stage=0;
     const bool fetched=niak_fetch_launchbox_asset_ex(
         source.c_str(),bytes,&error,&stage,&s.generation,task.generation);
     // A request may finish after the player has moved to another game.
     // Never attribute its HTTP failure or decode result to the new focus.
     {
       std::lock_guard<std::mutex> guard(s.mutex);
       if(task.generation!=s.generation || task.id!=s.selected)break;
       if(!fetched){
         s.last_network_error.store(error);
         s.last_network_stage.store(stage);
         transient_failure|=transient_network_failure(error);
         ++s.network_failed;
       }
     }
     if(!fetched)continue;
     // Keep the latest CDN failure visible until another game is selected.
     // A successful front must not hide an HTTPS failure on the back.
     std::vector<unsigned char> webp;
     const bool converted=convert_webp(bytes,source,task.side,webp);
     {
       std::lock_guard<std::mutex> guard(s.mutex);
       if(task.generation!=s.generation || task.id!=s.selected)break;
       if(!converted)++s.decode_failed;
     }
     if(!converted)continue;
     const bool saved=save(task,source,webp);
     {
       std::lock_guard<std::mutex> guard(s.mutex);
       if(task.generation!=s.generation || task.id!=s.selected)break;
       if(saved){
         ++s.side_completed[static_cast<std::size_t>(field)];
         ++s.completed;
         downloaded=true;
         if(task.side=="front")official_front_ready=true;
         if(task.side=="back")official_back_ready=true;
       }else{
         ++s.write_failed;
       }
     }
     if(saved)break;
     std::this_thread::sleep_for(std::chrono::milliseconds(150));
   }
   // Retain a valid lower-priority back while online promotion fails.
   // Never discard an existing PC/PS4 fallback just because the PS5 CDN
   // cannot be reached. Reattempt transient failures with bounded backoff.
   if(!downloaded && reusable_rank<candidates.size()){
     if(task.side=="front")official_front_ready=true;
     if(task.side=="back")official_back_ready=true;
   }
   // Retry temporary HTTP failures without changing selection. Navigation
   // cancels both pending and delayed work for the previous title.
   if(!downloaded && transient_failure)
     queue_retry(s,std::move(task));
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
   if(s.selected!=title_id ||
      s.seen.size()>=kMaxQueued || !s.seen.insert(name).second)return;
   // Scan the entire library without starving all remaining box fronts:
   // missing official front/back scans outrank extra logo/screenshots. New
   // titles also get a chance when the user navigates a long game shelf.
   if(std::strcmp(side,"front")==0||std::strcmp(side,"back")==0)
     s.tasks.push_front({title_id,side,s.generation});
   else s.tasks.push_back({title_id,side,s.generation});
   s.queued.store(static_cast<unsigned>(s.tasks.size()+s.retries.size()));
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

void niak_select_case_art(const char *title_id) {
#if defined(__PROSPERO__)
 State &s=state();
 const bool valid=valid_id(title_id);
 {
   std::lock_guard<std::mutex> lock(s.mutex);
   if(s.selected==(valid?std::string(title_id):std::string{}))return;
   s.selected=valid?title_id:"";
   ++s.generation;
   s.last_network_error.store(0);
   s.last_network_stage.store(0);
   // Only ONE game's CDN requests belong in the queue. A request already
   // in flight can finish; no next title ever waits behind the whole shelf.
   s.tasks.clear();
   s.retries.clear();
   s.queued.store(0);
   s.seen.clear();
 }
 s.cv.notify_one();
 if(!valid)return;
 // Eden Encore: originals first; scenery only for reconstruction. push_front
 // for front/back means both actual faces precede the optional resources.
 // No redundant clear logo is printed on the case or above the title.
 // Avoid its CDN request, decode, and GPU allocation.
 for(const char *side:{"spine","hero","shot1","shot2","back","front"})
   niak_queue_auto_case_art(title_id,side);
#else
 (void)title_id;
#endif
}

NiakArtDownloadStatus niak_case_art_download_status(){
#if defined(__PROSPERO__)
 const State &s=state();
 NiakArtDownloadStatus result{
     s.indexed.load(),s.queued.load(),s.completed.load(),
     s.network_failed.load(),s.decode_failed.load(),
     s.write_failed.load(),s.unmatched.load(),
     s.last_network_error.load(),s.requests.load(),s.exhausted.load(),
     s.last_network_stage.load()};
 for(std::size_t i=0;i<result.sides_completed.size();++i)
     result.sides_completed[i]=s.side_completed[i].load();
 return result;
#else
 return {};
#endif
}
