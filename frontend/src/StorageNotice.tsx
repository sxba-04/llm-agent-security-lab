import { HardDrive } from 'lucide-react';
import type { Health } from './types';

export function StorageNotice({ storage }: Readonly<{ storage: Health['storage'] }>) {
  if (storage?.state !== 'low') return null;
  const free = storage.free_bytes;
  const remaining = typeof free === 'number' && Number.isFinite(free) && free >= 0
    ? ` Noch ${(free / 1024 / 1024).toLocaleString('de-DE', { maximumFractionDigits: 1 })} MiB sind auf dem Datenträger des Arbeitsbereichs frei.`
    : '';
  return <aside className="notice warning" role="status" aria-label="Speicherwarnung"><HardDrive size={20} /><div><strong>Der Speicherplatz wird knapp.</strong>{remaining} Sichere den Forschungsbestand extern und prüfe den verfügbaren Speicher, bevor du weitere Dateien importierst oder Versuche startest.</div></aside>;
}
