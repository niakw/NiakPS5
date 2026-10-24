// SPDX-License-Identifier: GPL-3.0-or-later
// Fetches public released-PS5 media: GitHub JSON index + official PlayStation PNG.
// Network failure is never fatal; packaged wallpapers remain available.
#include "niak/daily_runtime.hpp"
// The PS5 title toolchain disables exceptions. Every field is type-checked
// before get<T>(); a failed internal assertion remains fail-closed.
#if !defined(__EXCEPTIONS) && !defined(_CPPUNWIND)
#define PICOJSON_ASSERT(x) do { if (!(x)) std::abort(); } while (0)
#endif
#include "niak/picojson.h"
#include <algorithm>
#include <cstdlib>
#include <utility>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

#if defined(__PROSPERO__)
#include "platform/ps5/console_curl.h"
#include "niak/one_shot_install.hpp"
#include <mutex>
#include <chrono>
extern "C" {
int sceNetInit();
int sceNetPoolCreate(const char*,int,int);
int sceSslInit(std::size_t);
int sceHttpInit(int,int,std::size_t);
int sceHttpCreateTemplate(int,const char*,int,int);
int sceHttpDeleteTemplate(int);
int sceHttpCreateConnectionWithURL(int,const char*,int);
int sceHttpDeleteConnection(int);
int sceHttpCreateRequestWithURL(int,int,const char*,std::uint64_t);
int sceHttpDeleteRequest(int);
int sceHttpSendRequest(int,const void*,std::size_t);
int sceHttpGetStatusCode(int,int*);
int sceHttpReadData(int,void*,std::size_t);
int sceHttpSetAutoRedirect(int,int);
int sceHttpSetResolveTimeOut(int,unsigned);
int sceHttpSetConnectTimeOut(int,unsigned);
int sceHttpSetSendTimeOut(int,unsigned);
int sceHttpSetRecvTimeOut(int,unsigned);
}
namespace {
constexpr const char *FEED="https://raw.githubusercontent.com/sharpemu/sharpemu-site/main/src/data/games.json";
constexpr const char *MEDIA="https://image.api.playstation.com/";
constexpr const char *LAUNCHBOX="https://images.launchbox-app.com/";
constexpr std::size_t MAX_FEED=5u*1024u*1024u, MAX_PNG=7u*1024u*1024u;
// The bundled GPLv3 console_curl shim uses OpenSSL and the console CA list.
// PS5 sceSsl may refuse public certificates once the GUI is elevated.
struct CurlBuffer {
 std::vector<std::uint8_t> bytes;
 std::size_t cap=0;
 bool oversized=false;
};
std::size_t curl_write(char *ptr,std::size_t size,std::size_t nmemb,void *context){
 auto &buffer=*static_cast<CurlBuffer*>(context);
 if(size && nmemb>SIZE_MAX/size){buffer.oversized=true;return 0;}
 const std::size_t n=size*nmemb;
 if(n>buffer.cap-buffer.bytes.size()){buffer.oversized=true;return 0;}
 buffer.bytes.insert(buffer.bytes.end(),
     reinterpret_cast<std::uint8_t*>(ptr),
     reinterpret_cast<std::uint8_t*>(ptr)+n);
 return n;
}
bool get_curl(const std::string &url,std::size_t limit,
              std::vector<std::uint8_t> &result,int *failure,int *stage){
 static std::once_flag started;
 static CURLcode initialized=CURLE_FAILED_INIT;
 std::call_once(started,[]{initialized=curl_global_init(CURL_GLOBAL_DEFAULT);});
 if(initialized!=CURLE_OK){
   if(failure)*failure=-10000-static_cast<int>(initialized);
   if(stage)*stage=10;
   return false;
 }
 CURL *easy=curl_easy_init();
 if(!easy){if(failure)*failure=-10002;if(stage)*stage=10;return false;}
 CurlBuffer body{};
 body.cap=limit;
 body.bytes.reserve(std::min(limit,std::size_t(1u<<20)));
 console_curl_setup(easy); // verified CA; socket nonblocking; no signals
 curl_easy_setopt(easy,CURLOPT_URL,url.c_str());
 curl_easy_setopt(easy,CURLOPT_PROTOCOLS_STR,"https");
 curl_easy_setopt(easy,CURLOPT_FOLLOWLOCATION,0L);
 curl_easy_setopt(easy,CURLOPT_HTTP_VERSION,CURL_HTTP_VERSION_1_1);
 curl_easy_setopt(easy,CURLOPT_IPRESOLVE,CURL_IPRESOLVE_V4);
 curl_easy_setopt(easy,CURLOPT_CONNECTTIMEOUT_MS,5000L);
 curl_easy_setopt(easy,CURLOPT_TIMEOUT_MS,15000L);
 curl_easy_setopt(easy,CURLOPT_SSL_VERIFYPEER,1L);
 curl_easy_setopt(easy,CURLOPT_SSL_VERIFYHOST,2L);
 curl_easy_setopt(easy,CURLOPT_USERAGENT,"NiakPS5-public-media/1.0");
 curl_easy_setopt(easy,CURLOPT_WRITEFUNCTION,curl_write);
 curl_easy_setopt(easy,CURLOPT_WRITEDATA,&body);
 curl_easy_setopt(easy,CURLOPT_MAXFILESIZE_LARGE,static_cast<curl_off_t>(limit));
 const CURLcode rc=curl_easy_perform(easy);
 long status=0;
 if(rc==CURLE_OK)curl_easy_getinfo(easy,CURLINFO_RESPONSE_CODE,&status);
 curl_easy_cleanup(easy);
 if(rc!=CURLE_OK){
   if(failure)*failure=body.oversized?-103:-10000-static_cast<int>(rc);
   if(stage)*stage=body.oversized?8:10;
   return false;
 }
 if(status!=200){if(failure)*failure=static_cast<int>(status);if(stage)*stage=6;return false;}
 if(body.bytes.empty()){if(failure)*failure=-101;if(stage)*stage=7;return false;}
 result=std::move(body.bytes);
 return true;
}
int context() {
  // Never permanently poison the only public-media transport if an early
  // boot, offline network or temporary PS5 sandbox error breaks sceHttpInit.
  // Retry the FAILED stage after a bounded delay on the HTTP worker only.
  // Successful pool/SSL objects are reused; no extra pools are created.
  static std::mutex init_mutex;
  static int pool=-1,ssl=-1,result=-1;
  static std::chrono::steady_clock::time_point next_attempt{};
  std::lock_guard<std::mutex> guard(init_mutex);
  if(result>=0)return result;
  const auto now=std::chrono::steady_clock::now();
  if(now<next_attempt)return result;
  next_attempt=now+std::chrono::seconds(30);
  if(pool<0) {
    (void)sceNetInit();
    pool=sceNetPoolCreate("NiakPS5 public art",4<<20,0);
  }
  if(pool<0)return result=pool;
  if(ssl<0)ssl=sceSslInit(2<<20);
  if(ssl<0)return result=ssl;
  result=sceHttpInit(pool,ssl,4<<20);
  return result;
}
bool launchbox_filename(const std::string &name) {
  const std::size_t start=name.rfind("r2_",0)==0?3u:0u;
  if(name.size()<start+40 || name.size()>start+41)return false;
  for(std::size_t i=start;i<start+36;++i) {
    const char c=name[i];
    if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')||
         (c>='A'&&c<='F')||c=='-'))return false;
  }
  const auto ext=name.substr(start+36);
  return ext==".png" || ext==".jpg" || ext==".jpeg";
}
bool get(const std::string &url,std::size_t limit,std::vector<std::uint8_t> &result,
         int *failure=nullptr,int *stage=nullptr) {
  if(failure)*failure=0;
  if(stage)*stage=0;
  // Host list is exact, not a substring. Refuse custom ports, parameters,
  // path traversal and redirects. No arbitrary user-supplied URLs.
  const bool feed=url==FEED;
  const bool art=url.rfind(MEDIA,0)==0 &&
      url.find("?",std::strlen(MEDIA))==std::string::npos &&
      url.find("..",std::strlen(MEDIA))==std::string::npos &&
      url.rfind(".png")==url.size()-4;
  const bool cases=url.rfind(LAUNCHBOX,0)==0 &&
      launchbox_filename(url.substr(std::strlen(LAUNCHBOX)));
  if(!feed&&!art&&!cases){if(failure)*failure=-100;if(stage)*stage=9;return false;}
  // The one-shot payload installer grants this GUI a privileged filesystem
  // identity. sceSsl can then reject public TLS with 0x8095F00C. libcurl
  // with OpenSSL retains peer/hostname verification under this identity.
  if(niak::payload_process_elevated)
     return get_curl(url,limit,result,failure,stage);
  const int ctx=context();
  if(ctx<0){if(failure)*failure=ctx;if(stage)*stage=1;return false;}
  int tmpl=sceHttpCreateTemplate(ctx,"NiakPS5-public-media/1.0",2,1);
  if(tmpl<0){if(failure)*failure=tmpl;if(stage)*stage=2;return false;}
  (void)sceHttpSetAutoRedirect(tmpl,0);
  // Some PS5 HTTP versions honor deadlines only at the actual connection
  // or request handle. Apply bounded DNS/connect/send/read timeouts at all
  // levels; no CDN call may stall the title's background queue indefinitely.
  const auto bounded_timeout=[](int id){
    (void)sceHttpSetResolveTimeOut(id,5000000);
    (void)sceHttpSetConnectTimeOut(id,5000000);
    (void)sceHttpSetSendTimeOut(id,5000000);
    (void)sceHttpSetRecvTimeOut(id,8000000);
  };
  bounded_timeout(tmpl);
  int conn=sceHttpCreateConnectionWithURL(tmpl,url.c_str(),0);
  if(conn<0){if(failure)*failure=conn;if(stage)*stage=3;
    sceHttpDeleteTemplate(tmpl);return false;}
  bounded_timeout(conn);
  int req=sceHttpCreateRequestWithURL(conn,0,url.c_str(),0);
  if(req>=0)bounded_timeout(req);
  bool ok=req>=0;
  if(!ok){if(failure)*failure=req;if(stage)*stage=4;}
  int status=0;
  if(ok) {
    const int sent=sceHttpSendRequest(req,nullptr,0);
    if(sent<0){ok=false;if(failure)*failure=sent;if(stage)*stage=5;}
    else {
      const int rc=sceHttpGetStatusCode(req,&status);
      if(rc<0){ok=false;if(failure)*failure=rc;if(stage)*stage=6;}
      else if(status!=200){ok=false;if(failure)*failure=status;if(stage)*stage=6;}
    }
  }
  std::vector<std::uint8_t> bytes;bytes.reserve(std::min(limit,std::size_t(1u<<20)));
  if(ok) {
    std::vector<std::uint8_t> chunk(32768);
    int n=0;
    while((n=sceHttpReadData(req,chunk.data(),chunk.size()))>0) {
      if(bytes.size()+std::size_t(n)>limit){
        ok=false;if(failure)*failure=-103;if(stage)*stage=8;break;
      }
      bytes.insert(bytes.end(),chunk.begin(),chunk.begin()+n);
    }
    if(n<0||bytes.empty()) {
      ok=false;
      if(failure)*failure=n<0?n:-101;
      if(stage)*stage=7;
    }
  }
  if(req>=0)(void)sceHttpDeleteRequest(req);
  (void)sceHttpDeleteConnection(conn);
  (void)sceHttpDeleteTemplate(tmpl);
  if(ok){result=std::move(bytes);return true;}
  return false;
}
std::string value_string(const picojson::object &row,const char *key) {
  const auto it=row.find(key);
  return it!=row.end()&&it->second.is<std::string>() ?
      it->second.get<std::string>() : std::string{};
}
}
#endif

bool niak_fetch_latest_ps5_wallpaper(const char *today_yyyy_mm_dd,
                                    std::uint32_t selection_seed,
                                    std::vector<std::uint8_t> &png) {
#if defined(__PROSPERO__)
  if(!today_yyyy_mm_dd||std::strlen(today_yyyy_mm_dd)!=10)return false;
  std::vector<std::uint8_t> body;
  if(!get(FEED,MAX_FEED,body))return false;
  picojson::value parsed;
  const std::string json(body.begin(),body.end());
  if(!picojson::parse(parsed,json).empty() ||
     !parsed.is<picojson::array>())return false;
  const std::string today(today_yyyy_mm_dd);
  // Prefer genuinely released games within two calendar years, not preorders.
  const std::string floor=std::to_string(std::max(2000,std::atoi(today.substr(0,4).c_str())-2))+"-";
  struct Candidate {std::string date,url,name;};
  std::vector<Candidate> items;
  for(const picojson::value &v:parsed.get<picojson::array>()) {
    if(!v.is<picojson::object>())continue;
    const auto &row=v.get<picojson::object>();
    const std::string id=value_string(row,"titleId");
    const std::string date=value_string(row,"releaseDate");
    const std::string url=value_string(row,"cover");
    const std::string name=value_string(row,"name");
    if(id.rfind("PPSA",0)!=0||date.size()<10 ||name.empty()||
       date.substr(0,10)>today||date<floor||name.size()>140 ||
       url.rfind(MEDIA,0)!=0||url.size()<5 ||
       url.substr(url.size()-4)!=".png"||url.find('?')!=std::string::npos)
       continue;
    const std::string lower=name; // no console personal data is inspected.
    if(lower.find("Hentai")!=std::string::npos||
       lower.find("Porn")!=std::string::npos ||
       lower.find("Casino")!=std::string::npos)continue;
    items.push_back({date.substr(0,10),url,name});
  }
  if(items.empty())return false;
  std::sort(items.begin(),items.end(),[](const Candidate &a,const Candidate &b) {
    if(a.date!=b.date)return a.date>b.date;
    return a.name<b.name;
  });
  if(items.size()>70)items.resize(70);
  // Try a few nearby games if an image host is unavailable, never make the
  // initial GUI depend on a successful connection.
  const std::size_t first=selection_seed%items.size();
  for(std::size_t i=0;i<3 && i<items.size();++i) {
    png.clear();
    if(get(items[(first+i)%items.size()].url,MAX_PNG,png) &&
       png.size()>32 && png[0]==137 && png[1]==80 && png[2]==78 && png[3]==71)
       return true;
  }
#else
  (void)today_yyyy_mm_dd;(void)selection_seed;(void)png;
#endif
  return false;
}

bool niak_fetch_launchbox_asset_ex(const char *filename,
                               std::vector<std::uint8_t>& bytes,int *failure,int *failure_stage) {
#if defined(__PROSPERO__)
  if(!filename || !launchbox_filename(filename)){
      if(failure)*failure=-100;
      if(failure_stage)*failure_stage=9;
      return false;
  }
  // Public CDN name only. Never include a profile, console title ID, token
  // or user-supplied URL in the outbound request.
  // Eden Encore likewise allows full originals before decoding/downscaling.
  return get(std::string(LAUNCHBOX)+filename,16u*1024u*1024u,bytes,failure,failure_stage);
#else
  (void)filename;(void)bytes;
  if(failure)*failure=-200;
  if(failure_stage)*failure_stage=9;
  return false;
#endif
}
bool niak_fetch_launchbox_asset(const char *filename,
                               std::vector<std::uint8_t>& bytes) {
  return niak_fetch_launchbox_asset_ex(filename,bytes,nullptr);
}
