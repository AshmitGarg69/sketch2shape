import { Edges, Environment, Lightformer } from "@react-three/drei";
import { END_Z, FIRST_Z, HALF_W, HEIGHT, SPACING } from "./galleryData";
import { Plaque } from "./Plaque";

const LEN = 104;
const CZ = 8 - LEN / 2;
const ks = Array.from({ length: 16 }, (_, i) => i - 1); // -1..14

/** Warm stone corridor: floor, walls, carved panels, pilasters, ceiling, fog. Dark and cinematic, but readable. */
export function GalleryEnvironment() {
  return (
    <>
      <color attach="background" args={["#0a0705"]} />
      <fog attach="fog" args={["#0a0705", 14, 98]} />
      <ambientLight intensity={0.6} color="#ffd9a8" />
      <hemisphereLight args={["#ffe2b8", "#3a2a1a", 0.55]} />
      <Environment resolution={128}>
        <Lightformer
          form="rect"
          intensity={1.3}
          color="#ffbf80"
          position={[0, 5, -4]}
          scale={[8, 3, 1]}
          target={[0, 0, 0]}
        />
        <Lightformer
          form="rect"
          intensity={0.9}
          color="#ffd9a8"
          position={[6, 2, 2]}
          scale={[3, 5, 1]}
          target={[0, 0, 0]}
        />
        <Lightformer
          form="rect"
          intensity={0.9}
          color="#ffd9a8"
          position={[-6, 2, -2]}
          scale={[3, 5, 1]}
          target={[0, 0, 0]}
        />
      </Environment>

      {/* floor: polished dark stone with clearly visible tile lines */}
      <mesh rotation-x={-Math.PI / 2} position={[0, 0, CZ]} receiveShadow>
        <planeGeometry args={[HALF_W * 2, LEN]} />
        <meshStandardMaterial
          color="#201812"
          roughness={0.35}
          metalness={0.25}
        />
      </mesh>
      <gridHelper
        args={[LEN, LEN / 2, "#7a5a38", "#5a4329"]}
        position={[0, 0.004, CZ]}
      />

      {/* ceiling + warm cove strips */}
      <mesh rotation-x={Math.PI / 2} position={[0, HEIGHT, CZ]}>
        <planeGeometry args={[HALF_W * 2, LEN]} />
        <meshStandardMaterial color="#17120d" roughness={1} />
      </mesh>
      {[-1, 1].map((s) => (
        <mesh key={s} position={[s * (HALF_W - 0.25), HEIGHT - 0.12, CZ]}>
          <boxGeometry args={[0.12, 0.06, LEN]} />
          <meshStandardMaterial
            color="#000"
            emissive="#ffa84d"
            emissiveIntensity={1.8}
          />
        </mesh>
      ))}

      {/* end wall */}
      <mesh position={[0, HEIGHT / 2, END_Z - 0.2]} receiveShadow>
        <boxGeometry args={[HALF_W * 2 + 1, HEIGHT, 0.4]} />
        <meshStandardMaterial color="#2a1f16" roughness={0.95} />
      </mesh>

      {[-1, 1].map((s) => (
        <group key={s}>
          <mesh position={[s * (HALF_W + 0.2), HEIGHT / 2, CZ]} receiveShadow>
            <boxGeometry args={[0.4, HEIGHT, LEN]} />
            <meshStandardMaterial color="#2e231a" roughness={0.95} />
          </mesh>
          {ks.map((k) => (
            <group key={k}>
              {/* carved pilaster between bays */}
              <mesh
                position={[
                  s * (HALF_W - 0.2),
                  HEIGHT / 2,
                  FIRST_Z + SPACING / 2 - k * SPACING,
                ]}
                castShadow
              >
                <boxGeometry args={[0.55, HEIGHT, 0.55]} />
                <meshStandardMaterial
                  color="#3d2d1f"
                  roughness={0.8}
                  metalness={0.15}
                />
              </mesh>
              {/* recessed panel with antique-bronze frame, centred behind each piece */}
              <mesh
                position={[s * (HALF_W - 0.02), 2.6, FIRST_Z - k * SPACING]}
              >
                <boxGeometry args={[0.06, 3.4, SPACING - 1.5]} />
                <meshStandardMaterial color="#21170f" roughness={0.9} />
                <Edges color="#a87a42" />
              </mesh>
            </group>
          ))}
        </group>
      ))}

      {/* welcome plaques in the entrance bay */}
      <Plaque
        position={[-(HALF_W - 0.1), 2.2, FIRST_Z + SPACING - 0.3]}
        rotationY={Math.PI / 2}
        title="Our Design Philosophy"
        text="We believe every digital object should feel crafted, not generated. Form, light and detail come first, performance follows."
      />
      <Plaque
        position={[HALF_W - 0.1, 2.2, FIRST_Z + SPACING - 0.3]}
        rotationY={-Math.PI / 2}
        title="Custom 3D Modelling"
        text="From a single prop to a full collection, we build bespoke models for products, games, education and the web. Walk on to explore."
      />
    </>
  );
}
