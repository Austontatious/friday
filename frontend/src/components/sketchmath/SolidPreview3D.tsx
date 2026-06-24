import React, { useCallback, useEffect, useMemo, useRef } from "react";
import { Box, Button, HStack, Text } from "@chakra-ui/react";
import type { SketchMathPreviewMesh, SketchMathPreviewTriangle } from "../../services/sketchmath";

type Vec3 = [number, number, number];
type Vec2 = { x: number; y: number; z: number };
export type SolidCameraState = {
  yaw: number;
  pitch: number;
  zoom: number;
  panX: number;
  panY: number;
  targetX: number;
  targetY: number;
  targetZ: number;
};
type DragState = { x: number; y: number; mode: "orbit" | "pan" };

export const DEFAULT_SOLID_CAMERA: SolidCameraState = {
  yaw: 0,
  pitch: -Math.PI / 2,
  zoom: 1,
  panX: 0,
  panY: 0,
  targetX: 0,
  targetY: 0,
  targetZ: 0,
};
const SURFACE_COLORS: Record<string, string> = {
  top: "#8fd3ff",
  bottom: "#355268",
  outer_wall: "#5b9fd2",
  hole_wall: "#162938",
};

const clamp = (value: number, min: number, max: number): number => Math.max(min, Math.min(max, value));
const degrees = (radians: number): number => Math.round((radians * 180) / Math.PI);
const formatCameraValue = (value: number): string => (Number.isInteger(value) ? String(value) : value.toFixed(2));
const isPanGesture = (event: Pick<React.PointerEvent<HTMLCanvasElement>, "button" | "buttons" | "shiftKey">): boolean =>
  event.shiftKey || event.button === 1 || event.button === 2 || Boolean(event.buttons & 4) || Boolean(event.buttons & 2);

const meshCenter = (mesh: SketchMathPreviewMesh): Vec3 => {
  const bbox = mesh.metadata?.bbox;
  if (bbox) {
    return [(bbox.xmin + bbox.xmax) / 2, (bbox.ymin + bbox.ymax) / 2, (bbox.zmin + bbox.zmax) / 2];
  }
  const vertices = mesh.vertices;
  if (!vertices.length) {
    return [0, 0, 0];
  }
  return [
    vertices.reduce((sum, vertex) => sum + vertex[0], 0) / vertices.length,
    vertices.reduce((sum, vertex) => sum + vertex[1], 0) / vertices.length,
    vertices.reduce((sum, vertex) => sum + vertex[2], 0) / vertices.length,
  ];
};

const meshSpan = (mesh: SketchMathPreviewMesh): number => {
  const bbox = mesh.metadata?.bbox;
  if (bbox) {
    return Math.max(bbox.xmax - bbox.xmin, bbox.ymax - bbox.ymin, bbox.zmax - bbox.zmin, 1);
  }
  return 60;
};

const rotateProject = (vertex: Vec3, center: Vec3, camera: SolidCameraState): Vec2 => {
  const x = vertex[0] - center[0];
  const y = vertex[1] - center[1];
  const z = vertex[2] - center[2];
  const cosYaw = Math.cos(camera.yaw);
  const sinYaw = Math.sin(camera.yaw);
  const cosPitch = Math.cos(camera.pitch);
  const sinPitch = Math.sin(camera.pitch);
  const yawX = x * cosYaw - y * sinYaw;
  const yawY = x * sinYaw + y * cosYaw;
  const pitchY = yawY * cosPitch - z * sinPitch;
  const pitchZ = yawY * sinPitch + z * cosPitch;
  return { x: yawX, y: -pitchZ, z: pitchY };
};

const triangleShade = (surface: string, normalZ: number): string => {
  const base = SURFACE_COLORS[surface] || "#6caed7";
  const amount = clamp(0.68 + Math.abs(normalZ) * 0.24 + (surface === "hole_wall" ? -0.14 : 0), 0.36, 1);
  const numeric = parseInt(base.slice(1), 16);
  const r = Math.round(((numeric >> 16) & 255) * amount);
  const g = Math.round(((numeric >> 8) & 255) * amount);
  const b = Math.round((numeric & 255) * amount);
  return `rgb(${r}, ${g}, ${b})`;
};

const normalZ = (a: Vec2, b: Vec2, c: Vec2): number => {
  const ux = b.x - a.x;
  const uy = b.y - a.y;
  const vx = c.x - a.x;
  const vy = c.y - a.y;
  return ux * vy - uy * vx;
};

const drawCenter = (mesh: SketchMathPreviewMesh, camera: SolidCameraState): Vec3 => {
  const center = meshCenter(mesh);
  const bbox = mesh.metadata?.bbox;
  if (!bbox) {
    return center;
  }
  const span = meshSpan(mesh);
  const targetNearMesh =
    camera.targetX >= bbox.xmin - span * 2 &&
    camera.targetX <= bbox.xmax + span * 2 &&
    camera.targetY >= bbox.ymin - span * 2 &&
    camera.targetY <= bbox.ymax + span * 2;
  return targetNearMesh ? [camera.targetX, camera.targetY, camera.targetZ] : center;
};

const drawMesh = (canvas: HTMLCanvasElement, mesh: SketchMathPreviewMesh, camera: SolidCameraState) => {
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }
  const bounds = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(bounds.width * dpr));
  const height = Math.max(1, Math.floor(bounds.height * dpr));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, bounds.width, bounds.height);
  context.fillStyle = "#071018";
  context.fillRect(0, 0, bounds.width, bounds.height);

  const center = drawCenter(mesh, camera);
  const span = meshSpan(mesh);
  const scale = (Math.min(bounds.width, bounds.height) * 0.62 * camera.zoom) / span;
  const projected = mesh.vertices.map((vertex) => rotateProject(vertex, center, camera));
  const faces = mesh.triangles
    .map((triangle) => {
      const [ia, ib, ic] = triangle.indices;
      const a = projected[ia];
      const b = projected[ib];
      const c = projected[ic];
      if (!a || !b || !c) {
        return null;
      }
      return {
        triangle,
        a,
        b,
        c,
        z: (a.z + b.z + c.z) / 3,
        nz: normalZ(a, b, c),
      };
    })
    .filter((face): face is { triangle: SketchMathPreviewTriangle; a: Vec2; b: Vec2; c: Vec2; z: number; nz: number } => Boolean(face))
    .sort((left, right) => left.z - right.z);

  context.save();
  context.translate(bounds.width / 2 + camera.panX, bounds.height / 2 + camera.panY);
  context.scale(scale, scale);
  context.lineWidth = 1 / scale;
  for (const face of faces) {
    context.beginPath();
    context.moveTo(face.a.x, face.a.y);
    context.lineTo(face.b.x, face.b.y);
    context.lineTo(face.c.x, face.c.y);
    context.closePath();
    context.fillStyle = triangleShade(face.triangle.surface, face.nz);
    context.strokeStyle = face.triangle.surface === "hole_wall" ? "rgba(2, 8, 13, 0.82)" : "rgba(237, 247, 251, 0.13)";
    context.fill();
    context.stroke();
  }
  context.restore();
};

type SolidPreview3DProps = {
  mesh: SketchMathPreviewMesh | null;
  camera: SolidCameraState;
  onCameraChange: (camera: SolidCameraState) => void;
  onPreset: (preset: "fit" | "reset" | "top" | "iso" | "front" | "tilt") => void;
};

export default function SolidPreview3D({ mesh, camera, onCameraChange, onPreset }: SolidPreview3DProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const holeCount = mesh?.metadata?.hole_count ?? 0;
  const depth = mesh?.depth ?? 0;
  const summary = useMemo(() => {
    if (!mesh) {
      return "Extrude a valid profile to preview the 3D solid.";
    }
    return `${depth} ${mesh.units} extrusion with ${holeCount === 1 ? "1 through-hole" : `${holeCount} through-holes`}.`;
  }, [depth, holeCount, mesh]);
  const cameraHud = useMemo(
    () => ({
      azimuth: degrees(camera.yaw),
      elevation: degrees(camera.pitch),
      zoom: Number(camera.zoom.toFixed(2)),
      panX: Math.round(camera.panX),
      panY: Math.round(camera.panY),
      targetX: Math.round(camera.targetX),
      targetY: Math.round(camera.targetY),
      targetZ: Math.round(camera.targetZ),
    }),
    [camera],
  );

  const redraw = useCallback(() => {
    if (mesh && canvasRef.current) {
      drawMesh(canvasRef.current, mesh, camera);
    }
  }, [camera, mesh]);

  useEffect(() => {
    redraw();
    window.addEventListener("resize", redraw);
    return () => window.removeEventListener("resize", redraw);
  }, [redraw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return undefined;
    }
    const handleWheel = (event: WheelEvent) => {
      if (!mesh) {
        return;
      }
      event.preventDefault();
      onCameraChange({ ...camera, zoom: clamp(camera.zoom * (event.deltaY < 0 ? 1.12 : 0.88), 0.35, 4) });
    };
    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleWheel);
  }, [camera, mesh, onCameraChange]);

  const onPointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!mesh) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { x: event.clientX, y: event.clientY, mode: isPanGesture(event) ? "pan" : "orbit" };
  };

  const onPointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (!drag) {
      return;
    }
    event.preventDefault();
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    const mode = isPanGesture(event) ? "pan" : drag.mode;
    dragRef.current = { ...drag, x: event.clientX, y: event.clientY, mode };
    onCameraChange(
      mode === "pan"
        ? { ...camera, panX: camera.panX + dx, panY: camera.panY + dy }
        : { ...camera, yaw: camera.yaw + dx * 0.01, pitch: clamp(camera.pitch + dy * 0.01, -Math.PI / 2, 1.45) },
    );
  };

  const onPointerUp = (event: React.PointerEvent<HTMLCanvasElement>) => {
    event.preventDefault();
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  return (
    <Box className="sketchmath-solid-preview" data-testid="sketchmath-solid-preview">
      <HStack className="sketchmath-solid-preview-controls" spacing={2} flexWrap="wrap">
        <Button size="sm" variant="outline" onClick={() => onPreset("fit")} isDisabled={!mesh}>
          Fit
        </Button>
        <Button size="sm" variant="outline" onClick={() => onPreset("reset")} isDisabled={!mesh}>
          Reset
        </Button>
        <Button size="sm" variant="outline" onClick={() => onPreset("top")} isDisabled={!mesh}>
          Top
        </Button>
        <Button size="sm" variant="outline" onClick={() => onPreset("iso")} isDisabled={!mesh}>
          Iso
        </Button>
        <Button size="sm" variant="outline" onClick={() => onPreset("front")} isDisabled={!mesh}>
          Front
        </Button>
        <Button size="sm" variant="outline" onClick={() => onPreset("tilt")} isDisabled={!mesh}>
          Tilt to 3D
        </Button>
      </HStack>
      <Text className="sketchmath-solid-preview-status" data-testid="sketchmath-solid-preview-status">
        {summary}
      </Text>
      <dl className="sketchmath-solid-preview-hud" data-testid="sketchmath-solid-camera-hud" aria-label="3D camera state">
        <div><dt>view</dt><dd>3D solid</dd></div>
        <div><dt>azimuth</dt><dd data-testid="sketchmath-camera-azimuth">{cameraHud.azimuth} deg</dd></div>
        <div><dt>elevation</dt><dd data-testid="sketchmath-camera-elevation">{cameraHud.elevation} deg</dd></div>
        <div><dt>zoom</dt><dd data-testid="sketchmath-camera-zoom">{formatCameraValue(cameraHud.zoom)}x</dd></div>
        <div><dt>pan</dt><dd data-testid="sketchmath-camera-pan">{cameraHud.panX}, {cameraHud.panY}</dd></div>
        <div><dt>target</dt><dd data-testid="sketchmath-camera-target">{cameraHud.targetX}, {cameraHud.targetY}</dd></div>
      </dl>
      <canvas
        ref={canvasRef}
        className="sketchmath-solid-preview-canvas"
        data-testid="sketchmath-solid-preview-canvas"
        aria-label="3D solid preview"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onContextMenu={(event) => event.preventDefault()}
      />
    </Box>
  );
}
