import { useEffect, useState } from "react";
import * as THREE from "three";

export const GALLERY_FONT = '"Cormorant Garamond", "Playfair Display", Georgia, serif';

/** Loads the gallery serif once and returns a counter that changes when it is ready (use as a memo dependency). */
export function useGalleryFont() {
  const [ready, setReady] = useState(0);
  useEffect(() => {
    if (!document.getElementById("bl-font")) {
      const l = document.createElement("link");
      l.id = "bl-font";
      l.rel = "stylesheet";
      l.href = "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&display=swap";
      document.head.appendChild(l);
    }
    const fonts = document.fonts;
    if (!fonts) return;
    Promise.all([
      fonts.load('500 40px "Cormorant Garamond"'),
      fonts.load('600 40px "Cormorant Garamond"'),
      fonts.load('700 40px "Cormorant Garamond"'),
    ])
      .then(() => setReady(1))
      .catch(() => {});
  }, []);
  return ready;
}

/**
 * Draws letter-spaced text centred on cx. Spacing is applied manually (canvas letterSpacing is not universal and
 * adds trailing space that pushes text off-centre) and the whole line is shrunk so it can never be cut off.
 */
export function drawSpaced(
  c: CanvasRenderingContext2D,
  text: string,
  cx: number,
  cy: number,
  size: number,
  weight: number,
  spacing: number,
  maxW: number,
) {
  const chars = Array.from(text);
  const measure = (s: number, sp: number) => {
    c.font = `${weight} ${s}px ${GALLERY_FONT}`;
    const widths = chars.map((ch) => c.measureText(ch).width);
    return { widths, total: widths.reduce((a, b) => a + b, 0) + sp * (chars.length - 1) };
  };
  let s = size;
  let sp = spacing;
  let m = measure(s, sp);
  if (m.total > maxW) {
    const k = maxW / m.total;
    s *= k;
    sp *= k;
    m = measure(s, sp);
  }
  c.textAlign = "left";
  c.textBaseline = "middle";
  let x = cx - m.total / 2;
  chars.forEach((ch, i) => {
    c.fillText(ch, x, cy);
    x += m.widths[i] + sp;
  });
}

export function wrapText(c: CanvasRenderingContext2D, text: string, maxW: number) {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(/\s+/)) {
    const test = line ? `${line} ${word}` : word;
    if (c.measureText(test).width > maxW && line) {
      lines.push(line);
      line = word;
    } else line = test;
  }
  if (line) lines.push(line);
  return lines;
}

export function makeTexture(cv: HTMLCanvasElement) {
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

export function glowTexture() {
  const cv = document.createElement("canvas");
  cv.width = cv.height = 256;
  const c = cv.getContext("2d")!;
  const g = c.createRadialGradient(128, 128, 0, 128, 128, 128);
  g.addColorStop(0, "rgba(255,190,100,0.9)");
  g.addColorStop(0.45, "rgba(255,150,60,0.35)");
  g.addColorStop(1, "rgba(255,120,40,0)");
  c.fillStyle = g;
  c.fillRect(0, 0, 256, 256);
  return makeTexture(cv);
}
