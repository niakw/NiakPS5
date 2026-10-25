#include "../app_classification.hpp"
#include <cassert>
int main(){
 assert(niak_application_category("PPSA99386","NiakPS5",1,0,false,true));
 assert(niak_application_category("PPSA12345","ShadowMountPlus",1,0,false,true));
 assert(niak_application_category("PPSA12345","Eden Encore",0,0,false,false));
 assert(niak_application_category("PPSA12345","Mes vidéos",0,0,false,false));
 assert(!niak_application_category("PPSA12345","EA Sports FC 27",1,1,false,false));
 // An installed Game manifest must beat an older FTP "Application".
 assert(!niak_application_category("PPSA12345","EA Sports FC 27",1,0,true,false));
 // A verified installed Application must beat an old metadata Game label.
 assert(niak_application_category("PPSA12345","Native Media App",2,0,false,true));
 // Unknown current category can still use the offline catalogue.
 assert(niak_application_category("PPSA12345","Native Media App",0,0,true,false));
 assert(!niak_application_category("PPSA12345","Unknown Title",0,1,false,true));
 assert(!niak_application_category("CUSA12345","Some Game",0,0,false,false));
 assert(niak_application_category("PPSA12345","Homebrew",0,1,false,false));
 return 0;
}
