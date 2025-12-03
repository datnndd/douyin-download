import json
import subprocess
import os
import shutil
import wave

CONFIG_FILE = "config_video.json"
OUTPUT_FILE = "out.mp4"
TEMP_AUDIO_DIR = "temp_audio_chunks"

# ================== CẤU HÌNH PCM / AUDIO ==================
PCM_SAMPLE_RATE = 24000
PCM_CHANNELS = 1
PCM_BITS_PER_SAMPLE = 16

# Tối ưu cho t3.micro (2 vCPU)
FFMPEG_THREADS = "2"
VIDEO_PRESET = "ultrafast"
VIDEO_CRF = "28"
MAX_HEIGHT = 720

# ================== FONT & MÀU SẮC SUBTITLE ==================
SUB_FONT = "Arial"
COLOR_TEXT = "&H00FFFF"      # chữ vàng sáng (Cyan in BGR = Yellow in RGB)
COLOR_OUTLINE = "0"       # viền đen
SUB_FONT_SIZE = 18
SUB_MARGIN_V = 12         # vị trí chữ


def get_duration(path: str, cache: dict) -> float:
    """Lấy duration của file audio (pcm hoặc định dạng khác) và cache lại."""
    if path in cache:
        return cache[path]
    dur = 0.0
    if path.lower().endswith(".pcm"):
        try:
            size_bytes = os.path.getsize(path)
            bytes_per_sample = PCM_BITS_PER_SAMPLE // 8
            bytes_per_second = PCM_SAMPLE_RATE * PCM_CHANNELS * bytes_per_sample
            dur = size_bytes / bytes_per_second if bytes_per_second > 0 else 0.0
        except FileNotFoundError:
            dur = 0.0
    else:
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                dur = float(result.stdout.strip())
        except Exception:
            dur = 0.0
    cache[path] = dur
    return dur


def create_silent_wav(filename, duration_sec):
    """Tạo file wav silence mono 24kHz với độ dài duration_sec."""
    if duration_sec <= 0:
        return
    num_frames = int(duration_sec * PCM_SAMPLE_RATE)
    data = b"\x00\x00" * num_frames * PCM_CHANNELS
    try:
        with wave.open(filename, "w") as wf:
            wf.setnchannels(PCM_CHANNELS)
            wf.setsampwidth(PCM_BITS_PER_SAMPLE // 8)
            wf.setframerate(PCM_SAMPLE_RATE)
            wf.writeframes(data)
    except Exception as e:
        print(f"Error creating silence: {e}")


def generate_optimized_audio(segments, output_wav):
    """
    MỤC TIÊU: ĐỒNG BỘ VỚI SRT.
    """
    if os.path.exists(TEMP_AUDIO_DIR):
        shutil.rmtree(TEMP_AUDIO_DIR)
    os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

    duration_cache = {}
    concat_list_path = os.path.join(TEMP_AUDIO_DIR, "concat_list.txt")
    concat_files = []

    last_end_time = 0.0
    total_segs = len(segments)

    print(f"--- Processing Audio: {total_segs} segments (Sync with SRT Mode) ---")

    for i, seg in enumerate(segments):
        audio_path = seg["path"]
        start = float(seg["start"])
        end_target = float(seg["end"]) 
        slot_len = max(end_target - start, 0.1)

        # ---- GAP TRƯỚC SEGMENT ----
        gap = start - last_end_time
        if gap > 0.01:
            silence_file = os.path.join(TEMP_AUDIO_DIR, f"silence_{i}.wav")
            create_silent_wav(silence_file, gap)
            if os.path.exists(silence_file):
                concat_files.append(silence_file)
            last_end_time += gap

        # ---- DURATION GỐC ----
        raw_dur = get_duration(audio_path, duration_cache)
        if raw_dur <= 0:
            silence_seg = os.path.join(TEMP_AUDIO_DIR, f"seg_silence_{i}.wav")
            create_silent_wav(silence_seg, slot_len)
            concat_files.append(silence_seg)
            last_end_time = end_target
            continue

        # ---- TEMPO ----
        tempo = raw_dur / slot_len
        need_padding = False

        if tempo < 1.0:
            # Nếu audio ngắn hơn slot -> KHÔNG giãn (slow), mà giữ nguyên tốc độ (1.0) + padding silence
            tempo = 1.0
            need_padding = True
        elif tempo > 2.0:
            # Nếu audio dài hơn slot quá nhiều -> tua nhanh tối đa 2.0
            tempo = 2.0

        seg_output = os.path.join(TEMP_AUDIO_DIR, f"seg_{i}.wav")

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-threads", FFMPEG_THREADS]

        if audio_path.lower().endswith(".pcm"):
            cmd += ["-f", "s16le", "-ar", str(PCM_SAMPLE_RATE), "-ac", str(PCM_CHANNELS), "-i", audio_path]
        else:
            cmd += ["-i", audio_path]

        filter_str = "asetpts=PTS-STARTPTS"
        if abs(tempo - 1.0) > 0.01:
            filter_str += f",atempo={tempo:.3f}"
        
        if need_padding:
            # Thêm pad vô tận, sau đó dùng -t để cắt đúng slot_len
            filter_str += ",apad"

        cmd += ["-af", filter_str, "-ac", str(PCM_CHANNELS), "-ar", str(PCM_SAMPLE_RATE)]

        if need_padding:
            # Cắt đúng thời lượng slot
            cmd += ["-t", str(slot_len)]

        cmd += ["-c:a", "pcm_s16le", seg_output]

        try:
            subprocess.run(cmd, check=True)
            concat_files.append(seg_output)
        except subprocess.CalledProcessError:
            silence_seg = os.path.join(TEMP_AUDIO_DIR, f"seg_fallback_silence_{i}.wav")
            create_silent_wav(silence_seg, slot_len)
            concat_files.append(silence_seg)

        last_end_time = end_target

    # ---- NỐI TOÀN BỘ AUDIO ----
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for path in concat_files:
            safe_path = os.path.abspath(path).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    print("--- Merging all audio segments ---")

    if not concat_files:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={PCM_SAMPLE_RATE}:cl=mono",
             "-t", "1", "-c:a", "pcm_s16le", output_wav],
            check=False,
        )
        return

    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", concat_list_path,
         "-c:a", "pcm_s16le", output_wav],
        check=True,
    )

    shutil.rmtree(TEMP_AUDIO_DIR, ignore_errors=True)


def main():
    full_tts_audio = "temp_full_tts.wav"

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        cfg = data[0]
        video_path = cfg["video_path"]
        subtitle_path = cfg["subtitle_path"]
        segments = cfg["segments"]

        print("Creating Audio (Sync with SRT Mode)...")
        generate_optimized_audio(segments, full_tts_audio)

        print("Rendering Video...")
        subtitle_style = subtitle_path.replace("\\", "/").replace(":", "\\:")

        # ==============================
        #  SUBTITLE DYNAMIC BOX — WHITE
        # ==============================
        # ==============================
        #  SUBTITLE DYNAMIC BOX — WHITE
        #  Strategy: 2 Passes
        #  1. Draw Box (Style 3, Text Transparent, Box White)
        #  2. Draw Text (Style 1, Text Yellow, Outline Black)
        # ==============================
        
        # Pass 1: Box Only
        # PrimaryColour=&HFF000000 (Transparent)
        # OutlineColour=&H00FFFFFF (White Box) - &H00 is opaque, &H80 is 50%
        # BorderStyle=3 (Opaque Box)
        video_filter_box = (
            f"[vs]subtitles={subtitle_style}:force_style="
            f"'FontName={SUB_FONT},"
            f"FontSize={SUB_FONT_SIZE},"
            f"Bold=1,Italic=1,"
            f"BorderStyle=3,"
            f"PrimaryColour=&HFF000000,"
            f"OutlineColour=&H00FFFFFF,"
            f"BackColour=&H00000000,"
            f"MarginV={SUB_MARGIN_V},"
            f"Outline=5,"
            f"Shadow=0'"
            f"[vbox]"
        )

        # Pass 2: Text Only
        # PrimaryColour=&H0000FFFF (Yellow) - Note: &H00FFFF is 00(B) FF(G) FF(R)
        # OutlineColour=&H00000000 (Black Outline)
        # BorderStyle=1 (Normal Outline)
        video_filter_text = (
            f"[vbox]subtitles={subtitle_style}:force_style="
            f"'FontName={SUB_FONT},"
            f"FontSize={SUB_FONT_SIZE},"
            f"Bold=1,Italic=1,"
            f"BorderStyle=1,"
            f"PrimaryColour={COLOR_TEXT},"
            f"OutlineColour={COLOR_OUTLINE},"
            f"BackColour=&HFF000000,"
            f"MarginV={SUB_MARGIN_V},"
            f"Outline=1,"
            f"Shadow=0'"
            f"[vout]"
        )

        video_filter = f"[0:v]scale=-2:{MAX_HEIGHT}[vs];{video_filter_box};{video_filter_text}"

        audio_filter = (
            "[0:a]volume=0.1[aorig];"
            "[1:a]volume=1.0[atts];"
            "[aorig][atts]amix=inputs=2:normalize=0:dropout_transition=0[aout]"
        )

        filter_complex = f"{video_filter};{audio_filter}"

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-threads", FFMPEG_THREADS,
            "-i", video_path,
            "-i", full_tts_audio,
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", VIDEO_PRESET, "-crf", VIDEO_CRF,
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            OUTPUT_FILE,
        ]

        subprocess.run(cmd, check=True)
        print(f"Done! Saved to {OUTPUT_FILE}")

    except Exception as e:
        print(f"Fatal Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if os.path.exists(full_tts_audio):
            try:
                os.remove(full_tts_audio)
            except OSError:
                pass


if __name__ == "__main__":
    main()
