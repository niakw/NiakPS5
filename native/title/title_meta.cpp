// Title-id/metadata data: andshrew/PlayStation-Titles (MIT), sharpemu-site.
#include "title_meta.hpp"
#include <cstdio>
#include <cstring>
#include <string>
#include <initializer_list>
#include <unordered_map>
using Index=std::unordered_map<std::string,NiakTitleMetadata>;
static Index read_titles(){
 Index index;
 for(const char *source : {"/app0/assets/niak-ps-titles.tsv",
                             "/app0/assets/niak-local-titles.tsv"}) {
 FILE *f=std::fopen(source,"rb");if(!f)continue;
 char line[1200];
 while(std::fgets(line,sizeof(line),f)){
  if(!std::strchr(line,'\n') && !std::feof(f)){
   int c;while((c=std::fgetc(f))!=EOF && c!='\n'){} continue;
  }
  char *v[5]={};int fields=0;char *current=line;
  for(int i=0;i<4;i++){
   char *next=std::strchr(current,'\t');if(!next)break;
   *next=0;v[fields++]=current;current=next+1;
  }
  if(fields!=4)continue;
  v[4]=current;v[4][std::strcspn(v[4],"\r\n")]=0;
  if(std::strlen(v[0])!=9 || !*v[1])continue;
  const auto it=index.find(v[0]);
  if(it==index.end()) index.emplace(v[0],NiakTitleMetadata{v[1],v[2],v[3],v[4]});
  else if(std::strstr(source,"local-titles"))it->second.name=v[1];
 }
 std::fclose(f);
 }
 return index;
}
bool niak_title_metadata(const char *id,NiakTitleMetadata &out){
 if(!id || std::strlen(id)!=9)return false;
 static const Index index=read_titles();
 const auto it=index.find(id);if(it==index.end())return false;
 out=it->second;return true;
}
std::string niak_title_summary(const NiakTitleMetadata &v){
 std::string text;
 if(!v.genre.empty())text="Genre : "+v.genre;
 if(!v.publisher.empty()){if(!text.empty())text+=" · ";text+="Éditeur : "+v.publisher;}
 if(!v.released.empty()){if(!text.empty())text+=" · ";text+="Sortie : "+v.released;}
 return text;
}

std::string niak_title_overview(const char *id) {
 if(!id || std::strlen(id)!=9)return {};
 static const auto index=[]() {
   std::unordered_map<std::string,std::string> data;
   FILE *f=std::fopen("/app0/assets/niak-launchbox-cases.tsv","rb");
   if(!f)return data;
   char line[1800];
   while(std::fgets(line,sizeof(line),f)) {
     if(!std::strchr(line,'\n')&&!std::feof(f)) {
       int ch;while((ch=std::fgetc(f))!=EOF&&ch!='\n'){}
       continue;
     }
     char *tab=std::strchr(line,'\t');
     if(!tab)continue;
     *tab=0;
     if(std::strlen(line)!=9||line[0]=='#')continue;
     char *overview=tab+1;
     tab=std::strchr(overview,'\t');
     if(tab)*tab=0;
     if(*overview && std::strcmp(overview,"-")!=0)
       data.emplace(line,overview);
   }
   std::fclose(f);return data;
 }();
 const auto it=index.find(id);
 return it==index.end()?std::string{}:it->second;
}
