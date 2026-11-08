// SPDX-License-Identifier: MIT
/* Render/readback diagnostic. A software renderer is not a hardware GPU pass. */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static GLuint shader(GLenum type, const char *source)
{
	GLuint object = glCreateShader(type);
	GLint ok;
	glShaderSource(object, 1, &source, NULL);
	glCompileShader(object);
	glGetShaderiv(object, GL_COMPILE_STATUS, &ok);
	if (!ok) {
		char log[2048];
		glGetShaderInfoLog(object, sizeof(log), NULL, log);
		fprintf(stderr, "shader compile failed: %s\n", log);
		exit(1);
	}
	return object;
}

int main(int argc, char **argv)
{
	EGLDisplay display;
	EGLConfig config;
	EGLSurface surface;
	EGLContext context;
	EGLint count;
	GLint ok;
	unsigned char pixel[4];
	const unsigned char expected[4] = { 51, 153, 230, 255 };
	const GLfloat vertices[] = { -1, -1, 3, -1, -1, 3 };
	const EGLint attributes[] = {
		EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
		EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE
	};
	const EGLint size[] = { EGL_WIDTH, 16, EGL_HEIGHT, 16, EGL_NONE };
	const EGLint version[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };
	if (argc > 2) {
		fprintf(stderr, "Usage: %s [required-renderer-substring]\n", argv[0]);
		return 2;
	}
	display = eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
	if (display == EGL_NO_DISPLAY || !eglInitialize(display, NULL, NULL) ||
	    !eglBindAPI(EGL_OPENGL_ES_API) || !eglChooseConfig(display, attributes, &config, 1, &count) || !count) {
		fprintf(stderr, "EGL setup failed: 0x%x\n", eglGetError());
		return 1;
	}
	surface = eglCreatePbufferSurface(display, config, size);
	context = eglCreateContext(display, config, EGL_NO_CONTEXT, version);
	if (surface == EGL_NO_SURFACE || context == EGL_NO_CONTEXT || !eglMakeCurrent(display, surface, surface, context)) {
		fprintf(stderr, "EGL context failed: 0x%x\n", eglGetError());
		return 1;
	}
	const char *renderer = (const char *)glGetString(GL_RENDERER);
	printf("renderer=%s\nversion=%s\n", renderer ? renderer : "(null)", glGetString(GL_VERSION));
	if (!renderer || (argc == 2 && !strstr(renderer, argv[1]))) {
		fprintf(stderr, "Required renderer missing\n");
		return 1;
	}
	GLuint vert = shader(GL_VERTEX_SHADER, "attribute vec2 p; void main(){gl_Position=vec4(p,0.,1.);}");
	GLuint frag = shader(GL_FRAGMENT_SHADER, "precision mediump float; void main(){gl_FragColor=vec4(.2,.6,.9,1.);}");
	GLuint program = glCreateProgram();
	glAttachShader(program, vert);
	glAttachShader(program, frag);
	glBindAttribLocation(program, 0, "p");
	glLinkProgram(program);
	glGetProgramiv(program, GL_LINK_STATUS, &ok);
	if (!ok) {
		fprintf(stderr, "shader link failed\n");
		return 1;
	}
	glUseProgram(program);
	glViewport(0, 0, 16, 16);
	glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, vertices);
	glEnableVertexAttribArray(0);
	glDrawArrays(GL_TRIANGLES, 0, 3);
	glReadPixels(8, 8, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
	if (glGetError() != GL_NO_ERROR) {
		fprintf(stderr, "GL draw/readback failed\n");
		return 1;
	}
	for (unsigned i = 0; i < 4; i++) {
		if (abs((int)pixel[i] - expected[i]) > 1) {
			fprintf(stderr, "pixel component %u: expected %u, got %u\n", i, expected[i], pixel[i]);
			return 1;
		}
	}
	printf("pixel=%u,%u,%u,%u\nrender_readback=PASS\n", pixel[0], pixel[1], pixel[2], pixel[3]);
	glDeleteProgram(program);
	glDeleteShader(vert);
	glDeleteShader(frag);
	eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
	eglDestroyContext(display, context);
	eglDestroySurface(display, surface);
	eglTerminate(display);
	return 0;
}
