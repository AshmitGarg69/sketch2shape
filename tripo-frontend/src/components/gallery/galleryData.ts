export interface Piece {
  id: string;
  label: string;
  url: string;
  plaqueTitle: string;
  plaqueText: string;
}

export const PIECES: Piece[] = [
  {
    id: "chair",
    label: "Designer Chair",
    url: "/models/chair.glb",
    plaqueTitle: "Ergonomic & Spatial Design",
    plaqueText:
      "Modern interior seating with balanced silhouette, clean quad topology and true-to-life studio materials.",
  },
  {
    id: "car",
    label: "Sedan Car",
    url: "/models/car.glb",
    plaqueTitle: "Automotive Design",
    plaqueText:
      "Precision vehicle prototyping and digital twins with accurate aerodynamics and sleek surface styling.",
  },
  {
    id: "mug",
    label: "Ceramic Mug",
    url: "/models/mug.glb",
    plaqueTitle: "Tactile Consumer Goods",
    plaqueText:
      "Comfortable ergonomic handle, glazed ceramic gloss and refined curvature designed for everyday elegance.",
  },
  {
    id: "lamp",
    label: "Studio Desk Lamp",
    url: "/models/lamp.glb",
    plaqueTitle: "Architectural Lighting",
    plaqueText:
      "Adjustable mechanical joints, spun metal shade and focused luminaire optics for creative workspaces.",
  },
  {
    id: "character",
    label: "Astronaut Character",
    url: "/models/character.glb",
    plaqueTitle: "Character & Detail Work",
    plaqueText:
      "Fine, organic humanoid detail sculpted, textured and optimised to perform seamlessly in real time.",
  },
  {
    id: "shuttle",
    label: "Space Shuttle",
    url: "/models/spacecraft.glb",
    plaqueTitle: "Interactive Web Showcases",
    plaqueText:
      "Lightweight GLB spacecraft assets and scroll-driven experiences that load fast on phones and desktops alike.",
  },
  {
    id: "flower",
    label: "Potted Flower",
    url: "/models/flower.glb",
    plaqueTitle: "Natural & Botanical Forms",
    plaqueText:
      "Delicate botanical shapes, organic petals and clean pot geometry crafted for vibrant real-time rendering.",
  },
  {
    id: "suv",
    label: "Concept SUV",
    url: "/models/suv.glb",
    plaqueTitle: "Concept & World Building",
    plaqueText:
      "Imaginative off-road vehicles, rigs and sci-fi transport that give games and brand experiences depth.",
  },
  {
    id: "table",
    label: "Wooden Table",
    url: "/models/table.glb",
    plaqueTitle: "Custom 3D Furniture",
    plaqueText:
      "Interior assets modelled with clean topology, realistic wood grain and true-to-life studio lighting.",
  },
  {
    id: "bottle",
    label: "Glass Tumbler",
    url: "/models/bottle.glb",
    plaqueTitle: "Product Visualisation",
    plaqueText:
      "Translucent material properties and cylindrical glass rendering engineered for e-commerce and packaging.",
  },
  {
    id: "train",
    label: "Locomotive",
    url: "/models/train.glb",
    plaqueTitle: "Industrial Engineering",
    plaqueText:
      "Heavy transport machinery and rolling stock engineered with robust industrial dimensions and materials.",
  },
  {
    id: "doodle",
    label: "Abstract Sculpture",
    url: "/models/doodle.glb",
    plaqueTitle: "Generative Art Forms",
    plaqueText:
      "Complex organic loops and expressive procedural volumes synthesized instantly from freehand line strokes.",
  },
];


// Corridor runs along -Z. The visitor enters at z = +8 and ends at the sign on END_Z.
export const FIRST_Z = -8;
export const SPACING = 6.5;
export const END_Z = -88;
export const HALF_W = 4.5;
export const HEIGHT = 5.4;
export const PED_H = 1;

/** Pieces alternate left/right so visitors discover them while travelling. */
export function pieceSlot(i: number) {
  const side = i % 2 === 0 ? -1 : 1;
  return { side, x: side * 2.5, z: FIRST_Z - i * SPACING };
}

/** Wall plaque position for a piece: same wall, towards the visitor, inside the recessed panel. */
export function plaqueSlot(i: number) {
  const { side, z } = pieceSlot(i);
  return {
    position: [side * (HALF_W - 0.1), 2.2, z + 1.7] as [number, number, number],
    rotationY: -side * (Math.PI / 2), // left wall (side -1) faces +X, right wall faces -X
  };
}
