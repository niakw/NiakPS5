#include "../app_classification.hpp"
#include <cassert>
int main(){
 assert(niak_application_category("PPSA99386","NiakPS5",1,0,false,true));
 assert(niak_application_category("PPSA12345","ShadowMountPlus",1,0,false,true));
 assert(niak_application_category("PPSA12345","Eden Encore",0,0,false,false));
 assert(niak_application_category("PPSA12345","Mes vidéos",0,0,false,false));
 assert(!niak_application_category("PPSA12345","EA Sports FC 27",1,1,false,false));
 assert(!niak_application_category("CUSA12345","Some Game",0,0,false,false));
 assert(niak_application_category("PPSA12345","Homebrew",0,1,false,false));
 return 0;
}
