/* SPDX-License-Identifier: MIT */
/* Resolve consumer-dlopen libraries with the real core24 loader, without a GUI. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <link.h>
#include <stdio.h>

int main(int argc, char **argv)
{
    int failed = 0;
    for (int i = 1; i < argc; ++i) {
        void *handle = dlopen(argv[i], RTLD_NOW | RTLD_LOCAL);
        struct link_map *map = NULL;
        if (!handle || dlinfo(handle, RTLD_DI_LINKMAP, &map) != 0) {
            fprintf(stderr, "%s: %s\n", argv[i], dlerror());
            failed = 1;
        } else {
            printf("%s => %s\n", argv[i], map->l_name);
        }
        if (handle)
            dlclose(handle);
    }
    return failed;
}
