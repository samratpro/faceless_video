# Faceless Video

This repository contains a simple pipeline/script for assembling “faceless” videos using prepared resources (scripts, images, and voice audio) and saving the final renders to the output directory.

The main entry point is `app.py`.

## Project structure

```
facelessvideo/
├─ app.py
├─ output/
│  └─ romantic story/
│     ├─ segments/
│     │  ├─ romantic_story_seg_0001.mp4
│     │  ├─ romantic_story_seg_0002.mp4
│     │  └─ romantic_story_seg_0003.mp4
│     └─ romantic_story_faceless_video.mp4
├─ prompt/
│  ├─ script.txt
│  └─ video generate prompt.txt
└─ resource/
   └─ romantic story/
      ├─ images/
      │  ├─ img1.webp
      │  ├─ img2.jpg
      │  └─ img3.jpg
      ├─ scripts/
      │  ├─ script1.txt
      │  ├─ script2.txt
      │  └─ script3.txt
      └─ voices/
         ├─ voice1.mp3
         ├─ voice2.mp3
         └─ voice3.mp3
```

### Directories
- output/: Destination for generated video artifacts.
  - romantic story/: Example output project/folder containing stitched segments and the final rendered video.
  - segments/: Intermediate rendered video segments used to compose the final video.
- prompt/: Text prompts or helper files that may guide the generation process.
- resource/: Source assets for a project/topic (e.g., “romantic story”).
  - images/: Still images or backgrounds used in the video.
  - scripts/: Source script text files.
  - voices/: Voice-over audio files.

## Usage

1. Ensure your resources (images, scripts, voices) are organized under `resource/` as shown above.
2. Run the application from the repository root:
   
   ```bash
   python app.py
   ```

3. Generated segments and final videos will be saved into `output/`.

Notes:
- If your environment requires additional Python packages, install them according to your setup (for example, with `pip install -r requirements.txt` if such a file is added to the project).
- Update paths or configuration in `app.py` as needed to match your resource folder names.

## Contributing
- Keep the folder structure consistent so scripts can reliably find assets.
- When adding third-party dependencies, include a `requirements.txt` and update this README accordingly.

## License
This project’s license has not been specified. Add a LICENSE file if you intend to open-source or distribute it.
