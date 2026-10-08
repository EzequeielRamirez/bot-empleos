"""Convierte la imagen vertical en un video corto (Reel) con un zoom suave."""
import subprocess

import imageio_ffmpeg

SEGUNDOS = 8
FPS = 30


def generar_video(imagen_vertical, destino):
    cuadros = SEGUNDOS * FPS
    filtro = (f"scale=2160:-1,zoompan=z='min(zoom+0.0006,1.12)':d={cuadros}:"
              f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={FPS},scale=out_range=tv,format=yuv420p")
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(imagen_vertical),
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",  # Instagram procesa mejor con pista de audio
        "-vf", filtro, "-t", str(SEGUNDOS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
        str(destino),
    ], check=True)
    return destino
