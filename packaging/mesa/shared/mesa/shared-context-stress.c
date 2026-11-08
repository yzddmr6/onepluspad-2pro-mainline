// SPDX-License-Identifier: MIT
/* Exercise shared buffer deletion while other threads create GL contexts.
 * Run with the selected Mesa libraries and an explicit hardware renderer.
 * This uses real EGL/GLES entry points, not a model of the context list.
 */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static EGLDisplay display;
static EGLConfig config;
static EGLContext shared;
static const EGLint version[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };
static pthread_barrier_t ready;
static atomic_bool done;
static atomic_uint contexts, buffers;

static void fail(const char *what)
{
   fprintf(stderr, "%s: EGL=0x%x GL=0x%x\n", what, eglGetError(), glGetError());
   exit(1);
}

static void *create_contexts(void *arg)
{
   unsigned rounds = *(unsigned *)arg;
   if (!eglBindAPI(EGL_OPENGL_ES_API))
      fail("bind API");
   pthread_barrier_wait(&ready);
   for (unsigned i = 0; i < rounds; ++i) {
      EGLContext ctx = eglCreateContext(display, config, shared, version);
      if (ctx == EGL_NO_CONTEXT)
         fail("create shared context");
      if (!eglDestroyContext(display, ctx))
         fail("destroy shared context");
      atomic_fetch_add(&contexts, 1);
   }
   eglReleaseThread();
   return NULL;
}

static void *delete_buffers(void *unused)
{
   (void)unused;
   if (!eglBindAPI(EGL_OPENGL_ES_API))
      fail("bind API");
   EGLContext ctx = eglCreateContext(display, config, shared, version);
   if (ctx == EGL_NO_CONTEXT ||
       !eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx))
      fail("make buffer context current");
   pthread_barrier_wait(&ready);
   do {
      GLuint names[64];
      glGenBuffers(64, names);
      for (unsigned i = 0; i < 64; ++i) {
         glBindBuffer(GL_ARRAY_BUFFER, names[i]);
         glBufferData(GL_ARRAY_BUFFER, 4096, NULL, GL_DYNAMIC_DRAW);
      }
      glBindBuffer(GL_ARRAY_BUFFER, 0);
      glDeleteBuffers(64, names);
      glFlush();
      if (glGetError() != GL_NO_ERROR)
         fail("buffer lifecycle");
      atomic_fetch_add(&buffers, 64);
   } while (!atomic_load(&done));
   glFinish();
   if (!eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT) ||
       !eglDestroyContext(display, ctx))
      fail("destroy buffer context");
   eglReleaseThread();
   return NULL;
}

int main(int argc, char **argv)
{
   unsigned rounds = 1000;
   if (argc != 2) {
      fprintf(stderr, "Usage: %s required-renderer-substring\n", argv[0]);
      return 2;
   }
   const EGLint attrs[] = {
      EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
      EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_NONE
   };
   EGLint count;
   display = eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA,
                                   EGL_DEFAULT_DISPLAY, NULL);
   if (!eglInitialize(display, NULL, NULL) || !eglBindAPI(EGL_OPENGL_ES_API) ||
       !eglChooseConfig(display, attrs, &config, 1, &count) || count != 1)
      fail("initialize EGL");
   shared = eglCreateContext(display, config, EGL_NO_CONTEXT, version);
   if (shared == EGL_NO_CONTEXT ||
       !eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, shared))
      fail("create root context");
   const char *renderer = (const char *)glGetString(GL_RENDERER);
   if (!renderer || !strstr(renderer, argv[1]))
      fail("required renderer missing");
   printf("renderer=%s\n", renderer);
   fflush(stdout);
   if (!eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT))
      fail("unbind root context");
   pthread_t creators[4], deleter;
   if (pthread_barrier_init(&ready, NULL, 5) ||
       pthread_create(&deleter, NULL, delete_buffers, NULL))
      fail("create buffer thread");
   for (unsigned i = 0; i < 4; ++i)
      if (pthread_create(&creators[i], NULL, create_contexts, &rounds))
         fail("create context thread");
   for (unsigned i = 0; i < 4; ++i)
      pthread_join(creators[i], NULL);
   atomic_store(&done, 1);
   pthread_join(deleter, NULL);
   pthread_barrier_destroy(&ready);
   if (!eglDestroyContext(display, shared) || !eglTerminate(display))
      fail("terminate EGL");
   printf("contexts=%u buffers=%u shared_context_stress=PASS\n",
          atomic_load(&contexts), atomic_load(&buffers));
   return 0;
}
