#include "../title_category.h"
#include <assert.h>

int main(void) {
    assert(niak_is_installed_media_category("{\"applicationCategoryType\":65536}"));
    assert(niak_is_installed_media_category("{\"applicationCategoryType\":\"65792\"}"));
    assert(niak_is_installed_media_category(
        "{ \"applicationCategoryType\" : \"66048\", \"titleName\": \"Media\" }"));
    assert(niak_is_installed_media_category(
        "{\"localizedParameters\":{\"en-US\":{\"applicationCategoryType\":0}},"
        "\"applicationCategoryType\":65536}"));
    assert(!niak_is_installed_media_category(
        "{\"localizedParameters\":{\"applicationCategoryType\":65536},"
        "\"applicationCategoryType\":0}"));
    assert(!niak_is_installed_media_category(
        "{\"localizedParameters\":{\"applicationCategoryType\":65536}}"));
    assert(!niak_is_installed_media_category(
        "{\"applicationCategoryType\":65536,\"applicationCategoryType\":0}"));
    assert(!niak_is_installed_media_category(
        "{\"applicationCategoryType\":0,\"applicationCategoryType\":65536}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":0}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":\"0\"}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":\"65536x\"}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":65536x}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":655360}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":-65536}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":null}"));
    assert(!niak_is_installed_media_category("{\"otherCategoryType\":65536}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":65536,}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":65536}garbage"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":65536"));
    assert(!niak_is_installed_media_category(
        "{\"other\":{\"nested\":[]],\"applicationCategoryType\":65536}"));
    assert(niak_is_installed_media_category_for_title(
        "{\"titleId\":\"NPXS00001\",\"applicationCategoryType\":65536}",
        "NPXS00001"));
    assert(!niak_is_installed_media_category_for_title(
        "{\"titleId\":\"NPXS00002\",\"applicationCategoryType\":65536}",
        "NPXS00001"));
    assert(!niak_is_installed_media_category_for_title(
        "{\"titleId\":\"NPXS00001\",\"titleId\":\"NPXS00001\","
        "\"applicationCategoryType\":65536}", "NPXS00001"));
    assert(niak_is_installed_media_category_for_title(
        "{\"titleName\":\"Media\",\"applicationCategoryType\":65536}",
        "NPXS00001"));
    /* A game category is valid but never turns a PS5 game into media. */
    assert(niak_installed_category_for_title(
        "{\"applicationCategoryType\":0}",NULL)==1);
    assert(niak_installed_category_for_title(
        "{\"applicationCategoryType\":65536}",NULL)==2);
    assert(niak_installed_category_for_title(
        "{\"localizedParameters\":{\"applicationCategoryType\":65536},"
        "\"applicationCategoryType\":0}",NULL)==1);
    assert(niak_installed_category_for_title(
        "{\"description\":\"applicationCategoryType:65536\","
        "\"applicationCategoryType\":0}",NULL)==1);
    assert(niak_installed_category_for_title(
        "{\"titleId\":\"PPSA12345\",\"applicationCategoryType\":65536}",
        "PPSA54321")==0);
    assert(niak_installed_category_for_title(
        "{\"applicationCategoryType\":0,\"applicationCategoryType\":65536}",NULL)==0);
    assert(niak_installed_category_for_title(
        "{\"applicationCategoryType\":655360}",NULL)==0);
    assert(!niak_is_installed_media_category(NULL));
    return 0;
}
