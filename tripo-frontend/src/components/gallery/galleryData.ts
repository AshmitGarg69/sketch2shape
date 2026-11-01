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
    label: "Armchair",
    url: "/models/chair.glb",
    plaqueTitle: "Custom 3D Asset Creation",
    plaqueText:
      "Every object is modelled from your brief, from product furniture to props, with clean topology and true-to-life materials.",
  },
  {
    id: "hair",
    label: "Long Black Hair",
    url: "/models/hair.glb",
    plaqueTitle: "Character & Detail Work",
    plaqueText:
      "Fine, organic detail such as hair, fabric and skin is sculpted, textured and optimised so it stays beautiful in real time.",
  },
  {
    id: "bicycle",
    label: "Urban Bicycle",
    url: "/models/bicycle.glb",
    plaqueTitle: "Product Visualisation",
    plaqueText:
      "Photoreal digital twins let customers inspect every angle of a product before it exists, with no studio shoot required.",
  },
  {
    id: "rooster",
    label: "Rooster",
    url: "/models/rooster.glb",
    plaqueTitle: "Rapid Digital Prototyping",
    plaqueText:
      "Move from sketch to a viewable 3D prototype in days. Test shapes, colours and ideas early and iterate quickly.",
  },
  {
    id: "airship",
    label: "Airship",
    url: "/models/airship.glb",
    plaqueTitle: "Concept & World Building",
    plaqueText:
      "Imaginative vehicles, scenes and environments that give games, films and brand stories a world worth exploring.",
  },
  {
    id: "skeleton",
    label: "Skeleton",
    url: "/models/skeleton.glb",
    plaqueTitle: "Educational Models",
    plaqueText:
      "Anatomically careful models for learning and exhibitions, built to be rotated, explored and understood by everyone.",
  },
  {
    id: "shuttle",
    label: "Space Shuttle",
    url: "/models/shuttle.glb",
    plaqueTitle: "Interactive Web Showcases",
    plaqueText:
      "Lightweight GLB assets and scroll-driven experiences that load fast and run smoothly on phones and desktops alike.",
  },
  {
    id: "sakura",
    label: "Sakura",
    url: "/models/sakura.glb",
    plaqueTitle: "Natural & Organic Forms",
    plaqueText:
      "Trees, flowers and landscapes crafted with delicate geometry and warm lighting, ready for any engine or storefront.",
  },
];

// Corridor runs along -Z. The visitor enters at z = +8 and ends at the sign on END_Z.
export const FIRST_Z = -8;
export const SPACING = 6.5;
export const END_Z = -62;
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
