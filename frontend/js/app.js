const $ = (s, root = document) => root.querySelector(s);
const state = { page: "dashboard", module: "loja_db", table: "", pageNo: 1, search: "", lastRun: null };
const labels = { loja_db: "Loja Online", escola_db: "Sistema Escolar" };
const view = $("#app-view");

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Erro HTTP ${response.status}`);
  return data;
}
function esc(v) { return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function toast(message) { const el = $("#toast"); el.textContent = message; el.classList.add("show"); setTimeout(() => el.classList.remove("show"), 2600); }
function go(page) { state.page = page; document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.page === page)); render(); }
function header(title) { $("#page-title").textContent = title; }
function stat(label, value, foot) { return `<div class="stat"><div class="stat-label">${label}</div><div class="stat-value">${value}</div><div class="stat-foot">${foot}</div></div>`; }
function panel(title, body, right = "") { return `<section class="panel"><div class="panel-head"><h2>${title}</h2>${right}</div><div class="panel-body">${body}</div></section>`; }

async function render() {
  view.innerHTML = '<div class="loading">A carregar…</div>';
  try {
    if (state.page === "dashboard") await dashboard();
    else if (state.page === "generate") generatePage();
    else if (state.page === "tables") await tablesPage();
    else if (state.page === "reports") await reportsPage();
  } catch (e) { view.innerHTML = `<div class="alert error">${esc(e.message)}</div>`; }
}

async function dashboard() {
  header("Dashboard");
  const [health, shop, school, reports] = await Promise.all([
    api("/api/health"), api("/api/tables?module=loja_db"), api("/api/tables?module=escola_db"), api("/api/reports")
  ]);
  $("#api-status").textContent = health.status === "ok" ? "API activa" : "API indisponível";
  const total = [...shop.tables, ...school.tables].reduce((sum, t) => sum + t.count, 0);
  view.innerHTML = `
    <section class="welcome"><div><span class="eyebrow">CENTRO DE OPERAÇÕES</span><h2>Dados preparados para crescer.</h2><p>Gera dados sintéticos ou importa produtos de uma API pública, explora tabelas e valida relações em bases SQLite reais.</p></div><div class="hero-icon">⌘</div></section>
    <div class="stats">${stat("Tabelas detectadas", shop.tables.length + school.tables.length, "Descobertas automaticamente no SQLite")}${stat("Registos existentes", total.toLocaleString("pt-PT"), "Somatório dos dois módulos")}${stat("Execuções registadas", reports.reports.length, "Histórico persistido em SQLite")}</div>
    <h2 class="section-title">Bases de dados</h2><div class="modules">
      <article class="module-card"><div class="module-icon">▣</div><div><h3>Loja Online</h3><p>Produtos, categorias, clientes, encomendas e itens de encomenda. As relações são verificadas durante a inserção.</p><button class="btn btn-primary" data-action="module-shop">Explorar Loja Online →</button></div></article>
      <article class="module-card"><div class="module-icon">▤</div><div><h3>Sistema Escolar</h3><p>Alunos, professores, turmas, disciplinas, matrículas e notas, com integridade referencial.</p><button class="btn btn-primary" data-action="module-school">Explorar Sistema Escolar →</button></div></article>
    </div>
    <h2 class="section-title">Começar</h2>${panel("Alimentação de dados", `<p class="muted">Escolhe uma base de dados e define quantos registos principais queres gerar. O DataForge prepara as dependências e guarda os resultados no SQLite.</p><button class="btn btn-primary" data-action="generate">Nova execução →</button>`)}
  `;
}

function generatePage() {
  header("Alimentação de dados");
  view.innerHTML = `
    <div class="muted" style="margin-bottom:18px">Configura a execução de geração de dados. Os registos são inseridos numa base SQLite real.</div>
    ${panel("Configuração da execução", `
      <form id="generate-form">
        <div class="form-grid">
          <div class="field"><label for="module">Base de dados de destino</label><select id="module"><option value="loja_db">Loja Online - loja.db</option><option value="escola_db">Sistema Escolar - escola.db</option></select><div class="hint">A API inspecciona as tabelas e as relações da base seleccionada.</div></div>
          <div class="field"><label for="quantity">Quantidade de registos principais</label><input id="quantity" type="number" min="1" max="5000" value="100" required><div class="hint">Valor permitido: 1 a 5000. As tabelas dependentes podem aumentar o total inserido.</div></div>
          <div class="field"><label for="origin">Origem dos dados</label><select id="origin"><option value="sintetico">Dados sintéticos</option><option value="internet">Internet - produtos da API DummyJSON</option><option value="misto">Misto - Internet + sintéticos</option></select><div class="hint">Internet/Misto aplica-se à Loja Online. Usa a API pública DummyJSON; o Sistema Escolar aceita apenas dados sintéticos.</div></div>
          <div class="field"><label>Integridade</label><input value="Chaves estrangeiras activadas + transacção" disabled><div class="hint">Se uma validação falhar, a transacção não deve ser considerada concluída.</div></div>
        </div>
        <div class="form-actions"><button class="btn btn-primary" id="run-btn" type="submit">▶ Executar alimentação</button></div>
      </form><div id="run-result"></div>
    `)}
    ${panel("Como funciona", `<div class="table-list"><div class="table-item"><strong>01 · Inspecção</strong><p>Detecta as tabelas reais com sqlite_master e as colunas com PRAGMA.</p></div><div class="table-item"><strong>02 · Dependências</strong><p>Prepara tabelas-pai antes de inserir dados dependentes.</p></div><div class="table-item"><strong>03 · Inserção SQL</strong><p>Usa uma transacção SQLite e mantém as chaves estrangeiras activas.</p></div><div class="table-item"><strong>04 · Relatório</strong><p>Guarda o resultado e as contagens por tabela no histórico DataForge.</p></div></div>`)}
  `;
  $("#module").value = state.module;
  const originSelect = $("#origin");
  function updateOrigins() {
    const school = $("#module").value === "escola_db";
    [...originSelect.options].forEach(option => { if (option.value !== "sintetico") option.disabled = school; });
    if (school) originSelect.value = "sintetico";
  }
  $("#module").addEventListener("change", updateOrigins); updateOrigins();
  $("#generate-form").addEventListener("submit", async e => {
    e.preventDefault(); const btn = $("#run-btn"); btn.disabled = true; btn.textContent = "A gerar dados…";
    const module = $("#module").value, quantity = Number($("#quantity").value), origin = $("#origin").value;
    const phases = [
      { at: 0, title: "A preparar a execução", detail: "A confirmar o módulo e os parâmetros seleccionados." },
      { at: 10000, title: origin === "internet" ? "A recolher dados da Internet" : "A gerar dados", detail: origin === "internet" ? "A consultar a fonte de dados web e a organizar os resultados." : "A criar registos e a preparar os dados relacionados." },
      { at: 24000, title: "A validar os dados", detail: "A verificar campos obrigatórios e relações entre registos." },
      { at: 39000, title: "A inserir nas tabelas", detail: "A guardar os registos na base de dados SQLite." },
      { at: 52000, title: "A finalizar a execução", detail: "A confirmar a integridade e a preparar o relatório." }
    ];
    const showProgress = (phaseIndex, elapsed) => {
      const phase = phases[phaseIndex] || { title: "Execução concluída", detail: "Os resultados foram guardados e o relatório está pronto." };
      const progress = phaseIndex === 5 ? 100 : Math.min(96, Math.round((elapsed / 60000) * 100));
      $("#run-result").innerHTML = `<section class="processing-card" aria-live="polite"><div class="processing-top"><div><span class="processing-kicker">EXECUÇÃO EM CURSO</span><h3>${esc(phase.title)}</h3><p>${esc(phase.detail)}</p></div><div class="processing-clock">${String(Math.floor(elapsed / 1000)).padStart(2, "0")}s</div></div><div class="progress-track"><div class="progress-fill" style="width:${progress}%"></div></div><div class="progress-meta"><span>${progress}%</span><span>Não feches esta página</span></div><ol class="process-steps">${phases.map((item, i) => `<li class="${i < phaseIndex ? "is-done" : i === phaseIndex ? "is-active" : ""}"><span class="step-mark">${i < phaseIndex ? "✓" : i + 1}</span><span>${esc(item.title.replace(/^A /, ""))}</span><small>${i < phaseIndex ? "Concluído" : i === phaseIndex ? "Em curso" : "Pendente"}</small></li>`).join("")}<li class="${phaseIndex === 5 ? "is-done" : ""}"><span class="step-mark">${phaseIndex === 5 ? "✓" : "6"}</span><span>Execução concluída</span><small>${phaseIndex === 5 ? "Concluído" : "Pendente"}</small></li></ol><p class="processing-note">A operação está a decorrer. O tempo apresentado inclui a etapa de processamento visual para acompanhar cada fase.</p></section>`;
    };
    try {
      const request = api("/api/generate", { method: "POST", body: JSON.stringify({ module, quantity, origin }) })
        .then(value => ({ ok: true, value }), error => ({ ok: false, error }));
      let result;
      const started = Date.now();
      while (Date.now() - started < 60000) {
        const elapsed = Date.now() - started;
        const phaseIndex = phases.reduce((idx, phase, i) => elapsed >= phase.at ? i : idx, 0);
        showProgress(phaseIndex, elapsed);
        const settled = await Promise.race([request, new Promise(resolve => setTimeout(() => resolve(null), Math.min(350, 60000 - elapsed)))]);
        if (settled) { if (!settled.ok) throw settled.error; result = settled.value; }
        if (!result && settled === null) continue;
        if (result) await new Promise(resolve => setTimeout(resolve, Math.min(350, 60000 - (Date.now() - started))));
      }
      if (!result) { const settled = await request; if (!settled.ok) throw settled.error; result = settled.value; }
      showProgress(5, 60000);
      await new Promise(resolve => setTimeout(resolve, 250));
      state.lastRun = result; state.module = module;
      $("#run-result").innerHTML = `<div class="alert"><strong>Execução concluída.</strong> Foram inseridos ${result.total_records_inserted.toLocaleString("pt-PT")} registos em <b>${esc(result.database_file)}</b>. Validação de chaves estrangeiras: ${result.foreign_key_errors === 0 ? "sem erros" : "com erros"}.</div>
      <div class="result-grid"><div class="result-box"><span>Quantidade pedida</span><strong>${result.quantity}</strong></div><div class="result-box"><span>Total inserido</span><strong>${result.total_records_inserted}</strong></div><div class="result-box"><span>Tabelas alteradas</span><strong>${Object.values(result.table_counts).filter(n => n > 0).length}</strong></div></div>
      ${result.imported_online ? `<div class="alert">Fonte: ${esc(result.source)}. Produtos importados da Internet: <b>${result.imported_online}</b>. Produtos sintéticos: <b>${result.generated_synthetic_products}</b>. Clientes e encomendas são sintéticos.</div>` : ""}
      ${panel("Registos inseridos por tabela", `<div class="table-wrap"><table><thead><tr><th>Tabela</th><th>Novos registos</th></tr></thead><tbody>${Object.entries(result.table_counts).map(([t, n]) => `<tr><td>${esc(t)}</td><td>${n}</td></tr>`).join("")}</tbody></table></div>`)}`;
      toast("Dados guardados no SQLite.");
    } catch (err) { $("#run-result").innerHTML = `<div class="alert error">${esc(err.message)}</div>`; }
    finally { btn.disabled = false; btn.textContent = "Executar alimentação"; }
  });
}
async function tablesPage() {
  header("Explorar tabelas");
  view.innerHTML = `${panel("Seleccionar módulo", `<div class="form-grid"><div class="field"><label>Base de dados</label><select id="table-module"><option value="loja_db">Loja Online</option><option value="escola_db">Sistema Escolar</option></select></div><div class="field"><label>Pesquisa de registos</label><input id="table-search" placeholder="Pesquisar em todas as colunas…"></div></div>`)}<div id="table-catalogue"></div><div id="rows-panel"></div>
    ${panel("Limpeza de dados", `<p class="muted">Apaga todos os registos do módulo seleccionado, incluindo tabelas relacionadas. Esta acção não pode ser desfeita. O histórico de relatórios do DataForge será preservado.</p><button class="btn btn-danger" id="clear-module">Apagar todos os registos de ${labels[state.module]}</button><div id="clear-result"></div>`)}`;
  $("#table-module").value = state.module;
  $("#table-module").addEventListener("change", () => { state.module = $("#table-module").value; state.table = ""; const clearButton = $("#clear-module"); if (clearButton) clearButton.textContent = `Apagar todos os registos de ${labels[state.module]}`; loadTables(); });
  $("#clear-module").addEventListener("click", async () => {
    const module = $("#table-module").value;
    const confirmed = window.confirm(`ATENÇÃO: vais apagar TODOS os registos de ${labels[module]}. O histórico de relatórios será preservado. Queres continuar?`);
    if (!confirmed) return;
    const button = $("#clear-module"); button.disabled = true; button.textContent = "A limpar dados…";
    try {
      const result = await api("/api/clear", { method: "POST", body: JSON.stringify({ module, confirm: module }) });
      $("#clear-result").innerHTML = `<div class="alert">Limpeza concluída. Foram apagados ${result.deleted_records.toLocaleString("pt-PT")} registos. Histórico de relatórios preservado.</div>`;
      state.table = ""; state.search = ""; $("#table-search").value = ""; await loadTables(); toast("Módulo limpo com sucesso.");
    } catch (err) { $("#clear-result").innerHTML = `<div class="alert error">${esc(err.message)}</div>`; }
    finally { button.disabled = false; button.textContent = `Apagar todos os registos de ${labels[module]}`; }
  });
  $("#table-search").addEventListener("input", () => { state.search = $("#table-search").value; state.pageNo = 1; if (state.table) loadRows(); });
  await loadTables();
}
async function loadTables() {
  const data = await api(`/api/tables?module=${encodeURIComponent(state.module)}`);
  $("#table-catalogue").innerHTML = panel(`${labels[state.module]} · ${data.tables.length} tabelas`, `<div class="table-list">${data.tables.map(t => `<button class="table-item" style="text-align:left;background:#fff;cursor:pointer" data-table="${esc(t.name)}"><strong>${esc(t.name)}</strong><p>${t.count.toLocaleString("pt-PT")} registos · ${t.columns.length} colunas · ${t.foreign_keys.length} chaves estrangeiras</p></button>`).join("")}</div>`);
  $("#table-catalogue").querySelectorAll("[data-table]").forEach(b => b.addEventListener("click", () => { state.table = b.dataset.table; state.pageNo = 1; loadRows(); }));
  if (state.table && data.tables.some(t => t.name === state.table)) await loadRows();
  else $("#rows-panel").innerHTML = "";
}
async function loadRows() {
  if (!state.table) return;
  const data = await api(`/api/rows?module=${encodeURIComponent(state.module)}&table=${encodeURIComponent(state.table)}&search=${encodeURIComponent(state.search)}&page=${state.pageNo}`);
  $("#rows-panel").innerHTML = panel(`Tabela: ${esc(state.table)}`, `<p class="muted">${data.total.toLocaleString("pt-PT")} registos encontrados · página ${data.page}</p><div class="table-wrap"><table><thead><tr>${data.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${data.rows.length ? data.rows.map(row => `<tr>${data.columns.map(c => `<td>${esc(row[c])}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${data.columns.length}" class="empty">Não existem registos nesta pesquisa.</td></tr>`}</tbody></table></div><div style="display:flex;justify-content:space-between;align-items:center;margin-top:15px"><span class="muted">Máximo de 50 registos por página</span><div><button class="btn" id="prev-page" ${data.page <= 1 ? "disabled" : ""}>← Anterior</button> <button class="btn" id="next-page" ${data.page * data.page_size >= data.total ? "disabled" : ""}>Seguinte →</button></div></div>`);
  $("#prev-page").addEventListener("click", () => { state.pageNo--; loadRows(); });
  $("#next-page").addEventListener("click", () => { state.pageNo++; loadRows(); });
}
async function reportsPage() {
  header("Relatórios");
  const data = await api("/api/reports");
  const reports = data.reports;
  view.innerHTML = panel(`Histórico de execuções · ${reports.length}`, reports.length ? reports.map(r => `<div class="report"><div class="report-top"><div><h3>${esc(labels[r.modulo] || r.modulo)} - ${esc(r.quantidade)} registos principais</h3><p>${esc(r.criada_em)} · Base: ${esc(r.detalhes.database_file)} · Total inserido: ${r.total_registos}</p><p>${Object.entries(r.detalhes.table_counts || r.detalhes.deleted_counts || {}).map(([t, n]) => `${esc(t)}: ${n}`).join(" · ")}</p><p>${r.detalhes.source ? `Origem: ${esc(r.detalhes.source)}` : ""}${r.origem === "limpeza" ? "Limpeza de dados" : esc(r.origem || "")}</p></div><span class="tag">${esc(r.estado)}</span></div></div>`).join("") : `<div class="empty">Ainda não existem execuções. Gera dados para criar o primeiro relatório.</div>`);
}
document.addEventListener("click", e => {
  const nav = e.target.closest("[data-page]");
  if (nav) go(nav.dataset.page);
  const action = e.target.closest("[data-action]")?.dataset.action;
  if (action === "generate") go("generate");
  if (action === "module-shop") { state.module = "loja_db"; go("tables"); }
  if (action === "module-school") { state.module = "escola_db"; go("tables"); }
});
(async () => { try { await api("/api/health"); $("#api-status").textContent = "API activa"; } catch { $("#api-status").textContent = "API indisponível"; } render(); })();
