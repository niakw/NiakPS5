#include "../title_category.h"
#include <assert.h>

int main(void) {
    assert(niak_is_installed_media_category("{\"applicationCategoryType\":65536}"));
    assert(niak_is_installed_media_category("{\"applicationCategoryType\":\"65792\"}"));
    assert(niak_is_installed_media_category(
        "{ \"applicationCategoryType\" : \"66048\", \"titleName\": \"Media\" }"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":0}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":\"0\"}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":\"65536x\"}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":65536x}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":655360}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":-65536}"));
    assert(!niak_is_installed_media_category("{\"applicationCategoryType\":null}"));
    assert(!niak_is_installed_media_category("{\"otherCategoryType\":65536}"));
    assert(!niak_is_installed_media_category(NULL));
    return 0;
}
