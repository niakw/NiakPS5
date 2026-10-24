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
#include <mutex>
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
int sceHttpSetConnectTimeOut(int,unsigned);
int sceHttpSetRecvTimeOut(int,unsigned);
}
namespace {
constexpr const char *FEED="https://raw.githubusercontent.com/sharpemu/sharpemu-site/main/src/data/games.json";
constexpr const char *MEDIA="https://image.api.playstation.com/";
constexpr const char *LAUNCHBOX="https://images.launchbox-app.com/";
constexpr std::size_t MAX_FEED=5u*1024u*1024u, MAX_PNG=7u*1024u*1024u;
int context() {
  static int result=-1;static std::once_flag once;
  std::call_once(once,[] {
    (void)sceNetInit();
    const int pool=sceNetPoolCreate("NiakPS5 public art",4<<20,0);
    const int ssl=pool>=0?sceSslInit(2<<20):-1;
    result=ssl>=0?sceHttpInit(pool,ssl,4<<20):-1;
  });
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
bool get(const std::string &url,std::size_t limit,std::vector<std::uint8_t> &result) {
  // Host list is exact, not a substring. Refuse custom ports, parameters,
  // path traversal and redirects. No arbitrary user-supplied URLs.
  const bool feed=url==FEED;
  const bool art=url.rfind(MEDIA,0)==0 &&
      url.find("?",std::strlen(MEDIA))==std::string::npos &&
      url.find("..",std::strlen(MEDIA))==std::string::npos &&
      url.rfind(".png")==url.size()-4;
  const bool cases=url.rfind(LAUNCHBOX,0)==0 &&
      launchbox_filename(url.substr(std::strlen(LAUNCHBOX)));
  if(!feed&&!art&&!cases)return false;
  const int ctx=context();if(ctx<0)return false;
  int tmpl=sceHttpCreateTemplate(ctx,"NiakPS5-public-media/1.0",2,1);
  if(tmpl<0)return false;
  (void)sceHttpSetAutoRedirect(tmpl,0);
  (void)sceHttpSetConnectTimeOut(tmpl,5000000);
  (void)sceHttpSetRecvTimeOut(tmpl,8000000);
  int conn=sceHttpCreateConnectionWithURL(tmpl,url.c_str(),0);
  if(conn<0){sceHttpDeleteTemplate(tmpl);return false;}
  int req=sceHttpCreateRequestWithURL(conn,0,url.c_str(),0);
  bool ok=req>=0;
  int status=0;
  if(ok)ok=sceHttpSendRequest(req,nullptr,0)>=0 &&
             sceHttpGetStatusCode(req,&status)>=0 && status==200;
  std::vector<std::uint8_t> bytes;bytes.reserve(std::min(limit,std::size_t(1u<<20)));
  if(ok) {
    std::vector<std::uint8_t> chunk(32768);
    int n=0;
    while((n=sceHttpReadData(req,chunk.data(),chunk.size()))>0) {
      if(bytes.size()+std::size_t(n)>limit){ok=false;break;}
      bytes.insert(bytes.end(),chunk.begin(),chunk.begin()+n);
    }
    if(n<0||bytes.empty())ok=false;
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

bool niak_fetch_launchbox_asset(const char *filename,
                               std::vector<std::uint8_t>& bytes) {
#if defined(__PROSPERO__)
  if(!filename || !launchbox_filename(filename))return false;
  // The request contains ONLY a public CDN filename; never game/title IDs,
  // PS5 profiles, local network addresses, tokens or user data.
  return get(std::string(LAUNCHBOX)+filename,5u*1024u*1024u,bytes);
#else
  (void)filename;(void)bytes;return false;
#endif
}
