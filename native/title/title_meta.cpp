// Title-id/metadata data: andshrew/PlayStation-Titles (MIT), sharpemu-site.
#include "title_meta.hpp"
#include <cstdio>
#include <cstring>
#include <string>
#include <unordered_map>
using Index=std::unordered_map<std::string,NiakTitleMetadata>;
static Index read_titles(){
 Index index;
 FILE *f=std::fopen("/app0/assets/niak-ps-titles.tsv","rb");if(!f)return index;
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
  index.emplace(v[0],NiakTitleMetadata{v[1],v[2],v[3],v[4]});
 }
 std::fclose(f);return index;
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
