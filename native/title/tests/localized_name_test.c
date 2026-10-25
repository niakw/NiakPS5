// Native PS5 manifest titles: raw UTF-8, JSON escapes and French preference.
#include "../localized_name.h"
#include <assert.h>
#include <string.h>

int main(void) {
 char title[128];
 assert(niak_json_title_value("\"Été à Noël\"",title,sizeof(title)));
 assert(strcmp(title,"Été à Noël")==0);
 assert(niak_json_title_value("\"\\u00c9t\\u00e9 \\u00e0 No\\u00ebl\"",title,sizeof(title)));
 assert(strcmp(title,"Été à Noël")==0);
 assert(niak_json_title_value("\"Jeu \\uD83C\\uDFAE\"",title,sizeof(title)));
 assert(strcmp(title,"Jeu 🎮")==0);
 assert(niak_json_title_value("\"\\\" A\\/B \\\\ \\t fin\"",title,sizeof(title)));
 assert(strcmp(title,"\" A/B \\   fin")==0);
 assert(niak_manifest_localized_title(
   "{\"localizedParameters\":{\"en-US\":{\"titleName\":\"Summer\"},"
   "\"fr-FR\":{\"titleName\":\"Été\"}}}",title,sizeof(title)));
 assert(strcmp(title,"Été")==0);
 assert(niak_manifest_localized_title(
   "{\"localizedParameters\":{\"en-US\":{\"titleName\":\"Summer\"},"
   "\"fr-FR\":{\"titleName\":\"\\uD800\"}}}",title,sizeof(title)));
 assert(strcmp(title,"Summer")==0);
 assert(!niak_json_title_value("\"\\uD800\"",title,sizeof(title)));
 assert(!niak_json_title_value("\"\\uDC00\"",title,sizeof(title)));
 assert(!niak_json_title_value("\"\\uD800\\u0041\"",title,sizeof(title)));
 assert(!niak_json_title_value("\"\\uZZZZ\"",title,sizeof(title)));
 assert(!niak_json_title_value("\"\xC0\xAF\"",title,sizeof(title)));
 assert(!niak_json_title_value("\"\xED\xA0\x80\"",title,sizeof(title)));
 assert(!niak_json_title_value("\"Été à Noël\"",title,4));
 assert(!niak_manifest_localized_title("{\"titleName\":\"Not localized\"}",title,sizeof(title)));
 return 0;
}
