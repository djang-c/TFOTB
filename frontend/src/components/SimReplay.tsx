"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Edges, Line, OrbitControls } from "@react-three/drei";
import { useMemo, useRef, useState } from "react";
import type { Group } from "three";
import type { SimRun } from "@/lib/api";

const S = 0.1; // mm -> scene units

const COLOR: Record<string, string> = {
  deck: "#e9edf0", tiprack: "#6d9ed6", source: "#5fae73", waste: "#a3abb3", plate: "#e7dc8f", tower: "#c4544d",
};

/** Kinematic replay of a recorded run: MuJoCo's z-up mm coordinates, drawn y-up. */
export default function SimReplay({ run }: { run: SimRun }) {
  const pts = run.trajectory.points;
  const failed = run.report.overall === "fail";
  const [t, setT] = useState(0); // 0..1 progress
  const [playing, setPlaying] = useState(true);

  return (
    <div className="overflow-hidden rounded-md border border-rule bg-white">
      <div className="relative h-[440px]">
        <Canvas camera={{ position: [30, 24, 26], fov: 38 }} dpr={[1, 2]}>
          <color attach="background" args={["#f7f9fa"]} />
          <ambientLight intensity={0.8} />
          <directionalLight position={[20, 40, 10]} intensity={1.2} />
          <group rotation={[-Math.PI / 2, 0, 0]} position={[-15, 0, 10]}>
            {run.scene.map((g) => (
              <mesh key={g.name} position={g.pos.map((v) => v * S) as [number, number, number]}>
                <boxGeometry args={g.size.map((v) => v * S) as [number, number, number]} />
                <meshStandardMaterial color={COLOR[g.name] ?? "#ccc"} transparent opacity={g.collides ? 0.9 : 1} />
                <Edges color={g.collides ? "#7a1f1a" : "#9aa5af"} />
              </mesh>
            ))}
            <Path pts={pts} t={t} failed={failed} />
            <Pipette pts={pts} t={t} setT={setT} playing={playing} setPlaying={setPlaying} />
          </group>
          <OrbitControls makeDefault enableDamping target={[0, 0, 0]} />
        </Canvas>
        <p className="pointer-events-none absolute left-3 top-3 rounded bg-white/90 px-2 py-1 text-xs font-medium">
          Recorded kinematic replay. Not live, not physics, not wet-lab validated.
        </p>
      </div>
      <div className="flex items-center gap-3 border-t border-rule px-4 py-2.5">
        <button onClick={() => { if (t >= 1) setT(0); setPlaying(!playing); }}
          className="w-16 rounded bg-ink px-2 py-1 text-sm font-medium text-white">
          {playing ? "Pause" : t >= 1 ? "Replay" : "Play"}
        </button>
        <input type="range" min={0} max={1000} value={Math.round(t * 1000)} aria-label="Replay position"
          onChange={(e) => { setPlaying(false); setT(Number(e.target.value) / 1000); }} className="flex-1 accent-[#17212e]" />
        <span className="w-24 text-right text-xs tabular-nums text-muted">
          step {Math.round(t * (pts.length - 1))} / {pts.length - 1}
        </span>
      </div>
    </div>
  );
}

function at(pts: number[][], t: number): [number, number, number] {
  const p = pts[Math.min(pts.length - 1, Math.round(t * (pts.length - 1)))] ?? [0, 0, 0];
  return [p[0] * S, p[1] * S, p[2] * S];
}

function Path({ pts, t, failed }: { pts: number[][]; t: number; failed: boolean }) {
  const all = useMemo(() => pts.map((p) => [p[0] * S, p[1] * S, p[2] * S] as [number, number, number]), [pts]);
  const done = all.slice(0, Math.max(2, Math.round(t * (all.length - 1)) + 1));
  const end = all[all.length - 1];
  return (
    <>
      {all.length > 1 && <Line points={all} color="#b9c2cb" lineWidth={1} dashed dashSize={0.6} gapSize={0.4} />}
      {done.length > 1 && <Line points={done} color="#1c56a3" lineWidth={2.5} />}
      {failed && end && t >= 0.999 && (
        <mesh position={end}>
          <sphereGeometry args={[0.9, 24, 24]} />
          <meshStandardMaterial color="#b3261e" emissive="#b3261e" emissiveIntensity={0.4} />
        </mesh>
      )}
    </>
  );
}

function Pipette({ pts, t, setT, playing, setPlaying }: {
  pts: number[][]; t: number; setT: (v: number) => void; playing: boolean; setPlaying: (v: boolean) => void;
}) {
  const ref = useRef<Group>(null);
  const duration = Math.max(4, pts.length / 60); // seconds
  useFrame((_, dt) => {
    if (playing) {
      const next = Math.min(1, t + dt / duration);
      setT(next);
      if (next >= 1) setPlaying(false);
    }
    ref.current?.position.set(...at(pts, t));
  });
  return (
    <group ref={ref}>
      {/* tip at origin, barrel extends up (+z in MuJoCo frame) */}
      <mesh position={[0, 0, 2.5]} rotation={[Math.PI / 2, 0, 0]}>
        <capsuleGeometry args={[0.25, 5, 4, 12]} />
        <meshStandardMaterial color="#17212e" />
      </mesh>
      <mesh position={[0, 0, 6]}>
        <boxGeometry args={[2.2, 2.2, 2]} />
        <meshStandardMaterial color="#56606c" />
      </mesh>
    </group>
  );
}
