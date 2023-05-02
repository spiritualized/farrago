# farrago

farrago generates customized album art collages, using listening data from last.fm and bandcamp.

![Faero  830x200  39 tiles  13x3](https://user-images.githubusercontent.com/12180217/235739644-dd3f7c9d-c71a-4b35-8061-f9d9b67c24aa.png)

Collages can be generated for any aspect ratio, and in any resolution.

Some suggested usages are:
- Desktop background
- A printed poster of any size, portrait or landscape
- Phone background
- A banner or column for your website

## Usage
You must edit `collage.py` and fill in a last.fm API key and shared secret.

`python collage.py --lastfm-username <username>  --bandcamp-username <username> --width 3840 --height 1600`

Use the `--width` and `--height` parameters to specify your required image resolution. You can also use `--max-covers` 
to limit how many covers are used - resulting in larger tiles.

## Examples
- [Smartphone wallpaper (4x9 grid, 1290x2796, 5MB)](https://user-images.githubusercontent.com/12180217/235741093-a6b0f4c4-667b-4872-a0c8-93edfbff8e8b.png)
- [Desktop background (20x11 grid, 3200x1800, 10MB)](https://i.imgur.com/LRd8LYD.jpg)
- [Ultrawide desktop background (24x10 grid, 3840x1600, 10MB)](https://i.imgur.com/SVF48pJ.jpg)

Poster-sized images are over 50MB, hence no examples are provided here.


## Printing a poster

If you want to generate a suitable resolution image for a professionally printed poster, use these resolution guidelines:
- 150dpi A0 - 7021 x 4967
- 300dpi A0 - 14043 x 9933
- 600dpi A0 - 28086 x 19866


## Implementation
The first run will be slow, as profile/image needs to be fetched from last.fm and bandcamp
especially if you try to generate a high resolution image. Subsequent runs will be 
much faster, as last.fm data and images will be cached from the previous attempt.
Bandcamp data is not yet cached, and will be fetched every time.
