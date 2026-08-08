import React from "react";
import GridLayer from "./GridLayer";
import EntityLayer from "./EntityLayer";
import PreviewLayer from "./PreviewLayer";
import type { SketchMathEntity, SketchMathOperationResult, SketchMathProfileCandidate } from "../../services/sketchmath";

type Point = { x: number; y: number };
type ViewBox = { x: number; y: number; width: number; height: number };

type SketchCanvas2DProps = {
  width: number;
  height: number;
  viewBox: ViewBox;
  entities: SketchMathEntity[];
  previewResult: SketchMathOperationResult | null;
  selectedEntityIds: string[];
  focusedEntityId: string | null;
  draftPoint: Point | null;
  rectangleDraft: { anchor: Point; current: Point } | null;
  circleDraft?: { center: Point; current: Point } | null;
  arcDraft?: { points: Point[]; current: Point } | null;
  dragPreviewPoint: { id: string; point: Point } | null;
  holePlacementPreview?: { center: Point; diameter: number } | null;
  holePlacementActive?: boolean;
  showDebugLabels?: boolean;
  profileCandidates?: SketchMathProfileCandidate[];
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
  viewBox,
  entities,
  previewResult,
  selectedEntityIds,
  focusedEntityId,
  draftPoint,
  rectangleDraft,
  circleDraft,
  arcDraft,
  dragPreviewPoint,
  holePlacementPreview,
  holePlacementActive = false,
  showDebugLabels = false,
  profileCandidates = [],
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
    const scale = Math.min(bounds.width / viewBox.width, bounds.height / viewBox.height);
    const contentWidth = viewBox.width * scale;
    const contentHeight = viewBox.height * scale;
    const contentLeft = (bounds.width - contentWidth) / 2;
    const contentTop = (bounds.height - contentHeight) / 2;
    return {
      x: viewBox.x + ((event.clientX - bounds.left - contentLeft) / contentWidth) * viewBox.width,
      y: viewBox.y + ((event.clientY - bounds.top - contentTop) / contentHeight) * viewBox.height,
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
      viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`}
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
      {circleDraft ? <circle cx={circleDraft.center.x} cy={circleDraft.center.y} r={Math.hypot(circleDraft.current.x - circleDraft.center.x, circleDraft.current.y - circleDraft.center.y)} fill="none" className="sketchmath-draft-rectangle" data-testid="sketchmath-circle-draft" /> : null}
      {arcDraft ? (
        <polyline
          points={[...arcDraft.points, arcDraft.current].map((point) => `${point.x},${point.y}`).join(" ")}
          fill="none"
          className="sketchmath-draft-rectangle"
          data-testid="sketchmath-arc-draft"
        />
      ) : null}
      {dragPreviewPoint ? <circle cx={dragPreviewPoint.point.x} cy={dragPreviewPoint.point.y} r={7} className="sketchmath-draft-point" data-testid={`sketchmath-drag-${dragPreviewPoint.id}`} /> : null}
      {holePlacementPreview ? (
        <circle
          cx={holePlacementPreview.center.x}
          cy={holePlacementPreview.center.y}
          r={Math.max(4, holePlacementPreview.diameter / 2)}
          className="sketchmath-hole-placement-ghost"
          data-testid="sketchmath-hole-placement-ghost"
        />
      ) : null}
      <EntityLayer
        entities={entities}
        selectedEntityIds={selectedEntityIds}
        focusedEntityId={focusedEntityId}
        placementActive={holePlacementActive}
        onEntityClick={onEntityClick}
        onEntityMouseDown={onEntityMouseDown}
        onDimensionLabelEdit={onDimensionLabelEdit}
        showDebugLabels={showDebugLabels}
        profileCandidates={profileCandidates}
      />
      {draftPoint ? <circle cx={draftPoint.x} cy={draftPoint.y} r={7} className="sketchmath-draft-point" data-testid="sketchmath-draft-point" /> : null}
      <PreviewLayer previewResult={previewResult} committedEntityIds={entities.map((entity) => entity.id)} />
    </svg>
  );
};

export default SketchCanvas2D;
