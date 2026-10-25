// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// A launcher or media utility must never acquire a commercial game box.
#include <string>
inline bool niak_known_application(const char *name) {
 if(!name)return false;
 std::string value;
 for(const unsigned char *p=(const unsigned char*)name;
     *p && value.size()<160;++p) {
   if(*p>='A'&&*p<='Z')value.push_back(char(*p-'A'+'a'));
   else if((*p>='a'&&*p<='z')||(*p>='0'&&*p<='9'))
     value.push_back(char(*p));
   else if(*p==' '||*p=='_'||*p=='-')value.push_back(' ');
 }
 auto prefix=[&](const char *s){return value.rfind(s,0)==0;};
 return prefix("shadowmount")||prefix("eden encore")||
        prefix("niakps5")||prefix("niaktv")||prefix("cleanmyps5")||
        prefix("ps5 game updater")||prefix("ps5 xplorer")||
        prefix("mes vid")||prefix("my videos")||
        prefix("media gallery");
}
inline bool niak_application_category(const char *id,const char *name,
 int verified,int is_homebrew,bool catalog_app,bool catalog_game){
 if(id && std::string(id)=="PPSA99386")return true;
 if(niak_known_application(name))return true;
 // A current installed title manifest outranks historical FTP and
 // offline game-database classifications. Recognized launchers above
 // remain applications even when a firmware omits their category field.
 if(verified==2)return true;
 if(verified==1)return false;
 if(catalog_app)return true;
 if(catalog_game)return false;
 return is_homebrew!=0;
}

/* A late installed-title inventory may correct a shelf built before the
 * title manifest mounted. Verified apps win; verified games may DEMOTE an
 * old application only when no current installed app evidence conflicts.
 * FTP labels alone never trigger a live category flip. */
inline bool niak_category_needs_refresh(bool current_app,
                                         bool verified_app,
                                         bool verified_game) {
 return (verified_app && !current_app) ||
        (verified_game && !verified_app && current_app);
}
