/* SPDX-License-Identifier: GPL-3.0-or-later */

#include "fs.h"

#include <stdio.h>
#include <stdlib.h>

uint8_t *
fs_readfile(const char *path, size_t *size) {
    uint8_t *buf;
    long len;
    FILE *file;

    if(!(file = fopen(path, "rb"))) {
        return 0;
    }
    if(fseek(file, 0, SEEK_END)) {
        fclose(file);
        return 0;
    }
    len = ftell(file);
    if(len < 0) {
        fclose(file);
        return 0;
    }
    if(fseek(file, 0, SEEK_SET)) {
        fclose(file);
        return 0;
    }
    if(!(buf = malloc((size_t)len))) {
        fclose(file);
        return 0;
    }
    if(fread(buf, 1, (size_t)len, file) != (size_t)len) {
        free(buf);
        fclose(file);
        return 0;
    }
    fclose(file);
    if(size) {
        *size = (size_t)len;
    }
    return buf;
}
