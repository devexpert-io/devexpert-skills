#!/usr/bin/env python3
from __future__ import annotations
"""
Transcribe un vídeo, genera subtítulos (SRT/ASS karaoke), ajusta el nivel de audio al pico -1 dBFS,
quema subtítulos en MP4 y crea un caption.

Requisitos: ffmpeg, Python 3.8+, `pip install --user openai-whisper`.
"""

import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import tempfile
from datetime import timedelta

import whisper

MAX_CHARS_PER_LINE = 18
MAX_LINES = 2
MAX_WORDS_PER_CUE = 3
DROP_FIRST_FRAME_SEC = 0.0  # sin recorte automático del primer frame
DEFAULT_MODEL = "small"
DEFAULT_LANG = "es"
DEFAULT_CRF = 20
DEFAULT_CAPTION_LEN = 240
DEFAULT_KARAOKE = True
DEFAULT_AUTO_GAIN = True
KEEP_AUDIO = False  # siempre borrar el WAV final normalizado


def sec_to_srt(ts: float) -> str:
    # Use divmod to avoid accumulating minutes/seconds twice and keep millis within 0-999
    hours, rem = divmod(int(ts), 3600)
    minutes, seconds = divmod(rem, 60)
    millis = int(round((ts - int(ts)) * 1000))
    # carry overflows (e.g. 59.9995 rounds to 60.000)
    if millis >= 1000:
        millis -= 1000
        seconds += 1
        if seconds >= 60:
            seconds -= 60
            minutes += 1
            if minutes >= 60:
                minutes -= 60
                hours += 1
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def write_srt(segments, out_path: pathlib.Path):
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = sec_to_srt(seg['start'])
        end = sec_to_srt(seg['end'])
        text = wrap_text(seg.get('text', ''), max_chars=MAX_CHARS_PER_LINE, max_lines=MAX_LINES)
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def sanitize(text: str) -> str:
    return text.replace('\u266a', '').strip()


def write_txt(segments, out_path: pathlib.Path):
    full = " ".join(sanitize(seg.get('text', '')) for seg in segments)
    out_path.write_text(full.strip(), encoding="utf-8")


def wrap_text(text: str, max_chars: int = MAX_CHARS_PER_LINE, max_lines: int = MAX_LINES) -> str:
    words = text.strip().split()
    lines, current = [], ""
    for w in words:
        candidate = (current + " " + w).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = w
        if len(lines) == max_lines - 1 and current and len(current) > max_chars:
            # force break early if last line would overflow badly
            pass
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        # merge overflow into the last line
        lines = lines[: max_lines - 1] + [" ".join(lines[max_lines - 1 :])]
    return "\n".join(lines)


def write_ass_karaoke(segments, out_path: pathlib.Path):
    header = textwrap.dedent(
        """
        [Script Info]
        ScriptType: v4.00+
        WrapStyle: 2
        PlayResX: 1920
        PlayResY: 1080
        ScaledBorderAndShadow: yes

        [V4+ Styles]
        Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        Style: Default,Arial,54,&H00FFFFFF,&H0078AAFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,1,2,90,90,220,0

        [Events]
        Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        """
    ).strip() + "\n"

    def ass_time(ts: float) -> str:
        hours, rem = divmod(int(ts), 3600)
        minutes, seconds = divmod(rem, 60)
        centiseconds = int(round((ts - int(ts)) * 100))
        if centiseconds >= 100:
            centiseconds -= 100
            seconds += 1
            if seconds >= 60:
                seconds -= 60
                minutes += 1
                if minutes >= 60:
                    minutes -= 60
                    hours += 1
        return f"{hours:d}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    def wrap_karaoke_words(words, max_chars: int = MAX_CHARS_PER_LINE, max_lines: int = MAX_LINES):
        lines = [[]]
        current_len = 0
        for w in words:
            clean = sanitize(w['word'])
            if not clean:
                continue
            token_len = len(clean) + 1  # include space
            if current_len + token_len > max_chars and len(lines) < max_lines:
                lines.append([])
                current_len = 0
            lines[-1].append(w)
            current_len += token_len
        # flatten with \N between lines
        parts = []
        for li, line_words in enumerate(lines):
            if li and line_words:
                parts.append("\\N")
            for w in line_words:
                duration_cs = max(1, int(round((w['end'] - w['start']) * 100)))
                parts.append(f"{{\\k{duration_cs}}}{sanitize(w['word'])}")
        return " ".join(parts)

    events = []
    for seg in segments:
        start = ass_time(seg['start'])
        end = ass_time(seg['end'])
        words = seg.get('words') or []
        if words:
            text = wrap_karaoke_words(words, max_chars=32, max_lines=2)
        else:
            text = wrap_text(seg.get('text', ''), max_chars=32, max_lines=2).replace("\n", "\\N")
        dialogue = f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"
        events.append(dialogue)

    out_path.write_text(header + "\n" + "\n".join(events) + "\n", encoding="utf-8")


def make_caption(full_text: str, max_chars: int = 240) -> str:
    # Very light heuristic summary: first 2 sentences trimmed to max_chars.
    sentences = re.split(r"(?<=[.!?])\s+", full_text.strip())
    caption = " ".join(sentences[:2]).strip()
    if not caption:
        caption = full_text.strip()
    if len(caption) > max_chars:
        caption = caption[: max_chars - 1].rstrip() + "…"
    return caption


def split_segments_for_brevity(segments, max_words: int = MAX_WORDS_PER_CUE):
    """Split long segments into smaller cues so fewer words appear on screen."""
    new_segments = []
    for seg in segments:
        words = seg.get('words')
        if words and len(words) > max_words:
            for i in range(0, len(words), max_words):
                chunk = words[i : i + max_words]
                text = " ".join(sanitize(w['word']) for w in chunk).strip()
                new_segments.append(
                    {
                        'start': chunk[0]['start'],
                        'end': chunk[-1]['end'],
                        'text': text,
                        'words': chunk,
                    }
                )
        else:
            new_segments.append(seg)
    return new_segments


def extract_wav(input_path: pathlib.Path, wav_path: pathlib.Path):
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "48000",
        "-sample_fmt",
        "s16",
        str(wav_path),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def normalize_audio(wav_in: pathlib.Path, wav_out: pathlib.Path):
    """Deprecated: mantenido por compatibilidad interna (no se usa)."""
    shutil.copyfile(wav_in, wav_out)


def apply_gain(wav_in: pathlib.Path, wav_out: pathlib.Path, gain_db: float = 0.0):
    """Aplica ganancia simple con limitador suave para evitar clipping."""
    if abs(gain_db) < 0.01:
        shutil.copyfile(wav_in, wav_out)
        return
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(wav_in),
        "-af",
        f"volume={gain_db}dB,alimiter=limit=0.97",
        "-ar",
        "48000",
        str(wav_out),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def analyze_volume(wav_in: pathlib.Path):
    """
    Usa ffmpeg volumedetect para obtener mean_volume y max_volume en dBFS.
    Devuelve dict con keys 'mean' y 'max'. Si falla, None.
    """
    cmd = [
        "ffmpeg",
        "-i",
        str(wav_in),
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    ]
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = proc.stderr or ""
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", stderr)
    max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", stderr)
    if not max_match:
        return None
    return {
        "mean": float(mean_match.group(1)) if mean_match else None,
        "max": float(max_match.group(1)),
    }


def detect_leading_silence(wav_in: pathlib.Path, threshold_db: float = -50.0, min_silence: float = 0.30) -> float:
    """
    Devuelve el momento (s) donde acaba el primer silencio inicial.
    Si no encuentra silencio, devuelve 0.0.
    """
    cmd = [
        "ffmpeg",
        "-i",
        str(wav_in),
        "-af",
        f"silencedetect=n={threshold_db}dB:d={min_silence}",
        "-f",
        "null",
        "-",
    ]
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = proc.stderr or ""
    match = re.search(r"silence_end:\s*([0-9.]+)", stderr)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def compute_gain_to_peak(current_peak_db: float, clamp_db: float = 6.0, deadband_db: float = 0.3, target_peak_db: float = -1.0) -> float:
    """
    Calcula la ganancia necesaria para llevar el pico a target_peak_db (-1 dBFS por defecto).
    Limita la ganancia a +/- clamp_db y aplica deadband para evitar microcambios.
    """
    gain = target_peak_db - current_peak_db
    if abs(gain) < deadband_db:
        return 0.0
    if gain > clamp_db:
        gain = clamp_db
    if gain < -clamp_db:
        gain = -clamp_db
    return gain


def resample_wav(wav_in: pathlib.Path, wav_out: pathlib.Path, ar: int = 48000):
    """Re-muestrea WAV a la frecuencia indicada."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(wav_in),
        "-ar",
        str(ar),
        str(wav_out),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def resample_wav_with_offset(wav_in: pathlib.Path, wav_out: pathlib.Path, ar: int, offset: float):
    """Re-muestrea WAV aplicando un desplazamiento inicial."""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{offset:.3f}",
        "-i",
        str(wav_in),
        "-ar",
        str(ar),
        str(wav_out),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def burn_subs(
    input_path: pathlib.Path,
    subs_path: pathlib.Path,
    output_path: pathlib.Path,
    karaoke: bool,
    crf: int = 20,
    enhanced_audio: pathlib.Path | None = None,
    start_offset: float = 0.0,
):
    base_vf = f"ass={subs_path}" if karaoke else f"subtitles={subs_path}"
    if start_offset > 0:
        # Corte preciso por filtro para evitar frame negro que deja el seek rápido
        vf = f"trim=start={start_offset:.3f},setpts=PTS-STARTPTS,{base_vf}"
    else:
        vf = base_vf

    cmd = ["ffmpeg", "-y", "-i", str(input_path)]
    if enhanced_audio:
        cmd += ["-i", str(enhanced_audio)]
    cmd += ["-vf", vf, "-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast"]
    if enhanced_audio:
        cmd += [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-af",
            "asetpts=PTS-STARTPTS",
        ]
    else:
        cmd += ["-c:a", "copy"]
    cmd.append(str(output_path))
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="Transcribe video, genera/ quema subtítulos y caption (parámetros fijos).")
    parser.add_argument("input", help="Ruta del video (mov/mp4/etc)")
    args = parser.parse_args()

    input_path = pathlib.Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"No encuentro el archivo: {input_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    base = input_path.stem
    srt_path = out_dir / f"{base}.srt"
    txt_path = out_dir / f"{base}.txt"
    ass_path = out_dir / f"{base}.ass"
    burned_path = out_dir / f"{base}_subtitled.mp4"

    # Normalizar audio y usarlo para transcripción y mux
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = pathlib.Path(tmpdir)
        raw_wav = tmpdir_path / "audio_raw.wav"
        norm_wav = tmpdir_path / "audio_norm.wav"
        print("Extrayendo audio a WAV…")
        extract_wav(input_path, raw_wav)
        leading_silence = 0.0  # sin recorte automático
        gain_to_apply = 0.0
        if DEFAULT_AUTO_GAIN:
            vol = analyze_volume(raw_wav)
            if vol and vol.get("max") is not None:
                gain_to_apply = compute_gain_to_peak(
                    current_peak_db=vol["max"],
                    clamp_db=6.0,
                    deadband_db=0.3,
                    target_peak_db=-1.0,
                )
                print(
                    f"Auto-gain: pico actual {vol['max']:.2f} dBFS → objetivo -1.00 dBFS, "
                    f"ganancia {gain_to_apply:+.2f} dB"
                )
            else:
                print("Auto-gain: no se pudo medir, se deja 0 dB.")
        print(f"Ajustando ganancia simple ({gain_to_apply:+.2f} dB) con limitador…")
        apply_gain(raw_wav, norm_wav, gain_db=gain_to_apply)
        # Sin recorte automático de silencio ni primer frame
        trimmed_norm_wav = norm_wav
        mux_offset = 0.0
        mux_wav = trimmed_norm_wav
        print("Recorte de silencio inicial y primer frame: desactivado (offset 0.000s).")
        print("Resampleando a 16 kHz para transcripción…")
        resamp16 = tmpdir_path / "audio_16k.wav"
        resample_wav(norm_wav, resamp16, ar=16000)
        print(f"Cargando modelo Whisper '{DEFAULT_MODEL}' (esto puede tardar la primera vez)...")
        audio_for_transcript = resamp16
        final_norm_wav = out_dir / f"{base}_normalized.wav"
        final_norm_wav.write_bytes(mux_wav.read_bytes())
        enhanced_audio_path = final_norm_wav

        model = whisper.load_model(DEFAULT_MODEL)
        print("Transcribiendo…")
        result = model.transcribe(str(audio_for_transcript), language=DEFAULT_LANG, word_timestamps=DEFAULT_KARAOKE)
        segments = split_segments_for_brevity(result.get('segments', []), max_words=MAX_WORDS_PER_CUE)
        if not segments:
            print("No se obtuvieron segmentos.", file=sys.stderr)
            sys.exit(1)

        print(f"Escribiendo {srt_path.name} y {txt_path.name}…")
        write_srt(segments, srt_path)
        write_txt(segments, txt_path)

        # Caption para redes
        full_text = txt_path.read_text(encoding="utf-8")
        caption = make_caption(full_text, max_chars=DEFAULT_CAPTION_LEN)
        caption_path = out_dir / f"{base}_caption.txt"
        caption_path.write_text(caption, encoding="utf-8")

        # Subtítulos a quemar
        subs_for_burn = srt_path
        if DEFAULT_KARAOKE:
            print(f"Generando ASS karaoke {ass_path.name}…")
            write_ass_karaoke(segments, ass_path)
            subs_for_burn = ass_path

        print(f"Quemando subtítulos en {burned_path.name}…")
        burn_subs(
            input_path,
            subs_for_burn,
            burned_path,
            karaoke=DEFAULT_KARAOKE,
            crf=DEFAULT_CRF,
            enhanced_audio=enhanced_audio_path,
            start_offset=mux_offset,
        )

        print("Listo. Salidas:")
        print("-", srt_path)
        print("-", ass_path if DEFAULT_KARAOKE else "(ASS omitido)")
        print("-", txt_path)
        print("-", caption_path)
        print("-", burned_path)
        if not KEEP_AUDIO:
            try:
                enhanced_audio_path.unlink(missing_ok=True)
            except Exception:
                pass


if __name__ == "__main__":
    main()
