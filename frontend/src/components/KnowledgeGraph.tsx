import { Canvas, useFrame } from "@react-three/fiber";
import { Line, OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { GraphEdge, GraphNode } from "@/lib/api";
import { clean, edgeKey, isHypothesisEdge } from "@/lib/graphStyle";

const colors: Record<string, string> = {
  disease: "#0d7266",
  gene: "#2f6f9f",
  variant: "#5b8fbf",
  phenotype: "#55667a",
  mechanism: "#6a46b0",
  drug: "#b4503c",
  asset: "#9a5b00",
  study: "#7d848c",
  organization: "#8a6d3b",
  term: "#3d7a99",
};
const colorOf = (type: string) => colors[type] ?? "#7d848c";
/** Solid green = reviewed, purple dashed = hypothesis, grey dashed = unreviewed, faint dotted = computed (no claim behind it). */
const edgeColor = (e: GraphEdge, onPath: boolean) =>
  onPath
    ? "#2952cc"
    : e.review_state === "reviewed"
      ? "#5fa79c"
      : isHypothesisEdge(e)
        ? "#8a63c9"
        : e.claim_id
          ? "#9aa0aa"
          : "#d5d8de";

type Pos = [number, number, number];

/** Center node at origin, direct neighbours on an inner shell, others on an outer shell (fibonacci sphere). */
function layout(nodes: GraphNode[], edges: GraphEdge[], centerId: string) {
  const direct = new Set(
    edges.flatMap((e) =>
      e.source === centerId ? [e.target] : e.target === centerId ? [e.source] : [],
    ),
  );
  const inner = nodes.filter((n) => n.id !== centerId && direct.has(n.id));
  const outer = nodes.filter((n) => n.id !== centerId && !direct.has(n.id));
  const out = new Map<string, Pos>([[centerId, [0, 0, 0]]]);
  const shell = (list: GraphNode[], r: number) =>
    list.forEach((n, i) => {
      const y = list.length === 1 ? 0 : 1 - (i / (list.length - 1)) * 2;
      const rad = Math.sqrt(1 - y * y) * 1.0;
      const t = i * 2.399963;
      out.set(n.id, [Math.cos(t) * rad * r * 1.25, y * r * 0.75, Math.sin(t) * rad * r * 0.7]);
    });
  shell(inner, 3.6);
  shell(outer, 6);
  return out;
}

function GraphNode({
  entity,
  position,
  selected,
  dim,
  onSelect,
}: {
  entity: GraphNode;
  position: Pos;
  selected: boolean;
  dim: boolean;
  onSelect: (id: string) => void;
}) {
  const mesh = useRef<THREE.Mesh>(null);
  const short = clean(entity.label);
  const label = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 72;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "rgba(255,255,255,.97)";
      ctx.fillRect(2, 2, 316, 68);
      ctx.strokeStyle = selected ? "#2952cc" : "#e5e7eb";
      ctx.lineWidth = selected ? 4 : 2;
      ctx.strokeRect(2, 2, 316, 68);
      ctx.fillStyle = selected ? "#2952cc" : "#111827";
      ctx.font = `${selected ? "600" : "500"} 24px Inter, Arial`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(short.length > 22 ? `${short.slice(0, 21)}…` : short, 160, 37);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }, [short, selected]);
  useEffect(() => () => label.dispose(), [label]);
  useFrame(({ clock }) => {
    if (mesh.current)
      mesh.current.position.y =
        position[1] + Math.sin(clock.elapsedTime * 0.7 + position[0]) * 0.05;
  });
  return (
    <group>
      <mesh
        ref={mesh}
        position={position}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(entity.id);
        }}
        scale={selected ? 1.28 : 1}
      >
        <sphereGeometry args={[entity.type === "disease" ? 0.46 : 0.32, 24, 24]} />
        <meshStandardMaterial
          color={colorOf(entity.type)}
          roughness={0.35}
          metalness={0.08}
          emissive={colorOf(entity.type)}
          emissiveIntensity={selected ? 0.22 : 0.05}
          transparent
          opacity={dim ? 0.35 : 1}
        />
      </mesh>
      <sprite position={[position[0], position[1] + 0.62, position[2]]} scale={[1.75, 0.4, 1]}>
        <spriteMaterial map={label} transparent depthTest={false} opacity={dim ? 0.45 : 1} />
      </sprite>
    </group>
  );
}

export function KnowledgeGraph({
  nodes,
  edges,
  centerId,
  selectedId,
  pathClaimIds = [],
  typeFilter = "all",
  onSelect,
  onEdgeSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  centerId: string;
  selectedId: string;
  pathClaimIds?: string[];
  typeFilter?: string;
  onSelect: (id: string) => void;
  onEdgeSelect?: (claimId: string) => void;
}) {
  const positions = useMemo(() => layout(nodes, edges, centerId), [nodes, edges, centerId]);
  const onPath = new Set(pathClaimIds);
  return (
    <div className="h-full w-full">
      <Canvas dpr={[1, 1.5]} camera={{ position: [0, 0, 13], fov: 50 }}>
        <color attach="background" args={["#fafafa"]} />
        <ambientLight intensity={1.8} />
        <directionalLight position={[4, 8, 8]} intensity={2.2} />
        {edges.map((e) => {
          const a = positions.get(e.source);
          const b = positions.get(e.target);
          return a && b ? (
            <group key={edgeKey(e)}>
              <Line
                points={[a, b]}
                color={edgeColor(e, onPath.has(e.claim_id ?? ""))}
                lineWidth={onPath.has(e.claim_id ?? "") ? 2.5 : 1.5}
                transparent
                opacity={0.85}
                dashed={e.review_state !== "reviewed"}
                dashSize={0.18}
                gapSize={0.12}
              />
              <Line
                points={[a, b]}
                color={edgeColor(e, onPath.has(e.claim_id ?? ""))}
                lineWidth={12}
                transparent
                opacity={0}
                onClick={(event) => {
                  event.stopPropagation();
                  if (e.claim_id) onEdgeSelect?.(e.claim_id);
                }}
                onPointerOver={() => {
                  if (e.claim_id) document.body.style.cursor = "pointer";
                }}
                onPointerOut={() => {
                  document.body.style.cursor = "";
                }}
              />
            </group>
          ) : null;
        })}
        {nodes.map((n) => {
          const p = positions.get(n.id);
          return p ? (
            <GraphNode
              key={n.id}
              entity={n}
              position={p}
              selected={selectedId === n.id}
              dim={typeFilter !== "all" && n.type !== typeFilter && n.id !== centerId}
              onSelect={onSelect}
            />
          ) : null;
        })}
        <OrbitControls
          enablePan
          enableZoom
          minDistance={6}
          maxDistance={22}
          autoRotate
          autoRotateSpeed={0.25}
        />
      </Canvas>
    </div>
  );
}
