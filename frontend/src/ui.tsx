import type { ReactNode } from 'react';
import { AlertCircle, ArrowRight, Check, ChevronRight, Inbox, LoaderCircle } from 'lucide-react';
import type { Data, Json } from './types';

export const variantNames: Record<string, string> = { B: 'Basis', F: 'Textfilter', P: 'Policy', FP: 'Filter + Policy' };
export const sourceNames: Record<string, string> = { clean: 'Saubere Quelle', attack: 'Manipulierte Quelle' };
export const goalNames: Record<string, string> = { G1: 'Unberechtigtes Lesen', G2: 'Unberechtigtes Schreiben', G3: 'Inhaltliche Manipulation' };
export const statusNames: Record<string, string> = { queued: 'Eingeplant', running: 'Läuft', cancelling: 'Wird beendet', completed: 'Abgeschlossen', cancelled: 'Abgebrochen', stopped: 'Gestoppt', interrupted: 'Unterbrochen', refused: 'Verweigert', technical_error: 'Technischer Fehler', limit_exceeded: 'Limit erreicht', budget_exhausted: 'Budget erreicht', pending: 'Offen', consensus: 'Übereinstimmung', disagreement: 'Abweichung', adjudicated: 'Geklärt' };
export const metricNames: Record<string, string> = { proposal_violation: 'Unberechtigter Vorschlag', backend_violation: 'Unberechtigter Effekt', context_disclosure: 'Offenlegung im Kontext', output_disclosure: 'Offenlegung in der Ausgabe', attacker_goal: 'Angriffsziel erreicht', legitimate_success: 'Legitime Aufgabe erfüllt', false_block: 'Fehlblockade' };
export function formatDate(date: string) { const d = new Date(date); return isNaN(d.getTime()) ? 'Zeitpunkt unbekannt' : new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(d); }
export function Pill({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) { return <span className={`pill ${tone}`}>{children}</span>; }
export function Status({ value }: { value: string }) { return <Pill tone={['running', 'queued', 'cancelling'].includes(value) ? 'blue' : ['completed', 'consensus', 'adjudicated'].includes(value) ? 'green' : ['technical_error', 'disagreement', 'interrupted', 'stopped'].includes(value) ? 'red' : 'neutral'}>{statusNames[value] || value}</Pill>; }
export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>; }
export function Panel({ title, subtitle, children, action, className = '' }: { title?: ReactNode; subtitle?: string; children: ReactNode; action?: ReactNode; className?: string }) { return <section className={`panel ${className}`}>{(title || action) && <header className="panel-header"><div>{title && <h2>{title}</h2>}{subtitle && <p>{subtitle}</p>}</div>{action}</header>}<div className="panel-body">{children}</div></section>; }
export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) { return <div className="empty-state"><span className="empty-icon"><Inbox size={24} /></span><h3>{title}</h3><p>{children}</p>{action}</div>; }
export function ErrorBox({ error, retry }: { error: string; retry?: () => void }) { return error ? <div role="alert" className="notice error"><AlertCircle size={19} /><div>{error}</div>{retry && <button className="text-button" onClick={retry}>Erneut versuchen</button>}</div> : null; }
export function Success({ children }: { children: ReactNode }) { return <div className="notice success" role="status"><Check size={18} /><span>{children}</span></div>; }
export function Loading({ text = 'Daten werden geladen …' }: { text?: string }) { return <div className="loading" role="status"><LoaderCircle className="spin" size={20} />{text}</div>; }
export function EngineeringNote() { return <p className="engineering-note"><span className="tiny-dot" />Diese Werkbank startet Mock-Läufe zur Funktionsprüfung. Mock-Ergebnisse sind keine empirischen LLM-Befunde.</p>; }
export function JsonBlock({ value }: { value: unknown }) { return <pre className="code-block">{JSON.stringify(value, null, 2)}</pre>; }
export function TextBlock({ children, className = '' }: { children: ReactNode; className?: string }) { return <div className={`text-block ${className}`}>{children || <span className="muted">Kein Inhalt vorhanden.</span>}</div>; }
export function Disclosure({ title, children, open = false }: { title: string; children: ReactNode; open?: boolean }) { return <details className="disclosure" open={open}><summary><ChevronRight size={16} />{title}</summary><div>{children}</div></details>; }
export function GoButton({ children, onClick }: { children: ReactNode; onClick: () => void }) { return <button className="text-button" onClick={onClick}>{children}<ArrowRight size={16} /></button>; }
export function Value({ value }: { value: Json | undefined }) { return value !== null && typeof value === 'object' ? <JsonBlock value={value} /> : <span className="wrap">{value === undefined || value === null ? '—' : String(value)}</span>; }
export function DataFields({ value }: { value: Data }) { return <dl className="data-fields">{Object.entries(value).map(([key, val]) => <div key={key}><dt>{key}</dt><dd><Value value={val} /></dd></div>)}</dl>; }
export function TicketDiff({ before, after }: { before: Record<string, Data>; after: Record<string, Data> }) {
  const ids = [...new Set([...Object.keys(before), ...Object.keys(after)])];
  return <div className="ticket-list">{ids.length === 0 && <p className="muted">Keine Ticketdaten vorhanden.</p>}{ids.map(id => {
    const changed = JSON.stringify(before[id]) !== JSON.stringify(after[id]);
    return <details key={id} className={`ticket-diff ${changed ? 'changed' : ''}`} open={changed}>
      <summary><span className="mono">{id}</span><span>{String(after[id]?.title || before[id]?.title || 'Ticket')}</span><Pill tone={changed ? 'amber' : 'neutral'}>{changed ? 'Verändert' : 'Unverändert'}</Pill></summary>
      <div className="split"><div><h4>Vorher</h4><JsonBlock value={before[id] || null} /></div><div><h4>Nachher</h4><JsonBlock value={after[id] || null} /></div></div>
    </details>;
  })}</div>;
}
/** Longest common subsequence of lines; each source remains fully visible. */
export function diffLines(clean: string, attack: string): { clean: { text: string; changed: boolean }[]; attack: { text: string; changed: boolean }[] } {
  const left = clean.split('\n'), right = attack.split('\n');
  // Bound work for large imported documents; full text is still displayed.
  if (left.length * right.length > 250_000) {
    const a = new Set(left), b = new Set(right);
    return { clean: left.map(text => ({ text, changed: !b.has(text) })), attack: right.map(text => ({ text, changed: !a.has(text) })) };
  }
  const lengths = Array.from({ length: left.length + 1 }, () => new Uint32Array(right.length + 1));
  for (let i = left.length - 1; i >= 0; i--) for (let j = right.length - 1; j >= 0; j--) lengths[i][j] = left[i] === right[j] ? lengths[i + 1][j + 1] + 1 : Math.max(lengths[i + 1][j], lengths[i][j + 1]);
  const l = left.map(text => ({ text, changed: true })), r = right.map(text => ({ text, changed: true }));
  let i = 0, j = 0;
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) { l[i++].changed = false; r[j++].changed = false; }
    else if (lengths[i + 1][j] >= lengths[i][j + 1]) i++; else j++;
  }
  return { clean: l, attack: r };
}
export function SourceDiff({ clean, attack }: { clean: string; attack: string }) {
  const diff = diffLines(clean, attack);
  return <div className="split source-diff">{(['clean', 'attack'] as const).map(source => <div key={source} className={`source-pane ${source}`}><div className="source-heading"><span className="tiny-dot" /><h3>{sourceNames[source]}</h3></div><pre>{diff[source].map((line, index) => <span key={index} className={line.changed ? 'diff-line changed' : 'diff-line'}><span className="line-number" aria-hidden="true">{index + 1}</span><span>{line.text || '\u00a0'}</span></span>)}</pre></div>)}</div>;
}
