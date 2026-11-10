import { useEffect, useRef, useState } from 'react';
import { Play, RefreshCw } from 'lucide-react';
import { ApiError, post, useResource } from './api';
import { DataFields, ErrorBox, Loading, PageHeader, Panel, statusNames, TextBlock } from './ui';

const pilotPath = '/api/pilot/luna';
const stateNames = {
  disabled: 'Noch nicht freigeschaltet',
  ready: 'Bereit',
  running: 'Läuft',
  completed: 'Abgeschlossen',
  failed: 'Beendet mit Fehler',
};

interface PilotResult {
  status: string;
  technical_acceptance: boolean;
  final_text: string;
  models: string[];
  model_calls: number;
  tool_calls: number;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_eur: string | null;
}
interface PilotStatus { state: keyof typeof stateNames; result: PilotResult | null }

const currency = new Intl.NumberFormat('de-DE', {
  style: 'currency', currency: 'EUR', maximumFractionDigits: 8,
});

function PilotReceipt({ result }: Readonly<{ result: PilotResult }>) {
  const unavailable = 'Unvollständig belegt';
  return <Panel title="Ergebnis">
    <DataFields value={{
      'Laufstatus': statusNames[result.status] || result.status,
      'Technische Abnahme': result.technical_acceptance ? 'Bestanden' : 'Nicht bestanden',
      'Gemeldetes Modell': result.models.join(', ') || unavailable,
      'Modellanfragen': result.model_calls,
      'Werkzeugaufrufe': result.tool_calls,
      'Eingabetokens': result.input_tokens?.toLocaleString('de-DE') ?? unavailable,
      'Ausgabetokens': result.output_tokens?.toLocaleString('de-DE') ?? unavailable,
      'Geschätzte Kosten': result.estimated_cost_eur === null ? unavailable : currency.format(Number(result.estimated_cost_eur)),
    }} />
    {result.final_text && <><h3>Modellantwort</h3><TextBlock label="Modellantwort">{result.final_text}</TextBlock></>}
  </Panel>;
}

export function LunaPilotPage() {
  const { data, error, loading, refresh } = useResource<PilotStatus>(pilotPath);
  const startSent = useRef(false);
  const [starting, setStarting] = useState(false);
  const [notice, setNotice] = useState('');
  // After opening a running attempt, refresh only its persisted status.
  useEffect(() => {
    if (data?.state !== 'running' || error) return;
    const timer = window.setTimeout(refresh, 4000);
    return () => window.clearTimeout(timer);
  }, [data, error, refresh]);

  async function start() {
    if (startSent.current || loading || error || data?.state !== 'ready') return;
    startSent.current = true;
    setStarting(true);
    setNotice('');
    try {
      await post<PilotStatus>(pilotPath);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        setNotice('Ein Start wurde bereits erfasst.');
      } else {
        setNotice('Der Start konnte nicht bestätigt werden. Prüfe den gespeicherten Status vor weiteren Schritten.');
      }
    } finally {
      setStarting(false);
      refresh();
    }
  }

  const state = data?.state;
  let stateText = state && stateNames[state];
  if (starting) stateText = 'Start wird verarbeitet …';
  return <>
    <PageHeader eyebrow="MODELLZUGANG" title="Luna-Pilot" description="GPT-6 Luna beantwortet die Aufgabe zu Ticket A17. Der feste Entwicklungsfall DEV-G1-01 verwendet eine saubere Quelle und die Objektberechtigung P." />
    <div className="stack"><Panel title="Einmaliger Pilotlauf">
      <p>Der Start auf Render kann bis zu vier Modellanfragen auslösen. Das Budget für den gesamten Versuch beträgt höchstens <strong>0,50 €</strong>.</p>
      <ErrorBox error={error || (data && !stateText ? 'Der Server hat keinen gültigen Pilotstatus geliefert.' : '')} />
      {stateText ? <p><output>Status: <strong>{stateText}</strong></output></p> : loading && <Loading text="Pilotstatus wird geladen …" />}
      {notice && (!state || state === 'ready' || state === 'disabled') && <p role="alert">{notice}</p>}
      {state === 'disabled' && <p>Der Pilot ist im Backend noch nicht für den Start freigegeben.</p>}
      {state === 'failed' && !data?.result && <p>Der gespeicherte Versuch enthält keinen vollständigen Ergebnisbeleg. Budgetprotokoll und Anbieternutzung müssen abgeglichen werden.</p>}
      <div className="button-row">
        {state === 'ready' && <button type="button" className="button primary" disabled={starting || startSent.current || loading || Boolean(error)} onClick={() => void start()}><Play size={16} />Luna-Pilot starten</button>}
        <button type="button" className="button secondary" disabled={loading || starting} onClick={refresh}><RefreshCw size={16} />Status aktualisieren</button>
      </div>
    </Panel>
    {data?.result && <PilotReceipt result={data.result} />}
    </div>
  </>;
}
