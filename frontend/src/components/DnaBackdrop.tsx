import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

const ink = "#b8c7d3",
  blue = "#aac2dc",
  green = "#a3c9c2";
type Segment = { a: THREE.Vector3; b: THREE.Vector3; tone: number; radius: number };

function Facet({
  a,
  b,
  color,
  radius,
}: {
  a: THREE.Vector3;
  b: THREE.Vector3;
  color: string;
  radius: number;
}) {
  const midpoint = useMemo(() => a.clone().add(b).multiplyScalar(0.5), [a, b]);
  const direction = useMemo(() => b.clone().sub(a), [a, b]);
  const quaternion = useMemo(
    () =>
      new THREE.Quaternion().setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        direction.clone().normalize(),
      ),
    [direction],
  );
  return (
    <mesh position={midpoint} quaternion={quaternion}>
      <cylinderGeometry args={[radius, radius, direction.length(), 8, 1]} />
      <meshStandardMaterial color={color} flatShading roughness={0.9} />
    </mesh>
  );
}

function Strand({
  offset,
  rise,
  depth,
  lean,
  phase,
  size,
}: {
  offset: number;
  rise: number;
  depth: number;
  lean: number;
  phase: number;
  size: number;
}) {
  const group = useRef<THREE.Group>(null);
  const { segments, nodes } = useMemo(() => {
    const segments: Segment[] = [],
      nodes: { point: THREE.Vector3; tone: number }[] = [];
    const side: THREE.Vector3[][] = [[], []];
    for (let i = 0; i < 38; i++) {
      const t = i * 0.29 + phase;
      const y = (i - 18.5) * 0.24;
      for (let s = 0; s < 2; s++) {
        const angle = t + s * Math.PI;
        const point = new THREE.Vector3(Math.cos(angle) * 0.62, y, Math.sin(angle) * 0.62);
        side[s]?.push(point);
        if (i % 3 === 0) nodes.push({ point, tone: s });
      }
      if (i % 4 === 0)
        segments.push({
          a: side[0]?.[i] ?? new THREE.Vector3(),
          b: side[1]?.[i] ?? new THREE.Vector3(),
          tone: 0,
          radius: 0.015,
        });
      if (i > 0)
        for (let s = 0; s < 2; s++)
          segments.push({
            a: side[s]?.[i - 1] ?? new THREE.Vector3(),
            b: side[s]?.[i] ?? new THREE.Vector3(),
            tone: s + 1,
            radius: 0.026,
          });
    }
    return { segments, nodes };
  }, [phase]);
  useFrame((state, delta) => {
    if (!group.current) return;
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      group.current.rotation.y += Math.min(delta, 0.05) * (offset < 0 ? 0.1 : -0.09);
      group.current.rotation.x = 0.24 + Math.sin(state.clock.elapsedTime * 0.17 + phase) * 0.08;
      group.current.rotation.z = lean + Math.sin(state.clock.elapsedTime * 0.12 + phase) * 0.1;
    }
    group.current.position.x =
      offset + Math.sin(state.clock.elapsedTime * 0.1 + phase) * 0.18 + state.pointer.x * 0.1;
    group.current.position.y =
      rise + Math.cos(state.clock.elapsedTime * 0.12 + phase) * 0.16 + state.pointer.y * 0.1;
  });
  return (
    <group ref={group} position={[offset, rise, depth]} rotation={[0.24, 0, lean]} scale={size}>
      {segments.map((segment, i) => (
        <Facet
          key={i}
          a={segment.a}
          b={segment.b}
          radius={segment.radius}
          color={[ink, blue, green][segment.tone] ?? ink}
        />
      ))}
      {nodes.map(({ point, tone }, i) => (
        <mesh key={i} position={point}>
          <icosahedronGeometry args={[0.066, 0]} />
          <meshStandardMaterial color={tone ? green : blue} flatShading />
        </mesh>
      ))}
    </group>
  );
}

function Network() {
  const narrow = useThree((state) => state.size.width < 600);
  return (
    <>
      <ambientLight intensity={2} />
      <directionalLight position={[2, 6, 8]} intensity={1.8} />
      <Strand
        offset={narrow ? -2.8 : -6.1}
        rise={-1.1}
        depth={-3.2}
        lean={-0.88}
        phase={0.2}
        size={narrow ? 0.58 : 1.04}
      />
      <Strand
        offset={narrow ? 2.9 : 6.2}
        rise={1.25}
        depth={-3.5}
        lean={0.9}
        phase={1.3}
        size={narrow ? 0.58 : 1}
      />
      {!narrow && (
        <>
          <Strand offset={-8.7} rise={2.6} depth={-5.2} lean={-0.62} phase={2.1} size={0.72} />
          <Strand offset={8.8} rise={-2.5} depth={-5.4} lean={0.64} phase={0.7} size={0.7} />
        </>
      )}
    </>
  );
}

export function DnaBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 12], fov: 46 }}
        gl={{ antialias: true, alpha: true }}
      >
        <Network />
      </Canvas>
    </div>
  );
}
