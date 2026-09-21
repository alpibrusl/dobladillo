Raw instrument files, exactly as written. Do not edit, crop, rename or convert
anything in this directory.

Export a copy to .gsf for the toolchain and put that here too -- alongside the
native file, not instead of it. `dobladillo afm read` will tell you whether the
pixel size and height units came through, which is worth checking before
believing any dimension downstream.
