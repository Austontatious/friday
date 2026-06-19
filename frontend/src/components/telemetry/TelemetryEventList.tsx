import type { TelemetryEvent } from "../../telemetry/sessionTelemetry";
import { formatTelemetryRaw } from "../../telemetry/sessionTelemetry";

type TelemetryEventListProps = {
  events: TelemetryEvent[];
  emptyMessage?: string;
};

const TelemetryEventList = ({ events, emptyMessage = "No system events yet." }: TelemetryEventListProps) => (
  <div className="friday-event-list">
    {events.length ? (
      events.map((event) => (
        <article key={event.id} className={`friday-event friday-event-${event.level}`}>
          <div className="friday-event-header">
            <span>{event.timestamp}</span>
            <strong>{event.title}</strong>
          </div>
          <p>{event.detail}</p>
          {event.raw !== undefined ? (
            <details className="friday-raw-details">
              <summary>Raw details</summary>
              <pre>{formatTelemetryRaw(event.raw)}</pre>
            </details>
          ) : null}
        </article>
      ))
    ) : (
      <p className="friday-quiet-empty">{emptyMessage}</p>
    )}
  </div>
);

export default TelemetryEventList;
