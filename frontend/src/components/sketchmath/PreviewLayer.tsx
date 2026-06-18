import React from "react";
import type { SketchMathEntity, SketchMathOperationResult } from "../../services/sketchmath";

type PreviewLayerProps = {
  previewResult: SketchMathOperationResult | null;
  committedEntityIds: string[];
};

const previewEntity = (entity: SketchMathEntity, previewed: boolean) => {
  if (entity.type === "point_2d") {
    return (
      <g key={entity.id}>
        <circle
          cx={entity.coords[0]}
          cy={entity.coords[1]}
          r={previewed ? 7 : 5}
          className="sketchmath-preview-point"
        />
      </g>
    );
  }
  if (entity.type === "line_2d" || entity.type === "construction_line_2d") {
    return <line key={entity.id} x1={entity.start[0]} y1={entity.start[1]} x2={entity.end[0]} y2={entity.end[1]} className="sketchmath-preview-line" />;
  }
  if (entity.type === "profile_2d") {
    const points = entity.vertices.map((vertex) => vertex.join(",")).join(" ");
    return <polygon key={entity.id} points={points} className="sketchmath-preview-profile" />;
  }
  return null;
};

const PreviewLayer = ({ previewResult, committedEntityIds }: PreviewLayerProps) => {
  if (!previewResult) {
    return null;
  }
  const changed = new Set(previewResult.changed_entity_ids);
  const previewed = previewResult.after.items.filter((entity) => changed.has(entity.id) && !committedEntityIds.includes(entity.id));
  const committedUpdates = previewResult.after.items.filter((entity) => changed.has(entity.id) && committedEntityIds.includes(entity.id));
  const entities = [...previewed, ...committedUpdates];

  return <g data-testid="sketchmath-preview">{entities.map((entity) => previewEntity(entity, true))}</g>;
};

export default PreviewLayer;
