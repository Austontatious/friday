import React from "react";
import type { SketchMathEntity, SketchMathProfileCandidate } from "../../services/sketchmath";
import { arcSvgPath } from "./arcGeometry";

type EntityLayerProps = {
  entities: SketchMathEntity[];
  selectedEntityIds: string[];
  focusedEntityId: string | null;
  placementActive?: boolean;
  showDebugLabels?: boolean;
  profileCandidates?: SketchMathProfileCandidate[];
  onEntityClick: (entityId: string, event: React.MouseEvent<SVGGElement | SVGCircleElement | SVGPolygonElement>) => void;
  onEntityMouseDown?: (entityId: string, entityType: SketchMathEntity["type"], event: React.MouseEvent<SVGGElement>) => void;
  onDimensionLabelEdit?: (baseId: string, dimension: "width" | "height") => void;
};

const isPoint = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "point_2d" }> =>
  entity.type === "point_2d";

const isLine = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "line_2d" | "construction_line_2d" }> =>
  entity.type === "line_2d" || entity.type === "construction_line_2d";

const isProfile = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> =>
  entity.type === "profile_2d";
const isCircle = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "circle_2d" }> => entity.type === "circle_2d";
const isArc = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "arc_2d" }> => entity.type === "arc_2d";

const formatDimension = (value: number): string => Number(value.toFixed(2)).toString();
const DIMENSION_GUIDE_OFFSET = 34;
const DIMENSION_TICK = 9;

const profileBounds = (entity: Extract<SketchMathEntity, { type: "profile_2d" }>) => {
  const vertices = entity.vertices.filter((vertex, index) => index === 0 || vertex[0] !== entity.vertices[0][0] || vertex[1] !== entity.vertices[0][1]);
  if (vertices.length === 0) {
    return null;
  }
  const xs = vertices.map((vertex) => vertex[0]);
  const ys = vertices.map((vertex) => vertex[1]);
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  };
};

const rectangleBaseIdFromPointId = (pointId: string): string | null => {
  const match = /^rect_(.+)_[abcd]$/.exec(pointId);
  return match ? `rect_${match[1]}` : null;
};

const rectangleBaseIdFromEntityId = (entityId: string): string | null => {
  const pointBaseId = rectangleBaseIdFromPointId(entityId);
  if (pointBaseId) {
    return pointBaseId;
  }
  const lineMatch = /^rect_(.+)_(ab|bc|cd|da)$/.exec(entityId);
  if (lineMatch) {
    return `rect_${lineMatch[1]}`;
  }
  const profileMatch = /^profile_(rect_.+)$/.exec(entityId);
  return profileMatch ? profileMatch[1] : null;
};

const EntityLayer = ({ entities, selectedEntityIds, focusedEntityId, placementActive = false, showDebugLabels = false, profileCandidates = [], onEntityClick, onEntityMouseDown, onDimensionLabelEdit }: EntityLayerProps) => {
  const linesById = new Map(entities.filter(isLine).map((entity) => [entity.id, entity] as const));
  const profileById = new Map(entities.filter(isProfile).map((entity) => [entity.id, entity] as const));
  const profileHoleIds = new Set(
    entities
      .filter(isProfile)
      .flatMap((entity) => entity.holes || [])
      .filter((entityId) => profileById.has(entityId)),
  );
  const selectedRectangleBaseIds = new Set(
    selectedEntityIds.map(rectangleBaseIdFromEntityId).filter((value): value is string => Boolean(value)),
  );

  return (
  <g data-testid="sketchmath-entities" className={placementActive ? "sketchmath-placement-active" : undefined}>
    {profileCandidates.filter((candidate) => candidate.valid).map((candidate) => (
      <polygon key={candidate.candidate_id} points={candidate.vertices.map((vertex) => vertex.join(",")).join(" ")} fill="none" className="sketchmath-profile-target-selected" data-testid={`profile-candidate-${candidate.candidate_id}`} />
    ))}
    {Array.from(selectedRectangleBaseIds).map((baseId) => {
      const top = linesById.get(`${baseId}_ab`);
      const right = linesById.get(`${baseId}_bc`);
      const bottom = linesById.get(`${baseId}_cd`);
      const left = linesById.get(`${baseId}_da`);
      if (!top || !right || !bottom || !left) {
        return null;
      }
      return (
        <polygon
          key={`${baseId}-selection-outline`}
          points={`${top.start.join(",")} ${top.end.join(",")} ${right.end.join(",")} ${bottom.end.join(",")}`}
          className="sketchmath-rectangle-selection-outline"
          data-testid={`rectangle-selection-outline-${baseId}`}
        />
      );
    })}
    {entities.filter((entity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> => isProfile(entity) && !profileHoleIds.has(entity.id)).map((entity) => {
      const points = entity.vertices.map((vertex) => vertex.join(",")).join(" ");
      const selected = selectedEntityIds.includes(entity.id) || Boolean(rectangleBaseIdFromEntityId(entity.id) && selectedRectangleBaseIds.has(rectangleBaseIdFromEntityId(entity.id) as string));
      return (
        <polygon
          key={entity.id}
          points={points}
          className={selected ? "sketchmath-profile-target sketchmath-profile-target-selected" : "sketchmath-profile-target"}
          data-testid={`entity-${entity.id}`}
          data-entity-id={entity.id}
          data-entity-type={entity.type}
          role="button"
          tabIndex={0}
          onClick={(event) => {
            event.stopPropagation();
            onEntityClick(entity.id, event);
          }}
        />
      );
    })}
    {entities.filter((entity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> => isProfile(entity) && profileHoleIds.has(entity.id)).map((entity) => {
      const points = entity.vertices.map((vertex) => vertex.join(",")).join(" ");
      const selected = selectedEntityIds.includes(entity.id);
      const bounds = profileBounds(entity);
      const diameter = bounds ? Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY) : 0;
      const centerX = bounds ? (bounds.minX + bounds.maxX) / 2 : 0;
      const centerY = bounds ? (bounds.minY + bounds.maxY) / 2 : 0;
      return (
        <g key={entity.id}>
          <polygon
            points={points}
            className={selected ? "sketchmath-hole-profile sketchmath-hole-profile-selected" : "sketchmath-hole-profile"}
            data-testid={`entity-${entity.id}`}
            data-entity-id={entity.id}
            data-entity-type={entity.type}
            role="button"
            tabIndex={0}
            onClick={(event) => {
              event.stopPropagation();
              onEntityClick(entity.id, event);
            }}
          />
          {selected && bounds ? (
            <text
              x={centerX}
              y={centerY - Math.max(12, diameter / 2 + 8)}
              className="sketchmath-dimension-label"
              data-testid={`dimension-${entity.id}-diameter`}
            >
              Dia {formatDimension(diameter)} mm
            </text>
          ) : null}
        </g>
      );
    })}
    {entities.filter(isLine).map((entity) => {
      const selected = selectedEntityIds.includes(entity.id);
      const displayName = entity.label || entity.id;
      const midpointX = (entity.start[0] + entity.end[0]) / 2;
      const midpointY = (entity.start[1] + entity.end[1]) / 2;
      return (
        <g
          key={entity.id}
          onClick={(event) => onEntityClick(entity.id, event)}
          onMouseDown={(event) => {
            event.stopPropagation();
            onEntityMouseDown?.(entity.id, entity.type, event);
          }}
          role="button"
          tabIndex={0}
          data-testid={`entity-${entity.id}`}
          data-entity-id={entity.id}
          data-entity-type={entity.type}
        >
          <line x1={entity.start[0]} y1={entity.start[1]} x2={entity.end[0]} y2={entity.end[1]} className="sketchmath-line-hit-target" />
          <line
            x1={entity.start[0]}
            y1={entity.start[1]}
            x2={entity.end[0]}
            y2={entity.end[1]}
            className={[
              "sketchmath-line",
              selected ? "sketchmath-line-selected" : "",
              focusedEntityId === entity.id ? "sketchmath-line-focus" : "",
            ].filter(Boolean).join(" ")}
          />
          {showDebugLabels ? (
            <text x={midpointX + 8} y={midpointY - 8} className="sketchmath-label">
              {displayName}
            </text>
          ) : null}
        </g>
      );
    })}
    {entities.filter(isCircle).map((entity) => {
      const selected = selectedEntityIds.includes(entity.id);
      return (
        <circle
          key={entity.id}
          cx={entity.center[0]}
          cy={entity.center[1]}
          r={entity.radius}
          fill="none"
          className={selected ? "sketchmath-line sketchmath-line-selected" : "sketchmath-line"}
          data-testid={`entity-${entity.id}`}
          data-entity-id={entity.id}
          data-entity-type={entity.type}
          role="button"
          tabIndex={0}
          onClick={(event) => {
            event.stopPropagation();
            onEntityClick(entity.id, event);
          }}
        />
      );
    })}
    {entities.filter(isArc).map((entity) => {
      const selected = selectedEntityIds.includes(entity.id);
      return (
        <g
          key={entity.id}
          data-testid={`entity-${entity.id}`}
          data-entity-id={entity.id}
          data-entity-type={entity.type}
          role="button"
          tabIndex={0}
          onClick={(event) => {
            event.stopPropagation();
            onEntityClick(entity.id, event);
          }}
        >
          <path d={arcSvgPath(entity)} fill="none" className="sketchmath-line-hit-target" />
          <path d={arcSvgPath(entity)} fill="none" className={selected ? "sketchmath-line sketchmath-line-selected" : "sketchmath-line"} />
        </g>
      );
    })}
    {entities.filter(isPoint).map((entity) => {
      const selected = selectedEntityIds.includes(entity.id);
      const displayName = entity.label || entity.id;
      return (
        <g
          key={entity.id}
          onClick={(event) => onEntityClick(entity.id, event)}
          onMouseDown={(event) => {
            event.stopPropagation();
            onEntityMouseDown?.(entity.id, entity.type, event);
          }}
          role="button"
          tabIndex={0}
          data-testid={`entity-${entity.id}`}
          data-entity-id={entity.id}
          data-entity-type={entity.type}
        >
          <circle
            cx={entity.coords[0]}
            cy={entity.coords[1]}
            r={selected ? 8 : 6}
            className={[
              "sketchmath-point",
              selected ? "sketchmath-point-selected" : "",
              focusedEntityId === entity.id ? "sketchmath-point-focus" : "",
            ].filter(Boolean).join(" ")}
          />
          {showDebugLabels ? (
            <text x={entity.coords[0] + 10} y={entity.coords[1] - 10} className="sketchmath-label">
              {displayName}
            </text>
          ) : null}
        </g>
      );
    })}
    {Array.from(selectedRectangleBaseIds).map((baseId) => {
      const ids = {
        a: `${baseId}_a`,
        b: `${baseId}_b`,
        c: `${baseId}_c`,
        d: `${baseId}_d`,
      };
      const top = linesById.get(`${baseId}_ab`);
      const right = linesById.get(`${baseId}_bc`);
      const bottom = linesById.get(`${baseId}_cd`);
      if (!top || !right || !bottom) {
        return null;
      }
      const handles = [
        { id: ids.a, corner: "a", coords: top.start },
        { id: ids.b, corner: "b", coords: top.end },
        { id: ids.c, corner: "c", coords: right.end },
        { id: ids.d, corner: "d", coords: bottom.end },
      ] as const;
      return (
        <g key={`${baseId}-corner-handles`} className="sketchmath-rectangle-corner-handles">
          {handles.map((handle) => (
            <circle
              key={handle.id}
              cx={handle.coords[0]}
              cy={handle.coords[1]}
              r={9}
              className={focusedEntityId === handle.id ? "sketchmath-rectangle-corner-handle sketchmath-point-focus" : "sketchmath-rectangle-corner-handle"}
              data-testid={`rectangle-corner-${baseId}-${handle.corner}`}
              data-entity-id={handle.id}
              data-entity-type="point_2d"
              onClick={(event) => {
                event.stopPropagation();
                onEntityClick(handle.id, event);
              }}
            />
          ))}
        </g>
      );
    })}
    {Array.from(selectedRectangleBaseIds).map((baseId) => {
      const top = linesById.get(`${baseId}_ab`);
      const left = linesById.get(`${baseId}_da`);
      const right = linesById.get(`${baseId}_bc`);
      const bottom = linesById.get(`${baseId}_cd`);
      if (!top || !left || !right || !bottom) {
        return null;
      }
      const width = Math.abs(top.end[0] - top.start[0]);
      const height = Math.abs(left.start[1] - left.end[1]);
      const widthX = (top.start[0] + top.end[0]) / 2;
      const guideAbove = top.start[1] <= bottom.start[1];
      const guideLeft = left.start[0] <= right.start[0];
      const widthGuideY = top.start[1] + (guideAbove ? -DIMENSION_GUIDE_OFFSET : DIMENSION_GUIDE_OFFSET);
      const widthLabelY = widthGuideY + (guideAbove ? -6 : 18);
      const heightGuideX = left.end[0] + (guideLeft ? -DIMENSION_GUIDE_OFFSET : DIMENSION_GUIDE_OFFSET);
      const heightLabelX = heightGuideX + (guideLeft ? -20 : 20);
      const heightY = (left.start[1] + left.end[1]) / 2;
      return (
        <g key={`${baseId}-dimensions`} className="sketchmath-dimensions">
          <line
            x1={top.start[0]}
            y1={widthGuideY}
            x2={top.end[0]}
            y2={widthGuideY}
            className="sketchmath-dimension-guide"
            data-testid={`dimension-guide-${baseId}-width`}
          />
          <line x1={top.start[0]} y1={top.start[1]} x2={top.start[0]} y2={widthGuideY + (guideAbove ? DIMENSION_TICK : -DIMENSION_TICK)} className="sketchmath-dimension-guide" />
          <line x1={top.end[0]} y1={top.end[1]} x2={top.end[0]} y2={widthGuideY + (guideAbove ? DIMENSION_TICK : -DIMENSION_TICK)} className="sketchmath-dimension-guide" />
          <line
            x1={heightGuideX}
            y1={left.end[1]}
            x2={heightGuideX}
            y2={left.start[1]}
            className="sketchmath-dimension-guide"
            data-testid={`dimension-guide-${baseId}-height`}
          />
          <line x1={left.end[0]} y1={left.end[1]} x2={heightGuideX + (guideLeft ? DIMENSION_TICK : -DIMENSION_TICK)} y2={left.end[1]} className="sketchmath-dimension-guide" />
          <line x1={left.start[0]} y1={left.start[1]} x2={heightGuideX + (guideLeft ? DIMENSION_TICK : -DIMENSION_TICK)} y2={left.start[1]} className="sketchmath-dimension-guide" />
          <text
            x={widthX}
            y={widthLabelY}
            className="sketchmath-dimension-label"
            data-testid={`dimension-${baseId}-width`}
            role="button"
            tabIndex={0}
            onClick={(event) => {
              event.stopPropagation();
              onDimensionLabelEdit?.(baseId, "width");
            }}
            onDoubleClick={(event) => {
              event.stopPropagation();
              onDimensionLabelEdit?.(baseId, "width");
            }}
          >
            {formatDimension(width)} mm
          </text>
          <text
            x={heightLabelX}
            y={heightY}
            className="sketchmath-dimension-label"
            data-testid={`dimension-${baseId}-height`}
            role="button"
            tabIndex={0}
            onClick={(event) => {
              event.stopPropagation();
              onDimensionLabelEdit?.(baseId, "height");
            }}
            onDoubleClick={(event) => {
              event.stopPropagation();
              onDimensionLabelEdit?.(baseId, "height");
            }}
          >
            {formatDimension(height)} mm
          </text>
        </g>
      );
    })}
  </g>
  );
};

export default EntityLayer;
