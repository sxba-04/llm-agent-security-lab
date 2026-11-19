import { useResource } from './api';
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

export function CleanBPlanPage() {
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
