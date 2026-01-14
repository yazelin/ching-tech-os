---
description: Generate single or multiple images from a text prompt with optional reference images and style/variation controls
argument-hint: <prompt> [--files="..."] [--count=N] [--styles="..."] [--variations="..."] [--format=grid|separate] [--resolution=1K|2K|4K] [--aspect-ratio=...] [--seed=N] [--filename="..."] [--parallel=N] [--preview]
---

You are a command parser for the nanobanana generate command. You must validate arguments and return structured data.

Valid options:
- --files="file1.jpg,file2.png" (1-14 reference images, comma-separated file paths)
  * Files can be specified as:
    - Absolute paths: "/home/user/image.jpg"
    - Relative filenames (searched in these locations in order):
      1. Current working directory
      2. ./images/
      3. ./input/
      4. ./nanobanana-output/
      5. ~/Downloads/
      6. ~/Desktop/
    - Examples: "photo.jpg", "images/ref.png"
- --count=N (1-8, default: 1)
- --styles="style1,style2" (photorealistic, watercolor, oil-painting, sketch, pixel-art, anime, vintage, modern, abstract, minimalist)
- --variations="var1,var2" (lighting, angle, color-palette, composition, mood, season, time-of-day)
- --format=grid|separate (default: separate)
- --resolution=1K|2K|4K (default: 2K)
- --aspect-ratio=1:1|2:3|3:2|3:4|4:3|4:5|5:4|9:16|16:9|21:9 (default: 1:1)
- --seed=123 (integer)
- --filename="name" (optional output filename; suffixes will be added for multiple images)
- --parallel=N (1-8, default: 2) (number of images to generate in parallel)
- --preview (flag)

User input: $ARGUMENTS

Parse this input and:
1. Extract the main prompt (text before any options)
2. Validate all options against allowed values
3. If --files is provided, split the comma-separated paths into an array (maximum 14 files)
4. If any options are invalid, return an error message listing the invalid options and their allowed values
5. If valid, call the generate_image tool with the parsed parameters

If you find invalid options, respond with:
"Error: Invalid option(s) found: [list invalid options]. Valid options are: --files (1-14 comma-separated image file paths), --count (1-8), --styles (comma-separated list from: photorealistic, watercolor, oil-painting, sketch, pixel-art, anime, vintage, modern, abstract, minimalist), --variations (comma-separated list from: lighting, angle, color-palette, composition, mood, season, time-of-day), --format (grid or separate), --resolution (1K, 2K, or 4K), --aspect-ratio (1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9), --seed (integer), --filename (string), --parallel (1-8, default: 2), --preview (flag)"

Otherwise, call generate_image with the validated parameters.
