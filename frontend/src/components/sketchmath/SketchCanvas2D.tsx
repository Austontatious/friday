import React from "react";
import GridLayer from "./GridLayer";
import EntityLayer from "./EntityLayer";
import PreviewLayer from "./PreviewLayer";
import type { SketchMathEntity, SketchMathOperationResult } from "../../services/sketchmath";

type Point = { x: number; y: number };

type SketchCanvas2DProps = {
  width: number;
  height: number;
  entities: SketchMathEntity[];
  previewResult: SketchMathOperationResult | null;
  selectedEntityIds: string[];
  focusedEntityId: string | null;
  draftPoint: Point | null;
  rectangleDraft: { anchor: Point; current: Point } | null;
  dragPreviewPoint: { id: string; point: Point } | null;
  onCanvasClick: (point: Point) => void;
  onCanvasMouseDown: (point: Point, event: React.MouseEvent<SVGSVGElement>) => void;
  onCanvasMouseMove: (point: Point, event: React.MouseEvent<SVGSVGElement>) => void;
  onCanvasMouseUp: (point: Point, event: React.MouseEvent<SVGSVGElement>) => void;
  onCanvasContextMenu: (point: Point, event: React.MouseEvent<SVGSVGElement>) => void;
  onEntityClick: (entityId: string, event: React.MouseEvent<SVGGElement | SVGCircleElement | SVGPolygonElement>) => void;
  onEntityMouseDown?: (entityId: string, entityType: SketchMathEntity["type"], event: React.MouseEvent<SVGGElement>) => void;
  onDimensionLabelEdit?: (baseId: string, dimension: "width" | "height") => void;
};

const SketchCanvas2D = ({
  width,
  height,
  entities,
  previewResult,
  selectedEntityIds,
  focusedEntityId,
  draftPoint,
  rectangleDraft,
  dragPreviewPoint,
  onCanvasClick,
  onCanvasMouseDown,
  onCanvasMouseMove,
  onCanvasMouseUp,
  onCanvasContextMenu,
  onEntityClick,
  onEntityMouseDown,
  onDimensionLabelEdit,
}: SketchCanvas2DProps) => {
  const getCanvasPoint = (event: React.MouseEvent<SVGSVGElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const scale = Math.min(bounds.width / width, bounds.height / height);
    const contentWidth = width * scale;
    const contentHeight = height * scale;
    const contentLeft = (bounds.width - contentWidth) / 2;
    const contentTop = (bounds.height - contentHeight) / 2;
    return {
      x: ((event.clientX - bounds.left - contentLeft) / contentWidth) * width,
      y: ((event.clientY - bounds.top - contentTop) / contentHeight) * height,
    };
  };

  const handleCanvasClick = (event: React.MouseEvent<SVGSVGElement>) => {
    if ((event.target as Element).closest("[data-entity-id]")) {
      return;
    }
    onCanvasClick(getCanvasPoint(event));
  };

  const handleCanvasMouseDown = (event: React.MouseEvent<SVGSVGElement>) => {
    if ((event.target as Element).closest("[data-entity-id]")) {
      return;
    }
    onCanvasMouseDown(getCanvasPoint(event), event);
  };

  const handleCanvasMouseMove = (event: React.MouseEvent<SVGSVGElement>) => {
    onCanvasMouseMove(getCanvasPoint(event), event);
  };

  const handleCanvasMouseUp = (event: React.MouseEvent<SVGSVGElement>) => {
    onCanvasMouseUp(getCanvasPoint(event), event);
  };

  const handleCanvasContextMenu = (event: React.MouseEvent<SVGSVGElement>) => {
    event.preventDefault();
    onCanvasContextMenu(getCanvasPoint(event), event);
  };

  const rectanglePoints = rectangleDraft
    ? [
        `${rectangleDraft.anchor.x},${rectangleDraft.anchor.y}`,
        `${rectangleDraft.current.x},${rectangleDraft.anchor.y}`,
        `${rectangleDraft.current.x},${rectangleDraft.current.y}`,
        `${rectangleDraft.anchor.x},${rectangleDraft.current.y}`,
      ].join(" ")
    : "";

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="SketchMath canvas"
      className="sketchmath-canvas"
      onClick={handleCanvasClick}
      onMouseDown={handleCanvasMouseDown}
      onMouseMove={handleCanvasMouseMove}
      onMouseUp={handleCanvasMouseUp}
      onContextMenu={handleCanvasContextMenu}
      data-testid="sketchmath-canvas"
    >
      <GridLayer width={width} height={height} />
      {rectangleDraft ? <polygon points={rectanglePoints} className="sketchmath-draft-rectangle" data-testid="sketchmath-rectangle-draft" /> : null}
      {dragPreviewPoint ? <circle cx={dragPreviewPoint.point.x} cy={dragPreviewPoint.point.y} r={7} className="sketchmath-draft-point" data-testid={`sketchmath-drag-${dragPreviewPoint.id}`} /> : null}
      <EntityLayer
        entities={entities}
        selectedEntityIds={selectedEntityIds}
        focusedEntityId={focusedEntityId}
        onEntityClick={onEntityClick}
        onEntityMouseDown={onEntityMouseDown}
        onDimensionLabelEdit={onDimensionLabelEdit}
      />
      {draftPoint ? <circle cx={draftPoint.x} cy={draftPoint.y} r={7} className="sketchmath-draft-point" data-testid="sketchmath-draft-point" /> : null}
      <PreviewLayer previewResult={previewResult} committedEntityIds={entities.map((entity) => entity.id)} />
    </svg>
  );
};

export default SketchCanvas2D;
