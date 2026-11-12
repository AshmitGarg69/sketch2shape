import { useEffect, useMemo } from "react";
import { Edges } from "@react-three/drei";
import { GALLERY_FONT, drawSpaced, makeTexture, useGalleryFont, wrapText } from "./galleryText";

const W = 1024;
const H = 640;

function plaqueTexture(title: string, text: string) {
  const cv = document.createElement("canvas");
  cv.width = W;
  cv.height = H;
  const c = cv.getContext("2d")!;

  c.fillStyle = "#15100b";
  c.fillRect(0, 0, W, H);
  const bg = c.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, "rgba(255,190,100,0.10)");
  bg.addColorStop(1, "rgba(255,190,100,0.02)");
  c.fillStyle = bg;
  c.fillRect(0, 0, W, H);

  // double gold border
  const gold = c.createLinearGradient(0, 0, W, H);
  gold.addColorStop(0, "#f0d58a");
  gold.addColorStop(0.5, "#b98a34");
  gold.addColorStop(1, "#f0d58a");
  c.strokeStyle = gold;
  c.lineWidth = 6;
  c.strokeRect(16, 16, W - 32, H - 32);
  c.lineWidth = 2;
  c.strokeRect(32, 32, W - 64, H - 64);

  // title
  c.fillStyle = "#f0d58a";
  c.shadowColor = "rgba(255,190,90,0.6)";
  c.shadowBlur = 14;
  drawSpaced(c, title.toUpperCase(), W / 2, 120, 50, 700, 8, W - 160);
  c.shadowBlur = 0;

  // divider with diamond
  c.strokeStyle = "#b98a34";
  c.lineWidth = 2;
  c.beginPath();
  c.moveTo(W / 2 - 200, 178);
  c.lineTo(W / 2 - 14, 178);
  c.moveTo(W / 2 + 14, 178);
  c.lineTo(W / 2 + 200, 178);
  c.stroke();
  c.fillStyle = "#e2b45a";
  c.beginPath();
  c.moveTo(W / 2, 168);
  c.lineTo(W / 2 + 9, 178);
  c.lineTo(W / 2, 188);
  c.lineTo(W / 2 - 9, 178);
  c.fill();

  // body
  c.fillStyle = "#f6edd6";
  c.font = `500 44px ${GALLERY_FONT}`;
  c.textAlign = "center";
  c.textBaseline = "middle";
  const lines = wrapText(c, text, W - 170).slice(0, 6);
  const lh = 58;
  const top = 250 + (6 - lines.length) * (lh / 2) * 0.5;
  lines.forEach((ln, i) => c.fillText(ln, W / 2, top + i * lh));

  c.fillStyle = "rgba(217,201,163,0.7)";
  drawSpaced(c, "THE BOOK LANTERN · 3D STUDIO", W / 2, H - 62, 22, 600, 6, W - 200);

  return makeTexture(cv);
}

interface Props {
  position: [number, number, number];
  rotationY: number;
  title: string;
  text: string;
}

/** Wall plaque: ivory text on dark stone with a softly glowing warm border. Faces +Z at rotationY = 0. */
export function Plaque({ position, rotationY, title, text }: Props) {
  const fontReady = useGalleryFont();
  const tex = useMemo(() => plaqueTexture(title, text), [title, text, fontReady]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      <mesh>
        <boxGeometry args={[2.5, 1.58, 0.05]} />
        <meshStandardMaterial color="#1a120a" emissive="#ffa84d" emissiveIntensity={0.9} roughness={0.6} />
        <Edges color="#c9a24f" />
      </mesh>
      <mesh position={[0, 0, 0.03]}>
        <planeGeometry args={[2.4, 1.5]} />
        <meshBasicMaterial map={tex} toneMapped={false} />
      </mesh>
      <pointLight position={[0, 0, 0.9]} intensity={1.6} distance={4} decay={2} color="#ffb45c" />
    </group>
  );
}
