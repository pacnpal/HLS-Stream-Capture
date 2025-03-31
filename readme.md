# HLS Stream Capture

A Python tool for capturing HLS (m3u8) live streams using the ffmpeg-asyncio library.

## Features

- Capture HLS (m3u8) live streams to MP4 files
- Async operation with asyncio for better performance
- Stop capturing gracefully with Ctrl+C
- Display recording progress and duration
- Option to add date and time to filenames
- Segment output into multiple files based on specified duration
- Option to complete the current segment when stopping
- Custom ffmpeg binary path support

## Requirements

- Python 3.6+
- FFmpeg (must be installed and in your PATH or specified via the `--ffmpeg-path` option)
- ffmpeg-asyncio 0.1.3

## Installation

### From Source

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/hls-stream-capture.git
   cd hls-stream-capture
   ```

2. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install the package:
   ```
   pip install -e .
   ```

### Using pip

```
pip install hls-stream-capture
```

## Usage

### Basic Usage

```
hlscapture https://example.com/stream.m3u8
```

This will capture the stream until you press Ctrl+C, and save it to `recordings/stream_TIMESTAMP.mp4`.

### Command-line Options

```
usage: hlscapture [-h] [-o OUTPUT_DIR] [-f FILENAME] [-p FFMPEG_PATH] [-v] [-d]
                 [-s SEGMENT_TIME] [-F SEGMENT_FORMAT] [-c] url

Capture HLS live stream (m3u8) until interrupted with Ctrl+C

positional arguments:
  url                   URL of the m3u8 stream to capture

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Directory to save recordings (default: ./recordings)
  -f FILENAME, --filename FILENAME
                        Output filename (default: stream_TIMESTAMP.mp4)
  -p FFMPEG_PATH, --ffmpeg-path FFMPEG_PATH
                        Path to ffmpeg binary (default: system default)
  -v, --verbose         Enable verbose logging
  -d, --add-datetime    Add date and time to the filename even when a custom filename is provided

segmentation:
  Options for segmenting the output into multiple files

  -s SEGMENT_TIME, --segment SEGMENT_TIME
                        Segment the output into files of specified duration (e.g. '60' for 60 seconds, '5:00' for 5 minutes)
  -F SEGMENT_FORMAT, --segment-format SEGMENT_FORMAT
                        Format string for segmented filenames (e.g. 'stream_%03d.mp4'). Default is based on filename.
  -c, --complete-segment
                        When stopping with Ctrl+C, continue until the current segment completes
```

## Examples

Capture a stream with a custom filename:
```
hlscapture https://example.com/stream.m3u8 -f my_recording
```

Specify custom output directory:
```
hlscapture https://example.com/stream.m3u8 -o /path/to/videos
```

Custom ffmpeg binary:
```
hlscapture https://example.com/stream.m3u8 -p /usr/local/bin/ffmpeg
```

Enable verbose logging:
```
hlscapture https://example.com/stream.m3u8 -v
```

Add date and time to a custom filename:
```
hlscapture https://example.com/stream.m3u8 -f game_stream -d
```
This will save as something like: `game_stream_20250330_152045.mp4`

Segment the recording into 5-minute chunks:
```
hlscapture https://example.com/stream.m3u8 -s 5:00
```
This will create files like: `stream_001.mp4`, `stream_002.mp4`, etc. for each 5-minute segment

Segment with custom format:
```
hlscapture https://example.com/stream.m3u8 -f game -s 60 -F "game_part_%04d.mp4"
```
This will create files like: `game_part_0001.mp4`, `game_part_0002.mp4`, etc. for each 1-minute segment

Complete current segment when stopping:
```
hlscapture https://example.com/stream.m3u8 -s 2:00 -c
```
This will wait until the current 2-minute segment completes before stopping when you press Ctrl+C

Combining multiple options:
```
hlscapture https://example.com/stream.m3u8 -f match -o videos -d -s 10:00 -c -v
```
This will:
- Save to a directory called "videos"
- Use a base filename "match" with added timestamp
- Segment into 10-minute chunks
- Complete the current segment when stopping
- Show verbose logging output

## Benefits of Async Implementation

The async implementation using ffmpeg-asyncio provides several advantages:

1. **Non-blocking operation**: The main thread remains responsive during the capture
2. **Better resource utilization**: More efficient CPU usage through asynchronous I/O
3. **Improved error handling**: Better exception handling through asyncio's mechanisms
4. **Clean signal handling**: Graceful cancellation through asyncio signal handlers

## License

MIT