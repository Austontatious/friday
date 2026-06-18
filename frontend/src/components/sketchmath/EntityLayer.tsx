import React from "react";
import type { SketchMathEntity } from "../../services/sketchmath";

type EntityLayerProps = {
  entities: SketchMathEntity[];
  selectedEntityIds: string[];
  focusedEntityId: string | null;
  onEntityClick: (entityId: string, event: React.MouseEvent<SVGGElement | SVGCircleElement>) => void;
  onEntityMouseDown?: (entityId: string, entityType: SketchMathEntity["type"], event: React.MouseEvent<SVGGElement>) => void;
  onDimensionLabelEdit?: (baseId: string, dimension: "width" | "height") => void;
};

const isPoint = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "point_2d" }> =>
  entity.type === "point_2d";

const isLine = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "line_2d" | "construction_line_2d" }> =>
  entity.type === "line_2d" || entity.type === "construction_line_2d";

const formatDimension = (value: number): string => Number(value.toFixed(2)).toString();

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

const EntityLayer = ({ entities, selectedEntityIds, focusedEntityId, onEntityClick, onEntityMouseDown, onDimensionLabelEdit }: EntityLayerProps) => {
  const linesById = new Map(entities.filter(isLine).map((entity) => [entity.id, entity] as const));
  const selectedRectangleBaseIds = new Set(
    selectedEntityIds.map(rectangleBaseIdFromEntityId).filter((value): value is string => Boolean(value)),
  );

  return (
  <g data-testid="sketchmath-entities">
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
          <text x={midpointX + 8} y={midpointY - 8} className="sketchmath-label">
            {displayName}
          </text>
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
          <text x={entity.coords[0] + 10} y={entity.coords[1] - 10} className="sketchmath-label">
            {displayName}
          </text>
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
      if (!top || !left) {
        return null;
      }
      const width = Math.abs(top.end[0] - top.start[0]);
      const height = Math.abs(left.start[1] - left.end[1]);
      const widthX = (top.start[0] + top.end[0]) / 2;
      const widthY = top.start[1] - 24;
      const heightX = left.end[0] - 54;
      const heightY = (left.start[1] + left.end[1]) / 2;
      return (
        <g key={`${baseId}-dimensions`} className="sketchmath-dimensions">
          <text
            x={widthX}
            y={widthY}
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
            x={heightX}
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
