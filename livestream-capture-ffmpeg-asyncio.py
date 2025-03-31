#!/usr/bin/env python3
"""
HLS Live Stream Capture using ffmpeg-asyncio
-------------------------------------------
This script captures an HLS (m3u8) live stream using the ffmpeg-asyncio module.
The script will run until interrupted with Ctrl+C, with an option to complete
the current segment before stopping.

Features:
- Capture HLS (m3u8) streams to MP4 files
- Segment output into multiple files
- Complete current segment when stopping
- Display progress during recording
- Asynchronous operation
"""

import argparse
import asyncio
import datetime
import logging
import os
import re
import signal
import sys
import time
from pathlib import Path

import ffmpeg_asyncio as ffmpeg

class LiveStreamCapture:
    def __init__(self, m3u8_url, output_dir="recordings", filename=None,
                 add_datetime=False, segment_time=None, segment_format=None,
                 complete_segment=False, ffmpeg_path=None):
        """Initialize the HLS stream capture."""
        self.url = m3u8_url
        self.output_dir = Path(output_dir)
        self.process = None
        self.is_running = False
        self.start_time = None
        self.stopping = False
        self.add_datetime = add_datetime
        self.ffmpeg_path = ffmpeg_path

        # Segmentation options
        self.segment_time = segment_time  # Time in seconds for each segment
        self.segment_format = segment_format  # Format string for segmented filenames
        self.complete_segment = complete_segment  # Whether to complete current segment when stopping

        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger("livestream-capture")

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp if requested
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if filename is None:
            self.filename = f"stream_{timestamp}.mp4"
        else:
            # Add datetime to the custom filename if requested
            if add_datetime:
                base_name, ext = os.path.splitext(filename)
                if not ext:
                    ext = ".mp4"
                self.filename = f"{base_name}_{timestamp}{ext}"
            else:
                if not filename.endswith(".mp4"):
                    filename = f"{filename}.mp4"
                self.filename = filename

        self.output_path = self.output_dir / self.filename

        # Set ffmpeg path if provided
        if self.ffmpeg_path:
            ffmpeg.set_ffmpeg_path(self.ffmpeg_path)

    async def start_capture(self):
        """Start capturing the HLS stream using ffmpeg-asyncio."""
        # Register signal handlers for graceful exit
        self._setup_signal_handlers()

        try:
            self.logger.info(f"Starting stream capture from: {self.url}")

            # Build the FFmpeg command
            cmd = ['-y']  # Overwrite output file if it exists

            # Input options
            cmd.extend(['-i', self.url])

            # Common options for both segmented and non-segmented output
            cmd.extend(['-c', 'copy'])  # Use copy codec to avoid re-encoding

            # Output options based on segmentation
            if self.segment_time:
                # If segmentation is requested
                if not self.segment_format:
                    # Generate a default segment format pattern based on the output filename
                    base_name, ext = os.path.splitext(self.filename)
                    if not ext:
                        ext = ".mp4"
                    self.segment_format = f"{base_name}_%03d{ext}"

                segment_path = str(self.output_dir / self.segment_format)

                # Add segmentation options
                cmd.extend([
                    '-f', 'segment',
                    '-segment_time', str(self.segment_time),
                    '-reset_timestamps', '1',
                    '-segment_start_number', '1',
                    '-segment_format', 'mp4',
                    segment_path
                ])

                self.logger.info(f"Segmenting output every {self.segment_time} seconds")
                self.logger.info(f"Segment format: {self.segment_format}")

                if self.complete_segment:
                    self.logger.info("Will complete current segment when stopping (Ctrl+C)")
            else:
                # Regular non-segmented output
                output_path = str(self.output_path)
                cmd.append(output_path)
                self.logger.info(f"Output will be saved to: {output_path}")

            # Start tracking time
            self.start_time = datetime.datetime.now()
            self.is_running = True
            self.stopping = False

            # Variables to track segment progress
            current_segment = 1
            segment_start_time = self.start_time
            segment_pattern = re.compile(r'Opening \'.*?(\d+)\.mp4\'')

            # Start ffmpeg process with asyncio
            self.logger.info("Press Ctrl+C to stop recording...")

            # Create process
            process = await asyncio.create_subprocess_exec(
                'ffmpeg', *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.process = process

            # Monitor progress
            last_progress_update = time.time()
            progress_interval = 5  # Update progress every 5 seconds

            # Process output
            async def read_output(stream, is_stderr=False):
                nonlocal current_segment, segment_start_time, last_progress_update

                while True:
                    line = await stream.readline()
                    if not line:
                        break

                    line_str = line.decode('utf-8', errors='replace').strip()

                    # Check for segment change in output
                    if is_stderr and self.segment_time:
                        match = segment_pattern.search(line_str)
                        if match:
                            segment_num = int(match.group(1))
                            if segment_num > current_segment:
                                now = datetime.datetime.now()
                                segment_duration = now - segment_start_time
                                hours, remainder = divmod(segment_duration.seconds, 3600)
                                minutes, seconds = divmod(remainder, 60)

                                self.logger.info(f"Segment {current_segment} completed "
                                                f"(duration: {hours:02d}:{minutes:02d}:{seconds:02d})")

                                # If we're stopping at segment completion, now's the time
                                if self.stopping and self.complete_segment:
                                    self.logger.info("Stopping as requested after segment completion")
                                    self.stop_capture()
                                    return

                                current_segment = segment_num
                                segment_start_time = now

                    # Log error messages
                    if is_stderr and ('error' in line_str.lower() or 'warning' in line_str.lower()):
                        self.logger.warning(f"ffmpeg: {line_str}")

                    # Show progress periodically
                    current_time = time.time()
                    if current_time - last_progress_update >= progress_interval:
                        duration = datetime.datetime.now() - self.start_time
                        hours, remainder = divmod(duration.seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)

                        if self.segment_time:
                            segment_duration = datetime.datetime.now() - segment_start_time
                            s_hours, s_remainder = divmod(segment_duration.seconds, 3600)
                            s_minutes, s_seconds = divmod(s_remainder, 60)

                            self.logger.info(f"Recording: {hours:02d}:{minutes:02d}:{seconds:02d} "
                                           f"(Current segment {current_segment}: {s_hours:02d}:{s_minutes:02d}:{s_seconds:02d})")
                        else:
                            self.logger.info(f"Recording duration: {hours:02d}:{minutes:02d}:{seconds:02d}")

                        last_progress_update = current_time

            # Start readers for stdout and stderr
            stdout_task = asyncio.create_task(read_output(process.stdout, False))
            stderr_task = asyncio.create_task(read_output(process.stderr, True))

            # Wait for process to complete
            try:
                await process.wait()
            except asyncio.CancelledError:
                # Handle cancellation
                if self.is_running:
                    self.stop_capture()
            finally:
                # Cancel output readers if they're still running
                stdout_task.cancel()
                stderr_task.cancel()
                try:
                    await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
                except asyncio.CancelledError:
                    pass

            # Process completed or was stopped
            if process.returncode != 0 and not self.stopping:
                self.logger.error(f"Error: ffmpeg exited with code {process.returncode}")
                return False
            else:
                self.is_running = False
                if self.stopping:
                    self.logger.info("Capture stopped by user")
                else:
                    self.logger.info("Stream capture completed successfully")
                return True

        except Exception as e:
            self.logger.error(f"Error capturing stream: {str(e)}")
            self.stop_capture()
            return False

    def stop_capture(self):
        """Stop the stream capture."""
        if not self.process or not self.is_running:
            return

        if self.segment_time and self.complete_segment and not self.stopping:
            # Mark as stopping but don't terminate yet
            self.stopping = True
            self.logger.info("Will stop after current segment completes...")
            return

        self.is_running = False
        self.logger.info("\nStopping stream capture gracefully...")

        # Terminate process if it's still running
        if self.process and self.process.returncode is None:
            try:
                if hasattr(self.process, 'terminate') and callable(getattr(self.process, 'terminate')):
                    self.process.terminate()
            except Exception as e:
                self.logger.error(f"Error stopping ffmpeg: {str(e)}")

        if self.start_time:
            duration = datetime.datetime.now() - self.start_time
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            if self.segment_time:
                self.logger.info(f"Stream segments saved to: {self.output_dir}")
            else:
                self.logger.info(f"Stream capture completed: {self.output_path}")

            self.logger.info(f"Total recording time: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful exit."""
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._signal_handler(s))
            )

    async def _signal_handler(self, sig):
        """Handle interrupt signals."""
        if self.segment_time and self.complete_segment and not self.stopping:
            self.logger.info(f"Received signal {sig}, will stop after current segment completes...")
            self.stopping = True
        else:
            self.logger.info(f"Received signal {sig}, stopping capture...")
            self.stop_capture()

async def async_main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Capture HLS live stream (m3u8) until interrupted with Ctrl+C")
    parser.add_argument("url", help="URL of the m3u8 stream to capture")
    parser.add_argument("-o", "--output-dir", default="recordings",
                        help="Directory to save recordings (default: ./recordings)")
    parser.add_argument("-f", "--filename", default=None,
                        help="Output filename (default: stream_TIMESTAMP.mp4)")
    parser.add_argument("-p", "--ffmpeg-path", default=None,
                        help="Path to ffmpeg binary (default: system default)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")
    parser.add_argument("-d", "--add-datetime", action="store_true",
                        help="Add date and time to the filename even when a custom filename is provided")

    # Add segmentation options
    segment_group = parser.add_argument_group('segmentation', 'Options for segmenting the output into multiple files')
    segment_group.add_argument("-s", "--segment", dest="segment_time", type=str,
                        help="Segment the output into files of specified duration (e.g. '60' for 60 seconds, '5:00' for 5 minutes)")
    segment_group.add_argument("-F", "--segment-format", dest="segment_format", type=str,
                        help="Format string for segmented filenames (e.g. 'stream_%%03d.mp4'). Default is based on filename.")
    segment_group.add_argument("-c", "--complete-segment", action="store_true",
                        help="When stopping with Ctrl+C, continue until the current segment completes")

    args = parser.parse_args()

    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse segment time if provided
    segment_time_seconds = None
    if args.segment_time:
        try:
            # Check if it contains a colon (indicating minutes:seconds format)
            if ":" in args.segment_time:
                minutes, seconds = args.segment_time.split(":")
                segment_time_seconds = int(minutes) * 60 + int(seconds)
            else:
                # Assume it's just seconds
                segment_time_seconds = int(args.segment_time)

            if segment_time_seconds <= 0:
                raise ValueError("Segment time must be positive")

            logging.info(f"Segmenting output every {segment_time_seconds} seconds")
        except ValueError as e:
            logging.error(f"Invalid segment time format: {str(e)}")
            sys.exit(1)

    # Validate complete-segment option
    if args.complete_segment and not args.segment_time:
        logging.error("The --complete-segment option requires --segment to be specified")
        sys.exit(1)

    # Validate URL
    if not args.url.endswith(".m3u8") and not "m3u8" in args.url:
        logging.warning("Warning: The URL doesn't appear to be an m3u8 stream. Make sure it's a valid HLS stream URL.")
        proceed = input("Continue anyway? (y/n): ")
        if proceed.lower() != 'y':
            sys.exit(1)

    try:
        # Create and start the capture
        capturer = LiveStreamCapture(
            m3u8_url=args.url,
            output_dir=args.output_dir,
            filename=args.filename,
            ffmpeg_path=args.ffmpeg_path,
            add_datetime=args.add_datetime,
            segment_time=segment_time_seconds,
            segment_format=args.segment_format,
            complete_segment=args.complete_segment
        )

        # Start capturing
        await capturer.start_capture()
    except KeyboardInterrupt:
        # This should be handled by the signal handler, but just in case
        logging.info("Interrupted by user")
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)

def main():
    """Entry point for the script."""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
