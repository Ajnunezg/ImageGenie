# ImageGenie - AI Image Generator

A Python application that lets you generate images using various AI models via the Replicate API.

## Features

- Generate images from text prompts using multiple AI models simultaneously
- Save generated images to model-specific folders with prompt-based filenames
- Scrollable image gallery to view all generated images
- Status log to track generation progress
- Support for custom Replicate models

## Requirements

- Python 3.6+
- A Replicate API token (get one at https://replicate.com)

## Installation

1. Clone this repository:
```
git clone https://github.com/yourusername/ImageGenie.git
cd ImageGenie
```

2. Install the required dependencies:
```
pip install -r requirements.txt
```

## Usage

1. Run the application:
```
python image_generator_gui.py
```

2. Enter your Replicate API token in the designated field
3. Enter a text prompt describing the image you want to generate
4. Select one or more AI models by checking the corresponding boxes
5. Click "Generate Images" to start the generation process
6. Generated images will appear in the right panel and be saved in model-specific folders

## Output Directory Structure

Generated images are saved in the following structure:
```
generated_images/
  ├── Flux_Schnell/
  │   ├── your_prompt_timestamp.png
  │   └── ...
  ├── Recraft-v3/
  │   ├── your_prompt_timestamp.png
  │   └── ...
  └── ...
```

## Advanced Options

- Show Advanced Options: Click to reveal additional settings
- Custom Model: Enter a custom Replicate model ID to use a model not in the default list

## License

MIT License 