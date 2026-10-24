(() => {
  const summary = document.getElementById('system-summary');
  const items = document.getElementById('system-items');
  const storage = document.getElementById('system-storage');
  for (const link of document.querySelectorAll('.system-monitor-link')) {
    link.href = `${location.protocol}//${location.hostname}:8083`;
  }
  let lastSuccess = null;
  let failures = 0;
  const stamp = ts => ts == null ? 'Noch keine erfolgreiche Aktualisierung' : new Date(ts*1000).toLocaleString('de-DE', {timeZone:'Europe/Berlin'});
  const size = bytes => (bytes/1024/1024).toLocaleString('de-DE',{maximumFractionDigits:1})+' MiB';
  async function refresh() {
    try {
      const response = await fetch('/api/system', {signal:AbortSignal.timeout(10000), cache:'no-store'});
      if (!response.ok) throw new Error('status');
      const data = await response.json();
      lastSuccess = data;
      failures = 0;
      render(data);
    } catch {
      failures += 1;
      if (lastSuccess) {
        render(lastSuccess);
        summary.textContent += ' · Aktualisierung verzögert';
      } else if (failures < 3) {
        summary.textContent = 'Status wird erneut abgerufen …';
      } else {
        summary.textContent = 'Status vorübergehend nicht erreichbar';
        items.replaceChildren();
        storage.textContent = 'Noch keine Systeminformationen empfangen.';
      }
    } finally { setTimeout(refresh, failures ? 2000 : 10000); }
  }
  function render(data) {
      summary.textContent = data.items.map(i => i.name+': '+i.label).join(' · ');
      items.replaceChildren();
      for (const item of data.items) {
        const card = document.createElement('article');
        card.className = 'system-item '+item.level;
        const title = document.createElement('h3'); title.textContent = item.name;
        const label = document.createElement('p'); label.textContent = item.label;
        const updated = document.createElement('p'); updated.className = 'muted'; updated.textContent = stamp(item.last_success);
        card.append(title,label,updated);
        if (item.error) { const error = document.createElement('p'); error.textContent = item.error; card.append(error); }
        items.append(card);
      }
      const s = data.storage;
      storage.textContent = 'Version '+data.version+' · '+(s.error || 'Datenbank: '+size(s.database_bytes)+' · Schreibjournal: '+size(s.wal_bytes)+' · Freier Speicher: '+size(s.free_bytes)+' · Speicherprüfung: '+stamp(s.checked_at));
  }
  refresh();
})();
