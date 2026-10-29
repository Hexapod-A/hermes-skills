# ffmpeg recipes

Copy-paste commands for jobs `assemble.py` does not cover. `in.mp4` = input, `out.mp4` = output.
Add `-c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart` to any
command that makes a final file.

## Inspect

    ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,pix_fmt,sample_rate -of json in.mp4
    ffmpeg -ss 00:00:12.4 -i in.mp4 -frames:v 1 frame.jpg                 # one frame
    ffmpeg -i in.mp4 -vf "fps=1,scale=320:-2,tile=6x4" -frames:v 1 sheet.jpg  # 24 frames, one per second
    ffmpeg -i in.mp4 -af ebur128=peak=true -f null - 2>&1 | tail -12       # loudness report

## Cut and join

    ffmpeg -ss 3.2 -i in.mp4 -t 1.8 out.mp4                               # exact cut (re-encodes)
    ffmpeg -ss 3.2 -i in.mp4 -t 1.8 -c copy out.mp4                       # fast, snaps to keyframes
    printf "file 'a.mp4'\nfile 'b.mp4'\n" > list.txt && ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4   # same-format files only

## Frame and aspect

    # fill 9:16 by cropping (move the crop with the x expression: 0 = left, (iw-ow) = right)
    ffmpeg -i in.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" out.mp4
    # whole frame on a blurred copy
    ffmpeg -i in.mp4 -filter_complex "[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:4[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2" out.mp4
    # letterbox to 1:1
    ffmpeg -i in.mp4 -vf "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2" out.mp4

## Speed and time

    ffmpeg -i in.mp4 -filter_complex "[0:v]setpts=PTS/2[v];[0:a]atempo=2[a]" -map "[v]" -map "[a]" out.mp4   # 2x
    ffmpeg -i in.mp4 -vf "setpts=4*PTS,minterpolate=fps=60:mi_mode=mci" -an slow.mp4    # smooth 0.25x slow motion
    ffmpeg -i in.mp4 -vf reverse -af areverse rev.mp4                                  # reverse (short clips only, uses RAM)
    ffmpeg -i in.mp4 -vf "tpad=stop_mode=clone:stop_duration=1.5" hold.mp4             # freeze the last frame 1.5 s
    # speed ramp: easiest as consecutive clips at different speeds ("ramp" in assemble.py)

## Motion and punch-ins

    # slow zoom-in on a photo, 3 s at 30 fps
    ffmpeg -i photo.jpg -vf "scale=3240:5760:force_original_aspect_ratio=increase,crop=3240:5760,zoompan=z='1+0.15*on/90':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=90:s=1080x1920:fps=30" -t 3 zoom.mp4
    # punch-in (1.2x crop) for a jump-cut feel on talking heads
    ffmpeg -i in.mp4 -vf "crop=iw/1.2:ih/1.2,scale=1080:1920" punch.mp4
    # camera shake (small random move)
    ffmpeg -i in.mp4 -vf "crop=iw-40:ih-40:20+10*sin(t*37):20+10*cos(t*29),scale=1080:1920" shake.mp4

## Transitions (between two clips of the same format)

    ffmpeg -i a.mp4 -i b.mp4 -filter_complex "[0:v][1:v]xfade=transition=fade:duration=0.3:offset=2.7[v];[0:a][1:a]acrossfade=d=0.3[a]" -map "[v]" -map "[a]" out.mp4
    # offset = length of a.mp4 minus the fade. Other transitions: wipeleft, slideup, circleopen, dissolve, pixelize, zoomin, smoothleft, fadeblack, fadewhite
    # a "flash" cut: fadewhite with duration 0.12

## Colour

    ffmpeg -i in.mp4 -vf "eq=contrast=1.08:saturation=1.15:brightness=0.02:gamma=0.98" out.mp4
    ffmpeg -i in.mp4 -vf "lut3d=file=look.cube" out.mp4                  # LUT grade (.cube)
    ffmpeg -i in.mp4 -vf "colorbalance=rs=0.05:bs=-0.05:rh=0.04:bh=-0.04" warm.mp4   # warmer
    ffmpeg -i in.mp4 -vf "curves=preset=increase_contrast,vignette=PI/5" filmic.mp4
    ffmpeg -i in.mp4 -vf "hue=s=0" bw.mp4

## Text and graphics

    # text with a box, appears at 0.5 s, fades in 0.2 s
    ffmpeg -i in.mp4 -vf "drawtext=fontfile=Font-Bold.ttf:text='Save 10 hours a week':fontsize=72:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=20:x=(w-text_w)/2:y=h*0.15:alpha='min(1,(t-0.5)/0.2)':enable='gte(t,0.5)'" out.mp4
    # logo bottom-right, 40 px margin, 85% opacity
    ffmpeg -i in.mp4 -i logo.png -filter_complex "[1]scale=220:-1,format=rgba,colorchannelmixer=aa=0.85[l];[0][l]overlay=W-w-40:H-h-40" out.mp4
    # burn .srt captions with a style (needs libass)
    ffmpeg -i in.mp4 -vf "subtitles=subs.srt:force_style='FontName=Inter,FontSize=14,Bold=1,Outline=2,MarginV=70'" out.mp4
    # progress bar along the bottom
    ffmpeg -i in.mp4 -filter_complex "color=c=0xFF9900:s=1080x12[bar];[0][bar]overlay=x='-w+w*t/DURATION':y=H-12:shortest=1" out.mp4   # replace DURATION with seconds

Word-by-word captions from speech: transcribe with faster-whisper (`word_timestamps=True`) and write an .ass file with one event per word or per 2-3 words; `video-clipper` has a working caption builder.

## Audio

    ffmpeg -i in.mp4 -af "loudnorm=I=-14:TP=-1.5:LRA=11" out.mp4                           # one-pass normalise (two-pass is in assemble.py)
    ffmpeg -i in.mp4 -af "afade=t=in:d=0.3,afade=t=out:st=14.2:d=0.8" out.mp4               # fades
    ffmpeg -i voice.wav -af "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-18dB:ratio=3,loudnorm=I=-16" clean.wav   # cleaner voice
    # duck music under voice
    ffmpeg -i voice.wav -i music.mp3 -filter_complex "[1:a]volume=0.5[m];[0:a]asplit[v1][v2];[m][v2]sidechaincompress=threshold=0.02:ratio=10:release=350[d];[v1][d]amix=inputs=2:normalize=0:duration=first" mix.wav
    # J-cut: next clip's audio starts 0.5 s before its picture -> build the audio track with adelay and the video with concat separately
    ffmpeg -i in.mp4 -af silencedetect=noise=-40dB:d=0.5 -f null - 2>&1 | grep silence_     # find pauses to cut

Beat timing: `ffmpeg -i music.mp3 -af "aresample=22050,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level" -f null -` prints the level per frame; peaks are the beats. Or use `aubio onset music.mp3` / `librosa.beat.beat_track` (pip). Put cuts on beats or just before them.

## Export

    ffmpeg -i in.mp4 -c copy -movflags +faststart out.mp4                  # fix "moov at end" without re-encoding
    ffmpeg -i in.mp4 -vf "fps=12,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" out.gif
    ffmpeg -ss 1.2 -i in.mp4 -frames:v 1 -q:v 2 thumb.jpg                   # cover image
    ffmpeg -i in.mov -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart master.mp4

## Platform specs (2026, check the platform's help page when it matters)

| Place | Size | Notes |
|---|---|---|
| Reels / TikTok / Shorts | 1080x1920, 30 fps | 9:16; keep text out of top ~12% and bottom ~20%; up to 90 s (Reels), longer allowed elsewhere |
| Feed (Instagram, LinkedIn, Facebook) | 1080x1350 (4:5) or 1080x1080 | 4:5 takes more screen space |
| YouTube / web | 1920x1080 | 16:9 |
| WhatsApp | under 16 MB | H.264 + AAC, yuv420p; send larger files as a document |
