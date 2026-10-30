export function buildComparisonTable(state: Record<string, unknown>): HTMLElement {
  const headers = (state.headers as string[] | undefined) ?? [];
  const rows = (state.rows as (string | number)[][] | undefined) ?? [];

  if (rows.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No table data.';
    return empty;
  }

  const table = document.createElement('table');
  table.className = 'cmp';
  if (headers.length > 0) {
    const thead = document.createElement('thead');
    const tr = document.createElement('tr');
    headers.forEach((h) => {
      const th = document.createElement('th');
      th.textContent = h;
      tr.appendChild(th);
    });
    thead.appendChild(tr);
    table.appendChild(thead);
  }
  const tbody = document.createElement('tbody');
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    row.forEach((cell) => {
      const td = document.createElement('td');
      td.textContent = String(cell);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  return table;
}
