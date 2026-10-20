# LiveLica

Media for livelica.com: narrated YouTube videos made from blog posts.

- renderer/make_video.py renders a video from a scenes.json file

- renderer/render_carousel.py renders 1080x1350 Instagram and Facebook carousels from a carousel.json file
- renderer/render_short.py renders 1080x1920 vertical product videos for Shorts and Reels, with burned-in captions



Optional: put a 5 to 10 second clip of a real person at renderer/assets/intro.mp4 and every new video will open with it.
- renderer/media.py puts finished videos and images on the `media` branch for Metricool to fetch, and removes them once every post is confirmed live. The media branch is always a single commit, so removed files free their space.

Media never goes on this main branch.
