import type { ReactNode } from "react";

interface PanelProps {
  title: string;
  /** 1px tick on the left of the title, used to colour-code panels. */
  tick?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  testId?: string;
}

/**
 * A framed region of the terminal. Panels are not floating cards: they share the
 * same surface and are separated by hairlines.
 */
export default function Panel({
  title,
  tick = "var(--color-blue)",
  right,
  children,
  className = "",
  bodyClassName = "",
  testId,
}: PanelProps) {
  return (
    <section className={`flex min-h-0 min-w-0 flex-col bg-surface ${className}`} data-testid={testId}>
      <header className="flex h-8 shrink-0 items-center gap-2 border-b border-line px-3">
        <span className="h-3 w-[2px] shrink-0 rounded-full" style={{ background: tick }} />
        <h2 className="panel-title">{title}</h2>
        <div className="ml-auto flex items-center gap-2">{right}</div>
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
