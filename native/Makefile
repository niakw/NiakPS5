# NiakPS5 native foreground launcher, built with the PS5 payload SDK and PacBrew SDL2.
# This is not a patched or swapped SceShellUI.
PS5_PAYLOAD_SDK ?=
ifeq ($(strip $(PS5_PAYLOAD_SDK)),)
$(error Please export PS5_PAYLOAD_SDK pointing to a PacBrew-compatible PS5 SDK)
endif
CC := $(PS5_PAYLOAD_SDK)/bin/prospero-clang
INCLUDE := $(PS5_PAYLOAD_SDK)/target/user/homebrew/include
LIB := $(PS5_PAYLOAD_SDK)/target/user/homebrew/lib
SQLITE := vendor/sqlite3.c
LOADER := gpl/pt.c gpl/elfldr.c gpl/hbldr.c gpl/fs_readfile.c
WARN := -Wall -Wextra -Wno-unused-parameter -O2 -D__PS5__ -I. -I$(INCLUDE) -I$(INCLUDE)/SDL2 -I$(INCLUDE)/freetype2 -DSQLITE_THREADSAFE=0 -DSQLITE_OMIT_LOAD_EXTENSION
GUI_LIBS := \
  $(LIB)/libSDL2main.a $(LIB)/libSDL2.a $(LIB)/libSDL2_image.a \
  $(LIB)/libSDL2_ttf.a $(LIB)/libfreetype.a $(LIB)/libpng.a \
  $(LIB)/libjpeg.a $(LIB)/libwebp.a $(LIB)/libwebpdemux.a $(LIB)/libsharpyuv.a \
  -lSceSystemService -lSceUserService -lSceVideoOut -lSceAudioOut \
  -lScePad -lSceKeyboard -lSceImeDialog -lkernel_sys -lm -lz -lbz2 -liconv
all: build/niakps5_ui.elf build/niakps5_bootstrap.elf
$(SQLITE):
	./fetch-sqlite.sh
build:
	mkdir -p build
build/niakps5_ui.elf: main.c catalog.c catalog.h ui_motion.c ui_motion.h ui_renderer.c ui_renderer.h ui_text_cache.c ui_text_cache.h $(SQLITE) | build
	$(CC) $(WARN) -o $@ main.c catalog.c ui_motion.c ui_renderer.c ui_text_cache.c $(SQLITE) $(GUI_LIBS)
build/niakps5_bootstrap.elf: bootstrap.c $(LOADER) | build
	$(CC) $(WARN) -o $@ bootstrap.c $(LOADER) -lSceSystemService -lSceUserService -lkernel_sys -lm -lz -lbz2 -liconv
clean:
	rm -rf build
.PHONY: all clean
