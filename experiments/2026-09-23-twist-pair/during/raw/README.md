Raw instrument files, exactly as written. Do not edit, crop, rename or convert
anything in this directory.

Native Bruker, JPK, Asylum, Gwyddion and WSXM .stp files are read directly;
there is nothing to export. Only for another format, export a .gsf copy from
Gwyddion and put it here too -- alongside the native file, not instead of it.
`dobladillo afm read` will tell you whether the pixel size and height units
came through, which is worth checking before believing any dimension
downstream.
