import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, Environment, Lightformer, OrbitControls } from "@react-three/drei";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { firstWorkflowStep, type WorkflowStep } from "@/lib/simulation";
import { wellAt } from "@/lib/simulation";

function stepTarget(item: WorkflowStep | undefined): [number, number, number] {
  if (!item) return [0, 3.1, -1.6];
  switch (item.op) {
    case "pick_tip":
      return [-2.1, 0.8, -1.8];
    case "aspirate":
      return [-3.2, 0.4, 1.35];
    case "drop_tip":
      return [-2.1, 0.9, -0.3];
    case "dispense":
    case "mix": {
      const w = wellAt(item.endMm);
      const col = w ? Number(w.slice(1)) - 1 : 0;
      const row = w ? "ABCDEFGH".indexOf(w[0] ?? "A") : 0;
      return [2.2 + (col - 5.5) * 0.29, item.op === "mix" ? 0.25 : 0.35, 0.3 + (row - 3.5) * 0.29];
    }
    default:
      return [0, 3.1, -1.6];
  }
}

function Plate({
  position,
  source = false,
}: {
  position: [number, number, number];
  source?: boolean;
}) {
  return (
    <group position={position}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[source ? 2.1 : 3.9, 0.28, source ? 2.3 : 2.7]} />
        <meshStandardMaterial color={source ? "#dbe7e6" : "#f3f4f6"} roughness={0.55} />
      </mesh>
      {Array.from({ length: source ? 12 : 96 }, (_, index) => {
        const cols = source ? 3 : 12;
        const rows = source ? 4 : 8;
        const x = ((index % cols) - (cols - 1) / 2) * (source ? 0.48 : 0.29);
        const z = (Math.floor(index / cols) - (rows - 1) / 2) * (source ? 0.48 : 0.29);
        return (
          <mesh key={index} position={[x, 0.19, z]}>
            <cylinderGeometry args={[source ? 0.16 : 0.095, source ? 0.13 : 0.075, 0.11, 12]} />
            <meshStandardMaterial color={source ? "#9fc8c2" : "#ffffff"} roughness={0.35} />
          </mesh>
        );
      })}
    </group>
  );
}

function Robot({ step, steps }: { step: number; steps: WorkflowStep[] }) {
  const carriage = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const pulse = useRef<THREE.Mesh>(null);
  const target = stepTarget(steps[step]);
  useEffect(() => {
    if (pulse.current) pulse.current.scale.setScalar(0.01);
  }, [step]);
  useFrame((state, rawDelta) => {
    const dt = Math.min(rawDelta, 0.05);
    const ease = 1 - Math.exp(-4.5 * dt);
    if (carriage.current) {
      carriage.current.position.x = THREE.MathUtils.lerp(
        carriage.current.position.x,
        target[0],
        ease,
      );
      carriage.current.position.z = THREE.MathUtils.lerp(
        carriage.current.position.z,
        target[2],
        ease,
      );
    }
    if (head.current) {
      const mix = steps[step]?.op === "mix" ? Math.sin(state.clock.elapsedTime * 10) * 0.16 : 0;
      head.current.position.y = THREE.MathUtils.lerp(
        head.current.position.y,
        target[1] + mix,
        ease,
      );
    }
    if (pulse.current && steps[step]?.op === "dispense") {
      const s = 0.3 + (Math.sin(state.clock.elapsedTime * 5) + 1) * 0.25;
      pulse.current.scale.setScalar(s);
    }
  });
  return (
    <group>
      <mesh position={[-4.8, 2.55, 0]} castShadow>
        <boxGeometry args={[0.7, 3.65, 0.8]} />
        <meshStandardMaterial color="#252a33" metalness={0.7} roughness={0.25} />
      </mesh>
      <mesh position={[0, 4.15, 0]} castShadow>
        <boxGeometry args={[10, 0.55, 0.72]} />
        <meshStandardMaterial color="#353b46" metalness={0.72} roughness={0.22} />
      </mesh>
      <group ref={carriage} position={[0, 3.1, -1.6]}>
        <mesh position={[0, 1.45, 0]} castShadow>
          <boxGeometry args={[1.35, 0.8, 1.05]} />
          <meshStandardMaterial color="#2952cc" roughness={0.3} />
        </mesh>
        <group ref={head}>
          <mesh position={[0, -0.95, 0]} castShadow>
            <boxGeometry args={[1.05, 1.5, 0.85]} />
            <meshStandardMaterial color="#eceff3" roughness={0.38} />
          </mesh>
          {[-0.27, -0.09, 0.09, 0.27].map((x) => (
            <mesh key={x} position={[x, -1.85, 0]}>
              <cylinderGeometry args={[0.035, 0.018, 0.85, 10]} />
              <meshStandardMaterial color="#3f4651" metalness={0.7} />
            </mesh>
          ))}
          <mesh ref={pulse} position={[0, -2.35, 0]}>
            <sphereGeometry args={[0.16, 16, 16]} />
            <meshBasicMaterial color="#2952cc" transparent opacity={0.35} />
          </mesh>
        </group>
      </group>
    </group>
  );
}

function Deck({ step, steps }: { step: number; steps: WorkflowStep[] }) {
  return (
    <>
      <mesh position={[0, -0.2, 0]} receiveShadow>
        <boxGeometry args={[12, 0.5, 7]} />
        <meshStandardMaterial color="#f7f8fa" roughness={0.75} />
      </mesh>
      <Plate position={[-3.2, 0.2, 1.35]} source />
      <Plate position={[2.2, 0.2, 0.3]} />
      <mesh position={[-2.1, 0.2, -1.8]}>
        <boxGeometry args={[1.5, 0.35, 1.5]} />
        <meshStandardMaterial color="#d4d8df" />
      </mesh>
      <Robot step={step} steps={steps} />
      <ContactShadows position={[0, 0.05, 0]} opacity={0.18} scale={13} blur={2.5} />
    </>
  );
}

export function LabDeck3D({
  step,
  steps = [firstWorkflowStep],
}: {
  step: number;
  steps?: WorkflowStep[];
}) {
  return (
    <div className="h-[390px] w-full border border-border bg-workspace">
      <Canvas shadows dpr={[1, 1.4]} camera={{ position: [10, 8, 11], fov: 42 }}>
        <color attach="background" args={["#fafafa"]} />
        <ambientLight intensity={1.6} />
        <directionalLight
          position={[6, 16, 8]}
          intensity={3.2}
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
        />
        <Environment>
          <Lightformer intensity={2.8} position={[0, 14, 2]} scale={[14, 10, 1]} />
        </Environment>
        <Deck step={step} steps={steps} />
        <OrbitControls
          target={[0, 2, 0]}
          minDistance={8}
          maxDistance={19}
          minPolarAngle={0.55}
          maxPolarAngle={1.35}
        />
      </Canvas>
    </div>
  );
}
