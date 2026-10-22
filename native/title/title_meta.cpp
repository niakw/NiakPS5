// Title-id/metadata data: andshrew/PlayStation-Titles (MIT), sharpemu-site.
#include "title_meta.hpp"
#include <cstdio>
#include <cstring>
#include <string>
#include <initializer_list>
#include <unordered_map>
#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <utility>
using Index=std::unordered_map<std::string,NiakTitleMetadata>;
static Index read_titles(){
 Index index;
 for(const char *source : {"/app0/assets/niak-ps-titles.tsv",
                             "/app0/assets/niak-local-titles.tsv",
                             "/data/homebrew/PPSA99386/assets/niak-local-titles.tsv"}) {
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
  const bool local=std::strstr(source,"local-titles")!=nullptr;
  auto is_category=[](const char *value) {
      return std::strcmp(value,"Jeu")==0 ||
             std::strcmp(value,"Application")==0;
  };
  if(it==index.end()) {
   NiakTitleMetadata data{v[1],v[2],v[3],v[4],{}};
   if(local && is_category(v[2])) {
      data.category=v[2];
      data.genre.clear(); // A classification is not a genre.
   }
   index.emplace(v[0],std::move(data));
  } else if(local) {
   it->second.name=v[1];
   if(v[2][0]) {
       if(is_category(v[2]))it->second.category=v[2];
       else it->second.genre=v[2];
   }
   if(v[3][0])it->second.publisher=v[3];
   if(v[4][0])it->second.released=v[4];
  }
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
namespace {
std::string trimmed(std::string v) {
 const auto a=v.find_first_not_of(" \t\r\n");
 if(a==std::string::npos)return {};
 const auto b=v.find_last_not_of(" \t\r\n");
 return v.substr(a,b-a+1);
}
std::string translated_genre(std::string genre) {
 static const std::unordered_map<std::string,std::string> vocabulary={
  {"strategy","Stratégie"},{"real time strategy","Stratégie en temps réel"},
  {"turn based strategy","Stratégie au tour par tour"},
  {"turn based","Tour par tour"},{"grand strategy","Grande stratégie"},
  {"tactical","Tactique"},{"tactical rpg","Jeu de rôle tactique"},
  {"rpg","Jeu de rôle"},{"role playing","Jeu de rôle"},
  {"role playing game","Jeu de rôle"},{"action rpg","Action-RPG"},
  {"jrpg","Jeu de rôle japonais"},
  {"action","Action"},{"action adventure","Action-aventure"},
  {"adventure","Aventure"},{"simulation","Simulation"},
  {"sports","Sport"},{"sport","Sport"},{"racing","Course"},
  {"racing simulation","Simulation de course"},{"driving","Conduite"},
  {"puzzle","Réflexion"},{"platformer","Plateforme"},
  {"platform","Plateforme"},{"fighting","Combat"},
  {"shooter","Tir"},{"first person shooter","Tir à la première personne"},
  {"third person shooter","Tir à la troisième personne"},
  {"fps","Tir à la première personne"},{"tps","Tir à la troisième personne"},
  {"sandbox","Bac à sable"},{"survival","Survie"},
  {"horror","Horreur"},{"indie","Indépendant"},
  {"casual","Occasionnel"},{"arcade","Arcade"},
  {"multiplayer","Multijoueur"},{"party","Jeu de groupe"},
  {"educational","Éducatif"},{"visual novel","Roman visuel"},
  {"music","Musique"},{"rhythm","Rythme"},
  {"city builder","Construction de villes"},{"management","Gestion"},
  {"building","Construction"},{"other","Autre"},
  {"open world","Monde ouvert"},{"survival horror","Survival horror"},
  {"hack and slash","Action-combat"},{"platform","Plateforme"},
  {"family","Famille"},{"board game","Jeu de société"},
  {"party game","Jeu de groupe"},{"massively multiplayer","Jeu massivement multijoueur"},
  {"online","En ligne"},{"co op","Coopération"},
  {"roguelike","Roguelike"},{"roguelite","Roguelite"}};
 std::string result;
 std::size_t begin=0;
 while(begin<genre.size()) {
  const auto end=genre.find_first_of(",;|",begin);
  std::string word=trimmed(genre.substr(begin,end==std::string::npos ?
      std::string::npos:end-begin));
  std::string lower=word;
  std::transform(lower.begin(),lower.end(),lower.begin(),[](unsigned char c) {
   return char(c<128 ? std::tolower(c) : c);
  });
  const auto it=vocabulary.find(lower);
  if(!result.empty())result+=", ";
  result+=it!=vocabulary.end()?it->second:word;
  if(end==std::string::npos)break;
  begin=end+1;
 }
 return result;
}
std::string french_date(const std::string &date) {
 // Locale FR: YYYY-MM-DD -> D/M/YYYY (no invented day if month-only).
 if(date.size()>=10 && date[4]=='-' && date[7]=='-' &&
    std::all_of(date.begin(),date.begin()+4,[](unsigned char c){return c>='0'&&c<='9';})) {
  const int m=std::atoi(date.substr(5,2).c_str());
  const int d=std::atoi(date.substr(8,2).c_str());
  if(m>=1&&m<=12&&d>=1&&d<=31)
   return std::to_string(d)+"/"+std::to_string(m)+"/"+date.substr(0,4);
 }
 return date;
}
}
std::string niak_title_summary(const NiakTitleMetadata &v){
 std::string text;
 if(!v.genre.empty())text="Genre : "+translated_genre(v.genre);
 if(!v.publisher.empty()){if(!text.empty())text+=" · ";text+="Éditeur : "+v.publisher;}
 if(!v.released.empty()){if(!text.empty())text+=" · ";text+="Sortie : "+french_date(v.released);}
 return text;
}

std::string niak_title_overview(const char *id) {
 if(!id || std::strlen(id)!=9)return {};
 static const auto index=[]() {
   std::unordered_map<std::string,std::string> data;
   FILE *f=std::fopen("/app0/assets/niak-launchbox-cases.tsv","rb");
   if(!f) f=std::fopen(
       "/data/homebrew/PPSA99386/assets/niak-launchbox-cases.tsv","rb");
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
