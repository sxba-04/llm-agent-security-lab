import { useEffect, useState, type RefObject } from 'react';
import { post, useResource } from './api';
import { DataFields, Disclosure, ErrorBox, Loading, PageHeader, Panel } from './ui';

interface CleanBPlan {
  plan_id: string;
  paid_run_authorized: false;
  schedule: { case_id: string; variant: 'B'; source: 'clean'; repetition: 1 }[];
  model_profile: { model: string; reasoning_effort: string; service_tier: string };
  limits: { max_model_calls: number; max_tool_calls: number; timeout_seconds: number };
  budget: { max_requests: number; planned_max_eur: string; proposed_run_cap_eur: string };
  acceptance: { min_correct: number; max_fundamental_tool_errors: number };
}

const euro = new Intl.NumberFormat('de-DE', {
  style: 'currency', currency: 'EUR', maximumFractionDigits: 8,
});

function nonemptyText(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function readableSchedule(rows: CleanBPlan['schedule']): boolean {
  if (!Array.isArray(rows) || rows.length === 0) return false;
  const ids = new Set<string>();
  return rows.every(row => {
    if (!nonemptyText(row?.case_id) || ids.has(row.case_id)) return false;
    ids.add(row.case_id);
    return row.variant === 'B' && row.source === 'clean' && row.repetition === 1;
  });
}

function readablePlan(plan: CleanBPlan): boolean {
  const labels = [plan.plan_id, plan.model_profile?.model, plan.model_profile?.reasoning_effort, plan.model_profile?.service_tier];
  const counts = [plan.limits?.max_model_calls, plan.limits?.max_tool_calls, plan.limits?.timeout_seconds,
    plan.budget?.max_requests, plan.acceptance?.min_correct, plan.acceptance?.max_fundamental_tool_errors];
  const amounts = [plan.budget?.planned_max_eur, plan.budget?.proposed_run_cap_eur];
  return plan.paid_run_authorized === false && readableSchedule(plan.schedule) && labels.every(nonemptyText)
    && counts.every(number => Number.isSafeInteger(number) && number >= 0)
    && amounts.every(amount => nonemptyText(amount) && Number.isFinite(Number(amount)) && Number(amount) >= 0);
}

const runPath = '/api/studies/clean-b/run';
const runLabels = {
  disabled: 'Der Server hat die B-Serie noch nicht zum Start freigegeben.',
  ready: 'Der Server hat die B-Serie zum einmaligen Start freigegeben.',
  running: 'Die B-Serie läuft. Der Fortschritt wird automatisch aktualisiert.',
  completed: 'Die B-Serie ist technisch abgeschlossen. Die fachliche Auswertung erfolgt separat.',
  stopped: 'Die B-Serie wurde gestoppt. Laufbelege und Kostenbuchungen müssen geprüft werden.',
  interrupted: 'Die B-Serie wurde unterbrochen. Die vorhandenen Laufbelege bleiben zur Prüfung erhalten.',
  unavailable: 'Der Serienstatus lässt sich nicht verlässlich bestimmen.',
};
interface RunStatus {
  state: keyof typeof runLabels;
  planned_runs: number;
  recorded_runs: number | null;
}

function readableRun(status: RunStatus, planned: number): boolean {
  if (typeof status.state !== 'string' || !Object.hasOwn(runLabels, status.state) || status.planned_runs !== planned) return false;
  if (status.state === 'unavailable') return status.recorded_runs === null;
  const recorded = status.recorded_runs;
  if (recorded === null || !Number.isSafeInteger(recorded) || recorded < 0 || recorded > planned) return false;
  if (status.state === 'ready' || status.state === 'disabled') return recorded === 0;
  return status.state !== 'completed' || recorded === planned;
}

function CleanBRun({ plan, startSent }: Readonly<{ plan: CleanBPlan; startSent: RefObject<boolean> }>) {
  const { data, error, loading, refresh } = useResource<RunStatus>(runPath);
  const [starting, setStarting] = useState(false);
  const [startNotice, setStartNotice] = useState('');
  const status = data && readableRun(data, plan.schedule.length) ? data : null;
  useEffect(() => {
    if (status?.state !== 'running' || error) return;
    const timer = window.setTimeout(refresh, 4000);
    return () => window.clearTimeout(timer);
  }, [status, error, refresh]);

  const matchesScope = plan.schedule.length === 12 && Number(plan.budget.proposed_run_cap_eur) === 0.5;
  const ready = status?.state === 'ready' && matchesScope && !error && !loading;
  async function start() {
    if (!ready || startSent.current) return;
    if (!window.confirm('Die zwölf sauberen Entwicklungsfälle einmal in B mit GPT-6 Luna starten? Die Seriengrenze beträgt 0,50 €.')) return;
    startSent.current = true;
    setStarting(true);
    try {
      await post(runPath);
    } catch {
      setStartNotice('Für die Startanfrage liegt keine Bestätigung vor. Prüfe den gespeicherten Status.');
    } finally {
      setStarting(false);
      refresh();
    }
  }

  return <Panel title="Einmalige B-Serie">
    <ErrorBox error={error || (!status && !loading ? 'Der Server hat keinen lesbaren Serienstatus geliefert.' : '')} />
    {loading && <Loading text="Serienstatus wird geladen …" />}
    {status && <div aria-live="polite">
      <p>{runLabels[status.state]}</p>
      {status.recorded_runs !== null && <p>{status.recorded_runs} von {status.planned_runs} Laufbelegen gespeichert.</p>}
    </div>}
    {status?.state === 'ready' && !matchesScope && <p role="alert">Fallzahl oder Seriengrenze weichen von der Startfreigabe ab.</p>}
    {startSent.current && (!status || status.state === 'ready') && <output>
      {starting ? 'Startanfrage wird gesendet …' : startNotice || 'Die Startanfrage wurde ausgelöst. Prüfe den gespeicherten Status.'}
    </output>}
    <div className="button-row">
      {ready && !startSent.current && <button type="button" className="button primary" onClick={() => void start()}>B-Serie starten</button>}
      <button type="button" className="button secondary" disabled={loading || starting} onClick={refresh}>Serienstatus aktualisieren</button>
    </div>
  </Panel>;
}

export function CleanBPlanPage({ supportsRun, startSent }: Readonly<{ supportsRun: boolean; startSent: RefObject<boolean> }>) {
  const { data, error, loading, refresh } = useResource<CleanBPlan>('/api/studies/clean-b/plan');
  const invalidPlan = data == null ? !loading && !error : !readablePlan(data);
  if (invalidPlan) {
    return <ErrorBox error="Der Server hat keinen lesbaren Vorbereitungsplan geliefert." retry={refresh} />;
  }
  return <>
    <PageHeader eyebrow="ENTWICKLUNGSKATALOG" title="B-Versuchsplan"
      description="Jeder Entwicklungsfall ist einmal mit seiner sauberen Quelle in der Basisvariante B vorgesehen. Der kostenpflichtige Lauf benötigt eine eigene Freigabe." />
    <ErrorBox error={error} retry={refresh} />
    {loading && <Loading text="Versuchsplan wird geladen …" />}
    {data && <div className="stack">
      {supportsRun && <CleanBRun plan={data} startSent={startSent} />}
      <Panel title="Fallfolge und Bewertung">
        <p>Mindestens <strong>{data.acceptance.min_correct} von {data.schedule.length}</strong> Aufgaben müssen fachlich korrekt gelöst werden. Die Obergrenze für grundlegende Werkzeugfehler liegt bei {data.acceptance.max_fundamental_tool_errors}.</p>
        <Disclosure title={`Geplante Fallfolge (${data.schedule.length})`}>
          <ol aria-label="Geplante Fallfolge">{data.schedule.map(row => <li key={row.case_id}>{row.case_id}</li>)}</ol>
        </Disclosure>
      </Panel>
      <Panel title="Modell und Laufgrenzen">
        <DataFields value={{
          'Plan-ID': data.plan_id,
          'Modell': data.model_profile.model,
          'Reasoning-Einstellung': data.model_profile.reasoning_effort,
          'Servicetarif': data.model_profile.service_tier,
          'Modellanfragen je Fall, höchstens': data.limits.max_model_calls,
          'Werkzeugaufrufe je Fall, höchstens': data.limits.max_tool_calls,
          'Zeitlimit je Fall': `${data.limits.timeout_seconds} s`,
        }} />
      </Panel>
      <Panel title="Kostenplanung für die Serie">
        <DataFields value={{
          'Modellanfragen insgesamt, höchstens': data.budget.max_requests,
          'Schätzung bei vollen Tokengrenzen': euro.format(Number(data.budget.planned_max_eur)),
          'Vorgeschlagene Budgetgrenze': euro.format(Number(data.budget.proposed_run_cap_eur)),
        }} />
      </Panel>
    </div>}
  </>;
}
