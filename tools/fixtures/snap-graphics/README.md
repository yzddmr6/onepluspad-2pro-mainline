Connection fixtures and GLSL probe are adapted from
https://github.com/yzddmr6/xiaomipad-8pro-mainline (MIT).
The connection helper originates at c14de88ac73f2f83354bf3799ca75aeae774a897;
the mediump regression case originates at 869b42ca61ca666a18b83b7b1d0d8ef7ba025102.
Only package names, repository paths and the discovered libgallium version
are adapted. Run tools/test-snap-graphics.py and tools/test-snap-graphics-glsl.py.

The ABI/layout validator and EGL smoke probe are adapted from c14de88ac73f2f83354bf3799ca75aeae774a897 (MIT).
