import { useState } from 'react';
import type { ReactNode } from 'react';
import { downloadFile, message } from './api';

export function DownloadButton({ path, filename, className, children }: { path: string; filename: string; className: string; children: ReactNode }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function download() {
    setBusy(true); setError('');
    try { await downloadFile(path, filename); }
    catch (err) { setError(message(err)); }
    finally { setBusy(false); }
  }
  return <span className="download-control"><button type="button" className={className} disabled={busy} onClick={() => void download()} aria-busy={busy}>{children}</button>{error && <span className="download-error" role="alert">{error}</span>}</span>;
}
